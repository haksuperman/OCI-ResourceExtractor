import json
import os
import time
from datetime import datetime

import common
from collectors import (
    adb,
    block_storage,
    compute,
    dbcs,
    dns,
    fastconnect,
    file_storage,
    load_balancer,
    mysql,
    network_load_balancer,
    object_storage,
    vcn,
    vpn,
    waf,
    waf_edge,
)
from formatters import formatter_base
from log_utils import log_event


SERVICE_REGISTRY = [
    {"name": "compute", "scope": "regional", "collector": compute.collect},
    {"name": "vcn", "scope": "regional", "collector": vcn.collect},
    {"name": "waf", "scope": "regional", "collector": waf.collect},
    {"name": "waf_edge", "scope": "regional", "collector": waf_edge.collect},
    {"name": "mysql", "scope": "regional", "collector": mysql.collect},
    {"name": "dbcs", "scope": "regional", "collector": dbcs.collect},
    {"name": "adb", "scope": "regional", "collector": adb.collect},
    {"name": "vpn", "scope": "regional", "collector": vpn.collect},
    {"name": "fastconnect", "scope": "regional", "collector": fastconnect.collect},
    {"name": "file_storage", "scope": "regional", "collector": file_storage.collect},
    {"name": "block_storage", "scope": "regional", "collector": block_storage.collect},
    {"name": "object_storage", "scope": "regional", "collector": object_storage.collect},
    {"name": "load_balancer", "scope": "regional", "collector": load_balancer.collect},
    {
        "name": "network_load_balancer",
        "scope": "regional",
        "collector": network_load_balancer.collect,
    },
    {"name": "dns", "scope": "global", "collector": dns.collect},
]


def _notify(callback, payload):
    if callback:
        callback(dict(payload))


def _emit(callback, level, service, event, **fields):
    log_event(level, service, event, **fields)
    payload = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "level": level.upper(),
        "service": service,
        "event": event,
    }
    payload.update(fields)
    _notify(callback, payload)


def _read_collected_data(path, progress_callback=None):
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        _emit(
            progress_callback,
            "WARN",
            "runner",
            "collected_data_read_failed",
            message="Failed to parse collected json for merge",
            detail=str(e),
            path=path,
        )
        return []


def _is_readable_json_list(path, progress_callback=None):
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return isinstance(data, list)
    except Exception as e:
        _emit(
            progress_callback,
            "WARN",
            "runner",
            "collected_json_validation_failed",
            message="Collected json is not readable as list",
            detail=str(e),
            path=path,
        )
        return False


def _write_merged_data(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, default=str, ensure_ascii=False)


def _default_raw_path(profile_name, service_name):
    return os.path.join("raw_data", profile_name, f"{service_name}_{profile_name}.json")


def _normalize_filter_values(values):
    if not values:
        return []
    if isinstance(values, str):
        return [item.strip() for item in values.split(",") if item.strip()]
    return [str(item).strip() for item in values if str(item).strip()]


def _apply_runtime_scope_filter(client, regions=None, compartments=None, progress_callback=None):
    allowed_regions = set(_normalize_filter_values(regions))
    allowed_compartments = {
        item.lower() for item in _normalize_filter_values(compartments)
    }

    if not allowed_regions and not allowed_compartments:
        return

    original_regions = list(client.regions)
    original_compartments = list(client.compartments)

    if allowed_regions:
        client.regions = [region for region in client.regions if region in allowed_regions]

    if allowed_compartments:
        client.compartments = [
            compartment
            for compartment in client.compartments
            if getattr(compartment, "name", "").lower() in allowed_compartments
        ]

    _emit(
        progress_callback,
        "WARN",
        "runner",
        "runtime_scope_filter_applied",
        message="Runtime scope filter applied",
        profile=client.profile_name,
        regions=",".join(client.regions) if client.regions else "-",
        compartments=",".join(
            getattr(compartment, "name", "-") for compartment in client.compartments
        )
        if client.compartments
        else "-",
        original_region_count=len(original_regions),
        filtered_region_count=len(client.regions),
        original_compartment_count=len(original_compartments),
        filtered_compartment_count=len(client.compartments),
    )


def _service_entries(service_names=None):
    requested = set(_normalize_filter_values(service_names))
    if not requested:
        return list(SERVICE_REGISTRY)
    return [svc for svc in SERVICE_REGISTRY if svc["name"] in requested]


def run_inventory(profile_name, *, regions=None, compartments=None, service_names=None, progress_callback=None):
    profiles = common.get_profiles()
    if profile_name not in profiles:
        raise ValueError(f"OCI profile not found: {profile_name}")

    services_for_run = _service_entries(service_names)
    if not services_for_run:
        raise ValueError("No matching services selected")

    client = common.OCIClient(profile_name)
    _apply_runtime_scope_filter(client, regions, compartments, progress_callback)

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_start_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_start = time.time()
    result = {
        "run_id": run_id,
        "profile": profile_name,
        "tenancy_name": client.tenancy_name,
        "tenancy_id": client.tenancy_id,
        "started_at": run_start_ts,
        "finished_at": None,
        "duration_ms": None,
        "report_path": f"OCI_Reports/OCI_Report_{profile_name}.xlsx",
        "json_paths": {},
        "service_results": [],
    }

    _emit(
        progress_callback,
        "INFO",
        "runner",
        "run_start",
        message="OCI inventory run started",
        run_id=run_id,
        profile=profile_name,
        tenancy=client.tenancy_id,
        started_at=run_start_ts,
    )

    json_paths = {}
    regional_services = [
        (svc["name"], svc["collector"])
        for svc in services_for_run
        if svc["scope"] == "regional"
    ]
    global_services = [
        (svc["name"], svc["collector"])
        for svc in services_for_run
        if svc["scope"] == "global"
    ]
    services = [(svc["name"], svc["collector"]) for svc in services_for_run]

    all_regions = list(client.regions)
    merged_data_by_service = {name: [] for name, _ in services}
    output_path_by_service = {}
    successful_collection_by_service = {name: False for name, _ in services}

    for region in all_regions:
        _emit(
            progress_callback,
            "INFO",
            "runner",
            "region_start",
            message="Region execution started",
            step_region=region,
        )
        client.regions = [region]

        for service_name, service_func in regional_services:
            step_result = _run_service_step(
                client,
                service_name,
                service_func,
                region,
                merged_data_by_service,
                output_path_by_service,
                successful_collection_by_service,
                progress_callback,
            )
            result["service_results"].append(step_result)

        _emit(
            progress_callback,
            "INFO",
            "runner",
            "region_end",
            message="Region execution finished",
            step_region=region,
        )

    if global_services:
        _emit(
            progress_callback,
            "INFO",
            "runner",
            "global_services_start",
            message="Global service collection started",
        )

    for service_name, service_func in global_services:
        client.regions = all_regions
        step_result = _run_service_step(
            client,
            service_name,
            service_func,
            "global",
            merged_data_by_service,
            output_path_by_service,
            successful_collection_by_service,
            progress_callback,
            global_service=True,
        )
        result["service_results"].append(step_result)

    if global_services:
        _emit(
            progress_callback,
            "INFO",
            "runner",
            "global_services_end",
            message="Global service collection finished",
        )

    client.regions = all_regions

    for service_name, _ in services:
        merged_rows = merged_data_by_service.get(service_name, [])
        output_path = output_path_by_service.get(
            service_name,
            _default_raw_path(profile_name, service_name),
        )
        if not successful_collection_by_service.get(service_name):
            _emit(
                progress_callback,
                "ERROR",
                "runner",
                "service_merge_skipped",
                message="No successful collection output found; existing raw data was preserved",
                step_service=service_name,
                path=output_path,
            )
            continue

        _write_merged_data(output_path, merged_rows)
        json_paths[service_name] = output_path
        _emit(
            progress_callback,
            "INFO",
            "runner",
            "service_merge_written",
            message="Merged service raw data written",
            step_service=service_name,
            collected=len(merged_rows),
            path=output_path,
        )

    formatter_base.create_report(
        profile_name,
        json_paths,
        tenancy_name=client.tenancy_name,
        extracted_at=run_start_ts,
    )

    run_duration_ms = int((time.time() - run_start) * 1000)
    result["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result["duration_ms"] = run_duration_ms
    result["json_paths"] = dict(json_paths)

    _emit(
        progress_callback,
        "INFO",
        "runner",
        "run_end",
        message="OCI inventory run finished",
        run_id=run_id,
        duration_ms=run_duration_ms,
        report=result["report_path"],
    )
    return result


def _run_service_step(
    client,
    service_name,
    service_func,
    region,
    merged_data_by_service,
    output_path_by_service,
    successful_collection_by_service,
    progress_callback,
    *,
    global_service=False,
):
    step_start = time.time()
    step_message = (
        "Global service collection step started"
        if global_service
        else "Service collection step started"
    )
    _emit(
        progress_callback,
        "INFO",
        "runner",
        "step_start",
        message=step_message,
        step_service=service_name,
        step_region=region,
    )

    errors = 0
    skipped = "0"
    collected = 0
    output_path = None
    detail = ""

    try:
        output_path = service_func(client)
        if output_path:
            output_path_by_service[service_name] = output_path
        if _is_readable_json_list(output_path, progress_callback):
            successful_collection_by_service[service_name] = True
        collected_rows = _read_collected_data(output_path, progress_callback)
        collected = len(collected_rows)
        merged_data_by_service[service_name].extend(collected_rows)
        if collected == 0:
            skipped = "1(no_data)"
    except Exception as e:
        errors = 1
        skipped = "1(error)"
        detail = str(e)
        failed_message = (
            "Global service collection step failed"
            if global_service
            else "Service collection step failed"
        )
        _emit(
            progress_callback,
            "ERROR",
            "runner",
            "service_run_failed",
            message=failed_message,
            step_service=service_name,
            step_region=region,
            detail=detail,
        )

    duration_ms = int((time.time() - step_start) * 1000)
    finished_message = (
        "Global service collection step finished"
        if global_service
        else "Service collection step finished"
    )
    _emit(
        progress_callback,
        "INFO",
        "runner",
        "step_end",
        message=finished_message,
        step_service=service_name,
        step_region=region,
        collected=collected,
        errors=errors,
        skipped=skipped,
        duration_ms=duration_ms,
    )

    return {
        "service": service_name,
        "region": region,
        "collected": collected,
        "errors": errors,
        "skipped": skipped,
        "duration_ms": duration_ms,
        "output_path": output_path,
        "detail": detail,
    }

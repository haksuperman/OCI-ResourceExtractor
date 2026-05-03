import common
from collectors import compute, waf, waf_edge, dns, mysql, dbcs, adb, vpn, vcn, file_storage, block_storage, load_balancer, network_load_balancer, object_storage, fastconnect
from formatters import formatter_base
import json
import os
import time
from datetime import datetime
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


def _read_collected_count(path):
    if not path or not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return len(data) if isinstance(data, list) else 0
    except Exception as e:
        log_event(
            "WARN",
            "runner",
            "collected_count_read_failed",
            message="Failed to parse collected json for count",
            detail=str(e),
            path=path,
        )
        return 0


def _read_collected_data(path):
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception as e:
        log_event(
            "WARN",
            "runner",
            "collected_data_read_failed",
            message="Failed to parse collected json for merge",
            detail=str(e),
            path=path,
        )
        return []


def _is_readable_json_list(path):
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return isinstance(data, list)
    except Exception as e:
        log_event(
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


def _select_profile(profiles):
    val = input("\nSelect number: ").strip()
    if val.isdigit():
        idx = int(val) - 1
        if 0 <= idx < len(profiles):
            return profiles[idx]
        log_event(
            "ERROR",
            "runner",
            "invalid_profile_selection",
            message="Selected profile number is out of range",
            selection=val,
            profile_count=len(profiles),
        )
        return None

    if val in profiles:
        return val

    log_event(
        "ERROR",
        "runner",
        "invalid_profile_selection",
        message="Selected profile name was not found in OCI config",
        selection=val,
    )
    return None


def main():
    profiles = common.get_profiles()
    if not profiles:
        log_event("ERROR", "runner", "profiles_not_found", message="No OCI profiles found")
        return

    print("\n--- Select OCI Profile ---")
    for i, p in enumerate(profiles):
        print(f"{i+1}. {p}")
    
    try:
        selected_profile = _select_profile(profiles)
        if not selected_profile:
            return
        
        # 1. 클라이언트 초기화
        client = common.OCIClient(selected_profile)
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        run_start_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_start = time.time()
        log_event(
            "INFO",
            "runner",
            "run_start",
            message="OCI inventory run started",
            run_id=run_id,
            profile=selected_profile,
            tenancy=client.tenancy_id,
            started_at=run_start_ts,
        )
        
        # 2. 서비스별 데이터 수집
        json_paths = {}

        regional_services = [
            (svc["name"], svc["collector"])
            for svc in SERVICE_REGISTRY
            if svc["scope"] == "regional"
        ]
        global_services = [
            (svc["name"], svc["collector"])
            for svc in SERVICE_REGISTRY
            if svc["scope"] == "global"
        ]
        services = [(svc["name"], svc["collector"]) for svc in SERVICE_REGISTRY]

        all_regions = list(client.regions)
        merged_data_by_service = {name: [] for name, _ in services}
        output_path_by_service = {}
        successful_collection_by_service = {name: False for name, _ in services}

        # showoci-style: region -> services (regional services only)
        for region in all_regions:
            log_event(
                "INFO",
                "runner",
                "region_start",
                message="Region execution started",
                step_region=region,
            )
            client.regions = [region]

            for service_name, service_func in regional_services:
                step_start = time.time()
                log_event(
                    "INFO",
                    "runner",
                    "step_start",
                    message="Service collection step started",
                    step_service=service_name,
                    step_region=region,
                )
                errors = 0
                skipped = "0"
                collected = 0
                output_path = None

                try:
                    output_path = service_func(client)
                    if output_path:
                        output_path_by_service[service_name] = output_path
                    if _is_readable_json_list(output_path):
                        successful_collection_by_service[service_name] = True
                    collected_rows = _read_collected_data(output_path)
                    collected = len(collected_rows)
                    merged_data_by_service[service_name].extend(collected_rows)
                    if collected == 0:
                        skipped = "1(no_data)"
                except Exception as e:
                    errors = 1
                    skipped = "1(error)"
                    log_event(
                        "ERROR",
                        "runner",
                        "service_run_failed",
                        message="Service collection step failed",
                        step_service=service_name,
                        step_region=region,
                        detail=str(e),
                    )

                duration_ms = int((time.time() - step_start) * 1000)
                log_event(
                    "INFO",
                    "runner",
                    "step_end",
                    message="Service collection step finished",
                    step_service=service_name,
                    step_region=region,
                    collected=collected,
                    errors=errors,
                    skipped=skipped,
                    duration_ms=duration_ms,
                )

            log_event(
                "INFO",
                "runner",
                "region_end",
                message="Region execution finished",
                step_region=region,
            )

        # Global services run once to avoid N(region)-times duplicate collection.
        if global_services:
            log_event(
                "INFO",
                "runner",
                "global_services_start",
                message="Global service collection started",
            )
        for service_name, service_func in global_services:
            step_start = time.time()
            log_event(
                "INFO",
                "runner",
                "step_start",
                message="Global service collection step started",
                step_service=service_name,
                step_region="global",
            )
            errors = 0
            skipped = "0"
            collected = 0
            output_path = None

            try:
                client.regions = all_regions
                output_path = service_func(client)
                if output_path:
                    output_path_by_service[service_name] = output_path
                if _is_readable_json_list(output_path):
                    successful_collection_by_service[service_name] = True
                collected_rows = _read_collected_data(output_path)
                collected = len(collected_rows)
                merged_data_by_service[service_name].extend(collected_rows)
                if collected == 0:
                    skipped = "1(no_data)"
            except Exception as e:
                errors = 1
                skipped = "1(error)"
                log_event(
                    "ERROR",
                    "runner",
                    "service_run_failed",
                    message="Global service collection step failed",
                    step_service=service_name,
                    step_region="global",
                    detail=str(e),
                )

            duration_ms = int((time.time() - step_start) * 1000)
            log_event(
                "INFO",
                "runner",
                "step_end",
                message="Global service collection step finished",
                step_service=service_name,
                step_region="global",
                collected=collected,
                errors=errors,
                skipped=skipped,
                duration_ms=duration_ms,
            )
        if global_services:
            log_event(
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
                _default_raw_path(selected_profile, service_name),
            )
            if not successful_collection_by_service.get(service_name):
                log_event(
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
            log_event(
                "INFO",
                "runner",
                "service_merge_written",
                message="Merged service raw data written",
                step_service=service_name,
                collected=len(merged_rows),
                path=output_path,
            )
        
        # 3. 엑셀 리포트 생성
        formatter_base.create_report(
            selected_profile,
            json_paths,
            tenancy_name=client.tenancy_name,
            extracted_at=run_start_ts
        )
        run_duration_ms = int((time.time() - run_start) * 1000)
        report_path = f"OCI_Reports/OCI_Report_{selected_profile}.xlsx"
        log_event(
            "INFO",
            "runner",
            "run_end",
            message="OCI inventory run finished",
            run_id=run_id,
            duration_ms=run_duration_ms,
            report=report_path,
        )
        
    except Exception as e:
        log_event("ERROR", "runner", "run_exception", detail=str(e))

if __name__ == "__main__":
    main()

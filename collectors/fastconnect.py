import json
import os

import oci

import common
from log_utils import log_event


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "fastconnect",
        event,
        region=region,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def _to_dict(obj):
    if obj is None:
        return {}
    return oci.util.to_dict(obj)


def _list_data(list_call, error_list, error_count_ref, err_label, **kwargs):
    try:
        return common.list_call_get_all_results(list_call, **kwargs).data
    except Exception as e:
        error_count_ref[0] += 1
        error_list.append(f"{err_label}: {e}")
        return []


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting FastConnect virtual circuits")
    all_fastconnect = []
    total_count = 0
    error_count = 0

    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config["region"] = region

        network_client = common.create_client(oci.core.VirtualNetworkClient, config)
        drg_cache = {}
        provider_cache = {}

        for comp in client.compartments:
            comp_name = comp.name

            try:
                circuits = common.list_call_get_all_results(
                    network_client.list_virtual_circuits,
                    compartment_id=comp.id,
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "virtual_circuits_listed",
                    count=len(circuits),
                )
            except oci.exceptions.ServiceError as e:
                error_count += 1
                if e.status == 404:
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "virtual_circuit_listing_not_authorized_or_not_found",
                        detail=common.service_error_detail(e),
                        status=e.status,
                        code=getattr(e, "code", None),
                        message=getattr(e, "message", str(e)),
                    )
                else:
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "virtual_circuit_listing_failed",
                        detail=common.service_error_detail(e),
                        status=e.status,
                        code=getattr(e, "code", None),
                        message=getattr(e, "message", str(e)),
                    )
                continue
            except Exception as e:
                error_count += 1
                _log(
                    "ERROR",
                    region,
                    comp_name,
                    "virtual_circuit_listing_unexpected_error",
                    detail=str(e),
                )
                continue

            try:
                bandwidth_shapes = common.list_call_get_all_results(
                    network_client.list_virtual_circuit_bandwidth_shapes,
                    compartment_id=comp.id,
                ).data
                bandwidth_shape_dicts = [_to_dict(shape) for shape in bandwidth_shapes]
                bandwidth_shape_error = None
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "bandwidth_shapes_listed",
                    count=len(bandwidth_shape_dicts),
                )
            except Exception as e:
                error_count += 1
                bandwidth_shape_dicts = []
                bandwidth_shape_error = str(e)
                _log(
                    "WARN",
                    region,
                    comp_name,
                    "bandwidth_shapes_listing_failed",
                    detail=str(e),
                )

            for circuit in circuits:
                total_count += 1
                circuit_id = getattr(circuit, "id", None)

                resource = {
                    "fastconnect_raw": _to_dict(circuit),
                    "fastconnect_enriched": {
                        "public_prefixes": [],
                        "cross_connect_mappings": [],
                        "associated_tunnels": [],
                        "provider_service_details": {},
                        "provider_service_key_details": {},
                        "bandwidth_shapes": [],
                    },
                    "networking_enriched": {"drg_details": {}},
                    "_errors": [],
                }
                fc_raw = resource["fastconnect_raw"]
                fc_enriched = resource["fastconnect_enriched"]
                net_enriched = resource["networking_enriched"]
                errors = resource["_errors"]

                fc_raw["region_name"] = region
                fc_raw["compartment_name"] = comp_name

                try:
                    detail = common.call_with_retry(
                        network_client.get_virtual_circuit,
                        virtual_circuit_id=circuit_id,
                    ).data
                    fc_raw = _to_dict(detail)
                    fc_raw["region_name"] = region
                    fc_raw["compartment_name"] = comp_name
                    resource["fastconnect_raw"] = fc_raw
                except Exception as e:
                    error_count += 1
                    errors.append(f"virtual circuit detail fetch failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "virtual_circuit_detail_fetch_failed",
                        resource_id=circuit_id,
                        detail=str(e),
                    )

                drg_id = fc_raw.get("gateway_id")
                if drg_id:
                    if drg_id not in drg_cache:
                        try:
                            drg_cache[drg_id] = _to_dict(
                                common.call_with_retry(network_client.get_drg, drg_id).data
                            )
                        except Exception as e:
                            error_count += 1
                            drg_cache[drg_id] = {"id": drg_id}
                            errors.append(f"drg fetch failed ({drg_id}): {e}")
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "drg_fetch_failed",
                                resource_id=circuit_id,
                                detail=str(e),
                            )
                    net_enriched["drg_details"] = drg_cache[drg_id]

                provider_service_id = fc_raw.get("provider_service_id")
                if provider_service_id:
                    if provider_service_id not in provider_cache:
                        try:
                            provider_cache[provider_service_id] = _to_dict(
                                common.call_with_retry(
                                    network_client.get_fast_connect_provider_service,
                                    provider_service_id=provider_service_id,
                                ).data
                            )
                        except Exception as e:
                            error_count += 1
                            provider_cache[provider_service_id] = {"id": provider_service_id}
                            errors.append(
                                f"provider service fetch failed ({provider_service_id}): {e}"
                            )
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "provider_service_fetch_failed",
                                resource_id=circuit_id,
                                detail=str(e),
                            )
                    fc_enriched["provider_service_details"] = provider_cache[provider_service_id]

                provider_key_name = fc_raw.get("provider_service_key_name")
                if provider_service_id and provider_key_name:
                    try:
                        provider_key = common.call_with_retry(
                            network_client.get_fast_connect_provider_service_key,
                            provider_service_id=provider_service_id,
                            provider_service_key_name=provider_key_name,
                        ).data
                        fc_enriched["provider_service_key_details"] = _to_dict(provider_key)
                    except Exception as e:
                        error_count += 1
                        errors.append(
                            f"provider service key fetch failed ({provider_key_name}): {e}"
                        )
                        _log(
                            "WARN",
                            region,
                            comp_name,
                            "provider_service_key_fetch_failed",
                            resource_id=circuit_id,
                            detail=str(e),
                        )

                err_ref = [0]
                public_prefixes = _list_data(
                    network_client.list_virtual_circuit_public_prefixes,
                    errors,
                    err_ref,
                    "public prefixes listing failed",
                    virtual_circuit_id=circuit_id,
                )
                cross_connect_mappings = _list_data(
                    network_client.list_cross_connect_mappings,
                    errors,
                    err_ref,
                    "cross connect mappings listing failed",
                    virtual_circuit_id=circuit_id,
                )
                associated_tunnels = _list_data(
                    network_client.list_virtual_circuit_associated_tunnels,
                    errors,
                    err_ref,
                    "associated tunnels listing failed",
                    virtual_circuit_id=circuit_id,
                )
                error_count += err_ref[0]
                if bandwidth_shape_error:
                    errors.append(f"bandwidth shapes listing failed: {bandwidth_shape_error}")

                fc_enriched["public_prefixes"] = [_to_dict(x) for x in public_prefixes]
                fc_enriched["cross_connect_mappings"] = [
                    _to_dict(x) for x in cross_connect_mappings
                ]
                fc_enriched["associated_tunnels"] = [_to_dict(x) for x in associated_tunnels]
                fc_enriched["bandwidth_shapes"] = bandwidth_shape_dicts

                all_fastconnect.append(resource)

    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"fastconnect_{client.profile_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_fastconnect, f, indent=4, default=str, ensure_ascii=False)
    return output_path

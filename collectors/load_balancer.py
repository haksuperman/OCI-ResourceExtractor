import json
import os

import oci
import common
from log_utils import log_event


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "load_balancer",
        event,
        region=region,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def _map_to_list(obj, key_name):
    if not isinstance(obj, dict):
        return []
    rows = []
    for key, value in obj.items():
        if isinstance(value, dict):
            item = value.copy()
            item[key_name] = key
            rows.append(item)
    return rows


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting Load Balancers")
    all_lbs = []
    total_count = 0
    error_count = 0

    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config["region"] = region
        lb_client = common.create_client(oci.load_balancer.LoadBalancerClient, config)
        network_client = common.create_client(oci.core.VirtualNetworkClient, config)
        subnet_cache = {}
        nsg_cache = {}

        for comp in client.compartments:
            comp_name = comp.name
            try:
                lbs = common.list_call_get_all_results(
                    lb_client.list_load_balancers, compartment_id=comp.id
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "load_balancers_listed",
                    count=len(lbs),
                )
            except Exception as e:
                error_count += 1
                _log(
                    "ERROR",
                    region,
                    comp_name,
                    "load_balancer_listing_failed",
                    detail=str(e),
                )
                continue

            for lb in lbs:
                total_count += 1

                resource = {
                    "load_balancer_raw": {
                        "id": getattr(lb, "id", None),
                        "display_name": getattr(lb, "display_name", None),
                        "lifecycle_state": getattr(lb, "lifecycle_state", None),
                        "region_name": region,
                        "compartment_name": comp_name,
                    },
                    "load_balancer_enriched": {
                        "listeners_list": [],
                        "backend_sets_list": [],
                        "hostnames_list": [],
                        "path_route_sets_list": [],
                        "certificates_list": [],
                    },
                    "networking_enriched": {
                        "subnet_details": [],
                        "nsg_details": [],
                    },
                    "_errors": [],
                }
                lb_raw = resource["load_balancer_raw"]
                lb_enriched = resource["load_balancer_enriched"]
                networking_enriched = resource["networking_enriched"]

                try:
                    detail = common.call_with_retry(lb_client.get_load_balancer, lb.id).data
                    lb_raw = oci.util.to_dict(detail)
                    lb_raw["region_name"] = region
                    lb_raw["compartment_name"] = comp_name
                    resource["load_balancer_raw"] = lb_raw
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(f"load balancer detail fetch failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "load_balancer_detail_fetch_failed",
                        resource_id=lb.id,
                        detail=str(e),
                    )

                # formatter가 안정적으로 쓰도록 map 객체들을 list 형태로 병행 저장
                lb_enriched["listeners_list"] = _map_to_list(
                    lb_raw.get("listeners"), "listener_name"
                )
                lb_enriched["backend_sets_list"] = _map_to_list(
                    lb_raw.get("backend_sets"), "backend_set_name"
                )
                lb_enriched["hostnames_list"] = _map_to_list(
                    lb_raw.get("hostnames"), "hostname_name"
                )
                lb_enriched["path_route_sets_list"] = _map_to_list(
                    lb_raw.get("path_route_sets"), "path_route_set_name"
                )
                lb_enriched["certificates_list"] = _map_to_list(
                    lb_raw.get("certificates"), "certificate_name"
                )

                networking_enriched["subnet_details"] = []
                for subnet_id in lb_raw.get("subnet_ids", []) or []:
                    if subnet_id not in subnet_cache:
                        try:
                            subnet_cache[subnet_id] = oci.util.to_dict(
                                common.call_with_retry(network_client.get_subnet, subnet_id).data
                            )
                        except Exception as e:
                            error_count += 1
                            subnet_cache[subnet_id] = {"id": subnet_id}
                            resource["_errors"].append(f"subnet fetch failed ({subnet_id}): {e}")
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "subnet_fetch_failed",
                                resource_id=lb_raw.get("id"),
                                detail=f"subnet_id={subnet_id} err={e}",
                            )
                    networking_enriched["subnet_details"].append(subnet_cache[subnet_id])

                networking_enriched["nsg_details"] = []
                for nsg_id in lb_raw.get("network_security_group_ids", []) or []:
                    if nsg_id not in nsg_cache:
                        try:
                            nsg_cache[nsg_id] = oci.util.to_dict(
                                common.call_with_retry(
                                    network_client.get_network_security_group,
                                    nsg_id,
                                ).data
                            )
                        except Exception as e:
                            error_count += 1
                            nsg_cache[nsg_id] = {"id": nsg_id}
                            resource["_errors"].append(f"nsg fetch failed ({nsg_id}): {e}")
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "nsg_fetch_failed",
                                resource_id=lb_raw.get("id"),
                                detail=f"nsg_id={nsg_id} err={e}",
                            )
                    networking_enriched["nsg_details"].append(nsg_cache[nsg_id])

                all_lbs.append(resource)

    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"load_balancer_{client.profile_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_lbs, f, indent=4, default=str, ensure_ascii=False)
    return output_path

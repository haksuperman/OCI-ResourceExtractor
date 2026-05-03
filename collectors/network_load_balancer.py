import json
import os

import oci
import common
from log_utils import log_event


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "network_load_balancer",
        event,
        region=region,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting Network Load Balancers")
    all_nlbs = []
    total_count = 0
    error_count = 0

    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config["region"] = region
        nlb_client = common.create_client(oci.network_load_balancer.NetworkLoadBalancerClient, config)
        network_client = common.create_client(oci.core.VirtualNetworkClient, config)
        subnet_cache = {}
        nsg_cache = {}

        for comp in client.compartments:
            comp_name = comp.name
            try:
                nlbs = common.list_call_get_all_results(
                    nlb_client.list_network_load_balancers,
                    compartment_id=comp.id,
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "network_load_balancers_listed",
                    count=len(nlbs),
                )
            except Exception as e:
                error_count += 1
                _log(
                    "ERROR",
                    region,
                    comp_name,
                    "network_load_balancer_listing_failed",
                    detail=str(e),
                )
                continue

            for nlb in nlbs:
                total_count += 1

                nlb_id = getattr(nlb, "id", None)
                resource = {
                    "network_load_balancer_raw": oci.util.to_dict(nlb),
                    "network_load_balancer_enriched": {
                        "listeners_list": [],
                        "backend_sets_list": [],
                    },
                    "networking_enriched": {
                        "subnet_details": None,
                        "nsg_details": [],
                    },
                    "_errors": [],
                }
                nlb_raw = resource["network_load_balancer_raw"]
                nlb_enriched = resource["network_load_balancer_enriched"]
                networking_enriched = resource["networking_enriched"]
                nlb_raw["region_name"] = region
                nlb_raw["compartment_name"] = comp_name

                # 상세 조회
                try:
                    detail = common.call_with_retry(
                        nlb_client.get_network_load_balancer,
                        network_load_balancer_id=nlb_id,
                    ).data
                    nlb_raw = oci.util.to_dict(detail)
                    nlb_raw["region_name"] = region
                    nlb_raw["compartment_name"] = comp_name
                    resource["network_load_balancer_raw"] = nlb_raw
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(f"detail fetch failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "network_load_balancer_detail_fetch_failed",
                        resource_id=nlb_id,
                        detail=str(e),
                    )

                subnet_id = nlb_raw.get("subnet_id")
                if subnet_id:
                    if subnet_id not in subnet_cache:
                        try:
                            subnet_cache[subnet_id] = oci.util.to_dict(
                                common.call_with_retry(
                                    network_client.get_subnet, subnet_id
                                ).data
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
                                resource_id=nlb_id,
                                detail=f"subnet_id={subnet_id} err={e}",
                            )
                    networking_enriched["subnet_details"] = subnet_cache[subnet_id]

                networking_enriched["nsg_details"] = []
                for nsg_id in nlb_raw.get("network_security_group_ids", []) or []:
                    if nsg_id not in nsg_cache:
                        try:
                            nsg_cache[nsg_id] = oci.util.to_dict(
                                common.call_with_retry(
                                    network_client.get_network_security_group, nsg_id
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
                                resource_id=nlb_id,
                                detail=f"nsg_id={nsg_id} err={e}",
                            )
                    networking_enriched["nsg_details"].append(nsg_cache[nsg_id])

                # listeners
                try:
                    listeners = common.list_call_get_all_results(
                        nlb_client.list_listeners,
                        network_load_balancer_id=nlb_id,
                    ).data
                    nlb_enriched["listeners_list"] = [oci.util.to_dict(x) for x in listeners]
                except Exception as e:
                    error_count += 1
                    nlb_enriched["listeners_list"] = []
                    resource["_errors"].append(f"listeners listing failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "listeners_listing_failed",
                        resource_id=nlb_id,
                        detail=str(e),
                    )

                # backend sets + backends
                backend_sets_list = []
                try:
                    backend_sets = common.list_call_get_all_results(
                        nlb_client.list_backend_sets,
                        network_load_balancer_id=nlb_id,
                    ).data
                    for bs in backend_sets:
                        bs_dict = oci.util.to_dict(bs)
                        bs_name = bs_dict.get("name")
                        try:
                            backends = common.list_call_get_all_results(
                                nlb_client.list_backends,
                                network_load_balancer_id=nlb_id,
                                backend_set_name=bs_name,
                            ).data
                            bs_dict["backends"] = [oci.util.to_dict(x) for x in backends]
                        except Exception as e:
                            error_count += 1
                            bs_dict["backends"] = []
                            resource["_errors"].append(
                                f"backends listing failed (backend_set={bs_name}): {e}"
                            )
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "backends_listing_failed",
                                resource_id=nlb_id,
                                detail=f"backend_set={bs_name} err={e}",
                            )
                        backend_sets_list.append(bs_dict)
                    nlb_enriched["backend_sets_list"] = backend_sets_list
                except Exception as e:
                    error_count += 1
                    nlb_enriched["backend_sets_list"] = []
                    resource["_errors"].append(f"backend sets listing failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "backend_sets_listing_failed",
                        resource_id=nlb_id,
                        detail=str(e),
                    )

                all_nlbs.append(resource)

    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(
        output_dir, f"network_load_balancer_{client.profile_name}.json"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_nlbs, f, indent=4, default=str, ensure_ascii=False)
    return output_path

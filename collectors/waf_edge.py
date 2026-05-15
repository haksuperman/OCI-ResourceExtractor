import json
import os

import oci
import common
from log_utils import log_event


def _log(level, region, compartment, event, policy_id="-", detail="", **fields):
    log_event(
        level,
        "waf_edge",
        event,
        region=region,
        compartment=compartment,
        resource=policy_id,
        detail=detail,
        **fields,
    )


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting WAF Edge (WAAS) Policies")
    all_edge_policies = []
    error_count = 0
    total_count = 0

    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config["region"] = region
        waas_client = common.create_client(oci.waas.WaasClient, config)

        for comp in client.compartments:
            comp_name = comp.name
            try:
                edge_policies = common.list_call_get_all_results(
                    waas_client.list_waas_policies, comp.id
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "waas_policies_listed",
                    count=len(edge_policies),
                )
            except oci.exceptions.ServiceError as e:
                error_count += 1
                if e.status == 404:
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "waas_policy_listing_not_authorized_or_not_found",
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
                        "waas_policy_listing_failed",
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
                    "waas_policy_listing_unexpected_error",
                    detail=str(e),
                )
                continue

            for edge_policy in edge_policies:
                edge_policy_id = getattr(edge_policy, "id", None)
                total_count += 1
                edge_dict = oci.util.to_dict(edge_policy)
                edge_dict["region_name"] = region
                edge_dict["compartment_name"] = comp_name
                edge_dict["resource_type"] = "waas_policy"
                edge_dict["_errors"] = []
                edge_detail = None

                try:
                    edge_detail = common.call_with_retry(
                        waas_client.get_waas_policy,
                        waas_policy_id=edge_policy_id
                    ).data
                    edge_dict.update(oci.util.to_dict(edge_detail))
                except Exception as e:
                    error_count += 1
                    edge_dict["_errors"].append(f"waas policy detail fetch failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "waas_policy_detail_fetch_failed",
                        policy_id=edge_policy_id or "-",
                        detail=str(e),
                    )

                # Root cause fix:
                # custom_protection_rules are included in get_waas_policy().waf_config.
                # Avoid extra list API call that returns 404(NotAuthorizedOrNotFound) in some tenancies.
                waf_cfg = getattr(edge_detail, "waf_config", None) if edge_detail else None
                custom_rules = getattr(waf_cfg, "custom_protection_rules", None) if waf_cfg else None
                edge_dict["custom_protection_rules"] = [
                    oci.util.to_dict(rule) for rule in (custom_rules or [])
                ]
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "waas_custom_protection_rules_loaded_from_policy_detail",
                    policy_id=edge_policy_id or "-",
                    count=len(edge_dict["custom_protection_rules"]),
                )

                resource = {
                    "waf_edge_raw": {
                        k: v
                        for k, v in edge_dict.items()
                        if k not in {"_errors", "custom_protection_rules"}
                    },
                    "waf_edge_enriched": {
                        "custom_protection_rules": edge_dict.get("custom_protection_rules", []),
                    },
                    "_errors": edge_dict.get("_errors", []),
                }
                all_edge_policies.append(resource)

    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"waf_edge_{client.profile_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_edge_policies, f, indent=4, default=str, ensure_ascii=False)
    return output_path

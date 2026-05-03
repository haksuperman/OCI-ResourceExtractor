import json
import os

import oci
import common
from log_utils import log_event


def _log(level, region, compartment, event, policy_id="-", detail="", **fields):
    log_event(
        level,
        "waf",
        event,
        region=region,
        compartment=compartment,
        resource=policy_id,
        detail=detail,
        **fields,
    )

def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting WAF Policies")
    all_policies = []
    error_count = 0
    total_count = 0

    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config["region"] = region
        waf_client = common.create_client(oci.waf.WafClient, config)

        for comp in client.compartments:
            comp_name = comp.name
            try:
                policies = common.list_call_get_all_results(
                    waf_client.list_web_app_firewall_policies, comp.id
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "waf_policies_listed",
                    count=len(policies),
                )
            except oci.exceptions.ServiceError as e:
                if e.status != 404:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "policy_listing_failed",
                        detail=f"code={e.status} message={e.message}",
                    )
                policies = []
            except Exception as e:
                error_count += 1
                _log(
                    "ERROR",
                    region,
                    comp_name,
                    "policy_listing_unexpected_error",
                    detail=str(e),
                )
                policies = []

            for policy in policies:
                policy_id = policy.id
                policy_name = policy.display_name
                total_count += 1
                policy_dict = {
                    "id": policy_id,
                    "display_name": policy_name,
                    "region_name": region,
                    "compartment_name": comp_name,
                    "resource_type": "waf_policy",
                }
                policy_dict["_errors"] = []

                try:
                    full_policy = common.call_with_retry(
                        waf_client.get_web_app_firewall_policy, policy_id
                    ).data
                    policy_dict.update(oci.util.to_dict(full_policy))
                except Exception as e:
                    error_count += 1
                    detail = f"policy detail fetch failed: {e}"
                    policy_dict["_errors"].append(detail)
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "policy_detail_fetch_failed",
                        policy_id=policy_id,
                        detail=str(e),
                    )

                try:
                    firewalls = common.list_call_get_all_results(
                        waf_client.list_web_app_firewalls,
                        compartment_id=comp.id,
                        web_app_firewall_policy_id=policy_id,
                    ).data
                    policy_dict["firewalls"] = [oci.util.to_dict(f) for f in firewalls]
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "linked_firewalls_listed",
                        policy_id=policy_id,
                        count=len(policy_dict["firewalls"]),
                    )
                except Exception as e:
                    error_count += 1
                    policy_dict["firewalls"] = []
                    detail = f"linked firewalls listing failed: {e}"
                    policy_dict["_errors"].append(detail)
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "linked_firewalls_listing_failed",
                        policy_id=policy_id,
                        detail=str(e),
                    )

                resource = {
                    "waf_raw": {
                        k: v
                        for k, v in policy_dict.items()
                        if k not in {"_errors", "firewalls"}
                    },
                    "waf_enriched": {
                        "firewalls": policy_dict.get("firewalls", []),
                    },
                    "_errors": policy_dict.get("_errors", []),
                }
                all_policies.append(resource)

    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"waf_{client.profile_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_policies, f, indent=4, default=str, ensure_ascii=False)
    return output_path

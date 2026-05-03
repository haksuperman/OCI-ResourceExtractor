import oci
import common
import json
import os
from log_utils import log_event


def _log(level, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "dns",
        event,
        region="global",
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def collect(client):
    _log("INFO", "-", "collection_start", message="Collecting DNS Zones and Records")
    all_zones = []
    error_count = 0
    total_zone_count = 0
    
    dns_client = common.create_client(oci.dns.DnsClient, client.config)
    
    for comp in client.compartments:
        comp_name = comp.name
        try:
            zones = common.list_call_get_all_results(
                dns_client.list_zones,
                compartment_id=comp.id
            ).data
            _log(
                "INFO",
                comp_name,
                "zones_listed",
                count=len(zones),
            )
                
        except oci.exceptions.ServiceError as e:
            if e.status != 404:
                error_count += 1
                _log(
                    "WARN",
                    comp_name,
                    "zone_listing_failed",
                    detail=f"code={e.status} message={e.message}",
                )
            continue
        except Exception as e:
            error_count += 1
            _log(
                "ERROR",
                comp_name,
                "zone_listing_unexpected_error",
                detail=str(e),
            )
            continue

        for zone in zones:
            total_zone_count += 1
            resource = {
                "dns_raw": oci.util.to_dict(zone),
                "dns_enriched": {
                    "records": [],
                },
                "_errors": [],
            }
            zone_dict = resource["dns_raw"]
            zone_dict["compartment_name"] = comp_name
            zone_dict["region_name"] = "global"

            try:
                zone_detail = common.call_with_retry(
                    dns_client.get_zone,
                    zone_name_or_id=zone.id,
                    scope=zone.scope,
                    view_id=zone.view_id if zone.scope == "PRIVATE" else None,
                ).data
                zone_dict = oci.util.to_dict(zone_detail)
                zone_dict["compartment_name"] = comp_name
                zone_dict["region_name"] = "global"
                resource["dns_raw"] = zone_dict
            except Exception as e:
                error_count += 1
                resource["_errors"].append(f"zone detail fetch failed: {e}")
                _log(
                    "WARN",
                    comp_name,
                    "zone_detail_fetch_failed",
                    resource_id=zone.id,
                    detail=str(e),
                )

            try:
                response = common.list_call_get_all_results(
                    dns_client.get_zone_records,
                    zone_name_or_id=zone_dict.get("id", zone.id),
                    scope=zone_dict.get("scope", zone.scope),
                    view_id=zone_dict.get("view_id")
                    if zone_dict.get("scope", zone.scope) == "PRIVATE"
                    else None,
                )
                if response.data and hasattr(response.data, "items"):
                    records = response.data.items
                    resource["dns_enriched"]["records"] = [oci.util.to_dict(r) for r in records]
                    _log(
                        "INFO",
                        comp_name,
                        "zone_records_listed",
                        resource_id=zone.id,
                        count=len(resource["dns_enriched"]["records"]),
                    )
                else:
                    resource["dns_enriched"]["records"] = []
            except Exception as e:
                error_count += 1
                resource["dns_enriched"]["records"] = []
                resource["_errors"].append(f"record listing failed: {e}")
                _log(
                    "WARN",
                    comp_name,
                    "zone_records_listing_failed",
                    resource_id=zone.id,
                    detail=str(e),
                )

            all_zones.append(resource)
            
    _log("INFO", "-", "collection_end", collected=total_zone_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"dns_{client.profile_name}.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_zones, f, indent=4, default=str, ensure_ascii=False)
    return output_path

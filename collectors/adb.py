import json
import os

import oci
import common
from log_utils import log_event


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "adb",
        event,
        region=region,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def _list_all(list_call, **kwargs):
    return common.list_call_get_all_results(list_call, **kwargs).data


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting Autonomous Databases")
    all_adbs = []
    total_count = 0
    error_count = 0

    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config["region"] = region
        db_client = common.create_client(oci.database.DatabaseClient, config)
        network_client = common.create_client(oci.core.VirtualNetworkClient, config)
        subnet_cache = {}
        nsg_cache = {}

        for comp in client.compartments:
            comp_name = comp.name
            try:
                adbs = _list_all(
                    db_client.list_autonomous_databases,
                    compartment_id=comp.id,
                    sort_by="DISPLAYNAME",
                )
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "autonomous_databases_listed",
                    count=len(adbs),
                )
            except oci.exceptions.ServiceError as e:
                error_count += 1
                if e.status == 404:
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "autonomous_database_listing_not_authorized_or_not_found",
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
                        "autonomous_database_listing_failed",
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
                    "autonomous_database_listing_unexpected_error",
                    detail=str(e),
                )
                continue

            for adb in adbs:
                total_count += 1
                adb_id = getattr(adb, "id", None)
                resource = {
                    "adb_raw": oci.util.to_dict(adb),
                    "networking_enriched": {
                        "subnet_details": None,
                        "nsg_details": [],
                    },
                    "backup_enriched": {
                        "backups": [],
                    },
                    "_errors": [],
                }
                adb_raw = resource["adb_raw"]
                adb_raw["region_name"] = region
                adb_raw["compartment_name"] = comp_name
                adb_raw["compartment_id"] = comp.id

                try:
                    adb_detail = common.call_with_retry(
                        db_client.get_autonomous_database,
                        autonomous_database_id=adb_id,
                    ).data
                    adb_raw = oci.util.to_dict(adb_detail)
                    adb_raw["region_name"] = region
                    adb_raw["compartment_name"] = comp_name
                    adb_raw["compartment_id"] = comp.id
                    resource["adb_raw"] = adb_raw
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(
                        f"autonomous database detail fetch failed: {e}"
                    )
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "autonomous_database_detail_fetch_failed",
                        resource_id=adb_id,
                        detail=str(e),
                    )

                subnet_id = adb_raw.get("subnet_id")
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
                            resource["_errors"].append(f"subnet fetch failed: {e}")
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "subnet_fetch_failed",
                                resource_id=adb_id,
                                detail=str(e),
                            )
                    resource["networking_enriched"]["subnet_details"] = subnet_cache[subnet_id]

                resource["networking_enriched"]["nsg_details"] = []
                for nsg_id in adb_raw.get("nsg_ids", []) or []:
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
                                resource_id=adb_id,
                                detail=f"nsg_id={nsg_id} err={e}",
                            )
                    resource["networking_enriched"]["nsg_details"].append(nsg_cache[nsg_id])

                resource["backup_enriched"]["backups"] = []
                try:
                    backups = _list_all(
                        db_client.list_autonomous_database_backups,
                        autonomous_database_id=adb_id,
                    )
                    resource["backup_enriched"]["backups"] = [
                        oci.util.to_dict(x) for x in backups
                    ]
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "autonomous_database_backups_listed",
                        resource_id=adb_id,
                        count=len(resource["backup_enriched"]["backups"]),
                    )
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(
                        f"autonomous database backup listing failed: {e}"
                    )
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "autonomous_database_backup_listing_failed",
                        resource_id=adb_id,
                        detail=str(e),
                    )

                all_adbs.append(resource)

    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"adb_{client.profile_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_adbs, f, indent=4, default=str, ensure_ascii=False)
    return output_path

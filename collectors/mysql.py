import oci
import common
import json
import os
from log_utils import log_event


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "mysql",
        event,
        region=region,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting MySQL DB Systems")
    all_db_systems = []
    error_count = 0
    total_count = 0
    
    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config['region'] = region
        
        mysql_client = common.create_client(oci.mysql.DbSystemClient, config)
        mysql_backup_client = common.create_client(oci.mysql.DbBackupsClient, config)
        network_client = common.create_client(oci.core.VirtualNetworkClient, config)
        subnet_cache = {}
        
        for comp in client.compartments:
            comp_name = comp.name
            backups_by_db_system_id = {}
            backup_listing_error = None

            try:
                backups = common.list_call_get_all_results(
                    mysql_backup_client.list_backups,
                    compartment_id=comp.id,
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "mysql_backups_listed",
                    count=len(backups),
                )
                for backup in backups:
                    backup_dict = oci.util.to_dict(backup)
                    db_system_id = backup_dict.get("db_system_id")
                    if not db_system_id:
                        continue
                    if db_system_id not in backups_by_db_system_id:
                        backups_by_db_system_id[db_system_id] = []
                    backups_by_db_system_id[db_system_id].append(backup_dict)
            except oci.exceptions.ServiceError as e:
                if e.status != 404:
                    error_count += 1
                    backup_listing_error = f"mysql backup listing failed: code={e.status} message={e.message}"
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "mysql_backup_listing_failed",
                        detail=f"code={e.status} message={e.message}",
                    )
            except Exception as e:
                error_count += 1
                backup_listing_error = f"mysql backup listing failed: {e}"
                _log(
                    "ERROR",
                    region,
                    comp_name,
                    "mysql_backup_listing_unexpected_error",
                    detail=str(e),
                )

            try:
                db_systems = common.list_call_get_all_results(
                    mysql_client.list_db_systems,
                    compartment_id=comp.id
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "db_systems_listed",
                    count=len(db_systems),
                )
            except oci.exceptions.ServiceError as e:
                if e.status != 404:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "db_system_listing_failed",
                        detail=f"code={e.status} message={e.message}",
                    )
                continue
            except Exception as e:
                error_count += 1
                _log(
                    "ERROR",
                    region,
                    comp_name,
                    "db_system_listing_unexpected_error",
                    detail=str(e),
                )
                continue

            for db in db_systems:
                total_count += 1
                resource = {
                    "mysql_raw": oci.util.to_dict(db),
                    "networking_enriched": {
                        "subnet_details": None,
                    },
                    "backup_enriched": {
                        "backups": [],
                    },
                    "_errors": [],
                }
                mysql_raw = resource["mysql_raw"]
                mysql_raw["region_name"] = region
                mysql_raw["compartment_name"] = comp_name
                mysql_raw["compartment_id"] = comp.id

                try:
                    db_detail = common.call_with_retry(
                        mysql_client.get_db_system, db.id
                    ).data
                    mysql_raw.update(oci.util.to_dict(db_detail))
                    mysql_raw["region_name"] = region
                    mysql_raw["compartment_name"] = comp_name
                    mysql_raw["compartment_id"] = comp.id
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(f"db system detail fetch failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "db_system_detail_fetch_failed",
                        resource_id=db.id,
                        detail=str(e),
                    )

                subnet_id = mysql_raw.get("subnet_id")
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
                                resource_id=db.id,
                                detail=str(e),
                            )
                    resource["networking_enriched"]["subnet_details"] = subnet_cache[subnet_id]
                resource["backup_enriched"]["backups"] = backups_by_db_system_id.get(db.id, [])
                if backup_listing_error:
                    resource["_errors"].append(backup_listing_error)
                all_db_systems.append(resource)
                
    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)
    
    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"mysql_{client.profile_name}.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_db_systems, f, indent=4, default=str, ensure_ascii=False)
    return output_path

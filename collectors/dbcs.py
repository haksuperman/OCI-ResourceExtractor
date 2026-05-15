import json
import os

import oci
import common
from log_utils import log_event


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "dbcs",
        event,
        region=region,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def _list_all(list_call, **kwargs):
    return common.list_call_get_all_results(list_call, **kwargs).data


def _to_dict(model):
    if model is None:
        return {}
    return oci.util.to_dict(model)


def _safe_get_vnic(network_client, vnic_id, region, compartment, db_system_id, error_list):
    if not vnic_id:
        return {}
    try:
        return _to_dict(common.call_with_retry(network_client.get_vnic, vnic_id).data)
    except Exception as e:
        error_list.append(f"vnic fetch failed ({vnic_id}): {e}")
        _log(
            "WARN",
            region,
            compartment,
            "vnic_fetch_failed",
            resource_id=db_system_id or "-",
            detail=f"vnic_id={vnic_id} err={e}",
        )
        return {"id": vnic_id}


def _safe_get_private_ip(
    network_client, private_ip_id, region, compartment, db_system_id, error_list
):
    if not private_ip_id:
        return {}
    try:
        return _to_dict(
            common.call_with_retry(network_client.get_private_ip, private_ip_id).data
        )
    except Exception as e:
        error_list.append(f"private ip fetch failed ({private_ip_id}): {e}")
        _log(
            "WARN",
            region,
            compartment,
            "private_ip_fetch_failed",
            resource_id=db_system_id or "-",
            detail=f"private_ip_id={private_ip_id} err={e}",
        )
        return {"id": private_ip_id}


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting Base Database(DBCS) resources")
    all_db_systems = []
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
                db_systems = _list_all(
                    db_client.list_db_systems, compartment_id=comp.id, sort_by="DISPLAYNAME"
                )
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "db_systems_listed",
                    count=len(db_systems),
                )
            except oci.exceptions.ServiceError as e:
                error_count += 1
                if e.status == 404:
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "db_system_listing_not_authorized_or_not_found",
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
                        "db_system_listing_failed",
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
                    "db_system_listing_unexpected_error",
                    detail=str(e),
                )
                continue

            for db_system in db_systems:
                total_count += 1
                dbs_id = getattr(db_system, "id", None)
                dbs_dict = oci.util.to_dict(db_system)
                dbs_dict["region_name"] = region
                dbs_dict["compartment_name"] = comp_name
                dbs_dict["compartment_id"] = comp.id
                dbs_dict["_errors"] = []

                try:
                    detail = common.call_with_retry(
                        db_client.get_db_system, db_system_id=dbs_id
                    ).data
                    dbs_dict = oci.util.to_dict(detail)
                    dbs_dict["region_name"] = region
                    dbs_dict["compartment_name"] = comp_name
                    dbs_dict["compartment_id"] = comp.id
                    dbs_dict["_errors"] = []
                except Exception as e:
                    error_count += 1
                    dbs_dict["_errors"].append(f"db system detail fetch failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "db_system_detail_fetch_failed",
                        resource_id=dbs_id,
                        detail=str(e),
                    )

                subnet_id = dbs_dict.get("subnet_id")
                if subnet_id:
                    if subnet_id not in subnet_cache:
                        try:
                            subnet_cache[subnet_id] = _to_dict(
                                common.call_with_retry(
                                    network_client.get_subnet, subnet_id
                                ).data
                            )
                        except Exception as e:
                            error_count += 1
                            subnet_cache[subnet_id] = {"id": subnet_id}
                            dbs_dict["_errors"].append(f"subnet fetch failed ({subnet_id}): {e}")
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "subnet_fetch_failed",
                                resource_id=dbs_id,
                                detail=f"subnet_id={subnet_id} err={e}",
                            )
                    dbs_dict["subnet_details"] = subnet_cache[subnet_id]

                backup_subnet_id = dbs_dict.get("backup_subnet_id")
                if backup_subnet_id:
                    if backup_subnet_id not in subnet_cache:
                        try:
                            subnet_cache[backup_subnet_id] = _to_dict(
                                common.call_with_retry(
                                    network_client.get_subnet, backup_subnet_id
                                ).data
                            )
                        except Exception as e:
                            error_count += 1
                            subnet_cache[backup_subnet_id] = {"id": backup_subnet_id}
                            dbs_dict["_errors"].append(
                                f"backup subnet fetch failed ({backup_subnet_id}): {e}"
                            )
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "backup_subnet_fetch_failed",
                                resource_id=dbs_id,
                                detail=f"backup_subnet_id={backup_subnet_id} err={e}",
                            )
                    dbs_dict["backup_subnet_details"] = subnet_cache[backup_subnet_id]

                dbs_dict["nsg_details"] = []
                for nsg_id in dbs_dict.get("nsg_ids", []) or []:
                    if nsg_id not in nsg_cache:
                        try:
                            nsg_cache[nsg_id] = _to_dict(
                                common.call_with_retry(
                                    network_client.get_network_security_group, nsg_id
                                ).data
                            )
                        except Exception as e:
                            error_count += 1
                            nsg_cache[nsg_id] = {"id": nsg_id}
                            dbs_dict["_errors"].append(f"nsg fetch failed ({nsg_id}): {e}")
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "nsg_fetch_failed",
                                resource_id=dbs_id,
                                detail=f"nsg_id={nsg_id} err={e}",
                            )
                    dbs_dict["nsg_details"].append(nsg_cache[nsg_id])

                db_homes_rows = []
                try:
                    db_homes = _list_all(
                        db_client.list_db_homes,
                        compartment_id=comp.id,
                        db_system_id=dbs_id,
                    )
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "db_homes_listed",
                        resource_id=dbs_id,
                        count=len(db_homes),
                    )

                    for db_home in db_homes:
                        db_home_dict = oci.util.to_dict(db_home)
                        db_home_id = db_home_dict.get("id")
                        db_home_dict["_errors"] = []
                        try:
                            home_detail = common.call_with_retry(
                                db_client.get_db_home, db_home_id=db_home_id
                            ).data
                            db_home_dict = oci.util.to_dict(home_detail)
                            db_home_dict["_errors"] = []
                        except Exception as e:
                            error_count += 1
                            dbs_dict["_errors"].append(
                                f"db home detail fetch failed (db_home={db_home_id}): {e}"
                            )
                            db_home_dict["_errors"].append(f"detail fetch failed: {e}")
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "db_home_detail_fetch_failed",
                                resource_id=dbs_id,
                                detail=f"db_home={db_home_id} err={e}",
                            )

                        db_home_dict["databases"] = []
                        try:
                            databases = _list_all(
                                db_client.list_databases,
                                compartment_id=comp.id,
                                db_home_id=db_home_id,
                                sort_by="DBNAME",
                            )
                            for db in databases:
                                db_dict = oci.util.to_dict(db)
                                db_id = db_dict.get("id")
                                db_dict["_errors"] = []
                                try:
                                    db_detail = common.call_with_retry(
                                        db_client.get_database, database_id=db_id
                                    ).data
                                    db_dict = oci.util.to_dict(db_detail)
                                    db_dict["_errors"] = []
                                except Exception as e:
                                    error_count += 1
                                    dbs_dict["_errors"].append(
                                        f"database detail fetch failed (database={db_id}): {e}"
                                    )
                                    db_dict["_errors"].append(f"detail fetch failed: {e}")
                                    _log(
                                        "WARN",
                                        region,
                                        comp_name,
                                        "database_detail_fetch_failed",
                                        resource_id=dbs_id,
                                        detail=f"database={db_id} err={e}",
                                    )

                                db_dict["dataguard_associations"] = []
                                try:
                                    dgs = _list_all(
                                        db_client.list_data_guard_associations, database_id=db_id
                                    )
                                    for dg in dgs:
                                        dg_dict = _to_dict(dg)
                                        peer_db_id = dg_dict.get("peer_database_id")
                                        peer_dbs_id = dg_dict.get("peer_db_system_id")
                                        if peer_db_id:
                                            try:
                                                peer_db = common.call_with_retry(
                                                    db_client.get_database,
                                                    database_id=peer_db_id,
                                                ).data
                                                dg_dict["peer_database_details"] = _to_dict(peer_db)
                                            except Exception as e:
                                                error_count += 1
                                                dbs_dict["_errors"].append(
                                                    f"peer database fetch failed (database={db_id}, peer_database={peer_db_id}): {e}"
                                                )
                                                db_dict["_errors"].append(
                                                    f"peer database fetch failed ({peer_db_id}): {e}"
                                                )
                                                dg_dict["peer_database_details"] = {
                                                    "id": peer_db_id
                                                }
                                                _log(
                                                    "WARN",
                                                    region,
                                                    comp_name,
                                                    "dataguard_peer_database_fetch_failed",
                                                    resource_id=dbs_id,
                                                    detail=f"database={db_id} peer_database={peer_db_id} err={e}",
                                                )
                                        if peer_dbs_id:
                                            try:
                                                peer_dbs = common.call_with_retry(
                                                    db_client.get_db_system,
                                                    db_system_id=peer_dbs_id,
                                                ).data
                                                dg_dict["peer_db_system_details"] = _to_dict(peer_dbs)
                                            except Exception as e:
                                                error_count += 1
                                                dbs_dict["_errors"].append(
                                                    f"peer db system fetch failed (database={db_id}, peer_db_system={peer_dbs_id}): {e}"
                                                )
                                                db_dict["_errors"].append(
                                                    f"peer db system fetch failed ({peer_dbs_id}): {e}"
                                                )
                                                dg_dict["peer_db_system_details"] = {
                                                    "id": peer_dbs_id
                                                }
                                                _log(
                                                    "WARN",
                                                    region,
                                                    comp_name,
                                                    "dataguard_peer_db_system_fetch_failed",
                                                    resource_id=dbs_id,
                                                    detail=f"database={db_id} peer_db_system={peer_dbs_id} err={e}",
                                                )
                                        db_dict["dataguard_associations"].append(dg_dict)
                                except Exception as e:
                                    error_count += 1
                                    dbs_dict["_errors"].append(
                                        f"dataguard listing failed (database={db_id}): {e}"
                                    )
                                    db_dict["_errors"].append(f"dataguard listing failed: {e}")
                                    _log(
                                        "WARN",
                                        region,
                                        comp_name,
                                        "database_dataguard_listing_failed",
                                        resource_id=dbs_id,
                                        detail=f"database={db_id} err={e}",
                                    )

                                db_dict["backups"] = []
                                try:
                                    backups = _list_all(db_client.list_backups, database_id=db_id)
                                    db_dict["backups"] = [_to_dict(b) for b in backups]
                                except Exception as e:
                                    error_count += 1
                                    dbs_dict["_errors"].append(
                                        f"database backup listing failed (database={db_id}): {e}"
                                    )
                                    db_dict["_errors"].append(f"backup listing failed: {e}")
                                    _log(
                                        "WARN",
                                        region,
                                        comp_name,
                                        "database_backup_listing_failed",
                                        resource_id=dbs_id,
                                        detail=f"database={db_id} err={e}",
                                    )

                                db_dict["pluggable_databases"] = []
                                try:
                                    pdbs = _list_all(
                                        db_client.list_pluggable_databases, database_id=db_id
                                    )
                                    db_dict["pluggable_databases"] = [_to_dict(p) for p in pdbs]
                                except Exception as e:
                                    error_count += 1
                                    dbs_dict["_errors"].append(
                                        f"pluggable database listing failed (database={db_id}): {e}"
                                    )
                                    db_dict["_errors"].append(
                                        f"pluggable database listing failed: {e}"
                                    )
                                    _log(
                                        "WARN",
                                        region,
                                        comp_name,
                                        "pluggable_database_listing_failed",
                                        resource_id=dbs_id,
                                        detail=f"database={db_id} err={e}",
                                    )
                                db_home_dict["databases"].append(db_dict)
                        except Exception as e:
                            error_count += 1
                            dbs_dict["_errors"].append(
                                f"database listing failed (db_home={db_home_id}): {e}"
                            )
                            db_home_dict["_errors"].append(f"database listing failed: {e}")
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "database_listing_failed",
                                resource_id=dbs_id,
                                detail=f"db_home={db_home_id} err={e}",
                            )

                        db_homes_rows.append(db_home_dict)
                except Exception as e:
                    error_count += 1
                    dbs_dict["_errors"].append(f"db home listing failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "db_home_listing_failed",
                        resource_id=dbs_id,
                        detail=str(e),
                    )

                db_nodes_rows = []
                try:
                    db_nodes = _list_all(
                        db_client.list_db_nodes,
                        compartment_id=comp.id,
                        db_system_id=dbs_id,
                    )
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "db_nodes_listed",
                        resource_id=dbs_id,
                        count=len(db_nodes),
                    )
                    for node in db_nodes:
                        node_dict = oci.util.to_dict(node)
                        node_id = node_dict.get("id")
                        node_dict["_errors"] = []
                        try:
                            node_detail = common.call_with_retry(
                                db_client.get_db_node, db_node_id=node_id
                            ).data
                            node_dict = oci.util.to_dict(node_detail)
                            node_dict["_errors"] = []
                        except Exception as e:
                            error_count += 1
                            dbs_dict["_errors"].append(
                                f"db node detail fetch failed (db_node={node_id}): {e}"
                            )
                            node_dict["_errors"].append(f"detail fetch failed: {e}")
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "db_node_detail_fetch_failed",
                                resource_id=dbs_id,
                                detail=f"db_node={node_id} err={e}",
                            )

                        node_dict["vnic_details"] = _safe_get_vnic(
                            network_client,
                            node_dict.get("vnic_id"),
                            region,
                            comp_name,
                            dbs_id,
                            dbs_dict["_errors"],
                        )
                        node_dict["backup_vnic_details"] = _safe_get_vnic(
                            network_client,
                            node_dict.get("backup_vnic_id"),
                            region,
                            comp_name,
                            dbs_id,
                            dbs_dict["_errors"],
                        )
                        node_dict["vnic2_details"] = _safe_get_vnic(
                            network_client,
                            node_dict.get("vnic2_id"),
                            region,
                            comp_name,
                            dbs_id,
                            dbs_dict["_errors"],
                        )
                        node_dict["backup_vnic2_details"] = _safe_get_vnic(
                            network_client,
                            node_dict.get("backup_vnic2_id"),
                            region,
                            comp_name,
                            dbs_id,
                            dbs_dict["_errors"],
                        )
                        node_dict["host_ip_details"] = _safe_get_private_ip(
                            network_client,
                            node_dict.get("host_ip_id"),
                            region,
                            comp_name,
                            dbs_id,
                            dbs_dict["_errors"],
                        )
                        node_dict["backup_ip_details"] = _safe_get_private_ip(
                            network_client,
                            node_dict.get("backup_ip_id"),
                            region,
                            comp_name,
                            dbs_id,
                            dbs_dict["_errors"],
                        )
                        db_nodes_rows.append(node_dict)
                except Exception as e:
                    error_count += 1
                    dbs_dict["_errors"].append(f"db node listing failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "db_node_listing_failed",
                        resource_id=dbs_id,
                        detail=str(e),
                    )

                dbs_dict["db_homes"] = db_homes_rows
                dbs_dict["db_nodes"] = db_nodes_rows

                resource = {
                    "dbcs_raw": {
                        k: v
                        for k, v in dbs_dict.items()
                        if k
                        not in {
                            "_errors",
                            "subnet_details",
                            "backup_subnet_details",
                            "nsg_details",
                            "db_homes",
                            "db_nodes",
                        }
                    },
                    "networking_enriched": {
                        "subnet_details": dbs_dict.get("subnet_details"),
                        "backup_subnet_details": dbs_dict.get("backup_subnet_details"),
                        "nsg_details": dbs_dict.get("nsg_details", []),
                    },
                    "dbcs_enriched": {
                        "db_homes": dbs_dict.get("db_homes", []),
                        "db_nodes": dbs_dict.get("db_nodes", []),
                    },
                    "_errors": dbs_dict.get("_errors", []),
                }
                all_db_systems.append(resource)

    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"dbcs_{client.profile_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_db_systems, f, indent=4, default=str, ensure_ascii=False)
    return output_path

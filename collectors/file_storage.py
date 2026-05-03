import json
import os

import oci
import common
from log_utils import log_event


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "file_storage",
        event,
        region=region,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def _to_detail_dict(resource, get_call, region, compartment):
    item = oci.util.to_dict(resource)
    item["_errors"] = []
    rid = item.get("id", "-")
    try:
        detail = common.call_with_retry(get_call, rid).data
        item = oci.util.to_dict(detail)
        item["_errors"] = []
    except Exception as e:
        item["_errors"].append(f"detail fetch failed: {e}")
        _log(
            "WARN",
            region,
            compartment,
            "resource detail fetch failed",
            resource_id=rid,
            detail=str(e),
        )
    return item


def _build_resource(raw, networking_enriched=None):
    raw_dict = dict(raw or {})
    errors = raw_dict.pop("_errors", [])
    if not isinstance(errors, list):
        errors = [str(errors)]
    return {
        "file_storage_raw": raw_dict,
        "file_storage_enriched": {},
        "networking_enriched": networking_enriched or {},
        "_errors": errors,
    }


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting File Storage resources")
    all_resources = []
    total_count = 0
    error_count = 0

    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config["region"] = region
        fs_client = common.create_client(oci.file_storage.FileStorageClient, config)
        network_client = common.create_client(oci.core.VirtualNetworkClient, config)
        identity_client = common.create_client(oci.identity.IdentityClient, config)
        subnet_cache = {}
        nsg_cache = {}

        try:
            ads = common.list_call_get_all_results(
                identity_client.list_availability_domains, client.tenancy_id
            ).data
            ad_names = [ad.name for ad in ads]
            _log("INFO", region, "tenancy", "availability_domains_listed", count=len(ad_names))
        except Exception as e:
            error_count += 1
            _log("ERROR", region, "tenancy", "availability_domain_listing_failed", detail=str(e))
            continue

        for comp in client.compartments:
            comp_name = comp.name

            export_set_ids = []
            file_system_ids = []

            for ad_name in ad_names:
                # File Systems
                try:
                    file_systems = common.list_call_get_all_results(
                        fs_client.list_file_systems,
                        compartment_id=comp.id,
                        availability_domain=ad_name,
                    ).data
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "file_systems_listed",
                        ad=ad_name,
                        count=len(file_systems),
                    )
                    for fs in file_systems:
                        fs_dict = _to_detail_dict(
                            fs, fs_client.get_file_system, region, comp_name
                        )
                        fs_dict["resource_type"] = "file_system"
                        fs_dict["region_name"] = region
                        fs_dict["compartment_name"] = comp_name
                        fs_dict["availability_domain_name"] = ad_name
                        all_resources.append(_build_resource(fs_dict))
                        file_system_ids.append(fs_dict.get("id"))
                        total_count += 1
                except Exception as e:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "file_systems_listing_failed",
                        ad=ad_name,
                        detail=str(e),
                    )

                # Mount Targets
                try:
                    mount_targets = common.list_call_get_all_results(
                        fs_client.list_mount_targets,
                        compartment_id=comp.id,
                        availability_domain=ad_name,
                    ).data
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "mount_targets_listed",
                        ad=ad_name,
                        count=len(mount_targets),
                    )
                    for mt in mount_targets:
                        mt_dict = _to_detail_dict(
                            mt, fs_client.get_mount_target, region, comp_name
                        )
                        mt_dict["resource_type"] = "mount_target"
                        mt_dict["region_name"] = region
                        mt_dict["compartment_name"] = comp_name
                        mt_dict["availability_domain_name"] = ad_name
                        subnet_id = mt_dict.get("subnet_id")
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
                                    mt_dict["_errors"].append(f"subnet fetch failed ({subnet_id}): {e}")
                                    _log(
                                        "WARN",
                                        region,
                                        comp_name,
                                        "mount_target_subnet_fetch_failed",
                                        resource_id=mt_dict.get("id", "-"),
                                        detail=str(e),
                                    )
                            mt_dict["subnet_details"] = subnet_cache[subnet_id]

                        mt_dict["nsg_details"] = []
                        for nsg_id in mt_dict.get("nsg_ids", []) or []:
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
                                    mt_dict["_errors"].append(f"nsg fetch failed ({nsg_id}): {e}")
                                    _log(
                                        "WARN",
                                        region,
                                        comp_name,
                                        "mount_target_nsg_fetch_failed",
                                        resource_id=mt_dict.get("id", "-"),
                                        detail=str(e),
                                    )
                            mt_dict["nsg_details"].append(nsg_cache[nsg_id])
                        networking_enriched = {
                            "subnet_details": mt_dict.pop("subnet_details", None),
                            "nsg_details": mt_dict.pop("nsg_details", []),
                        }
                        all_resources.append(
                            _build_resource(mt_dict, networking_enriched=networking_enriched)
                        )
                        total_count += 1
                except Exception as e:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "mount_targets_listing_failed",
                        ad=ad_name,
                        detail=str(e),
                    )

                # Export Sets
                try:
                    export_sets = common.list_call_get_all_results(
                        fs_client.list_export_sets,
                        compartment_id=comp.id,
                        availability_domain=ad_name,
                    ).data
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "export_sets_listed",
                        ad=ad_name,
                        count=len(export_sets),
                    )
                    for es in export_sets:
                        es_dict = _to_detail_dict(
                            es, fs_client.get_export_set, region, comp_name
                        )
                        es_dict["resource_type"] = "export_set"
                        es_dict["region_name"] = region
                        es_dict["compartment_name"] = comp_name
                        es_dict["availability_domain_name"] = ad_name
                        all_resources.append(_build_resource(es_dict))
                        export_set_ids.append(es_dict.get("id"))
                        total_count += 1
                except Exception as e:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "export_sets_listing_failed",
                        ad=ad_name,
                        detail=str(e),
                    )

                # Snapshot Policies
                try:
                    policies = common.list_call_get_all_results(
                        fs_client.list_filesystem_snapshot_policies,
                        compartment_id=comp.id,
                        availability_domain=ad_name,
                    ).data
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "snapshot_policies_listed",
                        ad=ad_name,
                        count=len(policies),
                    )
                    for pol in policies:
                        pol_dict = _to_detail_dict(
                            pol,
                            fs_client.get_filesystem_snapshot_policy,
                            region,
                            comp_name,
                        )
                        pol_dict["resource_type"] = "snapshot_policy"
                        pol_dict["region_name"] = region
                        pol_dict["compartment_name"] = comp_name
                        pol_dict["availability_domain_name"] = ad_name
                        all_resources.append(_build_resource(pol_dict))
                        total_count += 1
                except Exception as e:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "snapshot_policies_listing_failed",
                        ad=ad_name,
                        detail=str(e),
                    )

                # Replications
                try:
                    replications = common.list_call_get_all_results(
                        fs_client.list_replications,
                        compartment_id=comp.id,
                        availability_domain=ad_name,
                    ).data
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "replications_listed",
                        ad=ad_name,
                        count=len(replications),
                    )
                    for rep in replications:
                        rep_dict = _to_detail_dict(
                            rep, fs_client.get_replication, region, comp_name
                        )
                        rep_dict["resource_type"] = "replication"
                        rep_dict["region_name"] = region
                        rep_dict["compartment_name"] = comp_name
                        rep_dict["availability_domain_name"] = ad_name
                        all_resources.append(_build_resource(rep_dict))
                        total_count += 1
                except Exception as e:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "replications_listing_failed",
                        ad=ad_name,
                        detail=str(e),
                    )

            # Exports (per export set)
            for export_set_id in [x for x in export_set_ids if x]:
                try:
                    exports = common.list_call_get_all_results(
                        fs_client.list_exports, export_set_id=export_set_id
                    ).data
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "exports_listed",
                        resource_id=export_set_id,
                        count=len(exports),
                    )
                    for exp in exports:
                        exp_dict = _to_detail_dict(
                            exp, fs_client.get_export, region, comp_name
                        )
                        exp_dict["resource_type"] = "export"
                        exp_dict["region_name"] = region
                        exp_dict["compartment_name"] = comp_name
                        all_resources.append(_build_resource(exp_dict))
                        total_count += 1
                except Exception as e:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "exports_listing_failed",
                        resource_id=export_set_id,
                        detail=str(e),
                    )

            # Snapshots (per file system)
            for file_system_id in [x for x in file_system_ids if x]:
                try:
                    snapshots = common.list_call_get_all_results(
                        fs_client.list_snapshots, file_system_id=file_system_id
                    ).data
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "snapshots_listed",
                        resource_id=file_system_id,
                        count=len(snapshots),
                    )
                    for snap in snapshots:
                        snap_dict = _to_detail_dict(
                            snap, fs_client.get_snapshot, region, comp_name
                        )
                        snap_dict["resource_type"] = "snapshot"
                        snap_dict["region_name"] = region
                        snap_dict["compartment_name"] = comp_name
                        all_resources.append(_build_resource(snap_dict))
                        total_count += 1
                except Exception as e:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "snapshots_listing_failed",
                        resource_id=file_system_id,
                        detail=str(e),
                    )

    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(
        output_dir, f"file_storage_{client.profile_name}.json"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_resources, f, indent=4, default=str, ensure_ascii=False)
    return output_path

import json
import os

import oci
import common
from log_utils import log_event


def _is_not_found_error(exc):
    return isinstance(exc, oci.exceptions.ServiceError) and exc.status == 404


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "block_storage",
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
        return item, 0
    except Exception as e:
        item["_errors"].append(f"detail fetch failed: {e}")
        _log(
            "WARN",
            region,
            compartment,
            "resource_detail_fetch_failed",
            resource_id=rid,
            detail=str(e),
        )
        return item, 1


def _get_backup_policy_assignment(bs_client, asset_id, region, compartment):
    if not asset_id:
        return None, 0, None
    try:
        assignment = common.call_with_retry(
            bs_client.get_volume_backup_policy_asset_assignment,
            asset_id,
        ).data
        return oci.util.to_dict(assignment), 0, None
    except Exception as e:
        if _is_not_found_error(e):
            return None, 0, None
        _log(
            "WARN",
            region,
            compartment,
            "backup_policy_assignment_fetch_failed",
            resource_id=asset_id,
            detail=str(e),
        )
        return None, 1, f"backup policy assignment fetch failed: {e}"


def _get_backup_policy_detail(bs_client, policy_id, policy_cache, region, compartment):
    if not policy_id:
        return None, 0, None
    if policy_id in policy_cache:
        return policy_cache[policy_id], 0, None
    try:
        policy = common.call_with_retry(bs_client.get_volume_backup_policy, policy_id).data
        policy_dict = oci.util.to_dict(policy)
        policy_cache[policy_id] = policy_dict
        return policy_dict, 0, None
    except Exception as e:
        if _is_not_found_error(e):
            policy_cache[policy_id] = None
            return None, 0, None
        _log(
            "WARN",
            region,
            compartment,
            "backup_policy_detail_fetch_failed",
            resource_id=policy_id,
            detail=str(e),
        )
        return None, 1, f"backup policy detail fetch failed: {e}"


def _attach_backup_policy_fields(
    item, bs_client, policy_cache, region, compartment, error_count
):
    rid = item.get("id")
    assignment, assign_error, assign_error_msg = _get_backup_policy_assignment(
        bs_client, rid, region, compartment
    )
    error_count += assign_error
    if assign_error_msg:
        item["_errors"].append(assign_error_msg)

    policy_id = assignment.get("policy_id") if assignment else None
    policy, policy_error, policy_error_msg = _get_backup_policy_detail(
        bs_client, policy_id, policy_cache, region, compartment
    )
    error_count += policy_error
    if policy_error_msg:
        item["_errors"].append(policy_error_msg)

    item["is_backup_policy_assigned"] = bool(assignment)
    item["backup_policy_assignment"] = assignment
    item["backup_policy_assignment_id"] = assignment.get("id") if assignment else None
    item["backup_policy_id"] = policy_id
    item["backup_policy_time_assigned"] = (
        assignment.get("time_created") if assignment else None
    )
    item["backup_policy_display_name"] = policy.get("display_name") if policy else None
    item["backup_policy_destination_region"] = (
        policy.get("destination_region") if policy else None
    )
    item["backup_policy_schedules"] = policy.get("schedules") if policy else None
    return error_count


def _build_resource(raw):
    raw_dict = dict(raw or {})
    errors = raw_dict.pop("_errors", [])
    if not isinstance(errors, list):
        errors = [str(errors)]

    enriched_keys = {
        "volume_attachments",
        "boot_volume_attachments",
        "is_backup_policy_assigned",
        "backup_policy_assignment",
        "backup_policy_assignment_id",
        "backup_policy_id",
        "backup_policy_time_assigned",
        "backup_policy_display_name",
        "backup_policy_destination_region",
        "backup_policy_schedules",
    }
    block_storage_enriched = {}
    for key in enriched_keys:
        if key in raw_dict:
            block_storage_enriched[key] = raw_dict.pop(key)

    return {
        "block_storage_raw": raw_dict,
        "block_storage_enriched": block_storage_enriched,
        "_errors": errors,
    }


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting Block Storage resources")
    all_resources = []
    total_count = 0
    error_count = 0

    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config["region"] = region
        bs_client = common.create_client(oci.core.BlockstorageClient, config)
        compute_client = common.create_client(oci.core.ComputeClient, config)
        identity_client = common.create_client(oci.identity.IdentityClient, config)

        try:
            ads = common.list_call_get_all_results(
                identity_client.list_availability_domains,
                client.tenancy_id,
            ).data
            ad_names = [ad.name for ad in ads]
            _log("INFO", region, "tenancy", "availability_domains_listed", count=len(ad_names))
        except Exception as e:
            error_count += 1
            _log("ERROR", region, "tenancy", "availability_domain_listing_failed", detail=str(e))
            continue

        for comp in client.compartments:
            comp_name = comp.name
            policy_cache = {}
            volume_attachments_by_volume_id = {}
            boot_attachments_by_boot_volume_id = {}
            volume_attachment_listing_error = None
            boot_attachment_listing_errors = {}

            try:
                volume_attachments = common.list_call_get_all_results(
                    compute_client.list_volume_attachments,
                    compartment_id=comp.id,
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "volume_attachments_listed",
                    count=len(volume_attachments),
                )
                for attachment in volume_attachments:
                    attachment_dict = oci.util.to_dict(attachment)
                    volume_id = attachment_dict.get("volume_id")
                    if not volume_id:
                        continue
                    if volume_id not in volume_attachments_by_volume_id:
                        volume_attachments_by_volume_id[volume_id] = []
                    volume_attachments_by_volume_id[volume_id].append(attachment_dict)
            except Exception as e:
                error_count += 1
                volume_attachment_listing_error = str(e)
                _log(
                    "WARN",
                    region,
                    comp_name,
                    "volume_attachment_listing_failed",
                    detail=str(e),
                )

            for ad_name in ad_names:
                try:
                    boot_attachments = common.list_call_get_all_results(
                        compute_client.list_boot_volume_attachments,
                        availability_domain=ad_name,
                        compartment_id=comp.id,
                    ).data
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "boot_volume_attachments_listed",
                        ad=ad_name,
                        count=len(boot_attachments),
                    )
                    for attachment in boot_attachments:
                        attachment_dict = oci.util.to_dict(attachment)
                        boot_volume_id = attachment_dict.get("boot_volume_id")
                        if not boot_volume_id:
                            continue
                        if boot_volume_id not in boot_attachments_by_boot_volume_id:
                            boot_attachments_by_boot_volume_id[boot_volume_id] = []
                        boot_attachments_by_boot_volume_id[boot_volume_id].append(attachment_dict)
                except Exception as e:
                    error_count += 1
                    boot_attachment_listing_errors[ad_name] = str(e)
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "boot_volume_attachment_listing_failed",
                        ad=ad_name,
                        detail=str(e),
                    )

            # Region-scope resources
            try:
                volume_group_backups = common.list_call_get_all_results(
                    bs_client.list_volume_group_backups,
                    compartment_id=comp.id,
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "volume_group_backups_listed",
                    count=len(volume_group_backups),
                )
                for vgb in volume_group_backups:
                    item = oci.util.to_dict(vgb)
                    item["resource_type"] = "volume_group_backup"
                    item["region_name"] = region
                    item["compartment_name"] = comp_name
                    item["_errors"] = []
                    all_resources.append(_build_resource(item))
                    total_count += 1
            except Exception as e:
                error_count += 1
                _log(
                    "WARN",
                    region,
                    comp_name,
                    "volume_group_backup_listing_failed",
                    detail=str(e),
                )

            try:
                volume_backups = common.list_call_get_all_results(
                    bs_client.list_volume_backups,
                    compartment_id=comp.id,
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "volume_backups_listed",
                    count=len(volume_backups),
                )
                for vb in volume_backups:
                    item = oci.util.to_dict(vb)
                    item["resource_type"] = "volume_backup"
                    item["region_name"] = region
                    item["compartment_name"] = comp_name
                    item["_errors"] = []
                    all_resources.append(_build_resource(item))
                    total_count += 1
            except Exception as e:
                error_count += 1
                _log(
                    "WARN",
                    region,
                    comp_name,
                    "volume_backup_listing_failed",
                    detail=str(e),
                )

            try:
                boot_volume_backups = common.list_call_get_all_results(
                    bs_client.list_boot_volume_backups,
                    compartment_id=comp.id,
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "boot_volume_backups_listed",
                    count=len(boot_volume_backups),
                )
                for bvb in boot_volume_backups:
                    item = oci.util.to_dict(bvb)
                    item["resource_type"] = "boot_volume_backup"
                    item["region_name"] = region
                    item["compartment_name"] = comp_name
                    item["_errors"] = []
                    all_resources.append(_build_resource(item))
                    total_count += 1
            except Exception as e:
                error_count += 1
                _log(
                    "WARN",
                    region,
                    comp_name,
                    "boot_volume_backup_listing_failed",
                    detail=str(e),
                )

            for ad_name in ad_names:
                try:
                    volumes = common.list_call_get_all_results(
                        bs_client.list_volumes,
                        compartment_id=comp.id,
                        availability_domain=ad_name,
                    ).data
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "volumes_listed",
                        ad=ad_name,
                        count=len(volumes),
                    )
                    for vol in volumes:
                        item, detail_error = _to_detail_dict(
                            vol, bs_client.get_volume, region, comp_name
                        )
                        error_count += detail_error
                        item["resource_type"] = "volume"
                        item["region_name"] = region
                        item["compartment_name"] = comp_name
                        item["availability_domain_name"] = ad_name
                        item["volume_attachments"] = volume_attachments_by_volume_id.get(
                            item.get("id"), []
                        )
                        error_count = _attach_backup_policy_fields(
                            item, bs_client, policy_cache, region, comp_name, error_count
                        )
                        if volume_attachment_listing_error:
                            item["_errors"].append(
                                f"volume attachment listing failed: {volume_attachment_listing_error}"
                            )
                        all_resources.append(_build_resource(item))
                        total_count += 1
                except Exception as e:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "volume_listing_failed",
                        ad=ad_name,
                        detail=str(e),
                    )

                try:
                    boot_volumes = common.list_call_get_all_results(
                        bs_client.list_boot_volumes,
                        compartment_id=comp.id,
                        availability_domain=ad_name,
                    ).data
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "boot_volumes_listed",
                        ad=ad_name,
                        count=len(boot_volumes),
                    )
                    for bv in boot_volumes:
                        item, detail_error = _to_detail_dict(
                            bv, bs_client.get_boot_volume, region, comp_name
                        )
                        error_count += detail_error
                        item["resource_type"] = "boot_volume"
                        item["region_name"] = region
                        item["compartment_name"] = comp_name
                        item["availability_domain_name"] = ad_name
                        item["boot_volume_attachments"] = boot_attachments_by_boot_volume_id.get(
                            item.get("id"), []
                        )
                        error_count = _attach_backup_policy_fields(
                            item, bs_client, policy_cache, region, comp_name, error_count
                        )
                        if ad_name in boot_attachment_listing_errors:
                            item["_errors"].append(
                                "boot volume attachment listing failed: "
                                + boot_attachment_listing_errors[ad_name]
                            )
                        all_resources.append(_build_resource(item))
                        total_count += 1
                except Exception as e:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "boot_volume_listing_failed",
                        ad=ad_name,
                        detail=str(e),
                    )

                try:
                    volume_groups = common.list_call_get_all_results(
                        bs_client.list_volume_groups,
                        compartment_id=comp.id,
                        availability_domain=ad_name,
                    ).data
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "volume_groups_listed",
                        ad=ad_name,
                        count=len(volume_groups),
                    )
                    for vg in volume_groups:
                        item, detail_error = _to_detail_dict(
                            vg, bs_client.get_volume_group, region, comp_name
                        )
                        error_count += detail_error
                        item["resource_type"] = "volume_group"
                        item["region_name"] = region
                        item["compartment_name"] = comp_name
                        item["availability_domain_name"] = ad_name
                        all_resources.append(_build_resource(item))
                        total_count += 1
                except Exception as e:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "volume_group_listing_failed",
                        ad=ad_name,
                        detail=str(e),
                    )

    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"block_storage_{client.profile_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_resources, f, indent=4, default=str, ensure_ascii=False)
    return output_path

import json
import os

import oci
import common
from log_utils import log_event


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "compute",
        event,
        region=region,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def _build_networking_summary(vnics):
    summary = {
        "public_ip": None,
        "private_ip": None,
        "vcn_name": None,
        "subnet_name": None,
    }
    if not isinstance(vnics, list) or not vnics:
        return summary

    primary_vnic = None
    for vnic in vnics:
        if isinstance(vnic, dict) and vnic.get("is_primary"):
            primary_vnic = vnic
            break
    if primary_vnic is None:
        primary_vnic = vnics[0] if isinstance(vnics[0], dict) else None
    if not isinstance(primary_vnic, dict):
        return summary

    summary["public_ip"] = primary_vnic.get("public_ip")
    summary["private_ip"] = primary_vnic.get("private_ip")
    summary["vcn_name"] = primary_vnic.get("vcn_name")
    summary["subnet_name"] = primary_vnic.get("subnet_name")
    return summary


def _build_storage_summary(boot_volume_details_all, block_volume_details, block_volume_attachments):
    summary = {
        "boot_volume_name": None,
        "boot_volume_size_in_gbs": None,
        "block_volume_name": None,
        "block_volume_size_in_gbs": None,
        "block_volume_attachment_type": None,
    }

    if isinstance(boot_volume_details_all, list) and boot_volume_details_all:
        first_boot = boot_volume_details_all[0]
        if isinstance(first_boot, dict):
            summary["boot_volume_name"] = first_boot.get("display_name")
            summary["boot_volume_size_in_gbs"] = first_boot.get("size_in_gbs")

    first_block = None
    if isinstance(block_volume_details, list) and block_volume_details:
        maybe_first = block_volume_details[0]
        if isinstance(maybe_first, dict):
            first_block = maybe_first
            summary["block_volume_name"] = first_block.get("display_name")
            summary["block_volume_size_in_gbs"] = first_block.get("size_in_gbs")

    if first_block and isinstance(block_volume_attachments, list):
        block_volume_id = first_block.get("id")
        selected_attachment = None
        if block_volume_id:
            for attachment in block_volume_attachments:
                if isinstance(attachment, dict) and attachment.get("volume_id") == block_volume_id:
                    selected_attachment = attachment
                    break
        if selected_attachment is None:
            selected_attachment = (
                block_volume_attachments[0]
                if block_volume_attachments and isinstance(block_volume_attachments[0], dict)
                else None
            )
        if isinstance(selected_attachment, dict):
            summary["block_volume_attachment_type"] = (
                selected_attachment.get("attachment_type")
                or selected_attachment.get("type")
            )

    return summary


def _join_display_names(items):
    if not isinstance(items, list):
        return ""
    names = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("display_name") or item.get("name")
            if name:
                names.append(str(name))
    return ", ".join(names)


def _collect_capacity_reservations(compute_client, comp_id, region, comp_name):
    by_instance_id = {}
    errors = 0
    error_messages = []

    try:
        reservations = common.list_call_get_all_results(
            compute_client.list_compute_capacity_reservations,
            compartment_id=comp_id,
        ).data
        _log("INFO", region, comp_name, "capacity_reservations_listed", count=len(reservations))
    except Exception as e:
        errors += 1
        error_messages.append(f"capacity reservation listing failed: {e}")
        _log(
            "WARN",
            region,
            comp_name,
            "capacity_reservations_listing_failed",
            detail=str(e),
        )
        return by_instance_id, errors, error_messages

    for reservation in reservations:
        reservation_dict = oci.util.to_dict(reservation)
        reservation_id = reservation_dict.get("id")
        if not reservation_id:
            continue

        try:
            reservation_instances = common.list_call_get_all_results(
                compute_client.list_compute_capacity_reservation_instances,
                capacity_reservation_id=reservation_id,
            ).data
            for reservation_instance in reservation_instances:
                reservation_instance_dict = oci.util.to_dict(reservation_instance)
                instance_id = reservation_instance_dict.get("id") or reservation_instance_dict.get(
                    "instance_id"
                )
                if not instance_id:
                    continue
                by_instance_id[instance_id] = {
                    "reservation": reservation_dict,
                    "reservation_instance": reservation_instance_dict,
                }
        except Exception as e:
            errors += 1
            error_messages.append(
                f"capacity reservation instance listing failed ({reservation_id}): {e}"
            )
            _log(
                "WARN",
                region,
                comp_name,
                "capacity_reservation_instances_listing_failed",
                resource_id=reservation_id,
                detail=str(e),
            )

    return by_instance_id, errors, error_messages


def _collect_instance_pools(compute_management_client, comp_id, region, comp_name):
    by_instance_id = {}
    errors = 0
    error_messages = []

    if compute_management_client is None:
        return by_instance_id, errors, error_messages

    try:
        pools = common.list_call_get_all_results(
            compute_management_client.list_instance_pools,
            compartment_id=comp_id,
        ).data
        _log("INFO", region, comp_name, "instance_pools_listed", count=len(pools))
    except Exception as e:
        errors += 1
        error_messages.append(f"instance pool listing failed: {e}")
        _log(
            "WARN",
            region,
            comp_name,
            "instance_pools_listing_failed",
            detail=str(e),
        )
        return by_instance_id, errors, error_messages

    for pool in pools:
        pool_dict = oci.util.to_dict(pool)
        pool_id = pool_dict.get("id")
        if not pool_id:
            continue

        try:
            pool_instances = common.list_call_get_all_results(
                compute_management_client.list_instance_pool_instances,
                compartment_id=comp_id,
                instance_pool_id=pool_id,
            ).data
            for pool_instance in pool_instances:
                pool_instance_dict = oci.util.to_dict(pool_instance)
                instance_id = pool_instance_dict.get("id") or pool_instance_dict.get("instance_id")
                if not instance_id:
                    continue
                by_instance_id.setdefault(instance_id, []).append(
                    {
                        "pool": pool_dict,
                        "pool_instance": pool_instance_dict,
                    }
                )
        except Exception as e:
            errors += 1
            error_messages.append(f"instance pool member listing failed ({pool_id}): {e}")
            _log(
                "WARN",
                region,
                comp_name,
                "instance_pool_instances_listing_failed",
                resource_id=pool_id,
                detail=str(e),
            )

    return by_instance_id, errors, error_messages


def _collect_autoscaling(autoscaling_client, comp_id, region, comp_name):
    by_resource_id = {}
    errors = 0
    error_messages = []

    if autoscaling_client is None:
        return by_resource_id, errors, error_messages

    try:
        configurations = common.list_call_get_all_results(
            autoscaling_client.list_auto_scaling_configurations,
            compartment_id=comp_id,
        ).data
        _log(
            "INFO",
            region,
            comp_name,
            "autoscaling_configurations_listed",
            count=len(configurations),
        )
    except Exception as e:
        errors += 1
        error_messages.append(f"autoscaling configuration listing failed: {e}")
        _log(
            "WARN",
            region,
            comp_name,
            "autoscaling_configurations_listing_failed",
            detail=str(e),
        )
        return by_resource_id, errors, error_messages

    for conf in configurations:
        conf_dict = oci.util.to_dict(conf)
        conf_id = conf_dict.get("id")
        if not conf_id:
            continue

        try:
            policies = common.list_call_get_all_results(
                autoscaling_client.list_auto_scaling_policies,
                auto_scaling_configuration_id=conf_id,
            ).data
            conf_dict["policies"] = [oci.util.to_dict(p) for p in policies]
        except Exception as e:
            errors += 1
            error_messages.append(f"autoscaling policy listing failed ({conf_id}): {e}")
            conf_dict["policies"] = []
            _log(
                "WARN",
                region,
                comp_name,
                "autoscaling_policies_listing_failed",
                resource_id=conf_id,
                detail=str(e),
            )

        resource = conf_dict.get("resource")
        resource_id = None
        if isinstance(resource, dict):
            resource_id = resource.get("id")
        if not resource_id:
            resource_id = conf_dict.get("resource_id")

        if resource_id:
            by_resource_id.setdefault(resource_id, []).append(conf_dict)

    return by_resource_id, errors, error_messages


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting Compute Instances")
    all_instances = []
    image_cache = {}
    subnet_cache = {}
    vcn_cache = {}
    nsg_cache = {}
    block_volume_cache = {}
    boot_volume_cache = {}
    error_count = 0
    total_count = 0

    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config["region"] = region

        compute_client = common.create_client(oci.core.ComputeClient, config)
        network_client = common.create_client(oci.core.VirtualNetworkClient, config)
        block_storage_client = common.create_client(oci.core.BlockstorageClient, config)

        compute_management_client = None
        autoscaling_client = None
        plugin_client = None

        try:
            compute_management_client = common.create_client(
                oci.core.ComputeManagementClient, config
            )
        except Exception as e:
            error_count += 1
            _log(
                "WARN",
                region,
                "-",
                "compute_management_client_init_failed",
                detail=str(e),
            )

        try:
            autoscaling_client = common.create_client(oci.autoscaling.AutoScalingClient, config)
        except Exception as e:
            error_count += 1
            _log(
                "WARN",
                region,
                "-",
                "autoscaling_client_init_failed",
                detail=str(e),
            )

        try:
            plugin_client = common.create_client(oci.compute_instance_agent.PluginClient, config)
        except Exception as e:
            error_count += 1
            _log(
                "WARN",
                region,
                "-",
                "instance_agent_plugin_client_init_failed",
                detail=str(e),
            )

        for comp in client.compartments:
            comp_name = comp.name

            try:
                instances = common.list_call_get_all_results(
                    compute_client.list_instances,
                    comp.id,
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "instances_listed",
                    count=len(instances),
                )
            except Exception as e:
                error_count += 1
                _log(
                    "ERROR",
                    region,
                    comp_name,
                    "instance_listing_failed",
                    detail=str(e),
                )
                continue

            reservation_by_instance_id, ec, reservation_errors = _collect_capacity_reservations(
                compute_client,
                comp.id,
                region,
                comp_name,
            )
            error_count += ec

            pools_by_instance_id, ec, pool_errors = _collect_instance_pools(
                compute_management_client,
                comp.id,
                region,
                comp_name,
            )
            error_count += ec

            autoscaling_by_resource_id, ec, autoscaling_errors = _collect_autoscaling(
                autoscaling_client,
                comp.id,
                region,
                comp_name,
            )
            error_count += ec

            compartment_scope_errors = reservation_errors + pool_errors + autoscaling_errors

            for ins in instances:
                total_count += 1
                resource = {
                    "compute_raw": oci.util.to_dict(ins),
                    "networking_enriched": {
                        "public_ip": None,
                        "private_ip": None,
                        "vcn_name": None,
                        "subnet_name": None,
                        "vnic_attachments": [],
                        "vnics": [],
                    },
                    "storage_enriched": {
                        "boot_volume_name": None,
                        "boot_volume_size_in_gbs": None,
                        "block_volume_name": None,
                        "block_volume_size_in_gbs": None,
                        "block_volume_attachment_type": None,
                        "boot_volume_attachments": [],
                        "boot_volume_details_all": [],
                        "boot_volume_details": None,
                        "block_volume_attachments": [],
                        "block_volume_details": [],
                    },
                    "compute_enriched": {
                        "capacity_reservation": None,
                        "capacity_reservation_instance": None,
                        "instance_pools": [],
                        "instance_pool_names": "",
                        "autoscaling_configurations": [],
                        "autoscaling_configuration_names": "",
                        "console_connections": [],
                        "console_connection_count": 0,
                        "agent_plugin_status": [],
                        "agent_plugin_count": 0,
                    },
                    "_errors": list(compartment_scope_errors),
                }

                compute_raw = resource["compute_raw"]
                networking_enriched = resource["networking_enriched"]
                storage_enriched = resource["storage_enriched"]
                compute_enriched = resource["compute_enriched"]

                compute_raw["region_name"] = region
                compute_raw["compartment_name"] = comp_name

                if ins.image_id:
                    if ins.image_id not in image_cache:
                        try:
                            img = compute_client.get_image(ins.image_id).data
                            image_cache[ins.image_id] = oci.util.to_dict(img)
                        except Exception as e:
                            error_count += 1
                            image_cache[ins.image_id] = {"id": ins.image_id}
                            resource["_errors"].append(f"image fetch failed ({ins.image_id}): {e}")
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "image_fetch_failed",
                                resource_id=ins.id,
                                detail=str(e),
                            )
                    compute_raw["image_details"] = image_cache[ins.image_id]

                storage_enriched["boot_volume_attachments"] = []
                storage_enriched["boot_volume_details_all"] = []
                try:
                    bv_attachments = common.list_call_get_all_results(
                        compute_client.list_boot_volume_attachments,
                        availability_domain=ins.availability_domain,
                        compartment_id=comp.id,
                        instance_id=ins.id,
                    ).data
                    storage_enriched["boot_volume_attachments"] = [
                        oci.util.to_dict(a) for a in bv_attachments
                    ]
                    for attachment in bv_attachments:
                        bv_id = attachment.boot_volume_id
                        if bv_id not in boot_volume_cache:
                            try:
                                bv_data = block_storage_client.get_boot_volume(bv_id).data
                                boot_volume_cache[bv_id] = oci.util.to_dict(bv_data)
                            except Exception as e:
                                error_count += 1
                                boot_volume_cache[bv_id] = {"id": bv_id}
                                resource["_errors"].append(
                                    f"boot volume fetch failed ({bv_id}): {e}"
                                )
                                _log(
                                    "WARN",
                                    region,
                                    comp_name,
                                    "boot_volume_fetch_failed",
                                    resource_id=ins.id,
                                    detail=str(e),
                                )
                        storage_enriched["boot_volume_details_all"].append(
                            boot_volume_cache[bv_id]
                        )
                    if storage_enriched["boot_volume_details_all"]:
                        storage_enriched["boot_volume_details"] = storage_enriched[
                            "boot_volume_details_all"
                        ][0]
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(f"boot volume attachment listing failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "boot_volume_attachment_listing_failed",
                        resource_id=ins.id,
                        detail=str(e),
                    )

                storage_enriched["block_volume_attachments"] = []
                storage_enriched["block_volume_details"] = []
                try:
                    vol_attachments = common.list_call_get_all_results(
                        compute_client.list_volume_attachments,
                        compartment_id=comp.id,
                        instance_id=ins.id,
                    ).data
                    storage_enriched["block_volume_attachments"] = [
                        oci.util.to_dict(a) for a in vol_attachments
                    ]
                    for attachment in vol_attachments:
                        vol_id = attachment.volume_id
                        if vol_id not in block_volume_cache:
                            try:
                                vol_data = block_storage_client.get_volume(vol_id).data
                                block_volume_cache[vol_id] = oci.util.to_dict(vol_data)
                            except Exception as e:
                                error_count += 1
                                block_volume_cache[vol_id] = {"id": vol_id}
                                resource["_errors"].append(
                                    f"block volume fetch failed ({vol_id}): {e}"
                                )
                                _log(
                                    "WARN",
                                    region,
                                    comp_name,
                                    "block_volume_fetch_failed",
                                    resource_id=ins.id,
                                    detail=str(e),
                                )
                        storage_enriched["block_volume_details"].append(block_volume_cache[vol_id])
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(
                        f"block volume attachment listing failed: {e}"
                    )
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "block_volume_attachment_listing_failed",
                        resource_id=ins.id,
                        detail=str(e),
                    )

                storage_summary = _build_storage_summary(
                    storage_enriched.get("boot_volume_details_all", []),
                    storage_enriched.get("block_volume_details", []),
                    storage_enriched.get("block_volume_attachments", []),
                )
                storage_enriched.update(storage_summary)

                networking_enriched["vnic_attachments"] = []
                networking_enriched["vnics"] = []
                try:
                    vnic_attachments = common.list_call_get_all_results(
                        compute_client.list_vnic_attachments,
                        compartment_id=comp.id,
                        instance_id=ins.id,
                    ).data
                    networking_enriched["vnic_attachments"] = [
                        oci.util.to_dict(a) for a in vnic_attachments
                    ]

                    for attachment in vnic_attachments:
                        vnic = network_client.get_vnic(attachment.vnic_id).data
                        vnic_dict = oci.util.to_dict(vnic)
                        vnic_dict["attachment_details"] = oci.util.to_dict(attachment)
                        vnic_dict["nsg_details"] = []

                        if vnic.subnet_id:
                            if vnic.subnet_id not in subnet_cache:
                                try:
                                    subnet_cache[vnic.subnet_id] = oci.util.to_dict(
                                        network_client.get_subnet(vnic.subnet_id).data
                                    )
                                except Exception as e:
                                    error_count += 1
                                    subnet_cache[vnic.subnet_id] = {"id": vnic.subnet_id}
                                    resource["_errors"].append(
                                        f"subnet fetch failed ({vnic.subnet_id}): {e}"
                                    )
                                    _log(
                                        "WARN",
                                        region,
                                        comp_name,
                                        "subnet_fetch_failed",
                                        resource_id=ins.id,
                                        detail=str(e),
                                    )

                            subnet_dict = subnet_cache[vnic.subnet_id]
                            vnic_dict["subnet_details"] = subnet_dict
                            vnic_dict["subnet_name"] = subnet_dict.get("display_name")

                            vcn_id = subnet_dict.get("vcn_id")
                            if vcn_id:
                                if vcn_id not in vcn_cache:
                                    try:
                                        vcn_cache[vcn_id] = oci.util.to_dict(
                                            network_client.get_vcn(vcn_id).data
                                        )
                                    except Exception as e:
                                        error_count += 1
                                        vcn_cache[vcn_id] = {"id": vcn_id}
                                        resource["_errors"].append(
                                            f"vcn fetch failed ({vcn_id}): {e}"
                                        )
                                        _log(
                                            "WARN",
                                            region,
                                            comp_name,
                                            "vcn_fetch_failed",
                                            resource_id=ins.id,
                                            detail=str(e),
                                        )
                                vnic_dict["vcn_details"] = vcn_cache[vcn_id]
                                vnic_dict["vcn_name"] = vcn_cache[vcn_id].get("display_name")

                        for nsg_id in (vnic_dict.get("nsg_ids") or []):
                            if nsg_id not in nsg_cache:
                                try:
                                    nsg_cache[nsg_id] = oci.util.to_dict(
                                        network_client.get_network_security_group(nsg_id).data
                                    )
                                except Exception as e:
                                    error_count += 1
                                    nsg_cache[nsg_id] = {"id": nsg_id}
                                    resource["_errors"].append(
                                        f"nsg fetch failed ({nsg_id}): {e}"
                                    )
                                    _log(
                                        "WARN",
                                        region,
                                        comp_name,
                                        "nsg_fetch_failed",
                                        resource_id=ins.id,
                                        detail=str(e),
                                    )
                            vnic_dict["nsg_details"].append(nsg_cache[nsg_id])

                        vnic_dict["nsg_names"] = _join_display_names(vnic_dict.get("nsg_details", []))
                        networking_enriched["vnics"].append(vnic_dict)
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(f"vnic listing enrichment failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "vnic_listing_enrichment_failed",
                        resource_id=ins.id,
                        detail=str(e),
                    )

                networking_summary = _build_networking_summary(networking_enriched["vnics"])
                networking_enriched["public_ip"] = networking_summary["public_ip"]
                networking_enriched["private_ip"] = networking_summary["private_ip"]
                networking_enriched["vcn_name"] = networking_summary["vcn_name"]
                networking_enriched["subnet_name"] = networking_summary["subnet_name"]

                try:
                    reservation_info = reservation_by_instance_id.get(ins.id)
                    if reservation_info:
                        compute_enriched["capacity_reservation"] = reservation_info.get("reservation")
                        compute_enriched["capacity_reservation_instance"] = reservation_info.get(
                            "reservation_instance"
                        )
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(
                        f"capacity reservation enrichment failed ({ins.id}): {e}"
                    )
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "capacity_reservation_enrichment_failed",
                        resource_id=ins.id,
                        detail=str(e),
                    )

                try:
                    instance_pools = pools_by_instance_id.get(ins.id, [])
                    compute_enriched["instance_pools"] = instance_pools
                    compute_enriched["instance_pool_names"] = _join_display_names(
                        [x.get("pool") for x in instance_pools if isinstance(x, dict)]
                    )
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(f"instance pool enrichment failed ({ins.id}): {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "instance_pool_enrichment_failed",
                        resource_id=ins.id,
                        detail=str(e),
                    )

                try:
                    linked_resource_ids = []
                    for pool_entry in compute_enriched.get("instance_pools", []):
                        if isinstance(pool_entry, dict):
                            pool = pool_entry.get("pool")
                            if isinstance(pool, dict) and pool.get("id"):
                                linked_resource_ids.append(pool.get("id"))

                    autoscaling_entries = []
                    for resource_id in linked_resource_ids:
                        autoscaling_entries.extend(autoscaling_by_resource_id.get(resource_id, []))
                    compute_enriched["autoscaling_configurations"] = autoscaling_entries
                    compute_enriched["autoscaling_configuration_names"] = _join_display_names(
                        autoscaling_entries
                    )
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(f"autoscaling enrichment failed ({ins.id}): {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "autoscaling_enrichment_failed",
                        resource_id=ins.id,
                        detail=str(e),
                    )

                if plugin_client is not None:
                    try:
                        plugins = common.list_call_get_all_results(
                            plugin_client.list_instance_agent_plugins,
                            compartment_id=comp.id,
                            instanceagent_id=ins.id,
                        ).data
                        compute_enriched["agent_plugin_status"] = [oci.util.to_dict(x) for x in plugins]
                        compute_enriched["agent_plugin_count"] = len(plugins)
                    except Exception as e:
                        error_count += 1
                        resource["_errors"].append(f"agent plugin listing failed ({ins.id}): {e}")
                        _log(
                            "WARN",
                            region,
                            comp_name,
                            "agent_plugins_listing_failed",
                            resource_id=ins.id,
                            detail=str(e),
                        )

                try:
                    console_connections = common.list_call_get_all_results(
                        compute_client.list_instance_console_connections,
                        compartment_id=comp.id,
                        instance_id=ins.id,
                    ).data
                    compute_enriched["console_connections"] = [
                        oci.util.to_dict(x) for x in console_connections
                    ]
                    compute_enriched["console_connection_count"] = len(console_connections)
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(f"console connection listing failed ({ins.id}): {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "console_connections_listing_failed",
                        resource_id=ins.id,
                        detail=str(e),
                    )

                all_instances.append(resource)

    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"compute_{client.profile_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_instances, f, indent=4, default=str, ensure_ascii=False)
    return output_path

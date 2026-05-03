import json
import os

import oci
import common
from log_utils import log_event


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "vcn",
        event,
        region=region,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def _list_and_convert(list_call, region, compartment, vcn_id, resource_name, error_list, **kwargs):
    try:
        data = common.list_call_get_all_results(list_call, **kwargs).data
        converted = [oci.util.to_dict(x) for x in data]
        _log(
            "INFO",
            region,
            compartment,
            f"{resource_name}_listed",
            resource_id=vcn_id,
            count=len(converted),
        )
        return converted, 0
    except Exception as e:
        error_list.append(f"{resource_name} listing failed: {e}")
        _log(
            "WARN",
            region,
            compartment,
            f"{resource_name}_listing_failed",
            resource_id=vcn_id,
            detail=str(e),
        )
        return [], 1


def _collect_nsgs_with_rules(network_client, compartment_id, vcn_id, region, comp_name, error_list):
    nsg_summaries, ec = _list_and_convert(
        network_client.list_network_security_groups,
        region,
        comp_name,
        vcn_id,
        "network security groups",
        error_list,
        compartment_id=compartment_id,
        vcn_id=vcn_id,
    )
    if not nsg_summaries:
        return nsg_summaries, ec

    for nsg in nsg_summaries:
        nsg_id = nsg.get("id")
        if not nsg_id:
            continue

        try:
            rules = common.list_call_get_all_results(
                network_client.list_network_security_group_security_rules,
                network_security_group_id=nsg_id,
            ).data
            rule_dicts = [oci.util.to_dict(r) for r in rules]
            nsg["security_rules"] = rule_dicts
            nsg["ingress_security_rules"] = [
                r for r in rule_dicts if str(r.get("direction", "")).upper() == "INGRESS"
            ]
            nsg["egress_security_rules"] = [
                r for r in rule_dicts if str(r.get("direction", "")).upper() == "EGRESS"
            ]
            _log(
                "INFO",
                region,
                comp_name,
                "network_security_group_rules_listed",
                resource_id=nsg_id,
                count=len(rule_dicts),
            )
        except Exception as e:
            ec += 1
            error_list.append(f"network security group rules listing failed ({nsg_id}): {e}")
            _log(
                "WARN",
                region,
                comp_name,
                "network_security_group_rules_listing_failed",
                resource_id=nsg_id,
                detail=str(e),
            )
            nsg["security_rules"] = []
            nsg["ingress_security_rules"] = []
            nsg["egress_security_rules"] = []

    return nsg_summaries, ec


def _extract_related_vcn_id(drg_attachment):
    if not isinstance(drg_attachment, dict):
        return None

    direct_keys = [
        "vcn_id",
        "network_id",
    ]
    for key in direct_keys:
        value = drg_attachment.get(key)
        if value:
            return value

    network_details = drg_attachment.get("network_details")
    if isinstance(network_details, dict):
        nested_keys = ["id", "network_id", "vcn_id"]
        for key in nested_keys:
            value = network_details.get(key)
            if value:
                return value
    return None


def _collect_compartment_network_links(network_client, compartment_id, region, comp_name):
    comp_errors = []

    drgs, ec = _list_and_convert(
        network_client.list_drgs,
        region,
        comp_name,
        "-",
        "drgs",
        comp_errors,
        compartment_id=compartment_id,
    )

    drg_attachments, ec_attach = _list_and_convert(
        network_client.list_drg_attachments,
        region,
        comp_name,
        "-",
        "drg attachments",
        comp_errors,
        compartment_id=compartment_id,
    )
    ec += ec_attach

    virtual_circuits, ec_vc = _list_and_convert(
        network_client.list_virtual_circuits,
        region,
        comp_name,
        "-",
        "virtual circuits",
        comp_errors,
        compartment_id=compartment_id,
    )
    ec += ec_vc

    drg_map = {}
    for drg in drgs:
        drg_id = drg.get("id")
        if drg_id:
            drg_map[drg_id] = drg

    return {
        "errors": comp_errors,
        "error_count": ec,
        "drgs": drgs,
        "drg_map": drg_map,
        "drg_attachments": drg_attachments,
        "virtual_circuits": virtual_circuits,
    }


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting VCN and Networking Resources")
    all_vcns = []
    error_count = 0
    total_vcn_count = 0

    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config["region"] = region
        network_client = common.create_client(oci.core.VirtualNetworkClient, config)

        for comp in client.compartments:
            comp_name = comp.name
            links = _collect_compartment_network_links(
                network_client=network_client,
                compartment_id=comp.id,
                region=region,
                comp_name=comp_name,
            )
            error_count += links["error_count"]

            try:
                vcns = common.list_call_get_all_results(
                    network_client.list_vcns, compartment_id=comp.id
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "vcns_listed",
                    count=len(vcns),
                )
            except Exception as e:
                error_count += 1
                _log(
                    "ERROR",
                    region,
                    comp_name,
                    "vcn_listing_failed",
                    detail=str(e),
                )
                continue

            for vcn in vcns:
                total_vcn_count += 1
                resource = {
                    "vcn_raw": oci.util.to_dict(vcn),
                    "networking_enriched": {
                        "subnets": [],
                        "internet_gateways": [],
                        "nat_gateways": [],
                        "service_gateways": [],
                        "route_tables": [],
                        "security_lists": [],
                        "local_peering_gateways": [],
                        "dhcp_options": [],
                        "network_security_groups": [],
                        "drg_attachments": [],
                        "drgs": [],
                        "virtual_circuits": [],
                    },
                    "_errors": [],
                }
                vcn_raw = resource["vcn_raw"]
                vcn_raw["region_name"] = region
                vcn_raw["compartment_name"] = comp_name
                resource["_errors"].extend(links["errors"])

                subnets, ec = _list_and_convert(
                    network_client.list_subnets,
                    region,
                    comp_name,
                    vcn.id,
                    "subnets",
                    resource["_errors"],
                    compartment_id=comp.id,
                    vcn_id=vcn.id,
                )
                error_count += ec
                resource["networking_enriched"]["subnets"] = subnets

                igws, ec = _list_and_convert(
                    network_client.list_internet_gateways,
                    region,
                    comp_name,
                    vcn.id,
                    "internet gateways",
                    resource["_errors"],
                    compartment_id=comp.id,
                    vcn_id=vcn.id,
                )
                error_count += ec
                resource["networking_enriched"]["internet_gateways"] = igws

                nat_gateways, ec = _list_and_convert(
                    network_client.list_nat_gateways,
                    region,
                    comp_name,
                    vcn.id,
                    "nat gateways",
                    resource["_errors"],
                    compartment_id=comp.id,
                    vcn_id=vcn.id,
                )
                error_count += ec
                resource["networking_enriched"]["nat_gateways"] = nat_gateways

                service_gateways, ec = _list_and_convert(
                    network_client.list_service_gateways,
                    region,
                    comp_name,
                    vcn.id,
                    "service gateways",
                    resource["_errors"],
                    compartment_id=comp.id,
                    vcn_id=vcn.id,
                )
                error_count += ec
                resource["networking_enriched"]["service_gateways"] = service_gateways

                route_tables, ec = _list_and_convert(
                    network_client.list_route_tables,
                    region,
                    comp_name,
                    vcn.id,
                    "route tables",
                    resource["_errors"],
                    compartment_id=comp.id,
                    vcn_id=vcn.id,
                )
                error_count += ec
                resource["networking_enriched"]["route_tables"] = route_tables

                security_lists, ec = _list_and_convert(
                    network_client.list_security_lists,
                    region,
                    comp_name,
                    vcn.id,
                    "security lists",
                    resource["_errors"],
                    compartment_id=comp.id,
                    vcn_id=vcn.id,
                )
                error_count += ec
                resource["networking_enriched"]["security_lists"] = security_lists

                lpgs, ec = _list_and_convert(
                    network_client.list_local_peering_gateways,
                    region,
                    comp_name,
                    vcn.id,
                    "local peering gateways",
                    resource["_errors"],
                    compartment_id=comp.id,
                    vcn_id=vcn.id,
                )
                error_count += ec
                resource["networking_enriched"]["local_peering_gateways"] = lpgs

                dhcp_options, ec = _list_and_convert(
                    network_client.list_dhcp_options,
                    region,
                    comp_name,
                    vcn.id,
                    "dhcp options",
                    resource["_errors"],
                    compartment_id=comp.id,
                    vcn_id=vcn.id,
                )
                error_count += ec
                resource["networking_enriched"]["dhcp_options"] = dhcp_options

                network_security_groups, ec = _collect_nsgs_with_rules(
                    network_client=network_client,
                    compartment_id=comp.id,
                    vcn_id=vcn.id,
                    region=region,
                    comp_name=comp_name,
                    error_list=resource["_errors"],
                )
                error_count += ec
                resource["networking_enriched"]["network_security_groups"] = network_security_groups

                related_drg_attachments = []
                for attachment in links["drg_attachments"]:
                    related_vcn_id = _extract_related_vcn_id(attachment)
                    if related_vcn_id == vcn.id:
                        related_drg_attachments.append(attachment)
                resource["networking_enriched"]["drg_attachments"] = related_drg_attachments

                related_drg_ids = []
                for attachment in related_drg_attachments:
                    drg_id = attachment.get("drg_id")
                    if drg_id and drg_id not in related_drg_ids:
                        related_drg_ids.append(drg_id)

                resource["networking_enriched"]["drgs"] = [
                    links["drg_map"][drg_id]
                    for drg_id in related_drg_ids
                    if drg_id in links["drg_map"]
                ]

                related_virtual_circuits = []
                for vc in links["virtual_circuits"]:
                    gateway_id = vc.get("gateway_id")
                    if gateway_id and gateway_id in related_drg_ids:
                        related_virtual_circuits.append(vc)
                resource["networking_enriched"]["virtual_circuits"] = related_virtual_circuits

                all_vcns.append(resource)

    _log("INFO", "-", "-", "collection_end", collected=total_vcn_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"vcn_{client.profile_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_vcns, f, indent=4, default=str, ensure_ascii=False)
    return output_path

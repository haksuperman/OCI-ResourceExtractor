import copy

import pandas as pd


def get_preferred_columns():
    parent_context = [
        "vcn_raw.compartment_name",
        "vcn_raw.region_name",
        "vcn_raw.display_name",
        "vcn_raw.id",
    ]
    return {
        "Vcn": [
            "vcn_raw.display_name",
            "vcn_raw.id",
            "vcn_raw.lifecycle_state",
            "vcn_raw.cidr_block",
            "vcn_raw.cidr_blocks",
            "vcn_raw.dns_label",
            "vcn_raw.default_route_table_id",
            "vcn_raw.default_security_list_id",
            "vcn_raw.default_dhcp_options_id",
            "vcn_raw.region_name",
            "vcn_raw.compartment_name",
            "vcn_raw.time_created",
            "_errors",
        ],
        "Vcn_Subnets": parent_context
        + [
            "subnet_raw.display_name",
            "subnet_raw.id",
            "subnet_raw.lifecycle_state",
            "subnet_raw.cidr_block",
            "subnet_raw.availability_domain",
            "subnet_raw.route_table_id",
            "subnet_raw.dhcp_options_id",
            "subnet_raw.security_list_ids",
            "subnet_raw.prohibit_public_ip_on_vnic",
            "subnet_raw.prohibit_internet_ingress",
            "subnet_raw.time_created",
        ],
        "Vcn_Route_Tables": parent_context
        + [
            "route_table_raw.display_name",
            "route_table_raw.id",
            "route_table_raw.lifecycle_state",
            "route_table_raw.route_rules",
            "route_table_raw.time_created",
        ],
        "Vcn_Route_Rules": parent_context
        + [
            "route_table_raw.display_name",
            "route_table_raw.id",
            "route_rule_raw.destination",
            "route_rule_raw.destination_type",
            "route_rule_raw.network_entity_id",
            "route_rule_raw.route_type",
            "route_rule_raw.description",
        ],
        "Vcn_Security_Lists": parent_context
        + [
            "security_list_raw.display_name",
            "security_list_raw.id",
            "security_list_raw.lifecycle_state",
            "security_list_raw.ingress_security_rules",
            "security_list_raw.egress_security_rules",
            "security_list_raw.time_created",
        ],
        "Vcn_Security_Rules": parent_context
        + [
            "security_list_raw.display_name",
            "security_list_raw.id",
            "security_rule_raw.direction",
            "security_rule_raw.protocol",
            "security_rule_raw.is_stateless",
            "security_rule_raw.source",
            "security_rule_raw.source_type",
            "security_rule_raw.destination",
            "security_rule_raw.destination_type",
            "security_rule_raw.tcp_options",
            "security_rule_raw.udp_options",
            "security_rule_raw.icmp_options",
            "security_rule_raw.description",
        ],
        "Vcn_Network_Security_Groups": parent_context
        + [
            "nsg_raw.display_name",
            "nsg_raw.id",
            "nsg_raw.lifecycle_state",
            "nsg_raw.time_created",
        ],
        "Vcn_NSG_Rules": parent_context
        + [
            "nsg_raw.display_name",
            "nsg_raw.id",
            "nsg_rule_raw.direction",
            "nsg_rule_raw.protocol",
            "nsg_rule_raw.is_stateless",
            "nsg_rule_raw.source",
            "nsg_rule_raw.source_type",
            "nsg_rule_raw.destination",
            "nsg_rule_raw.destination_type",
            "nsg_rule_raw.tcp_options",
            "nsg_rule_raw.udp_options",
            "nsg_rule_raw.icmp_options",
            "nsg_rule_raw.description",
        ],
        "Vcn_Internet_Gateways": parent_context
        + [
            "internet_gateway_raw.display_name",
            "internet_gateway_raw.id",
            "internet_gateway_raw.lifecycle_state",
            "internet_gateway_raw.enabled",
            "internet_gateway_raw.time_created",
        ],
        "Vcn_NAT_Gateways": parent_context
        + [
            "nat_gateway_raw.display_name",
            "nat_gateway_raw.id",
            "nat_gateway_raw.lifecycle_state",
            "nat_gateway_raw.block_traffic",
            "nat_gateway_raw.nat_ip",
            "nat_gateway_raw.public_ip_id",
            "nat_gateway_raw.time_created",
        ],
        "Vcn_Service_Gateways": parent_context
        + [
            "service_gateway_raw.display_name",
            "service_gateway_raw.id",
            "service_gateway_raw.lifecycle_state",
            "service_gateway_raw.block_traffic",
            "service_gateway_raw.services",
            "service_gateway_raw.time_created",
        ],
        "Vcn_Local_Peering_Gateways": parent_context
        + [
            "local_peering_gateway_raw.display_name",
            "local_peering_gateway_raw.id",
            "local_peering_gateway_raw.lifecycle_state",
            "local_peering_gateway_raw.peering_status",
            "local_peering_gateway_raw.peer_id",
            "local_peering_gateway_raw.time_created",
        ],
        "Vcn_DHCP_Options": parent_context
        + [
            "dhcp_options_raw.display_name",
            "dhcp_options_raw.id",
            "dhcp_options_raw.lifecycle_state",
            "dhcp_options_raw.options",
            "dhcp_options_raw.time_created",
        ],
        "Vcn_DRG_Attachments": parent_context
        + [
            "drg_attachment_raw.display_name",
            "drg_attachment_raw.id",
            "drg_attachment_raw.lifecycle_state",
            "drg_attachment_raw.drg_id",
            "drg_attachment_raw.network_id",
            "drg_attachment_raw.network_details.id",
            "drg_attachment_raw.time_created",
        ],
        "Vcn_DRGs": parent_context
        + [
            "drg_raw.display_name",
            "drg_raw.id",
            "drg_raw.lifecycle_state",
            "drg_raw.time_created",
        ],
        "Vcn_Virtual_Circuits": parent_context
        + [
            "virtual_circuit_raw.display_name",
            "virtual_circuit_raw.id",
            "virtual_circuit_raw.lifecycle_state",
            "virtual_circuit_raw.type",
            "virtual_circuit_raw.bandwidth_shape_name",
            "virtual_circuit_raw.gateway_id",
            "virtual_circuit_raw.provider_name",
            "virtual_circuit_raw.time_created",
        ],
    }


def _safe_list(value):
    return value if isinstance(value, list) else []


def _parent_vcn_raw(row):
    return {
        "display_name": row.get("vcn_raw.display_name"),
        "id": row.get("vcn_raw.id"),
        "region_name": row.get("vcn_raw.region_name"),
        "compartment_name": row.get("vcn_raw.compartment_name"),
        "cidr_block": row.get("vcn_raw.cidr_block"),
        "cidr_blocks": row.get("vcn_raw.cidr_blocks"),
        "dns_label": row.get("vcn_raw.dns_label"),
    }


def _append_child_rows(rows, row, source_col, child_key):
    parent = _parent_vcn_raw(row)
    for child in _safe_list(row.get(source_col)):
        if isinstance(child, dict):
            rows.append({"vcn_raw": parent, child_key: child})


def _copy_rule(rule, direction):
    rule_raw = copy.deepcopy(rule) if isinstance(rule, dict) else {}
    rule_raw["direction"] = direction
    return rule_raw


def _normalize_rows(rows):
    if not rows:
        return pd.DataFrame()
    return pd.json_normalize(rows)


def transform(df):
    if df.empty:
        return {"Vcn": df}

    sheets = {"Vcn": df.copy()}
    subnet_rows = []
    route_table_rows = []
    route_rule_rows = []
    security_list_rows = []
    security_rule_rows = []
    nsg_rows = []
    nsg_rule_rows = []
    internet_gateway_rows = []
    nat_gateway_rows = []
    service_gateway_rows = []
    local_peering_gateway_rows = []
    dhcp_options_rows = []
    drg_attachment_rows = []
    drg_rows = []
    virtual_circuit_rows = []

    for _, row in df.iterrows():
        parent = _parent_vcn_raw(row)

        _append_child_rows(
            subnet_rows,
            row,
            "networking_enriched.subnets",
            "subnet_raw",
        )
        _append_child_rows(
            internet_gateway_rows,
            row,
            "networking_enriched.internet_gateways",
            "internet_gateway_raw",
        )
        _append_child_rows(
            nat_gateway_rows,
            row,
            "networking_enriched.nat_gateways",
            "nat_gateway_raw",
        )
        _append_child_rows(
            service_gateway_rows,
            row,
            "networking_enriched.service_gateways",
            "service_gateway_raw",
        )
        _append_child_rows(
            local_peering_gateway_rows,
            row,
            "networking_enriched.local_peering_gateways",
            "local_peering_gateway_raw",
        )
        _append_child_rows(
            dhcp_options_rows,
            row,
            "networking_enriched.dhcp_options",
            "dhcp_options_raw",
        )
        _append_child_rows(
            drg_attachment_rows,
            row,
            "networking_enriched.drg_attachments",
            "drg_attachment_raw",
        )
        _append_child_rows(
            drg_rows,
            row,
            "networking_enriched.drgs",
            "drg_raw",
        )
        _append_child_rows(
            virtual_circuit_rows,
            row,
            "networking_enriched.virtual_circuits",
            "virtual_circuit_raw",
        )

        for route_table in _safe_list(row.get("networking_enriched.route_tables")):
            if not isinstance(route_table, dict):
                continue
            route_table_rows.append({"vcn_raw": parent, "route_table_raw": route_table})
            for rule in _safe_list(route_table.get("route_rules")):
                if isinstance(rule, dict):
                    route_rule_rows.append(
                        {
                            "vcn_raw": parent,
                            "route_table_raw": route_table,
                            "route_rule_raw": rule,
                        }
                    )

        for security_list in _safe_list(row.get("networking_enriched.security_lists")):
            if not isinstance(security_list, dict):
                continue
            security_list_rows.append(
                {"vcn_raw": parent, "security_list_raw": security_list}
            )
            for rule in _safe_list(security_list.get("ingress_security_rules")):
                security_rule_rows.append(
                    {
                        "vcn_raw": parent,
                        "security_list_raw": security_list,
                        "security_rule_raw": _copy_rule(rule, "INGRESS"),
                    }
                )
            for rule in _safe_list(security_list.get("egress_security_rules")):
                security_rule_rows.append(
                    {
                        "vcn_raw": parent,
                        "security_list_raw": security_list,
                        "security_rule_raw": _copy_rule(rule, "EGRESS"),
                    }
                )

        for nsg in _safe_list(row.get("networking_enriched.network_security_groups")):
            if not isinstance(nsg, dict):
                continue
            nsg_rows.append({"vcn_raw": parent, "nsg_raw": nsg})
            for rule in _safe_list(nsg.get("security_rules")):
                if isinstance(rule, dict):
                    nsg_rule_rows.append(
                        {"vcn_raw": parent, "nsg_raw": nsg, "nsg_rule_raw": rule}
                    )

    detail_sheets = {
        "Vcn_Subnets": subnet_rows,
        "Vcn_Route_Tables": route_table_rows,
        "Vcn_Route_Rules": route_rule_rows,
        "Vcn_Security_Lists": security_list_rows,
        "Vcn_Security_Rules": security_rule_rows,
        "Vcn_Network_Security_Groups": nsg_rows,
        "Vcn_NSG_Rules": nsg_rule_rows,
        "Vcn_Internet_Gateways": internet_gateway_rows,
        "Vcn_NAT_Gateways": nat_gateway_rows,
        "Vcn_Service_Gateways": service_gateway_rows,
        "Vcn_Local_Peering_Gateways": local_peering_gateway_rows,
        "Vcn_DHCP_Options": dhcp_options_rows,
        "Vcn_DRG_Attachments": drg_attachment_rows,
        "Vcn_DRGs": drg_rows,
        "Vcn_Virtual_Circuits": virtual_circuit_rows,
    }

    for sheet_name, rows in detail_sheets.items():
        sheet_df = _normalize_rows(rows)
        if not sheet_df.empty:
            sheets[sheet_name] = sheet_df

    return sheets

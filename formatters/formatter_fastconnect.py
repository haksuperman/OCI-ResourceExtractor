import pandas as pd


PARENT_COLUMNS = [
    "fastconnect_raw.display_name",
    "fastconnect_raw.id",
    "fastconnect_raw.lifecycle_state",
    "fastconnect_raw.type",
    "fastconnect_raw.region_name",
    "fastconnect_raw.compartment_name",
]


def get_preferred_columns():
    return {
        "Fastconnect": [
            "fastconnect_raw.display_name",
            "fastconnect_raw.id",
            "fastconnect_raw.lifecycle_state",
            "fastconnect_raw.type",
            "fastconnect_raw.routing_policy",
            "fastconnect_raw.bandwidth_shape_name",
            "fastconnect_raw.provider_state",
            "networking_enriched.drg_details.display_name",
            "fastconnect_raw.gateway_id",
            "fastconnect_raw.provider_service_name",
            "fastconnect_raw.provider_service_key_name",
            "fastconnect_raw.customer_asn",
            "fastconnect_raw.region_name",
            "fastconnect_raw.compartment_name",
            "fastconnect_raw.time_created",
            "_errors",
        ],
        "Fastconnect_Public_Prefixes": [
            *PARENT_COLUMNS,
            "public_prefix_raw.cidr_block",
            "public_prefix_raw.verification_state",
        ],
        "Fastconnect_Cross_Connect_Mappings": [
            *PARENT_COLUMNS,
            "cross_connect_mapping_raw.cross_connect_or_cross_connect_group_id",
            "cross_connect_mapping_raw.bgp_md5auth_key",
            "cross_connect_mapping_raw.vlan",
            "cross_connect_mapping_raw.customer_bgp_peering_ip",
            "cross_connect_mapping_raw.oracle_bgp_peering_ip",
        ],
        "Fastconnect_Associated_Tunnels": [
            *PARENT_COLUMNS,
            "associated_tunnel_raw.id",
            "associated_tunnel_raw.ip_sec_connection_id",
            "associated_tunnel_raw.status",
            "associated_tunnel_raw.routing",
        ],
        "Fastconnect_Bandwidth_Shapes": [
            *PARENT_COLUMNS,
            "bandwidth_shape_raw.name",
            "bandwidth_shape_raw.bandwidth_in_mbps",
        ],
    }


def _safe_list(value):
    return value if isinstance(value, list) else []


def _parent_raw(row):
    return {
        col: row.get(col)
        for col in PARENT_COLUMNS
        if col in row.index
    }


def _detail_sheet(df, list_column, raw_key):
    rows = []
    for _, row in df.iterrows():
        parent = _parent_raw(row)
        for item in _safe_list(row.get(list_column)):
            rows.append(
                {
                    **parent,
                    raw_key: item if isinstance(item, dict) else {"value": item},
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.json_normalize(rows)


def transform(df):
    if df.empty:
        return {"Fastconnect": df}

    result = {"Fastconnect": df.copy()}

    optional = {
        "Fastconnect_Public_Prefixes": _detail_sheet(
            df, "fastconnect_enriched.public_prefixes", "public_prefix_raw"
        ),
        "Fastconnect_Cross_Connect_Mappings": _detail_sheet(
            df,
            "fastconnect_enriched.cross_connect_mappings",
            "cross_connect_mapping_raw",
        ),
        "Fastconnect_Associated_Tunnels": _detail_sheet(
            df, "fastconnect_enriched.associated_tunnels", "associated_tunnel_raw"
        ),
        "Fastconnect_Bandwidth_Shapes": _detail_sheet(
            df, "fastconnect_enriched.bandwidth_shapes", "bandwidth_shape_raw"
        ),
    }

    for name, sheet_df in optional.items():
        if isinstance(sheet_df, pd.DataFrame) and not sheet_df.empty:
            result[name] = sheet_df

    return result

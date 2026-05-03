import pandas as pd


PARENT_COLUMNS = [
    "vpn_raw.display_name",
    "vpn_raw.id",
    "vpn_raw.lifecycle_state",
    "vpn_raw.region_name",
    "vpn_raw.compartment_name",
    "vpn_raw.drg_id",
    "vpn_raw.cpe_id",
]


def get_preferred_columns():
    return {
        "Vpn": [
            "vpn_raw.display_name",
            "vpn_raw.id",
            "vpn_raw.lifecycle_state",
            "vpn_enriched.drg_details.display_name",
            "vpn_raw.drg_id",
            "vpn_enriched.cpe_details.display_name",
            "vpn_raw.cpe_id",
            "vpn_enriched.cpe_details.ip_address",
            "vpn_raw.static_routes",
            "vpn_raw.region_name",
            "vpn_raw.compartment_name",
            "vpn_raw.time_created",
            "_errors",
        ],
        "Vpn_Tunnels": [
            *PARENT_COLUMNS,
            "tunnel_raw.display_name",
            "tunnel_raw.id",
            "tunnel_raw.status",
            "tunnel_raw.lifecycle_state",
            "tunnel_raw.routing",
            "tunnel_raw.ike_version",
            "tunnel_raw.vpn_ip",
            "tunnel_raw.cpe_ip",
            "tunnel_raw.bgp_session_info.bgp_state",
            "tunnel_raw.nat_translation_enabled",
            "tunnel_raw.oracle_can_initiate",
            "tunnel_raw.dpd_mode",
            "tunnel_raw.dpd_timeout_in_sec",
            "tunnel_raw.phase_one_details.is_ike_established",
            "tunnel_raw.phase_one_details.negotiated_encryption_algorithm",
            "tunnel_raw.phase_one_details.negotiated_authentication_algorithm",
            "tunnel_raw.phase_one_details.negotiated_dh_group",
            "tunnel_raw.phase_two_details.is_esp_established",
            "tunnel_raw.phase_two_details.negotiated_encryption_algorithm",
            "tunnel_raw.phase_two_details.negotiated_authentication_algorithm",
            "tunnel_raw.phase_two_details.negotiated_dh_group",
            "tunnel_raw.phase_two_details.is_pfs_enabled",
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


def _normalize_rows(rows):
    if not rows:
        return pd.DataFrame()
    return pd.json_normalize(rows)


def transform(df):
    if df.empty:
        return {"Vpn": df}

    tunnel_rows = []
    for _, row in df.iterrows():
        parent = _parent_raw(row)
        for tunnel in _safe_list(row.get("vpn_enriched.tunnels")):
            tunnel_rows.append(
                {
                    **parent,
                    "tunnel_raw": tunnel,
                }
            )

    sheets = {"Vpn": df.copy()}
    tunnel_df = _normalize_rows(tunnel_rows)
    if not tunnel_df.empty:
        sheets["Vpn_Tunnels"] = tunnel_df
    return sheets

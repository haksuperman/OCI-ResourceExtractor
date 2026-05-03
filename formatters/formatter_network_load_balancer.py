import pandas as pd


PARENT_COLUMNS = [
    "network_load_balancer_raw.display_name",
    "network_load_balancer_raw.id",
    "network_load_balancer_raw.lifecycle_state",
    "network_load_balancer_raw.region_name",
    "network_load_balancer_raw.compartment_name",
    "network_load_balancer_raw.shape_name",
    "network_load_balancer_raw.is_private",
]


def get_preferred_columns():
    return {
        "NLB_Overview": [
            "network_load_balancer_raw.display_name",
            "network_load_balancer_raw.id",
            "network_load_balancer_raw.lifecycle_state",
            "network_load_balancer_raw.is_private",
            "network_load_balancer_raw.ip_version",
            "network_load_balancer_raw.subnet_id",
            "networking_enriched.subnet_details.display_name",
            "network_load_balancer_raw.network_security_group_ids",
            "network_load_balancer_raw.listeners",
            "network_load_balancer_raw.backend_sets",
            "network_load_balancer_raw.region_name",
            "network_load_balancer_raw.compartment_name",
            "network_load_balancer_raw.time_created",
        ],
        "NLB_Listeners": [
            *PARENT_COLUMNS,
            "listener_raw.name",
            "listener_raw.protocol",
            "listener_raw.port",
            "listener_raw.default_backend_set_name",
        ],
        "NLB_Backend_Sets": [
            *PARENT_COLUMNS,
            "backend_set_raw.name",
            "backend_set_raw.policy",
            "backend_set_raw.is_preserve_source",
            "backend_set_raw.health_checker.protocol",
            "backend_set_raw.health_checker.port",
            "backend_set_raw.backends",
        ],
        "NLB_Backends": [
            *PARENT_COLUMNS,
            "backend_set_raw.name",
            "backend_raw.name",
            "backend_raw.ip_address",
            "backend_raw.port",
            "backend_raw.weight",
            "backend_raw.is_drain",
            "backend_raw.is_offline",
            "backend_raw.is_backup",
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
        return {"NLB_Overview": df}

    nlb_df = df.copy()
    listener_rows = []
    backend_set_rows = []
    backend_rows = []

    for _, row in df.iterrows():
        parent = _parent_raw(row)

        for listener in _safe_list(row.get("network_load_balancer_enriched.listeners_list")):
            listener_rows.append(
                {
                    **parent,
                    "listener_raw": listener,
                }
            )

        for backend_set in _safe_list(
            row.get("network_load_balancer_enriched.backend_sets_list")
        ):
            backend_set_rows.append(
                {
                    **parent,
                    "backend_set_raw": backend_set,
                }
            )

            for backend in _safe_list(
                backend_set.get("backends") if isinstance(backend_set, dict) else []
            ):
                backend_rows.append(
                    {
                        **parent,
                        "backend_set_raw": backend_set,
                        "backend_raw": backend,
                    }
                )

    sheets = {"NLB_Overview": nlb_df}
    optional_sheets = {
        "NLB_Listeners": _normalize_rows(listener_rows),
        "NLB_Backend_Sets": _normalize_rows(backend_set_rows),
        "NLB_Backends": _normalize_rows(backend_rows),
    }
    for name, sheet_df in optional_sheets.items():
        if isinstance(sheet_df, pd.DataFrame) and not sheet_df.empty:
            sheets[name] = sheet_df
    return sheets

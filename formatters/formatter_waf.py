import pandas as pd


def _safe_list(value):
    return value if isinstance(value, list) else []


def _normalize_rows(rows):
    if not rows:
        return pd.DataFrame()
    return pd.json_normalize(rows)


WAF_PARENT_COLUMNS = [
    "waf_raw.display_name",
    "waf_raw.id",
    "waf_raw.lifecycle_state",
    "waf_raw.region_name",
    "waf_raw.compartment_name",
]


def get_preferred_columns():
    return {
        "WAF": [
            "waf_raw.display_name",
            "waf_raw.id",
            "waf_raw.lifecycle_state",
            "waf_raw.request_access_control.default_action_name",
            "waf_raw.region_name",
            "waf_raw.compartment_name",
            "waf_raw.time_created",
            "waf_raw.time_updated",
            "_errors",
        ],
        "WAF_Firewalls": [
            *WAF_PARENT_COLUMNS,
            "firewall_raw.display_name",
            "firewall_raw.id",
            "firewall_raw.lifecycle_state",
            "firewall_raw.backend_type",
            "firewall_raw.load_balancer_name",
            "firewall_raw.load_balancer_id",
            "firewall_raw.compartment_name",
            "firewall_raw.compartment_id",
            "firewall_raw.time_created",
            "firewall_raw.time_updated",
        ],
        "WAF_Request_Access": [
            *WAF_PARENT_COLUMNS,
            "rule_raw.name",
            "rule_raw.type",
            "rule_raw.action_name",
            "rule_raw.condition_language",
            "rule_raw.condition",
        ],
        "WAF_Response_Access": [
            *WAF_PARENT_COLUMNS,
            "rule_raw.name",
            "rule_raw.type",
            "rule_raw.action_name",
            "rule_raw.condition_language",
            "rule_raw.condition",
        ],
        "WAF_Request_Protection": [
            *WAF_PARENT_COLUMNS,
            "rule_raw.name",
            "rule_raw.type",
            "rule_raw.action_name",
            "rule_raw.condition_language",
            "rule_raw.condition",
            "rule_raw.is_body_inspection_enabled",
            "capability_raw.key",
            "capability_raw.version",
            "capability_raw.action_name",
            "capability_raw.exclusions",
            "capability_raw.collaborative_action_threshold",
            "capability_raw.collaborative_weights",
            "rule_raw.protection_capability_settings",
        ],
        "WAF_Response_Protection": [
            *WAF_PARENT_COLUMNS,
            "rule_raw.name",
            "rule_raw.type",
            "rule_raw.action_name",
            "rule_raw.condition_language",
            "rule_raw.condition",
            "rule_raw.is_body_inspection_enabled",
            "capability_raw.key",
            "capability_raw.version",
            "capability_raw.action_name",
            "capability_raw.exclusions",
            "capability_raw.collaborative_action_threshold",
            "capability_raw.collaborative_weights",
            "rule_raw.protection_capability_settings",
        ],
        "WAF_Request_Rate_Limits": [
            *WAF_PARENT_COLUMNS,
            "rule_raw.name",
            "rule_raw.type",
            "rule_raw.action_name",
            "rule_raw.requests_per_period",
            "rule_raw.period_in_seconds",
            "rule_raw.condition_language",
            "rule_raw.condition",
        ],
        "WAF_Actions": [
            *WAF_PARENT_COLUMNS,
            "action_raw.name",
            "action_raw.type",
        ],
    }


def _waf_parent_raw(row):
    return {
        col: row.get(col)
        for col in WAF_PARENT_COLUMNS
        if col in row.index
    }


def _extract_raw_list_rows(df, list_column, raw_key):
    rows = []
    for _, row in df.iterrows():
        parent = _waf_parent_raw(row)
        for item in _safe_list(row.get(list_column)):
            if isinstance(item, dict):
                rows.append({**parent, raw_key: item})
    return _normalize_rows(rows)


def _extract_raw_protection_rows(df, list_column):
    rows = []
    for _, row in df.iterrows():
        parent = _waf_parent_raw(row)
        for rule in _safe_list(row.get(list_column)):
            if not isinstance(rule, dict):
                continue
            capabilities = _safe_list(rule.get("protection_capabilities"))
            if not capabilities:
                rows.append({**parent, "rule_raw": rule})
                continue
            for capability in capabilities:
                if isinstance(capability, dict):
                    rows.append(
                        {
                            **parent,
                            "rule_raw": rule,
                            "capability_raw": capability,
                        }
                    )
    return _normalize_rows(rows)


def transform(df):
    if df.empty:
        return {"WAF": df}

    waf_df = df.copy()
    sheets = {"WAF": waf_df}
    optional = {
        "WAF_Firewalls": _extract_raw_list_rows(
            waf_df, "waf_enriched.firewalls", "firewall_raw"
        ),
        "WAF_Request_Access": _extract_raw_list_rows(
            waf_df, "waf_raw.request_access_control.rules", "rule_raw"
        ),
        "WAF_Response_Access": _extract_raw_list_rows(
            waf_df, "waf_raw.response_access_control.rules", "rule_raw"
        ),
        "WAF_Request_Protection": _extract_raw_protection_rows(
            waf_df, "waf_raw.request_protection.rules"
        ),
        "WAF_Response_Protection": _extract_raw_protection_rows(
            waf_df, "waf_raw.response_protection.rules"
        ),
        "WAF_Request_Rate_Limits": _extract_raw_list_rows(
            waf_df, "waf_raw.request_rate_limiting.rules", "rule_raw"
        ),
        "WAF_Actions": _extract_raw_list_rows(
            waf_df, "waf_raw.actions", "action_raw"
        ),
    }

    for name, sheet_df in optional.items():
        if isinstance(sheet_df, pd.DataFrame) and not sheet_df.empty:
            sheets[name] = sheet_df
    return sheets


WAF_EDGE_PARENT_COLUMNS = [
    "waf_edge_raw.display_name",
    "waf_edge_raw.id",
    "waf_edge_raw.lifecycle_state",
    "waf_edge_raw.region_name",
    "waf_edge_raw.compartment_name",
    "waf_edge_raw.domain",
]


def get_preferred_columns_edge():
    return {
        "WAF_Edge": [
            "waf_edge_raw.display_name",
            "waf_edge_raw.id",
            "waf_edge_raw.lifecycle_state",
            "waf_edge_raw.domain",
            "waf_edge_raw.additional_domains",
            "waf_edge_raw.waf_config.is_enabled",
            "waf_edge_raw.origins",
            "waf_edge_raw.region_name",
            "waf_edge_raw.compartment_name",
            "waf_edge_raw.time_created",
            "waf_edge_raw.time_updated",
            "_errors",
        ],
        "WAF_Edge_Custom_Rules": [
            *WAF_EDGE_PARENT_COLUMNS,
            "rule_raw.display_name",
            "rule_raw.name",
            "rule_raw.id",
            "rule_raw.action",
            "rule_raw.lifecycle_state",
            "rule_raw.template",
            "rule_raw.bypass_challenges",
            "rule_raw.mod_security_rule_ids",
        ],
        "WAF_Edge_Access_Rules": [
            *WAF_EDGE_PARENT_COLUMNS,
            "rule_raw.name",
            "rule_raw.action",
            "rule_raw.bypass_challenges",
            "rule_raw.criteria",
            "rule_raw.block_response_code",
            "rule_raw.redirect_url",
        ],
        "WAF_Edge_Protection_Rules": [
            *WAF_EDGE_PARENT_COLUMNS,
            "rule_raw.name",
            "rule_raw.key",
            "rule_raw.action",
            "rule_raw.description",
            "rule_raw.mod_security_rule_ids",
            "rule_raw.exclusions",
            "rule_raw.labels",
        ],
        "WAF_Edge_Rate_Limits": [
            *WAF_EDGE_PARENT_COLUMNS,
            "rate_limit_raw.is_enabled",
            "rate_limit_raw.allowed_rate_per_address",
            "rate_limit_raw.max_delayed_count_per_address",
            "rate_limit_raw.block_response_code",
        ],
    }


def _waf_edge_parent_raw(row):
    return {
        col: row.get(col)
        for col in WAF_EDGE_PARENT_COLUMNS
        if col in row.index
    }


def _extract_edge_raw_list_rows(df, list_column, raw_key):
    rows = []
    for _, row in df.iterrows():
        parent = _waf_edge_parent_raw(row)
        for item in _safe_list(row.get(list_column)):
            if isinstance(item, dict):
                rows.append({**parent, raw_key: item})
    return _normalize_rows(rows)


def _extract_edge_raw_rate_limits(df):
    rows = []
    for _, row in df.iterrows():
        parent = _waf_edge_parent_raw(row)
        rate_limit = row.get("waf_edge_raw.waf_config.address_rate_limiting")
        if isinstance(rate_limit, dict):
            rows.append({**parent, "rate_limit_raw": rate_limit})
        elif isinstance(rate_limit, list):
            for item in rate_limit:
                if isinstance(item, dict):
                    rows.append({**parent, "rate_limit_raw": item})
        else:
            flattened = {
                "is_enabled": row.get(
                    "waf_edge_raw.waf_config.address_rate_limiting.is_enabled"
                ),
                "allowed_rate_per_address": row.get(
                    "waf_edge_raw.waf_config.address_rate_limiting.allowed_rate_per_address"
                ),
                "max_delayed_count_per_address": row.get(
                    "waf_edge_raw.waf_config.address_rate_limiting.max_delayed_count_per_address"
                ),
                "block_response_code": row.get(
                    "waf_edge_raw.waf_config.address_rate_limiting.block_response_code"
                ),
            }
            if any(value is not None for value in flattened.values()):
                rows.append({**parent, "rate_limit_raw": flattened})
    return _normalize_rows(rows)


def transform_edge(df):
    if df.empty:
        return {"WAF_Edge": df}

    edge_df = df.copy()
    sheets = {"WAF_Edge": edge_df}
    optional = {
        "WAF_Edge_Custom_Rules": _extract_edge_raw_list_rows(
            edge_df, "waf_edge_enriched.custom_protection_rules", "rule_raw"
        ),
        "WAF_Edge_Access_Rules": _extract_edge_raw_list_rows(
            edge_df, "waf_edge_raw.waf_config.access_rules", "rule_raw"
        ),
        "WAF_Edge_Protection_Rules": _extract_edge_raw_list_rows(
            edge_df, "waf_edge_raw.waf_config.protection_rules", "rule_raw"
        ),
        "WAF_Edge_Rate_Limits": _extract_edge_raw_rate_limits(edge_df),
    }

    for name, sheet_df in optional.items():
        if isinstance(sheet_df, pd.DataFrame) and not sheet_df.empty:
            sheets[name] = sheet_df
    return sheets

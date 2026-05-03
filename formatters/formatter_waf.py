import json

import pandas as pd


def _safe_list(value):
    return value if isinstance(value, list) else []


def _safe_dict(value):
    return value if isinstance(value, dict) else {}


def _to_json(value):
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _series(df, candidates, default=None):
    for col in candidates:
        if col in df.columns:
            return df[col]
    return pd.Series([default] * len(df), index=df.index)


def _value(row, candidates, default=None):
    for col in candidates:
        if col in row.index:
            return row.get(col)
    return default


def _policy_identity(row):
    return {
        "waf.display_name": _value(row, ["waf_raw.display_name", "display_name"]),
        "waf.id": _value(row, ["waf_raw.id", "id"]),
        "waf.region_name": _value(row, ["waf_raw.region_name", "region_name"]),
        "waf.compartment_name": _value(row, ["waf_raw.compartment_name", "compartment_name"]),
    }


def get_preferred_columns():
    return {
        "WAF": [
            "waf.display_name",
            "waf.id",
            "waf.lifecycle_state",
            "waf.request_access_control.default_action_name",
            "waf.request_access_rules_count",
            "waf.request_protection_rules_count",
            "waf.request_protection_capabilities_count",
            "waf.request_rate_limit_rules_count",
            "waf.response_access_rules_count",
            "waf.response_protection_rules_count",
            "waf.actions_count",
            "waf.firewalls_count",
            "waf.firewall_names",
            "waf.region_name",
            "waf.compartment_name",
            "waf.time_created",
            "waf.time_updated",
            "_errors",
        ],
        "WAF_Firewalls": [
            "waf.display_name",
            "waf.id",
            "firewall.display_name",
            "firewall.id",
            "firewall.lifecycle_state",
            "firewall.backend_type",
            "firewall.load_balancer_name",
            "firewall.load_balancer_id",
            "firewall.compartment_name",
            "firewall.compartment_id",
            "firewall.time_created",
            "firewall.time_updated",
            "waf.region_name",
            "waf.compartment_name",
            "firewall.raw",
        ],
        "WAF_Request_Access": [
            "waf.display_name",
            "waf.id",
            "rule.name",
            "rule.type",
            "rule.action_name",
            "rule.condition_language",
            "rule.condition",
            "waf.region_name",
            "waf.compartment_name",
            "rule.raw",
        ],
        "WAF_Response_Access": [
            "waf.display_name",
            "waf.id",
            "rule.name",
            "rule.type",
            "rule.action_name",
            "rule.condition_language",
            "rule.condition",
            "waf.region_name",
            "waf.compartment_name",
            "rule.raw",
        ],
        "WAF_Request_Protection": [
            "waf.display_name",
            "waf.id",
            "rule.name",
            "rule.type",
            "rule.action_name",
            "rule.condition_language",
            "rule.condition",
            "rule.is_body_inspection_enabled",
            "capability.key",
            "capability.version",
            "capability.action_name",
            "capability.exclusions",
            "capability.collaborative_action_threshold",
            "capability.collaborative_weights",
            "rule.protection_capability_settings",
            "waf.region_name",
            "waf.compartment_name",
            "rule.raw",
        ],
        "WAF_Response_Protection": [
            "waf.display_name",
            "waf.id",
            "rule.name",
            "rule.type",
            "rule.action_name",
            "rule.condition_language",
            "rule.condition",
            "rule.is_body_inspection_enabled",
            "capability.key",
            "capability.version",
            "capability.action_name",
            "capability.exclusions",
            "capability.collaborative_action_threshold",
            "capability.collaborative_weights",
            "rule.protection_capability_settings",
            "waf.region_name",
            "waf.compartment_name",
            "rule.raw",
        ],
        "WAF_Request_Rate_Limits": [
            "waf.display_name",
            "waf.id",
            "rule.name",
            "rule.type",
            "rule.action_name",
            "rule.requests_per_period",
            "rule.period_in_seconds",
            "rule.condition_language",
            "rule.condition",
            "waf.region_name",
            "waf.compartment_name",
            "rule.raw",
        ],
        "WAF_Actions": [
            "waf.display_name",
            "waf.id",
            "action.name",
            "action.type",
            "waf.region_name",
            "waf.compartment_name",
            "action.raw",
        ],
    }


def get_preferred_columns_edge():
    return {
        "WAF_Edge": [
            "waf_edge.display_name",
            "waf_edge.id",
            "waf_edge.lifecycle_state",
            "waf_edge.domain",
            "waf_edge.additional_domains",
            "waf_edge.origins_count",
            "waf_edge.waf_config.is_enabled",
            "waf_edge.custom_protection_rules_count",
            "waf_edge.region_name",
            "waf_edge.compartment_name",
            "waf_edge.time_created",
            "waf_edge.time_updated",
            "_errors",
        ],
        "WAF_Edge_Custom_Rules": [
            "waf_edge.display_name",
            "waf_edge.id",
            "rule.display_name",
            "rule.id",
            "rule.action",
            "rule.lifecycle_state",
            "rule.template",
            "rule.bypass_challenges",
            "rule.mod_security_rule_ids",
            "waf_edge.region_name",
            "waf_edge.compartment_name",
            "rule.raw",
        ],
        "WAF_Edge_Access_Rules": [
            "waf_edge.display_name",
            "waf_edge.id",
            "rule.name",
            "rule.action",
            "rule.bypass_challenges",
            "rule.criteria",
            "rule.block_response_code",
            "rule.redirect_url",
            "waf_edge.region_name",
            "waf_edge.compartment_name",
            "rule.raw",
        ],
        "WAF_Edge_Protection_Rules": [
            "waf_edge.display_name",
            "waf_edge.id",
            "rule.name",
            "rule.key",
            "rule.action",
            "rule.description",
            "rule.mod_security_rule_ids",
            "rule.exclusions",
            "rule.labels",
            "waf_edge.region_name",
            "waf_edge.compartment_name",
            "rule.raw",
        ],
        "WAF_Edge_Rate_Limits": [
            "waf_edge.display_name",
            "waf_edge.id",
            "rate_limit.is_enabled",
            "rate_limit.allowed_rate_per_address",
            "rate_limit.max_delayed_count_per_address",
            "rate_limit.block_response_code",
            "waf_edge.region_name",
            "waf_edge.compartment_name",
            "rate_limit.raw",
        ],
    }


def _count_capabilities(rules):
    total = 0
    for rule in _safe_list(rules):
        if isinstance(rule, dict):
            total += len(_safe_list(rule.get("protection_capabilities")))
    return total


def _extract_access_rows(df, section_col):
    rows = []
    for _, row in df.iterrows():
        ident = _policy_identity(row)
        rules = _safe_list(_value(row, [section_col]))
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rows.append(
                {
                    **ident,
                    "rule.name": rule.get("name"),
                    "rule.type": rule.get("type"),
                    "rule.action_name": rule.get("action_name"),
                    "rule.condition_language": rule.get("condition_language"),
                    "rule.condition": rule.get("condition"),
                    "rule.raw": _to_json(rule),
                }
            )
    return pd.DataFrame(rows)


def _extract_rate_rows(df):
    rows = []
    for _, row in df.iterrows():
        ident = _policy_identity(row)
        rules = _safe_list(
            _value(row, ["waf_raw.request_rate_limiting.rules", "request_rate_limiting.rules"])
        )
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rows.append(
                {
                    **ident,
                    "rule.name": rule.get("name"),
                    "rule.type": rule.get("type"),
                    "rule.action_name": rule.get("action_name"),
                    "rule.requests_per_period": rule.get("requests_per_period"),
                    "rule.period_in_seconds": rule.get("period_in_seconds"),
                    "rule.condition_language": rule.get("condition_language"),
                    "rule.condition": rule.get("condition"),
                    "rule.raw": _to_json(rule),
                }
            )
    return pd.DataFrame(rows)


def _extract_protection_rows(df, section_col):
    rows = []
    for _, row in df.iterrows():
        ident = _policy_identity(row)
        rules = _safe_list(_value(row, [section_col]))

        for rule in rules:
            if not isinstance(rule, dict):
                continue

            capabilities = _safe_list(rule.get("protection_capabilities"))
            settings = _safe_dict(rule.get("protection_capability_settings"))

            if not capabilities:
                rows.append(
                    {
                        **ident,
                        "rule.name": rule.get("name"),
                        "rule.type": rule.get("type"),
                        "rule.action_name": rule.get("action_name"),
                        "rule.condition_language": rule.get("condition_language"),
                        "rule.condition": rule.get("condition"),
                        "rule.is_body_inspection_enabled": rule.get("is_body_inspection_enabled"),
                        "capability.key": None,
                        "capability.version": None,
                        "capability.action_name": None,
                        "capability.exclusions": None,
                        "capability.collaborative_action_threshold": None,
                        "capability.collaborative_weights": None,
                        "rule.protection_capability_settings": _to_json(settings) if settings else None,
                        "rule.raw": _to_json(rule),
                    }
                )
                continue

            for cap in capabilities:
                if not isinstance(cap, dict):
                    continue
                rows.append(
                    {
                        **ident,
                        "rule.name": rule.get("name"),
                        "rule.type": rule.get("type"),
                        "rule.action_name": rule.get("action_name"),
                        "rule.condition_language": rule.get("condition_language"),
                        "rule.condition": rule.get("condition"),
                        "rule.is_body_inspection_enabled": rule.get("is_body_inspection_enabled"),
                        "capability.key": cap.get("key"),
                        "capability.version": cap.get("version"),
                        "capability.action_name": cap.get("action_name"),
                        "capability.exclusions": _to_json(cap.get("exclusions")),
                        "capability.collaborative_action_threshold": cap.get("collaborative_action_threshold"),
                        "capability.collaborative_weights": _to_json(cap.get("collaborative_weights")),
                        "rule.protection_capability_settings": _to_json(settings) if settings else None,
                        "rule.raw": _to_json(rule),
                    }
                )
    return pd.DataFrame(rows)


def _extract_firewalls(df):
    rows = []
    for _, row in df.iterrows():
        ident = _policy_identity(row)
        firewalls = _safe_list(_value(row, ["waf_enriched.firewalls", "firewalls"]))
        for fw in firewalls:
            if not isinstance(fw, dict):
                continue
            rows.append(
                {
                    **ident,
                    "firewall.display_name": fw.get("display_name"),
                    "firewall.id": fw.get("id"),
                    "firewall.lifecycle_state": fw.get("lifecycle_state"),
                    "firewall.backend_type": fw.get("backend_type"),
                    "firewall.load_balancer_name": fw.get("load_balancer_name"),
                    "firewall.load_balancer_id": fw.get("load_balancer_id"),
                    "firewall.compartment_name": fw.get("compartment_name"),
                    "firewall.compartment_id": fw.get("compartment_id"),
                    "firewall.time_created": fw.get("time_created"),
                    "firewall.time_updated": fw.get("time_updated"),
                    "firewall.raw": _to_json(fw),
                }
            )
    return pd.DataFrame(rows)


def _extract_actions(df):
    rows = []
    for _, row in df.iterrows():
        ident = _policy_identity(row)
        actions = _safe_list(_value(row, ["waf_raw.actions", "actions"]))
        for action in actions:
            if not isinstance(action, dict):
                continue
            rows.append(
                {
                    **ident,
                    "action.name": action.get("name"),
                    "action.type": action.get("type"),
                    "action.raw": _to_json(action),
                }
            )
    return pd.DataFrame(rows)


def transform(df):
    if df.empty:
        return {"WAF": df}

    waf_df = df.copy()

    waf_df["waf.display_name"] = _series(waf_df, ["waf_raw.display_name", "display_name"])
    waf_df["waf.id"] = _series(waf_df, ["waf_raw.id", "id"])
    waf_df["waf.lifecycle_state"] = _series(waf_df, ["waf_raw.lifecycle_state", "lifecycle_state"])
    waf_df["waf.region_name"] = _series(waf_df, ["waf_raw.region_name", "region_name"])
    waf_df["waf.compartment_name"] = _series(
        waf_df, ["waf_raw.compartment_name", "compartment_name"]
    )
    waf_df["waf.time_created"] = _series(waf_df, ["waf_raw.time_created", "time_created"])
    waf_df["waf.time_updated"] = _series(waf_df, ["waf_raw.time_updated", "time_updated"])
    waf_df["waf.request_access_control.default_action_name"] = _series(
        waf_df,
        [
            "waf_raw.request_access_control.default_action_name",
            "request_access_control.default_action_name",
        ],
    )

    req_access_rules = _series(
        waf_df,
        ["waf_raw.request_access_control.rules", "request_access_control.rules"],
        default=[],
    )
    req_protection_rules = _series(
        waf_df,
        ["waf_raw.request_protection.rules", "request_protection.rules"],
        default=[],
    )
    req_rate_rules = _series(
        waf_df,
        ["waf_raw.request_rate_limiting.rules", "request_rate_limiting.rules"],
        default=[],
    )
    resp_access_rules = _series(
        waf_df,
        ["waf_raw.response_access_control.rules", "response_access_control.rules"],
        default=[],
    )
    resp_protection_rules = _series(
        waf_df,
        ["waf_raw.response_protection.rules", "response_protection.rules"],
        default=[],
    )
    actions_series = _series(waf_df, ["waf_raw.actions", "actions"], default=[])
    firewalls_series = _series(waf_df, ["waf_enriched.firewalls", "firewalls"], default=[])

    waf_df["waf.request_access_rules_count"] = req_access_rules.apply(
        lambda v: len(v) if isinstance(v, list) else 0
    )
    waf_df["waf.request_protection_rules_count"] = req_protection_rules.apply(
        lambda v: len(v) if isinstance(v, list) else 0
    )
    waf_df["waf.request_protection_capabilities_count"] = req_protection_rules.apply(
        _count_capabilities
    )
    waf_df["waf.request_rate_limit_rules_count"] = req_rate_rules.apply(
        lambda v: len(v) if isinstance(v, list) else 0
    )
    waf_df["waf.response_access_rules_count"] = resp_access_rules.apply(
        lambda v: len(v) if isinstance(v, list) else 0
    )
    waf_df["waf.response_protection_rules_count"] = resp_protection_rules.apply(
        lambda v: len(v) if isinstance(v, list) else 0
    )
    waf_df["waf.actions_count"] = actions_series.apply(
        lambda v: len(v) if isinstance(v, list) else 0
    )
    waf_df["waf.firewalls_count"] = firewalls_series.apply(
        lambda v: len(v) if isinstance(v, list) else 0
    )
    waf_df["waf.firewall_names"] = firewalls_series.apply(
        lambda items: ", ".join(
            [x.get("display_name") for x in items if isinstance(x, dict) and x.get("display_name")]
        )
        if isinstance(items, list)
        else None
    )

    firewalls_df = _extract_firewalls(waf_df)
    req_access_df = _extract_access_rows(
        waf_df,
        "waf_raw.request_access_control.rules"
        if "waf_raw.request_access_control.rules" in waf_df.columns
        else "request_access_control.rules",
    )
    resp_access_df = _extract_access_rows(
        waf_df,
        "waf_raw.response_access_control.rules"
        if "waf_raw.response_access_control.rules" in waf_df.columns
        else "response_access_control.rules",
    )
    req_protect_df = _extract_protection_rows(
        waf_df,
        "waf_raw.request_protection.rules"
        if "waf_raw.request_protection.rules" in waf_df.columns
        else "request_protection.rules",
    )
    resp_protect_df = _extract_protection_rows(
        waf_df,
        "waf_raw.response_protection.rules"
        if "waf_raw.response_protection.rules" in waf_df.columns
        else "response_protection.rules",
    )
    req_rate_df = _extract_rate_rows(waf_df)
    actions_df = _extract_actions(waf_df)

    sheets = {"WAF": waf_df}
    for name, sdf in {
        "WAF_Firewalls": firewalls_df,
        "WAF_Request_Access": req_access_df,
        "WAF_Response_Access": resp_access_df,
        "WAF_Request_Protection": req_protect_df,
        "WAF_Response_Protection": resp_protect_df,
        "WAF_Request_Rate_Limits": req_rate_df,
        "WAF_Actions": actions_df,
    }.items():
        if isinstance(sdf, pd.DataFrame) and not sdf.empty:
            sheets[name] = sdf

    return sheets


def _edge_identity(row):
    return {
        "waf_edge.display_name": _value(
            row, ["waf_edge_raw.display_name", "display_name"]
        ),
        "waf_edge.id": _value(row, ["waf_edge_raw.id", "id"]),
        "waf_edge.region_name": _value(
            row, ["waf_edge_raw.region_name", "region_name"]
        ),
        "waf_edge.compartment_name": _value(
            row, ["waf_edge_raw.compartment_name", "compartment_name"]
        ),
    }


def _extract_edge_custom_rules(df):
    rows = []
    for _, row in df.iterrows():
        ident = _edge_identity(row)
        rules = _safe_list(
            _value(
                row,
                [
                    "waf_edge_enriched.custom_protection_rules",
                    "custom_protection_rules",
                ],
            )
        )
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rows.append(
                {
                    **ident,
                    "rule.display_name": rule.get("display_name") or rule.get("name"),
                    "rule.id": rule.get("id"),
                    "rule.action": rule.get("action"),
                    "rule.lifecycle_state": rule.get("lifecycle_state"),
                    "rule.template": rule.get("template"),
                    "rule.bypass_challenges": rule.get("bypass_challenges"),
                    "rule.mod_security_rule_ids": _to_json(rule.get("mod_security_rule_ids")),
                    "rule.raw": _to_json(rule),
                }
            )
    return pd.DataFrame(rows)


def _extract_edge_access_rules(df):
    rows = []
    for _, row in df.iterrows():
        ident = _edge_identity(row)
        rules = _safe_list(
            _value(
                row,
                [
                    "waf_edge_raw.waf_config.access_rules",
                    "waf_config.access_rules",
                ],
            )
        )
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rows.append(
                {
                    **ident,
                    "rule.name": rule.get("name"),
                    "rule.action": rule.get("action"),
                    "rule.bypass_challenges": rule.get("bypass_challenges"),
                    "rule.criteria": _to_json(rule.get("criteria")),
                    "rule.block_response_code": rule.get("block_response_code"),
                    "rule.redirect_url": rule.get("redirect_url"),
                    "rule.raw": _to_json(rule),
                }
            )
    return pd.DataFrame(rows)


def _extract_edge_protection_rules(df):
    rows = []
    for _, row in df.iterrows():
        ident = _edge_identity(row)
        rules = _safe_list(
            _value(
                row,
                [
                    "waf_edge_raw.waf_config.protection_rules",
                    "waf_config.protection_rules",
                ],
            )
        )
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            rows.append(
                {
                    **ident,
                    "rule.name": rule.get("name"),
                    "rule.key": rule.get("key"),
                    "rule.action": rule.get("action"),
                    "rule.description": rule.get("description"),
                    "rule.mod_security_rule_ids": _to_json(rule.get("mod_security_rule_ids")),
                    "rule.exclusions": _to_json(rule.get("exclusions")),
                    "rule.labels": _to_json(rule.get("labels")),
                    "rule.raw": _to_json(rule),
                }
            )
    return pd.DataFrame(rows)


def _extract_edge_rate_limits(df):
    rows = []
    for _, row in df.iterrows():
        ident = _edge_identity(row)
        rate_limit = _value(
            row,
            [
                "waf_edge_raw.waf_config.address_rate_limiting",
                "waf_config.address_rate_limiting",
            ],
        )
        if isinstance(rate_limit, dict):
            rows.append(
                {
                    **ident,
                    "rate_limit.is_enabled": rate_limit.get("is_enabled"),
                    "rate_limit.allowed_rate_per_address": rate_limit.get("allowed_rate_per_address"),
                    "rate_limit.max_delayed_count_per_address": rate_limit.get(
                        "max_delayed_count_per_address"
                    ),
                    "rate_limit.block_response_code": rate_limit.get("block_response_code"),
                    "rate_limit.raw": _to_json(rate_limit),
                }
            )
        elif isinstance(rate_limit, list):
            for item in rate_limit:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    {
                        **ident,
                        "rate_limit.is_enabled": item.get("is_enabled"),
                        "rate_limit.allowed_rate_per_address": item.get(
                            "allowed_rate_per_address"
                        ),
                        "rate_limit.max_delayed_count_per_address": item.get(
                            "max_delayed_count_per_address"
                        ),
                        "rate_limit.block_response_code": item.get("block_response_code"),
                        "rate_limit.raw": _to_json(item),
                    }
                )
        else:
            is_enabled = _value(
                row,
                [
                    "waf_edge_raw.waf_config.address_rate_limiting.is_enabled",
                    "waf_config.address_rate_limiting.is_enabled",
                ],
            )
            allowed = _value(
                row,
                [
                    "waf_edge_raw.waf_config.address_rate_limiting.allowed_rate_per_address",
                    "waf_config.address_rate_limiting.allowed_rate_per_address",
                ],
            )
            delayed = _value(
                row,
                [
                    "waf_edge_raw.waf_config.address_rate_limiting.max_delayed_count_per_address",
                    "waf_config.address_rate_limiting.max_delayed_count_per_address",
                ],
            )
            code = _value(
                row,
                [
                    "waf_edge_raw.waf_config.address_rate_limiting.block_response_code",
                    "waf_config.address_rate_limiting.block_response_code",
                ],
            )
            if any(v is not None for v in [is_enabled, allowed, delayed, code]):
                rows.append(
                    {
                        **ident,
                        "rate_limit.is_enabled": is_enabled,
                        "rate_limit.allowed_rate_per_address": allowed,
                        "rate_limit.max_delayed_count_per_address": delayed,
                        "rate_limit.block_response_code": code,
                        "rate_limit.raw": _to_json(
                            {
                                "is_enabled": is_enabled,
                                "allowed_rate_per_address": allowed,
                                "max_delayed_count_per_address": delayed,
                                "block_response_code": code,
                            }
                        ),
                    }
                )
    return pd.DataFrame(rows)


def transform_edge(df):
    if df.empty:
        return {"WAF_Edge": df}

    edge_df = df.copy()
    edge_df["waf_edge.display_name"] = _series(
        edge_df, ["waf_edge_raw.display_name", "display_name"]
    )
    edge_df["waf_edge.id"] = _series(edge_df, ["waf_edge_raw.id", "id"])
    edge_df["waf_edge.lifecycle_state"] = _series(
        edge_df, ["waf_edge_raw.lifecycle_state", "lifecycle_state"]
    )
    edge_df["waf_edge.domain"] = _series(edge_df, ["waf_edge_raw.domain", "domain"])
    edge_df["waf_edge.additional_domains"] = _series(
        edge_df, ["waf_edge_raw.additional_domains", "additional_domains"], default=[]
    ).apply(lambda v: ", ".join(v) if isinstance(v, list) else None)
    edge_df["waf_edge.origins_count"] = _series(
        edge_df, ["waf_edge_raw.origins", "origins"], default=[]
    ).apply(lambda v: len(v) if isinstance(v, list) else 0)
    edge_df["waf_edge.waf_config.is_enabled"] = _series(
        edge_df,
        ["waf_edge_raw.waf_config.is_enabled", "waf_config.is_enabled"],
    )
    edge_df["waf_edge.custom_protection_rules_count"] = _series(
        edge_df,
        [
            "waf_edge_enriched.custom_protection_rules",
            "custom_protection_rules",
        ],
        default=[],
    ).apply(lambda v: len(v) if isinstance(v, list) else 0)
    edge_df["waf_edge.region_name"] = _series(
        edge_df, ["waf_edge_raw.region_name", "region_name"]
    )
    edge_df["waf_edge.compartment_name"] = _series(
        edge_df, ["waf_edge_raw.compartment_name", "compartment_name"]
    )
    edge_df["waf_edge.time_created"] = _series(
        edge_df, ["waf_edge_raw.time_created", "time_created"]
    )
    edge_df["waf_edge.time_updated"] = _series(
        edge_df, ["waf_edge_raw.time_updated", "time_updated"]
    )

    edge_custom_rules_df = _extract_edge_custom_rules(edge_df)
    edge_access_rules_df = _extract_edge_access_rules(edge_df)
    edge_protection_rules_df = _extract_edge_protection_rules(edge_df)
    edge_rate_limits_df = _extract_edge_rate_limits(edge_df)

    sheets = {"WAF_Edge": edge_df}
    for name, sdf in {
        "WAF_Edge_Custom_Rules": edge_custom_rules_df,
        "WAF_Edge_Access_Rules": edge_access_rules_df,
        "WAF_Edge_Protection_Rules": edge_protection_rules_df,
        "WAF_Edge_Rate_Limits": edge_rate_limits_df,
    }.items():
        if isinstance(sdf, pd.DataFrame) and not sdf.empty:
            sheets[name] = sdf
    return sheets


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


def _normalize_rows(rows):
    if not rows:
        return pd.DataFrame()
    return pd.json_normalize(rows)


def _extract_raw_list_rows(df, list_column, raw_key):
    rows = []
    for _, row in df.iterrows():
        parent = _waf_parent_raw(row)
        for item in _safe_list(row.get(list_column)):
            if not isinstance(item, dict):
                continue
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
                if not isinstance(capability, dict):
                    continue
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
            if not isinstance(item, dict):
                continue
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

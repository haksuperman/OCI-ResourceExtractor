import pandas as pd


PARENT_COLUMNS = [
    "object_storage_raw.name",
    "object_storage_raw.id",
    "object_storage_raw.namespace_name",
    "object_storage_raw.lifecycle_state",
    "object_storage_raw.region_name",
    "object_storage_raw.compartment_name",
]


def get_preferred_columns():
    return {
        "Object_Storage_Buckets": [
            "object_storage_raw.name",
            "object_storage_raw.id",
            "object_storage_raw.namespace_name",
            "object_storage_raw.lifecycle_state",
            "object_storage_raw.storage_tier",
            "object_storage_raw.public_access_type",
            "object_storage_raw.versioning",
            "object_storage_raw.auto_tiering",
            "object_storage_raw.object_events_enabled",
            "object_storage_raw.approximate_count",
            "object_storage_raw.approximate_size",
            "object_storage_raw.kms_key_id",
            "object_storage_raw.created_by",
            "object_storage_raw.region_name",
            "object_storage_raw.compartment_name",
            "object_storage_raw.time_created",
            "_errors",
        ],
        "Object_Storage_Retention_Rules": [
            *PARENT_COLUMNS,
            "retention_rule_raw.display_name",
            "retention_rule_raw.id",
            "retention_rule_raw.duration.time_amount",
            "retention_rule_raw.duration.time_unit",
            "retention_rule_raw.time_rule_locked",
            "retention_rule_raw.time_created",
            "retention_rule_raw.time_modified",
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
        return {"Object_Storage_Buckets": df}

    retention_rule_rows = []
    for _, row in df.iterrows():
        parent = _parent_raw(row)
        for rule in _safe_list(row.get("object_storage_enriched.retention_rules")):
            retention_rule_rows.append(
                {
                    **parent,
                    "retention_rule_raw": rule,
                }
            )

    sheets = {"Object_Storage_Buckets": df.copy()}
    retention_rule_df = _normalize_rows(retention_rule_rows)
    if not retention_rule_df.empty:
        sheets["Object_Storage_Retention_Rules"] = retention_rule_df
    return sheets

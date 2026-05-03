import pandas as pd


PARENT_COLUMNS = [
    "adb_raw.display_name",
    "adb_raw.id",
    "adb_raw.lifecycle_state",
    "adb_raw.region_name",
    "adb_raw.compartment_name",
    "adb_raw.db_name",
    "adb_raw.db_workload",
]


def get_preferred_columns():
    return {
        "Adb": [
            "adb_raw.display_name",
            "adb_raw.id",
            "adb_raw.lifecycle_state",
            "adb_raw.db_name",
            "adb_raw.db_workload",
            "adb_raw.compute_model",
            "adb_raw.compute_count",
            "adb_raw.cpu_core_count",
            "adb_raw.data_storage_size_in_tbs",
            "adb_raw.data_storage_size_in_gbs",
            "adb_raw.used_data_storage_size_in_gbs",
            "adb_raw.is_auto_scaling_enabled",
            "adb_raw.is_auto_scaling_for_storage_enabled",
            "adb_raw.license_model",
            "adb_raw.is_dedicated",
            "adb_raw.is_data_guard_enabled",
            "adb_raw.private_endpoint",
            "networking_enriched.subnet_details.display_name",
            "adb_raw.subnet_id",
            "networking_enriched.nsg_details",
            "adb_raw.nsg_ids",
            "adb_raw.db_version",
            "adb_raw.region_name",
            "adb_raw.compartment_name",
            "adb_raw.time_created",
            "_errors",
        ],
        "Adb_Backups": [
            *PARENT_COLUMNS,
            "backup_raw.display_name",
            "backup_raw.id",
            "backup_raw.type",
            "backup_raw.lifecycle_state",
            "backup_raw.is_automatic",
            "backup_raw.time_started",
            "backup_raw.time_ended",
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
        return {"Adb": df}

    backup_rows = []
    for _, row in df.iterrows():
        parent = _parent_raw(row)
        for backup in _safe_list(row.get("backup_enriched.backups")):
            backup_rows.append(
                {
                    **parent,
                    "backup_raw": backup,
                }
            )

    sheets = {"Adb": df.copy()}
    backup_df = _normalize_rows(backup_rows)
    if not backup_df.empty:
        sheets["Adb_Backups"] = backup_df
    return sheets

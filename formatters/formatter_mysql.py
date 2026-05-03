import pandas as pd


PARENT_COLUMNS = [
    "mysql_raw.display_name",
    "mysql_raw.id",
    "mysql_raw.lifecycle_state",
    "mysql_raw.region_name",
    "mysql_raw.compartment_name",
    "mysql_raw.mysql_version",
    "mysql_raw.shape_name",
]


def get_preferred_columns():
    return {
        "Mysql": [
            "mysql_raw.display_name",
            "mysql_raw.id",
            "mysql_raw.lifecycle_state",
            "mysql_raw.mysql_version",
            "mysql_raw.shape_name",
            "mysql_raw.is_highly_available",
            "mysql_raw.is_heat_wave_cluster_attached",
            "mysql_raw.endpoints",
            "mysql_raw.read_endpoint.is_enabled",
            "mysql_raw.read_endpoint.read_endpoint_ip_address",
            "mysql_raw.read_endpoint.read_endpoint_hostname_label",
            "networking_enriched.subnet_details.display_name",
            "mysql_raw.subnet_id",
            "mysql_raw.availability_domain",
            "mysql_raw.fault_domain",
            "mysql_raw.backup_policy.is_enabled",
            "mysql_raw.backup_policy.retention_in_days",
            "mysql_raw.backup_policy.pitr_policy.is_enabled",
            "mysql_raw.data_storage.allocated_storage_size_in_gbs",
            "mysql_raw.data_storage.is_auto_expand_storage_enabled",
            "mysql_raw.deletion_policy.is_delete_protected",
            "mysql_raw.crash_recovery",
            "mysql_raw.secure_connections.certificate_id",
            "mysql_raw.region_name",
            "mysql_raw.compartment_name",
            "mysql_raw.time_created",
            "_errors",
        ],
        "Mysql_Backups": [
            *PARENT_COLUMNS,
            "backup_raw.display_name",
            "backup_raw.id",
            "backup_raw.lifecycle_state",
            "backup_raw.backup_type",
            "backup_raw.creation_type",
            "backup_raw.backup_size_in_gbs",
            "backup_raw.time_created",
            "backup_raw.time_updated",
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
        return {"Mysql": df}

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

    sheets = {"Mysql": df.copy()}
    backup_df = _normalize_rows(backup_rows)
    if not backup_df.empty:
        sheets["Mysql_Backups"] = backup_df
    return sheets

import pandas as pd


PARENT_COLUMNS = [
    "dbcs_raw.display_name",
    "dbcs_raw.id",
    "dbcs_raw.lifecycle_state",
    "dbcs_raw.region_name",
    "dbcs_raw.compartment_name",
    "dbcs_raw.availability_domain",
    "dbcs_raw.fault_domain",
    "dbcs_raw.shape",
    "dbcs_raw.database_edition",
]


DB_HOME_CONTEXT_COLUMNS = [
    "db_home_raw.display_name",
    "db_home_raw.id",
    "db_home_raw.lifecycle_state",
    "db_home_raw.db_version",
]


DATABASE_CONTEXT_COLUMNS = [
    "database_raw.db_name",
    "database_raw.database_name",
    "database_raw.id",
    "database_raw.lifecycle_state",
]


def get_preferred_columns():
    return {
        "Dbcs": [
            "dbcs_raw.display_name",
            "dbcs_raw.id",
            "dbcs_raw.lifecycle_state",
            "dbcs_raw.shape",
            "dbcs_raw.cpu_core_count",
            "dbcs_raw.memory_size_in_gbs",
            "dbcs_raw.node_count",
            "dbcs_raw.data_storage_size_in_gbs",
            "dbcs_raw.reco_storage_size_in_gb",
            "dbcs_raw.database_edition",
            "dbcs_raw.license_model",
            "networking_enriched.subnet_details.display_name",
            "dbcs_raw.subnet_id",
            "networking_enriched.backup_subnet_details.display_name",
            "dbcs_raw.backup_subnet_id",
            "networking_enriched.nsg_details",
            "dbcs_raw.nsg_ids",
            "dbcs_raw.scan_dns_name",
            "dbcs_raw.listener_port",
            "dbcs_raw.cluster_name",
            "dbcs_raw.hostname",
            "dbcs_raw.domain",
            "dbcs_raw.region_name",
            "dbcs_raw.compartment_name",
            "dbcs_raw.time_created",
            "_errors",
        ],
        "Dbcs_DB_Homes": [
            *PARENT_COLUMNS,
            *DB_HOME_CONTEXT_COLUMNS,
            "db_home_raw.time_created",
        ],
        "Dbcs_Databases": [
            *PARENT_COLUMNS,
            *DB_HOME_CONTEXT_COLUMNS,
            *DATABASE_CONTEXT_COLUMNS,
            "database_raw.db_workload",
            "database_raw.db_unique_name",
            "database_raw.character_set",
            "database_raw.ncharacter_set",
            "database_raw.time_created",
        ],
        "Dbcs_Database_Backups": [
            *PARENT_COLUMNS,
            *DATABASE_CONTEXT_COLUMNS,
            "backup_raw.display_name",
            "backup_raw.id",
            "backup_raw.lifecycle_state",
            "backup_raw.type",
            "backup_raw.version",
            "backup_raw.time_started",
            "backup_raw.time_ended",
        ],
        "Dbcs_Data_Guard": [
            *PARENT_COLUMNS,
            *DATABASE_CONTEXT_COLUMNS,
            "data_guard_raw.id",
            "data_guard_raw.lifecycle_state",
            "data_guard_raw.role",
            "data_guard_raw.peer_role",
            "data_guard_raw.apply_rate",
            "data_guard_raw.apply_lag",
            "data_guard_raw.protection_mode",
            "data_guard_raw.time_created",
        ],
        "Dbcs_PDBs": [
            *PARENT_COLUMNS,
            *DATABASE_CONTEXT_COLUMNS,
            "pdb_raw.pdb_name",
            "pdb_raw.id",
            "pdb_raw.lifecycle_state",
            "pdb_raw.open_mode",
            "pdb_raw.management_status",
            "pdb_raw.time_created",
        ],
        "Dbcs_Nodes": [
            *PARENT_COLUMNS,
            "db_node_raw.hostname",
            "db_node_raw.id",
            "db_node_raw.lifecycle_state",
            "db_node_raw.fault_domain",
            "db_node_raw.vnic_id",
            "db_node_raw.backup_vnic_id",
            "db_node_raw.vnic2_id",
            "db_node_raw.backup_vnic2_id",
            "db_node_raw.host_ip_id",
            "db_node_raw.backup_ip_id",
            "db_node_raw.vnic_details.private_ip",
            "db_node_raw.backup_vnic_details.private_ip",
            "db_node_raw.host_ip_details.ip_address",
            "db_node_raw.backup_ip_details.ip_address",
            "db_node_raw.time_created",
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


def _db_home_context(db_home):
    return {"db_home_raw": db_home}


def _database_context(database):
    return {"database_raw": database}


def _normalize_rows(rows):
    if not rows:
        return pd.DataFrame()
    return pd.json_normalize(rows)


def _extract_db_homes(df):
    rows = []
    for _, row in df.iterrows():
        parent = _parent_raw(row)
        for home in _safe_list(row.get("dbcs_enriched.db_homes")):
            rows.append(
                {
                    **parent,
                    "db_home_raw": home,
                }
            )
    return _normalize_rows(rows)


def _extract_databases(df):
    rows = []
    for _, row in df.iterrows():
        parent = _parent_raw(row)
        for home in _safe_list(row.get("dbcs_enriched.db_homes")):
            for database in _safe_list(home.get("databases") if isinstance(home, dict) else []):
                rows.append(
                    {
                        **parent,
                        **_db_home_context(home),
                        "database_raw": database,
                    }
                )
    return _normalize_rows(rows)


def _extract_database_backups(df):
    rows = []
    for _, row in df.iterrows():
        parent = _parent_raw(row)
        for home in _safe_list(row.get("dbcs_enriched.db_homes")):
            for database in _safe_list(home.get("databases") if isinstance(home, dict) else []):
                for backup in _safe_list(
                    database.get("backups") if isinstance(database, dict) else []
                ):
                    rows.append(
                        {
                            **parent,
                            **_database_context(database),
                            "backup_raw": backup,
                        }
                    )
    return _normalize_rows(rows)


def _extract_data_guard(df):
    rows = []
    for _, row in df.iterrows():
        parent = _parent_raw(row)
        for home in _safe_list(row.get("dbcs_enriched.db_homes")):
            for database in _safe_list(home.get("databases") if isinstance(home, dict) else []):
                for association in _safe_list(
                    database.get("dataguard_associations")
                    if isinstance(database, dict)
                    else []
                ):
                    rows.append(
                        {
                            **parent,
                            **_database_context(database),
                            "data_guard_raw": association,
                        }
                    )
    return _normalize_rows(rows)


def _extract_pdbs(df):
    rows = []
    for _, row in df.iterrows():
        parent = _parent_raw(row)
        for home in _safe_list(row.get("dbcs_enriched.db_homes")):
            for database in _safe_list(home.get("databases") if isinstance(home, dict) else []):
                for pdb in _safe_list(
                    database.get("pluggable_databases")
                    if isinstance(database, dict)
                    else []
                ):
                    rows.append(
                        {
                            **parent,
                            **_database_context(database),
                            "pdb_raw": pdb,
                        }
                    )
    return _normalize_rows(rows)


def _extract_db_nodes(df):
    rows = []
    for _, row in df.iterrows():
        parent = _parent_raw(row)
        for node in _safe_list(row.get("dbcs_enriched.db_nodes")):
            rows.append(
                {
                    **parent,
                    "db_node_raw": node,
                }
            )
    return _normalize_rows(rows)


def transform(df):
    if df.empty:
        return {"Dbcs": df}

    sheets = {"Dbcs": df.copy()}

    for name, sheet_df in {
        "Dbcs_DB_Homes": _extract_db_homes(df),
        "Dbcs_Databases": _extract_databases(df),
        "Dbcs_Database_Backups": _extract_database_backups(df),
        "Dbcs_Data_Guard": _extract_data_guard(df),
        "Dbcs_PDBs": _extract_pdbs(df),
        "Dbcs_Nodes": _extract_db_nodes(df),
    }.items():
        if isinstance(sheet_df, pd.DataFrame) and not sheet_df.empty:
            sheets[name] = sheet_df

    return sheets

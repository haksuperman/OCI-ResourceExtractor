import pandas as pd


def get_preferred_columns():
    return {
        "File_Systems": [
            "file_storage_raw.display_name",
            "file_storage_raw.id",
            "file_storage_raw.lifecycle_state",
            "file_storage_raw.metered_bytes",
            "file_storage_raw.kms_key_id",
            "file_storage_raw.availability_domain_name",
            "file_storage_raw.region_name",
            "file_storage_raw.compartment_name",
            "file_storage_raw.time_created",
            "_errors",
        ],
        "Mount_Targets": [
            "file_storage_raw.display_name",
            "file_storage_raw.id",
            "file_storage_raw.lifecycle_state",
            "networking_enriched.subnet_details.display_name",
            "file_storage_raw.subnet_id",
            "file_storage_raw.private_ip_ids",
            "networking_enriched.nsg_details",
            "file_storage_raw.nsg_ids",
            "file_storage_raw.availability_domain_name",
            "file_storage_raw.region_name",
            "file_storage_raw.compartment_name",
            "file_storage_raw.time_created",
            "_errors",
        ],
        "Export_Sets": [
            "file_storage_raw.display_name",
            "file_storage_raw.id",
            "file_storage_raw.lifecycle_state",
            "file_storage_raw.mount_target_id",
            "file_storage_raw.max_fs_stat_bytes",
            "file_storage_raw.max_fs_stat_files",
            "file_storage_raw.availability_domain_name",
            "file_storage_raw.region_name",
            "file_storage_raw.compartment_name",
            "file_storage_raw.time_created",
            "_errors",
        ],
        "Exports": [
            "file_storage_raw.id",
            "file_storage_raw.lifecycle_state",
            "file_storage_raw.path",
            "file_storage_raw.file_system_id",
            "file_storage_raw.export_set_id",
            "file_storage_raw.export_options",
            "file_storage_raw.region_name",
            "file_storage_raw.compartment_name",
            "file_storage_raw.time_created",
            "_errors",
        ],
        "Snapshots": [
            "file_storage_raw.name",
            "file_storage_raw.id",
            "file_storage_raw.lifecycle_state",
            "file_storage_raw.file_system_id",
            "file_storage_raw.time_snapshot",
            "file_storage_raw.expiration_time",
            "file_storage_raw.region_name",
            "file_storage_raw.compartment_name",
            "file_storage_raw.time_created",
            "_errors",
        ],
        "Snapshot_Policies": [
            "file_storage_raw.display_name",
            "file_storage_raw.id",
            "file_storage_raw.lifecycle_state",
            "file_storage_raw.prefix",
            "file_storage_raw.schedules",
            "file_storage_raw.availability_domain_name",
            "file_storage_raw.region_name",
            "file_storage_raw.compartment_name",
            "file_storage_raw.time_created",
            "_errors",
        ],
        "Replications": [
            "file_storage_raw.display_name",
            "file_storage_raw.id",
            "file_storage_raw.lifecycle_state",
            "file_storage_raw.source_id",
            "file_storage_raw.target_region_name",
            "file_storage_raw.target_id",
            "file_storage_raw.availability_domain_name",
            "file_storage_raw.region_name",
            "file_storage_raw.compartment_name",
            "file_storage_raw.time_created",
            "_errors",
        ],
    }


def _subset(df, resource_type):
    if df.empty or "file_storage_raw.resource_type" not in df.columns:
        return pd.DataFrame()
    return df[df["file_storage_raw.resource_type"] == resource_type].copy()


def transform(df):
    if df.empty:
        return {"File_Systems": df}

    sheets = {
        "File_Systems": _subset(df, "file_system"),
        "Mount_Targets": _subset(df, "mount_target"),
        "Export_Sets": _subset(df, "export_set"),
        "Exports": _subset(df, "export"),
        "Snapshots": _subset(df, "snapshot"),
        "Snapshot_Policies": _subset(df, "snapshot_policy"),
        "Replications": _subset(df, "replication"),
    }

    return {
        name: sheet
        for name, sheet in sheets.items()
        if isinstance(sheet, pd.DataFrame) and not sheet.empty
    }

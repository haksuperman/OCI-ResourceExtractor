import pandas as pd


def get_preferred_columns():
    volume_context = [
        "block_storage_raw.compartment_name",
        "block_storage_raw.region_name",
        "block_storage_raw.availability_domain_name",
        "block_storage_raw.display_name",
        "block_storage_raw.id",
    ]
    return {
        "Block_Volumes": [
            "block_storage_raw.display_name",
            "block_storage_raw.id",
            "block_storage_raw.lifecycle_state",
            "block_storage_raw.size_in_gbs",
            "block_storage_raw.vpus_per_gb",
            "block_storage_raw.is_auto_tune_enabled",
            "block_storage_raw.kms_key_id",
            "block_storage_enriched.is_backup_policy_assigned",
            "block_storage_enriched.backup_policy_display_name",
            "block_storage_enriched.backup_policy_id",
            "block_storage_enriched.backup_policy_assignment_id",
            "block_storage_enriched.backup_policy_time_assigned",
            "block_storage_enriched.volume_attachments",
            "block_storage_raw.availability_domain_name",
            "block_storage_raw.region_name",
            "block_storage_raw.compartment_name",
            "block_storage_raw.time_created",
            "_errors",
        ],
        "Boot_Volumes": [
            "block_storage_raw.display_name",
            "block_storage_raw.id",
            "block_storage_raw.lifecycle_state",
            "block_storage_raw.size_in_gbs",
            "block_storage_raw.kms_key_id",
            "block_storage_enriched.is_backup_policy_assigned",
            "block_storage_enriched.backup_policy_display_name",
            "block_storage_enriched.backup_policy_id",
            "block_storage_enriched.backup_policy_assignment_id",
            "block_storage_enriched.backup_policy_time_assigned",
            "block_storage_enriched.boot_volume_attachments",
            "block_storage_raw.availability_domain_name",
            "block_storage_raw.region_name",
            "block_storage_raw.compartment_name",
            "block_storage_raw.time_created",
            "_errors",
        ],
        "Block_Volume_Attachments": volume_context
        + [
            "attachment_raw.display_name",
            "attachment_raw.id",
            "attachment_raw.lifecycle_state",
            "attachment_raw.attachment_type",
            "attachment_raw.type",
            "attachment_raw.instance_id",
            "attachment_raw.volume_id",
            "attachment_raw.device",
            "attachment_raw.is_read_only",
            "attachment_raw.is_shareable",
            "attachment_raw.time_created",
        ],
        "Boot_Volume_Attachments": volume_context
        + [
            "attachment_raw.display_name",
            "attachment_raw.id",
            "attachment_raw.lifecycle_state",
            "attachment_raw.attachment_type",
            "attachment_raw.type",
            "attachment_raw.instance_id",
            "attachment_raw.boot_volume_id",
            "attachment_raw.device",
            "attachment_raw.is_read_only",
            "attachment_raw.time_created",
        ],
        "Block_Volume_Backups": [
            "block_storage_raw.display_name",
            "block_storage_raw.id",
            "block_storage_raw.lifecycle_state",
            "block_storage_raw.type",
            "block_storage_raw.volume_id",
            "block_storage_raw.unique_size_in_gbs",
            "block_storage_raw.size_in_gbs",
            "block_storage_raw.availability_domain_name",
            "block_storage_raw.region_name",
            "block_storage_raw.compartment_name",
            "block_storage_raw.time_created",
            "_errors",
        ],
        "Boot_Volume_Backups": [
            "block_storage_raw.display_name",
            "block_storage_raw.id",
            "block_storage_raw.lifecycle_state",
            "block_storage_raw.type",
            "block_storage_raw.boot_volume_id",
            "block_storage_raw.unique_size_in_gbs",
            "block_storage_raw.size_in_gbs",
            "block_storage_raw.availability_domain_name",
            "block_storage_raw.region_name",
            "block_storage_raw.compartment_name",
            "block_storage_raw.time_created",
            "_errors",
        ],
        "Volume_Groups": [
            "block_storage_raw.display_name",
            "block_storage_raw.id",
            "block_storage_raw.lifecycle_state",
            "block_storage_raw.source_details.type",
            "block_storage_raw.volume_ids",
            "block_storage_raw.availability_domain_name",
            "block_storage_raw.region_name",
            "block_storage_raw.compartment_name",
            "block_storage_raw.time_created",
            "_errors",
        ],
        "Volume_Group_Backups": [
            "block_storage_raw.display_name",
            "block_storage_raw.id",
            "block_storage_raw.lifecycle_state",
            "block_storage_raw.type",
            "block_storage_raw.volume_group_id",
            "block_storage_raw.unique_size_in_gbs",
            "block_storage_raw.size_in_gbs",
            "block_storage_raw.region_name",
            "block_storage_raw.compartment_name",
            "block_storage_raw.time_created",
            "_errors",
        ],
    }


def _series(df, candidates, default=None):
    for col in candidates:
        if col in df.columns:
            return df[col]
    return pd.Series([default] * len(df), index=df.index)


def _subset(df, resource_type):
    if df.empty:
        return df
    resource_types = _series(df, ["block_storage_raw.resource_type", "resource_type"])
    return df[resource_types == resource_type].copy()


def _safe_list(value):
    return value if isinstance(value, list) else []


def _parent_raw(row):
    return {
        "display_name": row.get("block_storage_raw.display_name"),
        "id": row.get("block_storage_raw.id"),
        "lifecycle_state": row.get("block_storage_raw.lifecycle_state"),
        "resource_type": row.get("block_storage_raw.resource_type"),
        "size_in_gbs": row.get("block_storage_raw.size_in_gbs"),
        "availability_domain_name": row.get("block_storage_raw.availability_domain_name"),
        "region_name": row.get("block_storage_raw.region_name"),
        "compartment_name": row.get("block_storage_raw.compartment_name"),
    }


def _attachment_rows(parent_df, source_col):
    rows = []
    if parent_df.empty:
        return pd.DataFrame()

    for _, row in parent_df.iterrows():
        parent = _parent_raw(row)
        for attachment in _safe_list(row.get(source_col)):
            if isinstance(attachment, dict):
                rows.append(
                    {
                        "block_storage_raw": parent,
                        "attachment_raw": attachment,
                    }
                )

    return pd.json_normalize(rows) if rows else pd.DataFrame()


def transform(df):
    if df.empty:
        return {"Block_Volumes": df}

    block_volumes = _subset(df, "volume")
    boot_volumes = _subset(df, "boot_volume")

    sheets = {
        "Block_Volumes": block_volumes,
        "Boot_Volumes": boot_volumes,
        "Block_Volume_Attachments": _attachment_rows(
            block_volumes,
            "block_storage_enriched.volume_attachments",
        ),
        "Boot_Volume_Attachments": _attachment_rows(
            boot_volumes,
            "block_storage_enriched.boot_volume_attachments",
        ),
        "Block_Volume_Backups": _subset(df, "volume_backup"),
        "Boot_Volume_Backups": _subset(df, "boot_volume_backup"),
        "Volume_Groups": _subset(df, "volume_group"),
        "Volume_Group_Backups": _subset(df, "volume_group_backup"),
    }

    return {
        name: sheet
        for name, sheet in sheets.items()
        if isinstance(sheet, pd.DataFrame) and not sheet.empty
    }

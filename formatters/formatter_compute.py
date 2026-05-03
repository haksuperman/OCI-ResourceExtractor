def get_preferred_columns():
    # Raw-only priority columns for the Compute sheet.
    # No derived/alias columns are added at formatter level.
    return [
        "compute_raw.display_name",
        "compute_raw.id",
        "compute_raw.lifecycle_state",
        "compute_raw.shape",
        "compute_raw.shape_config.ocpus",
        "compute_raw.shape_config.memory_in_gbs",
        "compute_raw.image_details.operating_system",
        "compute_raw.image_details.operating_system_version",
        "compute_raw.image_details.display_name",
        "compute_raw.availability_domain",
        "compute_raw.fault_domain",
        "networking_enriched.public_ip",
        "networking_enriched.private_ip",
        "networking_enriched.vcn_name",
        "networking_enriched.subnet_name",
        "storage_enriched.boot_volume_name",
        "storage_enriched.boot_volume_size_in_gbs",
        "storage_enriched.block_volume_name",
        "storage_enriched.block_volume_size_in_gbs",
        "storage_enriched.block_volume_attachment_type",
        "compute_enriched.instance_pool_names",
        "compute_enriched.autoscaling_configuration_names",
        "compute_enriched.console_connection_count",
        "compute_enriched.agent_plugin_count",
        "compute_enriched.capacity_reservation.display_name",
        "compute_enriched.capacity_reservation.id",
        "compute_raw.time_created",
        "storage_enriched.block_volume_attachments",
        "compute_raw.region_name",
        "compute_raw.compartment_name",
        "networking_enriched.vnics",
        "networking_enriched.vnic_attachments",
        "storage_enriched.boot_volume_details_all",
        "storage_enriched.boot_volume_attachments",
        "storage_enriched.block_volume_details",
        "compute_enriched.instance_pools",
        "compute_enriched.autoscaling_configurations",
        "compute_enriched.console_connections",
        "compute_enriched.agent_plugin_status",
        "compute_enriched.capacity_reservation",
        "compute_enriched.capacity_reservation_instance",
    ]


def transform(df):
    # Keep raw data as-is for Compute.
    # Column ordering/styling is handled by formatter_base using preferred raw columns.
    return df

import pandas as pd


PARENT_CONTEXT_COLUMNS = [
    "instance_pool_raw.display_name",
    "instance_pool_raw.id",
    "instance_pool_raw.lifecycle_state",
    "instance_pool_raw.size",
    "instance_pool_raw.region_name",
    "instance_pool_raw.compartment_name",
    "instance_pool_raw.instance_configuration_id",
]


def get_preferred_columns():
    parent_context = [
        "instance_pool_raw.compartment_name",
        "instance_pool_raw.region_name",
        "instance_pool_raw.display_name",
        "instance_pool_raw.id",
    ]
    autoscaling_context = parent_context + [
        "auto_scaling_configuration_raw.display_name",
        "auto_scaling_configuration_raw.id",
    ]

    return {
        "Instance_Pools": [
            "instance_pool_raw.display_name",
            "instance_pool_raw.id",
            "instance_pool_raw.lifecycle_state",
            "instance_pool_raw.size",
            "pool_instances_enriched.instance_count",
            "pool_instances_enriched.instance_names",
            "instance_configuration_enriched.display_name",
            "instance_configuration_enriched.id",
            "autoscaling_enriched.configuration_names",
            "autoscaling_enriched.configuration_count",
            "autoscaling_enriched.enabled_configuration_count",
            "autoscaling_enriched.is_enabled",
            "autoscaling_enriched.min_resource_count",
            "autoscaling_enriched.max_resource_count",
            "autoscaling_enriched.cool_down_in_seconds",
            "autoscaling_enriched.policy_count",
            "autoscaling_enriched.policy_names",
            "load_balancer_enriched.load_balancer_names",
            "load_balancer_enriched.load_balancer_ids",
            "load_balancer_enriched.load_balancer_types",
            "load_balancer_enriched.attachment_count",
            "load_balancer_enriched.backend_set_names",
            "load_balancer_enriched.ports",
            "load_balancer_enriched.vnic_selections",
            "load_balancer_enriched.lifecycle_states",
            "instance_pool_raw.instance_configuration_id",
            "instance_pool_raw.placement_configurations",
            "instance_pool_raw.load_balancers",
            "instance_pool_raw.time_created",
            "instance_pool_raw.region_name",
            "instance_pool_raw.compartment_name",
            "pool_instances_enriched.instances",
            "autoscaling_enriched.configurations",
            "load_balancer_enriched.attachments",
            "_errors",
        ],
        "Instance_Pool_Instances": parent_context
        + [
            "pool_instance_raw.display_name",
            "pool_instance_raw.id",
            "pool_instance_raw.lifecycle_state",
            "pool_instance_raw.state",
            "pool_instance_raw.shape",
            "pool_instance_raw.availability_domain",
            "pool_instance_raw.fault_domain",
            "pool_instance_raw.instance_configuration_id",
            "pool_instance_raw.load_balancer_backends",
            "pool_instance_raw.time_created",
        ],
        "Instance_Configurations": parent_context
        + [
            "instance_configuration_raw.display_name",
            "instance_configuration_raw.id",
            "instance_configuration_raw.instance_details.instance_type",
            "instance_configuration_raw.instance_details.launch_details.shape",
            "instance_configuration_raw.instance_details.launch_details.source_details.source_type",
            "instance_configuration_raw.instance_details.launch_details.create_vnic_details.subnet_id",
            "instance_configuration_raw.time_created",
        ],
        "Autoscaling_Configurations": parent_context
        + [
            "auto_scaling_configuration_raw.display_name",
            "auto_scaling_configuration_raw.id",
            "auto_scaling_configuration_raw.is_enabled",
            "auto_scaling_configuration_raw.min_resource_count",
            "auto_scaling_configuration_raw.max_resource_count",
            "auto_scaling_configuration_raw.cool_down_in_seconds",
            "auto_scaling_configuration_raw.resource.id",
            "auto_scaling_configuration_raw.resource.type",
            "auto_scaling_configuration_raw.time_created",
        ],
        "Autoscaling_Policies": autoscaling_context
        + [
            "auto_scaling_policy_raw.display_name",
            "auto_scaling_policy_raw.id",
            "auto_scaling_policy_raw.policy_type",
            "auto_scaling_policy_raw.is_enabled",
            "auto_scaling_policy_raw.capacity.initial",
            "auto_scaling_policy_raw.capacity.min",
            "auto_scaling_policy_raw.capacity.max",
            "auto_scaling_policy_raw.rules",
            "auto_scaling_policy_raw.execution_schedule",
            "auto_scaling_policy_raw.resource_action",
            "auto_scaling_policy_raw.time_created",
        ],
        "Instance_Pool_LB_Attachments": parent_context
        + [
            "lb_attachment_raw.load_balancer_id",
            "load_balancer_raw.display_name",
            "network_load_balancer_raw.display_name",
            "lb_attachment_raw.backend_set_name",
            "lb_attachment_raw.port",
            "lb_attachment_raw.vnic_selection",
            "lb_attachment_raw.lifecycle_state",
            "lb_attachment_raw.id",
            "load_balancer_raw.lifecycle_state",
            "network_load_balancer_raw.lifecycle_state",
        ],
    }


def _safe_list(value):
    return value if isinstance(value, list) else []


def _set_nested(target, path, value):
    current = target
    for key in path[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[path[-1]] = value


def _extract_prefixed(row, prefix):
    result = {}
    prefix_dot = f"{prefix}."
    for column, value in row.items():
        if not isinstance(column, str) or not column.startswith(prefix_dot):
            continue
        path = column[len(prefix_dot) :].split(".")
        _set_nested(result, path, value)
    return result


def _parent_raw(row):
    return {
        column.split(".", 1)[1]: row.get(column)
        for column in PARENT_CONTEXT_COLUMNS
        if column in row.index
    }


def _normalize_rows(rows):
    if not rows:
        return pd.DataFrame()
    return pd.json_normalize(rows)


def transform(df):
    sheets = {"Instance_Pools": df.copy()}
    if df.empty:
        return sheets

    pool_instance_rows = []
    instance_configuration_rows = []
    autoscaling_configuration_rows = []
    autoscaling_policy_rows = []
    lb_attachment_rows = []

    for _, row in df.iterrows():
        parent = _parent_raw(row)

        for pool_instance in _safe_list(row.get("pool_instances_enriched.instances")):
            if isinstance(pool_instance, dict):
                pool_instance_rows.append(
                    {
                        "instance_pool_raw": parent,
                        "pool_instance_raw": pool_instance,
                    }
                )

        instance_configuration = _extract_prefixed(
            row,
            "instance_configuration_enriched.instance_configuration",
        )
        if instance_configuration.get("id"):
            instance_configuration_rows.append(
                {
                    "instance_pool_raw": parent,
                    "instance_configuration_raw": instance_configuration,
                }
            )

        for configuration in _safe_list(row.get("autoscaling_enriched.configurations")):
            if not isinstance(configuration, dict):
                continue
            configuration_raw = configuration.get("auto_scaling_configuration_raw")
            if not isinstance(configuration_raw, dict):
                continue
            autoscaling_configuration_rows.append(
                {
                    "instance_pool_raw": parent,
                    "auto_scaling_configuration_raw": configuration_raw,
                    "_errors": configuration.get("_errors") or [],
                }
            )

            for policy in _safe_list(configuration.get("policies")):
                if not isinstance(policy, dict):
                    continue
                policy_raw = policy.get("auto_scaling_policy_raw")
                if not isinstance(policy_raw, dict):
                    continue
                autoscaling_policy_rows.append(
                    {
                        "instance_pool_raw": parent,
                        "auto_scaling_configuration_raw": configuration_raw,
                        "auto_scaling_policy_raw": policy_raw,
                        "_errors": policy.get("_errors") or [],
                    }
                )

        for attachment in _safe_list(row.get("load_balancer_enriched.attachments")):
            if not isinstance(attachment, dict):
                continue
            lb_attachment_rows.append(
                {
                    "instance_pool_raw": parent,
                    "lb_attachment_raw": attachment.get("attachment_raw") or {},
                    "load_balancer_raw": attachment.get("load_balancer_raw"),
                    "network_load_balancer_raw": attachment.get(
                        "network_load_balancer_raw"
                    ),
                    "_errors": attachment.get("_errors") or [],
                }
            )

    optional_sheets = {
        "Instance_Pool_Instances": _normalize_rows(pool_instance_rows),
        "Instance_Configurations": _normalize_rows(instance_configuration_rows),
        "Autoscaling_Configurations": _normalize_rows(autoscaling_configuration_rows),
        "Autoscaling_Policies": _normalize_rows(autoscaling_policy_rows),
        "Instance_Pool_LB_Attachments": _normalize_rows(lb_attachment_rows),
    }

    for sheet_name, sheet_df in optional_sheets.items():
        if isinstance(sheet_df, pd.DataFrame) and not sheet_df.empty:
            sheets[sheet_name] = sheet_df

    return sheets

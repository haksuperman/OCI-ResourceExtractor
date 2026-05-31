import pandas as pd


USER_CONTEXT_COLUMNS = [
    "identity_raw.name",
    "identity_raw.id",
    "identity_raw.lifecycle_state",
    "identity_raw.compartment_name",
]

TAG_NAMESPACE_CONTEXT_COLUMNS = [
    "identity_raw.name",
    "identity_raw.id",
    "identity_raw.lifecycle_state",
    "identity_raw.compartment_name",
]


def get_preferred_columns():
    return {
        "IAM_Users": [
            "identity_raw.name",
            "identity_raw.id",
            "identity_raw.lifecycle_state",
            "identity_raw.email",
            "identity_raw.email_verified",
            "identity_raw.is_mfa_activated",
            "identity_raw.capabilities.can_use_console_password",
            "identity_raw.capabilities.can_use_api_keys",
            "identity_raw.capabilities.can_use_auth_tokens",
            "identity_raw.capabilities.can_use_customer_secret_keys",
            "identity_raw.capabilities.can_use_smtp_credentials",
            "identity_raw.capabilities.can_use_db_credentials",
            "identity_raw.identity_provider_id",
            "identity_raw.external_identifier",
            "identity_raw.time_created",
            "identity_enriched.group_memberships",
            "_errors",
        ],
        "IAM_Groups": [
            "identity_raw.name",
            "identity_raw.id",
            "identity_raw.lifecycle_state",
            "identity_raw.description",
            "identity_raw.time_created",
            "_errors",
        ],
        "IAM_Dynamic_Groups": [
            "identity_raw.name",
            "identity_raw.id",
            "identity_raw.lifecycle_state",
            "identity_raw.matching_rule",
            "identity_raw.description",
            "identity_raw.time_created",
            "_errors",
        ],
        "IAM_Policies": [
            "identity_raw.compartment_name",
            "identity_raw.name",
            "identity_raw.id",
            "identity_raw.lifecycle_state",
            "identity_raw.statements",
            "identity_raw.version_date",
            "identity_raw.description",
            "identity_raw.time_created",
            "_errors",
        ],
        "IAM_Compartments": [
            "identity_raw.name",
            "identity_raw.id",
            "identity_raw.lifecycle_state",
            "identity_raw.parent_compartment_id",
            "identity_raw.description",
            "identity_raw.time_created",
            "_errors",
        ],
        "IAM_Tag_Namespaces": [
            "identity_raw.compartment_name",
            "identity_raw.name",
            "identity_raw.id",
            "identity_raw.lifecycle_state",
            "identity_raw.is_retired",
            "identity_raw.description",
            "identity_raw.time_created",
            "identity_enriched.tags",
            "_errors",
        ],
        "IAM_Tags": [
            "tag_namespace_raw.compartment_name",
            "tag_namespace_raw.name",
            "tag_namespace_raw.id",
            "tag_raw.name",
            "tag_raw.id",
            "tag_raw.lifecycle_state",
            "tag_raw.is_retired",
            "tag_raw.is_cost_tracking",
            "tag_raw.description",
            "tag_raw.validator",
            "tag_raw.time_created",
        ],
        "IAM_Network_Sources": [
            "identity_raw.name",
            "identity_raw.id",
            "identity_raw.lifecycle_state",
            "identity_raw.description",
            "identity_raw.public_source_list",
            "identity_raw.virtual_source_list",
            "identity_raw.services",
            "identity_raw.time_created",
            "_errors",
        ],
        "IAM_User_Group_Memberships": [
            "user_raw.name",
            "user_raw.id",
            "group_membership_raw.group_name",
            "group_membership_raw.group_id",
            "group_membership_raw.user_name",
            "group_membership_raw.user_id",
            "group_membership_raw.id",
            "group_membership_raw.time_created",
        ],
    }


def _safe_list(value):
    return value if isinstance(value, list) else []


def _filter_resource_type(df, resource_type):
    if "identity_raw.resource_type" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    return df[df["identity_raw.resource_type"] == resource_type].copy()


def _context_raw(row, columns):
    return {
        column.split(".", 1)[1]: row.get(column)
        for column in columns
        if column in row.index
    }


def _normalize_rows(rows):
    if not rows:
        return pd.DataFrame()
    return pd.json_normalize(rows)


def transform(df):
    if df.empty:
        return {"IAM_Users": df}

    users_df = _filter_resource_type(df, "user")
    groups_df = _filter_resource_type(df, "group")
    dynamic_groups_df = _filter_resource_type(df, "dynamic_group")
    policies_df = _filter_resource_type(df, "policy")
    compartments_df = _filter_resource_type(df, "compartment")
    tag_namespaces_df = _filter_resource_type(df, "tag_namespace")
    network_sources_df = _filter_resource_type(df, "network_source")

    sheets = {}
    for sheet_name, sheet_df in [
        ("IAM_Users", users_df),
        ("IAM_Groups", groups_df),
        ("IAM_Dynamic_Groups", dynamic_groups_df),
        ("IAM_Policies", policies_df),
        ("IAM_Compartments", compartments_df),
        ("IAM_Tag_Namespaces", tag_namespaces_df),
        ("IAM_Network_Sources", network_sources_df),
    ]:
        if not sheet_df.empty:
            sheets[sheet_name] = sheet_df

    membership_rows = []
    for _, row in users_df.iterrows():
        user_raw = _context_raw(row, USER_CONTEXT_COLUMNS)
        for membership in _safe_list(row.get("identity_enriched.group_memberships")):
            if isinstance(membership, dict):
                membership_rows.append(
                    {
                        "user_raw": user_raw,
                        "group_membership_raw": membership,
                    }
                )

    tag_rows = []
    for _, row in tag_namespaces_df.iterrows():
        tag_namespace_raw = _context_raw(row, TAG_NAMESPACE_CONTEXT_COLUMNS)
        for tag in _safe_list(row.get("identity_enriched.tags")):
            if isinstance(tag, dict):
                tag_rows.append(
                    {
                        "tag_namespace_raw": tag_namespace_raw,
                        "tag_raw": tag,
                    }
                )

    memberships_df = _normalize_rows(membership_rows)
    if not memberships_df.empty:
        sheets["IAM_User_Group_Memberships"] = memberships_df

    tags_df = _normalize_rows(tag_rows)
    if not tags_df.empty:
        sheets["IAM_Tags"] = tags_df

    if not sheets:
        sheets["IAM_Users"] = users_df
    return sheets

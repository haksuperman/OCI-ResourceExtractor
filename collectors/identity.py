import json
import os

import oci

import common
from log_utils import log_event


SERVICE_NAME = "identity"
GLOBAL_REGION = "global"


RESOURCE_TYPE_LABELS = {
    "user": "User",
    "group": "Group",
    "dynamic_group": "Dynamic Group",
    "policy": "Policy",
    "compartment": "Compartment",
    "tag_namespace": "Tag Namespace",
    "network_source": "Network Source",
}

RESOURCE_TYPE_ORDER = {
    "user": 10,
    "group": 20,
    "dynamic_group": 30,
    "policy": 40,
    "compartment": 50,
    "tag_namespace": 60,
    "network_source": 70,
}


def _log(level, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        SERVICE_NAME,
        event,
        region=GLOBAL_REGION,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def _exception_fields(exc):
    return {
        "status": getattr(exc, "status", None),
        "code": getattr(exc, "code", None),
        "message": getattr(exc, "message", str(exc)),
    }


def _exception_detail(exc):
    if isinstance(exc, oci.exceptions.ServiceError):
        return common.service_error_detail(exc)
    return str(exc)


def _to_dict(value):
    if value is None:
        return {}
    return oci.util.to_dict(value)


def _sort_key(raw):
    if not isinstance(raw, dict):
        return ("", "", "")
    return (
        str(raw.get("compartment_name") or ""),
        str(raw.get("name") or raw.get("display_name") or ""),
        str(raw.get("id") or ""),
    )


def _sort_list(rows):
    return sorted([row for row in rows if isinstance(row, dict)], key=_sort_key)


def _resource_sort_key(resource):
    raw = resource.get("identity_raw") or {}
    return (
        RESOURCE_TYPE_ORDER.get(raw.get("resource_type"), 99),
        str(raw.get("compartment_name") or ""),
        str(raw.get("name") or raw.get("display_name") or ""),
        str(raw.get("id") or ""),
    )


def _list_resources(list_call, compartment_name, event, **kwargs):
    try:
        response = common.list_call_get_all_results(list_call, **kwargs)
        rows = [_to_dict(item) for item in response.data]
        _log(
            "INFO",
            compartment_name,
            event,
            count=len(rows),
        )
        return _sort_list(rows), 0, None
    except Exception as exc:
        detail = _exception_detail(exc)
        _log(
            "WARN",
            compartment_name,
            f"{event}_failed",
            detail=detail,
            **_exception_fields(exc),
        )
        return [], 1, detail


def _get_resource(get_call, resource_id, compartment_name, event, **kwargs):
    try:
        return _to_dict(common.call_with_retry(get_call, **kwargs).data), None
    except Exception as exc:
        detail = _exception_detail(exc)
        _log(
            "WARN",
            compartment_name,
            f"{event}_failed",
            resource_id=resource_id or "-",
            detail=detail,
            **_exception_fields(exc),
        )
        return None, detail


def _add_context(raw, resource_type, compartment_id, compartment_name):
    raw["resource_type"] = resource_type
    raw["resource_type_label"] = RESOURCE_TYPE_LABELS.get(resource_type, resource_type)
    raw["region"] = GLOBAL_REGION
    if "compartment_id" not in raw:
        raw["compartment_id"] = compartment_id
    else:
        raw["collection_compartment_id"] = compartment_id
    raw["compartment_name"] = compartment_name
    return raw


def _new_resource(raw, resource_type, compartment_id, compartment_name, enriched=None):
    return {
        "identity_raw": _add_context(raw, resource_type, compartment_id, compartment_name),
        "identity_enriched": enriched or {},
        "_errors": [],
    }

def _load_compartments(identity_client, tenancy_id, tenancy_name):
    rows, error_count, error_detail = _list_resources(
        identity_client.list_compartments,
        tenancy_name,
        "compartments_listed",
        compartment_id=tenancy_id,
        compartment_id_in_subtree=True,
        access_level="ANY",
    )

    root_raw, root_error = _get_resource(
        identity_client.get_compartment,
        tenancy_id,
        tenancy_name,
        "root_compartment_detail_fetch",
        compartment_id=tenancy_id,
    )
    if root_error:
        error_count += 1
        root_raw = {
            "id": tenancy_id,
            "name": tenancy_name,
            "lifecycle_state": "UNKNOWN",
        }

    root_raw = root_raw or {"id": tenancy_id, "name": tenancy_name}
    root_raw["parent_compartment_id"] = None
    compartments_by_id = {tenancy_id: root_raw}
    for row in rows:
        if row.get("id"):
            compartments_by_id[row["id"]] = row

    resources = []
    sorted_compartments = sorted(
        compartments_by_id.items(),
        key=lambda item: _sort_key(item[1]),
    )
    for compartment_id, compartment in sorted_compartments:
        comp_name = compartment.get("name") or compartment.get("display_name") or tenancy_name
        comp_raw = dict(compartment)
        detail_raw, detail_error = _get_resource(
            identity_client.get_compartment,
            compartment_id,
            comp_name,
            "compartment_detail_fetch",
            compartment_id=compartment_id,
        )
        resource = _new_resource(
            detail_raw or comp_raw,
            "compartment",
            compartment_id,
            comp_name,
        )
        if detail_error:
            error_count += 1
            resource["_errors"].append(f"compartment detail fetch failed: {detail_error}")
        resources.append(resource)

    if error_detail:
        _log(
            "WARN",
            tenancy_name,
            "compartment_listing_partial",
            detail=error_detail,
        )
    return compartments_by_id, resources, error_count


def _collect_users(identity_client, tenancy_id, tenancy_name):
    users, error_count, _ = _list_resources(
        identity_client.list_users,
        tenancy_name,
        "users_listed",
        compartment_id=tenancy_id,
        sort_by="NAME",
        sort_order="ASC",
    )
    resources = []
    for user in users:
        user_id = user.get("id")
        detail_raw, detail_error = _get_resource(
            identity_client.get_user,
            user_id,
            tenancy_name,
            "user_detail_fetch",
            user_id=user_id,
        )
        resource = _new_resource(
            detail_raw or user,
            "user",
            tenancy_id,
            tenancy_name,
            enriched={"group_memberships": []},
        )
        if detail_error:
            error_count += 1
            resource["_errors"].append(f"user detail fetch failed: {detail_error}")

        memberships, membership_errors, membership_error_detail = _list_resources(
            identity_client.list_user_group_memberships,
            tenancy_name,
            "user_group_memberships_listed",
            compartment_id=tenancy_id,
            user_id=user_id,
        )
        error_count += membership_errors
        resource["identity_enriched"]["group_memberships"] = memberships
        if membership_error_detail:
            resource["_errors"].append(
                f"user group membership listing failed: {membership_error_detail}"
            )

        resources.append(resource)
    return users, resources, error_count


def _collect_groups(identity_client, tenancy_id, tenancy_name):
    groups, error_count, _ = _list_resources(
        identity_client.list_groups,
        tenancy_name,
        "groups_listed",
        compartment_id=tenancy_id,
        sort_by="NAME",
        sort_order="ASC",
    )
    resources = []
    for group in groups:
        group_id = group.get("id")
        detail_raw, detail_error = _get_resource(
            identity_client.get_group,
            group_id,
            tenancy_name,
            "group_detail_fetch",
            group_id=group_id,
        )
        resource = _new_resource(detail_raw or group, "group", tenancy_id, tenancy_name)
        if detail_error:
            error_count += 1
            resource["_errors"].append(f"group detail fetch failed: {detail_error}")
        resources.append(resource)
    return groups, resources, error_count


def _collect_dynamic_groups(identity_client, tenancy_id, tenancy_name):
    dynamic_groups, error_count, _ = _list_resources(
        identity_client.list_dynamic_groups,
        tenancy_name,
        "dynamic_groups_listed",
        compartment_id=tenancy_id,
        sort_by="NAME",
        sort_order="ASC",
    )
    resources = []
    for dynamic_group in dynamic_groups:
        dynamic_group_id = dynamic_group.get("id")
        detail_raw, detail_error = _get_resource(
            identity_client.get_dynamic_group,
            dynamic_group_id,
            tenancy_name,
            "dynamic_group_detail_fetch",
            dynamic_group_id=dynamic_group_id,
        )
        resource = _new_resource(
            detail_raw or dynamic_group,
            "dynamic_group",
            tenancy_id,
            tenancy_name,
        )
        if detail_error:
            error_count += 1
            resource["_errors"].append(
                f"dynamic group detail fetch failed: {detail_error}"
            )
        resources.append(resource)
    return resources, error_count


def _collect_policies(identity_client, compartments_by_id, tenancy_id, tenancy_name):
    resources = []
    error_count = 0
    sorted_compartments = sorted(
        compartments_by_id.items(),
        key=lambda item: _sort_key(item[1]),
    )
    for compartment_id, compartment in sorted_compartments:
        comp_name = compartment.get("name") or compartment.get("display_name") or tenancy_name
        policies, list_errors, _ = _list_resources(
            identity_client.list_policies,
            comp_name,
            "policies_listed",
            compartment_id=compartment_id,
            sort_by="NAME",
            sort_order="ASC",
        )
        error_count += list_errors
        for policy in policies:
            policy_id = policy.get("id")
            detail_raw, detail_error = _get_resource(
                identity_client.get_policy,
                policy_id,
                comp_name,
                "policy_detail_fetch",
                policy_id=policy_id,
            )
            resource = _new_resource(
                detail_raw or policy,
                "policy",
                compartment_id,
                comp_name,
            )
            if detail_error:
                error_count += 1
                resource["_errors"].append(f"policy detail fetch failed: {detail_error}")
            resources.append(resource)
    return resources, error_count


def _collect_tag_namespaces(identity_client, compartments_by_id, tenancy_id, tenancy_name):
    namespaces, error_count, _ = _list_resources(
        identity_client.list_tag_namespaces,
        tenancy_name,
        "tag_namespaces_listed",
        compartment_id=tenancy_id,
        include_subcompartments=True,
    )
    resources = []
    for namespace in namespaces:
        namespace_id = namespace.get("id")
        compartment_id = namespace.get("compartment_id") or tenancy_id
        compartment = compartments_by_id.get(compartment_id) or {}
        comp_name = compartment.get("name") or compartment.get("display_name") or tenancy_name
        detail_raw, detail_error = _get_resource(
            identity_client.get_tag_namespace,
            namespace_id,
            comp_name,
            "tag_namespace_detail_fetch",
            tag_namespace_id=namespace_id,
        )
        namespace_raw = detail_raw or namespace
        resource = _new_resource(
            namespace_raw,
            "tag_namespace",
            compartment_id,
            comp_name,
            enriched={"tags": []},
        )
        if detail_error:
            error_count += 1
            resource["_errors"].append(
                f"tag namespace detail fetch failed: {detail_error}"
            )

        tags, tag_errors, tag_error_detail = _list_resources(
            identity_client.list_tags,
            comp_name,
            "tags_listed",
            tag_namespace_id=namespace_id,
        )
        error_count += tag_errors
        tag_details = []
        for tag in tags:
            tag_name = tag.get("name")
            tag_detail_raw, tag_detail_error = _get_resource(
                identity_client.get_tag,
                tag_name,
                comp_name,
                "tag_detail_fetch",
                tag_namespace_id=namespace_id,
                tag_name=tag_name,
            )
            if tag_detail_error:
                error_count += 1
                resource["_errors"].append(
                    f"tag detail fetch failed ({tag_name}): {tag_detail_error}"
                )
            tag_details.append(tag_detail_raw or tag)
        resource["identity_enriched"]["tags"] = _sort_list(tag_details)
        if tag_error_detail:
            resource["_errors"].append(f"tag listing failed: {tag_error_detail}")
        resources.append(resource)
    return resources, error_count


def _collect_network_sources(identity_client, tenancy_id, tenancy_name):
    network_sources, error_count, _ = _list_resources(
        identity_client.list_network_sources,
        tenancy_name,
        "network_sources_listed",
        compartment_id=tenancy_id,
        sort_by="NAME",
        sort_order="ASC",
    )
    resources = []
    for network_source in network_sources:
        network_source_id = network_source.get("id")
        detail_raw, detail_error = _get_resource(
            identity_client.get_network_source,
            network_source_id,
            tenancy_name,
            "network_source_detail_fetch",
            network_source_id=network_source_id,
        )
        resource = _new_resource(
            detail_raw or network_source,
            "network_source",
            tenancy_id,
            tenancy_name,
        )
        if detail_error:
            error_count += 1
            resource["_errors"].append(
                f"network source detail fetch failed: {detail_error}"
            )
        resources.append(resource)
    return resources, error_count


def _enrich_membership_names(resources, users, groups):
    user_names = {row.get("id"): row.get("name") for row in users if row.get("id")}
    group_names = {row.get("id"): row.get("name") for row in groups if row.get("id")}
    for resource in resources:
        memberships = (resource.get("identity_enriched") or {}).get("group_memberships")
        if not isinstance(memberships, list):
            continue
        for membership in memberships:
            if not isinstance(membership, dict):
                continue
            membership["user_name"] = user_names.get(membership.get("user_id"))
            membership["group_name"] = group_names.get(membership.get("group_id"))


def collect(client):
    _log("INFO", "-", "collection_start", message="Collecting IAM / Identity resources")
    tenancy_id = client.tenancy_id
    tenancy_name = getattr(client, "tenancy_name", None) or tenancy_id
    config = client.config.copy()
    identity_client = common.create_client(oci.identity.IdentityClient, config)

    all_resources = []
    error_count = 0

    compartments_by_id, compartment_resources, ec = _load_compartments(
        identity_client,
        tenancy_id,
        tenancy_name,
    )
    error_count += ec
    all_resources.extend(compartment_resources)

    users, user_resources, ec = _collect_users(identity_client, tenancy_id, tenancy_name)
    error_count += ec
    all_resources.extend(user_resources)

    groups, group_resources, ec = _collect_groups(identity_client, tenancy_id, tenancy_name)
    error_count += ec
    all_resources.extend(group_resources)
    _enrich_membership_names(user_resources, users, groups)

    dynamic_group_resources, ec = _collect_dynamic_groups(
        identity_client,
        tenancy_id,
        tenancy_name,
    )
    error_count += ec
    all_resources.extend(dynamic_group_resources)

    policy_resources, ec = _collect_policies(
        identity_client,
        compartments_by_id,
        tenancy_id,
        tenancy_name,
    )
    error_count += ec
    all_resources.extend(policy_resources)

    tag_namespace_resources, ec = _collect_tag_namespaces(
        identity_client,
        compartments_by_id,
        tenancy_id,
        tenancy_name,
    )
    error_count += ec
    all_resources.extend(tag_namespace_resources)

    network_source_resources, ec = _collect_network_sources(
        identity_client,
        tenancy_id,
        tenancy_name,
    )
    error_count += ec
    all_resources.extend(network_source_resources)

    all_resources = sorted(all_resources, key=_resource_sort_key)
    _log(
        "INFO",
        "-",
        "collection_end",
        collected=len(all_resources),
        errors=error_count,
    )

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"identity_{client.profile_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_resources, f, indent=4, default=str, ensure_ascii=False)
    return output_path

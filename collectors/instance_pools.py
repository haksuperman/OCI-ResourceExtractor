import json
import os

import oci

import common
from log_utils import log_event


SERVICE_NAME = "instance_pools"


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        SERVICE_NAME,
        event,
        region=region,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def _to_dict(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    try:
        return oci.util.to_dict(value)
    except Exception:
        return {"value": str(value)}


def _with_context(raw, region, compartment_name, compartment_id=None):
    if not isinstance(raw, dict):
        raw = {}
    raw["region_name"] = region
    raw["compartment_name"] = compartment_name
    if compartment_id and not raw.get("compartment_id"):
        raw["compartment_id"] = compartment_id
    return raw


def _join_unique(values):
    seen = set()
    result = []
    for value in values:
        if value is None or value == "":
            continue
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return ", ".join(result)


def _display_name(resource):
    if not isinstance(resource, dict):
        return None
    return resource.get("display_name") or resource.get("name") or resource.get("id")


def _resource_id_from_autoscaling_configuration(configuration):
    if not isinstance(configuration, dict):
        return None
    resource = configuration.get("resource")
    if isinstance(resource, dict):
        return resource.get("id")
    return configuration.get("resource_id")


def _load_balancer_type(load_balancer_id):
    if not load_balancer_id:
        return None
    if str(load_balancer_id).startswith("ocid1.networkloadbalancer."):
        return "network_load_balancer"
    if str(load_balancer_id).startswith("ocid1.loadbalancer."):
        return "load_balancer"
    return None


def _get_cached_instance_configuration(
    compute_management_client,
    configuration_id,
    cache,
    region,
    compartment_name,
    compartment_id,
    pool_id,
):
    if not configuration_id:
        return None, []
    if configuration_id in cache:
        return cache[configuration_id], []

    errors = []
    try:
        configuration = common.call_with_retry(
            compute_management_client.get_instance_configuration,
            instance_configuration_id=configuration_id,
        ).data
        raw = _with_context(_to_dict(configuration), region, compartment_name, compartment_id)
        cache[configuration_id] = raw
    except Exception as e:
        raw = _with_context({"id": configuration_id}, region, compartment_name, compartment_id)
        cache[configuration_id] = raw
        errors.append(f"instance configuration fetch failed ({configuration_id}): {e}")
        _log(
            "WARN",
            region,
            compartment_name,
            "instance_configuration_fetch_failed",
            resource_id=pool_id,
            detail=f"instance_configuration_id={configuration_id} err={e}",
        )
    return cache[configuration_id], errors


def _collect_pool_instances(
    compute_management_client,
    compartment_id,
    pool_id,
    region,
    compartment_name,
):
    try:
        instances = common.list_call_get_all_results(
            compute_management_client.list_instance_pool_instances,
            compartment_id=compartment_id,
            instance_pool_id=pool_id,
        ).data
        instance_rows = [
            _with_context(_to_dict(instance), region, compartment_name, compartment_id)
            for instance in instances
        ]
        _log(
            "INFO",
            region,
            compartment_name,
            "instance_pool_instances_listed",
            resource_id=pool_id,
            count=len(instance_rows),
        )
        return instance_rows, []
    except Exception as e:
        _log(
            "WARN",
            region,
            compartment_name,
            "instance_pool_instances_listing_failed",
            resource_id=pool_id,
            detail=str(e),
        )
        return [], [f"instance pool instances listing failed ({pool_id}): {e}"]


def _get_autoscaling_policy_detail(
    autoscaling_client,
    configuration_id,
    policy_summary,
    region,
    compartment_name,
):
    policy_raw = _to_dict(policy_summary) or {}
    policy_id = policy_raw.get("id")
    errors = []

    if not policy_id:
        return policy_raw, errors

    try:
        policy = common.call_with_retry(
            autoscaling_client.get_auto_scaling_policy,
            auto_scaling_configuration_id=configuration_id,
            auto_scaling_policy_id=policy_id,
        ).data
        policy_raw = _to_dict(policy) or policy_raw
    except Exception as e:
        errors.append(f"autoscaling policy detail fetch failed ({policy_id}): {e}")
        _log(
            "WARN",
            region,
            compartment_name,
            "autoscaling_policy_detail_fetch_failed",
            resource_id=configuration_id,
            detail=f"policy_id={policy_id} err={e}",
        )

    return policy_raw, errors


def _collect_autoscaling_by_resource(
    autoscaling_client,
    compartment_id,
    region,
    compartment_name,
):
    by_resource_id = {}
    error_count = 0
    compartment_errors = []

    if autoscaling_client is None:
        message = "autoscaling client unavailable"
        _log(
            "WARN",
            region,
            compartment_name,
            "autoscaling_client_unavailable",
            detail=message,
        )
        return by_resource_id, 1, [message]

    try:
        configurations = common.list_call_get_all_results(
            autoscaling_client.list_auto_scaling_configurations,
            compartment_id=compartment_id,
        ).data
        _log(
            "INFO",
            region,
            compartment_name,
            "autoscaling_configurations_listed",
            count=len(configurations),
        )
    except Exception as e:
        error_count += 1
        message = f"autoscaling configurations listing failed: {e}"
        compartment_errors.append(message)
        _log(
            "WARN",
            region,
            compartment_name,
            "autoscaling_configurations_listing_failed",
            detail=str(e),
        )
        return by_resource_id, error_count, compartment_errors

    for configuration in configurations:
        configuration_summary = _to_dict(configuration) or {}
        configuration_id = configuration_summary.get("id")
        if not configuration_id:
            continue

        configuration_errors = []
        try:
            configuration_detail = common.call_with_retry(
                autoscaling_client.get_auto_scaling_configuration,
                auto_scaling_configuration_id=configuration_id,
            ).data
            configuration_raw = _to_dict(configuration_detail) or configuration_summary
        except Exception as e:
            error_count += 1
            configuration_raw = configuration_summary
            configuration_errors.append(
                f"autoscaling configuration detail fetch failed ({configuration_id}): {e}"
            )
            _log(
                "WARN",
                region,
                compartment_name,
                "autoscaling_configuration_detail_fetch_failed",
                resource_id=configuration_id,
                detail=str(e),
            )

        configuration_raw = _with_context(
            configuration_raw,
            region,
            compartment_name,
            compartment_id,
        )

        policies = []
        try:
            policy_summaries = common.list_call_get_all_results(
                autoscaling_client.list_auto_scaling_policies,
                auto_scaling_configuration_id=configuration_id,
            ).data
            for policy_summary in policy_summaries:
                policy_raw, policy_errors = _get_autoscaling_policy_detail(
                    autoscaling_client,
                    configuration_id,
                    policy_summary,
                    region,
                    compartment_name,
                )
                if policy_errors:
                    error_count += len(policy_errors)
                    configuration_errors.extend(policy_errors)
                policies.append(
                    {
                        "auto_scaling_policy_raw": policy_raw,
                        "_errors": policy_errors,
                    }
                )
        except Exception as e:
            error_count += 1
            configuration_errors.append(
                f"autoscaling policies listing failed ({configuration_id}): {e}"
            )
            _log(
                "WARN",
                region,
                compartment_name,
                "autoscaling_policies_listing_failed",
                resource_id=configuration_id,
                detail=str(e),
            )

        entry = {
            "auto_scaling_configuration_raw": configuration_raw,
            "policies": policies,
            "_errors": configuration_errors,
        }
        resource_id = _resource_id_from_autoscaling_configuration(configuration_raw)
        if resource_id:
            by_resource_id.setdefault(resource_id, []).append(entry)

    return by_resource_id, error_count, compartment_errors


def _summarize_autoscaling(configurations):
    configuration_raws = [
        entry.get("auto_scaling_configuration_raw")
        for entry in configurations
        if isinstance(entry, dict)
    ]
    policy_rows = []
    for entry in configurations:
        if isinstance(entry, dict):
            policy_rows.extend(entry.get("policies") or [])
    policy_raws = [
        entry.get("auto_scaling_policy_raw")
        for entry in policy_rows
        if isinstance(entry, dict)
    ]

    return {
        "configurations": configurations,
        "configuration_count": len(configurations),
        "configuration_names": _join_unique(_display_name(raw) for raw in configuration_raws),
        "enabled_configuration_count": sum(
            1 for raw in configuration_raws if isinstance(raw, dict) and raw.get("is_enabled")
        ),
        "is_enabled": _join_unique(
            raw.get("is_enabled") for raw in configuration_raws if isinstance(raw, dict)
        ),
        "min_resource_count": _join_unique(
            raw.get("min_resource_count") for raw in configuration_raws if isinstance(raw, dict)
        ),
        "max_resource_count": _join_unique(
            raw.get("max_resource_count") for raw in configuration_raws if isinstance(raw, dict)
        ),
        "cool_down_in_seconds": _join_unique(
            raw.get("cool_down_in_seconds")
            for raw in configuration_raws
            if isinstance(raw, dict)
        ),
        "policy_count": len(policy_rows),
        "policy_names": _join_unique(_display_name(raw) for raw in policy_raws),
    }


def _try_get_load_balancer(lb_client, load_balancer_id, cache, region):
    if lb_client is None:
        raise RuntimeError("load balancer client unavailable")
    if load_balancer_id not in cache:
        raw = _to_dict(
            common.call_with_retry(
                lb_client.get_load_balancer,
                load_balancer_id=load_balancer_id,
            ).data
        )
        if isinstance(raw, dict):
            raw["region_name"] = region
        cache[load_balancer_id] = raw
    return cache[load_balancer_id]


def _try_get_network_load_balancer(nlb_client, load_balancer_id, cache, region):
    if nlb_client is None:
        raise RuntimeError("network load balancer client unavailable")
    if load_balancer_id not in cache:
        raw = _to_dict(
            common.call_with_retry(
                nlb_client.get_network_load_balancer,
                network_load_balancer_id=load_balancer_id,
            ).data
        )
        if isinstance(raw, dict):
            raw["region_name"] = region
        cache[load_balancer_id] = raw
    return cache[load_balancer_id]


def _resolve_load_balancer(
    load_balancer_id,
    lb_client,
    nlb_client,
    lb_cache,
    nlb_cache,
    region,
    compartment_name,
    pool_id,
):
    if not load_balancer_id:
        return None, None, []

    errors = []
    lb_type = _load_balancer_type(load_balancer_id)

    if lb_type == "load_balancer":
        try:
            return (
                _try_get_load_balancer(lb_client, load_balancer_id, lb_cache, region),
                None,
                errors,
            )
        except Exception as e:
            errors.append(f"load balancer fetch failed ({load_balancer_id}): {e}")
            _log(
                "WARN",
                region,
                compartment_name,
                "load_balancer_fetch_failed",
                resource_id=pool_id,
                detail=f"load_balancer_id={load_balancer_id} err={e}",
            )
            return {"id": load_balancer_id}, None, errors

    if lb_type == "network_load_balancer":
        try:
            return (
                None,
                _try_get_network_load_balancer(nlb_client, load_balancer_id, nlb_cache, region),
                errors,
            )
        except Exception as e:
            errors.append(f"network load balancer fetch failed ({load_balancer_id}): {e}")
            _log(
                "WARN",
                region,
                compartment_name,
                "network_load_balancer_fetch_failed",
                resource_id=pool_id,
                detail=f"load_balancer_id={load_balancer_id} err={e}",
            )
            return None, {"id": load_balancer_id}, errors

    lb_error = None
    try:
        return (
            _try_get_load_balancer(lb_client, load_balancer_id, lb_cache, region),
            None,
            errors,
        )
    except Exception as e:
        lb_error = e

    try:
        return (
            None,
            _try_get_network_load_balancer(nlb_client, load_balancer_id, nlb_cache, region),
            errors,
        )
    except Exception as nlb_error:
        message = (
            f"load balancer type resolution failed ({load_balancer_id}): "
            f"lb_error={lb_error}; nlb_error={nlb_error}"
        )
        errors.append(message)
        _log(
            "WARN",
            region,
            compartment_name,
            "load_balancer_type_resolution_failed",
            resource_id=pool_id,
            detail=message,
        )
        return {"id": load_balancer_id}, None, errors


def _load_balancer_attachment_id(reference):
    if not isinstance(reference, dict):
        return None
    return (
        reference.get("id")
        or reference.get("load_balancer_attachment_id")
        or reference.get("instance_pool_load_balancer_attachment_id")
    )


def _collect_load_balancer_attachments(
    compute_management_client,
    lb_client,
    nlb_client,
    pool_raw,
    region,
    compartment_name,
    lb_cache,
    nlb_cache,
):
    pool_id = pool_raw.get("id")
    attachment_refs = pool_raw.get("load_balancers") or []
    if not isinstance(attachment_refs, list):
        attachment_refs = []

    attachments = []
    errors = []

    for attachment_ref in attachment_refs:
        attachment_ref_raw = _to_dict(attachment_ref) or {}
        attachment_id = _load_balancer_attachment_id(attachment_ref_raw)
        attachment_raw = dict(attachment_ref_raw)

        if attachment_id:
            try:
                attachment_detail = common.call_with_retry(
                    compute_management_client.get_instance_pool_load_balancer_attachment,
                    instance_pool_id=pool_id,
                    instance_pool_load_balancer_attachment_id=attachment_id,
                ).data
                attachment_raw = _to_dict(attachment_detail) or attachment_raw
            except Exception as e:
                message = (
                    f"instance pool load balancer attachment fetch failed "
                    f"({attachment_id}): {e}"
                )
                errors.append(message)
                _log(
                    "WARN",
                    region,
                    compartment_name,
                    "load_balancer_attachment_fetch_failed",
                    resource_id=pool_id,
                    detail=f"attachment_id={attachment_id} err={e}",
                )
        else:
            message = "load balancer attachment id missing; using pool reference only"
            errors.append(message)
            _log(
                "WARN",
                region,
                compartment_name,
                "load_balancer_attachment_id_missing",
                resource_id=pool_id,
                detail=message,
            )

        attachment_raw["region_name"] = region
        attachment_raw["compartment_name"] = compartment_name
        load_balancer_id = attachment_raw.get("load_balancer_id") or attachment_ref_raw.get(
            "load_balancer_id"
        )
        lb_raw, nlb_raw, resolver_errors = _resolve_load_balancer(
            load_balancer_id,
            lb_client,
            nlb_client,
            lb_cache,
            nlb_cache,
            region,
            compartment_name,
            pool_id,
        )
        errors.extend(resolver_errors)
        attachments.append(
            {
                "attachment_raw": attachment_raw,
                "load_balancer_raw": lb_raw,
                "network_load_balancer_raw": nlb_raw,
                "_errors": resolver_errors,
            }
        )

    return attachments, errors


def _summarize_load_balancers(attachments):
    names = []
    ids = []
    types = []
    backend_sets = []
    ports = []
    vnic_selections = []
    lifecycle_states = []

    for entry in attachments:
        if not isinstance(entry, dict):
            continue
        attachment = entry.get("attachment_raw") or {}
        lb_raw = entry.get("load_balancer_raw")
        nlb_raw = entry.get("network_load_balancer_raw")

        if isinstance(lb_raw, dict):
            names.append(_display_name(lb_raw))
            types.append("load_balancer")
        if isinstance(nlb_raw, dict):
            names.append(_display_name(nlb_raw))
            types.append("network_load_balancer")

        ids.append(attachment.get("load_balancer_id"))
        backend_sets.append(attachment.get("backend_set_name"))
        ports.append(attachment.get("port"))
        vnic_selections.append(attachment.get("vnic_selection"))
        lifecycle_states.append(attachment.get("lifecycle_state"))

    return {
        "attachments": attachments,
        "attachment_count": len(attachments),
        "load_balancer_names": _join_unique(names),
        "load_balancer_ids": _join_unique(ids),
        "load_balancer_types": _join_unique(types),
        "backend_set_names": _join_unique(backend_sets),
        "ports": _join_unique(ports),
        "vnic_selections": _join_unique(vnic_selections),
        "lifecycle_states": _join_unique(lifecycle_states),
    }


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting Instance Pools")
    all_pools = []
    total_count = 0
    error_count = 0

    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config["region"] = region

        compute_management_client = None
        autoscaling_client = None
        lb_client = None
        nlb_client = None

        try:
            compute_management_client = common.create_client(
                oci.core.ComputeManagementClient,
                config,
            )
        except Exception as e:
            error_count += 1
            _log(
                "ERROR",
                region,
                "-",
                "compute_management_client_init_failed",
                detail=str(e),
            )

        try:
            autoscaling_client = common.create_client(oci.autoscaling.AutoScalingClient, config)
        except Exception as e:
            error_count += 1
            _log(
                "WARN",
                region,
                "-",
                "autoscaling_client_init_failed",
                detail=str(e),
            )

        try:
            lb_client = common.create_client(oci.load_balancer.LoadBalancerClient, config)
        except Exception as e:
            error_count += 1
            _log(
                "WARN",
                region,
                "-",
                "load_balancer_client_init_failed",
                detail=str(e),
            )

        try:
            nlb_client = common.create_client(
                oci.network_load_balancer.NetworkLoadBalancerClient,
                config,
            )
        except Exception as e:
            error_count += 1
            _log(
                "WARN",
                region,
                "-",
                "network_load_balancer_client_init_failed",
                detail=str(e),
            )

        if compute_management_client is None:
            continue

        instance_configuration_cache = {}
        lb_cache = {}
        nlb_cache = {}

        for comp in client.compartments:
            comp_name = comp.name

            try:
                pools = common.list_call_get_all_results(
                    compute_management_client.list_instance_pools,
                    compartment_id=comp.id,
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "instance_pools_listed",
                    count=len(pools),
                )
            except Exception as e:
                error_count += 1
                _log(
                    "ERROR",
                    region,
                    comp_name,
                    "instance_pools_listing_failed",
                    detail=str(e),
                )
                continue

            if not pools:
                continue

            autoscaling_by_resource_id, autoscaling_error_count, autoscaling_errors = (
                _collect_autoscaling_by_resource(
                    autoscaling_client,
                    comp.id,
                    region,
                    comp_name,
                )
            )
            error_count += autoscaling_error_count

            for pool in pools:
                total_count += 1
                pool_list_raw = _with_context(_to_dict(pool), region, comp_name, comp.id)
                pool_id = pool_list_raw.get("id")
                resource_errors = list(autoscaling_errors)

                try:
                    pool_detail = common.call_with_retry(
                        compute_management_client.get_instance_pool,
                        instance_pool_id=pool_id,
                    ).data
                    pool_raw = _with_context(_to_dict(pool_detail), region, comp_name, comp.id)
                except Exception as e:
                    error_count += 1
                    pool_raw = pool_list_raw
                    resource_errors.append(f"instance pool detail fetch failed ({pool_id}): {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "instance_pool_detail_fetch_failed",
                        resource_id=pool_id,
                        detail=str(e),
                    )

                pool_instances, pool_instance_errors = _collect_pool_instances(
                    compute_management_client,
                    comp.id,
                    pool_id,
                    region,
                    comp_name,
                )
                if pool_instance_errors:
                    error_count += len(pool_instance_errors)
                    resource_errors.extend(pool_instance_errors)

                configuration_id = pool_raw.get("instance_configuration_id")
                instance_configuration_raw, configuration_errors = (
                    _get_cached_instance_configuration(
                        compute_management_client,
                        configuration_id,
                        instance_configuration_cache,
                        region,
                        comp_name,
                        comp.id,
                        pool_id,
                    )
                )
                if configuration_errors:
                    error_count += len(configuration_errors)
                    resource_errors.extend(configuration_errors)

                autoscaling_configurations = autoscaling_by_resource_id.get(pool_id, [])
                for entry in autoscaling_configurations:
                    if isinstance(entry, dict):
                        resource_errors.extend(entry.get("_errors") or [])

                lb_attachments, lb_errors = _collect_load_balancer_attachments(
                    compute_management_client,
                    lb_client,
                    nlb_client,
                    pool_raw,
                    region,
                    comp_name,
                    lb_cache,
                    nlb_cache,
                )
                if lb_errors:
                    error_count += len(lb_errors)
                    resource_errors.extend(lb_errors)

                resource = {
                    "instance_pool_raw": pool_raw,
                    "instance_configuration_enriched": {
                        "instance_configuration": instance_configuration_raw,
                        "display_name": _display_name(instance_configuration_raw),
                        "id": (
                            instance_configuration_raw.get("id")
                            if isinstance(instance_configuration_raw, dict)
                            else configuration_id
                        ),
                    },
                    "pool_instances_enriched": {
                        "instances": pool_instances,
                        "instance_count": len(pool_instances),
                        "instance_names": _join_unique(
                            _display_name(instance) for instance in pool_instances
                        ),
                    },
                    "autoscaling_enriched": _summarize_autoscaling(
                        autoscaling_configurations
                    ),
                    "load_balancer_enriched": _summarize_load_balancers(lb_attachments),
                    "_errors": resource_errors,
                }
                all_pools.append(resource)

    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"instance_pools_{client.profile_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_pools, f, indent=4, default=str, ensure_ascii=False)
    return output_path

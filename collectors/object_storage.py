import json
import os

import oci
import common
from log_utils import log_event


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "object_storage",
        event,
        region=region,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting Object Storage Buckets")
    all_buckets = []
    total_count = 0
    error_count = 0

    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config["region"] = region
        os_client = common.create_client(oci.object_storage.ObjectStorageClient, config)

        namespace = None
        try:
            namespace = common.call_with_retry(
                os_client.get_namespace, compartment_id=client.tenancy_id
            ).data
            _log("INFO", region, "tenancy", "namespace_resolved", namespace=namespace)
        except Exception as e:
            error_count += 1
            _log("ERROR", region, "tenancy", "namespace_resolution_failed", detail=str(e))
            continue

        for comp in client.compartments:
            comp_name = comp.name
            try:
                buckets = common.list_call_get_all_results(
                    os_client.list_buckets,
                    namespace_name=namespace,
                    compartment_id=comp.id,
                    fields=["tags"],
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "buckets_listed",
                    count=len(buckets),
                )
            except Exception as e:
                error_count += 1
                _log(
                    "ERROR",
                    region,
                    comp_name,
                    "bucket_listing_failed",
                    detail=str(e),
                )
                continue

            for bucket in buckets:
                total_count += 1
                bucket_name = getattr(bucket, "name", None)
                resource = {
                    "object_storage_raw": oci.util.to_dict(bucket),
                    "object_storage_enriched": {
                        "retention_rules": [],
                    },
                    "_errors": [],
                }
                bucket_raw = resource["object_storage_raw"]
                bucket_raw["region_name"] = region
                bucket_raw["compartment_name"] = comp_name
                bucket_raw["namespace_name"] = namespace

                try:
                    detail = common.call_with_retry(
                        os_client.get_bucket,
                        namespace_name=namespace,
                        bucket_name=bucket_name,
                        fields=["approximateCount", "approximateSize", "autoTiering"],
                    ).data
                    bucket_raw = oci.util.to_dict(detail)
                    bucket_raw["region_name"] = region
                    bucket_raw["compartment_name"] = comp_name
                    bucket_raw["namespace_name"] = namespace
                    resource["object_storage_raw"] = bucket_raw
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(f"bucket detail fetch failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "bucket_detail_fetch_failed",
                        resource_id=bucket_name or "-",
                        detail=str(e),
                    )

                try:
                    retention_rules = common.list_call_get_all_results(
                        os_client.list_retention_rules,
                        namespace_name=namespace,
                        bucket_name=bucket_name,
                    ).data
                    resource["object_storage_enriched"]["retention_rules"] = [
                        oci.util.to_dict(rule) for rule in retention_rules
                    ]
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "bucket_retention_rules_listed",
                        resource_id=bucket_name or "-",
                        count=len(resource["object_storage_enriched"]["retention_rules"]),
                    )
                except Exception as e:
                    error_count += 1
                    resource["object_storage_enriched"]["retention_rules"] = []
                    resource["_errors"].append(f"retention rule listing failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "bucket_retention_rule_listing_failed",
                        resource_id=bucket_name or "-",
                        detail=str(e),
                    )

                all_buckets.append(resource)

    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)

    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"object_storage_{client.profile_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_buckets, f, indent=4, default=str, ensure_ascii=False)
    return output_path

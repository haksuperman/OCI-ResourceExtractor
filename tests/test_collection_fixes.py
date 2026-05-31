import ast
import inspect
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import oci

import common
from collectors import identity, object_storage, vcn


class FakeResponse:
    def __init__(self, data):
        self.data = data
        self.status = 200
        self.headers = {}
        self.request = None
        self.has_next_page = False
        self.next_page = None


class FakeModel:
    swagger_types = {}

    def __init__(self, **fields):
        self.swagger_types = {key: type(value).__name__ for key, value in fields.items()}
        for key, value in fields.items():
            setattr(self, key, value)


class FakeCompartment:
    id = "ocid1.compartment.oc1..unit"
    name = "unit-compartment"


class FakeInventoryClient:
    profile_name = "unit"
    tenancy_id = "ocid1.tenancy.oc1..unit"
    config = {}
    regions = ["ap-test-1"]
    compartments = [FakeCompartment()]


class FakeObjectStorageClient:
    def __init__(self):
        self.list_bucket_fields = []
        self.get_bucket_fields = []

    def get_namespace(self, **kwargs):
        return FakeResponse("unitns")

    def list_buckets(self, namespace_name, compartment_id, **kwargs):
        self.list_bucket_fields.append(kwargs.get("fields"))
        return FakeResponse(
            [
                FakeModel(
                    name="bucket-a",
                    id="ocid1.bucket.oc1..bucket-a",
                    compartment_id=compartment_id,
                )
            ]
        )

    def get_bucket(self, namespace_name, bucket_name, **kwargs):
        self.get_bucket_fields.append(kwargs.get("fields"))
        return FakeResponse(
            FakeModel(
                name=bucket_name,
                id="ocid1.bucket.oc1..bucket-a",
                namespace_name=namespace_name,
                lifecycle_state="ACTIVE",
                storage_tier="Standard",
                approximate_count=7,
                approximate_size=4096,
                auto_tiering="Disabled",
            )
        )

    def list_retention_rules(self, namespace_name, bucket_name, **kwargs):
        return FakeResponse([])


class FakeNetworkClient:
    def list_vcns(self, compartment_id, **kwargs):
        return FakeResponse(
            [
                FakeModel(
                    id="ocid1.vcn.oc1..vcn-a",
                    display_name="vcn-a",
                    compartment_id=compartment_id,
                    lifecycle_state="AVAILABLE",
                )
            ]
        )

    def list_subnets(self, compartment_id, **kwargs):
        return FakeResponse([])

    def list_internet_gateways(self, compartment_id, **kwargs):
        return FakeResponse([])

    def list_nat_gateways(self, compartment_id, **kwargs):
        return FakeResponse([])

    def list_service_gateways(self, compartment_id, **kwargs):
        return FakeResponse([])

    def list_route_tables(self, compartment_id, **kwargs):
        return FakeResponse([])

    def list_security_lists(self, compartment_id, **kwargs):
        return FakeResponse([])

    def list_local_peering_gateways(self, compartment_id, **kwargs):
        return FakeResponse([])

    def list_dhcp_options(self, compartment_id, **kwargs):
        return FakeResponse([])

    def list_network_security_groups(self, **kwargs):
        return FakeResponse([])


class FakeIdentityClient:
    def list_compartments(self, compartment_id, **kwargs):
        return FakeResponse(
            [
                FakeModel(
                    id="ocid1.compartment.oc1..security",
                    name="security",
                    description="security compartment",
                    lifecycle_state="ACTIVE",
                    compartment_id=compartment_id,
                )
            ]
        )

    def get_compartment(self, compartment_id, **kwargs):
        if compartment_id == "ocid1.tenancy.oc1..unit":
            return FakeResponse(
                FakeModel(
                    id=compartment_id,
                    name="unit-tenancy",
                    description="root",
                    lifecycle_state="ACTIVE",
                )
            )
        return FakeResponse(
            FakeModel(
                id=compartment_id,
                name="security",
                description="security compartment",
                lifecycle_state="ACTIVE",
                compartment_id="ocid1.tenancy.oc1..unit",
            )
        )

    def list_users(self, compartment_id, **kwargs):
        return FakeResponse(
            [
                FakeModel(
                    id="ocid1.user.oc1..alice",
                    name="alice",
                    lifecycle_state="ACTIVE",
                    email="alice@example.com",
                )
            ]
        )

    def get_user(self, user_id, **kwargs):
        return FakeResponse(
            FakeModel(
                id=user_id,
                name="alice",
                lifecycle_state="ACTIVE",
                email="alice@example.com",
                email_verified=True,
            )
        )

    def list_user_group_memberships(self, compartment_id, **kwargs):
        return FakeResponse(
            [
                FakeModel(
                    id="ocid1.usergroupmembership.oc1..alice-admins",
                    user_id=kwargs.get("user_id"),
                    group_id="ocid1.group.oc1..admins",
                    time_created="2026-01-01T00:00:00Z",
                )
            ]
        )

    def list_groups(self, compartment_id, **kwargs):
        return FakeResponse(
            [
                FakeModel(
                    id="ocid1.group.oc1..admins",
                    name="admins",
                    lifecycle_state="ACTIVE",
                )
            ]
        )

    def get_group(self, group_id, **kwargs):
        return FakeResponse(
            FakeModel(
                id=group_id,
                name="admins",
                lifecycle_state="ACTIVE",
                description="Administrators",
            )
        )

    def list_dynamic_groups(self, compartment_id, **kwargs):
        return FakeResponse(
            [
                FakeModel(
                    id="ocid1.dynamicgroup.oc1..instances",
                    name="instances",
                    lifecycle_state="ACTIVE",
                    matching_rule="ALL {instance.compartment.id = 'ocid1.compartment.oc1..security'}",
                )
            ]
        )

    def get_dynamic_group(self, dynamic_group_id, **kwargs):
        return FakeResponse(
            FakeModel(
                id=dynamic_group_id,
                name="instances",
                lifecycle_state="ACTIVE",
                matching_rule="ALL {instance.compartment.id = 'ocid1.compartment.oc1..security'}",
            )
        )

    def list_policies(self, compartment_id, **kwargs):
        if compartment_id != "ocid1.tenancy.oc1..unit":
            return FakeResponse([])
        return FakeResponse(
            [
                FakeModel(
                    id="ocid1.policy.oc1..admins",
                    name="admins-policy",
                    lifecycle_state="ACTIVE",
                    statements=["Allow group admins to manage all-resources in tenancy"],
                )
            ]
        )

    def get_policy(self, policy_id, **kwargs):
        return FakeResponse(
            FakeModel(
                id=policy_id,
                name="admins-policy",
                lifecycle_state="ACTIVE",
                statements=["Allow group admins to manage all-resources in tenancy"],
            )
        )

    def list_tag_namespaces(self, compartment_id, **kwargs):
        return FakeResponse(
            [
                FakeModel(
                    id="ocid1.tagnamespace.oc1..ops",
                    name="ops",
                    compartment_id="ocid1.compartment.oc1..security",
                    lifecycle_state="ACTIVE",
                )
            ]
        )

    def get_tag_namespace(self, tag_namespace_id, **kwargs):
        return FakeResponse(
            FakeModel(
                id=tag_namespace_id,
                name="ops",
                compartment_id="ocid1.compartment.oc1..security",
                lifecycle_state="ACTIVE",
                is_retired=False,
            )
        )

    def list_tags(self, tag_namespace_id, **kwargs):
        return FakeResponse(
            [
                FakeModel(
                    id="ocid1.tag.oc1..environment",
                    name="environment",
                    lifecycle_state="ACTIVE",
                    is_cost_tracking=True,
                )
            ]
        )

    def get_tag(self, tag_namespace_id, tag_name, **kwargs):
        return FakeResponse(
            FakeModel(
                id="ocid1.tag.oc1..environment",
                name=tag_name,
                lifecycle_state="ACTIVE",
                is_cost_tracking=True,
                description="Environment",
            )
        )

    def list_network_sources(self, compartment_id, **kwargs):
        return FakeResponse(
            [
                FakeModel(
                    id="ocid1.networksource.oc1..corp",
                    name="corp",
                    lifecycle_state="ACTIVE",
                    public_source_list=["203.0.113.0/24"],
                )
            ]
        )

    def get_network_source(self, network_source_id, **kwargs):
        return FakeResponse(
            FakeModel(
                id=network_source_id,
                name="corp",
                lifecycle_state="ACTIVE",
                public_source_list=["203.0.113.0/24"],
            )
        )


class CollectionFixesTest(unittest.TestCase):
    def test_collector_sdk_wrapped_calls_use_supported_keyword_arguments(self):
        class_map = {
            "oci.autoscaling.AutoScalingClient": oci.autoscaling.AutoScalingClient,
            "oci.compute_instance_agent.PluginClient": oci.compute_instance_agent.PluginClient,
            "oci.core.BlockstorageClient": oci.core.BlockstorageClient,
            "oci.core.ComputeClient": oci.core.ComputeClient,
            "oci.core.ComputeManagementClient": oci.core.ComputeManagementClient,
            "oci.core.VirtualNetworkClient": oci.core.VirtualNetworkClient,
            "oci.database.DatabaseClient": oci.database.DatabaseClient,
            "oci.dns.DnsClient": oci.dns.DnsClient,
            "oci.file_storage.FileStorageClient": oci.file_storage.FileStorageClient,
            "oci.identity.IdentityClient": oci.identity.IdentityClient,
            "oci.load_balancer.LoadBalancerClient": oci.load_balancer.LoadBalancerClient,
            "oci.mysql.DbBackupsClient": oci.mysql.DbBackupsClient,
            "oci.mysql.DbSystemClient": oci.mysql.DbSystemClient,
            "oci.network_load_balancer.NetworkLoadBalancerClient": (
                oci.network_load_balancer.NetworkLoadBalancerClient
            ),
            "oci.object_storage.ObjectStorageClient": oci.object_storage.ObjectStorageClient,
            "oci.waas.WaasClient": oci.waas.WaasClient,
            "oci.waf.WafClient": oci.waf.WafClient,
        }
        wrappers = {
            "common.call_with_retry",
            "common.list_call_get_all_results",
            "_list_all",
            "_list_data",
        }

        def dotted(node):
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Attribute):
                base = dotted(node.value)
                return f"{base}.{node.attr}" if base else node.attr
            return None

        def client_vars(tree):
            vars_by_name = {}
            for node in ast.walk(tree):
                value = getattr(node, "value", None)
                if isinstance(node, ast.Assign):
                    targets = node.targets
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                else:
                    continue
                if not isinstance(value, ast.Call):
                    continue
                if dotted(value.func) != "common.create_client" or not value.args:
                    continue
                client_cls = class_map.get(dotted(value.args[0]))
                if not client_cls:
                    continue
                for target in targets:
                    if isinstance(target, ast.Name):
                        vars_by_name[target.id] = client_cls
            return vars_by_name

        expected_cache = {}

        def accepted_kwargs(client_cls, method_name):
            key = (client_cls, method_name)
            if key in expected_cache:
                return expected_cache[key]
            method = getattr(client_cls, method_name)
            signature = inspect.signature(method)
            accepted = {
                name
                for name, param in signature.parameters.items()
                if name != "self"
                and param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)
            }
            source = inspect.getsource(method)
            matched = re.search(r"expected_kwargs\s*=\s*\[(.*?)\]", source, re.S)
            if matched:
                accepted.update(re.findall(r"[\"']([^\"']+)[\"']", matched.group(1)))
            expected_cache[key] = accepted
            return accepted

        failures = []
        for path in sorted(Path("collectors").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            vars_by_name = client_vars(tree)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if dotted(node.func) not in wrappers or not node.args:
                    continue
                first_arg = node.args[0]
                if not (
                    isinstance(first_arg, ast.Attribute)
                    and isinstance(first_arg.value, ast.Name)
                ):
                    continue
                client_cls = vars_by_name.get(first_arg.value.id)
                if not client_cls or not hasattr(client_cls, first_arg.attr):
                    continue
                accepted = accepted_kwargs(client_cls, first_arg.attr)
                bad_kwargs = [
                    keyword.arg
                    for keyword in node.keywords
                    if keyword.arg and keyword.arg not in accepted
                ]
                if bad_kwargs:
                    failures.append(
                        f"{path}:{node.lineno} {client_cls.__name__}.{first_arg.attr} "
                        f"unsupported kwargs={bad_kwargs}"
                    )

        self.assertEqual(failures, [])

    def test_list_pagination_falls_back_when_injected_retry_strategy_is_rejected(self):
        calls = []

        def list_func(**kwargs):
            calls.append(dict(kwargs))
            if "retry_strategy" in kwargs:
                raise TypeError("<lambda>() got an unexpected keyword argument 'retry_strategy'")
            return FakeResponse([FakeModel(id="resource-a")])

        response = common.list_call_get_all_results(
            list_func,
            compartment_id="ocid1.compartment.oc1..unit",
        )

        self.assertEqual(len(response.data), 1)
        self.assertIn("retry_strategy", calls[0])
        self.assertNotIn("retry_strategy", calls[-1])
        self.assertEqual(calls[-1]["compartment_id"], "ocid1.compartment.oc1..unit")

    def test_vcn_list_helper_uses_retry_strategy_fallback(self):
        def list_func(**kwargs):
            if "retry_strategy" in kwargs:
                raise TypeError("<lambda>() got an unexpected keyword argument 'retry_strategy'")
            return FakeResponse([FakeModel(id="child-a")])

        rows, error_count = vcn._list_and_convert(
            list_func,
            "ap-test-1",
            "unit-compartment",
            "ocid1.vcn.oc1..vcn-a",
            "subnets",
            [],
            compartment_id="ocid1.compartment.oc1..unit",
        )

        self.assertEqual(error_count, 0)
        self.assertEqual(rows, [{"id": "child-a"}])

    def test_object_storage_uses_valid_bucket_and_detail_fields(self):
        fake_os_client = FakeObjectStorageClient()

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                with mock.patch.object(
                    object_storage.common,
                    "create_client",
                    return_value=fake_os_client,
                ):
                    path = object_storage.collect(FakeInventoryClient())
                data = json.loads(Path(path).read_text(encoding="utf-8"))
            finally:
                os.chdir(old_cwd)

        self.assertEqual(fake_os_client.list_bucket_fields, [["tags"]])
        self.assertEqual(
            fake_os_client.get_bucket_fields,
            [["approximateCount", "approximateSize", "autoTiering"]],
        )
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["object_storage_raw"]["approximate_count"], 7)
        self.assertEqual(data[0]["object_storage_raw"]["namespace_name"], "unitns")

    def test_identity_collector_writes_requested_iam_resource_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                with mock.patch.object(
                    identity.common,
                    "create_client",
                    return_value=FakeIdentityClient(),
                ):
                    path = identity.collect(FakeInventoryClient())
                data = json.loads(Path(path).read_text(encoding="utf-8"))
            finally:
                os.chdir(old_cwd)

        resource_types = {row["identity_raw"]["resource_type"] for row in data}
        self.assertEqual(
            resource_types,
            {
                "user",
                "group",
                "dynamic_group",
                "policy",
                "compartment",
                "tag_namespace",
                "network_source",
            },
        )
        self.assertTrue(
            all(set(row.keys()) == {"identity_raw", "identity_enriched", "_errors"} for row in data)
        )
        user = next(row for row in data if row["identity_raw"]["resource_type"] == "user")
        membership = user["identity_enriched"]["group_memberships"][0]
        self.assertEqual(membership["user_name"], "alice")
        self.assertEqual(membership["group_name"], "admins")
        tag_namespace = next(
            row for row in data if row["identity_raw"]["resource_type"] == "tag_namespace"
        )
        self.assertEqual(tag_namespace["identity_enriched"]["tags"][0]["name"], "environment")

    def test_vcn_compartment_link_errors_are_not_copied_to_each_vcn(self):
        fake_links = {
            "errors": ["drgs listing failed: permission denied"],
            "error_count": 1,
            "drgs": [],
            "drg_map": {},
            "drg_attachments": [],
            "virtual_circuits": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                with mock.patch.object(
                    vcn.common,
                    "create_client",
                    return_value=FakeNetworkClient(),
                ):
                    with mock.patch.object(
                        vcn,
                        "_collect_compartment_network_links",
                        return_value=fake_links,
                    ):
                        path = vcn.collect(FakeInventoryClient())
                data = json.loads(Path(path).read_text(encoding="utf-8"))
            finally:
                os.chdir(old_cwd)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["_errors"], [])
        self.assertEqual(data[0]["networking_enriched"]["subnets"], [])


if __name__ == "__main__":
    unittest.main()

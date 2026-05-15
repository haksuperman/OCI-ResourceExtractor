import oci
import os
import configparser
import threading
import time
from log_utils import log_event


DEFAULT_RETRY_STRATEGY = oci.retry.DEFAULT_RETRY_STRATEGY
_API_MIN_INTERVAL_SEC = float(os.getenv("OCI_API_MIN_INTERVAL_MS", "0")) / 1000.0
_API_LOCK = threading.Lock()
_NEXT_API_TS = 0.0


def _csv_env_set(name):
    return {item.strip() for item in os.getenv(name, "").split(",") if item.strip()}


def _load_profile_scope_filters_from_env():
    profile = os.getenv("OCI_SCOPE_FILTER_PROFILE", "").strip()
    if not profile:
        return {}

    regions = _csv_env_set("OCI_SCOPE_FILTER_REGIONS")
    compartments = _csv_env_set("OCI_SCOPE_FILTER_COMPARTMENTS")
    if not regions and not compartments:
        return {}

    return {
        profile: {
            "regions": regions,
            "compartments": compartments,
        }
    }


_TEMP_PROFILE_SCOPE_FILTERS = _load_profile_scope_filters_from_env()


def _respect_min_interval():
    global _NEXT_API_TS
    if _API_MIN_INTERVAL_SEC <= 0:
        return
    with _API_LOCK:
        now = time.time()
        wait_sec = _NEXT_API_TS - now
        if wait_sec > 0:
            time.sleep(wait_sec)
            now = time.time()
        _NEXT_API_TS = now + _API_MIN_INTERVAL_SEC


def call_with_retry(call_func, *args, **kwargs):
    _respect_min_interval()
    retry_kwargs = dict(kwargs)
    retry_kwargs.setdefault("retry_strategy", DEFAULT_RETRY_STRATEGY)
    try:
        return call_func(*args, **retry_kwargs)
    except TypeError:
        return call_func(*args, **kwargs)


def list_call_get_all_results(list_func, *args, **kwargs):
    _respect_min_interval()
    retry_kwargs = dict(kwargs)
    retry_kwargs.setdefault("retry_strategy", DEFAULT_RETRY_STRATEGY)
    return oci.pagination.list_call_get_all_results(list_func, *args, **retry_kwargs)


def service_error_detail(error):
    status = getattr(error, "status", "-")
    code = getattr(error, "code", "-")
    message = getattr(error, "message", str(error))
    return f"status={status} code={code} message={message}"


def create_client(client_cls, *args, **kwargs):
    retry_kwargs = dict(kwargs)
    retry_kwargs.setdefault("retry_strategy", DEFAULT_RETRY_STRATEGY)
    try:
        return client_cls(*args, **retry_kwargs)
    except TypeError:
        return client_cls(*args, **kwargs)


def get_profiles():
    config_path = os.path.expanduser(oci.config.DEFAULT_LOCATION)
    if not os.path.exists(config_path):
        return []
    config = configparser.ConfigParser()
    config.read(config_path)
    return config.sections()

class OCIClient:
    def __init__(self, profile_name):
        self.profile_name = profile_name
        self.config = oci.config.from_file(profile_name=profile_name)
        self.tenancy_id = self.config['tenancy']
        self.identity_client = create_client(oci.identity.IdentityClient, self.config)
        self.tenancy_name = self._get_tenancy_name()

        print(f"[!] Target Tenancy: {self.tenancy_name} ({self.tenancy_id})")
        region_subscriptions = list_call_get_all_results(
            self.identity_client.list_region_subscriptions,
            self.tenancy_id,
        ).data
        self.regions = [r.region_name for r in region_subscriptions]
        self.compartments = self.get_all_compartments()
        self._apply_temp_scope_filter()

    def _get_tenancy_name(self):
        try:
            tenancy = call_with_retry(
                self.identity_client.get_tenancy,
                self.tenancy_id,
            ).data
            if tenancy and getattr(tenancy, "name", None):
                return tenancy.name
        except Exception as e:
            log_event(
                "WARN",
                "runner",
                "tenancy_name_lookup_failed",
                message="Failed to resolve tenancy name via get_tenancy",
                resource=self.tenancy_id,
                detail=str(e),
            )

        try:
            tenancy_compartment = call_with_retry(
                self.identity_client.get_compartment,
                self.tenancy_id,
            ).data
            if tenancy_compartment and getattr(tenancy_compartment, "name", None):
                return tenancy_compartment.name
        except Exception as e:
            log_event(
                "WARN",
                "runner",
                "tenancy_compartment_lookup_failed",
                message="Failed to resolve tenancy name via get_compartment",
                resource=self.tenancy_id,
                detail=str(e),
            )

        return self.tenancy_id

    def get_all_compartments(self):
        print("[*] Fetching all compartments...")
        compartments = list_call_get_all_results(
            self.identity_client.list_compartments,
            self.tenancy_id,
            compartment_id_in_subtree=True,
            access_level="ANY"
        ).data
        root = call_with_retry(
            self.identity_client.get_compartment,
            self.tenancy_id,
        ).data
        compartments.append(root)
        return [c for c in compartments if c.lifecycle_state == "ACTIVE"]

    def _apply_temp_scope_filter(self):
        scope_filter = _TEMP_PROFILE_SCOPE_FILTERS.get(self.profile_name)
        if not scope_filter:
            return

        original_regions = list(self.regions)
        original_compartments = list(self.compartments)

        allowed_regions = scope_filter.get("regions") or set()
        if allowed_regions:
            self.regions = [region for region in self.regions if region in allowed_regions]

        allowed_compartments = {
            name.lower() for name in (scope_filter.get("compartments") or set())
        }
        if allowed_compartments:
            self.compartments = [
                compartment
                for compartment in self.compartments
                if getattr(compartment, "name", "").lower() in allowed_compartments
            ]

        log_event(
            "WARN",
            "runner",
            "temporary_scope_filter_applied",
            message="Temporary development scope filter applied",
            profile=self.profile_name,
            regions=",".join(self.regions) if self.regions else "-",
            compartments=",".join(
                getattr(compartment, "name", "-") for compartment in self.compartments
            )
            if self.compartments
            else "-",
            original_region_count=len(original_regions),
            filtered_region_count=len(self.regions),
            original_compartment_count=len(original_compartments),
            filtered_compartment_count=len(self.compartments),
        )

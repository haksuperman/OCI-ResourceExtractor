import pandas as pd


def get_preferred_columns():
    parent_context = [
        "load_balancer_raw.compartment_name",
        "load_balancer_raw.region_name",
        "load_balancer_raw.display_name",
        "load_balancer_raw.id",
    ]
    return {
        "Load_Balancers": [
            "load_balancer_raw.display_name",
            "load_balancer_raw.id",
            "load_balancer_raw.lifecycle_state",
            "load_balancer_raw.shape_name",
            "load_balancer_raw.shape_details.minimum_bandwidth_in_mbps",
            "load_balancer_raw.shape_details.maximum_bandwidth_in_mbps",
            "load_balancer_raw.is_private",
            "load_balancer_raw.ip_addresses",
            "load_balancer_raw.subnet_ids",
            "load_balancer_raw.network_security_group_ids",
            "load_balancer_raw.listeners",
            "load_balancer_raw.backend_sets",
            "load_balancer_raw.hostnames",
            "load_balancer_raw.path_route_sets",
            "load_balancer_raw.certificates",
            "networking_enriched.subnet_details",
            "networking_enriched.nsg_details",
            "load_balancer_raw.region_name",
            "load_balancer_raw.compartment_name",
            "load_balancer_raw.time_created",
            "_errors",
        ],
        "LB_Listeners": parent_context
        + [
            "listener_raw.listener_name",
            "listener_raw.protocol",
            "listener_raw.port",
            "listener_raw.default_backend_set_name",
            "listener_raw.hostname_names",
            "listener_raw.path_route_set_name",
            "listener_raw.ssl_configuration",
            "listener_raw.connection_configuration",
            "listener_raw.rule_set_names",
        ],
        "LB_Backend_Sets": parent_context
        + [
            "backend_set_raw.backend_set_name",
            "backend_set_raw.policy",
            "backend_set_raw.health_checker.protocol",
            "backend_set_raw.health_checker.port",
            "backend_set_raw.health_checker.url_path",
            "backend_set_raw.session_persistence_configuration",
            "backend_set_raw.ssl_configuration",
            "backend_set_raw.backends",
        ],
        "LB_Backends": parent_context
        + [
            "backend_set_raw.backend_set_name",
            "backend_raw.name",
            "backend_raw.ip_address",
            "backend_raw.port",
            "backend_raw.weight",
            "backend_raw.drain",
            "backend_raw.offline",
            "backend_raw.backup",
        ],
        "LB_Hostnames": parent_context
        + [
            "hostname_raw.hostname_name",
            "hostname_raw.hostname",
        ],
        "LB_Path_Route_Sets": parent_context
        + [
            "path_route_set_raw.path_route_set_name",
            "path_route_set_raw.path_routes",
        ],
        "LB_Path_Route_Rules": parent_context
        + [
            "path_route_set_raw.path_route_set_name",
            "path_route_raw.path",
            "path_route_raw.path_match_type",
            "path_route_raw.backend_set_name",
        ],
        "LB_Certificates": parent_context
        + [
            "certificate_raw.certificate_name",
            "certificate_raw.public_certificate",
            "certificate_raw.ca_certificate",
            "certificate_raw.passphrase",
        ],
    }


def _safe_list(value):
    return value if isinstance(value, list) else []


def _parent_raw(row):
    return {
        "display_name": row.get("load_balancer_raw.display_name"),
        "id": row.get("load_balancer_raw.id"),
        "lifecycle_state": row.get("load_balancer_raw.lifecycle_state"),
        "region_name": row.get("load_balancer_raw.region_name"),
        "compartment_name": row.get("load_balancer_raw.compartment_name"),
        "shape_name": row.get("load_balancer_raw.shape_name"),
        "is_private": row.get("load_balancer_raw.is_private"),
    }


def _append_rows(rows, row, source_col, child_key):
    parent = _parent_raw(row)
    for child in _safe_list(row.get(source_col)):
        if isinstance(child, dict):
            rows.append({"load_balancer_raw": parent, child_key: child})


def _normalize(rows):
    return pd.json_normalize(rows) if rows else pd.DataFrame()


def transform(df):
    if df.empty:
        return {"Load_Balancers": df}

    sheets = {"Load_Balancers": df.copy()}
    listener_rows = []
    backend_set_rows = []
    backend_rows = []
    hostname_rows = []
    path_route_set_rows = []
    path_route_rows = []
    certificate_rows = []

    for _, row in df.iterrows():
        parent = _parent_raw(row)

        _append_rows(
            listener_rows,
            row,
            "load_balancer_enriched.listeners_list",
            "listener_raw",
        )
        _append_rows(
            hostname_rows,
            row,
            "load_balancer_enriched.hostnames_list",
            "hostname_raw",
        )
        _append_rows(
            certificate_rows,
            row,
            "load_balancer_enriched.certificates_list",
            "certificate_raw",
        )

        for backend_set in _safe_list(row.get("load_balancer_enriched.backend_sets_list")):
            if not isinstance(backend_set, dict):
                continue
            backend_set_rows.append(
                {"load_balancer_raw": parent, "backend_set_raw": backend_set}
            )
            for backend in _safe_list(backend_set.get("backends")):
                if isinstance(backend, dict):
                    backend_rows.append(
                        {
                            "load_balancer_raw": parent,
                            "backend_set_raw": backend_set,
                            "backend_raw": backend,
                        }
                    )

        for path_route_set in _safe_list(row.get("load_balancer_enriched.path_route_sets_list")):
            if not isinstance(path_route_set, dict):
                continue
            path_route_set_rows.append(
                {
                    "load_balancer_raw": parent,
                    "path_route_set_raw": path_route_set,
                }
            )
            for path_route in _safe_list(path_route_set.get("path_routes")):
                if isinstance(path_route, dict):
                    path_route_rows.append(
                        {
                            "load_balancer_raw": parent,
                            "path_route_set_raw": path_route_set,
                            "path_route_raw": path_route,
                        }
                    )

    optional = {
        "LB_Listeners": _normalize(listener_rows),
        "LB_Backend_Sets": _normalize(backend_set_rows),
        "LB_Backends": _normalize(backend_rows),
        "LB_Hostnames": _normalize(hostname_rows),
        "LB_Path_Route_Sets": _normalize(path_route_set_rows),
        "LB_Path_Route_Rules": _normalize(path_route_rows),
        "LB_Certificates": _normalize(certificate_rows),
    }

    for name, sheet_df in optional.items():
        if isinstance(sheet_df, pd.DataFrame) and not sheet_df.empty:
            sheets[name] = sheet_df

    return sheets

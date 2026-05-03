import oci
import common
import json
import os
from log_utils import log_event


def _log(level, region, compartment, event, resource_id="-", detail="", **fields):
    log_event(
        level,
        "vpn",
        event,
        region=region,
        compartment=compartment,
        resource=resource_id,
        detail=detail,
        **fields,
    )


def collect(client):
    _log("INFO", "-", "-", "collection_start", message="Collecting VPN IPSec Connections")
    all_vpns = []
    cpe_cache = {}
    drg_cache = {}
    error_count = 0
    total_count = 0
    
    for region in client.regions:
        _log("INFO", region, "-", "region_scan_start")
        config = client.config.copy()
        config['region'] = region
        
        network_client = common.create_client(oci.core.VirtualNetworkClient, config)
        
        for comp in client.compartments:
            comp_name = comp.name
            try:
                # 1. IPSec 연결 목록 조회
                connections = common.list_call_get_all_results(
                    network_client.list_ip_sec_connections,
                    compartment_id=comp.id
                ).data
                _log(
                    "INFO",
                    region,
                    comp_name,
                    "ipsec_connections_listed",
                    count=len(connections),
                )
                
            except oci.exceptions.ServiceError as e:
                if e.status != 404:
                    error_count += 1
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "ipsec_connection_listing_failed",
                        detail=f"code={e.status} message={e.message}",
                    )
                continue
            except Exception as e:
                error_count += 1
                _log(
                    "ERROR",
                    region,
                    comp_name,
                    "ipsec_connection_listing_unexpected_error",
                    detail=str(e),
                )
                continue

            for conn in connections:
                total_count += 1
                resource = {
                    "vpn_raw": oci.util.to_dict(conn),
                    "vpn_enriched": {
                        "cpe_details": {},
                        "drg_details": {},
                        "tunnels": [],
                    },
                    "_errors": [],
                }
                conn_dict = resource["vpn_raw"]
                conn_dict["region_name"] = region
                conn_dict["compartment_name"] = comp_name

                try:
                    conn_detail = common.call_with_retry(
                        network_client.get_ip_sec_connection,
                        conn.id,
                    ).data
                    conn_dict = oci.util.to_dict(conn_detail)
                    conn_dict["region_name"] = region
                    conn_dict["compartment_name"] = comp_name
                    resource["vpn_raw"] = conn_dict
                except Exception as e:
                    error_count += 1
                    resource["_errors"].append(f"ipsec connection detail fetch failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "ipsec_connection_detail_fetch_failed",
                        resource_id=conn.id,
                        detail=str(e),
                    )

                # 2. CPE 정보 연합 (Cache 활용)
                cpe_id = conn_dict.get("cpe_id")
                if cpe_id:
                    if cpe_id not in cpe_cache:
                        try:
                            cpe = common.call_with_retry(network_client.get_cpe, cpe_id).data
                            cpe_cache[cpe_id] = oci.util.to_dict(cpe)
                        except Exception as e:
                            error_count += 1
                            cpe_cache[cpe_id] = {"id": cpe_id}
                            resource["_errors"].append(f"cpe fetch failed: {e}")
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "cpe_fetch_failed",
                                resource_id=conn_dict.get("id", conn.id),
                                detail=str(e),
                            )
                    resource["vpn_enriched"]["cpe_details"] = cpe_cache[cpe_id]

                drg_id = conn_dict.get("drg_id")
                if drg_id:
                    if drg_id not in drg_cache:
                        try:
                            drg = common.call_with_retry(network_client.get_drg, drg_id).data
                            drg_cache[drg_id] = oci.util.to_dict(drg)
                        except Exception as e:
                            error_count += 1
                            drg_cache[drg_id] = {"id": drg_id}
                            resource["_errors"].append(f"drg fetch failed: {e}")
                            _log(
                                "WARN",
                                region,
                                comp_name,
                                "drg_fetch_failed",
                                resource_id=conn_dict.get("id", conn.id),
                                detail=str(e),
                            )
                    resource["vpn_enriched"]["drg_details"] = drg_cache[drg_id]

                # 3. 터널 정보 상세 수집
                try:
                    tunnels = common.list_call_get_all_results(
                        network_client.list_ip_sec_connection_tunnels,
                        conn.id,
                    ).data
                    resource["vpn_enriched"]["tunnels"] = [oci.util.to_dict(t) for t in tunnels]
                    _log(
                        "INFO",
                        region,
                        comp_name,
                        "ipsec_tunnels_listed",
                        resource_id=conn.id,
                        count=len(resource["vpn_enriched"]["tunnels"]),
                    )
                except Exception as e:
                    error_count += 1
                    resource["vpn_enriched"]["tunnels"] = []
                    resource["_errors"].append(f"tunnel listing failed: {e}")
                    _log(
                        "WARN",
                        region,
                        comp_name,
                        "ipsec_tunnels_listing_failed",
                        resource_id=conn.id,
                        detail=str(e),
                    )
                
                all_vpns.append(resource)
                
    _log("INFO", "-", "-", "collection_end", collected=total_count, errors=error_count)
    
    output_dir = os.path.join("raw_data", client.profile_name)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"vpn_{client.profile_name}.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_vpns, f, indent=4, default=str, ensure_ascii=False)
    return output_path

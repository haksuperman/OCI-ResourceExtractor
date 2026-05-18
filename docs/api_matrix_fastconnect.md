# FastConnect API Matrix

## Permission-Limited Collection

- 권한 부족(`401`, `403`, `404 NotAuthorizedOrNotFound`)은 공통 `permission_denied` 진단으로 남긴다.
- 권한 없는 `list_*` 범위는 WARN으로 기록하고 해당 범위만 스킵한다.
- 권한 없는 상세/관계 조회는 리소스 `_errors`에 기록하고 가능한 raw 수집을 계속한다.
- 권한 제한 profile 검증 시 로그, 웹 Health(`permission_limited`), Excel `99-Run_Diagnostics` 표현이 일치해야 한다.

## Scope
FastConnect 수집은 OCI Console의 Virtual Circuit 상세 화면에서 운영자가 확인하는 circuit 기본 구성, DRG 연결, provider service/key, public prefix, cross-connect mapping, associated tunnel, bandwidth shape 정보를 raw-first로 보존하는 것을 목표로 한다.

## P0 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.core.VirtualNetworkClient` | `list_virtual_circuits` | compartment 내 Virtual Circuit 목록 수집 | 마스터 FastConnect 리소스 발견의 시작점 | `fastconnect_raw` | region + compartment | compartment 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_virtual_circuit` | Virtual Circuit 상세 보강 | Console 상세의 상태/provider/routing/bandwidth/DRG 연결 재현에 필요 | `fastconnect_raw` | Virtual Circuit 1개당 1회 | Virtual Circuit 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_drg` | 연결 DRG 상세 보강 | DRG 이름과 연결 영향 범위 확인에 필요 | `networking_enriched.drg_details` | 고유 DRG OCID당 캐시 조회 | 고유 DRG 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_fast_connect_provider_service` | Provider service 상세 보강 | FastConnect provider 회선 식별과 Console 재현에 필요 | `fastconnect_enriched.provider_service_details` | 고유 provider service OCID당 캐시 조회 | 고유 provider service 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_fast_connect_provider_service_key` | Provider service key 상세 보강 | provider key 기반 회선 상태/식별 정보 확인에 필요 | `fastconnect_enriched.provider_service_key_details` | provider key 1개당 1회 | provider key 수에 비례 |
| `oci.core.VirtualNetworkClient` | `list_virtual_circuit_public_prefixes` | public prefix 목록 수집 | public peering 구성 검토에 필요 | `fastconnect_enriched.public_prefixes[]` | Virtual Circuit 1개당 1회 | Virtual Circuit 수에 비례 |
| `oci.core.VirtualNetworkClient` | `list_cross_connect_mappings` | cross-connect mapping 목록 수집 | BGP peering IP/VLAN/cross-connect 관계 확인에 필요 | `fastconnect_enriched.cross_connect_mappings[]` | Virtual Circuit 1개당 1회 | Virtual Circuit 수에 비례 |
| `oci.core.VirtualNetworkClient` | `list_virtual_circuit_associated_tunnels` | associated tunnel 목록 수집 | FastConnect over IPSec 등 tunnel 연관 추적에 필요 | `fastconnect_enriched.associated_tunnels[]` | Virtual Circuit 1개당 1회 | Virtual Circuit 수에 비례 |
| `oci.core.VirtualNetworkClient` | `list_virtual_circuit_bandwidth_shapes` | 사용 가능한 bandwidth shape 목록 수집 | 현재/가능 bandwidth 옵션 확인에 필요 | `fastconnect_enriched.bandwidth_shapes[]` | Virtual Circuit 1개당 1회 | Virtual Circuit 수에 비례 |

## P1 APIs

현재 collector에서 별도 P1 API는 사용하지 않는다.

## P0 Candidates

현재 없음.

## P1 Candidates

| SDK 클래스명 | 메소드명 | 호출 목적 | 후보 이유 | 예상 raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.core.VirtualNetworkClient` | `list_fast_connect_provider_services` | provider service 전체 목록 수집 | provider service id가 없는 legacy/수동 회선의 provider 맥락 보강이 필요할 때 채택 | `fastconnect_enriched.provider_services_catalog[]` | region 1회 | region 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_cross_connect` | cross-connect 상세 조회 | mapping의 cross_connect id를 이름/상태로 보강해야 할 때 채택 | `fastconnect_enriched.cross_connect_mappings[].cross_connect_detail` | mapping 1개당 1회 | mapping 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_cross_connect_group` | cross-connect group 상세 조회 | mapping의 group id를 이름/상태로 보강해야 할 때 채택 | `fastconnect_enriched.cross_connect_mappings[].cross_connect_group_detail` | mapping 1개당 1회 | mapping 수에 비례 |

## Hold Candidates

| SDK 클래스명 | 메소드명 | 보류 이유 |
| --- | --- | --- |
| `oci.core.VirtualNetworkClient` | 변경성 FastConnect/Virtual Circuit 메소드 | 수집 리포트에서 생성/수정/삭제성 API 호출 금지 |

## Formatter Mapping

| Raw source | Worksheet | Row grain |
| --- | --- | --- |
| `fastconnect_raw` | `Fastconnect` | Virtual Circuit 1개당 1행 |
| `fastconnect_enriched.public_prefixes[]` | `Fastconnect_Public_Prefixes` | Public Prefix 1개당 1행 |
| `fastconnect_enriched.cross_connect_mappings[]` | `Fastconnect_Cross_Connect_Mappings` | Cross Connect Mapping 1개당 1행 |
| `fastconnect_enriched.associated_tunnels[]` | `Fastconnect_Associated_Tunnels` | Associated Tunnel 1개당 1행 |
| `fastconnect_enriched.bandwidth_shapes[]` | `Fastconnect_Bandwidth_Shapes` | Bandwidth Shape 1개당 1행 |

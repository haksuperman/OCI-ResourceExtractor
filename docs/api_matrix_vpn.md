# VPN API Matrix

## Permission-Limited Collection

- 권한 부족(`401`, `403`, `404 NotAuthorizedOrNotFound`)은 공통 `permission_denied` 진단으로 남긴다.
- 권한 없는 `list_*` 범위는 WARN으로 기록하고 해당 범위만 스킵한다.
- 권한 없는 상세/관계 조회는 리소스 `_errors`에 기록하고 가능한 raw 수집을 계속한다.
- 권한 제한 profile 검증 시 로그, 웹 Health(`permission_limited`), Excel `99-Run_Diagnostics` 표현이 일치해야 한다.

## Scope
VPN 수집은 OCI Console의 Site-to-Site VPN(IPSec Connection) 상세 화면에서 운영자가 확인하는 IPSec connection 기본 구성, CPE, DRG, static route, tunnel 상태/암호화/BGP 정보를 raw-first로 보존하는 것을 목표로 한다.

## P0 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.core.VirtualNetworkClient` | `list_ip_sec_connections` | compartment 내 IPSec connection 목록 수집 | 마스터 VPN 리소스 발견의 시작점 | `vpn_raw` | region + compartment | compartment 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_ip_sec_connection` | IPSec connection 상세 보강 | Console 상세의 static route/연결 속성 재현에 필요 | `vpn_raw` | IPSec connection 1개당 1회 | VPN 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_cpe` | 연결 CPE 상세 보강 | 고객 장비 이름/IP를 같이 확인해야 운영 추적 가능 | `vpn_enriched.cpe_details` | 고유 CPE OCID당 캐시 조회 | 고유 CPE 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_drg` | 연결 DRG 상세 보강 | DRG 연결 영향 범위와 이름 식별에 필요 | `vpn_enriched.drg_details` | 고유 DRG OCID당 캐시 조회 | 고유 DRG 수에 비례 |
| `oci.core.VirtualNetworkClient` | `list_ip_sec_connection_tunnels` | IPSec tunnel 목록/상태 수집 | tunnel별 상태, BGP, 암호화 정보는 Console 재현과 장애 판단 핵심 정보 | `vpn_enriched.tunnels[]` | IPSec connection 1개당 1회 | VPN 수에 비례 |

## P1 APIs

현재 collector에서 별도 P1 API는 사용하지 않는다.

## P0 Candidates

현재 없음.

## P1 Candidates

| SDK 클래스명 | 메소드명 | 호출 목적 | 후보 이유 | 예상 raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.core.VirtualNetworkClient` | `get_ip_sec_connection_tunnel` | tunnel 상세 조회 | list tunnel 응답이 Console의 tunnel 상세 필드를 충분히 제공하지 않는 경우 채택 | `vpn_enriched.tunnels[].tunnel_detail` | Tunnel 1개당 1회 | Tunnel 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_drg_attachment` | DRG attachment 상세 보강 | VPN과 DRG attachment 관계를 별도 시트로 분석해야 할 때 채택 | `vpn_enriched.drg_attachment_detail` | VPN/DRG 관계당 1회 | VPN 수에 비례 |

## Hold Candidates

| SDK 클래스명 | 메소드명 | 보류 이유 |
| --- | --- | --- |
| `oci.core.VirtualNetworkClient` | 변경성 VPN/IPSec/CPE/DRG 메소드 | 수집 리포트에서 생성/수정/삭제성 API 호출 금지 |

## Formatter Mapping

| Raw source | Worksheet | Row grain |
| --- | --- | --- |
| `vpn_raw` | `Vpn` | IPSec connection 1개당 1행 |
| `vpn_enriched.tunnels[]` | `Vpn_Tunnels` | Tunnel 1개당 1행 |

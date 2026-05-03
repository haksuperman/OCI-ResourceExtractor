# Network Load Balancer API Matrix

## Scope
Network Load Balancer 수집은 OCI Console의 Network Load Balancer 상세 화면에서 운영자가 확인하는 기본 구성, Listener, Backend Set, Backend, Subnet, NSG 연결 정보를 raw-first로 보존하는 것을 목표로 한다.

## P0 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.network_load_balancer.NetworkLoadBalancerClient` | `list_network_load_balancers` | compartment 내 NLB 목록 수집 | 마스터 리소스 발견의 시작점 | `network_load_balancer_raw` | region + compartment | compartment 수에 비례 |
| `oci.network_load_balancer.NetworkLoadBalancerClient` | `get_network_load_balancer` | NLB 상세 정보 보강 | list 응답보다 Console 상세 재현성이 높음 | `network_load_balancer_raw` | NLB 1개당 1회 | NLB 수에 비례 |
| `oci.network_load_balancer.NetworkLoadBalancerClient` | `list_listeners` | Listener 구성 수집 | Listener/port/protocol/기본 backend set은 운영 영향 판단 핵심 정보 | `network_load_balancer_enriched.listeners_list` | NLB 1개당 1회 | NLB 수에 비례 |
| `oci.network_load_balancer.NetworkLoadBalancerClient` | `list_backend_sets` | Backend Set 구성 수집 | 트래픽 분산 정책/health checker 확인에 필요 | `network_load_balancer_enriched.backend_sets_list[]` | NLB 1개당 1회 | NLB 수에 비례 |
| `oci.network_load_balancer.NetworkLoadBalancerClient` | `list_backends` | Backend 서버 구성 수집 | 실제 트래픽 대상 IP/port/상태 판단에 필요 | `network_load_balancer_enriched.backend_sets_list[].backends` | Backend Set 1개당 1회 | NLB별 backend set 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_subnet` | 연결 Subnet 이름/상세 보강 | Console의 Networking 맥락 재현에 필요 | `networking_enriched.subnet_details` | subnet OCID 1개당 캐시 조회 | 고유 subnet 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_network_security_group` | 연결 NSG 이름/상세 보강 | 보안 연결 맥락 추적에 필요 | `networking_enriched.nsg_details[]` | NSG OCID 1개당 캐시 조회 | 고유 NSG 수에 비례 |

## P1 APIs

현재 collector에서 별도 P1 API는 사용하지 않는다. NLB의 Listener/Backend Set/Backend는 Console 운영 판단에 직접 필요한 구성 정보라 P0로 취급한다.

## P0 Candidates

현재 없음.

## P1 Candidates

| SDK 클래스명 | 메소드명 | 호출 목적 | 후보 이유 | 예상 raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.network_load_balancer.NetworkLoadBalancerClient` | `get_listener` | Listener 상세 조회 | list listener 응답이 상세 필드를 충분히 제공하지 않는 경우 채택 | `network_load_balancer_enriched.listeners_list[].listener_detail` | Listener 1개당 1회 | Listener 수에 비례 |
| `oci.network_load_balancer.NetworkLoadBalancerClient` | `get_backend_set` | Backend Set 상세 조회 | list backend set 응답이 health checker/정책 상세를 충분히 제공하지 않는 경우 채택 | `network_load_balancer_enriched.backend_sets_list[].backend_set_detail` | Backend Set 1개당 1회 | Backend Set 수에 비례 |
| `oci.network_load_balancer.NetworkLoadBalancerClient` | `get_backend` | Backend 상세 조회 | list backend 응답이 상태/속성 추적에 부족한 경우 채택 | `network_load_balancer_enriched.backend_sets_list[].backends[].backend_detail` | Backend 1개당 1회 | Backend 수에 비례 |

## Hold Candidates

| SDK 클래스명 | 메소드명 | 보류 이유 |
| --- | --- | --- |
| `oci.network_load_balancer.NetworkLoadBalancerClient` | `get_network_load_balancer_health` | 상태 모니터링 성격이 강해 구성 인벤토리 리포트 기본 범위에서는 보류 |
| `oci.network_load_balancer.NetworkLoadBalancerClient` | `get_backend_set_health` | 실행 시점 health 값은 변동성이 높아 별도 운영 모니터링 요구가 있을 때 채택 |
| `oci.network_load_balancer.NetworkLoadBalancerClient` | `get_backend_health` | backend별 health는 호출량이 많고 변동성이 높아 별도 요구 전까지 보류 |

## Formatter Mapping

| Raw source | Worksheet | Row grain |
| --- | --- | --- |
| `network_load_balancer_raw` | `NLB_Overview` | NLB 1개당 1행 |
| `network_load_balancer_enriched.listeners_list[]` | `NLB_Listeners` | Listener 1개당 1행 |
| `network_load_balancer_enriched.backend_sets_list[]` | `NLB_Backend_Sets` | Backend Set 1개당 1행 |
| `network_load_balancer_enriched.backend_sets_list[].backends[]` | `NLB_Backends` | Backend 1개당 1행 |

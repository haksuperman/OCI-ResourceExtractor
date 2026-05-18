# Load Balancer API Matrix

## Permission-Limited Collection

- 권한 부족(`401`, `403`, `404 NotAuthorizedOrNotFound`)은 공통 `permission_denied` 진단으로 남긴다.
- 권한 없는 `list_*` 범위는 WARN으로 기록하고 해당 범위만 스킵한다.
- 권한 없는 상세/관계 조회는 리소스 `_errors`에 기록하고 가능한 raw 수집을 계속한다.
- 권한 제한 profile 검증 시 로그, 웹 Health(`permission_limited`), Excel `99-Run_Diagnostics` 표현이 일치해야 한다.

이 문서는 `collectors/load_balancer.py`가 현재 실제로 호출하는 OCI SDK 메소드와 향후 확장 후보를 정리한 서비스별 API 문서다.

## 개요

- collector: `collectors/load_balancer.py`
- formatter: `formatters/formatter_load_balancer.py`
- raw path: `raw_data/<profile>/load_balancer_<profile>.json`
- raw top-level containers:
  - `load_balancer_raw`
  - `load_balancer_enriched`
  - `networking_enriched`
  - `_errors`

## Console 기준 리포트 구조

- `Load_Balancers`: Load Balancer 마스터 시트. 기본 속성, shape, IP, subnet, NSG, listener/backend/certificate raw 목록을 표시한다.
- `Load_Balancer_Listeners`: listener를 1행 1listener 구조로 표시한다.
- `Load_Balancer_Backend_Sets`: backend set을 1행 1backend set 구조로 표시한다.
- `Load_Balancer_Backends`: backend를 1행 1backend 구조로 표시한다.
- `Load_Balancer_Hostnames`: hostname을 1행 1hostname 구조로 표시한다.
- `Load_Balancer_Path_Route_Sets`: path route set을 1행 1set 구조로 표시한다.
- `Load_Balancer_Path_Routes`: path route rule을 1행 1rule 구조로 표시한다.
- `Load_Balancer_Certificates`: certificate를 1행 1certificate 구조로 표시한다.

## 현재 호출 중인 P0 메소드

- `oci.load_balancer.LoadBalancerClient.list_load_balancers`
  - 호출 목적: load balancer 수집의 기준 리소스 목록 확보
  - 분류 이유: 이 호출이 없으면 `load_balancer` 서비스 수집 자체가 성립하지 않는다
  - raw 저장 위치: 최소 식별 정보로 `load_balancer_raw` 초기화
  - 호출 단위: `region + compartment`
  - 호출량 영향: 기본 기준 호출

- `oci.load_balancer.LoadBalancerClient.get_load_balancer`
  - 호출 목적: load balancer 상세 정보 조회
  - 분류 이유: Console 상세 화면의 listener, backend set, backend, hostname, path route set, certificate 정보가 상세 응답에 포함된다
  - raw 저장 위치: `load_balancer_raw`
  - 호출 단위: `load_balancer`
  - 호출량 영향: load balancer 수에 비례

- `oci.core.VirtualNetworkClient.get_subnet`
  - 호출 목적: load balancer가 연결된 subnet 상세 조회
  - 분류 이유: subnet 이름과 네트워크 맥락은 Console 재현과 영향 분석에 필요하다
  - raw 저장 위치: `networking_enriched.subnet_details`
  - 호출 단위: `subnet_id` 기준 캐시
  - 호출량 영향: 참조 subnet 수에 비례

- `oci.core.VirtualNetworkClient.get_network_security_group`
  - 호출 목적: load balancer가 연결된 NSG 상세 조회
  - 분류 이유: 보안 검토와 Console 재현에 필요하다
  - raw 저장 위치: `networking_enriched.nsg_details`
  - 호출 단위: `nsg_id` 기준 캐시
  - 호출량 영향: 참조 NSG 수에 비례

## 현재 호출 중인 P1 메소드

- 현재 별도 P1 호출 없음
  - `get_load_balancer` 상세 응답에서 listener/backend/certificate/path route 정보를 함께 보존한다.
  - formatter는 이 중첩 구조를 도메인별 상세 시트로 분리한다.

## 미수집 후보 - P0

- `oci.load_balancer.LoadBalancerClient.get_backend_set`
  - 왜 후보인가: 현재 backend set은 `get_load_balancer` 상세 응답의 중첩 raw를 사용한다. Console backend set 상세와 필드 차이가 확인되면 채택한다
  - 운영 질문: "Backend set 상세 구성과 health checker 설정이 충분히 보존되는가?"
  - 저장 예상 위치: `load_balancer_enriched.backend_sets_list[*].backend_set_detail`
  - 호출량 영향: backend set 수에 비례

- `oci.load_balancer.LoadBalancerClient.get_backend`
  - 왜 후보인가: 현재 backend는 `get_load_balancer` 상세 응답의 중첩 raw를 사용한다. Console backend 상세와 필드 차이가 확인되면 채택한다
  - 운영 질문: "Backend 서버 상태/가중치/드레인/오프라인 설정이 충분히 보존되는가?"
  - 저장 예상 위치: `load_balancer_enriched.backend_sets_list[*].backends[*].backend_detail`
  - 호출량 영향: backend 수에 비례

- `oci.load_balancer.LoadBalancerClient.get_listener`
  - 왜 후보인가: 현재 listener는 `get_load_balancer` 상세 응답의 중첩 raw를 사용한다. Console listener 상세와 필드 차이가 확인되면 채택한다
  - 운영 질문: "Listener 프로토콜/포트/SSL/hostname/path route 설정이 충분히 보존되는가?"
  - 저장 예상 위치: `load_balancer_enriched.listeners_list[*].listener_detail`
  - 호출량 영향: listener 수에 비례

## 미수집 후보 - P1

- `oci.load_balancer.LoadBalancerClient.get_certificate`
  - 왜 후보인가: 현재 certificate는 `get_load_balancer` 상세 응답의 중첩 raw를 사용한다. 인증서 상세 화면과 필드 차이가 확인되면 채택한다
  - 운영 질문: "Certificate/CA chain/passphrase 여부 등 인증서 구성이 충분히 보존되는가?"
  - 저장 예상 위치: `load_balancer_enriched.certificates_list[*].certificate_detail`
  - 호출량 영향: certificate 수에 비례

- `oci.load_balancer.LoadBalancerClient.get_path_route_set`
  - 왜 후보인가: 현재 path route set은 `get_load_balancer` 상세 응답의 중첩 raw를 사용한다. 상세 화면과 필드 차이가 확인되면 채택한다
  - 운영 질문: "Path route rule과 backend set 연결이 충분히 보존되는가?"
  - 저장 예상 위치: `load_balancer_enriched.path_route_sets_list[*].path_route_set_detail`
  - 호출량 영향: path route set 수에 비례

- `oci.load_balancer.LoadBalancerClient.get_hostname`
  - 왜 후보인가: 현재 hostname은 `get_load_balancer` 상세 응답의 중첩 raw를 사용한다. 상세 화면과 필드 차이가 확인되면 채택한다
  - 운영 질문: "Hostname 구성이 충분히 보존되는가?"
  - 저장 예상 위치: `load_balancer_enriched.hostnames_list[*].hostname_detail`
  - 호출량 영향: hostname 수에 비례

## 미수집 후보 - 보류

- `oci.load_balancer.LoadBalancerClient.get_load_balancer_health`
  - 보류 이유: 상태 진단 성격이 강하고 실행 시점 상태 변동성이 높다. Inventory 기본 수집보다 운영 점검 모드에서 별도로 다루는 편이 적합하다

- `oci.load_balancer.LoadBalancerClient.get_backend_health`
  - 보류 이유: 상태 진단 성격이 강하고 시점성 데이터다. 정적 구성 리포트와 분리하는 편이 좋다

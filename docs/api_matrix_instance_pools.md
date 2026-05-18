# Instance Pools API Matrix

## Permission-Limited Collection

- 권한 부족(`401`, `403`, `404 NotAuthorizedOrNotFound`)은 공통 `permission_denied` 진단으로 남긴다.
- 권한 없는 `list_*` 범위는 WARN으로 기록하고 해당 범위만 스킵한다.
- 권한 없는 상세/관계 조회는 리소스 `_errors`에 기록하고 가능한 raw 수집을 계속한다.
- 권한 제한 profile 검증 시 로그, 웹 Health(`permission_limited`), Excel `99-Run_Diagnostics` 표현이 일치해야 한다.

이 문서는 `collectors/instance_pools.py`가 호출하는 OCI SDK 메소드와 후속 확장 후보를 정리한 서비스별 API 문서다.

## 개요

- collector: `collectors/instance_pools.py`
- formatter: `formatters/formatter_instance_pools.py`
- raw path: `raw_data/<profile>/instance_pools_<profile>.json`
- raw top-level containers:
  - `instance_pool_raw`
  - `instance_configuration_enriched`
  - `pool_instances_enriched`
  - `autoscaling_enriched`
  - `load_balancer_enriched`
  - `_errors`

## 현재 호출 중인 P0 메소드

- `oci.core.ComputeManagementClient.list_instance_pools`
  - 목적: compartment 내 instance pool 목록 확보
  - 분류 이유: 이 호출이 없으면 Instance Pool 서비스 수집 자체가 성립하지 않는다
  - raw 저장 위치: `instance_pool_raw`
  - 호출 단위: `region + compartment`
  - 호출량 영향: compartment 수에 비례

- `oci.core.ComputeManagementClient.get_instance_pool`
  - 목적: pool 상세 설정과 load balancer attachment 참조 보존
  - 분류 이유: list 응답만으로 Console 상세 화면의 pool 설정을 충분히 재현할 수 없다
  - raw 저장 위치: `instance_pool_raw`
  - 호출 단위: `instance_pool`
  - 호출량 영향: instance pool 수에 비례

- `oci.core.ComputeManagementClient.list_instance_pool_instances`
  - 목적: pool 소속 instance 목록 조회
  - 분류 이유: 운영자가 pool 단위 현재 구성원을 확인해야 scale 영향 범위를 판단할 수 있다
  - raw 저장 위치: `pool_instances_enriched.instances`
  - 호출 단위: `instance_pool`
  - 호출량 영향: instance pool 수에 비례

- `oci.core.ComputeManagementClient.get_instance_configuration`
  - 목적: pool이 사용하는 instance configuration 상세 조회
  - 분류 이유: pool 인스턴스 생성 템플릿은 장애/변경 영향 판단의 핵심 설정이다
  - raw 저장 위치: `instance_configuration_enriched.instance_configuration`
  - 호출 단위: `instance_configuration_id` 기준 캐시
  - 호출량 영향: 참조 instance configuration 수에 비례

- `oci.autoscaling.AutoScalingClient.list_auto_scaling_configurations`
  - 목적: compartment 내 autoscaling configuration 목록 조회
  - 분류 이유: pool이 autoscaling 대상인지 확인하기 위한 기준 데이터다
  - raw 저장 위치: `autoscaling_enriched.configurations[*].auto_scaling_configuration_raw`
  - 호출 단위: `region + compartment`
  - 호출량 영향: compartment 수에 비례

- `oci.autoscaling.AutoScalingClient.get_auto_scaling_configuration`
  - 목적: autoscaling configuration 상세 설정 조회
  - 분류 이유: list summary만으로 min/max/cooldown/resource 세부 속성 보존이 부족할 수 있다
  - raw 저장 위치: `autoscaling_enriched.configurations[*].auto_scaling_configuration_raw`
  - 호출 단위: `auto_scaling_configuration`
  - 호출량 영향: autoscaling configuration 수에 비례

- `oci.autoscaling.AutoScalingClient.list_auto_scaling_policies`
  - 목적: autoscaling configuration 하위 policy 목록 조회
  - 분류 이유: configuration만으로 실제 scaling 조건과 실행 방식을 판단할 수 없다
  - raw 저장 위치: `autoscaling_enriched.configurations[*].policies[*].auto_scaling_policy_raw`
  - 호출 단위: `auto_scaling_configuration`
  - 호출량 영향: autoscaling configuration 수에 비례

- `oci.autoscaling.AutoScalingClient.get_auto_scaling_policy`
  - 목적: autoscaling policy 상세 조회
  - 분류 이유: threshold/scheduled policy의 상세 조건은 운영 판단에 직접 필요하다
  - raw 저장 위치: `autoscaling_enriched.configurations[*].policies[*].auto_scaling_policy_raw`
  - 호출 단위: `auto_scaling_policy`
  - 호출량 영향: autoscaling policy 수에 비례

- `oci.core.ComputeManagementClient.get_instance_pool_load_balancer_attachment`
  - 목적: pool에 연결된 load balancer attachment 상세 조회
  - 분류 이유: attachment의 backend set, port, VNIC selection, lifecycle state는 Console의 핵심 연결 정보다
  - raw 저장 위치: `load_balancer_enriched.attachments[*].attachment_raw`
  - 호출 단위: `instance_pool.load_balancers[*]`
  - 호출량 영향: instance pool load balancer attachment 수에 비례

- `oci.load_balancer.LoadBalancerClient.get_load_balancer`
  - 목적: attachment가 참조하는 Load Balancer 이름/상태 조회
  - 분류 이유: 운영 가독성을 위해 OCID와 함께 Display Name이 필요하다
  - raw 저장 위치: `load_balancer_enriched.attachments[*].load_balancer_raw`
  - 호출 단위: load balancer attachment 기준 캐시
  - 호출량 영향: 참조 load balancer 수에 비례

- `oci.network_load_balancer.NetworkLoadBalancerClient.get_network_load_balancer`
  - 목적: attachment가 참조하는 Network Load Balancer 이름/상태 조회
  - 분류 이유: Instance Pool은 Load Balancer와 Network Load Balancer 모두 연결할 수 있다
  - raw 저장 위치: `load_balancer_enriched.attachments[*].network_load_balancer_raw`
  - 호출 단위: network load balancer attachment 기준 캐시
  - 호출량 영향: 참조 network load balancer 수에 비례

## 현재 호출 중인 P1 메소드

- 없음

## 미수집 후보 - P1

- `oci.load_balancer.LoadBalancerClient.get_backend_set`
  - 왜 후보인가: attachment의 `backend_set_name`으로 backend set 상세 정책과 health checker를 확인할 수 있다
  - 운영 질문: "Instance Pool traffic이 어떤 backend policy와 health check 조건으로 들어오는가?"
  - 저장 예상 위치: `load_balancer_enriched.attachments[*].backend_set_raw`
  - 호출량 영향: load balancer attachment 수에 비례

- `oci.load_balancer.LoadBalancerClient.list_backends`
  - 왜 후보인가: pool 소속 인스턴스가 실제 backend로 등록됐는지 확인할 수 있다
  - 운영 질문: "Pool instance가 LB backend set에 정상 등록되어 있는가?"
  - 저장 예상 위치: `load_balancer_enriched.attachments[*].backends`
  - 호출량 영향: backend set 수에 비례

- `oci.network_load_balancer.NetworkLoadBalancerClient.get_backend_set`
  - 왜 후보인가: NLB attachment의 backend set 상세 정책과 health checker를 확인할 수 있다
  - 운영 질문: "Instance Pool traffic이 어떤 NLB backend policy와 health check 조건으로 들어오는가?"
  - 저장 예상 위치: `load_balancer_enriched.attachments[*].network_backend_set_raw`
  - 호출량 영향: network load balancer attachment 수에 비례

- `oci.network_load_balancer.NetworkLoadBalancerClient.list_backends`
  - 왜 후보인가: pool 소속 인스턴스가 실제 NLB backend로 등록됐는지 확인할 수 있다
  - 운영 질문: "Pool instance가 NLB backend set에 정상 등록되어 있는가?"
  - 저장 예상 위치: `load_balancer_enriched.attachments[*].network_backends`
  - 호출량 영향: network backend set 수에 비례

## 보류 후보

- `oci.core.ComputeClient.get_instance`
  - 보류 이유: pool 구성원은 `Instance_Pool_Instances` 시트에서 pool membership 중심으로 제공하고, 개별 instance 상세는 기존 `Compute` 시트가 담당한다
  - 재검토 조건: Instance Pool 탭에서 개별 instance의 shape/network/storage까지 독립적으로 재현해야 하는 요구가 생길 때

- LB/NLB listener 전체 조회
  - 보류 이유: 초기 요구사항은 pool에 연결된 LB/NLB와 attachment 관계 확인이며 listener 전개는 기존 `load_balancer`, `network_load_balancer` 서비스 시트가 담당한다
  - 재검토 조건: Instance Pool 리포트만으로 트래픽 진입점 listener까지 단일 화면에서 확인해야 하는 요구가 생길 때

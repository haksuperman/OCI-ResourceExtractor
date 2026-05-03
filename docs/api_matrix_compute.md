# Compute API Matrix

이 문서는 `collectors/compute.py`가 현재 실제로 호출하는 OCI SDK 메소드와 향후 확장 후보를 정리한 서비스별 API 문서다.

## 개요

- collector: `collectors/compute.py`
- formatter: `formatters/formatter_compute.py`
- raw path: `raw_data/<profile>/compute_<profile>.json`
- raw top-level containers:
  - `compute_raw`
  - `networking_enriched`
  - `storage_enriched`
  - `compute_enriched`
  - `_errors`

## 현재 호출 중인 P0 메소드

- `oci.core.ComputeClient.list_instances`
  - 목적: compute 수집의 기준 인스턴스 목록 확보
  - 분류 이유: 이 호출이 없으면 `compute` 서비스 수집 자체가 성립하지 않는다
  - 저장 위치: `compute_raw`
  - 호출 단위: `region + compartment`
  - 호출량 영향: 기본 기준 호출

- `oci.core.ComputeClient.get_image`
  - 목적: 인스턴스 이미지의 OS / OS 버전 / 이미지명 보강
  - 분류 이유: 운영 시점에 인스턴스 OS 식별은 핵심 질문이며 Console 재현에도 직접 필요하다
  - 저장 위치: `compute_raw.image_details`
  - 호출 단위: `instance.image_id` 기준 캐시
  - 호출량 영향: 참조 이미지 수에 비례

- `oci.core.ComputeClient.list_vnic_attachments`
  - 목적: 인스턴스와 VNIC 연결 관계 조회
  - 분류 이유: Console의 Networking 맥락 재현을 위한 진입점이다
  - 저장 위치: `networking_enriched.vnic_attachments`
  - 호출 단위: `instance`
  - 호출량 영향: 인스턴스 수에 비례

- `oci.core.VirtualNetworkClient.get_vnic`
  - 목적: VNIC 상세 정보와 실제 public/private IP 확보
  - 분류 이유: 인스턴스 네트워크 추적의 핵심 raw다
  - 저장 위치: `networking_enriched.vnics`
  - 호출 단위: `vnic_attachment.vnic_id`
  - 호출량 영향: VNIC 수에 비례

- `oci.core.VirtualNetworkClient.get_subnet`
  - 목적: VNIC가 속한 subnet 이름과 VCN 연결 정보 보강
  - 분류 이유: subnet 식별은 Console 네트워크 맥락에서 필수다
  - 저장 위치: `networking_enriched.vnics[*].subnet_details`
  - 호출 단위: `vnic.subnet_id` 기준 캐시
  - 호출량 영향: 참조 subnet 수에 비례

- `oci.core.VirtualNetworkClient.get_vcn`
  - 목적: subnet 상위 VCN 이름 보강
  - 분류 이유: 운영자가 인스턴스 네트워크 소속을 판단할 때 VCN 정보가 필수다
  - 저장 위치: `networking_enriched.vnics[*].vcn_details`
  - 호출 단위: `subnet.vcn_id` 기준 캐시
  - 호출량 영향: 참조 VCN 수에 비례

- `oci.core.VirtualNetworkClient.get_network_security_group`
  - 목적: VNIC 연결 NSG 이름/식별자 보강
  - 분류 이유: 보안 검토와 Console 재현에 직접 필요하다
  - 저장 위치: `networking_enriched.vnics[*].nsg_details`
  - 호출 단위: `nsg_id` 기준 캐시
  - 호출량 영향: 참조 NSG 수에 비례

- `oci.core.ComputeClient.list_boot_volume_attachments`
  - 목적: 인스턴스 연결 boot volume 조회
  - 분류 이유: 인스턴스의 실제 부트 디스크 연결 여부를 raw로 보존해야 한다
  - 저장 위치: `storage_enriched.boot_volume_attachments`
  - 호출 단위: `instance`
  - 호출량 영향: 인스턴스 수에 비례

- `oci.core.BlockstorageClient.get_boot_volume`
  - 목적: boot volume 이름/용량 등 상세 조회
  - 분류 이유: Console 수준의 스토리지 식별과 요약값 산출에 필요하다
  - 저장 위치: `storage_enriched.boot_volume_details_all`, `storage_enriched.boot_volume_details`
  - 호출 단위: `boot_volume_id` 기준 캐시
  - 호출량 영향: 참조 boot volume 수에 비례

- `oci.core.ComputeClient.list_volume_attachments`
  - 목적: 인스턴스 연결 block volume 조회
  - 분류 이유: 추가 블록 스토리지 연결 여부는 운영 영향 판단에 필수다
  - 저장 위치: `storage_enriched.block_volume_attachments`
  - 호출 단위: `instance`
  - 호출량 영향: 인스턴스 수에 비례

- `oci.core.BlockstorageClient.get_volume`
  - 목적: block volume 이름/용량 등 상세 조회
  - 분류 이유: block volume 식별과 요약값 산출에 필요하다
  - 저장 위치: `storage_enriched.block_volume_details`
  - 호출 단위: `volume_id` 기준 캐시
  - 호출량 영향: 참조 block volume 수에 비례

## 현재 호출 중인 P1 메소드

- `oci.core.ComputeClient.list_compute_capacity_reservations`
  - 목적: compartment 내 capacity reservation 목록 조회
  - 분류 이유: 인스턴스가 예약 용량에 속하는지 운영 판단을 보강한다
  - 저장 위치: 인스턴스 매핑 후 `compute_enriched.capacity_reservation`
  - 호출 단위: `region + compartment`
  - 호출량 영향: compartment 수에 비례

- `oci.core.ComputeClient.list_compute_capacity_reservation_instances`
  - 목적: capacity reservation 과 instance 연결 관계 조회
  - 분류 이유: reservation 목록만으로는 어떤 인스턴스가 연결됐는지 알 수 없다
  - 저장 위치: 인스턴스 매핑 후 `compute_enriched.capacity_reservation_instance`
  - 호출 단위: `capacity_reservation`
  - 호출량 영향: reservation 수에 비례

- `oci.core.ComputeManagementClient.list_instance_pools`
  - 목적: compartment 내 instance pool 목록 조회
  - 분류 이유: 인스턴스가 pool 기반인지 판단하기 위한 기준 데이터다
  - 저장 위치: 인스턴스 매핑 후 `compute_enriched.instance_pools`
  - 호출 단위: `region + compartment`
  - 호출량 영향: compartment 수에 비례

- `oci.core.ComputeManagementClient.list_instance_pool_instances`
  - 목적: instance pool 과 instance 연결 관계 조회
  - 분류 이유: pool 소속 인스턴스를 식별해야 autoscaling 연계도 가능하다
  - 저장 위치: 인스턴스 매핑 후 `compute_enriched.instance_pools`
  - 호출 단위: `instance_pool`
  - 호출량 영향: instance pool 수에 비례

- `oci.autoscaling.AutoScalingClient.list_auto_scaling_configurations`
  - 목적: autoscaling 설정 목록 조회
  - 분류 이유: instance pool 운영 정책을 추적하는 보강 정보다
  - 저장 위치: 인스턴스 매핑 후 `compute_enriched.autoscaling_configurations`
  - 호출 단위: `region + compartment`
  - 호출량 영향: compartment 수에 비례

- `oci.autoscaling.AutoScalingClient.list_auto_scaling_policies`
  - 목적: autoscaling configuration 하위 policy 조회
  - 분류 이유: 설정만으로는 실제 scaling 조건을 알 수 없어 보강이 필요하다
  - 저장 위치: `compute_enriched.autoscaling_configurations[*].policies`
  - 호출 단위: `auto_scaling_configuration`
  - 호출량 영향: autoscaling configuration 수에 비례

- `oci.compute_instance_agent.PluginClient.list_instance_agent_plugins`
  - 목적: 인스턴스 agent plugin 상태 조회
  - 분류 이유: 운영성 판단에는 유용하지만 기본 인벤토리보다 우선순위는 낮다
  - 저장 위치: `compute_enriched.agent_plugin_status`, `compute_enriched.agent_plugin_count`
  - 호출 단위: `instance`
  - 호출량 영향: 인스턴스 수에 비례

- `oci.core.ComputeClient.list_instance_console_connections`
  - 목적: 인스턴스 콘솔 연결 조회
  - 분류 이유: 운영 접근 흔적/연결 상태 파악에 유용한 보강 정보다
  - 저장 위치: `compute_enriched.console_connections`, `compute_enriched.console_connection_count`
  - 호출 단위: `instance`
  - 호출량 영향: 인스턴스 수에 비례

## 미수집 후보 - P0

- `oci.core.ComputeClient.get_instance`
  - 왜 후보인가: 현재는 `list_instances` 결과를 기본 raw로 쓰고 있어 상세 속성 보존 범위가 제한될 수 있다
  - 운영 질문: "이 인스턴스의 상세 설정이 Console 상세 화면과 왜 다른가?"
  - 저장 예상 위치: `compute_raw.instance_detail` 또는 `compute_detail.instance`
  - 호출량 영향: `instance`당 1회

- `oci.core.ComputeManagementClient.get_instance_pool`
  - 왜 후보인가: 현재는 pool 소속 관계만 있고 pool 상세 설정은 raw에 없다
  - 운영 질문: "이 인스턴스가 속한 pool의 실제 운영 설정은 무엇인가?"
  - 저장 예상 위치: `compute_enriched.instance_pools[*].pool_detail`
  - 호출량 영향: `instance_pool`당 1회

- `oci.core.ComputeManagementClient.get_instance_configuration`
  - 왜 후보인가: pool 인스턴스의 원형 템플릿을 현재 raw에서 재현하지 못한다
  - 운영 질문: "이 pool 인스턴스는 어떤 템플릿으로 생성되는가?"
  - 저장 예상 위치: `compute_enriched.instance_pools[*].instance_configuration_detail`
  - 호출량 영향: `instance_configuration`당 1회

## 미수집 후보 - P1

- `oci.autoscaling.AutoScalingClient.get_auto_scaling_configuration`
  - 왜 후보인가: 현재는 autoscaling list 응답만 사용한다
  - 운영 질문: "autoscaling 설정의 상세 속성이 충분히 보존되고 있는가?"
  - 저장 예상 위치: `compute_enriched.autoscaling_configurations[*].configuration_detail`
  - 호출량 영향: `auto_scaling_configuration`당 1회

- `oci.autoscaling.AutoScalingClient.get_auto_scaling_policy`
  - 왜 후보인가: 현재 policy 상세 보존은 list 응답 수준에 머문다
  - 운영 질문: "실제 scaling policy 상세 설정은 무엇인가?"
  - 저장 예상 위치: `compute_enriched.autoscaling_configurations[*].policies[*].policy_detail`
  - 호출량 영향: `policy`당 1회

- `oci.core.ComputeClient.list_instance_maintenance_events`
  - 왜 후보인가: 현재 maintenance 관련 정보는 수집하지 않는다
  - 운영 질문: "이 인스턴스에 예정된 maintenance가 있는가?"
  - 저장 예상 위치: `compute_enriched.maintenance_events`
  - 호출량 영향: `instance`당 1회

- `oci.core.ComputeClient.get_instance_maintenance_event`
  - 왜 후보인가: maintenance event 상세를 운영 판단 수준까지 끌어올릴 수 있다
  - 운영 질문: "maintenance 이벤트의 구체적인 영향과 일정은 무엇인가?"
  - 저장 예상 위치: `compute_enriched.maintenance_events[*].event_detail`
  - 호출량 영향: `maintenance_event`당 1회

- `oci.core.ComputeClient.list_instance_devices`
  - 왜 후보인가: 현재 boot/block volume 외의 인스턴스 장치 관점 정보는 없다
  - 운영 질문: "이 인스턴스의 실제 디바이스 토폴로지는 어떻게 되는가?"
  - 저장 예상 위치: `storage_enriched.instance_devices`
  - 호출량 영향: `instance`당 1회

- `oci.compute_instance_agent.PluginClient.get_instance_agent_plugin`
  - 왜 후보인가: 현재 plugin list 결과만 저장한다
  - 운영 질문: "특정 agent plugin의 상세 상태와 속성은 무엇인가?"
  - 저장 예상 위치: `compute_enriched.agent_plugin_status[*].plugin_detail`
  - 호출량 영향: `plugin`당 1회

- `oci.core.ComputeClient.get_instance_console_connection`
  - 왜 후보인가: 현재는 console connection 목록만 저장한다
  - 운영 질문: "특정 console connection의 상세 상태는 무엇인가?"
  - 저장 예상 위치: `compute_enriched.console_connections[*].connection_detail`
  - 호출량 영향: `console_connection`당 1회

- `oci.core.ComputeClient.get_volume_attachment`
  - 왜 후보인가: 현재는 block volume attachment list 결과만 저장한다
  - 운영 질문: "block volume attachment의 세부 연결 속성은 무엇인가?"
  - 저장 예상 위치: `storage_enriched.block_volume_attachments[*].attachment_detail`
  - 호출량 영향: `volume_attachment`당 1회

- `oci.core.ComputeClient.get_boot_volume_attachment`
  - 왜 후보인가: 현재는 boot volume attachment list 결과만 저장한다
  - 운영 질문: "boot volume attachment의 세부 연결 속성은 무엇인가?"
  - 저장 예상 위치: `storage_enriched.boot_volume_attachments[*].attachment_detail`
  - 호출량 영향: `boot_volume_attachment`당 1회

- `oci.core.ComputeClient.get_vnic_attachment`
  - 왜 후보인가: 현재는 vnic attachment list 결과만 저장한다
  - 운영 질문: "vnic attachment의 세부 연결 속성은 무엇인가?"
  - 저장 예상 위치: `networking_enriched.vnic_attachments[*].attachment_detail`
  - 호출량 영향: `vnic_attachment`당 1회

## 미수집 후보 - 보류

- `oci.core.ComputeClient.list_console_histories`
  - 보류 이유: inventory보다 운영 로그/진단 성격이 강하고 데이터 양이 커질 수 있다

- `oci.core.ComputeClient.get_console_history`
  - 보류 이유: 메타데이터만으로도 활용도가 제한적이며 기본 인벤토리 우선순위가 아니다

- `oci.core.ComputeClient.get_console_history_content`
  - 보류 이유: 로그 본문은 민감도와 데이터 크기 문제가 커서 raw 기본 수집 대상으로 부적절하다

- `oci.core.ComputeClient.get_windows_instance_initial_credentials`
  - 보류 이유: 민감 정보다. 기본 인벤토리 수집 대상으로 넣으면 안 된다

- `oci.core.ComputeClient.get_measured_boot_report`
  - 보류 이유: 보안/신뢰성 분석에는 가치가 있지만 일반 운영 인벤토리 기본 범위를 벗어난다

- `oci.core.ComputeClient.get_instance_maintenance_reboot`
  - 보류 이유: 특정 운영 액션 컨텍스트가 강하고 상시 인벤토리 raw 범위로는 우선순위가 낮다

- `oci.core.ComputeClient.list_shapes`
  - 보류 이유: 인스턴스 인벤토리보다 리전 카탈로그 성격이 강하다

- `oci.core.ComputeClient.list_images`
  - 보류 이유: 현재는 실제 인스턴스가 참조하는 이미지에 대해서만 `get_image`를 호출하는 편이 비용 대비 효율이 높다

- `oci.core.ComputeClient.list_dedicated_vm_hosts`
  - 보류 이유: 인스턴스 중심 collector의 범위를 넘어 host 인벤토리 축으로 확장되는 성격이다

- `oci.core.ComputeClient.get_dedicated_vm_host`
  - 보류 이유: dedicated host를 별도 리소스 축으로 다룰 때 검토하는 편이 적절하다

- `oci.core.ComputeClient.list_compute_clusters`
  - 보류 이유: HPC/cluster 성격의 별도 리소스 축으로 보는 것이 맞다

- `oci.core.ComputeClient.get_compute_cluster`
  - 보류 이유: cluster 수집을 시작할 때 함께 검토하는 것이 자연스럽다

## 요약

- 현재 `compute`는 OCI SDK의 모든 `list_*` / `get_*`를 호출하지 않는다.
- 현재 collector는 운영 질문과 OCI Console 재현에 필요한 subset만 호출한다.
- 현재 raw는 인스턴스 기본 정보, 네트워크 연결, 스토리지 연결, pool/autoscaling/agent/console 보강까지 포함한다.
- 다음 확장 우선순위는 `get_instance`, `get_instance_pool`, `get_instance_configuration` 순서로 보는 것이 적절하다.

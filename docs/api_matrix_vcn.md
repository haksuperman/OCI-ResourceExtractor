# VCN API Matrix

이 문서는 `collectors/vcn.py`가 현재 실제로 호출하는 OCI SDK 메소드와 향후 확장 후보를 정리한 서비스별 API 문서다.

## 개요

- collector: `collectors/vcn.py`
- formatter: `formatters/formatter_vcn.py`
- raw path: `raw_data/<profile>/vcn_<profile>.json`
- raw top-level containers:
  - `vcn_raw`
  - `networking_enriched`
  - `_errors`

## Console 기준 리포트 구조

- `VCNs`: VCN 마스터 시트. VCN 자체 scalar 중심 운영 정보와 default 참조 ID를 표시한다.
- `VCN_Subnets`: VCN 하위 subnet 목록을 1행 1subnet 구조로 표시한다.
- `VCN_Route_Tables`: route table 목록을 1행 1route table 구조로 표시한다.
- `VCN_Route_Rules`: route rule 목록을 1행 1rule 구조로 표시한다.
- `VCN_Security_Lists`: security list 목록을 1행 1security list 구조로 표시한다.
- `VCN_Security_Rules`: security list ingress/egress rule을 1행 1rule 구조로 표시한다.
- `VCN_Network_Security_Groups`: NSG 목록을 1행 1NSG 구조로 표시한다.
- `VCN_NSG_Rules`: NSG security rule을 1행 1rule 구조로 표시한다.
- `VCN_Internet_Gateways`, `VCN_NAT_Gateways`, `VCN_Service_Gateways`, `VCN_Local_Peering_Gateways`, `VCN_DHCP_Options`: VCN 하위 네트워크 리소스를 도메인별로 표시한다.
- `VCN_DRG_Attachments`, `VCN_DRGs`, `VCN_Virtual_Circuits`: VCN과 DRG/FastConnect 연결 맥락을 표시한다.

## 현재 호출 중인 P0 메소드

- `oci.core.VirtualNetworkClient.list_vcns`
  - 호출 목적: VCN 수집의 기준 리소스 목록 확보
  - 분류 이유: 이 호출이 없으면 `vcn` 서비스 수집 자체가 성립하지 않는다
  - raw 저장 위치: `vcn_raw`
  - 호출 단위: `region + compartment`
  - 호출량 영향: 기본 기준 호출

- `oci.core.VirtualNetworkClient.list_subnets`
  - 호출 목적: VCN 하위 subnet 목록 조회
  - 분류 이유: subnet은 VCN Console 상세 화면의 핵심 하위 리소스이며 Compute/DB/LB 연결 영향 판단에 직접 필요하다
  - raw 저장 위치: `networking_enriched.subnets`
  - 호출 단위: `vcn`
  - 호출량 영향: VCN 수에 비례

- `oci.core.VirtualNetworkClient.list_route_tables`
  - 호출 목적: VCN 하위 route table 및 route rule 조회
  - 분류 이유: 트래픽 경로와 gateway/DRG/FastConnect 영향 판단에 필수다
  - raw 저장 위치: `networking_enriched.route_tables`
  - 호출 단위: `vcn`
  - 호출량 영향: VCN 수에 비례

- `oci.core.VirtualNetworkClient.list_security_lists`
  - 호출 목적: VCN 하위 security list 및 ingress/egress rule 조회
  - 분류 이유: 네트워크 보안 검토의 기본 자료다
  - raw 저장 위치: `networking_enriched.security_lists`
  - 호출 단위: `vcn`
  - 호출량 영향: VCN 수에 비례

- `oci.core.VirtualNetworkClient.list_network_security_groups`
  - 호출 목적: VCN 하위 NSG 목록 조회
  - 분류 이유: Console의 Network Security Groups 탭 재현과 보안 영향 판단에 필요하다
  - raw 저장 위치: `networking_enriched.network_security_groups`
  - 호출 단위: `vcn`
  - 호출량 영향: VCN 수에 비례

- `oci.core.VirtualNetworkClient.list_network_security_group_security_rules`
  - 호출 목적: NSG별 ingress/egress security rule 조회
  - 분류 이유: NSG 목록만으로는 실제 허용/차단 정책을 판단할 수 없다
  - raw 저장 위치: `networking_enriched.network_security_groups[*].security_rules`
  - 호출 단위: `network_security_group`
  - 호출량 영향: NSG 수에 비례

- `oci.core.VirtualNetworkClient.list_internet_gateways`
  - 호출 목적: VCN 하위 internet gateway 목록 조회
  - 분류 이유: public outbound/inbound 경로 판단에 필요하다
  - raw 저장 위치: `networking_enriched.internet_gateways`
  - 호출 단위: `vcn`
  - 호출량 영향: VCN 수에 비례

- `oci.core.VirtualNetworkClient.list_nat_gateways`
  - 호출 목적: VCN 하위 NAT gateway 목록 조회
  - 분류 이유: private subnet outbound 경로 판단에 필요하다
  - raw 저장 위치: `networking_enriched.nat_gateways`
  - 호출 단위: `vcn`
  - 호출량 영향: VCN 수에 비례

- `oci.core.VirtualNetworkClient.list_service_gateways`
  - 호출 목적: VCN 하위 service gateway 목록 조회
  - 분류 이유: OCI service network 경로 판단에 필요하다
  - raw 저장 위치: `networking_enriched.service_gateways`
  - 호출 단위: `vcn`
  - 호출량 영향: VCN 수에 비례

- `oci.core.VirtualNetworkClient.list_local_peering_gateways`
  - 호출 목적: VCN 하위 local peering gateway 목록 조회
  - 분류 이유: VCN 간 로컬 피어링 연결 맥락 판단에 필요하다
  - raw 저장 위치: `networking_enriched.local_peering_gateways`
  - 호출 단위: `vcn`
  - 호출량 영향: VCN 수에 비례

- `oci.core.VirtualNetworkClient.list_dhcp_options`
  - 호출 목적: VCN 하위 DHCP option 목록 조회
  - 분류 이유: subnet DNS/DHCP 동작 확인에 필요하다
  - raw 저장 위치: `networking_enriched.dhcp_options`
  - 호출 단위: `vcn`
  - 호출량 영향: VCN 수에 비례

## 현재 호출 중인 P1 메소드

- `oci.core.VirtualNetworkClient.list_drgs`
  - 호출 목적: compartment 내 DRG 목록 조회
  - 분류 이유: VCN과 DRG attachment 연결 정보를 이름과 함께 해석하기 위한 보강 데이터다
  - raw 저장 위치: VCN 연결 필터링 후 `networking_enriched.drgs`
  - 호출 단위: `region + compartment`
  - 호출량 영향: compartment 수에 비례

- `oci.core.VirtualNetworkClient.list_drg_attachments`
  - 호출 목적: compartment 내 DRG attachment 목록 조회
  - 분류 이유: VCN이 DRG에 연결되어 있는지 판단하기 위한 관계 데이터다
  - raw 저장 위치: VCN 연결 필터링 후 `networking_enriched.drg_attachments`
  - 호출 단위: `region + compartment`
  - 호출량 영향: compartment 수에 비례

- `oci.core.VirtualNetworkClient.list_virtual_circuits`
  - 호출 목적: compartment 내 virtual circuit 목록 조회
  - 분류 이유: VCN이 DRG를 통해 FastConnect와 연결되는 맥락을 보강한다
  - raw 저장 위치: VCN 관련 DRG 기준 필터링 후 `networking_enriched.virtual_circuits`
  - 호출 단위: `region + compartment`
  - 호출량 영향: compartment 수에 비례

## 미수집 후보 - P0

- `oci.core.VirtualNetworkClient.get_vcn`
  - 왜 후보인가: 현재는 `list_vcns` 응답을 기본 raw로 사용한다. Console 상세와 list 응답 간 필드 차이가 확인되면 채택한다
  - 운영 질문: "VCN 상세 화면의 속성이 raw에 모두 보존되는가?"
  - 저장 예상 위치: `vcn_raw.vcn_detail` 또는 `vcn_detail.vcn`
  - 호출량 영향: VCN 수에 비례

- `oci.core.VirtualNetworkClient.get_subnet`
  - 왜 후보인가: subnet 상세 화면과 list 응답 간 필드 차이가 확인되면 채택한다
  - 운영 질문: "Subnet 상세 화면의 핵심 속성이 누락되어 있지 않은가?"
  - 저장 예상 위치: `networking_enriched.subnets[*].subnet_detail`
  - 호출량 영향: subnet 수에 비례

- `oci.core.VirtualNetworkClient.get_route_table`
  - 왜 후보인가: route table 상세 화면과 list 응답 간 필드 차이가 확인되면 채택한다
  - 운영 질문: "Route table/rule 상세 구성이 정확히 보존되는가?"
  - 저장 예상 위치: `networking_enriched.route_tables[*].route_table_detail`
  - 호출량 영향: route table 수에 비례

- `oci.core.VirtualNetworkClient.get_security_list`
  - 왜 후보인가: security list 상세 화면과 list 응답 간 필드 차이가 확인되면 채택한다
  - 운영 질문: "Security list rule 상세가 정확히 보존되는가?"
  - 저장 예상 위치: `networking_enriched.security_lists[*].security_list_detail`
  - 호출량 영향: security list 수에 비례

## 미수집 후보 - P1

- `oci.core.VirtualNetworkClient.get_network_security_group`
  - 왜 후보인가: NSG list와 rule 수집만으로 상세 메타데이터가 부족하면 채택한다
  - 운영 질문: "NSG 상세 속성이 Console과 일치하는가?"
  - 저장 예상 위치: `networking_enriched.network_security_groups[*].nsg_detail`
  - 호출량 영향: NSG 수에 비례

- `oci.core.VirtualNetworkClient.get_internet_gateway`
  - 왜 후보인가: gateway list 응답에 상세 속성이 부족하면 채택한다
  - 운영 질문: "IGW 활성화/상태 상세가 Console과 일치하는가?"
  - 저장 예상 위치: `networking_enriched.internet_gateways[*].gateway_detail`
  - 호출량 영향: internet gateway 수에 비례

- `oci.core.VirtualNetworkClient.get_nat_gateway`
  - 왜 후보인가: NAT gateway list 응답에 상세 속성이 부족하면 채택한다
  - 운영 질문: "NAT gateway public IP/traffic block 상태가 Console과 일치하는가?"
  - 저장 예상 위치: `networking_enriched.nat_gateways[*].gateway_detail`
  - 호출량 영향: NAT gateway 수에 비례

- `oci.core.VirtualNetworkClient.get_service_gateway`
  - 왜 후보인가: service gateway list 응답에 상세 속성이 부족하면 채택한다
  - 운영 질문: "Service gateway 대상 서비스와 block 상태가 Console과 일치하는가?"
  - 저장 예상 위치: `networking_enriched.service_gateways[*].gateway_detail`
  - 호출량 영향: service gateway 수에 비례

- `oci.core.VirtualNetworkClient.get_local_peering_gateway`
  - 왜 후보인가: local peering gateway list 응답에 상세 속성이 부족하면 채택한다
  - 운영 질문: "LPG peering 상태와 peer 관계가 Console과 일치하는가?"
  - 저장 예상 위치: `networking_enriched.local_peering_gateways[*].gateway_detail`
  - 호출량 영향: LPG 수에 비례

- `oci.core.VirtualNetworkClient.get_dhcp_options`
  - 왜 후보인가: DHCP option list 응답에 상세 options 보존이 부족하면 채택한다
  - 운영 질문: "DHCP/DNS 옵션이 Console과 일치하는가?"
  - 저장 예상 위치: `networking_enriched.dhcp_options[*].dhcp_options_detail`
  - 호출량 영향: DHCP option 수에 비례

## 미수집 후보 - 보류

- `oci.core.VirtualNetworkClient.list_private_ips`
  - 보류 이유: VCN 인벤토리보다 subnet/VNIC/Compute 상세 수집에서 다루는 편이 관계 추적에 적합하다

- `oci.core.VirtualNetworkClient.list_public_ips`
  - 보류 이유: public IP inventory 서비스로 분리하거나 Compute/LB/NAT Gateway 맥락에서 수집하는 편이 중복을 줄인다

- `oci.core.VirtualNetworkClient.list_ip_inventory`
  - 보류 이유: IP 사용 현황 분석에는 유용하지만 VCN 구성 리포트 기본 범위를 넘어설 수 있다

# DNS API Matrix

## Scope
DNS 수집은 OCI Console의 DNS Zone 상세 화면에서 운영자가 확인하는 Zone 기본 구성과 Record 목록을 raw-first로 보존하는 것을 목표로 한다. `dns`는 global 서비스로 취급하며 리전 루프 내부에서 반복 실행하지 않는다.

## P0 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.dns.DnsClient` | `list_zones` | compartment 내 DNS Zone 목록 수집 | 마스터 DNS Zone 발견의 시작점 | `dns_raw` | compartment | compartment 수에 비례 |
| `oci.dns.DnsClient` | `get_zone` | DNS Zone 상세 보강 | Console 상세의 zone 상태/scope/serial/DNSSEC 정보를 재현하기 위해 필요 | `dns_raw` | Zone 1개당 1회 | Zone 수에 비례 |
| `oci.dns.DnsClient` | `get_zone_records` | Zone record 목록 수집 | 실제 DNS 운영값(domain/type/ttl/rdata) 확인에 필수 | `dns_enriched.records[]` | Zone 1개당 1회 | Zone 수와 record 수에 비례 |

## P1 APIs

현재 collector에서 별도 P1 API는 사용하지 않는다.

## P0 Candidates

현재 없음.

## P1 Candidates

| SDK 클래스명 | 메소드명 | 호출 목적 | 후보 이유 | 예상 raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.dns.DnsClient` | `list_views` | private DNS view 목록 수집 | private zone의 view 맥락을 별도 시트로 분석해야 할 때 채택 | `dns_enriched.views[]` | compartment | compartment 수에 비례 |
| `oci.dns.DnsClient` | `get_view` | private DNS view 상세 보강 | view 이름/상태와 private zone 관계를 추적해야 할 때 채택 | `dns_enriched.view_detail` | View 1개당 1회 | View 수에 비례 |
| `oci.dns.DnsClient` | `get_rr_set` | RRSet 상세 조회 | 특정 record set 단위로 Console 상세를 재현해야 할 때 채택 | `dns_enriched.rrsets[]` | RRSet 1개당 1회 | RRSet 수에 비례 |

## Hold Candidates

| SDK 클래스명 | 메소드명 | 보류 이유 |
| --- | --- | --- |
| `oci.dns.DnsClient` | 변경성 Zone/Record 메소드 | 수집 리포트에서 생성/수정/삭제성 API 호출 금지 |
| `oci.dns.DnsClient` | steering policy 관련 API | DNS traffic management 요구가 명확해질 때 별도 서비스/시트로 확장 |

## Formatter Mapping

| Raw source | Worksheet | Row grain |
| --- | --- | --- |
| `dns_raw` | `DNS_Zones` | Zone 1개당 1행 |
| `dns_enriched.records[]` | `DNS_Records` | Record 1개당 1행 |

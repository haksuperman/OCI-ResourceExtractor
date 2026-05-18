# WAF Edge API Matrix

## Permission-Limited Collection

- 권한 부족(`401`, `403`, `404 NotAuthorizedOrNotFound`)은 공통 `permission_denied` 진단으로 남긴다.
- 권한 없는 `list_*` 범위는 WARN으로 기록하고 해당 범위만 스킵한다.
- 권한 없는 상세/관계 조회는 리소스 `_errors`에 기록하고 가능한 raw 수집을 계속한다.
- 권한 제한 profile 검증 시 로그, 웹 Health(`permission_limited`), Excel `99-Run_Diagnostics` 표현이 일치해야 한다.

## Scope
WAF Edge(legacy WAAS) 수집은 OCI Console의 WAAS Policy 상세 화면에서 운영자가 확인하는 policy 기본 구성, domain/origin, WAF config, custom protection rule, access rule, protection rule, address rate limiting 정보를 raw-first로 보존하는 것을 목표로 한다.

## P0 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.waas.WaasClient` | `list_waas_policies` | compartment 내 WAAS policy 목록 수집 | 마스터 WAF Edge 리소스 발견의 시작점 | `waf_edge_raw` | region + compartment | compartment 수에 비례 |
| `oci.waas.WaasClient` | `get_waas_policy` | WAAS policy 상세 보강 | Console 상세의 domain/origin/waf_config/rule 정보를 재현하기 위해 필요 | `waf_edge_raw`, `waf_edge_enriched.custom_protection_rules[]` | WAAS policy 1개당 1회 | policy 수에 비례 |

## P1 APIs

현재 collector에서 별도 P1 API는 사용하지 않는다.

## P0 Candidates

현재 없음.

## P1 Candidates

| SDK 클래스명 | 메소드명 | 호출 목적 | 후보 이유 | 예상 raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.waas.WaasClient` | `list_custom_protection_rules` | custom protection rule 카탈로그 수집 | policy detail에 포함되지 않는 custom rule 상세가 필요할 때 채택. 일부 테넌시에서 404/권한 오류가 발생해 현재 기본 호출에서는 제외 | `waf_edge_enriched.custom_protection_rule_catalog[]` | region + compartment | rule 수에 비례 |

## Hold Candidates

| SDK 클래스명 | 메소드명 | 보류 이유 |
| --- | --- | --- |
| `oci.waas.WaasClient` | 변경성 WAAS policy/custom rule 메소드 | 수집 리포트에서 생성/수정/삭제성 API 호출 금지 |

## Formatter Mapping

| Raw source | Worksheet | Row grain |
| --- | --- | --- |
| `waf_edge_raw` | `WAF_Edge` | WAAS policy 1개당 1행 |
| `waf_edge_enriched.custom_protection_rules[]` | `WAF_Edge_Custom_Rules` | Custom protection rule 1개당 1행 |
| `waf_edge_raw.waf_config.access_rules[]` | `WAF_Edge_Access_Rules` | Access rule 1개당 1행 |
| `waf_edge_raw.waf_config.protection_rules[]` | `WAF_Edge_Protection_Rules` | Protection rule 1개당 1행 |
| `waf_edge_raw.waf_config.address_rate_limiting` | `WAF_Edge_Rate_Limits` | Rate limit config 1개당 1행 |

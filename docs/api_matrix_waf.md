# WAF API Matrix

## Scope
WAF 수집은 OCI Console의 Web Application Firewall Policy 상세 화면에서 운영자가 확인하는 policy 기본 구성, 연결 firewall, request/response access control, protection rule/capability, rate limit, action 정보를 raw-first로 보존하는 것을 목표로 한다.

## P0 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.waf.WafClient` | `list_web_app_firewall_policies` | compartment 내 WAF policy 목록 수집 | 마스터 policy 리소스 발견의 시작점 | `waf_raw` | region + compartment | compartment 수에 비례 |
| `oci.waf.WafClient` | `get_web_app_firewall_policy` | WAF policy 상세 보강 | Console 상세의 access/protection/rate/action 정책 재현에 필요 | `waf_raw` | WAF policy 1개당 1회 | policy 수에 비례 |
| `oci.waf.WafClient` | `list_web_app_firewalls` | policy에 연결된 firewall 목록 수집 | policy가 실제 어떤 backend/firewall에 적용되는지 확인에 필요 | `waf_enriched.firewalls[]` | WAF policy 1개당 1회 | policy 수에 비례 |

## P1 APIs

현재 collector에서 별도 P1 API는 사용하지 않는다.

## P0 Candidates

현재 없음.

## P1 Candidates

| SDK 클래스명 | 메소드명 | 호출 목적 | 후보 이유 | 예상 raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.waf.WafClient` | `get_web_app_firewall` | 연결 firewall 상세 조회 | list firewall 응답이 backend/load balancer 상세를 충분히 제공하지 않는 경우 채택 | `waf_enriched.firewalls[].firewall_detail` | Firewall 1개당 1회 | firewall 수에 비례 |
| `oci.waf.WafClient` | `list_protection_capabilities` | protection capability catalog 수집 | capability key를 이름/설명으로 해석해야 할 때 채택 | `waf_enriched.protection_capability_catalog[]` | region 1회 또는 policy별 | catalog 크기에 비례 |

## Hold Candidates

| SDK 클래스명 | 메소드명 | 보류 이유 |
| --- | --- | --- |
| `oci.waf.WafClient` | 변경성 WAF policy/firewall 메소드 | 수집 리포트에서 생성/수정/삭제성 API 호출 금지 |

## Formatter Mapping

| Raw source | Worksheet | Row grain |
| --- | --- | --- |
| `waf_raw` | `WAF` | WAF policy 1개당 1행 |
| `waf_enriched.firewalls[]` | `WAF_Firewalls` | Firewall 1개당 1행 |
| `waf_raw.request_access_control.rules[]` | `WAF_Request_Access` | Request access rule 1개당 1행 |
| `waf_raw.response_access_control.rules[]` | `WAF_Response_Access` | Response access rule 1개당 1행 |
| `waf_raw.request_protection.rules[]` + `protection_capabilities[]` | `WAF_Request_Protection` | Protection rule/capability 1개당 1행 |
| `waf_raw.response_protection.rules[]` + `protection_capabilities[]` | `WAF_Response_Protection` | Protection rule/capability 1개당 1행 |
| `waf_raw.request_rate_limiting.rules[]` | `WAF_Request_Rate_Limits` | Rate limit rule 1개당 1행 |
| `waf_raw.actions[]` | `WAF_Actions` | Action 1개당 1행 |

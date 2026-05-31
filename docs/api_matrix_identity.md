# IAM / Identity API Matrix

## Permission-Limited Collection

IAM / Identity 수집은 권한 부족을 서비스 전체 실패로 숨기지 않는다. `list_*` 실패는 해당 범위만 `WARN`으로 기록하고 가능한 다른 IAM 리소스 수집을 계속한다. `get_*` 상세 조회 실패는 해당 리소스의 `_errors`에 누적한다.

## Scope

이 문서는 `collectors/identity.py`가 현재 실제로 호출하는 OCI SDK 메소드와 후속 확장 후보를 정리한 서비스별 API 문서다.

- collector: `collectors/identity.py`
- formatter: `formatters/formatter_identity.py`
- raw path: `raw_data/<profile>/identity_<profile>.json`
- primary raw containers:
  - `identity_raw`
  - `identity_enriched`
  - `_errors`

IAM / Identity 수집은 OCI Console의 Identity & Security 영역에서 보안/권한 검토자가 확인하는 Users, Groups, Dynamic Groups, Policies, Compartments, Tag Namespaces, Network Sources 구성을 raw-first로 보존하는 것을 목표로 한다. User-Group Membership과 Tag Definition은 부모 리소스 상세 판단에 필요한 하위 구성이라 상세 시트로 분리한다.

## P0 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.identity.IdentityClient` | `list_compartments` | 전체 compartment 계층 수집 | 정책/태그 네임스페이스 범위와 리소스 소유 컨텍스트 판단의 기준 | `identity_raw` (`resource_type=compartment`) | tenancy 1회 | compartment 수에 비례 |
| `oci.identity.IdentityClient` | `get_compartment` | compartment 상세 보강 | root compartment 포함 상세 필드와 Console 표시 정보를 보존 | `identity_raw` (`resource_type=compartment`) | compartment 1개당 1회 | compartment 수에 비례 |
| `oci.identity.IdentityClient` | `list_users` | tenancy IAM user 목록 수집 | 권한 검토의 주체 리소스 발견 시작점 | `identity_raw` (`resource_type=user`) | tenancy 1회 | user 수에 비례 |
| `oci.identity.IdentityClient` | `get_user` | user 상세 보강 | Console의 user 상태, email, capabilities 등 상세 판단에 필요 | `identity_raw` (`resource_type=user`) | user 1개당 1회 | user 수에 비례 |
| `oci.identity.IdentityClient` | `list_user_group_memberships` | user별 group membership 수집 | user가 어떤 group을 통해 권한을 받는지 추적해야 함 | `identity_enriched.group_memberships[]` | user 1개당 1회 | user 수에 비례 |
| `oci.identity.IdentityClient` | `list_groups` | group 목록 수집 | 정책 statement의 principal 추적 기준 | `identity_raw` (`resource_type=group`) | tenancy 1회 | group 수에 비례 |
| `oci.identity.IdentityClient` | `get_group` | group 상세 보강 | list 응답보다 Console 상세 재현성이 높음 | `identity_raw` (`resource_type=group`) | group 1개당 1회 | group 수에 비례 |
| `oci.identity.IdentityClient` | `list_dynamic_groups` | dynamic group 목록 수집 | instance/resource principal 권한 부여 조건 검토의 핵심 | `identity_raw` (`resource_type=dynamic_group`) | tenancy 1회 | dynamic group 수에 비례 |
| `oci.identity.IdentityClient` | `get_dynamic_group` | dynamic group 상세 보강 | matching rule과 상태 확인에 필요 | `identity_raw` (`resource_type=dynamic_group`) | dynamic group 1개당 1회 | dynamic group 수에 비례 |
| `oci.identity.IdentityClient` | `list_policies` | compartment별 policy 목록 수집 | 실제 권한 부여 statement 원천 수집 | `identity_raw` (`resource_type=policy`) | compartment 1개당 1회 | compartment 수와 policy 수에 비례 |
| `oci.identity.IdentityClient` | `get_policy` | policy 상세 보강 | statement/version/description 상세 보존 | `identity_raw` (`resource_type=policy`) | policy 1개당 1회 | policy 수에 비례 |
| `oci.identity.IdentityClient` | `list_tag_namespaces` | tag namespace 전체 목록 수집 | governance/tagging 기준과 비용/운영 분류 정책 확인 | `identity_raw` (`resource_type=tag_namespace`) | tenancy 1회 (`include_subcompartments=True`) | namespace 수에 비례 |
| `oci.identity.IdentityClient` | `get_tag_namespace` | tag namespace 상세 보강 | namespace lifecycle/retired/description 상세 보존 | `identity_raw` (`resource_type=tag_namespace`) | namespace 1개당 1회 | namespace 수에 비례 |
| `oci.identity.IdentityClient` | `list_tags` | namespace 하위 tag definition 수집 | 실제 적용 가능한 tag key/validator/cost tracking 확인 | `identity_enriched.tags[]` | namespace 1개당 1회 | tag namespace와 tag 수에 비례 |
| `oci.identity.IdentityClient` | `get_tag` | tag definition 상세 보강 | validator, cost tracking, lifecycle 등 Console 상세 재현 | `identity_enriched.tags[]` | tag 1개당 1회 | tag 수에 비례 |
| `oci.identity.IdentityClient` | `list_network_sources` | network source 목록 수집 | IAM policy 조건의 source restriction 검토에 필요 | `identity_raw` (`resource_type=network_source`) | tenancy 1회 | network source 수에 비례 |
| `oci.identity.IdentityClient` | `get_network_source` | network source 상세 보강 | public/virtual source list와 service 조건 상세 보존 | `identity_raw` (`resource_type=network_source`) | network source 1개당 1회 | network source 수에 비례 |

## P1 APIs

현재 collector에서 별도 P1 API는 사용하지 않는다. 사용자 credential 메타데이터와 Identity Domains는 보안 가치가 높지만 권한/민감도/호출량 영향이 있어 별도 요청 시 확장한다.

## P0 Candidates

현재 요청 범위 기준 P0 후보는 없다.

## P1 Candidates

| SDK 클래스명 | 메소드명 | 호출 목적 | 후보 이유 | 예상 raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.identity.IdentityClient` | `list_domains` | Identity Domain 목록 수집 | Identity Domains 사용 테넌시에서 도메인별 사용자/그룹 권한 경계를 확인해야 할 때 채택 | `identity_domain_raw` 또는 `identity_enriched.domains[]` | tenancy 또는 compartment | domain 수에 비례 |
| `oci.identity.IdentityClient` | `list_api_keys` | user별 API key 메타데이터 수집 | 장기 키/회전 상태 보안 점검 요구가 있을 때 채택 | `identity_enriched.user_credentials.api_keys[]` | user 1개당 1회 | user 수에 비례 |
| `oci.identity.IdentityClient` | `list_auth_tokens` | user별 auth token 메타데이터 수집 | Object Storage Swift/API token 사용 점검 요구가 있을 때 채택 | `identity_enriched.user_credentials.auth_tokens[]` | user 1개당 1회 | user 수에 비례 |
| `oci.identity.IdentityClient` | `list_customer_secret_keys` | user별 customer secret key 메타데이터 수집 | S3 compatible key 보안 점검 요구가 있을 때 채택 | `identity_enriched.user_credentials.customer_secret_keys[]` | user 1개당 1회 | user 수에 비례 |
| `oci.identity.IdentityClient` | `list_mfa_totp_devices` | user별 MFA device 메타데이터 수집 | MFA 활성화 근거를 상세하게 검증해야 할 때 채택 | `identity_enriched.user_security.mfa_totp_devices[]` | user 1개당 1회 | user 수에 비례 |
| `oci.identity.IdentityClient` | `list_tag_defaults` | compartment별 tag default 수집 | 리소스 생성 시 자동 태그 정책 검토 요구가 있을 때 채택 | `identity_enriched.tag_defaults[]` | compartment 1개당 1회 | compartment 수에 비례 |
| `oci.identity.IdentityClient` | `list_cost_tracking_tags` | 비용 추적 tag 목록 수집 | 비용 관리/FinOps 리포트와 연결할 때 채택 | `identity_enriched.cost_tracking_tags[]` | tenancy 1회 | tag 수에 비례 |

## Hold Candidates

| SDK 클래스명 | 메소드명 | 보류 이유 |
| --- | --- |
| `oci.identity.IdentityClient` | create/update/delete 계열 IAM 메소드 | 수집 리포트에서 생성/수정/삭제성 API 호출 금지 |
| `oci.identity.IdentityClient` | deprecated identity provider/idp mapping API | Identity Domains 전환 환경과 혼재 가능성이 있어 별도 요구 전까지 기본 수집 제외 |

## Formatter Mapping

| raw path | sheet | row granularity |
| --- | --- | --- |
| `identity_raw(resource_type=user)` | `IAM_Users` | User 1개당 1행 |
| `identity_raw(resource_type=group)` | `IAM_Groups` | Group 1개당 1행 |
| `identity_raw(resource_type=dynamic_group)` | `IAM_Dynamic_Groups` | Dynamic Group 1개당 1행 |
| `identity_raw(resource_type=policy)` | `IAM_Policies` | Policy 1개당 1행 |
| `identity_raw(resource_type=compartment)` | `IAM_Compartments` | Compartment 1개당 1행 |
| `identity_raw(resource_type=tag_namespace)` | `IAM_Tag_Namespaces` | Tag Namespace 1개당 1행 |
| `identity_enriched.tags[]` | `IAM_Tags` | Tag Definition 1개당 1행 |
| `identity_raw(resource_type=network_source)` | `IAM_Network_Sources` | Network Source 1개당 1행 |
| `identity_enriched.group_memberships[]` | `IAM_User_Group_Memberships` | User-Group Membership 1개당 1행 |

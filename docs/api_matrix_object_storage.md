# Object Storage API Matrix

## Permission-Limited Collection

- 권한 부족(`401`, `403`, `404 NotAuthorizedOrNotFound`)은 공통 `permission_denied` 진단으로 남긴다.
- 권한 없는 `list_*` 범위는 WARN으로 기록하고 해당 범위만 스킵한다.
- 권한 없는 상세/관계 조회는 리소스 `_errors`에 기록하고 가능한 raw 수집을 계속한다.
- 권한 제한 profile 검증 시 로그, 웹 Health(`permission_limited`), Excel `99-Run_Diagnostics` 표현이 일치해야 한다.

## Scope
Object Storage 수집은 OCI Console의 Bucket 상세 화면에서 운영자가 확인하는 bucket 기본 구성, namespace, public access, versioning, auto tiering, approximate object count/size, KMS, retention rule 정보를 raw-first로 보존하는 것을 목표로 한다.

## P0 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.object_storage.ObjectStorageClient` | `get_namespace` | region별 Object Storage namespace 확인 | 모든 bucket API 호출의 필수 입력값 | `object_storage_raw.namespace_name` | region 1회 | region 수에 비례 |
| `oci.object_storage.ObjectStorageClient` | `list_buckets` | compartment 내 bucket 목록 수집 | 마스터 bucket 리소스 발견의 시작점 | `object_storage_raw` | region + compartment | compartment 수에 비례 |
| `oci.object_storage.ObjectStorageClient` | `get_bucket` | bucket 상세 보강 | Console 상세의 access/versioning/tiering/KMS/size/count 정보를 재현하기 위해 필요 | `object_storage_raw` | Bucket 1개당 1회 | Bucket 수에 비례 |
| `oci.object_storage.ObjectStorageClient` | `list_retention_rules` | bucket retention rule 목록 수집 | 보존 정책은 삭제/컴플라이언스 영향 판단 핵심 정보 | `object_storage_enriched.retention_rules[]` | Bucket 1개당 1회 | Bucket 수에 비례 |

## P1 APIs

현재 collector에서 별도 P1 API는 사용하지 않는다.

## P0 Candidates

현재 없음.

## P1 Candidates

| SDK 클래스명 | 메소드명 | 호출 목적 | 후보 이유 | 예상 raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.object_storage.ObjectStorageClient` | `get_object_lifecycle_policy` | lifecycle policy 상세 수집 | lifecycle rule이 Console 검토 범위에 포함될 때 채택 | `object_storage_enriched.lifecycle_policy` | Bucket 1개당 1회 | Bucket 수에 비례 |
| `oci.object_storage.ObjectStorageClient` | `list_replication_policies` | bucket replication policy 수집 | DR/복제 구성 검토가 필요할 때 채택 | `object_storage_enriched.replication_policies[]` | Bucket 1개당 1회 | Bucket 수에 비례 |
| `oci.object_storage.ObjectStorageClient` | `list_preauthenticated_requests` | PAR 목록 수집 | 외부 접근/보안 검토 요구가 있을 때 채택 | `object_storage_enriched.preauthenticated_requests[]` | Bucket 1개당 1회 | Bucket 수에 비례 |

## Hold Candidates

| SDK 클래스명 | 메소드명 | 보류 이유 |
| --- | --- | --- |
| `oci.object_storage.ObjectStorageClient` | `list_objects` | object 단위 전체 listing은 호출량과 결과 크기가 매우 커서 bucket 인벤토리 기본 범위에서는 보류 |
| `oci.object_storage.ObjectStorageClient` | `get_object` | object data 다운로드 성격의 API이므로 인벤토리 수집에서 호출 금지 |
| `oci.object_storage.ObjectStorageClient` | 변경성 bucket/object 메소드 | 수집 리포트에서 생성/수정/삭제성 API 호출 금지 |

## Formatter Mapping

| Raw source | Worksheet | Row grain |
| --- | --- | --- |
| `object_storage_raw` | `Object_Storage_Buckets` | Bucket 1개당 1행 |
| `object_storage_enriched.retention_rules[]` | `Object_Storage_Retention_Rules` | Retention Rule 1개당 1행 |

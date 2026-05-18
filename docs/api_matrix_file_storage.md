# File Storage API Matrix

## Permission-Limited Collection

- 권한 부족(`401`, `403`, `404 NotAuthorizedOrNotFound`)은 공통 `permission_denied` 진단으로 남긴다.
- 권한 없는 `list_*` 범위는 WARN으로 기록하고 해당 범위만 스킵한다.
- 권한 없는 상세/관계 조회는 리소스 `_errors`에 기록하고 가능한 raw 수집을 계속한다.
- 권한 제한 profile 검증 시 로그, 웹 Health(`permission_limited`), Excel `99-Run_Diagnostics` 표현이 일치해야 한다.

## Scope
File Storage 수집은 OCI Console의 File System, Mount Target, Export Set, Export, Snapshot, Snapshot Policy, Replication 상세 화면에서 운영자가 확인하는 구성과 연결 정보를 raw-first로 보존하는 것을 목표로 한다.

## P0 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.identity.IdentityClient` | `list_availability_domains` | AD별 File Storage 리소스 조회 범위 확정 | File Storage list API가 AD 단위 조회를 요구 | loop context | region 1회 | region 수에 비례 |
| `oci.file_storage.FileStorageClient` | `list_file_systems` | File System 목록 수집 | 마스터 스토리지 리소스 발견의 시작점 | `file_storage_raw` | region + compartment + AD | compartment x AD 수에 비례 |
| `oci.file_storage.FileStorageClient` | `get_file_system` | File System 상세 보강 | Console 상세의 lifecycle/size/KMS 정보를 재현하기 위해 필요 | `file_storage_raw` | File System 1개당 1회 | File System 수에 비례 |
| `oci.file_storage.FileStorageClient` | `list_mount_targets` | Mount Target 목록 수집 | NFS 접근 endpoint와 네트워크 연결 확인에 필요 | `file_storage_raw` | region + compartment + AD | compartment x AD 수에 비례 |
| `oci.file_storage.FileStorageClient` | `get_mount_target` | Mount Target 상세 보강 | subnet/private IP/NSG 연결 추적에 필요 | `file_storage_raw` | Mount Target 1개당 1회 | Mount Target 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_subnet` | Mount Target subnet 상세 보강 | Console의 네트워크 맥락과 변경 영향 판단에 필요 | `networking_enriched.subnet_details` | 고유 subnet OCID당 캐시 조회 | 고유 subnet 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_network_security_group` | Mount Target NSG 상세 보강 | 보안 연결 맥락 추적에 필요 | `networking_enriched.nsg_details[]` | 고유 NSG OCID당 캐시 조회 | 고유 NSG 수에 비례 |
| `oci.file_storage.FileStorageClient` | `list_export_sets` | Export Set 목록 수집 | Mount Target와 Export 연결 구조 확인에 필요 | `file_storage_raw` | region + compartment + AD | compartment x AD 수에 비례 |
| `oci.file_storage.FileStorageClient` | `get_export_set` | Export Set 상세 보강 | quota/stat 제한과 mount target 연결 정보 확인에 필요 | `file_storage_raw` | Export Set 1개당 1회 | Export Set 수에 비례 |
| `oci.file_storage.FileStorageClient` | `list_exports` | Export 목록 수집 | File System export path와 export option 확인에 필요 | `file_storage_raw` | Export Set 1개당 1회 | Export Set 수에 비례 |
| `oci.file_storage.FileStorageClient` | `get_export` | Export 상세 보강 | export option/anonymous uid/gid 등 접근 정책 확인에 필요 | `file_storage_raw` | Export 1개당 1회 | Export 수에 비례 |
| `oci.file_storage.FileStorageClient` | `list_snapshots` | File System snapshot 목록 수집 | 복구 지점/보존 상태 확인에 필요 | `file_storage_raw` | File System 1개당 1회 | File System 수에 비례 |
| `oci.file_storage.FileStorageClient` | `get_snapshot` | Snapshot 상세 보강 | snapshot lifecycle/expiration 정보 확인에 필요 | `file_storage_raw` | Snapshot 1개당 1회 | Snapshot 수에 비례 |
| `oci.file_storage.FileStorageClient` | `list_filesystem_snapshot_policies` | Snapshot Policy 목록 수집 | 자동 snapshot 정책 확인에 필요 | `file_storage_raw` | region + compartment + AD | compartment x AD 수에 비례 |
| `oci.file_storage.FileStorageClient` | `get_filesystem_snapshot_policy` | Snapshot Policy 상세 보강 | schedules/prefix 등 정책 상세 확인에 필요 | `file_storage_raw` | Snapshot Policy 1개당 1회 | Snapshot Policy 수에 비례 |
| `oci.file_storage.FileStorageClient` | `list_replications` | Replication 목록 수집 | DR/복제 구성 확인에 필요 | `file_storage_raw` | region + compartment + AD | compartment x AD 수에 비례 |
| `oci.file_storage.FileStorageClient` | `get_replication` | Replication 상세 보강 | source/target/region 상태 확인에 필요 | `file_storage_raw` | Replication 1개당 1회 | Replication 수에 비례 |

## P1 APIs

현재 collector에서 별도 P1 API는 사용하지 않는다. File Storage의 주요 구성 리소스는 Console 재현성 기준으로 P0로 취급한다.

## P0 Candidates

현재 없음.

## P1 Candidates

| SDK 클래스명 | 메소드명 | 호출 목적 | 후보 이유 | 예상 raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.file_storage.FileStorageClient` | `list_outbound_connectors` | outbound connector 수집 | LDAP/Kerberos 등 고급 연계 구성이 리포트 요구에 포함될 때 채택 | `file_storage_enriched.outbound_connectors[]` | region + compartment | connector 수에 비례 |
| `oci.file_storage.FileStorageClient` | `get_outbound_connector` | outbound connector 상세 조회 | connector 목록만으로 운영 상세가 부족한 경우 채택 | `file_storage_enriched.outbound_connectors[].connector_detail` | connector 1개당 1회 | connector 수에 비례 |

## Hold Candidates

| SDK 클래스명 | 메소드명 | 보류 이유 |
| --- | --- | --- |
| `oci.file_storage.FileStorageClient` | 변경성 메소드 | 수집 리포트에서 생성/수정/삭제성 API 호출 금지 |

## Formatter Mapping

| Raw source | Worksheet | Row grain |
| --- | --- | --- |
| `file_storage_raw.resource_type == "file_system"` | `File_Systems` | File System 1개당 1행 |
| `file_storage_raw.resource_type == "mount_target"` | `Mount_Targets` | Mount Target 1개당 1행 |
| `file_storage_raw.resource_type == "export_set"` | `Export_Sets` | Export Set 1개당 1행 |
| `file_storage_raw.resource_type == "export"` | `Exports` | Export 1개당 1행 |
| `file_storage_raw.resource_type == "snapshot"` | `Snapshots` | Snapshot 1개당 1행 |
| `file_storage_raw.resource_type == "snapshot_policy"` | `Snapshot_Policies` | Snapshot Policy 1개당 1행 |
| `file_storage_raw.resource_type == "replication"` | `Replications` | Replication 1개당 1행 |

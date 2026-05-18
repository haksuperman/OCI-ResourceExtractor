# DBCS API Matrix

## Permission-Limited Collection

- 권한 부족(`401`, `403`, `404 NotAuthorizedOrNotFound`)은 공통 `permission_denied` 진단으로 남긴다.
- 권한 없는 `list_*` 범위는 WARN으로 기록하고 해당 범위만 스킵한다.
- 권한 없는 상세/관계 조회는 리소스 `_errors`에 기록하고 가능한 raw 수집을 계속한다.
- 권한 제한 profile 검증 시 로그, 웹 Health(`permission_limited`), Excel `99-Run_Diagnostics` 표현이 일치해야 한다.

## Scope
DBCS 수집은 OCI Console의 Oracle Base Database Service(DB System) 상세 화면에서 운영자가 확인하는 DB System 기본 구성, 네트워크 연결, DB Home, Database, Backup, Data Guard, PDB, DB Node 정보를 raw-first로 보존하는 것을 목표로 한다.

## P0 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.database.DatabaseClient` | `list_db_systems` | compartment 내 DB System 목록 수집 | 마스터 리소스 발견의 시작점 | `dbcs_raw` | region + compartment | compartment 수에 비례 |
| `oci.database.DatabaseClient` | `get_db_system` | DB System 상세 보강 | Console 상세의 shape/storage/network/edition 정보를 재현하기 위해 필요 | `dbcs_raw` | DB System 1개당 1회 | DB System 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_subnet` | DB System subnet/backup subnet 이름과 상세 보강 | Console의 네트워크 맥락과 변경 영향 판단에 필요 | `networking_enriched.subnet_details`, `networking_enriched.backup_subnet_details` | 고유 subnet OCID당 캐시 조회 | 고유 subnet 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_network_security_group` | 연결 NSG 상세 보강 | 보안 연결 맥락 추적에 필요 | `networking_enriched.nsg_details[]` | 고유 NSG OCID당 캐시 조회 | 고유 NSG 수에 비례 |
| `oci.database.DatabaseClient` | `list_db_homes` | DB Home 목록 수집 | DB version/DB Home 단위 구성 확인에 필요 | `dbcs_enriched.db_homes[]` | DB System 1개당 1회 | DB System 수에 비례 |
| `oci.database.DatabaseClient` | `get_db_home` | DB Home 상세 보강 | list 응답보다 Console 상세 재현성이 높음 | `dbcs_enriched.db_homes[]` | DB Home 1개당 1회 | DB Home 수에 비례 |
| `oci.database.DatabaseClient` | `list_databases` | DB Home 하위 Database 목록 수집 | 실제 Database 단위 운영 판단에 필요 | `dbcs_enriched.db_homes[].databases[]` | DB Home 1개당 1회 | DB Home 수에 비례 |
| `oci.database.DatabaseClient` | `get_database` | Database 상세 보강 | DB workload/charset/unique name 등 상세 확인에 필요 | `dbcs_enriched.db_homes[].databases[]` | Database 1개당 1회 | Database 수에 비례 |
| `oci.database.DatabaseClient` | `list_backups` | Database backup 목록 수집 | 백업 존재/상태/시간 확인은 운영 핵심 정보 | `dbcs_enriched.db_homes[].databases[].backups[]` | Database 1개당 1회 | Database 수에 비례 |
| `oci.database.DatabaseClient` | `list_data_guard_associations` | Data Guard 연결 수집 | DR 구성/peer/role 판단에 필요 | `dbcs_enriched.db_homes[].databases[].dataguard_associations[]` | Database 1개당 1회 | Database 수에 비례 |
| `oci.database.DatabaseClient` | `list_pluggable_databases` | PDB 목록 수집 | CDB/PDB 운영 구조 확인에 필요 | `dbcs_enriched.db_homes[].databases[].pluggable_databases[]` | Database 1개당 1회 | Database 수에 비례 |
| `oci.database.DatabaseClient` | `list_db_nodes` | DB Node 목록 수집 | RAC/노드/네트워크 영향 판단에 필요 | `dbcs_enriched.db_nodes[]` | DB System 1개당 1회 | DB System 수에 비례 |
| `oci.database.DatabaseClient` | `get_db_node` | DB Node 상세 보강 | VNIC/Private IP 연결 추적에 필요 | `dbcs_enriched.db_nodes[]` | DB Node 1개당 1회 | DB Node 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_vnic` | DB Node VNIC 상세 보강 | 노드별 private IP/네트워크 연결 확인에 필요 | `dbcs_enriched.db_nodes[].*_vnic_details` | VNIC OCID당 1회 | DB Node VNIC 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_private_ip` | DB Node private IP 상세 보강 | host/backup IP 추적에 필요 | `dbcs_enriched.db_nodes[].*_ip_details` | Private IP OCID당 1회 | DB Node IP 수에 비례 |

## P1 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.database.DatabaseClient` | `get_database` | Data Guard peer database 상세 보강 | Data Guard peer 표시명/상태 추적에 유용하나 peer가 없는 경우 호출 없음 | `dbcs_enriched.db_homes[].databases[].dataguard_associations[].peer_database_details` | Data Guard peer database 1개당 1회 | Data Guard association 수에 비례 |
| `oci.database.DatabaseClient` | `get_db_system` | Data Guard peer DB System 상세 보강 | peer system 영향 범위 확인에 유용하나 peer가 없는 경우 호출 없음 | `dbcs_enriched.db_homes[].databases[].dataguard_associations[].peer_db_system_details` | Data Guard peer DB System 1개당 1회 | Data Guard association 수에 비례 |

## P0 Candidates

현재 없음.

## P1 Candidates

| SDK 클래스명 | 메소드명 | 호출 목적 | 후보 이유 | 예상 raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.database.DatabaseClient` | `get_backup` | Backup 상세 조회 | list backup 응답이 Console 상세 필드를 충분히 제공하지 않는 경우 채택 | `dbcs_enriched.db_homes[].databases[].backups[].backup_detail` | Backup 1개당 1회 | Backup 수에 비례 |
| `oci.database.DatabaseClient` | `get_pluggable_database` | PDB 상세 조회 | list PDB 응답이 open mode/management detail을 충분히 제공하지 않는 경우 채택 | `dbcs_enriched.db_homes[].databases[].pluggable_databases[].pdb_detail` | PDB 1개당 1회 | PDB 수에 비례 |

## Hold Candidates

| SDK 클래스명 | 메소드명 | 보류 이유 |
| --- | --- | --- |
| `oci.database.DatabaseClient` | `list_db_system_patches` | 패치 후보/가용 패치는 상태성 정보가 강해 현재 구성 인벤토리 기본 범위에서는 보류 |
| `oci.database.DatabaseClient` | `list_db_home_patches` | 패치 상세 리포트 요구가 있을 때 별도 시트로 확장 |
| `oci.database.DatabaseClient` | `list_db_home_patch_history_entries` | 이력 데이터는 운영 감사 요구가 명확할 때 채택 |

## Formatter Mapping

| Raw source | Worksheet | Row grain |
| --- | --- | --- |
| `dbcs_raw` | `Dbcs` | DB System 1개당 1행 |
| `dbcs_enriched.db_homes[]` | `Dbcs_DB_Homes` | DB Home 1개당 1행 |
| `dbcs_enriched.db_homes[].databases[]` | `Dbcs_Databases` | Database 1개당 1행 |
| `dbcs_enriched.db_homes[].databases[].backups[]` | `Dbcs_Database_Backups` | Backup 1개당 1행 |
| `dbcs_enriched.db_homes[].databases[].dataguard_associations[]` | `Dbcs_Data_Guard` | Data Guard association 1개당 1행 |
| `dbcs_enriched.db_homes[].databases[].pluggable_databases[]` | `Dbcs_PDBs` | PDB 1개당 1행 |
| `dbcs_enriched.db_nodes[]` | `Dbcs_Nodes` | DB Node 1개당 1행 |

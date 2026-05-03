# ADB API Matrix

## Scope
Autonomous Database 수집은 OCI Console의 Autonomous Database 상세 화면에서 운영자가 확인하는 기본 구성, compute/storage, license, Data Guard 여부, private endpoint 네트워크, NSG, backup 정보를 raw-first로 보존하는 것을 목표로 한다.

## P0 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.database.DatabaseClient` | `list_autonomous_databases` | compartment 내 Autonomous Database 목록 수집 | 마스터 리소스 발견의 시작점 | `adb_raw` | region + compartment | compartment 수에 비례 |
| `oci.database.DatabaseClient` | `get_autonomous_database` | Autonomous Database 상세 보강 | Console 상세의 compute/storage/network/Data Guard/버전 정보를 재현하기 위해 필요 | `adb_raw` | ADB 1개당 1회 | ADB 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_subnet` | private endpoint subnet 상세 보강 | Console의 네트워크 맥락과 변경 영향 판단에 필요 | `networking_enriched.subnet_details` | 고유 subnet OCID당 캐시 조회 | 고유 subnet 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_network_security_group` | 연결 NSG 상세 보강 | 보안 연결 맥락 추적에 필요 | `networking_enriched.nsg_details[]` | 고유 NSG OCID당 캐시 조회 | 고유 NSG 수에 비례 |
| `oci.database.DatabaseClient` | `list_autonomous_database_backups` | Autonomous Database backup 목록 수집 | 백업 존재/상태/시점은 운영 복구 판단 핵심 정보 | `backup_enriched.backups[]` | ADB 1개당 1회 | ADB 수에 비례 |

## P1 APIs

현재 collector에서 별도 P1 API는 사용하지 않는다.

## P0 Candidates

현재 없음.

## P1 Candidates

| SDK 클래스명 | 메소드명 | 호출 목적 | 후보 이유 | 예상 raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.database.DatabaseClient` | `get_autonomous_database_backup` | backup 상세 조회 | list backup 응답이 복구/보존 관련 상세 필드를 충분히 제공하지 않는 경우 채택 | `backup_enriched.backups[].backup_detail` | Backup 1개당 1회 | Backup 수에 비례 |
| `oci.database.DatabaseClient` | `list_autonomous_database_clones` | clone 관계 수집 | Console/운영 요구에서 clone lineage 추적이 필요해질 때 채택 | `adb_enriched.clones[]` | ADB 1개당 1회 | ADB 수에 비례 |

## Hold Candidates

| SDK 클래스명 | 메소드명 | 보류 이유 |
| --- | --- | --- |
| `oci.database.DatabaseClient` | `generate_autonomous_database_wallet` | credential/wallet 생성 성격의 API이므로 인벤토리 리포트에서 호출 금지 |
| `oci.database.DatabaseClient` | `create_autonomous_database_backup` | 변경성 API이므로 수집 대상 아님 |

## Formatter Mapping

| Raw source | Worksheet | Row grain |
| --- | --- | --- |
| `adb_raw` | `Adb` | Autonomous Database 1개당 1행 |
| `backup_enriched.backups[]` | `Adb_Backups` | Backup 1개당 1행 |

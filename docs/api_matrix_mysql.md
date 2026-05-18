# MySQL HeatWave API Matrix

## Permission-Limited Collection

- 권한 부족(`401`, `403`, `404 NotAuthorizedOrNotFound`)은 공통 `permission_denied` 진단으로 남긴다.
- 권한 없는 `list_*` 범위는 WARN으로 기록하고 해당 범위만 스킵한다.
- 권한 없는 상세/관계 조회는 리소스 `_errors`에 기록하고 가능한 raw 수집을 계속한다.
- 권한 제한 profile 검증 시 로그, 웹 Health(`permission_limited`), Excel `99-Run_Diagnostics` 표현이 일치해야 한다.

## Scope
MySQL HeatWave 수집은 OCI Console의 DB System 상세 화면에서 운영자가 확인하는 DB System 기본 구성, endpoint/read endpoint, HA/HeatWave 여부, subnet, backup policy, storage, deletion policy, backup 목록 정보를 raw-first로 보존하는 것을 목표로 한다.

## P0 APIs

| SDK 클래스명 | 메소드명 | 호출 목적 | 분류 이유 | raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.mysql.DbSystemClient` | `list_db_systems` | compartment 내 MySQL DB System 목록 수집 | 마스터 리소스 발견의 시작점 | `mysql_raw` | region + compartment | compartment 수에 비례 |
| `oci.mysql.DbSystemClient` | `get_db_system` | DB System 상세 보강 | Console 상세의 endpoint/storage/backup policy/HA/HeatWave 정보를 재현하기 위해 필요 | `mysql_raw` | DB System 1개당 1회 | DB System 수에 비례 |
| `oci.core.VirtualNetworkClient` | `get_subnet` | 연결 subnet 상세 보강 | Console의 네트워크 맥락과 변경 영향 판단에 필요 | `networking_enriched.subnet_details` | 고유 subnet OCID당 캐시 조회 | 고유 subnet 수에 비례 |
| `oci.mysql.DbBackupsClient` | `list_backups` | compartment 내 backup 목록 수집 후 DB System별 연결 | 백업 존재/상태/시점은 운영 복구 판단 핵심 정보 | `backup_enriched.backups[]` | region + compartment | compartment 수와 backup 수에 비례 |

## P1 APIs

현재 collector에서 별도 P1 API는 사용하지 않는다.

## P0 Candidates

현재 없음.

## P1 Candidates

| SDK 클래스명 | 메소드명 | 호출 목적 | 후보 이유 | 예상 raw 저장 위치 | 호출 단위 | 호출량 영향 |
| --- | --- | --- | --- | --- | --- | --- |
| `oci.mysql.DbBackupsClient` | `get_backup` | backup 상세 조회 | list backup 응답이 복구/보존 관련 상세 필드를 충분히 제공하지 않는 경우 채택 | `backup_enriched.backups[].backup_detail` | Backup 1개당 1회 | Backup 수에 비례 |
| `oci.mysql.ChannelsClient` | `list_channels` | replication channel 수집 | Console 운영 요구에서 replication/channel 상태 확인이 필요해질 때 채택 | `mysql_enriched.channels[]` | region + compartment 또는 DB System 기준 | channel 수에 비례 |
| `oci.mysql.ConfigurationsClient` | `get_configuration` | configuration 상세 보강 | DB System configuration id가 있고 파라미터 상세 추적이 필요할 때 채택 | `mysql_enriched.configuration_detail` | DB System 1개당 캐시 조회 | 고유 configuration 수에 비례 |

## Hold Candidates

| SDK 클래스명 | 메소드명 | 보류 이유 |
| --- | --- | --- |
| `oci.mysql.WorkRequestsClient` | `list_work_requests` | 작업 이력/상태성 데이터라 구성 인벤토리 기본 범위에서는 보류 |
| `oci.mysql.MysqlaasClient` | 변경성 메소드 | 수집 리포트에서 변경성 API 호출 금지 |

## Formatter Mapping

| Raw source | Worksheet | Row grain |
| --- | --- | --- |
| `mysql_raw` | `Mysql` | MySQL DB System 1개당 1행 |
| `backup_enriched.backups[]` | `Mysql_Backups` | Backup 1개당 1행 |

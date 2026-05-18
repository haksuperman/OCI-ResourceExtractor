# Block Storage API Matrix

## Permission-Limited Collection

- 권한 부족(`401`, `403`, `404 NotAuthorizedOrNotFound`)은 공통 `permission_denied` 진단으로 남긴다.
- 권한 없는 `list_*` 범위는 WARN으로 기록하고 해당 범위만 스킵한다.
- 권한 없는 상세/관계 조회는 리소스 `_errors`에 기록하고 가능한 raw 수집을 계속한다.
- 권한 제한 profile 검증 시 로그, 웹 Health(`permission_limited`), Excel `99-Run_Diagnostics` 표현이 일치해야 한다.

이 문서는 `collectors/block_storage.py`가 현재 실제로 호출하는 OCI SDK 메소드와 향후 확장 후보를 정리한 서비스별 API 문서다.

## 개요

- collector: `collectors/block_storage.py`
- formatter: `formatters/formatter_block_storage.py`
- raw path: `raw_data/<profile>/block_storage_<profile>.json`
- raw top-level containers:
  - `block_storage_raw`
  - `block_storage_enriched`
  - `_errors`

## Console 기준 리포트 구조

- `Block_Volumes`: block volume 마스터 시트. 용량, 성능, 암호화, 백업 정책, attachment raw 목록을 표시한다.
- `Boot_Volumes`: boot volume 마스터 시트. 용량, 암호화, 백업 정책, attachment raw 목록을 표시한다.
- `Block_Volume_Attachments`: block volume attachment를 1행 1attachment 구조로 표시한다.
- `Boot_Volume_Attachments`: boot volume attachment를 1행 1attachment 구조로 표시한다.
- `Block_Volume_Backups`: block volume backup 목록을 표시한다.
- `Boot_Volume_Backups`: boot volume backup 목록을 표시한다.
- `Volume_Groups`: volume group 목록을 표시한다.
- `Volume_Group_Backups`: volume group backup 목록을 표시한다.

## 현재 호출 중인 P0 메소드

- `oci.identity.IdentityClient.list_availability_domains`
  - 호출 목적: AD별 block/boot volume 및 backup 조회 범위 확보
  - 분류 이유: Block Storage 리소스는 AD 단위 조회 API가 많아 전체 수집의 기준 정보다
  - raw 저장 위치: 직접 저장하지 않고 AD 루프 기준으로 사용
  - 호출 단위: `region + tenancy`
  - 호출량 영향: region 수에 비례

- `oci.core.BlockstorageClient.list_volumes`
  - 호출 목적: block volume 목록 조회
  - 분류 이유: block volume 수집의 기준 리소스 목록이다
  - raw 저장 위치: `block_storage_raw`
  - 호출 단위: `region + compartment + availability_domain`
  - 호출량 영향: compartment x AD 수에 비례

- `oci.core.BlockstorageClient.get_volume`
  - 호출 목적: block volume 상세 정보 조회
  - 분류 이유: Console 상세 화면 수준의 용량/성능/암호화/상태 정보를 보존하기 위해 필요하다
  - raw 저장 위치: `block_storage_raw`
  - 호출 단위: `volume`
  - 호출량 영향: block volume 수에 비례

- `oci.core.BlockstorageClient.list_boot_volumes`
  - 호출 목적: boot volume 목록 조회
  - 분류 이유: boot volume 수집의 기준 리소스 목록이다
  - raw 저장 위치: `block_storage_raw`
  - 호출 단위: `region + compartment + availability_domain`
  - 호출량 영향: compartment x AD 수에 비례

- `oci.core.BlockstorageClient.get_boot_volume`
  - 호출 목적: boot volume 상세 정보 조회
  - 분류 이유: Console 상세 화면 수준의 용량/암호화/상태 정보를 보존하기 위해 필요하다
  - raw 저장 위치: `block_storage_raw`
  - 호출 단위: `boot_volume`
  - 호출량 영향: boot volume 수에 비례

- `oci.core.ComputeClient.list_volume_attachments`
  - 호출 목적: block volume과 compute instance 연결 정보 조회
  - 분류 이유: volume이 어떤 instance에 어떤 attachment type으로 연결됐는지 운영 판단에 필수다
  - raw 저장 위치: `block_storage_enriched.volume_attachments`
  - 호출 단위: `region + compartment`
  - 호출량 영향: compartment 수에 비례

- `oci.core.ComputeClient.list_boot_volume_attachments`
  - 호출 목적: boot volume과 compute instance 연결 정보 조회
  - 분류 이유: boot volume 소유 instance 및 연결 상태 판단에 필수다
  - raw 저장 위치: `block_storage_enriched.boot_volume_attachments`
  - 호출 단위: `region + compartment + availability_domain`
  - 호출량 영향: compartment x AD 수에 비례

## 현재 호출 중인 P1 메소드

- `oci.core.BlockstorageClient.list_volume_backups`
  - 호출 목적: block volume backup 목록 조회
  - 분류 이유: 백업 존재 여부와 백업 상태 확인에 필요하다
  - raw 저장 위치: `block_storage_raw`
  - 호출 단위: `region + compartment + availability_domain`
  - 호출량 영향: compartment x AD 수에 비례

- `oci.core.BlockstorageClient.list_boot_volume_backups`
  - 호출 목적: boot volume backup 목록 조회
  - 분류 이유: boot volume 백업 존재 여부와 백업 상태 확인에 필요하다
  - raw 저장 위치: `block_storage_raw`
  - 호출 단위: `region + compartment + availability_domain`
  - 호출량 영향: compartment x AD 수에 비례

- `oci.core.BlockstorageClient.list_volume_groups`
  - 호출 목적: volume group 목록 조회
  - 분류 이유: group 기반 백업/복제/운영 단위 판단에 필요하다
  - raw 저장 위치: `block_storage_raw`
  - 호출 단위: `region + compartment + availability_domain`
  - 호출량 영향: compartment x AD 수에 비례

- `oci.core.BlockstorageClient.get_volume_group`
  - 호출 목적: volume group 상세 정보 조회
  - 분류 이유: 포함 volume과 source detail 등 Console 상세 정보 보존에 필요하다
  - raw 저장 위치: `block_storage_raw`
  - 호출 단위: `volume_group`
  - 호출량 영향: volume group 수에 비례

- `oci.core.BlockstorageClient.list_volume_group_backups`
  - 호출 목적: volume group backup 목록 조회
  - 분류 이유: group backup 운영 상태 확인에 필요하다
  - raw 저장 위치: `block_storage_raw`
  - 호출 단위: `region + compartment`
  - 호출량 영향: compartment 수에 비례

- `oci.core.BlockstorageClient.get_volume_backup_policy_asset_assignment`
  - 호출 목적: volume/boot volume 백업 정책 할당 조회
  - 분류 이유: Console의 backup policy 연결 여부 판단에 필요하다
  - raw 저장 위치: `block_storage_enriched.backup_policy_assignment`
  - 호출 단위: `volume` 또는 `boot_volume`
  - 호출량 영향: volume + boot volume 수에 비례

- `oci.core.BlockstorageClient.get_volume_backup_policy`
  - 호출 목적: 백업 정책 상세 조회
  - 분류 이유: 할당된 정책 이름/스케줄/대상 리전 확인에 필요하다
  - raw 저장 위치: `block_storage_enriched.backup_policy_*`
  - 호출 단위: `policy_id` 기준 캐시
  - 호출량 영향: 참조 policy 수에 비례

## 미수집 후보 - P0

- `oci.core.ComputeClient.get_volume_attachment`
  - 왜 후보인가: 현재 attachment는 list 응답을 보존한다. Console attachment 상세와 list 응답 간 차이가 확인되면 채택한다
  - 운영 질문: "Block volume attachment의 상세 연결 속성이 충분히 보존되는가?"
  - 저장 예상 위치: `block_storage_enriched.volume_attachments[*].attachment_detail`
  - 호출량 영향: block volume attachment 수에 비례

- `oci.core.ComputeClient.get_boot_volume_attachment`
  - 왜 후보인가: 현재 boot attachment는 list 응답을 보존한다. Console attachment 상세와 list 응답 간 차이가 확인되면 채택한다
  - 운영 질문: "Boot volume attachment의 상세 연결 속성이 충분히 보존되는가?"
  - 저장 예상 위치: `block_storage_enriched.boot_volume_attachments[*].attachment_detail`
  - 호출량 영향: boot volume attachment 수에 비례

## 미수집 후보 - P1

- `oci.core.BlockstorageClient.get_volume_backup`
  - 왜 후보인가: 현재 volume backup은 list 응답을 보존한다. 상세 화면과 필드 차이가 확인되면 채택한다
  - 운영 질문: "Block volume backup 상세 정보가 Console과 일치하는가?"
  - 저장 예상 위치: `block_storage_raw.volume_backup_detail`
  - 호출량 영향: volume backup 수에 비례

- `oci.core.BlockstorageClient.get_boot_volume_backup`
  - 왜 후보인가: 현재 boot volume backup은 list 응답을 보존한다. 상세 화면과 필드 차이가 확인되면 채택한다
  - 운영 질문: "Boot volume backup 상세 정보가 Console과 일치하는가?"
  - 저장 예상 위치: `block_storage_raw.boot_volume_backup_detail`
  - 호출량 영향: boot volume backup 수에 비례

- `oci.core.BlockstorageClient.get_volume_group_backup`
  - 왜 후보인가: 현재 volume group backup은 list 응답을 보존한다. 상세 화면과 필드 차이가 확인되면 채택한다
  - 운영 질문: "Volume group backup 상세 정보가 Console과 일치하는가?"
  - 저장 예상 위치: `block_storage_raw.volume_group_backup_detail`
  - 호출량 영향: volume group backup 수에 비례

## 미수집 후보 - 보류

- `oci.core.BlockstorageClient.list_volume_backup_policies`
  - 보류 이유: 전체 정책 카탈로그 성격이 강하다. 현재는 실제 volume/boot volume에 할당된 정책만 추적한다

- `oci.core.BlockstorageClient.list_volume_replicas`
  - 보류 이유: 재해복구/복제 관점에서는 가치가 있으나 기본 inventory 확장 범위에서 별도 검토가 필요하다

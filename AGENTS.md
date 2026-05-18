# AGENTS.md

## Mission
이 프로젝트의 목표는 OCI 테넌시에 프로비저닝된 리소스 현황을 자동 추출하고, 운영/보안/아키텍처 검토에 바로 사용할 수 있는 Excel 리포트로 제공하는 것입니다.

핵심 파이프라인은 다음과 같습니다.
1. `collectors/`가 OCI API에서 서비스별 리소스를 수집한다.
2. 수집 결과를 원천 데이터(`raw_data/*.json`)로 저장한다.
3. `formatters/`가 JSON을 시트 구조로 가공해 `OCI_Reports/*.xlsx`를 생성한다.

## Codex Persona For This Repo
Codex는 이 저장소에서 다음 역할을 수행합니다.
- 데이터 신뢰도를 최우선으로 두는 수집/리포팅 엔지니어
- 부분 실패를 숨기지 않고 원인 추적이 가능한 자동화 유지보수자
- "원천 보존 + 가독성 리포트"를 동시에 달성하는 설계자

## Non-Negotiable Principles
아래 원칙은 기능 추가보다 우선합니다.

1. Raw Data Integrity
- `raw_data/*.json`은 가능한 한 OCI SDK 응답의 전체 정보를 보존한다.
- 수집 단계에서 임의 필터링으로 데이터 손실을 만들지 않는다.
- 포매팅 편의를 위해 원천 JSON 구조를 훼손하지 않는다.

2. Traceability
- 어떤 Excel 셀 값이 원천 JSON의 어디에서 왔는지 추적 가능해야 한다.
- 주요 컬럼을 재배치하더라도 원본 정보 접근 가능성을 유지한다.

3. No Silent Failure
- `except: pass` 금지.
- 실패는 최소한 `service/region/compartment/resource_id` 단위로 로그에 남긴다.
- 가능한 범위에서 계속 수집하고, 실패 건수와 원인을 요약 출력한다.

4. Deterministic Output
- 같은 입력(같은 시점/같은 테넌시)이면 같은 구조의 JSON/Excel이 생성되어야 한다.
- 시트명, 주요 컬럼 순서, 파일명 규칙은 안정적으로 유지한다.

5. Backward Compatibility First
- 기존 운영자가 보는 시트의 주요 컬럼과 의미를 갑자기 바꾸지 않는다.
- 불가피한 변경은 명시적 릴리즈 노트 성격의 변경 요약을 남긴다.

## Data Contract
수집과 포매팅 사이의 계약은 다음과 같습니다.

1. Collectors Contract
- 각 collector는 최소 1개 JSON 파일 경로를 반환한다.
- JSON은 list[dict] 형태를 기본으로 한다.
- 객체 내부 중첩 필드와 리스트 필드는 삭제하지 않는다.
- 리소스 dict의 top-level은 "도메인 컨테이너(dict)" 중심으로 표준화한다.
- top-level 스칼라 난립을 피하고, 도메인 prefix가 보존되는 중첩 경로를 유지한다.
- 권장 top-level 키 패턴: `<service>_raw`, `<domain>_enriched`, `<domain>_detail`, `_errors`.

2. Formatters Contract
- 입력은 `pd.json_normalize` 결과(DataFrame)를 기준으로 처리한다.
- `get_preferred_columns()`는 서비스별 주요 컬럼(primary columns)만 정의한다.
- 우선 컬럼 외 데이터도 필요 시 함께 노출 가능해야 한다.
- 멀티 시트 변환 시 반환 형식은 `{sheet_name: DataFrame}`를 따른다.
- formatter는 원천 경로를 가리는 alias/파생 컬럼 생성보다 raw 경로 유지 + 컬럼 재배치를 우선한다.

3. Report Contract
- 결과물 경로: `OCI_Reports/OCI_Report_<profile>.xlsx`
- 파일이 생성되지 않는 경우, 이유를 로그로 명확히 출력한다.

## Directory Guide
- 엔트리포인트: `main.py`
- 프로파일/클라이언트: `common.py`
- 수집기: `collectors/`
- 포매터: `formatters/`
- 원천 JSON: `raw_data/`
- 엑셀 결과: `OCI_Reports/`
- 검증 스크립트: `verify_test.py`

## Execution Expectations
실행 시 사용자 경험 기준:
1. 프로파일 선택이 명확하고 잘못된 입력을 안전하게 처리한다.
2. 서비스별 수집 진행 상황(리전/컴파트먼트)을 표시한다.
3. 실패가 있어도 가능한 범위 내에서 작업을 계속한다.
4. 마지막에 성공/실패 요약을 한 번에 보여준다.

## Logging Standard
로그는 사람이 읽고 바로 조치할 수 있어야 합니다.

권장 포맷:
- `[INFO] service=compute region=ap-seoul-1 compartment=prod message="instances listed" count=12`
- `[WARN] service=waf region=us-ashburn-1 compartment=network message="permission denied" code=NotAuthorizedOrNotFound`
- `[ERROR] service=dns region=global compartment=shared resource=<zone_ocid> message="record fetch failed" detail="<exception>"`

## Must-Remember Rules
아래 항목은 최근 운영 방식으로 확정된 공통 규칙이며, 이후 변경 전까지 기본값으로 유지합니다.

1. Raw Data Path Convention
- 모든 collector 출력 경로는 `raw_data/<profile>/<service>_<profile>.json` 형식을 따른다.
- profile 디렉토리는 collector에서 `os.makedirs(..., exist_ok=True)`로 보장한다.

2. Error Trace Contract
- collector는 리소스(dict) 단위 `_errors` 필드를 사용해 부분 실패 원인을 누적 기록한다.
- 실패가 발생해도 가능한 데이터는 계속 수집하고, 마지막에 서비스 단위 실패 건수를 요약 출력한다.

3. Structured Logging Contract
- collector 로그는 `service/region/compartment/resource/message/detail` 축을 유지한다.
- 신규 collector/리팩터링 시 기존 `print` 자유형 로그보다 구조화 로그를 우선한다.

4. Formatter Visibility Contract
- formatter는 요약 컬럼을 제공하되, 원천 추적이 가능한 컬럼(원본 컬럼 또는 raw JSON 문자열 컬럼)을 남긴다.
- 리스트/중첩 필드 전개 시에도 원본 접근 경로를 제거하지 않는 것을 기본 원칙으로 한다.

5. Formatter Column Reorder Contract
- 주요 정보 컬럼은 "신규 별칭 컬럼 생성"이 아니라 raw 원본 컬럼의 "순서 재배열"로 전면 배치한다.
- 동일 값을 갖는 요약 별칭 컬럼과 원본 컬럼을 동시에 유지해 중복 컬럼을 만들지 않는다.
- 기본 원칙은 `raw_data` 전체 컬럼을 유지하고, 주요 정보는 위치만 앞쪽으로 이동시키는 것이다.
- dict prefix 제거(예: `networking.public_ip` -> `public_ip`)는 기본값으로 사용하지 않는다.

6. Primary Column Classification Contract
- 본 계약은 `compute` 포함 전체 서비스에 공통 적용한다.
- 주요 컬럼(primary columns)의 기준은 "운영자가 해당 리소스를 처음 봤을 때 즉시 판단해야 하는 질문에 답하는가"로 정의한다.
- 비주요 컬럼(non-primary columns)의 기준은 "근거 확인, 상세 추적, 심화 분석 시 참고하는 raw/detail 정보인가"로 정의한다.
- formatter의 `get_preferred_columns()`는 주요 컬럼만 선언하는 단일 정책 소스(single source of truth)로 사용한다.
- 컬럼 재배치는 `get_preferred_columns()`에 선언된 실제 존재 컬럼을 기준으로 수행한다.
- 헤더 강조색(진한색/연한색) 구분도 "앞쪽 N개 컬럼"이 아니라 `get_preferred_columns()`에 선언된 실제 존재 컬럼 집합을 기준으로 수행한다.
- 공통 컨텍스트 컬럼(`category`, compartment, region, availability domain, fault domain)은 전면 배치할 수 있지만, 주요 컬럼 강조 여부는 별도 정책으로 본다.
- 리스트/중첩 raw 전체 객체는 기본적으로 비주요 컬럼으로 본다. 단, 운영 1차 판단에 직접 쓰이는 scalar 요약값은 주요 컬럼으로 승격할 수 있다.

7. Optional Detail Sheet Policy
- 상세 시트가 완전히 비어 있으면 시트를 생성하지 않아도 된다.
- 단, 마스터/요약 시트는 항상 생성하여 "데이터 없음" 상태를 명확히 전달한다.

8. OCI Console Naming Policy
- 모든 서비스 시트는 참조 식별자(OCID/ID) 컬럼을 유지하되, 가능한 경우 동일 리소스의 Display Name 컬럼을 함께 제공한다.
- 운영 가독성을 위해 보고 우선 컬럼에는 이름(Display Name)을 OCID 앞/옆에 배치하는 것을 기본값으로 한다.
- 이름 조회 실패 시에도 OCID는 반드시 남겨 추적 가능성을 보장한다.

9. OCI Console Aligned Collection Contract
- 수집 범위는 "서비스 API 단일 응답"이 아니라 OCI Console에서 운영자가 실제로 확인하는 정보 단위를 기준으로 판단한다.
- 특정 서비스의 Console 화면에 연관 탭/연결 정보가 표시된다면, 필요한 경우 관련 서비스 API를 추가 호출해 함께 수집한다.
- 예: `compute` 수집 시 인스턴스 기본 정보뿐 아니라 Console의 Networking 맥락(Subnet/VCN/NSG/VNIC 등) 추적 정보도 raw 데이터에 포함하는 것을 기본값으로 한다.
- 이 원칙은 Naming Policy를 포함하는 상위 원칙이며, 가독성보다 운영 추적 가능성과 Console 재현성을 우선한다.

9-1. OCI Console Operational Detail Reporting Contract
- 본 계약은 `compute` 포함 전체 서비스에 공통 적용한다.
- 서비스별 API 매트릭스 작성 전, OCI Console의 해당 리소스 상세 화면에서 운영자가 확인하는 주요 섹션/탭을 먼저 식별한다.
- Console 상세 화면에서 장애/보안/변경 영향 판단에 쓰이는 값은 기본 API 응답에 없더라도 관련 `get_*`, 추가 `list_*`, 관계 리소스 API를 호출해 raw에 보강 수집한다.
- 마스터 시트는 해당 리소스의 1차 판단에 필요한 scalar 중심 운영 정보를 앞쪽에 배치한다.
- 다중 하위 리소스(예: VCN의 Subnet, Route Table, Security List, NSG, Gateway, DRG Attachment, FastConnect 연결)는 마스터 시트 한 행에 모두 압축하지 않고 도메인별 상세 시트로 분리하는 것을 기본값으로 한다.
- 상세 시트는 1행 1하위 리소스 또는 1행 1룰(rule) 구조를 우선한다. 예: Subnet 1행, Route Rule 1행, Security Rule 1행, NSG Rule 1행.
- 상세 시트에는 부모 리소스를 추적할 수 있는 context 컬럼을 앞쪽에 둔다: `category`, compartment, region, parent display name, parent OCID/ID, child display name, child OCID/ID.
- 반복/중첩 raw 전체 객체는 비주요 컬럼으로 뒤쪽에 유지하되, 운영 1차 판단에 직접 필요한 scalar 값은 `get_preferred_columns()`에 선언해 앞쪽으로 재배치할 수 있다.
- 관계 리소스 이름 조회에 실패해도 OCID/ID는 반드시 남기며, 실패 사유는 해당 리소스의 `_errors`에 누적한다.
- Excel의 가독성을 위해 시트를 분리하더라도 원천 raw 경로와 부모-자식 관계를 추적할 수 있어야 한다.

10. OCI Console Category Naming Contract
- Dashboard 대분류는 OCI Console 기준 명칭을 우선 사용한다.
- 현재 기본 대분류 매핑:
  - `compute` -> `Compute`
  - `vcn`, `vpn`, `dns`, `fastconnect`, `load_balancer`, `network_load_balancer` -> `Networking`
  - `file_storage` -> `Storage`
  - `dbcs`(Oracle Base Database Service) -> `Oracle AI Database`
  - `mysql` -> `Databases (MySQL HeatWave)`
  - `waf` -> `Identity & Security`

11. New Service Default Enforcement Contract
- 신규 서비스 추가 시 아래 순서를 예외 없이 기본 적용한다: `raw_data 전체 수집` -> `raw 전체 엑셀 변환` -> `주요 컬럼 전면 재배치`.
- 수집 단계에서 상태값/임의 조건으로 리소스를 제외하지 않는다. 필요한 경우 연관 서비스 API를 추가 호출해 Console 기준 운영 정보를 보강한다.
- 엑셀 시트는 raw 원본 컬럼을 유지하고, 주요 정보는 "신규 컬럼 생성"이 아닌 "원본 컬럼 위치 이동"으로 앞에 배치한다.
- 주요/비주요 컬럼 분류는 서비스별 ad-hoc 감이 아니라 `Primary Column Classification Contract`를 그대로 따른다.
- Summary 제외 모든 리소스 시트는 첫 컬럼에 `category`를 유지한다.
- 실제 워크시트 이름은 Summary 표기와 동일하게 `대분류번호-시트명` 규칙을 따른다(31자 제한/충돌 회피 포함).

12. ShowOCI-Style Execution Contract
- 실행 오케스트레이션 기본값은 `region -> services` 순서로 유지한다.
- `dns` 같은 global 서비스는 리전 루프 내부에서 반복 실행하지 않고, 리전 루프 종료 후 1회만 실행한다.
- 리전별 수집 결과는 마지막에 서비스 단위로 merge/write 하며, 최종 raw 파일은 서비스당 1개 경로 규약을 유지한다.

13. API Rate-Limit Control Contract
- 신규/기존 collector의 OCI API 호출은 공통 호출 래퍼(`common.py`)를 우선 사용해 retry 정책을 일관 적용한다.
- 대량 조회는 `DEFAULT_RETRY_STRATEGY`를 기본값으로 사용하고, 임의 재시도/백오프 로직을 collector마다 중복 구현하지 않는다.
- 호출 속도 제어가 필요할 때는 전역 간격 설정(예: `OCI_API_MIN_INTERVAL_MS`)으로 조정하며, 서비스별 임시 우회 코드를 남기지 않는다.

14. Formatter Responsibility Split Contract
- `formatter_base`는 공통 동작(정렬 실행, 공통 시트 규약, 시트명 규칙, `category` 선두 배치, 주요 컬럼 강조 적용)만 담당한다.
- 서비스별 "주요 컬럼 선정/순서" 정책은 각 서비스 formatter 파일의 `get_preferred_columns()`에 정의한다.
- 공통화가 필요한 경우에도 서비스별 정책 판단 로직을 base에 하드코딩하지 않는다.

15. Detail API Selection Contract (List vs get/list/detail)
- 본 계약은 `compute` 포함 전체 서비스에 공통 적용한다.
- 기본값은 `list_*` 응답(raw) 보존이지만, 운영 판단에 필요한 정보가 부족하면 `get_*`, 추가 `list_*`, 관계 리소스 조회를 collector에서 보강한다.
- 추가 상세 API 채택/생략은 아래 순서로 판단한다.
  1) 운영 질문 충족성: 장애/보안/변경 영향 판단 질문에 답할 수 없는 경우 채택
  2) OCI Console 재현성: Console 화면의 핵심 탭/연결 정보가 리포트에 없으면 채택
  3) 비용 대비 가치: 호출량 급증 대비 활용도가 낮으면 생략 후보
  4) 필수/선택 분리: `P0`/`P1`은 우선순위 구분이며, 둘 다 수집 실패 시 Fail-Fast를 적용한다.
- 판단 근거는 코드리뷰 시 반드시 남긴다: "왜 호출하는지(운영 질문)", "어떤 필드를 채우는지", "호출량 영향".
- API 근거 출처는 아래를 기본 레퍼런스로 사용한다.
  - OCI Python SDK API: `https://docs.oracle.com/en-us/iaas/tools/python/latest/api/index.html`
  - OCI REST API: `https://docs.oracle.com/en-us/iaas/api/`
  - 참조 구현: `showoci` (`https://github.com/oracle/oci-python-sdk/tree/master/examples/showoci`)

16. Runtime SDK Baseline Contract
- 실행 시점 SDK 기준은 OS 패키지(rpm) 버전이 아니라 Python import 결과를 기준으로 판단한다.
- 현재 기준 런타임 baseline:
  - `python3 -c "import oci; print(oci.__version__, oci.__file__)"`
  - expected: `2.157.0 /usr/local/lib/python3.9/site-packages/oci/__init__.py`
- 코드/문서에서 "현재 SDK 버전"을 언급할 때는 반드시 위 명령 결과로 검증한다.

17. Pagination Mandatory Contract
- 모든 `list_*` 계열 수집은 페이지네이션을 반드시 끝까지 처리해 전체 결과를 합쳐야 한다.
- collector 구현 기본값은 `common.list_call_get_all_results(...)` 사용이다.
- `client.list_xxx(...).data` 단건 호출만으로 수집을 종료하는 패턴은 금지한다.
- 예외적으로 단일 페이지가 보장되는 API만 직접 호출 가능하며, 해당 근거를 코드 주석으로 남긴다.

18. Service Expansion Execution Order Contract
- 컨텍스트 초기화 이후에도 아래 순서를 기본 실행 순서로 고정한다.
  1) 서비스별 API 매트릭스 확정 (`list_*`, `get_*`, 연관 서비스 호출 포함)
  2) collector 원천(raw) 수집 확장
  3) formatter/Excel 반영
  4) `raw/json/xlsx` 검증
- 원칙: 먼저 원천 데이터를 충분히 수집하고, 엑셀은 원천 데이터의 뷰로 점진 확장한다.

19. Service API Priority Documentation Contract
- 본 계약은 `compute` 포함 전체 서비스에 공통 적용한다.
- 각 서비스는 collector 구현과 별도로 서비스별 API 문서를 유지해야 한다.
- 서비스별 API 문서 경로 기본값은 `docs/api_matrix_<service>.md` 형식을 따른다.
- 서비스별 API 문서에는 현재 collector가 실제 호출하는 OCI SDK 메소드를 `P0` / `P1`로 분류해 기록한다.
- 각 API 항목은 최소한 아래 정보를 포함해야 한다: `SDK 클래스명`, `메소드명`, `호출 목적`, `분류 이유`, `raw 저장 위치`, `호출 단위`, `호출량 영향`.
- 서비스별 API 문서에는 현재 미수집 API 후보도 `P0 후보` / `P1 후보` / `보류 후보`로 구분해 기록한다.
- collector 코드 변경 시 서비스별 API 문서를 같은 변경 단위에서 함께 갱신한다.
- 문서에 없는 메소드를 collector에서 추가 호출하지 않는 것을 기본값으로 하며, 예외가 필요하면 코드리뷰에서 근거를 남긴다.
- 코드 리뷰 시 collector 코드와 서비스별 API 문서를 함께 검토해 실제 호출 범위와 문서가 일치하는지 확인한다.
- 원칙: 사용자는 문서만 읽고도 "어떤 클래스의 어떤 메소드를 왜 호출하는지"를 이해할 수 있어야 한다.

20. Permission-Limited Collection Contract
- 본 계약은 `compute` 포함 전체 서비스에 공통 적용한다.
- 권한 부족은 애플리케이션 전체 실패가 아니라 서비스/리전/컴파트먼트/리소스 범위의 부분 실패로 취급한다.
- 오류 분류는 공통 `log_utils.classify_error()` 기준을 사용한다: `permission_denied`, `not_found`, `rate_limited`, `service_error`, `unexpected_error`.
- `permission_denied` 기준은 `401`, `403`, `404 NotAuthorizedOrNotFound`로 고정한다.
- 권한 없는 `list_*` 범위는 `WARN`으로 구조화 로그에 남기고 해당 범위만 스킵한다.
- 권한 없는 `get_*`/상세/관계 조회는 해당 리소스의 `_errors`에 남기고 가능한 나머지 raw 수집을 계속한다.
- 서비스 전체가 권한 부족이어도 runner는 빈 raw list 파일을 생성해 Excel 리포트 생성이 이어지게 한다.
- runner는 서비스 결과에 `warning_count`, `permission_denied_count`, `error_count`, `health`를 남긴다.
- `health` 값은 `ok`, `partial`, `permission_limited`, `failed`, `no_data` 중 하나만 사용한다.
- formatter는 권한 진단 요약을 서비스별 formatter에서 만들지 않는다. 진단 요약과 `99-Run_Diagnostics` 시트는 runner와 `formatter_base` 공통 로직만 담당한다.
- 서비스별 API 문서에는 권한 제한 profile 검증 관점을 포함한다: 권한 없는 scope에서 서비스 스킵/로그/웹/Excel 표현이 일치해야 한다.

## Quality Gates Before Merging Changes
코드 변경 후 최소 확인 항목:
1. 문법 검사: `python3 -m py_compile main.py common.py collectors/*.py formatters/*.py`
2. 최소 1개 프로파일 기준 실행 검증(가능 시)
3. `raw_data` JSON 생성 확인
4. Excel 파일 생성 및 시트 구성 확인
5. 주요 컬럼 정렬/누락 여부 확인
6. 실패 로그가 무음 처리되지 않는지 확인
7. 권한 제한 profile 또는 fake 권한 오류로 서비스 스킵/로그/웹/Excel 표현이 일치하는지 확인

## Change Policy
변경은 작고 검증 가능하게 진행합니다.

1. 수집기 변경 시
- API 호출 변경 이유를 남긴다.
- 데이터 누락 가능성(필드 삭제, 리스트 축약)을 먼저 점검한다.

2. 포매터 변경 시
- 가독성 개선과 데이터 보존 사이의 트레이드오프를 명시한다.
- 시트 분리/컬럼명 변경은 영향도를 설명한다.

3. 장애 수정 시
- 재현 조건, 원인, 수정 포인트를 간단히 기록한다.
- 같은 유형의 실패가 다른 서비스에도 있는지 확인한다.

## Out Of Scope For Now
아래 항목은 후속 요청 전까지 기본 범위 밖입니다.
- 대규모 UI 구축
- 외부 DB 저장소 도입
- 배포 파이프라인 전면 재설계

## Definition of Success
이 프로젝트는 아래를 만족하면 성공입니다.
1. 각 OCI 서비스의 원천 설정 데이터가 `raw_data`에 안정적으로 축적된다.
2. Excel 리포트가 운영자가 즉시 검토 가능한 구조로 생성된다.
3. 데이터 누락과 무음 실패 없이, 실패 원인이 추적 가능하다.
4. 새로운 요구사항이 들어와도 raw schema(collector) 표준을 유지하며 formatter 최소 변경으로 확장 가능하다.

## Ongoing Working Agreements (2026-03-06)
아래 항목은 사용자와 합의된 운영 규칙이며, 별도 변경 요청 전까지 유지한다.

1. Raw-First Display Rule
- formatter는 기본적으로 raw 컬럼을 우선 사용한다.
- 컬럼 개선은 "신규 별칭 생성"보다 "raw 컬럼 재배치"를 우선한다.
- 사용자가 명시적으로 요청하지 않은 derived/alias 컬럼은 추가하지 않는다.

2. Primary Column Rule
- 주요 컬럼은 "운영자가 해당 리소스를 처음 봤을 때 즉시 판단해야 하는 질문에 답하는 컬럼"으로 정의한다.
- 비주요 컬럼은 "근거 확인, 상세 추적, 심화 분석 시 참고하는 raw/detail 컬럼"으로 정의한다.
- 서비스별 formatter는 `get_preferred_columns()`에 주요 컬럼만 선언한다.
- 헤더 강조색은 앞쪽 N개 컬럼이 아니라 `get_preferred_columns()`에 선언된 실제 존재 컬럼에만 적용한다.

3. Category Naming Rule
- 모든 리소스 시트의 `category` 값은 실제 워크시트 이름에서 대분류 접두(`N-`)를 제거한 값으로 설정한다.
- 예: `1-Instance` 시트의 `category` 값은 `Instance`.

4. Common Context Placement Rule
- 공통 컨텍스트 컬럼은 `category` 다음 우선 배치한다.
- 기본 우선순위: `<service>_raw|<service>_enriched`의 `compartment_name` -> `region_name/region` -> `availability_domain_name/availability_domain` -> `fault_domain`.
- 해당 컬럼이 raw에 없으면 추가 생성하지 않는다.
- 공통 컨텍스트 컬럼은 전면 배치와 주요 컬럼 강조를 동일 개념으로 취급하지 않는다.

5. Compute Sheet Naming Rule
- compute 서비스 시트 canonical 이름은 `Instance`를 사용한다 (`1-Instance`).

6. Compute Raw-Only Formatter Rule
- `formatters/formatter_compute.py`는 raw 중심으로 유지한다.
- compute의 주요 정보는 raw 컬럼 순서 재배치로만 관리한다.
- dict prefix가 포함된 raw 경로 컬럼을 그대로 사용하고, 컬럼명 축약/alias는 기본 정책으로 사용하지 않는다.

7. Raw Schema Standardization Contract (Top-Level Dict-Only + Prefix Retention)
- 신규/리팩터링 대상 서비스는 리소스 단위 raw 스키마를 "top-level dict 컨테이너" 방식으로 맞춘다.
- top-level에는 도메인 컨테이너(dict)와 예외 키(`_errors`)만 두는 것을 기본값으로 한다.
- 컨테이너 내부 키는 도메인 의미를 유지하며, `pd.json_normalize` 이후에도 경로 prefix가 보존되도록 설계한다.
- 예시(Compute): `compute_raw.*`, `networking_enriched.*`, `storage_enriched.*`.
- 컬럼 충돌 회피를 위해 formatter에서 prefix를 제거하지 않는다.
- Excel 표시 헤더는 가독성을 위해 최상위 도메인명의 `_raw`/`_enriched` 접미사만 제거해 표시한다.

8. Enriched Data Placement Contract
- 기본 서비스 API에 없는 운영 핵심값(public/private IP, boot/block 용량 등)은 collector에서 추가 API로 보강 수집한다.
- 보강값은 서비스 기본 raw와 분리된 도메인 컨테이너(`*_enriched`/`*_detail`)에 저장한다.
- 값 선정 규칙(예: primary 우선, 첫 항목 fallback)은 collector 코드 주석/로그로 추적 가능하게 남긴다.

9. Cross-Service Standardization Contract (All New Services)
- 아래 규칙은 앞으로 추가/개편하는 모든 서비스에 공통 적용한다.
- Collector는 리소스 단위 top-level dict-only 구조를 사용한다: `<service>_raw` + `<domain>_enriched`(+ 선택적 `<domain>_detail`) + `_errors`.
- Formatter는 raw-first 원칙을 유지한다. 원본 경로 보존을 우선하고, 임의 alias/derived 컬럼 생성은 지양한다.
- Excel 컬럼명은 `x.y` 형식을 유지한다. 표시 단계에서만 최상위 세그먼트의 `_raw`/`_enriched` 접미사를 제거한다.
- 공통 컨텍스트(`compartment/region/ad/fd`)는 Summary 제외 모든 리소스 시트에서 `category` 다음으로 재정렬한다.
- 공통 컨텍스트 재정렬 대상은 `*_raw`와 `*_enriched`를 모두 포함한다.
- 주요/비주요 컬럼 분류 기준은 서비스 공통으로 `Primary Column Rule`을 따른다.
- 도메인 상세 데이터는 가능한 한 도메인별 시트로 분리하며, 데이터가 없는 상세 시트는 생성하지 않는다.
- 실패는 `_errors`에 누적하고, `except: pass` 없이 부분 실패를 노출한다.
- 권한 부족은 공통 오류 분류와 `permission_limited` health로 노출하고, 가능한 raw는 계속 저장한다.

## Deterministic Context Lock (2026-03-06)
이 섹션은 컨텍스트 초기화 후에도 동일 작업 재현을 위한 "정확값 스펙"이다.
본 섹션은 상단 일반 원칙보다 우선 적용한다.

1. Summary/Tab Spec (Exact)
- Summary 제목: `OCI Resource Report`
- 탭 정렬: `Summary` 고정 맨 앞 + 나머지 `N-<SheetName>`를 `N` 오름차순 정렬
- WARN/ERROR 진단이 있으면 `99-Run_Diagnostics` 시트를 생성하며, 탭 정렬상 마지막 진단 시트로 둔다

2. Category Spec (Exact)
- category 계산식: 워크시트 이름에서 첫 `-` 기준 오른쪽 문자열
- 예: `1-Instance` -> `Instance`

3. Canonical Sheet Name Map (Exact)
- 아래 매핑은 `formatters/formatter_base.py` 기준 정확 문자열을 따른다.
- `Compute` -> `Instance`
- `Vcn` -> `VCNs`
- `Vcn_Subnets` -> `VCN_Subnets`
- `Vcn_Route_Tables` -> `VCN_Route_Tables`
- `Vcn_Route_Rules` -> `VCN_Route_Rules`
- `Vcn_Security_Lists` -> `VCN_Security_Lists`
- `Vcn_Security_Rules` -> `VCN_Security_Rules`
- `Vcn_Network_Security_Groups` -> `VCN_Network_Security_Groups`
- `Vcn_NSG_Rules` -> `VCN_NSG_Rules`
- `Vcn_Internet_Gateways` -> `VCN_Internet_Gateways`
- `Vcn_NAT_Gateways` -> `VCN_NAT_Gateways`
- `Vcn_Service_Gateways` -> `VCN_Service_Gateways`
- `Vcn_Local_Peering_Gateways` -> `VCN_Local_Peering_Gateways`
- `Vcn_DHCP_Options` -> `VCN_DHCP_Options`
- `Vcn_DRG_Attachments` -> `VCN_DRG_Attachments`
- `Vcn_DRGs` -> `VCN_DRGs`
- `Vcn_Virtual_Circuits` -> `VCN_Virtual_Circuits`
- `Vpn` -> `VPN_Connections`
- `Vpn_Tunnels` -> `VPN_Tunnels`
- `Fastconnect` -> `FastConnect`
- `Fastconnect_Public_Prefixes` -> `FastConnect_Public_Prefixes`
- `Fastconnect_Cross_Connect_Mappings` -> `FastConnect_Cross_Connect_Mappings`
- `Fastconnect_Associated_Tunnels` -> `FastConnect_Associated_Tunnels`
- `Fastconnect_Bandwidth_Shapes` -> `FastConnect_Bandwidth_Shapes`
- `DNS_Zones` -> `DNS_Zones`
- `DNS_Records` -> `DNS_Records`
- `Dbcs` -> `DBCS_Systems`
- `Dbcs_Operations` -> `DBCS_Operations`
- `Dbcs_DB_Homes` -> `DBCS_DB_Homes`
- `Dbcs_Databases` -> `DBCS_Databases`
- `Dbcs_Database_Backups` -> `DBCS_Database_Backups`
- `Dbcs_Data_Guard` -> `DBCS_Data_Guard`
- `Dbcs_PDBs` -> `DBCS_PDBs`
- `Dbcs_Nodes` -> `DBCS_Nodes`
- `Adb` -> `ADB_Databases`
- `Adb_Backups` -> `ADB_Backups`
- `Mysql` -> `MySQL_DB_Systems`
- `Mysql_Backups` -> `MySQL_Backups`
- `File_Systems` -> `File_Systems`
- `Mount_Targets` -> `Mount_Targets`
- `Export_Sets` -> `Export_Sets`
- `Exports` -> `Exports`
- `Snapshots` -> `Snapshots`
- `Snapshot_Policies` -> `Snapshot_Policies`
- `Replications` -> `Replications`
- `Object_Storage_Buckets` -> `Object_Storage_Buckets`
- `Object_Storage_Retention_Rules` -> `Object_Storage_Retention_Rules`
- `WAF` -> `WAF_Policies`
- `WAF_Firewalls` -> `WAF_Firewalls`
- `WAF_Request_Access` -> `WAF_Request_Access`
- `WAF_Response_Access` -> `WAF_Response_Access`
- `WAF_Request_Protection` -> `WAF_Request_Protection`
- `WAF_Response_Protection` -> `WAF_Response_Protection`
- `WAF_Request_Rate_Limits` -> `WAF_Request_Rate_Limits`
- `WAF_Actions` -> `WAF_Actions`
- `WAF_Edge` -> `WAF_Edge_Policies`
- `WAF_Edge_Custom_Rules` -> `WAF_Edge_Custom_Rules`
- `WAF_Edge_Access_Rules` -> `WAF_Edge_Access_Rules`
- `WAF_Edge_Protection_Rules` -> `WAF_Edge_Protection_Rules`
- `WAF_Edge_Rate_Limits` -> `WAF_Edge_Rate_Limits`
- `Load_Balancers` -> `Load_Balancers`
- `LB_Listeners` -> `Load_Balancer_Listeners`
- `LB_Backend_Sets` -> `Load_Balancer_Backend_Sets`
- `LB_Backends` -> `Load_Balancer_Backends`
- `LB_Hostnames` -> `Load_Balancer_Hostnames`
- `LB_Path_Route_Sets` -> `Load_Balancer_Path_Route_Sets`
- `LB_Path_Route_Rules` -> `Load_Balancer_Path_Routes`
- `LB_Certificates` -> `Load_Balancer_Certificates`
- `NLB_Overview` -> `NetworkLoadBalancers`
- `NLB_Listeners` -> `NetworkLoadBalancerListeners`
- `NLB_Backend_Sets` -> `NetworkLoadBalancerBackendSet`
- `NLB_Backends` -> `NetworkLoadBalancerBackends`
- `Block_Volume_Attachments` -> `Block_Volume_Attachments`
- `Boot_Volume_Attachments` -> `Boot_Volume_Attachments`

4. Common Context Placement (Exact Priority)
- `category` 다음 우선 배치 후보(첫 존재 컬럼 선택):
- `["<service>_raw.compartment_name", "<service>_enriched.compartment_name", "compartment_name", "Compartment", "compartment"]`
- `["<service>_raw.region", "<service>_raw.region_name", "<service>_enriched.region", "<service>_enriched.region_name", "region", "region_name", "Region"]`
- `["<service>_raw.availability_domain", "<service>_raw.availability_domain_name", "<service>_enriched.availability_domain", "<service>_enriched.availability_domain_name", "availability_domain", "availability_domain_name", "Availability Domain"]`
- `["<service>_raw.fault_domain", "<service>_enriched.fault_domain", "fault_domain", "Fault Domain"]`
- 존재하지 않는 컬럼은 생성하지 않는다.

5. Compute Formatter Lock (Exact, Raw-Only)
- 파일: `formatters/formatter_compute.py`
- `transform(df)`는 raw 그대로 반환한다.
- 별칭/요약/파생 컬럼을 formatter에서 생성하지 않는다.
- `get_preferred_columns()`는 top-level 도메인 컨테이너 prefix가 보존된 raw 컬럼 경로를 사용한다.
- 우선 노출 정책은 "compute 기본 컨테이너 -> networking/storage enriched 컨테이너 -> detail 컨테이너" 순서를 따른다.
- 헤더 강조색은 최종 시트의 앞쪽 N개 컬럼이 아니라 `get_preferred_columns()`에 선언된 실제 존재 컬럼에만 적용한다.

6. Compute Collector Schema Lock (Exact)
- 파일: `collectors/compute.py`
- 리소스 raw는 top-level dict 컨테이너 구조를 따른다.
- 필수 컨테이너: `compute_raw`, `networking_enriched`, `storage_enriched`, `_errors`.
- `networking_enriched`는 `public_ip`, `private_ip`, `vcn_name`, `subnet_name`를 포함한다.
- 네트워크 값 선정 규칙: `is_primary=True` VNIC 우선, 없으면 첫 VNIC fallback.
- `storage_enriched`는 `boot_volume_name`, `boot_volume_size_in_gbs`, `block_volume_name`, `block_volume_size_in_gbs`, `block_volume_attachment_type`를 포함한다.
- 스토리지 값 선정 규칙: boot는 첫 boot volume 기준, block은 첫 block volume 기준, attachment type은 동일 `volume_id` 매칭 우선 후 첫 attachment fallback.
- block attachment 부재 시 block 관련 summary 값은 `None` 유지.

7. Hard Prohibitions For This Context
- 중복 컬럼 탐지/삭제 로직 추가 금지
- 요청 없는 전체 prefix 제거/컬럼 축약 금지(재배치만 허용). 단, Excel 표시명에서 `_raw`/`_enriched` 접미사 제거는 허용한다.
- formatter에서 raw 외 임의 derived/alias 컬럼 생성 금지(명시적 승인 전까지)

8. Validation Checklist (Must Pass)
- `python3 -m py_compile collectors/compute.py formatters/formatter_compute.py formatters/formatter_base.py`
- `<profile>` 기준 compute 수집 후 raw 검증:
- `raw_data/<profile>/compute_<profile>.json`의 각 리소스 top-level에 `compute_raw`/`networking_enriched`/`storage_enriched` 존재
- 리포트 검증:
- `1-Instance` 시트 존재
- 첫 컬럼명이 `category`
- `category` 값이 `Instance`
- 주요 raw 컬럼 순서가 본 섹션 5번(컨테이너 prefix 유지 순서)과 일치

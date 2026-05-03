# OCI Resource Extractor

OCI Resource Extractor는 OCI 테넌시에 프로비저닝된 리소스를 서비스별로 수집하고, 운영/보안/아키텍처 검토에 사용할 수 있는 Excel 리포트를 생성하는 Python 도구입니다.

## 주요 기능

- OCI 프로파일 기반 리소스 수집
- 서비스별 raw JSON 저장
- raw-first 원칙의 Excel 리포트 생성
- 서비스별 API 호출 범위 문서화
- 부분 실패 시 `_errors` 필드와 구조화 로그로 원인 추적
- pagination/retry 공통 래퍼 기반 수집

## 지원 서비스

현재 수집 대상 서비스는 다음과 같습니다.

- Compute
- VCN
- WAF
- WAF Edge
- MySQL HeatWave
- Oracle Base Database Service(DBCS)
- Autonomous Database(ADB)
- VPN
- FastConnect
- File Storage
- Block Storage
- Object Storage
- Load Balancer
- Network Load Balancer
- DNS

## 디렉토리 구조

```text
.
├── main.py                 # 실행 엔트리포인트
├── common.py               # OCI client, retry, pagination 공통 로직
├── collectors/             # 서비스별 raw 수집기
├── formatters/             # Excel 시트 변환기
├── docs/                   # 서비스별 API matrix 문서
├── raw_data/               # 생성되는 raw JSON, git 제외
├── OCI_Reports/            # 생성되는 Excel 리포트, git 제외
├── AGENTS.md               # 프로젝트 작업 규칙
└── requirements.txt
```

## 설치

Python 가상환경 사용을 권장합니다.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## OCI 설정

OCI Python SDK 기본 설정 파일을 사용합니다.

```text
~/.oci/config
```

실행 시 config에 등록된 profile 목록이 표시되며, 번호 또는 profile 이름을 선택할 수 있습니다.

## 실행

```bash
python3 main.py
```

생성 결과:

- raw JSON: `raw_data/<profile>/<service>_<profile>.json`
- Excel 리포트: `OCI_Reports/OCI_Report_<profile>.xlsx`

## 선택적 수집 범위 제한

개발/검증 중 특정 profile, region, compartment만 대상으로 실행하려면 코드에 값을 하드코딩하지 말고 환경변수를 사용합니다.

```bash
export OCI_SCOPE_FILTER_PROFILE="<profile>"
export OCI_SCOPE_FILTER_REGIONS="ap-seoul-1,ap-tokyo-1"
export OCI_SCOPE_FILTER_COMPARTMENTS="compartment-a,compartment-b"
python3 main.py
```

환경변수를 지정하지 않으면 전체 region/compartment를 대상으로 실행합니다.

## API Matrix

서비스별 수집 API와 후보 API는 `docs/api_matrix_<service>.md`에 정리되어 있습니다. collector 변경 시 해당 문서도 함께 갱신하는 것을 원칙으로 합니다.

## 검증

문법 검사는 다음 명령으로 수행합니다.

```bash
python3 -m py_compile main.py common.py collectors/*.py formatters/*.py
```

가능한 경우 실제 OCI 개발 환경에서 최소 1개 profile 기준으로 다음을 확인합니다.

- raw JSON 생성 여부
- Excel 파일 생성 여부
- Summary 및 서비스별 시트 구성
- 주요 컬럼 정렬
- `_errors` 및 구조화 로그

## Git 관리 주의사항

다음 항목은 `.gitignore`에 포함되어 GitHub에 올리지 않습니다.

- `raw_data/`
- `OCI_Reports/`
- `venv/`, `.venv/`, `env/`
- `.oci/`
- `.env`, `.env.*`
- `*.pem`, `*.key`, `*.pub`
- `*.log`

GitHub에 push하기 전에는 아래 명령으로 포함 파일을 확인하세요.

```bash
git status --short
```

## GitHub Push 예시

remote 이름을 `resourceextractor`로 등록하는 예시입니다.

```bash
git init
git add .
git commit -m "Initial OCI resource extractor"
git remote add resourceextractor https://github.com/<OWNER>/<REPO>.git
git branch -M main
git -c credential.helper= push -u resourceextractor main
```

Fine-grained token을 저장하지 않으려면 push할 때마다 아래처럼 실행하고, password 입력란에 token 값을 입력합니다.

```bash
git -c credential.helper= push resourceextractor main
```

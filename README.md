# OCI Resource Extractor

OCI Resource Extractor는 OCI 테넌시에 프로비저닝된 리소스를 서비스별로 수집하고, 운영/보안/아키텍처 검토에 바로 사용할 수 있는 Excel 리포트를 생성하는 CLI 기반 Python 도구입니다.

이 도구는 단순히 `list_instances` 같은 단일 API 결과만 엑셀로 옮기는 것이 아니라, OCI Console의 리소스 상세 화면에서 운영자가 함께 보는 연결 정보까지 최대한 따라가며 수집하는 것을 목표로 합니다. 예를 들어 Compute는 인스턴스 기본 정보뿐 아니라 VNIC, Public/Private IP, Subnet, VCN, Boot Volume, Block Volume, Attachment Type 같은 연관 정보를 함께 raw 데이터와 Excel에 반영합니다.

## 한눈에 보기

```text
OCI API
  ↓
collectors/*.py
  ↓
raw_data/<profile>/<service>_<profile>.json
  ↓
formatters/*.py
  ↓
OCI_Reports/OCI_Report_<profile>.xlsx
```

실행 후 생성되는 주요 결과물은 두 가지입니다.

- `raw_data/`: OCI SDK 응답과 보강 수집 정보를 보존한 서비스별 JSON
- `OCI_Reports/`: 사람이 검토하기 좋은 Excel 리포트

두 디렉토리는 실제 고객사/테넌시 결과물이므로 `.gitignore`에 포함되어 GitHub에 올라가지 않습니다.

## 지원 서비스

현재 수집 대상 서비스는 다음과 같습니다.

| 영역 | 서비스 |
| --- | --- |
| Compute | Compute Instance |
| Networking | VCN, VPN, FastConnect, DNS, Load Balancer, Network Load Balancer |
| Storage | Block Storage, File Storage, Object Storage |
| Oracle AI Database | Oracle Base Database Service(DBCS), Autonomous Database(ADB) |
| Databases | MySQL HeatWave |
| Identity & Security | WAF, WAF Edge |

서비스별 상세 API 호출 범위는 `docs/api_matrix_<service>.md`에 정리되어 있습니다.

## 디렉토리 구조

```text
.
├── main.py                 # 실행 엔트리포인트
├── runner.py               # CLI/Web 공용 수집 실행 엔진
├── web_app.py              # FastAPI 기반 웹 실행 화면
├── common.py               # OCI client, retry, pagination 공통 로직
├── collectors/             # 서비스별 raw 수집기
├── formatters/             # Excel 시트 변환기
├── docs/                   # 서비스별 API matrix 문서
├── deploy/                 # systemd 등록 예시
├── raw_data/               # 생성되는 raw JSON, git 제외
├── OCI_Reports/            # 생성되는 Excel 리포트, git 제외
├── AGENTS.md               # 프로젝트 작업 규칙
└── requirements.txt
```

## 준비물

실행 환경에는 다음이 필요합니다.

- Python 3.x
- OCI Python SDK 및 Excel 생성 라이브러리
- OCI API 접근 권한이 있는 `~/.oci/config`
- OCI config에 연결된 key file
- 대상 테넌시/컴파트먼트/서비스를 조회할 수 있는 IAM 권한

OCI config는 OCI Python SDK 기본 위치를 사용합니다.

```text
~/.oci/config
```

예시:

```ini
[DEFAULT]
user=ocid1.user.oc1..example
fingerprint=00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00
tenancy=ocid1.tenancy.oc1..example
region=ap-seoul-1
key_file=/Users/example/.oci/oci_api_key.pem

[DEV]
user=ocid1.user.oc1..example
fingerprint=00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00
tenancy=ocid1.tenancy.oc1..example
region=ap-seoul-1
key_file=/Users/example/.oci/oci_api_key.pem
```

## 설치

Python 가상환경 사용을 권장합니다.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 실행 방법

CLI 실행은 아래 한 줄입니다.

```bash
python3 main.py
```

웹 화면으로 실행하려면 `uvicorn`으로 FastAPI 앱을 실행합니다.

```bash
uvicorn web_app:app --host 127.0.0.1 --port 8088
```

브라우저에서 아래 주소로 접속합니다.

```text
http://127.0.0.1:8088
```

웹 화면에서는 다음 작업을 할 수 있습니다.

- OCI profile 선택
- profile 기준 region/compartment 조회 후 범위 선택
- 수집할 서비스 선택
- 수집 작업 시작
- 정확한 step 진행률과 서비스별 수집 결과 확인
- 이벤트 로그 검색, WARN/ERROR 필터링, 중요 로그 복사
- 생성된 Excel 리포트 다운로드

## CLI 실행

기본 실행은 아래 한 줄입니다.

```bash
python3 main.py
```

실행하면 `~/.oci/config`에 등록된 profile 목록이 표시됩니다. 번호 또는 profile 이름을 입력해 대상을 선택합니다.

```text
--- Select OCI Profile ---
1. DEFAULT
2. DEV
3. PROD

Select number: 2
```

이후 도구는 다음 순서로 동작합니다.

1. 선택한 profile로 OCI Client를 초기화합니다.
2. 테넌시 이름, 구독 리전, 활성 컴파트먼트를 조회합니다.
3. 리전별로 지원 서비스 수집기를 실행합니다.
4. DNS 같은 global 서비스는 리전 반복 없이 1회 실행합니다.
5. 서비스별 raw JSON을 `raw_data/<profile>/`에 저장합니다.
6. 저장된 raw JSON을 기반으로 Excel 리포트를 생성합니다.

실행 중에는 아래와 같은 구조화 로그가 출력됩니다.

```text
[INFO] service=runner event=run_start message="OCI inventory run started" profile=DEV
[INFO] service=runner event=run_plan message="Collection plan prepared" total_steps=16
[INFO] service=runner event=region_start message="Region execution started" step_region=ap-seoul-1
[INFO] service=runner event=step_start message="Service collection step started" step_service=compute step_region=ap-seoul-1
[INFO] service=runner event=step_end message="Service collection step finished" step_service=compute collected=12 errors=0 skipped=0
[INFO] service=report event=report_generated message="Excel report generated" report=OCI_Reports/OCI_Report_DEV.xlsx
```

## 웹 실행

웹 실행은 운영자가 브라우저에서 수집 작업을 시작하고 결과물을 다운로드하기 위한 모드입니다. 내부적으로는 CLI와 같은 `runner.py` 실행 엔진을 사용하므로 생성되는 raw JSON과 Excel 구조는 동일합니다.

```bash
source venv/bin/activate
uvicorn web_app:app --host 127.0.0.1 --port 8088
```

웹 첫 화면에는 `~/.oci/config`에 등록된 profile 목록과 수집 범위 선택 영역이 표시됩니다. Profile을 선택하면 웹 앱이 OCI Identity API로 테넌시 이름, 구독 리전, 활성 컴파트먼트를 조회해 체크박스로 보여줍니다. 전체가 선택된 상태는 별도 필터 없이 전체 범위를 수집한다는 의미입니다.

```text
OCI Profile: DEV
Region 제한: ap-seoul-1 선택
Compartment 제한: network-dev 선택
서비스 선택: compute, vcn, block_storage, ...
```

조회가 실패하거나 목록에서 바로 고르기 어려운 경우에는 region/compartment를 직접 입력할 수 있습니다. 직접 입력은 기존과 같이 콤마 구분 형식을 사용합니다.

```text
ap-seoul-1,ap-tokyo-1
network-dev,app-dev
```

수집을 시작하면 작업 상세 화면에서 현재 상태와 정확한 진행률을 확인할 수 있습니다. 진행률은 실행 계획의 전체 step 수 대비 완료 step 수로 계산됩니다.

```text
Status: running
Current Step: compute / ap-seoul-1
Completed Steps: 4 / 16
```

작업 상세 화면에는 서비스별 수집 결과와 이벤트 로그가 함께 표시됩니다. 이벤트 로그는 전체/WARN/ERROR 필터, 키워드 검색, WARN/ERROR 복사 기능을 제공합니다.

작업이 완료되면 `Excel 다운로드` 버튼으로 아래 파일을 받을 수 있습니다.

```text
OCI_Reports/OCI_Report_<profile>.xlsx
```

주의: 현재 웹 앱에는 자체 로그인 기능이 없습니다. 운영 서버에 올릴 때는 `127.0.0.1` 바인딩, VPN/사내망 접근 제한, reverse proxy 인증 같은 외부 접근 통제를 반드시 함께 구성하세요.

## 데몬 등록(systemd)

Linux 개발 서버에서 웹 앱을 상시 실행하려면 `systemd` 서비스로 등록할 수 있습니다. 예시 파일은 아래 경로에 있습니다.

```text
deploy/oci-resource-extractor-web.service.example
```

서버 환경에 맞게 `User`, `Group`, `WorkingDirectory`, `ExecStart` 경로를 수정한 뒤 등록합니다.

```bash
sudo cp deploy/oci-resource-extractor-web.service.example /etc/systemd/system/oci-resource-extractor-web.service
sudo systemctl daemon-reload
sudo systemctl enable --now oci-resource-extractor-web
sudo systemctl status oci-resource-extractor-web
```

로그 확인:

```bash
journalctl -u oci-resource-extractor-web -f
```

기본 예시는 보안을 위해 `127.0.0.1:8088`에만 바인딩합니다. 외부 브라우저에서 접근해야 한다면 Nginx/Apache 같은 reverse proxy를 앞단에 두고 인증과 접근 제한을 적용하는 구성을 권장합니다.

systemd로 실행할 때 OCI SDK는 서비스 계정의 홈 디렉토리 기준 `~/.oci/config`를 읽습니다. 예시처럼 `User=oci-extractor`를 사용한다면 `/home/oci-extractor/.oci/config`와 key file 권한을 먼저 준비해야 합니다.

## 처음 실행할 때 권장 방식

처음부터 전체 테넌시를 조회하면 API 호출량과 실행 시간이 커질 수 있습니다. 개발/검증 중에는 특정 profile, region, compartment로 범위를 좁혀 실행하는 것을 권장합니다.

```bash
export OCI_SCOPE_FILTER_PROFILE="DEV"
export OCI_SCOPE_FILTER_REGIONS="ap-seoul-1"
export OCI_SCOPE_FILTER_COMPARTMENTS="network-dev,app-dev"
python3 main.py
```

환경변수를 지정하지 않으면 선택한 profile 기준 전체 구독 리전과 활성 컴파트먼트를 대상으로 실행합니다.

API 호출 간격을 조절해야 하는 환경에서는 아래 값을 사용할 수 있습니다.

```bash
export OCI_API_MIN_INTERVAL_MS="200"
python3 main.py
```

## 예상 결과물

예를 들어 `DEV` profile로 실행하면 아래와 같은 파일이 생성됩니다.

```text
raw_data/
└── DEV/
    ├── compute_DEV.json
    ├── vcn_DEV.json
    ├── block_storage_DEV.json
    ├── load_balancer_DEV.json
    ├── dns_DEV.json
    └── ...

OCI_Reports/
└── OCI_Report_DEV.xlsx
```

### Raw JSON

raw JSON은 서비스별 원천 데이터입니다. formatter가 보기 좋게 Excel로 바꾸더라도, 추적 가능한 원본 경로를 최대한 유지하기 위해 raw에는 도메인별 컨테이너 구조를 사용합니다.

Compute raw 예시:

```json
[
  {
    "compute_raw": {
      "id": "ocid1.instance.oc1..example",
      "display_name": "app-server-01",
      "lifecycle_state": "RUNNING",
      "shape": "VM.Standard.E4.Flex",
      "region": "ap-seoul-1",
      "compartment_name": "app-dev"
    },
    "networking_enriched": {
      "public_ip": "203.0.113.10",
      "private_ip": "10.0.1.10",
      "vcn_name": "dev-vcn",
      "subnet_name": "app-subnet"
    },
    "storage_enriched": {
      "boot_volume_name": "app-server-01-boot",
      "boot_volume_size_in_gbs": 100,
      "block_volume_name": "app-data-01",
      "block_volume_size_in_gbs": 512,
      "block_volume_attachment_type": "PARAVIRTUALIZED"
    },
    "_errors": []
  }
]
```

### Excel 리포트

Excel 파일은 `Summary` 시트를 맨 앞에 만들고, 서비스별 시트를 OCI Console 대분류 기준으로 정렬합니다.

대표 시트 예시:

```text
Summary
1-Instance
2-VCNs
2-VCN_Subnets
2-VCN_Route_Tables
2-VCN_Security_Rules
2-VPN_Connections
2-FastConnect
2-DNS_Zones
2-Load_Balancers
2-NetworkLoadBalancers
3-Block_Volumes
3-Boot_Volumes
3-File_Systems
3-Object_Storage_Buckets
4-DBCS_Systems
4-ADB_Databases
5-MySQL_DB_Systems
6-WAF_Policies
6-WAF_Edge_Policies
```

`Summary` 시트에는 다음 정보가 표시됩니다.

- 테넌시명
- 추출일자
- 서비스 그룹
- 생성된 시트 이름
- 시트별 리소스 개수
- 각 시트로 이동하는 링크

각 리소스 시트는 다음 원칙으로 구성됩니다.

- 첫 컬럼은 `category`
- 그 다음에 compartment, region, availability domain 같은 공통 운영 컨텍스트 배치
- 운영자가 먼저 보는 주요 컬럼을 앞쪽에 배치
- 상세 추적용 raw/detail 컬럼은 뒤쪽에 유지
- VCN, Load Balancer, WAF처럼 하위 리소스가 많은 서비스는 도메인별 상세 시트로 분리

## 결과를 어떻게 보면 되나요?

운영자가 리포트를 열었을 때의 기본 흐름은 다음과 같습니다.

1. `Summary`에서 전체 시트와 리소스 개수를 확인합니다.
2. `1-Instance`에서 Compute 인스턴스 상태, shape, 네트워크, 스토리지 연결 정보를 봅니다.
3. `2-VCNs`, `2-VCN_Subnets`, `2-VCN_Security_Rules`에서 네트워크 구성과 보안 규칙을 확인합니다.
4. `3-Block_Volumes`, `3-File_Systems`, `3-Object_Storage_Buckets`에서 스토리지 구성을 확인합니다.
5. `4-DBCS_Systems`, `4-ADB_Databases`, `5-MySQL_DB_Systems`에서 DB 계층을 확인합니다.
6. `_errors` 컬럼이 있는 경우 부분 수집 실패 원인을 확인합니다.

## 검증

문법 검사는 다음 명령으로 수행합니다.

```bash
python3 -m py_compile main.py common.py collectors/*.py formatters/*.py
```

가능한 경우 실제 OCI 개발 환경에서 최소 1개 profile 기준으로 다음을 확인합니다.

- `raw_data/<profile>/`에 서비스별 JSON 생성 여부
- `OCI_Reports/OCI_Report_<profile>.xlsx` 생성 여부
- `Summary` 및 서비스별 시트 구성
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
git status --short --ignored
```

`raw_data/`, `OCI_Reports/`, `venv/`, `__pycache__/` 등이 `!!`로 표시되면 ignore가 적용된 상태입니다.

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

import pandas as pd
import json
import os
import sys

# 테스트용 복잡한 JSON 데이터 생성
test_data = [
    {
        "display_name": "test-instance",
        "region_name": "ap-seoul-1",
        "compartment_name": "root",
        "lifecycle_state": "RUNNING",
        "shape_config": {
            "ocpus": 2,
            "memory_in_gbs": 16,
            "nested_detail": {
                "key1": "val1",
                "key2": "val2"
            }
        },
        "vnics": [
            {"ip": "10.0.0.1", "public": "1.1.1.1", "subnet": "ocid1..."},
            {"ip": "10.0.0.2", "public": None, "subnet": "ocid1..."}
        ],
        "tags": {"project": "demo", "env": "dev"}
    }
]

# raw_data 폴더 생성 및 저장
os.makedirs("raw_data", exist_ok=True)
with open("raw_data/test_verify.json", "w") as f:
    json.dump(test_data, f)

# formatter 로직 시뮬레이션
def verify():
    with open("raw_data/test_verify.json", "r") as f:
        data = json.load(f)
    
    df = pd.json_normalize(data)
    
    print("--- 검증 결과 ---")
    print(f"1. 생성된 총 컬럼 수: {len(df.columns)}")
    print(f"2. 컬럼 목록: {df.columns.tolist()}")
    
    # 중첩 데이터 검증
    expected_nested = ['shape_config.ocpus', 'shape_config.nested_detail.key1', 'tags.project']
    for col in expected_nested:
        if col in df.columns:
            print(f"[OK] 중첩 필드 추출 성공: {col} = {df.iloc[0][col]}")
        else:
            print(f"[FAIL] 중첩 필드 누락: {col}")

    # 리스트 데이터 검증 (데이터가 통째로 들어있는지)
    if 'vnics' in df.columns:
        vnic_data = df.iloc[0]['vnics']
        if isinstance(vnic_data, list) and len(vnic_data) == 2:
            print(f"[OK] 리스트 데이터 보존 성공: vnics (항목 {len(vnic_data)}개 포함)")
        else:
            print(f"[FAIL] 리스트 데이터 형식 오류")
    else:
        print("[FAIL] 리스트 필드 누락: vnics")

if __name__ == "__main__":
    verify()

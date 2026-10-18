"""
계약서 이미지 1장을 4단계 파이프라인에 통과시켜 결과를 한눈에 보여준다.
서버가 떠 있어야 함 (uvicorn app.main:app).

사용:
    .venv/bin/python tests/run_pipeline.py                                # 기본: 독소 계약서
    .venv/bin/python tests/run_pipeline.py tests/fixtures/sample_contract_clean.png
"""
import sys
import httpx

BASE = "http://127.0.0.1:8000/api"
IMG = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/sample_contract.png"
ADDRESS_FALLBACK = "서울특별시 강남구 테헤란로 123"  # OCR이 주소를 못 뽑은 경우에만 사용

c = httpx.Client(timeout=180.0)

print(f"\n계약서: {IMG}")

# 1단계: 이미지 → OCR + 마스킹 (주소도 여기서 자동 추출)
with open(IMG, "rb") as f:
    r1 = c.post(f"{BASE}/analyze/image", files={"file": ("c.png", f, "image/png")}).json()
sid = r1["session_id"]
address = r1.get("address") or ADDRESS_FALLBACK
print("\n[1단계] OCR + 마스킹")
print("  OCR 원문(앞 120자):", r1["ocr_text"].replace("\n", " ")[:120])
print("  마스킹(앞 120자) :", r1["masked_text"].replace("\n", " ")[:120])
print("  추출 주소:", r1.get("address"), "(자동)" if r1.get("address") else "(추출 실패 → 수동값 사용)")

# 2단계: 주소 검증 (1단계에서 추출한 주소 사용)
r2 = c.post(f"{BASE}/verify/address", json={"session_id": sid, "address": address}).json()
print("\n[2단계] 주소 검증")
print("  도로명:", r2.get("road_address"), "| 법정동코드:", r2.get("bjd_code"))

# 3단계: 건물 조회
r3 = c.post(f"{BASE}/building", json={"session_id": sid}).json()
print("\n[3단계] 건물 조회")
print("  등기:", r3.get("is_registered"), "| 실거래가:", r3.get("sale_price"), "| 전세가율:", r3.get("jeonse_ratio"))

# 4단계: AI 리스크 분석
r4 = c.post(f"{BASE}/analyze/risk", json={"session_id": sid})
print("\n[4단계] AI 리스크 분석", f"(HTTP {r4.status_code})")
d = r4.json()
if r4.status_code == 200:
    print(f"  점수: {d['score']} / 등급: {d['level']}")
    print(f"  독소조항 {len(d['issues'])}건:")
    for it in d["issues"]:
        tag = "법적위반" if it["is_legal_basis"] else "개인체크"
        print(f"    - [{tag}] 심각도{it['severity']} | {it['clause']}")
    print("  행동가이드:", [g["type"] for g in d["action_guide"]])
    print("  매핑테이블 파기:", d["mapping_table_purged"])
else:
    print("  오류:", d)

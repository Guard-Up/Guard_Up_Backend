import asyncio
import re

from fastapi import APIRouter, File, UploadFile

from app.core.exceptions import AppException
from app.core.session import (
    KEY_BJD_CODE,
    KEY_BUILDING,
    KEY_JEONSE_AMOUNT,
    KEY_MAPPING,
    KEY_MASKED_TEXT,
    KEY_OCR_TEXT,
    KEY_RAW_ADDRESS,
    KEY_STEPS_COMPLETED,
    create_session,
    get_session,
    new_session_id,
    purge_mapping,
)
from app.schemas.analyze import (
    ImageResponse,
    Issue,
    PublicData,
    RiskRequest,
    RiskResponse,
)
from app.services import masking_service, ocr_service, risk_service

router = APIRouter()


MAX_PAGES = 10


@router.post("/analyze/image", response_model=ImageResponse)
async def analyze_image(file: list[UploadFile] = File(...)):
    """
    1단계: 계약서 이미지 분석 (여러 장 지원)
    - 페이지별 CLOVA OCR 텍스트 추출
    - 페이지별 개인정보 비식별화 (매핑 테이블은 문서 전체 공유)
    - Redis 세션 생성

    같은 필드명(file)으로 여러 장을 보내면 페이지 순서대로 처리한다. 1장이면 기존과 동일.
    """
    if not file:
        raise AppException(400, "INVALID_IMAGE", "이미지가 없습니다.")
    if len(file) > MAX_PAGES:
        raise AppException(400, "TOO_MANY_PAGES", f"한 번에 최대 {MAX_PAGES}장까지 분석할 수 있습니다.")

    # 1. 페이지별 OCR (병렬)
    page_bytes = [await f.read() for f in file]
    ocr_results = await asyncio.gather(*(ocr_service.run_ocr(b) for b in page_bytes))

    page_texts = [r["text"] for r in ocr_results]
    ocr_text = "\n".join(page_texts)
    # 주소는 먼저 잡힌 페이지 것을 사용 (보통 1페이지 상단의 소재지)
    raw_address = next((r["address"] for r in ocr_results if r.get("address")), None)

    if not ocr_text.strip():
        raise AppException(422, "OCR_FAILED", "텍스트를 추출할 수 없습니다.")

    # 1-1. 입력 검증 — 전세계약서 한 건인지 확인 (비전세·월세·여러 건 차단)
    _validate_jeonse_contract(ocr_text)

    # 2. 비식별화 (팀원2 - masking_service). 페이지별 마스킹 + 매핑 공유
    masking_result = masking_service.run_masking_pages(page_texts)
    masked_text = masking_result["masked_text"]
    mapping = masking_result["mapping"]

    # 3. 전세금 추출 (전체 텍스트 기준)
    jeonse_amount = _extract_jeonse_amount(ocr_text)

    # 4. 세션 생성 및 Redis 저장
    session_id = new_session_id()
    await create_session(
        session_id,
        {
            KEY_OCR_TEXT: ocr_text,
            KEY_MASKED_TEXT: masked_text,
            KEY_MAPPING: mapping,
            KEY_RAW_ADDRESS: raw_address,
            KEY_JEONSE_AMOUNT: jeonse_amount,
            KEY_STEPS_COMPLETED: [1],
        },
    )

    return ImageResponse(
        session_id=session_id,
        ocr_text=ocr_text,
        masked_text=masked_text,
        address=raw_address,
    )


@router.post("/analyze/risk", response_model=RiskResponse)
async def analyze_risk(req: RiskRequest):
    """
    4단계: AI 리스크 분석
    - 세션에서 masked_text, building 데이터 조회
    - RAG + GPT-4o 독소 조항 분석
    - 규칙 기반 리스크 점수 산출 
    """
    session = await get_session(req.session_id)
    if not session:
        raise AppException(400, "INVALID_SESSION", "세션이 만료되었거나 존재하지 않습니다.")

    # 선행 단계(2: 주소검증, 3: 건물조회) 완료 여부 확인
    steps = session.get(KEY_STEPS_COMPLETED, [])
    if 2 not in steps or 3 not in steps:
        raise AppException(424, "PREREQUISITE_FAILED", "이전 단계(주소 검증·건물 조회)가 완료되지 않았습니다.")

    masked_text = session.get(KEY_MASKED_TEXT, "")
    if not masked_text:
        raise AppException(400, "INVALID_SESSION", "분석할 계약서 텍스트가 없습니다. 처음부터 다시 진행해 주세요.")

    # 공공 API 단계에서 저장된 building 데이터 (없으면 기본값 사용)
    building: dict = session.get(KEY_BUILDING) or {}
    bjd_code: str | None = session.get(KEY_BJD_CODE)

    jeonse_ratio_pct = _parse_ratio(building.get("jeonse_ratio"))
    is_registered: bool = building.get("is_registered", True)
    # mortgage_amount: int = building.get("mortgage_amount") or 0   # TODO: 등기부등본 API 연동 시 복구
    sale_price: int = building.get("sale_price") or 0
    # mortgage_ratio_pct = (mortgage_amount / sale_price * 100) if sale_price > 0 else 0.0 # TODO: 등기부등본 API 연동 시 복구

    # 리스크 분석 (동기 함수 — RAG + GPT)
    result = risk_service.calculate_risk(
        masked_text=masked_text,
        jeonse_ratio_pct=jeonse_ratio_pct,
        is_registered=is_registered,
        # mortgage_ratio_pct=mortgage_ratio_pct,    # TODO: 등기부등본 API 연동 시 복구
        bjd_code=bjd_code,
    )

    # 분석 완료 후 개인정보 매핑 테이블 파기
    await purge_mapping(req.session_id)

    return RiskResponse(
        score=result["score"],
        level=result["level"],
        issues=[Issue(**i) for i in result["issues"]],
        action_guide=result["action_guide"],
        public_data=PublicData(
            jeonse_ratio=building.get("jeonse_ratio") or "정보 없음",
            is_registered=is_registered,
            # mortgage_amount=mortgage_amount or None,  # TODO: 등기부등본 API 연동 시 복구
        ),
        mapping_table_purged=True,
    )


def _parse_ratio(ratio_str: str | None) -> float:
    """'83%' → 83.0, None → 0.0"""
    if not ratio_str:
        return 0.0
    try:
        return float(ratio_str.replace("%", "").strip())
    except ValueError:
        return 0.0


# ── 전세계약서 입력 검증 ──────────────────────────────────────
# 여러 장을 받게 되면서, 전세계약서가 아니거나(월세·비계약서) 서로 다른 계약서를
# 한꺼번에 넣는 입력을 걸러야 한다. OCR 텍스트만으로 판별하는 가벼운 규칙 검증.

_LEASE_KEYWORDS = ("임대차", "전세", "보증금")

# 계약서 한 건당 '제1조'는 한 번. 두 번 이상이면 여러 계약서를 함께 넣은 것.
_ARTICLE1_RE = re.compile(r"제\s*1\s*조")

# 체크박스: 대괄호 안에 공백이 아닌 표식(V·√·✓·■ 등)이 있으면 '선택됨'
_CHECKED = r"\[\s*[^\s\]]{1,2}\s*\]"
_WOLSE_CHECKED_RE = re.compile(_CHECKED + r"\s*(?:보증금\s*있는\s*)?월세")
_JEONSE_CHECKED_RE = re.compile(_CHECKED + r"\s*전세")
# 차임(월세) 값이 '없음'이 아니라 실제 금액이면 월세/반전세
_CHARIM_RE = re.compile(r"차임\s*(?:\(\s*월\s*세\s*\))?\s*[:：]?\s*([^\n]{0,20})")


def _is_wolse(text: str) -> bool:
    """월세(반전세 포함) 여부. 이 앱은 전세만 받으므로 월세면 차단한다."""
    # 표준계약서 상단 체크박스: 월세만 선택되고 전세는 미선택
    if _WOLSE_CHECKED_RE.search(text) and not _JEONSE_CHECKED_RE.search(text):
        return True
    # 차임 항목에 실제 금액이 적혀 있으면 월세
    m = _CHARIM_RE.search(text)
    if m and "없음" not in m.group(1) and re.search(r"[\d만억천]|원", m.group(1)):
        return True
    return False


def _validate_jeonse_contract(text: str) -> None:
    """전세계약서 한 건인지 검증. 아니면 AppException(422)."""
    # 계약서 자체로 인식되지 않음
    if not any(k in text for k in _LEASE_KEYWORDS):
        raise AppException(
            422, "NOT_CONTRACT",
            "전세계약서로 인식되지 않습니다. 계약서 전체가 선명하게 보이도록 다시 촬영해 주세요.",
        )
    # 여러 건의 계약서가 함께 들어옴
    if len(_ARTICLE1_RE.findall(text)) >= 2:
        raise AppException(
            422, "MULTIPLE_CONTRACTS",
            "여러 건의 계약서가 감지되었습니다. 한 번에 한 계약서만 넣어 주세요.",
        )
    # 월세 계약서 (이 앱은 전세 전용)
    if _is_wolse(text):
        raise AppException(
            422, "NOT_JEONSE",
            "월세 계약서로 보입니다. 이 앱은 전세 계약서만 분석합니다.",
        )


# ── 전세금 추출 ────────────────────────────────────────────────

_KO_NUM = {"영": 0, "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5,
           "육": 6, "칠": 7, "팔": 8, "구": 9}
_UNIT_SMALL = {"십": 10, "백": 100, "천": 1000}
_UNIT_BIG = {"만": 10_000, "억": 100_000_000}

# 콤마/평문 숫자 + 원   (예: "250,000,000원")
_RE_DIGIT_AMOUNT = re.compile(r"(\d[\d,]{5,})\s*원")
# 숫자·한글 혼합 + 단위 + 원 (내부 공백 허용: "2억 5천만원", "이억오천만원")
_AMT_CHARS = r"\d일이삼사오육칠팔구십백천만억"
_RE_UNIT_AMOUNT = re.compile(rf"([{_AMT_CHARS}]+(?:[ \t]+[{_AMT_CHARS}]+)*)\s*원")


def _parse_mixed_amount(s: str) -> int:
    """'2억5천만' / '이억오천만' / '5000만' → 정수 환산"""
    total = section = num = 0
    digit_buf = ""
    for ch in s:
        if ch.isdigit():
            digit_buf += ch
            continue
        if digit_buf:
            num = int(digit_buf)
            digit_buf = ""
        if ch in _KO_NUM:
            num = _KO_NUM[ch]
        elif ch in _UNIT_SMALL:
            section += (num or 1) * _UNIT_SMALL[ch]
            num = 0
        elif ch in _UNIT_BIG:
            section += num
            total += section * _UNIT_BIG[ch]
            section = num = 0
    if digit_buf:
        num = int(digit_buf)
    return total + section + num


def _find_amount_candidates(text: str) -> list[tuple[int, int]]:
    """(위치, 금액) 후보 목록. 콤마 숫자 + 단위 표기 모두 수집 (100만원 이상)."""
    candidates: list[tuple[int, int]] = []

    for m in _RE_DIGIT_AMOUNT.finditer(text):
        value = int(m.group(1).replace(",", ""))
        if value >= 1_000_000:
            candidates.append((m.start(), value))

    for m in _RE_UNIT_AMOUNT.finditer(text):
        raw = m.group(1)
        if not any(u in raw for u in "억만천"):  # 단위 없으면 콤마 패턴이 처리하므로 스킵
            continue
        value = _parse_mixed_amount(raw)
        if value >= 1_000_000:
            candidates.append((m.start(), value))

    return candidates


def _extract_jeonse_amount(text: str) -> int:
    """
    OCR 텍스트에서 전세보증금 추출.
    표기 지원: 콤마 숫자(250,000,000원) / 숫자+단위(2억5천만원) / 한글(이억오천만원).
    '보증금'·'전세' 키워드 근처 금액을 우선 채택, 없으면 최댓값.
    """
    candidates = _find_amount_candidates(text)
    if not candidates:
        return 0

    for pos, amount in candidates:
        context = text[max(0, pos - 20):pos]
        if "보증금" in context or "전세" in context:
            return amount

    return max(amount for _, amount in candidates)
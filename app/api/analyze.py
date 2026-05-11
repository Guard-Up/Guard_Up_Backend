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


@router.post("/analyze/image", response_model=ImageResponse)
async def analyze_image(file: UploadFile = File(...)):
    """
    1단계: 계약서 이미지 분석
    - CLOVA OCR 텍스트 추출
    - 개인정보 비식별화
    - Redis 세션 생성
    """
    image_bytes = await file.read()

    # 1. OCR 실행
    ocr_result = await ocr_service.run_ocr(image_bytes)
    ocr_text = ocr_result["text"]
    raw_address = ocr_result["address"]

    if not ocr_text.strip():
        raise AppException(422, "OCR_FAILED", "텍스트를 추출할 수 없습니다.")

    # 2. 비식별화 (팀원2 - masking_service)
    masking_result = masking_service.run_masking(ocr_text)
    masked_text = masking_result["masked_text"]
    mapping = masking_result["mapping"]

    # 3. 전세금 추출
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
        raise AppException(404, "SESSION_NOT_FOUND", "세션이 만료되었거나 존재하지 않습니다.")

    masked_text = session.get(KEY_MASKED_TEXT, "")
    if not masked_text:
        raise AppException(422, "NO_MASKED_TEXT", "분석할 계약서 텍스트가 없습니다. 1단계부터 다시 진행해 주세요.")

    # 공공 API 단계에서 저장된 building 데이터 (없으면 기본값 사용)
    building: dict = session.get(KEY_BUILDING) or {}
    bjd_code: str | None = session.get(KEY_BJD_CODE)

    jeonse_ratio_pct = _parse_ratio(building.get("jeonse_ratio"))
    is_registered: bool = building.get("is_registered", True)
    mortgage_amount: int = building.get("mortgage_amount") or 0
    sale_price: int = building.get("sale_price") or 0
    mortgage_ratio_pct = (mortgage_amount / sale_price * 100) if sale_price > 0 else 0.0

    # 리스크 분석 (동기 함수 — RAG + GPT)
    result = risk_service.calculate_risk(
        masked_text=masked_text,
        jeonse_ratio_pct=jeonse_ratio_pct,
        is_registered=is_registered,
        mortgage_ratio_pct=mortgage_ratio_pct,
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
            mortgage_amount=mortgage_amount or None,
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


def _extract_jeonse_amount(text: str) -> int:
    """
    텍스트에서 전세금 추출
    예: "보증금 2억 5천만원" → 250_000_000
    """
    import re

    match = re.search(r"(\d+)\s*억\s*(\d+)?\s*천?\s*만?", text)
    if match:
        uk = int(match.group(1))
        chun = int(match.group(2)) if match.group(2) else 0
        return uk * 100_000_000 + chun * 10_000_000

    match = re.search(r"(\d+)\s*만\s*원", text)
    if match:
        return int(match.group(1)) * 10_000

    return 0
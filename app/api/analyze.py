from fastapi import APIRouter

from app.core.exceptions import AppException
from app.core.session import (
    KEY_JEONSE_AMOUNT,
    KEY_MAPPING,
    KEY_MASKED_TEXT,
    KEY_OCR_TEXT,
    KEY_RAW_ADDRESS,
    KEY_STEPS_COMPLETED,
    create_session,
    new_session_id,
)
from app.schemas.analyze import (
    ImageRequest,
    ImageResponse,
    Issue,
    PublicData,
    RiskRequest,
    RiskResponse,
)
from app.services import masking_service, ocr_service

router = APIRouter()


@router.post("/analyze/image", response_model=ImageResponse)
async def analyze_image(req: ImageRequest):
    """
    1단계: 계약서 이미지 분석
    - CLOVA OCR 텍스트 추출 (본인)
    - 개인정보 비식별화 (팀원2 - masking_service)
    - Redis 세션 생성
    """
    # 1. OCR 실행
    ocr_result = await ocr_service.run_ocr(req.image)
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
    TODO: 팀원2가 risk_service.py 완성 후 실제 구현으로 교체
    """
    return RiskResponse(
        score=25,
        level="danger",
        issues=[
            Issue(
                clause="임대인은 임차인에게 사전 통보 없이 보증금을 감액할 수 있다.",
                reason="임차인 동의 없는 보증금 감액은 주택임대차보호법 위반입니다.",
                severity=5,
            )
        ],
        action_guide=[
            {"type": "stop", "message": "계약서에 독소 조항이 발견되었습니다. 즉시 날인을 중단하세요."},
            {
                "type": "institution",
                "name": "서울 자립지원 전담기관",
                "phone": "02-000-0000",
                "region": "서울특별시",
                "address": "서울시 종로구 OO로 00",
            },
            {
                "type": "legal",
                "message": "전세사기 피해 신고는 경찰청 112 또는 LH콜센터 1600-1004로 연락하세요.",
            },
        ],
        public_data=PublicData(
            jeonse_ratio="83%",
            is_registered=True,
            mortgage_amount=50000000,
        ),
        mapping_table_purged=True,
    )


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
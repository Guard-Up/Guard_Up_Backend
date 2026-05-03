from fastapi import APIRouter

from app.core.session import new_session_id
from app.schemas.analyze import (
    ImageRequest,
    ImageResponse,
    Issue,
    PublicData,
    RiskRequest,
    RiskResponse,
)

router = APIRouter()


@router.post("/analyze/image", response_model=ImageResponse)
async def analyze_image(req: ImageRequest):
    return ImageResponse(
        session_id=new_session_id(),
        ocr_text="임대인 홍길동, 임차인 김철수. 전세금 이억원. 주소 서울시 강남구 역삼동 123-45.",
        masked_text="임대인 [PERSON_001], 임차인 [PERSON_002]. 전세금 이억원. 주소 [ADDR_001].",
        address="서울시 강남구 역삼동 123-45",
    )


@router.post("/analyze/risk", response_model=RiskResponse)
async def analyze_risk(req: RiskRequest):
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

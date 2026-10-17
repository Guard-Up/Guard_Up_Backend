from typing import Any, Optional
from pydantic import BaseModel


# ── 1단계: /api/analyze/image ──────────────────────────────

class ImageResponse(BaseModel):
    session_id: str
    ocr_text: str
    masked_text: str
    address: Optional[str] = None


# ── 4단계: /api/analyze/risk ───────────────────────────────

class RiskRequest(BaseModel):
    session_id: str


class Issue(BaseModel):
    clause: str
    reason: str
    severity: int  # 1~5
    is_legal_basis: bool  # true: 강행규정 위반(법적 무효), false: 임차인 동의 시 유효(개인 체크 권장)
    location: Optional[str] = None  # 계약서상 위치. "제9조(계약의 종료)" / "특약사항 1항". 전세가율·미등기 항목은 null
    page: Optional[int] = None  # 몇 번째 이미지인지 (1부터). 전세가율·미등기 항목은 null
    legal_basis: Optional[str] = None  # 근거 법령·조문. "주택임대차보호법 제3조"


class PublicData(BaseModel):
    jeonse_ratio: str
    is_registered: bool
    # mortgage_amount: Optional[int] = None     # TODO: 등기부등본 API 연동 시 복구


class RiskResponse(BaseModel):
    score: int  # 0~100 (낮을수록 위험)
    level: str  # "safe" | "caution" | "danger"
    issues: list[Issue]
    action_guide: list[Any]
    public_data: PublicData
    mapping_table_purged: bool
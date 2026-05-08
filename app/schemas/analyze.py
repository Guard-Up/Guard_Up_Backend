from typing import Any, Optional
from pydantic import BaseModel


# ── 1단계: /api/analyze/image ──────────────────────────────

class ImageRequest(BaseModel):
    image: str  # base64 인코딩된 계약서 이미지


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


class PublicData(BaseModel):
    jeonse_ratio: str
    guarantee_available: Optional[bool] = None
    max_guarantee_amount: Optional[int] = None
    is_registered: bool
    mortgage_amount: Optional[int] = None


class RiskResponse(BaseModel):
    score: int  # 0~100 (낮을수록 위험)
    level: str  # "safe" | "caution" | "danger"
    issues: list[Issue]
    action_guide: list[Any]
    public_data: PublicData
    mapping_table_purged: bool
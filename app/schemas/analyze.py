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
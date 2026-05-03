from typing import Optional

from pydantic import BaseModel


class ImageRequest(BaseModel):
    image: str  # base64 인코딩된 계약서 이미지


class ImageResponse(BaseModel):
    session_id: str
    ocr_text: str
    masked_text: str
    address: Optional[str] = None


class RiskRequest(BaseModel):
    session_id: str


class Issue(BaseModel):
    clause: str
    reason: str
    severity: int  # 1~5


class PublicData(BaseModel):
    jeonse_ratio: str
    is_registered: bool
    mortgage_amount: Optional[int] = None


class RiskResponse(BaseModel):
    score: int  # 0~100, 낮을수록 위험
    level: str  # "safe" / "caution" / "danger"
    issues: list[Issue]
    action_guide: list[dict]
    public_data: PublicData
    mapping_table_purged: bool

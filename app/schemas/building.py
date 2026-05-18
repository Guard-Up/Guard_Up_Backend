from typing import Optional

from pydantic import BaseModel


class BuildingRequest(BaseModel):
    session_id: str


class BuildingResponse(BaseModel):
    building_name: Optional[str] = None
    build_year: Optional[int] = None
    # owner_type: Optional[str] = None       # TODO: 등기부등본 API 연동 시 복구
    # mortgage_amount: Optional[int] = None  # TODO: 등기부등본 API 연동 시 복구
    is_registered: bool
    sale_price: Optional[int] = None
    jeonse_ratio: Optional[str] = None

from typing import Optional

from pydantic import BaseModel


class BuildingRequest(BaseModel):
    session_id: str
    road_address: str


class BuildingResponse(BaseModel):
    building_name: Optional[str] = None
    build_year: Optional[int] = None
    owner_type: Optional[str] = None
    mortgage_amount: Optional[int] = None
    is_registered: bool
    sale_price: Optional[int] = None
    jeonse_ratio: Optional[str] = None

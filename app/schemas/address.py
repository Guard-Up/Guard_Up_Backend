from typing import Optional

from pydantic import BaseModel


class AddressRequest(BaseModel):
    session_id: str
    address: str


class AddressResponse(BaseModel):
    is_valid: bool
    road_address: Optional[str] = None
    jibun_address: Optional[str] = None
    zip_code: Optional[str] = None
    bjd_code: Optional[str] = None  # 도로명주소 API 실패 시 JSON 폴백 테이블 사용

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str  # "ok" / "degraded" / "down"
    ocr_api: bool
    address_api: bool
    building_api: bool
    ai_module: bool
    institution_db: bool

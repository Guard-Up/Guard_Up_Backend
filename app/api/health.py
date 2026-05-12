from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ok",
        ocr_api=False,
        address_api=False,
        building_api=False,
        ai_module=False,
        institution_db=False,
    )

from fastapi import APIRouter

from app.core.exceptions import AppException
from app.schemas.institution import Institution, InstitutionRequest, InstitutionResponse
from app.services import institution_service

router = APIRouter()


@router.post("/institution", response_model=InstitutionResponse)
async def get_institutions(req: InstitutionRequest):
    results = institution_service.get_by_region(req.region)

    if not results:
        raise AppException(404, "REGION_NOT_FOUND", "해당 지역의 기관 정보가 없습니다.")

    return InstitutionResponse(
        region=req.region,
        institutions=[Institution(**inst) for inst in results],
    )

from fastapi import APIRouter

from app.schemas.institution import InstitutionRequest, InstitutionResponse, Institution
from app.services import institution_service

router = APIRouter()


@router.post("/institution", response_model=InstitutionResponse)
async def get_institutions(req: InstitutionRequest):
    results = institution_service.get_by_region(req.region)
    return InstitutionResponse(
        region=req.region,
        institutions=[Institution(**inst) for inst in results],
    )

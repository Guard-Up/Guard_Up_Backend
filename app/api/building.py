from fastapi import APIRouter

from app.schemas.building import BuildingRequest, BuildingResponse

router = APIRouter()


@router.post("/building", response_model=BuildingResponse)
async def get_building(req: BuildingRequest):
    return BuildingResponse(
        building_name="테헤란빌라",
        build_year=2005,
        owner_type="개인",
        mortgage_amount=50000000,
        is_registered=True,
        sale_price=300000000,
        jeonse_ratio="83%",
    )

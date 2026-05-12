from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.building import BuildingRequest, BuildingResponse
from app.services.public_api_service import get_building_info

router = APIRouter()


def is_valid_session(session_id: str) -> bool:
    return bool(session_id and session_id.strip())


@router.post("/building", response_model=BuildingResponse)
async def get_building(req: BuildingRequest, request: Request) -> BuildingResponse:
    if not is_valid_session(req.session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_SESSION"},
        )

    try:
        result = await get_building_info(
            road_address=req.road_address,
            jibun_address=req.jibun_address,
            bjd_code=req.bjd_code,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error_code": "PUBLIC_API_ERROR"},
        )

    if not result.is_registered:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "BUILDING_NOT_FOUND"},
        )

    request.session["building_name"] = result.building_name
    request.session["is_registered"] = result.is_registered
    request.session["sale_price"] = result.sale_price
    request.session["jeonse_ratio"] = result.jeonse_ratio

    return result
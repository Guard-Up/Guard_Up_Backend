from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.building import BuildingRequest, BuildingResponse
from app.services.public_api_service import get_building_info
from app.core.session import (get_session, update_session, KEY_ROAD_ADDRESS, KEY_BJD_CODE, KEY_BUILDING, KEY_JEONSE_AMOUNT)

router = APIRouter()


@router.post("/building", response_model=BuildingResponse)
async def get_building(req: BuildingRequest, request: Request) -> BuildingResponse:
    session=await get_session(req.session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_SESSION"},
        )
    
    road_address = session.get(KEY_ROAD_ADDRESS)
    bjd_code = session.get(KEY_BJD_CODE)
    jeonse_amount = session.get(KEY_JEONSE_AMOUNT)

    if not road_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_SESSION"},
        )

    try:
        result = await get_building_info(
            road_address=road_address,
            jibun_address=None,
            bjd_code=bjd_code,
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
    
    jeonse_ratio = None
    if result.sale_price and jeonse_amount:
        sale_price_won = result.sale_price * 10000  # 만원 → 원 변환
        ratio = (jeonse_amount / sale_price_won) * 100
        jeonse_ratio = f"{ratio:.1f}%"
    
    building_data = {
        "building_name": result.building_name,
        "is_registered": result.is_registered,
    }
    if result.sale_price is not None:
            building_data["sale_price"] = result.sale_price
    if jeonse_ratio is not None:
            building_data["jeonse_ratio"] = jeonse_ratio

    await update_session(req.session_id, {KEY_BUILDING: building_data})

    return BuildingResponse(
        building_name=result.building_name,
        build_year=result.build_year,
        is_registered=result.is_registered,
        sale_price=result.sale_price,
        jeonse_ratio=jeonse_ratio,
    )
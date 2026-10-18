from fastapi import APIRouter

from app.core.exceptions import AppException
from app.schemas.building import BuildingRequest, BuildingResponse
from app.services.public_api_service import get_building_info
from app.core.session import (
    get_session,
    update_session,
    KEY_ROAD_ADDRESS,
    KEY_BJD_CODE,
    KEY_BUILDING,
    KEY_JEONSE_AMOUNT,
    KEY_JIBUN_ADDRESS,
    KEY_STEPS_COMPLETED,
)

router = APIRouter()


@router.post("/building", response_model=BuildingResponse)
async def get_building(req: BuildingRequest) -> BuildingResponse:
    session = await get_session(req.session_id)
    if session is None:
        raise AppException(400, "INVALID_SESSION", "세션이 만료되었거나 존재하지 않습니다.")

    road_address = session.get(KEY_ROAD_ADDRESS)
    bjd_code = session.get(KEY_BJD_CODE)
    jeonse_amount = session.get(KEY_JEONSE_AMOUNT)
    jibun_address = session.get(KEY_JIBUN_ADDRESS)

    if not road_address:
        raise AppException(400, "INVALID_SESSION", "주소 검증(2단계)이 완료되지 않았습니다.")

    try:
        result = await get_building_info(
            road_address=road_address,
            jibun_address=jibun_address,
            bjd_code=bjd_code,
        )
    except Exception:
        raise AppException(502, "PUBLIC_API_ERROR", "건축물대장 API 호출에 실패했습니다.")

    # 미등기/건물 정보 없음(is_registered=False)이어도 404로 막지 않고 끝까지 진행.
    # 4단계 리스크 분석에서 점수 0점·danger로 고정 처리됨.
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

    steps = session.get(KEY_STEPS_COMPLETED, [])
    if 3 not in steps:
        steps.append(3)

    await update_session(
        req.session_id,
        {KEY_BUILDING: building_data, KEY_STEPS_COMPLETED: steps},
    )

    return BuildingResponse(
        building_name=result.building_name,
        build_year=result.build_year,
        is_registered=result.is_registered,
        sale_price=result.sale_price,
        jeonse_ratio=jeonse_ratio,
    )

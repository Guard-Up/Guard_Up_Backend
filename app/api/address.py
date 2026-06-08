from fastapi import APIRouter

from app.core.exceptions import AppException
from app.schemas.address import AddressRequest, AddressResponse
from app.services.public_api_service import verify_address as verify_address_service
from app.core.session import (
    get_session,
    update_session,
    KEY_ROAD_ADDRESS,
    KEY_BJD_CODE,
    KEY_JIBUN_ADDRESS,
    KEY_STEPS_COMPLETED,
)

router = APIRouter()


@router.post("/verify/address", response_model=AddressResponse)
async def verify_address(req: AddressRequest) -> AddressResponse:
    session = await get_session(req.session_id)
    if session is None:
        raise AppException(400, "INVALID_SESSION", "세션이 만료되었거나 존재하지 않습니다.")

    try:
        result = await verify_address_service(req.address)
    except Exception:
        raise AppException(502, "PUBLIC_API_ERROR", "도로명주소 API 호출에 실패했습니다.")

    if not result.is_valid:
        raise AppException(404, "ADDRESS_NOT_FOUND", "주소를 찾을 수 없습니다.")

    steps = session.get(KEY_STEPS_COMPLETED, [])
    if 2 not in steps:
        steps.append(2)

    await update_session(
        req.session_id,
        {
            KEY_ROAD_ADDRESS: result.road_address,
            KEY_BJD_CODE: result.bjd_code,
            KEY_JIBUN_ADDRESS: result.jibun_address,
            KEY_STEPS_COMPLETED: steps,
        },
    )

    return result

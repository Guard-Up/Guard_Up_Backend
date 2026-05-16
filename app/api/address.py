from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.address import AddressRequest, AddressResponse
from app.services.public_api_service import verify_address as verify_address_service
from app.core.session import get_session, update_session, KEY_ROAD_ADDRESS, KEY_BJD_CODE

router = APIRouter()


@router.post("/verify/address", response_model=AddressResponse)
async def verify_address(req: AddressRequest, request: Request) -> AddressResponse:
    session=await get_session(req.session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_SESSION"},
        )

    try:
        result = await verify_address_service(req.address)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error_code": "PUBLIC_API_ERROR"},
        )

    if not result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "ADDRESS_NOT_FOUND"},
        )

    await update_session(req.session_id, {
        KEY_ROAD_ADDRESS: result.road_address,
        KEY_BJD_CODE: result.bjd_code,
    })

    return result
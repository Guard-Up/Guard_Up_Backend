from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.address import AddressRequest, AddressResponse
from app.services.public_api_service import verify_address as verify_address_service

router = APIRouter()


def is_valid_session(session_id: str) -> bool:
    return bool(session_id and session_id.strip())


@router.post("/verify/address", response_model=AddressResponse)
async def verify_address(req: AddressRequest, request: Request) -> AddressResponse:
    if not is_valid_session(req.session_id):
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

    request.session["road_address"] = result.road_address
    request.session["bjd_code"] = result.bjd_code

    return result
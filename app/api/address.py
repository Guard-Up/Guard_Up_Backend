from fastapi import APIRouter

from app.schemas.address import AddressRequest, AddressResponse

router = APIRouter()


@router.post("/verify/address", response_model=AddressResponse)
async def verify_address(req: AddressRequest):
    result = await verify_address_service(req.address)
    return result

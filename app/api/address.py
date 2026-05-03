from fastapi import APIRouter

from app.schemas.address import AddressRequest, AddressResponse

router = APIRouter()


@router.post("/verify/address", response_model=AddressResponse)
async def verify_address(req: AddressRequest):
    return AddressResponse(
        is_valid=True,
        road_address="서울특별시 강남구 테헤란로 123",
        jibun_address="서울특별시 강남구 역삼동 123-45",
        zip_code="06134",
        bjd_code="1168010100",
    )

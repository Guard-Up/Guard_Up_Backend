from app.schemas.address import AddressResponse

async def verify_address(address: str) -> AddressResponse:
    address = address.strip()

    if not address:
        return AddressResponse(
            is_valid = False,
            road_address = None,
            jibun_address = None,
            zip_code = None,
            bjd_code = None,
        )

    return AddressResponse(
        is_valid = True,
        road_address = "서울특별시 강남구 테헤란로 123",
        jibun_address = "서울특별시 강남구 역삼동 123-45",
        zip_code = "06134",
        bjd_code = "1168010100",
    )
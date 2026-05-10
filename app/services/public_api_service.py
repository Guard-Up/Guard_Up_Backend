import re
import httpx
import xml.etree.ElementTree as ET

from datetime import datetime
from app.core.config import settings
from app.schemas.address import AddressResponse
from app.schemas.building import BuildingResponse


def split_bjd_code(bjd_code: str) -> tuple[str | None, str | None]:
    if not bjd_code or len(bjd_code) < 10:
        return None, None

    return bjd_code[:5], bjd_code[5:10]


def parse_jibun(jibun_address: str | None) -> tuple[str, str]:
    if not jibun_address:
        return "0000", "0000"

    m = re.search(r"(\d+)(?:-(\d+))?", jibun_address)
    if not m:
        return "0000", "0000"

    bun = m.group(1)
    ji = m.group(2) or "0"

    return bun.zfill(4), ji.zfill(4)


async def verify_address(address: str) -> AddressResponse:
    address = address.strip()

    if not address:
        return AddressResponse(
            is_valid=False,
            road_address=None,
            jibun_address=None,
            zip_code=None,
            bjd_code=None,
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                settings.ROAD_ADDRESS_API_URL,
                params={
                    "confmKey": settings.ROAD_ADDRESS_API_KEY,
                    "currentPage": 1,
                    "countPerPage": 10,
                    "keyword": address,
                    "resultType": "json",
                }
            )

        response.raise_for_status()
        data = response.json()

    except Exception:
        return AddressResponse(
            is_valid=False,
            road_address=None,
            jibun_address=None,
            zip_code=None,
            bjd_code=None,
        )

    results = data.get("results", {})
    juso_list = results.get("juso", [])

    if not juso_list:
        return AddressResponse(
            is_valid=False,
            road_address=None,
            jibun_address=None,
            zip_code=None,
            bjd_code=None,
        )

    first = juso_list[0]

    return AddressResponse(
        is_valid=True,
        road_address=first.get("roadAddr"),
        jibun_address=first.get("jibunAddr"),
        zip_code=first.get("zipNo"),
        bjd_code=first.get("admCd"),
    )

async def get_apartment_sale_price(
    building_name: str | None,
    bjd_code: str | None,
) -> int | None:
    if not building_name or not bjd_code or len(bjd_code) < 5:
        return None

    lawd_cd = bjd_code[:5]
    target_name = building_name.replace(" ", "").replace(",", "").replace("아파트", "")
    now = datetime.now()

    deal_ymd_candidates = []
    for i in range(12):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        deal_ymd_candidates.append(f"{year}{month:02d}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for deal_ymd in deal_ymd_candidates:
                response = await client.get(
                    settings.APT_TRADE_API_URL,
                    params={
                        "serviceKey": settings.MOLIT_API_KEY,
                        "LAWD_CD": lawd_cd,
                        "DEAL_YMD": deal_ymd,
                    },
                )
                response.raise_for_status()

                root = ET.fromstring(response.text)
                items = root.findall(".//item")

                for item in items:
                    apt_nm = (
                        item.findtext("aptNm")
                        or item.findtext("아파트")
                        or ""
                    ).strip()

                    deal_amount = (
                        item.findtext("dealAmount")
                        or item.findtext("거래금액")
                        or ""
                    ).strip()

                    if not apt_nm or not deal_amount:
                        continue

                    normalized_apt_nm = (
                        apt_nm.replace(" ", "")
                        .replace(",", "")
                        .replace("아파트", "")
                    )

                    if (
                        normalized_apt_nm in target_name
                        or target_name in normalized_apt_nm
                    ):
                        try:
                            return int(
                                deal_amount.replace(",", "").replace(" ", "")
                            )
                        except ValueError:
                            continue

        return None

    except Exception:
        return None

async def get_building_info(
    road_address: str,
    jibun_address: str | None = None,
    bjd_code: str | None = None,
) -> BuildingResponse:
    sigungu_cd, bjdong_cd = split_bjd_code(bjd_code or "")
    bun, ji = parse_jibun(jibun_address)

    if not sigungu_cd or not bjdong_cd:
        return BuildingResponse(
            building_name=None,
            build_year=None,
            owner_type=None,
            mortgage_amount=None,
            is_registered=False,
            sale_price=None,
            jeonse_ratio=None,
        )

    try:
        params = {
            "serviceKey": settings.BUILDING_API_KEY,
            "sigunguCd": sigungu_cd,
            "bjdongCd": bjdong_cd,
            "platGbCd": 0,
            "bun": bun,
            "ji": ji,
            "numOfRows": 10,
            "pageNo": 1,
            "_type": "json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(settings.BUILDING_API_URL, params=params)

        response.raise_for_status()
        data = response.json()

        body = data.get("response", {}).get("body", {})
        total_count = int(body.get("totalCount", 0))

        if total_count == 0:
            return BuildingResponse(
                building_name=None,
                build_year=None,
                owner_type=None,
                mortgage_amount=None,
                is_registered=False,
                sale_price=None,
                jeonse_ratio=None,
            )

        items = body.get("items", {}).get("item", [])

        if isinstance(items, dict):
            item = items
        elif isinstance(items, list) and len(items) > 0:
            item = items[0]
        else:
            item = {}

        building_name = item.get("bldNm")
        sale_price = await get_apartment_sale_price(building_name, bjd_code)

        return BuildingResponse(
            building_name=building_name,
            build_year=None,
            owner_type=None,
            mortgage_amount=None,
            is_registered=True,
            sale_price=sale_price,
            jeonse_ratio=None,
        )

    except Exception:
        return BuildingResponse(
            building_name=None,
            build_year=None,
            owner_type=None,
            mortgage_amount=None,
            is_registered=False,
            sale_price=None,
            jeonse_ratio=None,
        )
    
    
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


def normalize_building_name(name: str | None) -> str:
    if not name:
        return ""

    normalized = name.strip()
    normalized = normalized.replace(" ", "")
    normalized = normalized.replace(",", "")
    normalized = normalized.replace(".", "")
    normalized = normalized.replace("아파트", "")
    normalized = normalized.replace("오피스텔", "")
    normalized = normalized.replace("연립", "")
    normalized = normalized.replace("다세대", "")
    normalized = normalized.replace("주택", "")
    return normalized


def get_deal_ymd_candidates(months: int = 12) -> list[str]:
    now = datetime.now()
    candidates = []

    for i in range(months):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        candidates.append(f"{year}{month:02d}")

    return candidates


def parse_trade_amount(text: str | None) -> int | None:
    if not text:
        return None

    cleaned = text.replace(",", "").replace(" ", "").strip()
    if not cleaned:
        return None

    try:
        return int(cleaned)
    except ValueError:
        return None


async def fetch_trade_price_by_name(
    api_url: str,
    building_name: str | None,
    bjd_code: str | None,
    name_fields: list[str],
) -> int | None:
    if not api_url or not building_name or not bjd_code or len(bjd_code) < 5:
        return None

    lawd_cd = bjd_code[:5]
    target_name = normalize_building_name(building_name)
    if not target_name:
        return None

    deal_ymd_candidates = get_deal_ymd_candidates(12)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for deal_ymd in deal_ymd_candidates:
                response = await client.get(
                    api_url,
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
                    trade_name = ""

                    for field in name_fields:
                        value = item.findtext(field)
                        if value and value.strip():
                            trade_name = value.strip()
                            break

                    deal_amount = (
                        item.findtext("dealAmount")
                        or item.findtext("거래금액")
                        or ""
                    ).strip()

                    if not trade_name or not deal_amount:
                        continue

                    normalized_trade_name = normalize_building_name(trade_name)

                    if (
                        normalized_trade_name in target_name
                        or target_name in normalized_trade_name
                    ):
                        parsed_amount = parse_trade_amount(deal_amount)
                        if parsed_amount is not None:
                            return parsed_amount

        return None

    except Exception:
        return None


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
    return await fetch_trade_price_by_name(
        api_url=settings.APT_TRADE_API_URL,
        building_name=building_name,
        bjd_code=bjd_code,
        name_fields=["aptNm", "아파트"],
    )


async def get_rowhouse_sale_price(
    building_name: str | None,
    bjd_code: str | None,
) -> int | None:
    return await fetch_trade_price_by_name(
        api_url=settings.ROWHOUSE_TRADE_API_URL,
        building_name=building_name,
        bjd_code=bjd_code,
        name_fields=["mhouseNm", "연립다세대", "건물명"],
    )


async def get_officetel_sale_price(
    building_name: str | None,
    bjd_code: str | None,
) -> int | None:
    return await fetch_trade_price_by_name(
        api_url=settings.OFFICETEL_TRADE_API_URL,
        building_name=building_name,
        bjd_code=bjd_code,
        name_fields=["offiNm", "오피스텔", "건물명"],
    )


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
                # owner_type=None,      # TODO: 등기부등본 API 연동 시 복구
                # mortgage_amount=None, # TODO: 등기부등본 API 연동 시 복구
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

        use_apr_day = item.get("useAprDay")
        build_year = int(use_apr_day[:4]) if use_apr_day and len(use_apr_day) >= 4 else None

        sale_price = await get_apartment_sale_price(building_name, bjd_code)
        if sale_price is None:
            sale_price = await get_rowhouse_sale_price(building_name, bjd_code)
        if sale_price is None:
            sale_price = await get_officetel_sale_price(building_name, bjd_code)

        return BuildingResponse(
            building_name=building_name,
            build_year=build_year,
            # owner_type=None,      # TODO: 등기부등본 API 연동 시 복구
            # mortgage_amount=None, # TODO: 등기부등본 API 연동 시 복구
            is_registered=True,
            sale_price=sale_price,
            jeonse_ratio=None,
        )

    except Exception:
        return BuildingResponse(
            building_name=None,
            build_year=None,
            # owner_type=None,      # TODO: 등기부등본 API 연동 시 복구
            # mortgage_amount=None, # TODO: 등기부등본 API 연동 시 복구
            is_registered=False,
            sale_price=None,
            jeonse_ratio=None,
        )
    
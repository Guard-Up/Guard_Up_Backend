import asyncio

import httpx
from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse
from app.services import institution_service

router = APIRouter()

_TIMEOUT = 3.0


async def _reachable(url: str, *, headers: dict | None = None, params: dict | None = None) -> bool:
    """HTTP 응답을 받으면(서버 다운 5xx 제외) 연결된 것으로 간주."""
    if not url:
        return False
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, headers=headers, params=params)
        return resp.status_code < 500
    except Exception:
        return False


async def _check_ocr() -> bool:
    # CLOVA OCR은 POST 전용. GET하면 4xx가 오지만 호스트 도달 = 연결 정상으로 판단.
    if not settings.CLOVA_OCR_INVOKE_URL or not settings.CLOVA_OCR_SECRET:
        return False
    return await _reachable(settings.CLOVA_OCR_INVOKE_URL)


async def _check_address() -> bool:
    if not settings.ROAD_ADDRESS_API_KEY:
        return False
    return await _reachable(
        settings.ROAD_ADDRESS_API_URL,
        params={
            "confmKey": settings.ROAD_ADDRESS_API_KEY,
            "currentPage": 1,
            "countPerPage": 1,
            "keyword": "서울특별시",
            "resultType": "json",
        },
    )


async def _check_building() -> bool:
    if not settings.BUILDING_API_KEY:
        return False
    return await _reachable(settings.BUILDING_API_URL)


async def _check_ai() -> bool:
    # OpenAI 모델 목록 조회로 키 유효성까지 확인 (200일 때만 정상)
    if not settings.OPENAI_API_KEY:
        return False
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            )
        return resp.status_code == 200
    except Exception:
        return False


def _check_institution_db() -> bool:
    try:
        return bool(institution_service._load())
    except Exception:
        return False


@router.get("/health", response_model=HealthResponse)
async def health_check():
    ocr_api, address_api, building_api, ai_module = await asyncio.gather(
        _check_ocr(),
        _check_address(),
        _check_building(),
        _check_ai(),
    )
    institution_db = _check_institution_db()

    checks = [ocr_api, address_api, building_api, ai_module, institution_db]
    if all(checks):
        status = "ok"
    elif any(checks):
        status = "degraded"
    else:
        status = "down"

    return HealthResponse(
        status=status,
        ocr_api=ocr_api,
        address_api=address_api,
        building_api=building_api,
        ai_module=ai_module,
        institution_db=institution_db,
    )

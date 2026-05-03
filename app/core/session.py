import json
import uuid

import redis.asyncio as redis

from app.core.config import settings

# 세션 키 상수 (모든 서비스에서 이 상수 사용)
KEY_OCR_TEXT = "ocr_text"
KEY_MASKED_TEXT = "masked_text"
KEY_MAPPING = "mapping"
KEY_RAW_ADDRESS = "raw_address"
KEY_JEONSE_AMOUNT = "jeonse_amount"
KEY_ROAD_ADDRESS = "road_address"
KEY_BJD_CODE = "bjd_code"
KEY_BUILDING = "building"
KEY_STEPS_COMPLETED = "steps_completed"

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def new_session_id() -> str:
    return str(uuid.uuid4())


async def create_session(session_id: str, data: dict) -> None:
    r = get_redis()
    await r.setex(f"session:{session_id}", settings.SESSION_TTL, json.dumps(data, ensure_ascii=False))


async def get_session(session_id: str) -> dict | None:
    r = get_redis()
    raw = await r.get(f"session:{session_id}")
    if raw is None:
        return None
    return json.loads(raw)


async def update_session(session_id: str, updates: dict) -> None:
    data = await get_session(session_id)
    if data is None:
        return
    data.update(updates)
    r = get_redis()
    await r.setex(f"session:{session_id}", settings.SESSION_TTL, json.dumps(data, ensure_ascii=False))


async def delete_session(session_id: str) -> None:
    r = get_redis()
    await r.delete(f"session:{session_id}")

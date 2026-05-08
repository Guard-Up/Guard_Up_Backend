import io
import re
import uuid
import base64
from typing import Optional

import httpx
from PIL import Image

from app.core.config import settings
from app.core.exceptions import AppException

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass


async def run_ocr(image_bytes: bytes) -> dict:
    """
    CLOVA OCR API 호출하여 텍스트 추출
    Returns: {"text": str, "address": Optional[str]}
    """
    jpg_base64 = _to_jpg_base64(image_bytes)

    payload = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": 0,
        "images": [
            {
                "format": "jpg",
                "name": "contract",
                "data": jpg_base64,
            }
        ],
    }

    headers = {
        "X-OCR-SECRET": settings.CLOVA_OCR_SECRET,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                settings.CLOVA_OCR_INVOKE_URL,
                json=payload,
                headers=headers,
            )

        if response.status_code != 200:
            raise AppException(422, "OCR_FAILED", f"CLOVA OCR 오류: {response.status_code}")

        data = response.json()
        text = _extract_text(data)
        address = _extract_address(text)

        return {"text": text, "address": address}

    except AppException:
        raise
    except Exception as e:
        raise AppException(422, "OCR_FAILED", f"CLOVA OCR 처리 실패: {str(e)}")


def _to_jpg_base64(image_bytes: bytes) -> str:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        output = io.BytesIO()
        image.convert("RGB").save(output, format="JPEG", quality=95)
        return base64.b64encode(output.getvalue()).decode()
    except Exception:
        raise AppException(400, "INVALID_IMAGE", "지원하지 않는 이미지 형식입니다.")


def _extract_text(ocr_response: dict) -> str:
    lines = []
    for image in ocr_response.get("images", []):
        for field in image.get("fields", []):
            lines.append(field.get("inferText", ""))
    return "\n".join(lines)


def _extract_address(text: str) -> Optional[str]:
    patterns = [
        r"(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
        r"[^\n]{2,40}(로|길)\s*\d+[^\n]{0,20}",
        r"(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
        r"[^\n]{2,40}(동|읍|면)\s*\d+[-\d]*",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group().strip()

    return None

import re
import uuid
import base64
from typing import Optional

import httpx

from app.core.config import settings
from app.core.exceptions import AppException


async def run_ocr(image_base64: str) -> dict:
    """
    CLOVA OCR API 호출하여 텍스트 추출
    Returns: {"text": str, "address": Optional[str]}
    """
    _validate_base64(image_base64)

    payload = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": 0,
        "images": [
            {
                "format": "jpg",
                "name": "contract",
                "data": image_base64,
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


def _validate_base64(image_base64: str) -> None:
    """base64 유효성 검증"""
    try:
        base64.b64decode(image_base64, validate=True)
    except Exception:
        raise AppException(400, "INVALID_IMAGE", "유효하지 않은 base64 이미지입니다.")


def _extract_text(ocr_response: dict) -> str:
    """CLOVA OCR 응답에서 텍스트 추출"""
    lines = []
    for image in ocr_response.get("images", []):
        for field in image.get("fields", []):
            lines.append(field.get("inferText", ""))
    return "\n".join(lines)


def _extract_address(text: str) -> Optional[str]:
    """
    OCR 텍스트에서 주소 추출 (정규표현식 기반)
    시/도 + 시/군/구 + 도로명/지번 패턴 매칭
    """
    patterns = [
        # 도로명 주소: 시/도 + ... + 로/길 + 번지
        r"(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
        r"[^\n]{2,40}(로|길)\s*\d+[^\n]{0,20}",
        # 지번 주소: 시/도 + ... + 동/읍/면 + 번지
        r"(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
        r"[^\n]{2,40}(동|읍|면)\s*\d+[-\d]*",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group().strip()

    return None
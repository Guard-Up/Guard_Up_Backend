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


# 시/도로 시작, 사이의 공백·줄바꿈 허용(CLOVA가 단어마다 줄을 바꿔 주므로),
# 로/길+번호 또는 동/읍/면/리+번지에서 끝. 한글·숫자·공백만 허용해 문서 전체를 가로지르지 않게 함.
_ADDRESS_RE = re.compile(
    r"(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
    r"[가-힣0-9\s]{0,50}?"
    r"(?:(?:로|길)\s*\d+(?:-\d+)?|[가-힣]+(?:동|읍|면|리)\s*\d+(?:-\d+)?)"
)


def _extract_address(text: str) -> Optional[str]:
    match = _ADDRESS_RE.search(text)
    if not match:
        return None
    # 매칭된 주소의 줄바꿈·중복 공백만 한 칸으로 정리(입력 원문은 그대로 둠)
    return " ".join(match.group().split())

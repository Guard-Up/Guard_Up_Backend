import json
from pathlib import Path

_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "institutions.json"

BJD_PREFIX_TO_REGION = {
    "11": "서울특별시",
    "26": "부산광역시",
    "27": "대구광역시",
    "28": "인천광역시",
    "29": "광주광역시",
    "30": "대전광역시",
    "31": "울산광역시",
    "36": "세종특별자치시",
    "41": "경기도",
    "42": "강원특별자치도",
    "43": "충청북도",
    "44": "충청남도",
    "45": "전북특별자치도",
    "46": "전라남도",
    "47": "경상북도",
    "48": "경상남도",
    "50": "제주특별자치도",
}


def _load() -> list[dict]:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["institutions"]


def get_by_region(region: str) -> list[dict]:
    return [inst for inst in _load() if inst["region"] == region]


def get_by_bjd_code(bjd_code: str) -> list[dict]:
    prefix = bjd_code[:2]
    region = BJD_PREFIX_TO_REGION.get(prefix)
    if not region:
        return []
    return get_by_region(region)

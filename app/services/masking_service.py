import re
from functools import lru_cache

from transformers import pipeline

NER_MODEL = "Leo97/KoELECTRA-small-v3-modu-ner"

# NER 레이블 → 마스킹 토큰 접두사
MASK_TYPES = {
    "PS": "PERSON",
    "LC": "ADDR",
    "OG": "ORG",
}


@lru_cache(maxsize=1)
def _get_ner():
    return pipeline("ner", model=NER_MODEL, aggregation_strategy="simple")


def run_masking(text: str) -> dict:
    """
    NER + 정규식으로 개인정보 마스킹

    Returns:
        {
            "masked_text": "[PERSON_001]이 임대인으로...",
            "mapping": {"[PERSON_001]": "홍길동", "[ADDR_001]": "서울시 강남구..."}
        }
    """
    masked_text = text
    mapping = {}
    counters = {}

    # 1. KLUE-NER: 인명(PS), 장소(LC), 기관(OG) 마스킹
    try:
        entities = _get_ner()(text)
        # 뒤에서부터 교체해야 앞 인덱스가 밀리지 않음
        entities = sorted(entities, key=lambda e: e["start"], reverse=True)

        for ent in entities:
            prefix = MASK_TYPES.get(ent["entity_group"])
            if not prefix:
                continue
            counters[prefix] = counters.get(prefix, 0) + 1
            token = f"[{prefix}_{counters[prefix]:03d}]"
            mapping[token] = text[ent["start"]:ent["end"]]
            masked_text = masked_text[:ent["start"]] + token + masked_text[ent["end"]:]

    except Exception:
        pass

    # 2. 정규식: 주민등록번호
    masked_text, m = _regex_mask(masked_text, r"\d{6}-[1-4]\d{6}", "RRN", counters)
    mapping.update(m)

    # 3. 정규식: 전화번호
    masked_text, m = _regex_mask(masked_text, r"0\d{1,2}-\d{3,4}-\d{4}", "PHONE", counters)
    mapping.update(m)

    return {"masked_text": masked_text, "mapping": mapping}


def _regex_mask(text: str, pattern: str, prefix: str, counters: dict) -> tuple[str, dict]:
    mapping = {}
    count = counters.get(prefix, 0)

    def replace(match):
        nonlocal count
        count += 1
        token = f"[{prefix}_{count:03d}]"
        mapping[token] = match.group()
        return token

    result = re.sub(pattern, replace, text)
    counters[prefix] = count
    return result, mapping

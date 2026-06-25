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
    다층 비식별화 파이프라인. 확실한 정규식 → 라벨 → NER 순으로 통과시켜 누출을 최소화.
    (단계가 쌓일수록 커버리지↑. 단, 어떤 PII 시스템도 100%는 불가 — OCR 오타·비표준 양식은 놓칠 수 있음)

    순서:
      1) 구조적 정규식 (주민등록번호·전화) — 형식 고정이라 거의 100%
      2) 주소 정규식 (시/도 시작 도로명·지번)
      3) 라벨 기반 인명 ('성명: 홍길동', '임대인(홍길동)')
      4) KLUE-NER — 위 단계가 놓친 자유 텍스트의 인명·장소·기관

    Returns:
        {"masked_text": "...", "mapping": {"[PERSON_001]": "홍길동", ...}}
    """
    masked_text = text
    mapping: dict = {}
    counters: dict = {}

    # 1) 구조적 정규식 (가장 확실). 구분자(-/./공백) 유무·법인명 변형까지 폭넓게 처리
    for pattern, prefix in (
        (r"\d{6}[-\s]?[1-4]\d{6}", "RRN"),                     # 주민등록번호 (하이픈·공백 옵션)
        (r"0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}", "PHONE"),      # 전화번호 (-, ., 공백, 없음)
        (r"(?:주식회사|유한회사|\(주\))\s*[가-힣A-Za-z0-9]+"
         r"|[가-힣A-Za-z0-9]+\s*(?:주식회사|\(주\))", "ORG"),   # 법인명
    ):
        masked_text, m = _regex_mask(masked_text, pattern, prefix, counters)
        mapping.update(m)

    # 2) 주소 정규식
    masked_text, m = _regex_mask(masked_text, _ADDR_PATTERN, "ADDR", counters)
    mapping.update(m)

    # 3) 라벨 기반 인명
    masked_text = _mask_label_names(masked_text, mapping, counters)

    # 4) KLUE-NER (남은 자유 텍스트 보강) — 이미 마스킹된 토큰 구간은 건너뜀
    try:
        entities = sorted(_get_ner()(masked_text), key=lambda e: e["start"], reverse=True)
        for ent in entities:
            prefix = MASK_TYPES.get(ent["entity_group"])
            if not prefix:
                continue
            span = masked_text[ent["start"]:ent["end"]]
            if "[" in span or "]" in span:  # 이미 [TOKEN] 으로 치환된 구간
                continue
            counters[prefix] = counters.get(prefix, 0) + 1
            token = f"[{prefix}_{counters[prefix]:03d}]"
            mapping[token] = span
            masked_text = masked_text[:ent["start"]] + token + masked_text[ent["end"]:]
    except Exception:
        pass

    return {"masked_text": masked_text, "mapping": mapping}


# 시/도로 시작하는 도로명·지번 주소 (NER 보강). 로/길 + 번호 또는 동/읍/면/리 + 번지.
_SIDO = (
    "서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|"
    "경기도|강원특별자치도|충청북도|충청남도|전북특별자치도|전라남도|경상북도|경상남도|제주특별자치도|"
    "서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주"
)
_ADDR_PATTERN = (
    rf"(?:{_SIDO})[가-힣0-9\s]*?"
    r"(?:(?:로|길)\s*\d+[-\d]*|[가-힣]+(?:동|읍|면|리)\s*\d+[-\d]*)"
    r"(?:\s*\d+동)?(?:\s*\d+호)?"
)


# 정형 라벨 뒤 한글 이름(2~4자) — NER이 자주 놓치는 라벨 컨텍스트를 정규식으로 확실히 커버
_NAME_LABEL_PATTERNS = [
    r"(?:성\s*명|이름|대표자?)\s*[:：]?\s*([가-힣]{2,4})",
    r"(?:임대인|임차인|대리인)\s*[(:：]\s*([가-힣]{2,4})",
]


def _mask_label_names(text: str, mapping: dict, counters: dict) -> str:
    """라벨 뒤 인명만 마스킹(라벨 자체는 보존). 이미 [PERSON_xxx]로 치환된 곳은 한글이 아니라 매칭 안 됨."""
    def repl(match: "re.Match") -> str:
        name = match.group(1)
        counters["PERSON"] = counters.get("PERSON", 0) + 1
        token = f"[PERSON_{counters['PERSON']:03d}]"
        mapping[token] = name
        return match.group(0).replace(name, token)

    for pattern in _NAME_LABEL_PATTERNS:
        text = re.sub(pattern, repl, text)
    return text


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

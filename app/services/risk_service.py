"""
리스크 분석 서비스
- RAG: 유사 법률 조항 검색 (ChromaDB + KURE-v1)
- GPT-4o: 독소 조항 탐지 및 심각도 평가
- 규칙 기반: 전세가율 / 등기 / 근저당 감점
"""
import json
import re
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.exceptions import AppException
from app.services.institution_service import get_by_bjd_code
from app.services.masking_service import PAGE_SEPARATOR
from app.services.rag_service import search_relevant_clauses

# ── 감점 기준 ─────────────────────────────────────────────────

_JEONSE_RATIO_DEDUCTIONS = [
    (90, 30),
    (80, 20),
    (70, 10),
]

#_MORTGAGE_RATIO_DEDUCTIONS = [     # TODO: 등기부등본 API 연동 시 복구
#    (30, 20),
#    (10, 10),
#    (0,   5),
#]

_SEVERITY_DEDUCTIONS = {5: 25, 4: 15, 3: 10, 2: 5, 1: 2}

# ── GPT 프롬프트 ──────────────────────────────────────────────

_SYSTEM_PROMPT = """당신은 한국 전세계약서 전문 법률 분석가입니다.
계약서 텍스트에서 임차인에게 불리한 독소 조항을 찾아 심각도와 법적 근거 여부를 평가하세요.

출력 형식 (JSON 배열만 반환, 다른 텍스트 금지):
[
  {
    "clause": "문제 조항의 원문을 그대로 발췌 (요약·의역 금지, [PERSON_001] 같은 토큰도 그대로, 60자 이내로 핵심 문장만)",
    "reason": "왜 문제인지 구체적으로 (150자 이내). 이 조항 때문에 임차인이 실제로 어떤 불이익을 받는지, 법적으로 무효인지 유효한지를 포함",
    "severity": 5,
    "is_legal_basis": true,
    "location": "계약서상 위치. 예: '특약사항 1항', '제9조(계약의 종료)'. 알 수 없으면 null",
    "page": 1,
    "legal_basis": "근거 법령과 조문. 예: '주택임대차보호법 제3조'. 특정할 수 없으면 null"
  }
]

위치 표기:
- 계약서는 '===== 페이지 N =====' 표시로 페이지가 나뉜다. page에는 그 조항이 있는 페이지 번호를 넣는다.
- 본문 조항은 '제N조(제목)', 특약은 '특약사항 N항'으로 쓴다.

심각도(severity) 기준:
5: 계약 즉시 중단 (전입신고 금지, 임의 해지 등 주택임대차보호법 강행규정 위반)
4: 매우 불리 (보증금 감액, 갱신권 포기 등)
3: 불리 (포괄적 수선의무 전가, 과도한 원상복구 등)
2: 주의 (관리비 불명확, 잔금 조건 모호 등)
1: 경미 (표준계약서 미비사항)

is_legal_basis 판단 기준:
- true: 주택임대차보호법 강행규정 위반 (제3, 6의3, 7, 10조 등) → 임차인 동의해도 무효
- false: 민법 위반이지만 임차인 동의 시 유효 (수선의무 전가, 원상복구 등)
- false: 표준계약서 미준수 (강제 아닌 권장사항)
- 판단 모호 시 → false (보수적 분류)

참고 법률 조항에 is_legal_basis가 명시되어 있다면 그 값을 우선 따르세요.

오탐 방지 (정상 조항을 독소로 분류하지 말 것):
- 참고 법률 조항에 예외·조건·임차인 귀책사유가 명시되어 있으면 반드시 반영하라.
- 조건부 해지는 독소가 아니다. 예: "임차인이 2기 이상 차임을 연체한 경우 임대인이 해지" 등 임차인의 귀책사유나 법정 사유에 근거한 해지는 정당하다.
- 주택임대차보호법·표준계약서가 인정하는 표준 조항(2년 임대차 보장, 계약갱신요구권, 분쟁조정 신청, 통상 마모를 제외한 원상복구 등)은 독소가 아니다.
- 조항의 조건을 무시하고 일부 문구만으로 판단하지 마라. 임대인의 권한이 무조건적·일방적일 때만 독소로 본다.

독소 조항이 없으면 빈 배열 []을 반환하세요."""


# ── 공개 API ──────────────────────────────────────────────────

def calculate_risk(
    masked_text: str,
    jeonse_ratio_pct: float,
    is_registered: bool,
    # mortgage_ratio_pct: float = 0.0,    # TODO: 등기부등본 API 연동 시 복구
    bjd_code: Optional[str] = None,
    jeonse_amount: Optional[int] = None,
    sale_price_manwon: Optional[int] = None,
) -> dict:
    """
    리스크 점수 계산

    Args:
        masked_text: 비식별화된 계약서 텍스트
        jeonse_ratio_pct: 전세가율 (예: 83.5)
        is_registered: 건물 등기 여부
        mortgage_ratio_pct: 근저당액/매매가 비율 (예: 25.0)
        bjd_code: 법정동 코드 (기관 추천용)
        jeonse_amount: 계약서 보증금 (원). 전세가율 항목 설명에 금액을 넣는 데만 쓴다
        sale_price_manwon: 실거래 매매가 (만원). 위와 같음

    Returns:
        score, level, issues, action_guide 포함 dict
    """
    # 실거래가 매칭 실패 등으로 전세가율이 None이면 0.0으로 간주
    # (None >= threshold 비교 시 TypeError 방지)
    if jeonse_ratio_pct is None:
        jeonse_ratio_pct = 0.0

    rag_clauses = search_relevant_clauses(masked_text, n_results=5)
    gpt_issues = _analyze_with_gpt(masked_text, rag_clauses)
    public_issues = _build_public_data_issues(
        jeonse_ratio_pct, is_registered, # mortgage_ratio_pct   # TODO: 등기부등본 API 연동 시 복구
        pages=_split_pages(masked_text),
        jeonse_amount=jeonse_amount,
        sale_price_manwon=sale_price_manwon,
    )

    score = _calculate_score(
        jeonse_ratio_pct, 
        is_registered, 
        #mortgage_ratio_pct,    # TODO: 등기부등본 API 연동 시 복구
        gpt_issues
    )
    level = _score_to_level(score, is_registered, jeonse_ratio_pct)
    action_guide = _build_action_guide(level, bjd_code)

    return {
        "score": score,
        "level": level,
        "issues": public_issues + gpt_issues,
        "action_guide": action_guide,
    }


# ── 내부 함수 ─────────────────────────────────────────────────

def _calculate_score(
    jeonse_ratio_pct: float,
    is_registered: bool,
    issues: list[dict],
) -> int:
    # 미등기는 소유권 확인 불가 = 최악의 위험. 다른 항목과 무관하게 0점 고정
    if not is_registered:
        return 0

    deduction = 0

    for threshold, pts in _JEONSE_RATIO_DEDUCTIONS:
        if jeonse_ratio_pct >= threshold:
            deduction += pts
            break

    for issue in issues:
        deduction += _SEVERITY_DEDUCTIONS.get(issue.get("severity", 0), 0)

    return max(0, 100 - deduction)


def _score_to_level(score: int, is_registered: bool, jeonse_ratio_pct: float = 0.0) -> str:
    # 미등기는 점수 무관 강제 danger (소유권 확인 불가 = 보호 불가)
    if not is_registered:
        return "danger"
    # 깡통전세(전세가율 90% 이상)는 점수 무관 강제 danger (전세사기 1순위 신호)
    if jeonse_ratio_pct >= 90:
        return "danger"
    if score >= 90:
        return "safe"
    elif score >= 70:
        return "caution"
    return "danger"


_JEONSE_RISK_TEXT = [
    (90, 5, "90% 이상이면 집이 경매로 넘어갈 때 보증금을 온전히 돌려받기 어려운 깡통전세 위험이 매우 높습니다."),
    (80, 4, "80% 이상이면 집값이 조금만 떨어져도 보증금을 다 돌려받지 못할 수 있습니다."),
    (70, 3, "70% 이상이라 집값이 떨어지면 보증금 회수에 주의가 필요합니다."),
]


def _build_public_data_issues(
    jeonse_ratio_pct: float,
    is_registered: bool,
    pages: Optional[list[str]] = None,
    jeonse_amount: Optional[int] = None,
    sale_price_manwon: Optional[int] = None,
) -> list[dict]:
    """공공데이터 기반 위험요소를 issue 형태로 변환"""
    issues: list[dict] = []

    for threshold, severity, risk_text in _JEONSE_RISK_TEXT:
        if jeonse_ratio_pct >= threshold:
            if jeonse_amount and sale_price_manwon:
                reason = (f"보증금 {_fmt_won(jeonse_amount)}이 최근 실거래 매매가 "
                          f"{_fmt_won(sale_price_manwon * 10_000)}의 {jeonse_ratio_pct:.1f}%입니다. {risk_text}")
            else:
                reason = f"매매가 대비 전세금 비율이 {risk_text}"
            # 원인은 계약서 제1조의 보증금 줄이므로 그 위치를 가리킨다
            page, location = _article_location(pages or [], 1)
            issues.append({
                "clause": f"전세가율 {jeonse_ratio_pct:.0f}%",
                "reason": reason,
                "severity": severity,
                "is_legal_basis": True,
                "location": f"{location} 보증금" if location else None,
                "page": page,
            })
            break

    if not is_registered:
        issues.append({
            "clause": "건물 미등기",
            "reason": "등기부등본이 없어 소유권 확인이 불가능합니다. 대항력·우선변제권 보호를 받을 수 없으므로 계약을 중단하세요.",
            "severity": 5,
            "is_legal_basis": True,
        })

    return issues


def _analyze_with_gpt(masked_text: str, rag_clauses: list[dict]) -> list[dict]:
    # RAG 결과에 is_legal_basis 포함해서 GPT가 참고할 수 있도록 컨텍스트 구성
    rag_context = "\n".join(
        f"[{c['category']}] (is_legal_basis={c.get('is_legal_basis', False)}) {c['content']}"
        for c in rag_clauses
    )
    pages = _split_pages(masked_text)
    # 1페이지에는 구분선이 없으므로 GPT가 페이지를 셀 수 있게 모든 페이지에 표시를 붙인다
    labeled = "".join(PAGE_SEPARATOR.format(n=i) + p for i, p in enumerate(pages, start=1))
    user_message = f"참고 법률 조항:\n{rag_context}\n\n분석할 계약서:{labeled}"

    try:
        llm = ChatOpenAI(
            model=settings.GPT_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0,
        )
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ])
    except Exception as e:
        # 호출 실패(쿼터/네트워크 등)는 빈 결과로 숨기지 말고 502로 드러낸다
        raise AppException(502, "AI_MODULE_ERROR", f"AI 분석 호출 실패: {e}")

    try:
        raw = json.loads(_strip_code_fence(response.content))
    except Exception as e:
        raise AppException(502, "AI_MODULE_ERROR", f"AI 응답 파싱 실패: {e}")

    issues = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        clause = str(item.get("clause", ""))
        # 위치는 계약서 원문에서 직접 찾은 값을 우선한다. 못 찾을 때만 GPT 답을 쓴다.
        found_page, found_location = _locate_clause(clause, pages)
        issues.append({
            "clause": clause,
            "reason": str(item.get("reason", "")),
            "severity": min(5, max(1, int(item.get("severity", 1)))),
            "is_legal_basis": bool(item.get("is_legal_basis", False)),
            "location": found_location or _clean_str(item.get("location")),
            "page": found_page or _valid_page(item.get("page"), len(pages)),
            "legal_basis": _clean_str(item.get("legal_basis")),
        })
    return issues


# ── 조항 위치 찾기 ────────────────────────────────────────────

_PAGE_SPLIT_RE = re.compile(r"\n\n===== 페이지 \d+ =====\n\n")
_ARTICLE_RE = re.compile(r"제(\d+)조(?:\(([^)]{1,20})\))?")
_SPECIAL_RE = re.compile(r"\[?특약사항\]?")
# 공백을 지운 텍스트라 앞 문장의 마침표와 붙는다("있다.2.임대차…"). 앞이 숫자만 아니면 번호로 본다
_SPECIAL_ITEM_RE = re.compile(r"(?<!\d)(\d{1,2})\.(?!\d)")


def _split_pages(masked_text: str) -> list[str]:
    return _PAGE_SPLIT_RE.split(masked_text)


def _compact(text: str) -> str:
    # CLOVA가 단어마다 줄을 바꾸므로 공백·줄바꿈을 모두 지우고 비교한다
    return re.sub(r"\s+", "", text)


def _locate_clause(clause: str, pages: list[str]) -> tuple[Optional[int], Optional[str]]:
    """
    GPT가 발췌한 조항을 계약서 원문(마스킹본)에서 찾아 (페이지, '제N조(제목)' 또는 '특약사항 N항')을 돌려준다.
    원문에서 못 찾으면 (None, None). 단일 페이지 계약서는 페이지만이라도 1로 채운다.
    """
    needle = _compact(clause).strip("\"'“”‘’….")
    # 발췌가 원문과 끝부분이 조금 달라도 찾을 수 있게 앞부분부터 점점 짧게 시도
    for size in (len(needle), 30, 20, 12):
        probe = needle[:size]
        if len(probe) < 8:
            break
        for page_no, page in enumerate(pages, start=1):
            compact = _compact(page)
            pos = compact.find(probe)
            if pos != -1:
                return page_no, _heading_before(compact, pos, page)
    return (1, None) if len(pages) == 1 else (None, None)


def _heading_before(compact: str, pos: int, page: str) -> Optional[str]:
    """원문 위치 pos 직전의 조 제목 또는 특약 번호를 찾는다."""
    before = compact[:pos]
    article = None
    for m in _ARTICLE_RE.finditer(before):
        article = m
    special = None
    for m in _SPECIAL_RE.finditer(before):
        special = m

    # 특약사항 표시가 마지막 조 제목보다 뒤에 있으면 특약 영역
    if special and (article is None or special.start() > article.start()):
        items = list(_SPECIAL_ITEM_RE.finditer(before, special.end()))
        return f"특약사항 {items[-1].group(1)}항" if items else "특약사항"
    if article:
        num = article.group(1)
        # 제목은 띄어쓰기가 남아 있는 원문에서 다시 읽는다 ("계약의종료" → "계약의 종료")
        m = re.search(rf"제\s*{num}\s*조\s*\(([^)]{{1,40}})\)", page)
        title = " ".join(m.group(1).split()) if m else article.group(2)
        return f"제{num}조({title})" if title else f"제{num}조"
    return None


def _article_location(pages: list[str], num: int) -> tuple[Optional[int], Optional[str]]:
    """'제N조(제목)'이 있는 페이지와 표기를 찾는다."""
    for page_no, page in enumerate(pages, start=1):
        m = re.search(rf"제\s*{num}\s*조\s*\(([^)]{{1,40}})\)", page)
        if m:
            return page_no, f"제{num}조({' '.join(m.group(1).split())})"
    return None, None


def _fmt_won(won: int) -> str:
    """2_045_000_000 → '20억 4,500만원'"""
    eok, man = divmod(won // 10_000, 10_000)
    parts = ([f"{eok}억"] if eok else []) + ([f"{man:,}만"] if man else [])
    return " ".join(parts) + "원" if parts else f"{won:,}원"


def _clean_str(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s and s.lower() not in ("null", "none") else None


def _valid_page(value, n_pages: int) -> Optional[int]:
    try:
        p = int(value)
    except (TypeError, ValueError):
        return None
    return p if 1 <= p <= n_pages else None


def _strip_code_fence(text: str) -> str:
    """GPT가 ```json ... ``` 코드펜스로 감싼 경우 제거."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _build_action_guide(level: str, bjd_code: Optional[str]) -> list[dict]:
    guide: list[dict] = []

    if level == "danger":
        guide.append({
            "type": "stop",
            "message": "계약서에 심각한 독소 조항이 발견되었습니다. 즉시 날인을 중단하고 전문가 상담을 받으세요.",
        })
    elif level == "caution":
        guide.append({
            "type": "warning",
            "message": "주의가 필요한 조항이 있습니다. 서명 전 전문가 확인을 권장합니다.",
        })

    if bjd_code:
        institutions = get_by_bjd_code(bjd_code)
        if institutions:
            inst = institutions[0]
            guide.append({
                "type": "institution",
                "name": inst["name"],
                "phone": inst["phone"],
                "region": inst["region"],
                "address": inst.get("address", ""),
            })

    guide.append({
        "type": "legal",
        "message": "전세사기 피해 신고: 경찰청 112 또는 LH콜센터 1600-1004",
    })

    return guide

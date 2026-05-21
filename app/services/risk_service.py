"""
리스크 분석 서비스
- RAG: 유사 법률 조항 검색 (ChromaDB + KURE-v1)
- GPT-4o: 독소 조항 탐지 및 심각도 평가
- 규칙 기반: 전세가율 / 등기 / 근저당 감점
"""
import json
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.services.institution_service import get_by_bjd_code
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
계약서 텍스트에서 임차인에게 불리한 독소 조항을 찾아 심각도를 평가하세요.

출력 형식 (JSON 배열만 반환, 다른 텍스트 금지):
[
  {
    "clause": "문제 조항 원문 또는 요약 (50자 이내)",
    "reason": "위험 이유 및 법적 근거 (100자 이내)",
    "severity": 5
  }
]

심각도 기준:
5: 계약 즉시 중단 (전입신고 금지, 임의 해지 등 주택임대차보호법 강행규정 위반)
4: 매우 불리 (보증금 감액, 갱신권 포기 등)
3: 불리 (포괄적 수선의무 전가, 과도한 원상복구 등)
2: 주의 (관리비 불명확, 잔금 조건 모호 등)
1: 경미 (표준계약서 미비사항)

독소 조항이 없으면 빈 배열 []을 반환하세요."""


# ── 공개 API ──────────────────────────────────────────────────

def calculate_risk(
    masked_text: str,
    jeonse_ratio_pct: float,
    is_registered: bool,
    # mortgage_ratio_pct: float = 0.0,    # TODO: 등기부등본 API 연동 시 복구
    bjd_code: Optional[str] = None,
) -> dict:
    """
    리스크 점수 계산

    Args:
        masked_text: 비식별화된 계약서 텍스트
        jeonse_ratio_pct: 전세가율 (예: 83.5)
        is_registered: 건물 등기 여부
        mortgage_ratio_pct: 근저당액/매매가 비율 (예: 25.0)
        bjd_code: 법정동 코드 (기관 추천용)

    Returns:
        score, level, issues, action_guide 포함 dict
    """
    rag_clauses = search_relevant_clauses(masked_text, n_results=5)
    gpt_issues = _analyze_with_gpt(masked_text, rag_clauses)
    public_issues = _build_public_data_issues(
        jeonse_ratio_pct, is_registered, # mortgage_ratio_pct   # TODO: 등기부등본 API 연동 시 복구
    )

    score = _calculate_score(
        jeonse_ratio_pct, 
        is_registered, 
        #mortgage_ratio_pct,    # TODO: 등기부등본 API 연동 시 복구
        gpt_issues
    )
    level = _score_to_level(score, is_registered)
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
    deduction = 0

    for threshold, pts in _JEONSE_RATIO_DEDUCTIONS:
        if jeonse_ratio_pct >= threshold:
            deduction += pts
            break

    if not is_registered:
        deduction += 30

    for issue in issues:
        deduction += _SEVERITY_DEDUCTIONS.get(issue.get("severity", 0), 0)

    return max(0, 100 - deduction)


def _score_to_level(score: int, is_registered: bool) -> str:
    # 미등기는 점수 무관 강제 danger (소유권 확인 불가 = 보호 불가)
    if not is_registered:
        return "danger"
    if score >= 70:
        return "safe"
    elif score >= 40:
        return "caution"
    return "danger"


def _build_public_data_issues(
    jeonse_ratio_pct: float,
    is_registered: bool,
) -> list[dict]:
    """공공데이터 기반 위험요소를 issue 형태로 변환"""
    issues: list[dict] = []

    if jeonse_ratio_pct >= 90:
        issues.append({
            "clause": f"전세가율 {jeonse_ratio_pct:.0f}%",
            "reason": "매매가 대비 전세금 비율이 90% 이상으로 깡통전세 위험이 매우 높습니다.",
            "severity": 5,
        })
    elif jeonse_ratio_pct >= 80:
        issues.append({
            "clause": f"전세가율 {jeonse_ratio_pct:.0f}%",
            "reason": "매매가 대비 전세금 비율이 80% 이상으로 깡통전세 가능성이 있습니다.",
            "severity": 4,
        })
    elif jeonse_ratio_pct >= 70:
        issues.append({
            "clause": f"전세가율 {jeonse_ratio_pct:.0f}%",
            "reason": "매매가 대비 전세금 비율이 70% 이상으로 주의가 필요합니다.",
            "severity": 3,
        })

    if not is_registered:
        issues.append({
            "clause": "건물 미등기",
            "reason": "등기부등본이 없어 소유권 확인이 불가능합니다. 대항력·우선변제권 보호를 받을 수 없으므로 계약을 중단하세요.",
            "severity": 5,
        })

    return issues


def _analyze_with_gpt(masked_text: str, rag_clauses: list[dict]) -> list[dict]:
    rag_context = "\n".join(
        f"[{c['category']}] {c['content']}" for c in rag_clauses
    )
    user_message = f"참고 법률 조항:\n{rag_context}\n\n분석할 계약서:\n{masked_text}"

    try:
        llm = ChatOpenAI(
            model="gpt-4o",
            api_key=settings.OPENAI_API_KEY,
            temperature=0,
        )
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ])
        raw = json.loads(response.content)
        return [
            {
                "clause": str(item.get("clause", "")),
                "reason": str(item.get("reason", "")),
                "severity": min(5, max(1, int(item.get("severity", 1)))),
            }
            for item in raw
            if isinstance(item, dict)
        ]
    except Exception:
        return []


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

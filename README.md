# Guard Up Backend

**안심 계약 가디언** 백엔드 서버 — 자립준비청년을 위한 전세 계약서 분석 서비스

## 주요 기능

계약서 이미지를 받아 4단계 파이프라인으로 분석합니다.

1. **OCR + 비식별화** (`POST /api/analyze/image`) — CLOVA OCR로 계약서 텍스트 추출 후, KLUE-NER + 정규식으로 성명·주소 등 개인정보를 마스킹
2. **주소 검증** (`POST /api/verify/address`) — 도로명주소 공공 API로 주소 유효성 확인 및 법정동 코드 반환
3. **건물 정보 조회** (`POST /api/building`) — 건축물대장·국토부 실거래가·HUG 전세보증 API로 근저당·등기 현황·전세가율·보증 가능 여부 조회
4. **리스크 스코어링** (`POST /api/analyze/risk`) — 마스킹된 계약서 텍스트 + 공공 데이터를 GPT-4o + RAG(ChromaDB + KURE-v1)로 분석하여 독소 조항 탐지 및 위험 점수(0~100, 낮을수록 위험) 산출

Redis 세션(UUID v4, 30분 TTL)으로 단계 간 상태를 유지합니다. 개인정보 매핑 테이블은 리스크 분석 완료 후 즉시 삭제되며, GPT-4o에는 실명·주소가 전달되지 않습니다.

## 기술 스택

| 영역 | 라이브러리 |
|---|---|
| 웹 프레임워크 | FastAPI + Uvicorn |
| 스키마 검증 | Pydantic v2 |
| OCR | CLOVA OCR |
| NER 비식별화 | KLUE-NER + 정규식 |
| 벡터 검색 | ChromaDB + KURE-v1 |
| LLM | GPT-4o (LangChain) |
| 세션 저장소 | Redis (async) |
| 공공 API | 도로명주소, 건축물대장, 국토부 실거래가, HUG 전세보증 |

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/api/analyze/image` | OCR + 비식별화 → `session_id` 반환 |
| `POST` | `/api/verify/address` | 주소 유효성 검증 및 표준화 |
| `POST` | `/api/building` | 건물 정보 + 전세보증 가능 여부 조회 |
| `POST` | `/api/analyze/risk` | 위험 점수 + 독소 조항 탐지 |
| `GET` | `/api/health` | 서비스 상태 확인 |

현재 모든 엔드포인트는 목 데이터를 반환합니다. 실제 서비스 연동은 다음 단계에서 진행합니다.

## 프로젝트 구조

```
app/
├── api/          # 라우터 (엔드포인트 그룹별 파일)
├── core/
│   ├── config.py     # .env 환경 변수 설정 (pydantic-settings)
│   ├── exceptions.py # AppException — 구조화된 에러 응답
│   └── session.py    # Redis 세션 헬퍼 + 키 상수
└── schemas/      # Pydantic 요청/응답 모델
```

## 환경 설정

```bash
# Python 버전 설정 (pyenv 필요)
pyenv install 3.13.3
pyenv local 3.13.3

# 가상 환경
python -m venv .venv
source .venv/bin/activate

# 패키지 설치
pip install -r requirements.txt

# 환경 변수
cp .env.example .env
# .env 파일에 API 키 입력
```

## 실행

```bash
uvicorn app.main:app --reload
```

API 문서: `http://localhost:8000/docs`

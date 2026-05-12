develop
# Guard Up Backend

> 자립준비청년을 위한 전세 계약서 분석 서비스 — **안심 계약 가디언** 백엔드

---

## 서비스 소개

전세 계약서 사진을 찍어 올리면 AI가 자동으로 분석해서 위험도를 알려주는 서비스입니다.

```
계약서 사진 업로드
      ↓
텍스트 추출 (OCR)
      ↓
개인정보 마스킹 (이름·주소 가림)
      ↓
주소 검증 + 건물 정보 조회 (공공 API)
      ↓
독소 조항 탐지 + 위험도 점수 산출 (GPT-4o + RAG)
      ↓
결과 반환 → Flutter 앱에서 표시
```

---

## 주요 기능

| 기능 | 설명 |
|---|---|
| OCR | CLOVA OCR로 계약서 텍스트 추출. JPG/PNG/HEIC 등 모든 이미지 포맷 지원 |
| 개인정보 마스킹 | KLUE-NER(AI 모델)로 이름·주소·기관명 탐지 후 `[PERSON_001]` 형태로 치환. 주민번호·전화번호는 정규식으로 추가 처리 |
| 주소 검증 | 도로명주소 공공 API로 주소 유효성 확인 및 법정동 코드 반환 |
| 건물 정보 조회 | 건축물대장·국토부 실거래가 API로 건물 현황·전세가율 계산 |
| 독소 조항 탐지 | 주택임대차보호법·전세사기 판례를 벡터 DB에 저장해두고, 계약서 내용과 비교해 위험 조항 탐지 |
| 위험도 점수 | 0~100점 (낮을수록 위험). 전세가율·근저당·독소 조항 심각도를 종합해 계산 |
| 개인정보 보호 | GPT-4o에는 마스킹된 텍스트만 전달. 분석 완료 후 매핑 테이블 즉시 삭제 |
| 기관 안내 | 위험 계약서 발견 시 지역별 자립지원 전담기관 자동 안내 |

---

## 기술 스택

| 분류 | 기술 |
|---|---|
| 웹 프레임워크 | FastAPI + Uvicorn |
| 데이터 검증 | Pydantic v2 |
| OCR | CLOVA OCR (NAVER Cloud) |
| 이미지 처리 | Pillow + pillow-heif (HEIC 포함 모든 포맷 → JPG 변환) |
| 개인정보 마스킹 | KLUE-NER (`Leo97/KoELECTRA-small-v3-modu-ner`) + 정규식 |
| 벡터 검색 (RAG) | ChromaDB + KURE-v1 (`nlpai-lab/KURE-v1`) |
| LLM | GPT-4o (LangChain) |
| 세션 관리 | Redis (UUID v4, 30분 TTL) |
| 공공 API | 도로명주소, 건축물대장, 국토부 실거래가 |

---

## API 엔드포인트

| 단계 | 메서드 | 경로 | 설명 |
|---|---|---|---|
| 1 | POST | `/api/analyze/image` | 계약서 이미지 분석 (OCR + 마스킹) |
| 2 | POST | `/api/verify/address` | 주소 검증 |
| 3 | POST | `/api/building` | 건물 정보 + 전세가율 조회 |
| 4 | POST | `/api/analyze/risk` | 위험도 분석 결과 반환 |
| - | POST | `/api/institution` | 지역별 자립지원 기관 조회 |
| - | GET | `/api/health` | 서비스 상태 확인 |

---

## 프로젝트 구조

```
app/
├── api/            # 엔드포인트 (라우터)
├── core/
│   ├── config.py       # 환경 변수 설정
│   ├── exceptions.py   # 공통 에러 처리
│   └── session.py      # Redis 세션 관리
├── schemas/        # 요청·응답 데이터 모델
└── services/       # 실제 비즈니스 로직
    ├── ocr_service.py          # CLOVA OCR 호출
    ├── masking_service.py      # 개인정보 마스킹
    ├── public_api_service.py   # 공공 API 연동
    ├── rag_service.py          # 벡터 검색
    ├── risk_service.py         # 위험도 분석·스코어링
    └── institution_service.py  # 기관 정보 조회

data/
├── legal_docs/     # RAG용 법령·판례·독소조항 데이터 (JSON)
└── institutions.json  # 지역별 자립지원 기관 목록
```

---

## 시작하기

### 1. Python 버전 설정

```bash
pyenv install 3.13.3
pyenv local 3.13.3
```

### 2. 가상 환경 생성 및 패키지 설치

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에 API 키 입력
```

```env
CLOVA_OCR_INVOKE_URL=   # NAVER Cloud CLOVA OCR Invoke URL
CLOVA_OCR_SECRET=       # CLOVA OCR Secret Key
OPENAI_API_KEY=         # OpenAI API Key
ROAD_ADDRESS_API_KEY=   # 도로명주소 API Key
MOLIT_API_KEY=          # 국토부 실거래가 API Key
REDIS_URL=redis://localhost:6379
SESSION_TTL=1800
```

### 4. Redis 실행

```bash
# Mac
brew install redis && brew services start redis

# Docker
docker run -d -p 6379:6379 redis
```

### 5. 서버 실행

```bash
uvicorn app.main:app --reload
```

서버가 켜지면 법령 데이터가 ChromaDB에 자동으로 적재됩니다.

API 문서: http://localhost:8000/docs

---

## 위험도 점수 기준

| 점수 | 등급 | 의미 |
|---|---|---|
| 70 ~ 100 | 🟢 safe | 안전한 계약서 |
| 40 ~ 69 | 🟡 caution | 주의 필요 |
| 0 ~ 39 | 🔴 danger | 계약 중단 권고 |

점수는 전세가율·근저당 금액·독소 조항 심각도(1~5등급)를 종합해 산출합니다.

---

## 개인정보 처리 흐름

```
원문 텍스트: "임대인 홍길동, 주소 서울시 강남구..."
         ↓ 마스킹
마스킹 텍스트: "임대인 [PERSON_001], 주소 [ADDR_001]..."
         ↓ GPT-4o 분석 (마스킹 텍스트만 전달)
         ↓ 분석 완료
매핑 테이블 삭제 → mapping_table_purged: true
```

GPT-4o에는 실명·주소가 절대 전달되지 않습니다.
=======
# Guard_Up_Backend
안심 계약 가디언 백엔드 서버 | FastAPI 기반 OCR·비식별화·RAG·공공API 파이프라인
main

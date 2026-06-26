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
| OCR | CLOVA OCR로 계약서 텍스트 추출. JPG/PNG/HEIC 등 모든 이미지 포맷 자동 변환 후 처리 |
| 개인정보 마스킹 | KLUE-NER로 이름·주소·기관명 탐지 후 `[PERSON_001]` 형태로 치환. 주민번호·전화번호는 정규식으로 추가 처리 |
| 주소 검증 | 도로명주소 공공 API로 주소 유효성 확인 및 법정동 코드 반환 |
| 건물 정보 조회 | 건축물대장·국토부 실거래가 API로 건물 정보 + 전세가율 자동 계산 (만원→원 단위 환산 포함) |
| 독소 조항 탐지 | 주임법·표준계약서·전세사기 판례 46개 항목을 벡터 DB에 적재하고, 계약서 내용과 비교해 위험 조항 탐지 |
| 법적 근거 분류 | 각 위험 항목을 **법적 위반(강행규정 위반)** / **개인 체크 권장(임차인 판단 영역)**으로 분류 표시 |
| 위험도 점수 | 0~100점 (낮을수록 위험). 전세가율·등기 여부·독소 조항 심각도를 종합 |
| 미등기 강제 차단 | 미등기 건물 감지 시 점수 무관 강제 `danger` 등급으로 처리 |
| 개인정보 보호 | GPT-4o에는 마스킹된 텍스트만 전달. 분석 완료 후 매핑 테이블 즉시 삭제 |
| 기관 안내 | 위험 계약서 발견 시 지역별 자립지원 전담기관 자동 안내 |

---

## 기술 스택

| 분류 | 기술 |
|---|---|
| 웹 프레임워크 | FastAPI + Uvicorn |
| 데이터 검증 | Pydantic v2 |
| OCR | CLOVA OCR (NAVER Cloud) |
| 이미지 처리 | Pillow + pillow-heif |
| 개인정보 마스킹 | KLUE-NER (`Leo97/KoELECTRA-small-v3-modu-ner`) + 정규식 |
| 벡터 검색 (RAG) | ChromaDB + KURE-v1 (`nlpai-lab/KURE-v1`) |
| LLM | GPT-4o (LangChain) |
| 세션 관리 | Redis (UUID v4, 30분 TTL) |
| 공공 API | 도로명주소, 건축물대장, 국토부 실거래가 (아파트/연립다세대/오피스텔) |

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

서버 실행 후 `http://localhost:8000/docs`에서 Swagger UI로 상세 스키마 확인 가능.

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
└── services/       # 비즈니스 로직
    ├── ocr_service.py          # CLOVA OCR 호출
    ├── masking_service.py      # 개인정보 마스킹
    ├── public_api_service.py   # 공공 API 연동
    ├── rag_service.py          # ChromaDB 벡터 검색
    ├── risk_service.py         # 위험도 분석·스코어링
    └── institution_service.py  # 기관 정보 조회

data/
├── legal_docs/                       # RAG 학습 데이터 (총 46개 항목)
│   ├── housing_lease_law.json        #  주임법 조문 12개
│   ├── standard_contract_guide.json  #  표준계약서 가이드 12개
│   ├── toxic_clauses.json            #  독소 조항 패턴 12개
│   └── fraud_cases.json              #  전세사기 판례 10개
└── institutions.json                 # 지역별 자립지원 기관 목록
```

---

## 시작하기

### 1. Python 가상 환경 + 패키지 설치

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에 API 키 입력
```

`.env` 필수 항목:

```env
CLOVA_OCR_INVOKE_URL=   # NAVER Cloud CLOVA OCR Invoke URL
CLOVA_OCR_SECRET=       # CLOVA OCR Secret Key
OPENAI_API_KEY=         # OpenAI API Key (GPT-4o)
ROAD_ADDRESS_API_KEY=   # 도로명주소 API Key
BUILDING_API_KEY=       # 건축물대장 API Key (data.go.kr)
MOLIT_API_KEY=          # 국토부 실거래가 API Key (data.go.kr)
REDIS_URL=redis://localhost:6379
SESSION_TTL=1800
```

⚠️ `.env`는 `.gitignore`에 포함되어 있어 절대 커밋되지 않습니다. 실제 키는 `.env`에만 작성하세요.

### 3. Redis 실행

```bash
# macOS
brew install redis && brew services start redis

# Docker
docker run -d --restart=always -p 6379:6379 --name redis redis
```

확인:
```bash
redis-cli ping
# → PONG
```

### 4. 서버 실행

```bash
uvicorn app.main:app --reload
```

첫 실행 시 KURE-v1 임베딩 모델(약 2.3GB) 자동 다운로드 → ChromaDB에 법령 데이터 46개 적재 → 서버 시작. 두 번째부터는 캐시되어 즉시 시작합니다.

- API 문서: `http://localhost:8000/docs`

---

## 위험도 점수 기준

| 점수 | 등급 | 의미 |
|---|---|---|
| 90 ~ 100 | 🟢 safe | 안심 |
| 70 ~ 89 | 🟡 caution | 주의 |
| 0 ~ 69 | 🔴 danger | 위험 (계약 중단 권고) |

### 감점 항목

| 항목 | 감점 |
|---|---|
| 전세가율 70~80% | -10 |
| 전세가율 80~90% (HUG 보증 한도 임박) | -20 |
| 전세가율 90% 이상 (깡통전세) | -30 (+ 점수 무관 강제 `danger`) |
| 미등기 건물 | -30 (+ 점수 무관 강제 `danger`) |
| 독소 조항 severity 5 (강행규정 위반) | -25 |
| 독소 조항 severity 4 | -15 |
| 독소 조항 severity 3 | -10 |
| 독소 조항 severity 2 | -5 |
| 독소 조항 severity 1 | -2 |

### 법적 근거 분류 (`is_legal_basis`)

각 위험 항목에 분류 표시:

- **`true` (법적 위반)** — 주택임대차보호법 강행규정 위반. 임차인 동의해도 법적으로 무효
- **`false` (개인 체크 권장)** — 민법 영역 또는 표준계약서 미준수. 임차인 동의 시 유효, 사용자 판단 영역

RAG 학습 데이터(46개) 중 32개는 법적 위반, 14개는 개인 체크 권장으로 사전 분류되어 있습니다.

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

- 계약서 이미지는 서버에 저장되지 않고 메모리에서 처리 후 즉시 폐기
- 개인정보 매핑 테이블은 Redis에 세션 TTL(30분)로 자동 만료
- 분석 완료 시점에 매핑 테이블 즉시 파기 (`purge_mapping`)
- GPT-4o에는 실명·주소가 절대 전달되지 않음

---

## 분석 한계 및 면책 사항

본 서비스는 참고용 분석 도구이며 법률 자문이 아닙니다. 다음 항목은 사용자 직접 확인이 필요합니다.

| 항목 | 사유 | 사용자 확인 방법 |
|---|---|---|
| 근저당 / 가압류 | 등기부등본 API 미연동 (유료, 별도 신청) | 인터넷등기소(iros.go.kr)에서 등기부등본 발급 |
| 임대인 신원 | 자동 검증 불가 | 임대인 신분증과 등기부등본 소유자 정보 대조 |
| 전세보증보험 가입 가능 여부 | 보증기관별 정책 상이 | HUG / SGI에 직접 문의 |

또한 위험도 점수의 가중치는 현재 데모 단계의 자체 설계로, 향후 변호사 자문 및 샘플 캘리브레이션으로 보강할 예정입니다.

---

## 브랜치 전략

| 브랜치 | 용도 |
|---|---|
| `main` | 배포 가능한 안정 버전 |
| `develop` | 통합 개발 브랜치 |
| `feature/*` | 기능 단위 작업 브랜치 |
| `fix/*` | 버그 수정 브랜치 |
| `chore/*` | 빌드/설정/리팩토링 브랜치 |

작업 후 GitHub PR을 통해 `develop`으로 머지합니다.

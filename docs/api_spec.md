# 안심 계약 가디언 API 명세서 (실서버 반영본)

> 이 문서는 실제 구현된 백엔드(`http://localhost:8000/docs`)와 1:1로 맞춘 버전입니다.
> 기존 노션 명세 대비 **🔄 변경**으로 표시된 부분만 다릅니다.

---

# 1. 개요

- **Base URL** : `http://localhost:8000/api`
- **Content-Type** : `application/json`
  단, `POST /api/analyze/image` 는 `multipart/form-data`

## 설계 원칙

| 원칙 | 내용 |
| --- | --- |
| 로컬 저장 방식 | 분석 내역은 서버에 저장하지 않으며, 클라이언트(디바이스) 로컬 스토리지에서 관리 (Flutter: sqflite/shared_preferences) |
| Privacy-First | 분석 완료 후 매핑 테이블(개인정보) 즉시 파기. 마스킹 데이터만 외부 API에 전달 |
| 자립지원기관 연결 | 외부 API 미사용. 서버 내부 DB(`data/institutions.json`)에 기관 목록 저장 후 법정동 코드 기반 매칭하여 action_guide에 포함 |

## 처리 흐름

1단계 이미지 분석 → 2단계 주소 검증 → 3단계 건물 정보 조회 → 4단계 AI 리스크 분석

## Redis 세션 구조

```
session:{uuid} = {
  # 1단계
  "ocr_text": str,
  "masked_text": str,
  "mapping": dict,           # 분석 완료 후 null로 파기
  "raw_address": str,
  "jeonse_amount": int,      # OCR 텍스트에서 자동 추출 (한글/콤마/단위 모두 인식)

  # 2단계
  "road_address": str,
  "bjd_code": str,
  "jibun_address": str,

  # 3단계
  "building": {
    "building_name": str,
    "is_registered": bool,
    "sale_price": int,       # 실거래 있을 때만 (단위: 만원)
    "jeonse_ratio": str      # sale_price 있을 때만
  },

  # 단계 완료 추적
  "steps_completed": [1, 2, 3]
}
```

> 🔄 **변경**: `building`에서 `owner_type`, `mortgage_amount`, `build_year`는 세션에 저장하지 않음
> (근저당/소유형태는 등기부등본 API 미연동, `build_year`는 응답에만 포함).

---

# 2. API 엔드포인트 상세

## 2-1. 계약서 이미지 분석 (1단계)

### `POST /api/analyze/image`

계약서 사진을 받아 OCR 처리 및 개인정보 비식별화를 수행하고 `session_id`를 발급.
세션은 UUID v4로 생성되어 Redis에 30분 TTL로 저장됩니다.

**요청 (multipart/form-data)**

| 필드명 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| file | file | 필수 | 계약서 이미지 파일 (JPG/PNG/HEIC 등) |

**응답 (200)**

| 필드명 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| session_id | string | 필수 | 이후 단계에서 사용할 세션 식별자 |
| ocr_text | string | 필수 | OCR로 추출된 원본 텍스트 |
| masked_text | string | 필수 | 개인정보가 마스킹된 텍스트 |
| address | string\|null | 선택 | 계약서에서 추출된 주소 (없으면 null) |

**에러 응답**

| HTTP | error_code | 설명 |
| --- | --- | --- |
| 400 | INVALID_IMAGE | 지원하지 않는 이미지 형식 |
| 422 | OCR_FAILED | CLOVA OCR 처리 실패 / 텍스트 추출 불가 |
| 500 | SERVER_ERROR | 서버 내부 오류 |

---

## 2-2. 주소 검증 (2단계)

### `POST /api/verify/address`

도로명주소 공공 API로 계약서상 주소의 유효성을 검증합니다.

**요청 (Request Body)**

| 필드명 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| session_id | string | 필수 | 1단계에서 발급된 세션 식별자 |
| address | string | 필수 | 검증할 주소 문자열 |

**응답 (200)**

| 필드명 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| is_valid | boolean | 필수 | 주소 유효성 여부 |
| road_address | string\|null | 선택 | 정제된 도로명주소 |
| jibun_address | string\|null | 선택 | 지번 주소 |
| zip_code | string\|null | 선택 | 우편번호 |
| bjd_code | string\|null | 선택 | 법정동 코드 (자립지원기관 매칭 및 이후 단계 사용) |

**에러 응답**

| HTTP | error_code | 설명 |
| --- | --- | --- |
| 400 | INVALID_SESSION | 유효하지 않은 session_id |
| 404 | ADDRESS_NOT_FOUND | 주소를 찾을 수 없음 |
| 502 | PUBLIC_API_ERROR | 도로명주소 공공 API 호출 실패 |

---

## 2-3. 건물 정보 조회 (3단계)

### `POST /api/building`

건축물대장·국토부 실거래가 API로 건물 정보와 전세가율을 조회합니다.

**요청 (Request Body)**

| 필드명 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| session_id | string | 필수 | 1단계에서 발급된 세션 식별자 |

> 🔄 **변경**: `road_address`는 **보내지 않아도 됩니다.** 서버가 2단계에서 저장한 세션 값을 사용합니다.

**응답 (200)**

| 필드명 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| building_name | string\|null | 선택 | 건물명 |
| build_year | number\|null | 선택 | 건축연도 |
| is_registered | boolean | 필수 | 등기(건축물대장 등재) 여부 |
| sale_price | number\|null | 선택 | 최근 매매 실거래가 (**단위: 만원**). 실거래 없을 수 있음 |
| jeonse_ratio | string\|null | 선택 | 전세가율 (예: "83.0%"). sale_price 없으면 null |

> 🔄 **변경**: `owner_type`, `mortgage_amount`는 **현재 미제공** (등기부등본 API 미연동, 추후 추가 예정).

**에러 응답**

| HTTP | error_code | 설명 |
| --- | --- | --- |
| 400 | INVALID_SESSION | 유효하지 않은 session_id / 2단계 미완료 |
| 502 | PUBLIC_API_ERROR | 건축물대장·국토부 API 호출 실패 |

> 🔄 **변경**: `BUILDING_NOT_FOUND`(404) **미사용**.
> 건물 미등기·정보 없음이어도 404로 막지 않고 4단계까지 진행하며, 4단계에서 **점수 0점·danger**로 처리됩니다.
> (`is_registered: false`로 응답되니, Flutter는 이 값으로 미등기 경고를 표시하면 됩니다.)

---

## 2-4. AI 리스크 분석 (4단계)

### `POST /api/analyze/risk`

세션에 축적된 모든 정보를 기반으로 RAG 파이프라인을 통해 위험도를 분석하고 액션 가이드를 제공합니다.

**요청 (Request Body)**

| 필드명 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| session_id | string | 필수 | 1단계에서 발급된 세션 식별자 |

**응답 (200)**

| 필드명 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| score | number | 필수 | 위험 점수 (0~100, 낮을수록 위험). **미등기 시 0점 고정** |
| level | string | 필수 | "safe"(70~100) / "caution"(40~69) / "danger"(0~39) |
| issues | array | 필수 | 위험 조항 목록 |
| issues[].clause | string | 필수 | 위험 조항 원문/요약 |
| issues[].reason | string | 필수 | 위험 이유 설명 |
| issues[].severity | number | 필수 | 심각도 (1~5) |
| issues[].is_legal_basis | boolean | 필수 | 🆕 **법적 위반 여부**. true=강행규정 위반(동의해도 무효) / false=개인 체크 권장 |
| action_guide | array | 필수 | 사용자 권고 액션 목록 (아래 상세) |
| public_data | object | 필수 | 공공 데이터 요약 |
| public_data.jeonse_ratio | string | 필수 | 전세가율 (예: "83.0%", 없으면 "정보 없음") |
| public_data.is_registered | boolean | 필수 | 등기 여부 |
| mapping_table_purged | boolean | 필수 | 분석 후 개인정보 매핑 테이블 파기 여부 (항상 true) |

> 🆕 **추가**: `issues[].is_legal_basis` — Flutter에서 true면 "법적 위반(빨강)", false면 "개인 확인 권장(노랑)" 등으로 구분 표시 권장.
> 🔄 **변경**: `public_data.mortgage_amount`는 **현재 미제공** (등기부등본 API 미연동).

### action_guide 상세

각 항목은 `type` 필드로 구분됩니다.

| type | 필드 | 설명 | 발생 조건 |
| --- | --- | --- | --- |
| **stop** | message | 즉시 날인 중단 안내 | level=danger |
| **warning** | message | 🆕 서명 전 전문가 확인 권장 | level=caution |
| **institution** | name, phone, region, address | 자립지원기관 (법정동 코드 매칭) | bjd_code로 기관 매칭 시 |
| **legal** | message | 법률 상담 안내 (항상 포함) | 항상 |

> 🆕 **추가**: `warning` 타입 — caution 등급에서 나옵니다. Flutter가 `stop`/`institution`/`legal`만 처리하면 이 항목이 누락되니 **`warning`도 핸들링 필요**.

**action_guide 예시 (danger)**

```json
"action_guide": [
  { "type": "stop", "message": "계약서에 심각한 독소 조항이 발견되었습니다. 즉시 날인을 중단하고 전문가 상담을 받으세요." },
  { "type": "institution", "name": "서울 자립지원 전담기관", "phone": "02-000-0000", "region": "서울특별시", "address": "서울시 종로구 OO로 00" },
  { "type": "legal", "message": "전세사기 피해 신고: 경찰청 112 또는 LH콜센터 1600-1004" }
]
```

**에러 응답**

| HTTP | error_code | 설명 |
| --- | --- | --- |
| 400 | INVALID_SESSION | 유효하지 않은 session_id / masked_text 없음 |
| 424 | PREREQUISITE_FAILED | 이전 단계(2 주소검증·3 건물조회) 미완료 |
| 500 | SERVER_ERROR | 서버 내부 오류 |

---

## 2-5. 자립지원기관 조회

### `POST /api/institution`

지역명 기반으로 자립지원 전담기관 목록을 조회합니다. 서버 내부 JSON(`data/institutions.json`)에서 조회.

**요청 (Request Body)**

| 필드명 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| region | string | 필수 | 지역명 (예: "서울특별시") — 17개 광역시도 정식 명칭 |

**응답 (200)**

| 필드명 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| region | string | 필수 | 조회된 지역명 |
| institutions | array | 필수 | 기관 목록 |
| institutions[].id | string | 필수 | 기관 ID |
| institutions[].name | string | 필수 | 기관명 |
| institutions[].region | string | 필수 | 관할 지역 |
| institutions[].phone | string | 필수 | 전화번호 |
| institutions[].address | string | 필수 | 주소 |

**에러 응답**

| HTTP | error_code | 설명 |
| --- | --- | --- |
| 404 | REGION_NOT_FOUND | 해당 지역의 기관 정보 없음 |

---

## 2-6. 서버 상태 확인 (헬스체크)

### `GET /api/health`

서버 및 외부 API 실제 연결 상태를 확인합니다. (호출 시 외부 API에 실제 핑 → 응답에 1~3초 소요)

**응답 (200)**

| 필드명 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| status | string | 필수 | "ok"(전부 정상) / "degraded"(일부) / "down"(전부 실패) |
| ocr_api | boolean | 필수 | CLOVA OCR 연결 여부 |
| address_api | boolean | 필수 | 도로명주소 API 연결 여부 |
| building_api | boolean | 필수 | 건축물대장/국토부 API 연결 여부 |
| ai_module | boolean | 필수 | OpenAI(GPT-4o) 연결 여부 |
| institution_db | boolean | 필수 | 자립지원기관 내부 DB 로드 여부 |

---

# 3. 전체 에러 코드 → 화면 매핑

| # | error_code | HTTP | 발생 단계 | 사용자 메시지 | 다이얼로그 |
| --- | --- | --- | --- | --- | --- |
| 1 | INVALID_IMAGE | 400 | 1 이미지 | 지원하지 않는 이미지 형식이에요. 다른 사진을 선택해주세요. | B (다시 시작) |
| 2 | OCR_FAILED | 422 | 1 이미지 | 계약서 텍스트를 추출하지 못했어요. 더 선명한 사진으로 다시 시도해주세요. | B (다시 시작) |
| 3 | INVALID_SESSION | 400 | 2~4 | 세션이 만료되었어요. 처음부터 다시 시도해주세요. | B (다시 시작) |
| 4 | ADDRESS_NOT_FOUND | 404 | 2 주소 | 계약서의 주소 정보를 찾을 수 없어요. 사진을 다시 확인해주세요. | B (다시 시작) |
| 5 | PUBLIC_API_ERROR | 502 | 2~3 | 공공 데이터 서비스가 일시적으로 불안정해요. 잠시 후 다시 시도해주세요. | A (재시도) |
| 6 | PREREQUISITE_FAILED | 424 | 4 리스크 | 이전 단계가 완료되지 않았어요. 처음부터 다시 시도해주세요. | B (다시 시작) |
| 7 | REGION_NOT_FOUND | 404 | 기관 조회 | 해당 지역의 자립지원 기관 정보가 없어요. | (알림만) |
| 8 | SERVER_ERROR | 500 | 어디든 | 일시적인 오류가 발생했어요. 잠시 후 다시 시도해주세요. | A (재시도) |
| - | (네트워크 끊김) | - | 어디든 | 인터넷 연결을 확인해주세요. | A (재시도) |

> 🔄 **변경**: `BUILDING_NOT_FOUND`(404), `AI_MODULE_ERROR`(502)는 현재 서버에서 발생하지 않음
> (미등기는 정상 진행, AI 오류는 빈 결과로 폴백). Flutter 매핑에서 제외 가능.

---

# 4. 공통 에러 응답 포맷

모든 에러는 아래 형태로 반환됩니다.

```json
{ "error_code": "INVALID_SESSION", "message": "세션이 만료되었거나 존재하지 않습니다." }
```

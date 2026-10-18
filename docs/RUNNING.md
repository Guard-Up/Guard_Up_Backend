# 로컬에서 서버 켜고 테스트하기

백엔드를 직접 띄워서 계약서 한 장을 넣고 결과까지 보는 방법을 정리한다. VS Code 터미널에서 그대로 하면 되고, 터미널을 두 개 쓴다. 하나는 서버를 계속 띄워두는 용도, 다른 하나는 계약서를 던지는 용도다.

## 사전 준비

처음 한 번만 해두면 된다.

- 가상환경과 패키지: `python -m venv .venv` 후 `.venv/bin/pip install -r requirements.txt`
- Redis 실행 확인: `redis-cli ping` 을 쳐서 `PONG` 이 나오면 된다 (안 떠 있으면 `brew services start redis`)
- `.env` 에 API 키가 채워져 있어야 한다 (CLOVA, OpenAI, 공공API)

## 1. 서버 켜기 (터미널 A)

```bash
.venv/bin/uvicorn app.main:app --reload
```

`Application startup complete` 가 뜨면 준비된 것이다. 이 터미널은 그대로 둔다. 끄려면 여기서 Ctrl+C.

`--reload` 는 코드를 고치면 서버가 자동으로 다시 뜨게 해주는 개발용 옵션이다. 배포할 때는 뺀다.

## 2. 계약서 분석하기 (터미널 B)

터미널을 하나 더 연다(VS Code 터미널 패널의 `+`). 두 가지 방법이 있다.

### 스크립트로 한 번에 보기

```bash
.venv/bin/python tests/run_pipeline.py tests/fixtures/sample_contract_standard.png
```

1단계 OCR·마스킹 → 2단계 주소 → 3단계 건물·전세가율 → 4단계 위험도까지 한 번에 출력된다. 뒤의 파일만 바꾸면 다른 계약서로 테스트할 수 있고, 어떤 계약서가 무엇을 검증하는지는 `tests/fixtures/FIXTURES.md` 에 정리돼 있다.

### Swagger로 버튼 눌러 보기

브라우저에서 `http://localhost:8000/docs` 를 연다. 엔드포인트마다 "Try it out" 으로 직접 호출하고 응답을 확인할 수 있다. 1단계에서 이미지를 올리면 나오는 `session_id` 를 2~4단계에 넣으면 된다.

## 모델 바꾸기 (비용 조절)

GPT 모델은 `.env` 의 `GPT_MODEL` 로 정해진다.

- 테스트는 `gpt-4o-mini` (건당 1~2원 수준)
- 발표·최종 확인은 `gpt-4o`

`.env` 를 고친 뒤에는 서버를 다시 띄워야 반영된다 (시작할 때 한 번 읽기 때문).

## 돈이 나가는 곳

- 4단계 위험도 분석이 OpenAI(GPT)를 호출한다 — 여기만 모델에 따라 과금
- 1단계 OCR은 CLOVA
- 2·3단계 공공 API(주소·건물·실거래가)는 무료
- 마스킹·RAG 검색은 로컬에서 도므로 무료

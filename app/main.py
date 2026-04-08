from fastapi import FastAPI
from app.api import ocr, masking, public_api, analyze, risk

app = FastAPI(
    title="안심 계약 가디언 API",
    description="계약서 OCR·비식별화·RAG 분석·리스크 스코어링 백엔드",
    version="0.1.0",
)

app.include_router(ocr.router, prefix="/ocr", tags=["OCR"])
app.include_router(masking.router, prefix="/masking", tags=["비식별화"])
app.include_router(public_api.router, prefix="/public", tags=["공공API"])
app.include_router(analyze.router, prefix="/analyze", tags=["RAG분석"])
app.include_router(risk.router, prefix="/risk", tags=["리스크"])

@app.get("/")
def health_check():
    return {"status": "ok", "service": "ansi-backend"}
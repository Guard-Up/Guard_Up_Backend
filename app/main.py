from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import address, analyze, building, health, institution
from app.core.exceptions import AppException

app = FastAPI(
    title="안심 계약 가디언 API",
    description="계약서 OCR·비식별화·RAG 분석·리스크 스코어링 백엔드",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "message": exc.message},
    )


app.include_router(analyze.router, prefix="/api")
app.include_router(address.router, prefix="/api")
app.include_router(building.router, prefix="/api")
app.include_router(institution.router, prefix="/api")
app.include_router(health.router, prefix="/api")

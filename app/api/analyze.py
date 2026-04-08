from fastapi import APIRouter

router = APIRouter()

@router.post("/contract")
def analyze_contract():
    return {"message": "RAG 분석 연동 예정"}
from fastapi import APIRouter

router = APIRouter()

@router.get("/score")
def get_risk_score():
    return {"message": "리스크 스코어링 연동 예정"}
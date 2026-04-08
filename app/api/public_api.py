from fastapi import APIRouter

router = APIRouter()

@router.get("/jeonse-rate")
def get_jeonse_rate():
    return {"message": "국토부 API 연동 예정"}
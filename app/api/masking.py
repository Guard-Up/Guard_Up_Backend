from fastapi import APIRouter

router = APIRouter()

@router.post("/mask")
def mask_contract():
    return {"message": "비식별화 연동 예정"}
from fastapi import APIRouter

router = APIRouter()

@router.post("/scan")
def scan_contract():
    return {"message": "OCR 연동 예정"}
from pydantic import BaseModel
from typing import Optional


class OCRResult(BaseModel):
    raw_text: str
    address: Optional[str] = None
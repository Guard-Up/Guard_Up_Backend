from pydantic import BaseModel


class InstitutionRequest(BaseModel):
    region: str


class Institution(BaseModel):
    id: str
    name: str
    region: str
    phone: str
    address: str


class InstitutionResponse(BaseModel):
    region: str
    institutions: list[Institution]

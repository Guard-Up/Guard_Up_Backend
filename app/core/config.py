from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    CLOVA_OCR_API_URL: str = ""
    CLOVA_OCR_SECRET_KEY: str = ""
    OPENAI_API_KEY: str = ""
    JUSO_API_KEY: str = ""
    MOLIT_API_KEY: str = ""
    HUG_API_KEY: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
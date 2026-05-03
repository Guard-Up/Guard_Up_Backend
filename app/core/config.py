from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CLOVA_OCR_INVOKE_URL: str = ""
    CLOVA_OCR_SECRET: str = ""
    OPENAI_API_KEY: str = ""
    ROAD_ADDRESS_API_KEY: str = ""
    MOLIT_API_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    SESSION_TTL: int = 1800  # 30분

    class Config:
        env_file = ".env"


settings = Settings()

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CLOVA_OCR_INVOKE_URL: str = ""
    CLOVA_OCR_SECRET: str = ""
    OPENAI_API_KEY: str = ""

    ROAD_ADDRESS_API_KEY: str = "devU01TX0FVVEgyMDI2MDUwOTIwNTk0MDExODEyNzE="
    ROAD_ADDRESS_API_URL: str = "https://business.juso.go.kr/addrlink/addrLinkApi.do"

    BUILDING_API_KEY: str = "ebc04b0dad1f5bad095b461d47c888dd534457a79bc29aacea0285a40a3b30d7"
    BUILDING_API_URL: str = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrBasisOulnInfo"

    MOLIT_API_KEY: str = "ebc04b0dad1f5bad095b461d47c888dd534457a79bc29aacea0285a40a3b30d7"
    APT_TRADE_API_URL: str = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
    ROWHOUSE_TRADE_API_URL: str = ""
    OFFICETEL_TRADE_API_URL: str = ""

    SESSION_SECRET_KEY: str = "guardup-test-secret-key-2026"

    REDIS_URL: str = "redis://localhost:6379"
    SESSION_TTL: int = 1800  # 30분

    class Config:
        env_file = ".env"


settings = Settings()

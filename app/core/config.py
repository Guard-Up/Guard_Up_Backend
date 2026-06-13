from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # CLOVA OCR
    CLOVA_OCR_INVOKE_URL: str = ""
    CLOVA_OCR_SECRET: str = ""

    # GPT-4o
    OPENAI_API_KEY: str = ""
    GPT_MODEL: str = "gpt-4o"  # 테스트는 gpt-4o-mini로 .env에서 전환 가능

    # 공공 API (키는 .env에서 주입, URL은 고정)
    ROAD_ADDRESS_API_KEY: str = ""
    ROAD_ADDRESS_API_URL: str = "https://business.juso.go.kr/addrlink/addrLinkApi.do"

    BUILDING_API_KEY: str = ""
    BUILDING_API_URL: str = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrBasisOulnInfo"

    MOLIT_API_KEY: str = ""
    APT_TRADE_API_URL: str = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
    ROWHOUSE_TRADE_API_URL: str = "https://apis.data.go.kr/1613000/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade"
    OFFICETEL_TRADE_API_URL: str = "http://apis.data.go.kr/1613000/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade"

    # Redis 세션
    REDIS_URL: str = "redis://localhost:6379"
    SESSION_TTL: int = 1800  # 30분

    class Config:
        env_file = ".env"


settings = Settings()

import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "WaCRM")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "wa-crm-super-secret-key-change-in-production-2026")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))

    DATABASE_URL: str = os.getenv("DATABASE_URL", "mysql+pymysql://root:root@localhost:3306/wa_crm")

    # Meta Lead Ads Integration
    META_APP_ID: str = os.getenv("META_APP_ID", "")
    META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")
    META_ACCESS_TOKEN: str = os.getenv("META_ACCESS_TOKEN", "")
    META_VERIFY_TOKEN: str = os.getenv("META_VERIFY_TOKEN", "")
    META_PAGE_ID: str = os.getenv("META_PAGE_ID", "")
    META_API_VERSION: str = os.getenv("META_API_VERSION", "v20.0")

    # WhatsApp Integration
    WHATSAPP_API_TOKEN: str = os.getenv("WHATSAPP_API_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")

    # IVR Integration
    IVR_API_KEY: str = os.getenv("IVR_API_KEY", "")
    IVR_API_SECRET: str = os.getenv("IVR_API_SECRET", "")
    IVR_BASE_URL: str = os.getenv("IVR_BASE_URL", "")

    UPLOAD_DIR: str = "uploads"
    # Public origin used to turn stored media paths such as
    # /uploads/recordings/... into absolute URLs for the web and mobile apps.
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "https://www.wapluscrm.in")

    class Config:
        case_sensitive = True

settings = Settings()

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://idp_user:idp_password@localhost:5432/idp_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin123"
    minio_bucket: str = "idp-documents"
    minio_secure: bool = False

    # App
    secret_key: str = "changeme-secret-key"
    cors_origins: str = "http://localhost:3000"
    models_dir: str = "./models"
    temp_dir: str = "./temp"
    review_confidence_threshold: float = 0.85

    # OCR
    default_ocr_engine: str = "easyocr"  # "easyocr" or "pymupdf"
    ocr_dpi: int = 200

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()

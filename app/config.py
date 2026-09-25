
from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    ENVIRONMENT: str = Field(default="development", validation_alias="ENVIRONMENT")
    PYTHONPATH: str = Field(default="/app", validation_alias="PYTHONPATH")

    # Database (PostgreSQL)
    DATABASE_URL: PostgresDsn = Field(validation_alias="DATABASE_URL")

    # Redis
    REDIS_URL: RedisDsn = Field(validation_alias="REDIS_URL")

    # Paths
    UPLOAD_DIR: str = Field(default="/app/data/uploads", validation_alias="UPLOAD_DIR")
    OUTPUT_DIR: str = Field(default="/app/data/outputs", validation_alias="OUTPUT_DIR")
    CAMERA_CONFIG_PATH: str = Field(default="/app/configs/camera.yaml", validation_alias="CAMERA_CONFIG_PATH")

    # Video limits
    MAX_UPLOAD_SIZE_MB: int = Field(default=100, validation_alias="MAX_UPLOAD_SIZE_MB")
    MAX_DURATION_SEC: int = Field(default=120, validation_alias="MAX_DURATION_SEC")
    ALLOWED_MIME_TYPES: list[str] = Field(default=["video/mp4"], validation_alias="ALLOWED_MIME_TYPES")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_URL = "http://localhost:8000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Database handling
    database_url: str

    secret_key: SecretStr
    algorithm: str = "HS256"
    access_token_expiration_timedelta_in_minutes: int = 30
    max_profile_pic_image_size_bytes: int = 5 * 1024 * 1024  # 5 MB
    default_posts_per_page: int = 10

    # Aws object storage
    s3_bucket_name: str
    s3_region: str = "us-east-1"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None
    s3_endpoint_url: str | None = None

    # Reset token handling
    reset_token_expiration_in_minutes: int = 60
    reset_password_base_url: str = BASE_URL

    # Mail server settings
    mail_server: str = "localhost"
    mail_port: int = 587
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_use_tls: bool = True


settings = Settings()  # Loads from .env file

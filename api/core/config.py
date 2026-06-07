from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "sqlite+aiosqlite:///./ecommerce.db"

    # JWT
    secret_key: str = "change-this-to-a-long-random-secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_reload: bool = False

    # File uploads
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 5

    # Simulated payment
    payment_delay_min_ms: int = 300
    payment_delay_max_ms: int = 800
    payment_failure_rate: float = 0.05

    # Rate limiting (0 = disabled)
    rate_limit_per_minute: int = 0

    # Logging
    log_dir: str = "logs"
    log_max_bytes: int = 10_485_760  # 10 MB
    log_backup_count: int = 5

    # Environment
    environment: str = "development"


settings = Settings()

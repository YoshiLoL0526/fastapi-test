from pydantic_settings import BaseSettings, SettingsConfigDict


class LoadTestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_base_url: str = "http://localhost:8000"
    scenario: str = "combined"
    max_workers: int = 100
    duration_seconds: int = 300
    think_time_min_ms: int = 50
    think_time_max_ms: int = 300
    request_timeout_s: float = 10.0
    token_pool_size: int = 50
    dashboard_port: int = 8001
    results_dir: str = "results"

    # Admin credentials (must exist in the seeded DB)
    admin_email: str = "admin01@example.com"
    admin_password: str = "TestPassword123!"

    # Ramp-up scenario
    ramp_initial_workers: int = 5
    ramp_step_workers: int = 5
    ramp_step_interval_s: float = 15.0

    # Spike scenario
    spike_base_workers: int = 10
    spike_peak_workers: int = 80
    spike_peak_duration_s: float = 30.0
    spike_base_before_s: float = 30.0
    spike_base_after_s: float = 30.0

    # Sustained scenario
    sustained_workers: int = 50
    sustained_duration_s: float = 120.0

    # Sliding-window size for real-time metrics
    metrics_window_s: float = 5.0

    # Flow distribution (must sum to 1.0)
    flow_browse_and_buy_ratio: float = 0.3
    flow_browse_only_ratio: float = 0.6
    flow_admin_ratio: float = 0.1


settings = LoadTestSettings()

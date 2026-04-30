from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    nasa_api_key: str = Field(default="DEMO_KEY", alias="NASA_API_KEY")
    api_timeout_seconds: PositiveInt = Field(default=20, alias="API_TIMEOUT_SECONDS")
    retry_attempts: PositiveInt = Field(default=3, alias="RETRY_ATTEMPTS")
    retry_delay_seconds: PositiveInt = Field(default=5, alias="RETRY_DELAY_SECONDS")
    fetch_interval_seconds: PositiveInt = Field(default=7200, alias="FETCH_INTERVAL_SECONDS")

    base_dir: Path = Field(default=BASE_DIR, alias="BASE_DIR")
    image_filename: str = Field(default="earth_wallpaper.jpg", alias="IMAGE_FILENAME")
    state_filename: str = Field(default="state.json", alias="STATE_FILENAME")
    log_filename: str = Field(default="earth_service.log", alias="LOG_FILENAME")
    history_dirname: str = Field(default="history", alias="HISTORY_DIRNAME")

    image_type: Literal["natural", "enhanced"] = Field(default="natural", alias="IMAGE_TYPE")

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def latest_metadata_url(self) -> str:
        return f"https://api.nasa.gov/EPIC/api/{self.image_type}"

    @property
    def image_path(self) -> Path:
        return self.base_dir / self.image_filename

    @property
    def state_path(self) -> Path:
        return self.base_dir / self.state_filename

    @property
    def log_path(self) -> Path:
        return self.base_dir / self.log_filename

    @property
    def history_path(self) -> Path:
        return self.base_dir / self.history_dirname


def get_settings() -> Settings:
    settings = Settings()
    settings.base_dir.mkdir(parents=True, exist_ok=True)
    settings.history_path.mkdir(parents=True, exist_ok=True)
    return settings

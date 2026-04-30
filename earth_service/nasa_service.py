from __future__ import annotations

import logging
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel, Field, ValidationError

from config import Settings


class NasaServiceError(RuntimeError):
    """Raised when NASA EPIC requests fail after all retries."""


class EpicImageMetadata(BaseModel):
    identifier: str
    image: str
    caption: str | None = None
    date: datetime
    version: str | None = None
    centroid_coordinates: dict[str, float] | None = None
    dscovr_j2000_position: dict[str, float] | None = None
    lunar_j2000_position: dict[str, float] | None = None
    sun_j2000_position: dict[str, float] | None = None
    attitude_quaternions: dict[str, float] | None = None
    coords: dict[str, Any] | None = None

    model_config = {"extra": "allow"}


class NasaEpicService:
    """Client responsible for fetching EPIC metadata and image binaries."""

    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger
        self.session = requests.Session()

    def fetch_latest_metadata(self) -> EpicImageMetadata:
        response = self._request(
            "GET",
            self.settings.latest_metadata_url,
            params={"api_key": self.settings.nasa_api_key},
        )

        try:
            payload = response.json()
        except ValueError as exc:
            raise NasaServiceError("NASA EPIC metadata response was not valid JSON") from exc

        if not isinstance(payload, list) or not payload:
            raise NasaServiceError("NASA EPIC returned no image metadata")

        try:
            images = [EpicImageMetadata.model_validate(item) for item in payload]
        except ValidationError as exc:
            raise NasaServiceError(f"NASA EPIC metadata validation failed: {exc}") from exc

        latest = max(images, key=lambda item: item.date)
        self.logger.info(
            "Latest NASA EPIC image metadata fetched",
            extra={"image_id": latest.identifier, "image_name": latest.image, "image_date": latest.date.isoformat()},
        )
        return latest

    def download_image(self, metadata: EpicImageMetadata, destination: Path) -> None:
        image_url = self.build_image_url(metadata)
        destination.parent.mkdir(parents=True, exist_ok=True)

        response = self._request("GET", image_url, stream=True)
        content_type = response.headers.get("Content-Type", "")
        if "image" not in content_type.lower():
            raise NasaServiceError(f"NASA EPIC image response was not an image: {content_type}")

        temp_path = destination.with_suffix(".download")
        try:
            with temp_path.open("wb") as file_obj:
                for chunk in response.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        file_obj.write(chunk)

            if temp_path.stat().st_size == 0:
                raise NasaServiceError("Downloaded image was empty")

            temp_path.replace(destination)
            self.logger.info(
                "NASA EPIC image downloaded",
                extra={
                    "image_id": metadata.identifier,
                    "image_url": self._redact_api_key(image_url),
                    "destination": str(destination),
                },
            )
        except OSError:
            self.logger.exception("Failed to write downloaded image", extra={"destination": str(destination)})
            raise
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def archive_image(self, source: Path, metadata: EpicImageMetadata, history_path: Path) -> Path:
        history_path.mkdir(parents=True, exist_ok=True)
        timestamp = metadata.date.strftime("%Y%m%d_%H%M%S")
        archive_path = history_path / f"earth_{timestamp}_{metadata.identifier}.jpg"
        shutil.copy2(source, archive_path)
        self.logger.info(
            "Image archived",
            extra={"source": str(source), "archive_path": str(archive_path), "image_id": metadata.identifier},
        )
        return archive_path

    def build_image_url(self, metadata: EpicImageMetadata) -> str:
        image_date = metadata.date
        date_path = image_date.strftime("%Y/%m/%d")
        return (
            f"https://epic.gsfc.nasa.gov/archive/{self.settings.image_type}/"
            f"{date_path}/jpg/{metadata.image}.jpg"
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        request_kwargs = {"timeout": self.settings.api_timeout_seconds, **kwargs}
        last_error: Exception | None = None

        for attempt in range(1, self.settings.retry_attempts + 1):
            try:
                response = self.session.request(method, url, **request_kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                self.logger.warning(
                    "NASA EPIC request failed",
                    extra={
                        "method": method,
                        "url": self._redact_api_key(url),
                        "attempt": attempt,
                        "max_attempts": self.settings.retry_attempts,
                        "error": self._redact_api_key(str(exc)),
                    },
                )
                if attempt < self.settings.retry_attempts:
                    time.sleep(self.settings.retry_delay_seconds)

        raise NasaServiceError(f"NASA EPIC request failed after retries: {last_error}") from last_error

    @staticmethod
    def _redact_api_key(url: str) -> str:
        return re.sub(r"api_key=[^&\s]+", "api_key=***", url)

from __future__ import annotations

import logging
import time

from config import Settings, get_settings
from logger import configure_logging
from nasa_service import NasaEpicService, NasaServiceError
from state_manager import StateManager
from wallpaper import WallpaperError, WallpaperSetter


class EarthWallpaperService:
    """Coordinates metadata fetch, download, archive, wallpaper, and state."""

    def __init__(self, settings: Settings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger
        self.nasa_service = NasaEpicService(settings=settings, logger=logger)
        self.state_manager = StateManager(state_path=settings.state_path, logger=logger)
        self.wallpaper_setter = WallpaperSetter(logger=logger)

    def run_forever(self) -> None:
        self.logger.info(
            "Earth wallpaper service started",
            extra={"fetch_interval_seconds": self.settings.fetch_interval_seconds},
        )

        while True:
            started_at = time.monotonic()
            try:
                self.run_once()
            except Exception:
                self.logger.exception("Unexpected service cycle failure")

            elapsed_seconds = time.monotonic() - started_at
            sleep_seconds = max(0, self.settings.fetch_interval_seconds - elapsed_seconds)
            self.logger.info("Service cycle complete", extra={"sleep_seconds": round(sleep_seconds, 2)})
            time.sleep(sleep_seconds)

    def run_once(self) -> None:
        try:
            metadata = self.nasa_service.fetch_latest_metadata()
        except NasaServiceError:
            self.logger.exception("Unable to fetch NASA EPIC metadata")
            return

        if self.state_manager.is_duplicate(metadata.identifier):
            self.logger.info("Latest image already processed", extra={"image_id": metadata.identifier})
            return

        try:
            self.nasa_service.download_image(metadata=metadata, destination=self.settings.image_path)
            self.nasa_service.archive_image(
                source=self.settings.image_path,
                metadata=metadata,
                history_path=self.settings.history_path,
            )
            self.state_manager.update(metadata.identifier)
            self.wallpaper_setter.set_wallpaper(self.settings.image_path)
        except (NasaServiceError, WallpaperError, OSError):
            self.logger.exception("Image update cycle failed", extra={"image_id": metadata.identifier})


def main() -> None:
    settings = get_settings()
    logger = configure_logging(settings.log_path)
    service = EarthWallpaperService(settings=settings, logger=logger)

    try:
        service.run_forever()
    except KeyboardInterrupt:
        logger.info("Earth wallpaper service stopped by user")


if __name__ == "__main__":
    main()

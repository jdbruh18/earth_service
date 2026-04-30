from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    from .config import Settings
    from .models import HistoryImageResponse
except ImportError:  # Allows `uvicorn api:app --reload` from inside earth_service/.
    from config import Settings
    from models import HistoryImageResponse


ARCHIVE_IMAGE_PATTERN = re.compile(
    r"^earth_(?P<date>\d{8})_(?P<time>\d{6})_(?P<identifier>.+)\.(?:jpg|jpeg|png)$",
    re.IGNORECASE,
)


def absolute_path(path: Path) -> Path:
    return path.expanduser().resolve()


def timelapse_path(settings: Settings) -> Path:
    return absolute_path(settings.base_dir / "earth_timelapse.mp4")


def parse_archive_filename(path: Path) -> tuple[datetime | None, str | None]:
    match = ARCHIVE_IMAGE_PATTERN.match(path.name)
    if not match:
        return None, None

    timestamp_text = f"{match.group('date')}_{match.group('time')}"
    timestamp = datetime.strptime(timestamp_text, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    return timestamp, match.group("identifier")


def list_history_images(history_path: Path, logger: logging.Logger | None = None) -> list[HistoryImageResponse]:
    resolved_history_path = absolute_path(history_path)
    if not resolved_history_path.exists():
        return []

    images: list[HistoryImageResponse] = []
    for path in resolved_history_path.iterdir():
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue

        timestamp, image_id = parse_archive_filename(path)
        try:
            size_bytes = path.stat().st_size
        except OSError as exc:
            if logger:
                logger.warning(
                    "Unable to stat archived image",
                    extra={"file_path": str(path), "error": str(exc)},
                )
            continue

        images.append(
            HistoryImageResponse(
                id=image_id,
                timestamp=timestamp,
                file_path=str(absolute_path(path)),
                image_url=f"/history/{path.name}/image",
                filename=path.name,
                size_bytes=size_bytes,
            )
        )

    return sorted(images, key=lambda item: (item.timestamp is None, item.timestamp or datetime.max.replace(tzinfo=timezone.utc), item.filename))


def parse_state_timestamp(value: str | None, logger: logging.Logger | None = None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        if logger:
            logger.warning("State timestamp is invalid", extra={"timestamp": value, "error": str(exc)})
        return None


def resolve_history_image(history_path: Path, filename: str) -> Path | None:
    resolved_history_path = absolute_path(history_path)
    candidate = absolute_path(resolved_history_path / filename)

    try:
        candidate.relative_to(resolved_history_path)
    except ValueError:
        return None

    if not candidate.is_file() or candidate.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        return None

    return candidate

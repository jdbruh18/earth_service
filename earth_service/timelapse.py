from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    from .models import HistoryImageResponse, TimelapseResponse
    from .utils import absolute_path
except ImportError:  # Allows `uvicorn api:app --reload` from inside earth_service/.
    from models import HistoryImageResponse, TimelapseResponse
    from utils import absolute_path


class TimelapseError(RuntimeError):
    """Base exception for timelapse generation failures."""


class FfmpegNotFoundError(TimelapseError):
    """Raised when ffmpeg is not available on PATH."""


class EmptyHistoryError(TimelapseError):
    """Raised when there are no history images to render."""


class TimelapseEngine:
    """Builds an MP4 timelapse from archived Earth images using ffmpeg."""

    def __init__(self, output_path: Path, logger: logging.Logger, frame_rate: int = 24) -> None:
        self.output_path = absolute_path(output_path)
        self.logger = logger
        self.frame_rate = frame_rate

    def get_status(self) -> TimelapseResponse:
        exists = self.output_path.exists()
        return TimelapseResponse(
            file_path=str(self.output_path),
            exists=exists,
            size_bytes=self.output_path.stat().st_size if exists else None,
            generated_from_count=None,
            frame_rate=self.frame_rate,
            status="available" if exists else "missing",
        )

    def generate(self, images: list[HistoryImageResponse]) -> TimelapseResponse:
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            raise FfmpegNotFoundError("ffmpeg is not installed or is not available on PATH")

        sorted_images = [image for image in images if Path(image.file_path).exists()]
        if not sorted_images:
            raise EmptyHistoryError("No archived images are available for timelapse generation")

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="earth_timelapse_") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            self._stage_frames(sorted_images, temp_dir)
            temp_output_path = self.output_path.with_suffix(".tmp.mp4")

            command = [
                ffmpeg_path,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-framerate",
                str(self.frame_rate),
                "-i",
                str(temp_dir / "frame_%06d.jpg"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(temp_output_path),
            ]

            self.logger.info(
                "Generating Earth timelapse",
                extra={
                    "frame_count": len(sorted_images),
                    "frame_rate": self.frame_rate,
                    "output_path": str(self.output_path),
                },
            )
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                if temp_output_path.exists():
                    temp_output_path.unlink(missing_ok=True)
                raise TimelapseError(f"ffmpeg failed: {completed.stderr.strip()}")

            temp_output_path.replace(self.output_path)

        response = TimelapseResponse(
            file_path=str(self.output_path),
            exists=True,
            size_bytes=self.output_path.stat().st_size,
            generated_from_count=len(sorted_images),
            frame_rate=self.frame_rate,
            status="generated",
        )
        self.logger.info("Earth timelapse generated", extra=response.model_dump())
        return response

    def _stage_frames(self, images: list[HistoryImageResponse], temp_dir: Path) -> None:
        for index, image in enumerate(images, start=1):
            source = Path(image.file_path)
            destination = temp_dir / f"frame_{index:06d}.jpg"
            shutil.copy2(source, destination)

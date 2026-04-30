from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LatestImageResponse(BaseModel):
    id: str | None = Field(default=None, description="Last processed NASA EPIC image identifier.")
    timestamp: datetime | None = Field(default=None, description="UTC timestamp when the image was processed.")
    file_path: str = Field(description="Absolute path to the current wallpaper image.")
    image_url: str = Field(description="Local API URL that serves the current wallpaper image.")
    exists: bool = Field(description="Whether the current wallpaper image exists on disk.")


class HistoryImageResponse(BaseModel):
    id: str | None = Field(default=None, description="NASA EPIC image identifier parsed from the archive filename.")
    timestamp: datetime | None = Field(default=None, description="Image timestamp parsed from the archive filename.")
    file_path: str = Field(description="Absolute path to the archived image.")
    image_url: str = Field(description="Local API URL that serves the archived image.")
    filename: str = Field(description="Archived image filename.")
    size_bytes: int = Field(description="Archived image size in bytes.")


class HistoryResponse(BaseModel):
    count: int
    images: list[HistoryImageResponse]


class TimelapseResponse(BaseModel):
    file_path: str = Field(description="Absolute path to the timelapse video.")
    exists: bool = Field(description="Whether the timelapse video exists on disk.")
    size_bytes: int | None = Field(default=None, description="Timelapse video size in bytes.")
    generated_from_count: int | None = Field(default=None, description="Number of images used to generate the video.")
    frame_rate: int = Field(default=24, description="Video frame rate.")
    status: Literal["available", "missing", "generated"] = Field(description="Current timelapse status.")


class ErrorResponse(BaseModel):
    detail: str

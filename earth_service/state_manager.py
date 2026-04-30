from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class ServiceState(BaseModel):
    last_id: str | None = None
    last_updated: str | None = None


class StateManager:
    """Reads and writes the small JSON state file used for deduplication."""

    def __init__(self, state_path: Path, logger: logging.Logger) -> None:
        self.state_path = state_path
        self.logger = logger

    def load(self) -> ServiceState:
        if not self.state_path.exists():
            return ServiceState()

        try:
            raw: dict[str, Any] = json.loads(self.state_path.read_text(encoding="utf-8"))
            return ServiceState.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            self.logger.warning(
                "State file could not be read; starting with empty state",
                extra={"state_path": str(self.state_path), "error": str(exc)},
            )
            return ServiceState()

    def is_duplicate(self, image_id: str) -> bool:
        return self.load().last_id == image_id

    def update(self, image_id: str) -> None:
        state = ServiceState(
            last_id=image_id,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

        temp_path = self.state_path.with_suffix(".tmp")
        payload = state.model_dump()
        try:
            temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp_path.replace(self.state_path)
            self.logger.info("State file updated", extra={"state": payload})
        except OSError:
            self.logger.exception("Failed to update state file", extra={"state_path": str(self.state_path)})
            raise

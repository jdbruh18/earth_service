from __future__ import annotations

import ctypes
import logging
import platform
import subprocess
from pathlib import Path


class WallpaperError(RuntimeError):
    """Raised when the operating system rejects a wallpaper update."""


class WallpaperSetter:
    """Cross-platform desktop wallpaper integration."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def set_wallpaper(self, image_path: Path) -> None:
        absolute_path = image_path.resolve()
        if not absolute_path.exists():
            raise WallpaperError(f"Wallpaper image does not exist: {absolute_path}")

        system = platform.system().lower()
        self.logger.info(
            "Setting desktop wallpaper",
            extra={"platform": system, "image_path": str(absolute_path)},
        )

        if system == "windows":
            self._set_windows_wallpaper(absolute_path)
        elif system == "linux":
            self._set_linux_wallpaper(absolute_path)
        elif system == "darwin":
            self._set_macos_wallpaper(absolute_path)
        else:
            raise WallpaperError(f"Unsupported operating system: {platform.system()}")

    @staticmethod
    def _set_windows_wallpaper(image_path: Path) -> None:
        spi_setdeskwallpaper = 20
        spif_updateinifile = 0x01
        spif_sendchange = 0x02

        success = ctypes.windll.user32.SystemParametersInfoW(
            spi_setdeskwallpaper,
            0,
            str(image_path),
            spif_updateinifile | spif_sendchange,
        )
        if not success:
            raise WallpaperError("Windows SystemParametersInfoW failed")

    @staticmethod
    def _set_linux_wallpaper(image_path: Path) -> None:
        image_uri = image_path.as_uri()
        commands = [
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", image_uri],
            ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", image_uri],
        ]

        for command in commands:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                raise WallpaperError(
                    f"Linux gsettings failed: {' '.join(command)}; stderr={completed.stderr.strip()}"
                )

    @staticmethod
    def _set_macos_wallpaper(image_path: Path) -> None:
        escaped_path = str(image_path).replace('"', '\\"')
        script = (
            'tell application "System Events" to tell every desktop '
            f'to set picture to POSIX file "{escaped_path}"'
        )
        completed = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise WallpaperError(f"macOS osascript failed: {completed.stderr.strip()}")

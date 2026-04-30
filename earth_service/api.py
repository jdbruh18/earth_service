from __future__ import annotations

import logging

from html import escape

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse

try:
    from .config import Settings, get_settings
    from .logger import configure_logging
    from .models import HistoryResponse, LatestImageResponse, TimelapseResponse
    from .state_manager import StateManager
    from .timelapse import EmptyHistoryError, FfmpegNotFoundError, TimelapseEngine, TimelapseError
    from .utils import absolute_path, list_history_images, parse_state_timestamp, resolve_history_image, timelapse_path
except ImportError:  # Allows `uvicorn api:app --reload` from inside earth_service/.
    from config import Settings, get_settings
    from logger import configure_logging
    from models import HistoryResponse, LatestImageResponse, TimelapseResponse
    from state_manager import StateManager
    from timelapse import EmptyHistoryError, FfmpegNotFoundError, TimelapseEngine, TimelapseError
    from utils import absolute_path, list_history_images, parse_state_timestamp, resolve_history_image, timelapse_path


def create_app() -> FastAPI:
    settings = get_settings()
    logger = configure_logging(settings.log_path)
    state_manager = StateManager(state_path=settings.state_path, logger=logger)
    timelapse_engine = TimelapseEngine(output_path=timelapse_path(settings), logger=logger)

    app = FastAPI(
        title="Earth Service API",
        description="Local API for NASA EPIC wallpaper state, archive history, and timelapse generation.",
        version="1.0.0",
    )
    app.state.settings = settings
    app.state.logger = logger
    app.state.state_manager = state_manager
    app.state.timelapse_engine = timelapse_engine

    @app.get("/")
    def root() -> dict[str, object]:
        return {
            "service": "earth_service",
            "status": "running",
            "endpoints": {
                "viewer": "/viewer",
                "latest": "/latest",
                "latest_image": "/latest/image",
                "history": "/history",
                "timelapse": "/timelapse",
                "generate_timelapse": "/generate-timelapse",
                "docs": "/docs",
            },
        }

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/latest", response_model=LatestImageResponse)
    def latest() -> LatestImageResponse:
        state = app.state.state_manager.load()
        image_path = absolute_path(app.state.settings.image_path)
        return LatestImageResponse(
            id=state.last_id,
            timestamp=parse_state_timestamp(state.last_updated, app.state.logger),
            file_path=str(image_path),
            image_url="/latest/image",
            exists=image_path.exists(),
        )

    @app.get("/latest/image", response_class=FileResponse)
    def latest_image() -> FileResponse:
        image_path = absolute_path(app.state.settings.image_path)
        if not image_path.is_file():
            raise HTTPException(status_code=404, detail="Latest Earth image has not been downloaded yet")

        return FileResponse(
            image_path,
            media_type="image/jpeg",
            filename=image_path.name,
        )

    @app.get("/history", response_model=HistoryResponse)
    def history() -> HistoryResponse:
        images = list_history_images(app.state.settings.history_path, app.state.logger)
        return HistoryResponse(count=len(images), images=images)

    @app.get("/history/{filename}/image", response_class=FileResponse)
    def history_image(filename: str) -> FileResponse:
        image_path = resolve_history_image(app.state.settings.history_path, filename)
        if image_path is None:
            raise HTTPException(status_code=404, detail="Archived image was not found")

        media_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        return FileResponse(
            image_path,
            media_type=media_type,
            filename=image_path.name,
        )

    @app.get("/timelapse", response_model=TimelapseResponse)
    def timelapse() -> TimelapseResponse:
        return app.state.timelapse_engine.get_status()

    @app.post("/generate-timelapse", response_model=TimelapseResponse)
    def generate_timelapse() -> TimelapseResponse:
        images = list_history_images(app.state.settings.history_path, app.state.logger)
        try:
            return app.state.timelapse_engine.generate(images)
        except EmptyHistoryError as exc:
            app.state.logger.warning("Timelapse generation skipped", extra={"error": str(exc)})
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except FfmpegNotFoundError as exc:
            app.state.logger.error("ffmpeg is missing", extra={"error": str(exc)})
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except TimelapseError as exc:
            app.state.logger.exception("Timelapse generation failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/viewer", response_class=HTMLResponse)
    def viewer() -> HTMLResponse:
        state = app.state.state_manager.load()
        latest_path = absolute_path(app.state.settings.image_path)
        images = list_history_images(app.state.settings.history_path, app.state.logger)
        latest_timestamp = parse_state_timestamp(state.last_updated, app.state.logger)

        if latest_path.exists():
            latest_image_html = '<img class="hero-image" src="/latest/image" alt="Latest Earth image">'
        else:
            latest_image_html = '<div class="empty">No latest image has been downloaded yet.</div>'

        history_items = "\n".join(
            f"""
            <a class="thumb" href="{escape(image.image_url)}" target="_blank" rel="noreferrer">
                <img src="{escape(image.image_url)}" alt="{escape(image.filename)}">
                <span>{escape(image.timestamp.isoformat() if image.timestamp else image.filename)}</span>
            </a>
            """
            for image in images[:24]
        )
        if not history_items:
            history_items = '<div class="empty">No archived images yet.</div>'

        html = f"""
        <!doctype html>
        <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Earth Service Viewer</title>
            <style>
                :root {{
                    color-scheme: dark;
                    font-family: Inter, Segoe UI, Arial, sans-serif;
                    background: #0e1116;
                    color: #eef3f8;
                }}
                body {{
                    margin: 0;
                    min-height: 100vh;
                    background: #0e1116;
                }}
                header, main {{
                    width: min(1120px, calc(100vw - 32px));
                    margin: 0 auto;
                }}
                header {{
                    padding: 24px 0 12px;
                    display: flex;
                    justify-content: space-between;
                    gap: 16px;
                    align-items: end;
                }}
                h1, h2, p {{
                    margin: 0;
                }}
                h1 {{
                    font-size: 28px;
                    font-weight: 700;
                }}
                h2 {{
                    font-size: 18px;
                    margin: 28px 0 12px;
                }}
                .meta {{
                    color: #aab6c2;
                    font-size: 14px;
                    margin-top: 6px;
                }}
                .links {{
                    display: flex;
                    gap: 10px;
                    flex-wrap: wrap;
                }}
                .links a {{
                    color: #d9f2ff;
                    text-decoration: none;
                    border: 1px solid #334253;
                    padding: 8px 10px;
                    border-radius: 6px;
                    background: #151b23;
                }}
                .hero-image {{
                    width: 100%;
                    max-height: 72vh;
                    object-fit: contain;
                    background: #05070a;
                    border: 1px solid #263140;
                    border-radius: 8px;
                }}
                .grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
                    gap: 12px;
                    padding-bottom: 32px;
                }}
                .thumb {{
                    display: grid;
                    gap: 8px;
                    color: #dfe9f2;
                    text-decoration: none;
                    background: #151b23;
                    border: 1px solid #263140;
                    border-radius: 8px;
                    padding: 8px;
                }}
                .thumb img {{
                    width: 100%;
                    aspect-ratio: 1 / 1;
                    object-fit: cover;
                    background: #05070a;
                    border-radius: 4px;
                }}
                .thumb span {{
                    color: #aab6c2;
                    font-size: 12px;
                    overflow-wrap: anywhere;
                }}
                .empty {{
                    border: 1px dashed #334253;
                    border-radius: 8px;
                    padding: 24px;
                    color: #aab6c2;
                    background: #151b23;
                }}
            </style>
        </head>
        <body>
            <header>
                <div>
                    <h1>Earth Service</h1>
                    <p class="meta">Latest ID: {escape(state.last_id or "none")} | Updated: {escape(latest_timestamp.isoformat() if latest_timestamp else "unknown")}</p>
                </div>
                <nav class="links">
                    <a href="/latest">Latest JSON</a>
                    <a href="/history">History JSON</a>
                    <a href="/docs">API Docs</a>
                </nav>
            </header>
            <main>
                {latest_image_html}
                <h2>History</h2>
                <section class="grid">{history_items}</section>
            </main>
        </body>
        </html>
        """
        return HTMLResponse(content=html)

    return app


app = create_app()


def get_api_components() -> tuple[Settings, logging.Logger]:
    return app.state.settings, app.state.logger

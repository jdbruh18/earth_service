# Earth Service

Production-grade local Python backend for NASA EPIC Earth imagery.

## Features

- Fetches latest Earth image metadata from NASA EPIC.
- Downloads the latest Earth image.
- Sets the image as desktop wallpaper on Windows, Linux, and macOS.
- Archives downloaded images in `earth_service/history/`.
- Avoids duplicate downloads using local JSON state.
- Logs operations with structured JSON logs.
- Exposes a local FastAPI backend.
- Serves the latest image in-browser.
- Generates timelapse videos from archived images using `ffmpeg`.

## Install

```powershell
cd earth_service
python -m pip install -r requirements.txt
```

## Run Wallpaper Service

```powershell
cd earth_service
python main.py
```

## Run Local API

```powershell
cd earth_service
uvicorn api:app --reload
```

Open:

```text
http://127.0.0.1:8000/viewer
http://127.0.0.1:8000/docs
```

## API Endpoints

```text
GET  /
GET  /viewer
GET  /latest
GET  /latest/image
GET  /history
GET  /history/{filename}/image
GET  /timelapse
POST /generate-timelapse
```

## Configuration

The service works with default values. To customize runtime settings, create `earth_service/.env`:

```env
NASA_API_KEY=DEMO_KEY
API_TIMEOUT_SECONDS=20
RETRY_ATTEMPTS=3
RETRY_DELAY_SECONDS=5
FETCH_INTERVAL_SECONDS=7200
IMAGE_TYPE=natural
```

## Timelapse

Install `ffmpeg` and make sure it is available on `PATH`, then call:

```text
POST http://127.0.0.1:8000/generate-timelapse
```

The output file is:

```text
earth_service/earth_timelapse.mp4
```

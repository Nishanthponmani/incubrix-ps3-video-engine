# INCUBRIX PS3 - Script-to-B-roll Video Engine

A FastAPI application that turns a text script or audio input into a planned, narrated B-roll video project. It supports scene planning, footage selection using keywords, narration generation, subtitles, project metadata, and asynchronous rendering jobs.

## Features

- **FastAPI REST API** with health, readiness, planning, script, rendering, and job-status endpoints.
- **Scene planning** that divides scripts into scenes and generates search terms.
- **Audio input and transcription** using a local transcription workflow.
- **Text-to-speech** for narration.
- **B-roll selection** using scene keywords and clip metadata.
- **Video rendering** with FFmpeg, including 16:9, 9:16, and 1:1 aspect ratios.
- **Project artifacts** including subtitles (`subtitles.srt`), a timeline (`timeline.json`), and a manifest (`manifest.json`).
- **Background rendering jobs** with status and progress information.
- **Docker support** through Dockerfile and Docker Compose.
- **Automated tests** covering API and project functionality.

## Technology stack

- Python 3.12
- FastAPI and Uvicorn
- FFmpeg and ffprobe
- faster-whisper for audio transcription
- Docker and Docker Compose
- pytest and HTTPX for testing

## Requirements

- Python 3.12
- FFmpeg and ffprobe available on `PATH` for local development
- Docker Desktop with Docker Compose for containerized execution

## Setup on Windows

Open PowerShell in the project root.

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, use the environment's Python executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run locally

Start the API from the project root:

```powershell
python -m uvicorn app.main:app --reload
```

Open the interactive API documentation:

- Swagger UI: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health
- Readiness: http://127.0.0.1:8000/ready

## Run with Docker Compose

Build and start the container:

```powershell
docker compose up -d --build
```

Check the running containers:

```powershell
docker compose ps
```

Check API readiness:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/ready" -Method Get
```

Stop the containers:

```powershell
docker compose down
```

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/ready` | Readiness check |
| GET | `/api/v1` | API information |
| POST | `/api/v1/plan` | Plan scenes from a script |
| POST | `/api/v1/script` | Process a script |
| POST | `/api/v1/render` | Submit a background rendering job |
| GET | `/api/v1/jobs/{job_id}` | Retrieve rendering job status |
| POST | `/api/v1/broll/jobs` | Submit an audio-based B-roll job |

See `/docs` for request schemas and response details.

## Generate a video

Submit a render request to `POST /api/v1/render`. For example, in PowerShell:

```powershell
$body = @{
    script = "Artificial intelligence is transforming healthcare. It can help detect diseases and support doctors."
    words_per_minute = 150
    minimum_scene_seconds = 2
    aspect_ratio = "16:9"
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/render" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$response | ConvertTo-Json -Depth 10
```

The response provides a job ID. Use that ID to check progress:

```powershell
$jobId = $response.job_id

Invoke-RestMethod `
    -Uri "http://localhost:8000/api/v1/jobs/$jobId" `
    -Method Get |
    ConvertTo-Json -Depth 10
```

A successful render includes the output video path in the job response. Generated files are stored under `outputs/jobs/<job_id>/` in the project output directory.

**Important:** A render job may stop with `needs_assets` if matching footage or the required licence metadata is missing. Only use footage you are permitted to use, and review the original source and licence terms before distributing a video.

## Run tests

From the project root, run:

```powershell
python -m pytest -q
```

Latest recorded test result: **55 passed**.

## Project structure

```text
.
├── app/                  # FastAPI application and processing modules
├── assets/
│   └── clips/            # B-roll clips and metadata
├── outputs/
│   └── jobs/             # Job artifacts and rendered videos
├── tests/                # Automated tests
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── openapi.yaml
└── README.md
```

## Usage and licensing notes

- Review the licence and usage terms for every third-party clip before distributing generated videos.
- Do not treat the presence of licence metadata as independent legal verification.
- Keep credentials and private configuration out of source control.
- Generated outputs may contain narration, captions, and media obtained from configured assets.

## Current validation

The project has recorded the following checks:

- 55 automated tests passed.
- The readiness endpoint returned `{"status": "ready"}`.
- A sample 16:9 render completed successfully.
- The generated MP4 played without a playback error.

These checks confirm the recorded test and runtime results; narration synchronization and final visual quality should still be reviewed manually.


import json
import uuid
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from app.tts_engine import generate_speech
from app.scene_planner import (
    plan_scenes,
    plan_scenes_from_transcription,
)
from app.exporter import export_project
from app.renderer import render_scenes, RenderError

from app.audio_input import (
    download_audio,
    validate_audio_duration,
    validate_audio_url,
)
from app.transcription import transcribe_audio

import logging
import time
from datetime import datetime, timezone

import hashlib
import threading


logger = logging.getLogger("broll_api")
logger.setLevel(logging.INFO)
logger.propagate = True

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)


# In-memory idempotency cache.
# Production deployments should use shared persistent storage.
_idempotency_cache = {}
_idempotency_lock = threading.Lock()
_idempotency_key_locks = {}


def get_idempotency_key_lock(endpoint: str, idempotency_key: str):
    """Return a shared lock for this endpoint and idempotency key."""
    cache_key = (endpoint, idempotency_key)

    with _idempotency_lock:
        if cache_key not in _idempotency_key_locks:
            _idempotency_key_locks[cache_key] = threading.Lock()

        return _idempotency_key_locks[cache_key]


def get_request_fingerprint(payload: dict) -> str:
    """Create a stable fingerprint for a request payload."""
    request_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(request_json.encode("utf-8")).hexdigest()


def get_idempotent_response(
    endpoint: str,
    idempotency_key: str | None,
    payload: dict,
):
    """Return a cached response if the key and payload match."""
    if not idempotency_key:
        return None

    fingerprint = get_request_fingerprint(payload)
    cache_key = (endpoint, idempotency_key)

    with _idempotency_lock:
        cached = _idempotency_cache.get(cache_key)

        if cached is None:
            return None

        if cached["fingerprint"] != fingerprint:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "IDEMPOTENCY_KEY_REUSED",
                    "message": (
                        "This Idempotency-Key was already used "
                        "with a different request."
                    ),
                },
            )

        return cached["response"]


def save_idempotent_response(
    endpoint: str,
    idempotency_key: str | None,
    payload: dict,
    response: dict,
):
    """Cache the response for a later retry."""
    if not idempotency_key:
        return

    fingerprint = get_request_fingerprint(payload)
    cache_key = (endpoint, idempotency_key)

    with _idempotency_lock:
        _idempotency_cache[cache_key] = {
            "fingerprint": fingerprint,
            "response": response,
        }


def save_job_manifest(manifest_path: Path, manifest: dict):
    """Save the current job status and progress."""
    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)

def process_render_job_with_cleanup(job_id: str, request: "RenderRequest"):
    """Run the render job and clean up temporary narration audio afterward."""
    try:
        process_render_job(job_id, request)
    finally:
        if request.narration_audio_path:
            Path(request.narration_audio_path).unlink(missing_ok=True)

def process_render_job(job_id: str, request: "RenderRequest"):
    """Process a video-rendering job in the background."""
    output_dir = Path("outputs") / "jobs" / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "manifest.json"

    manifest = {
        "job_id": job_id,
        "status": "running",
        "rendered": False,
        "progress": 0,
        "error": None,
        "video": None,
        "assets": [],
        "note": "The rendering job has started.",
    }

    save_job_manifest(manifest_path, manifest)

    
    try:
        
        if request.transcription_segments:
            scenes = plan_scenes_from_transcription(
                {
                    "segments": request.transcription_segments,
                },
                minimum_scene_seconds=request.minimum_scene_seconds,
            )
        else:
            scenes = plan_scenes(
                script=request.script,
                words_per_minute=request.words_per_minute,
                minimum_scene_seconds=request.minimum_scene_seconds,
            )

        if not scenes:
            raise ValueError("No scenes could be created.")

        manifest["progress"] = 10
        manifest["scene_count"] = len(scenes)
        manifest["note"] = "Scene planning completed."
        save_job_manifest(manifest_path, manifest)

        if request.narration_audio_path:
            narration_path = request.narration_audio_path
        else:
            narration_path = generate_speech(
                request.script,
                str(output_dir / "narration.wav"),
            )

        manifest["progress"] = 30
        manifest["narration"] = narration_path
        manifest["note"] = "Scene planning and narration completed."
        save_job_manifest(manifest_path, manifest)


        '''manifest["progress"] = 30
        manifest["narration"] = narration_path
        manifest["note"] = "Scene planning and narration completed."
        save_job_manifest(manifest_path, manifest)'''

        
        export_result = export_project(
            scenes,
            narration_path,
            str(output_dir),
        )

        assets = export_result["assets"]
        manifest["assets"] = assets
        manifest["progress"] = 50
        manifest["note"] = "Project metadata exported; checking B-roll assets."
        save_job_manifest(manifest_path, manifest)

        all_assets_verified = (
            len(assets) == len(scenes)
            and all(
                asset.get("status") == "matched"
                and asset.get("clip_path")
                and Path(asset["clip_path"]).is_file()
                and asset.get("license_verified") is True
                for asset in assets
            )
        )

        if not all_assets_verified:
            manifest["status"] = "needs_assets"
            manifest["error"] = None
            manifest["note"] = (
                "Narration and metadata are ready, but every scene "
                "needs a matching clip with verified licence metadata."
            )
            save_job_manifest(manifest_path, manifest)
            return
        
        
        requested_ratios = request.aspect_ratios or [request.aspect_ratio]
        videos = []

        for index, ratio in enumerate(requested_ratios):
            video_path = output_dir / (
                f"video_{ratio.replace(':', 'x')}.mp4"
            )

            manifest["progress"] = 60 + int(
                40 * index / len(requested_ratios)
            )
            manifest["note"] = f"Rendering {ratio} video."
            save_job_manifest(manifest_path, manifest)

            render_scenes(
                clip_paths=[asset["clip_path"] for asset in assets],
                durations=[scene["duration"] for scene in scenes],
                audio_path=narration_path,
                output_path=str(video_path),
                aspect_ratio=ratio,
            )

            videos.append({
                "aspect_ratio": ratio,
                "path": str(video_path),
            })

        manifest["status"] = "succeeded"
        manifest["progress"] = 100
        manifest["videos"] = videos
        manifest["video"] = videos[0]["path"]
        manifest["rendered"] = True
        manifest["error"] = None
        manifest["note"] = "All requested videos rendered successfully."
        save_job_manifest(manifest_path, manifest)




    
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error"] = {
            "code": "job_processing_failed",
            "message": str(exc),
        }
        manifest["note"] = "Job processing failed."
        save_job_manifest(manifest_path, manifest)



app = FastAPI(
    title="INCUBRIX Script-to-B-roll Video Engine",
    description="API for planning and rendering narrated B-roll videos.",
    version="0.1.0",
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id")

    if not correlation_id or len(correlation_id) > 128:
        correlation_id = str(uuid.uuid4())

    request.state.correlation_id = correlation_id
    start_time = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

    logger.info(
        json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "job_id": getattr(request.state, "job_id", None),
            "correlation_id": correlation_id,
        })
    )
    response.headers["X-Correlation-Id"] = correlation_id
    return response



@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail

    if isinstance(detail, dict):
        code = str(detail.get("code", "HTTP_ERROR")).upper()
        message = str(detail.get("message", "Request failed."))
        details = detail.get("details", {})
    else:
        code = "HTTP_ERROR"
        message = str(detail)
        details = {}

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": exc.status_code >= 500,
                "details": details,
            }
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    errors = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request data is invalid.",
                "retryable": False,
                "details": {"fields": errors},
            }
        },
    )


class ScriptRequest(BaseModel):
    script: str = Field(
        ...,
        min_length=1,
        description="The script to split into timed scenes.",
    )
    words_per_minute: int = Field(default=150, gt=0)
    minimum_scene_seconds: float = Field(default=2.0, gt=0)


class RenderRequest(ScriptRequest):
    aspect_ratio: Literal["16:9", "9:16", "1:1"] = Field(
        default="16:9",
        description="Output video aspect ratio.",
    )
    aspect_ratios: list[Literal["16:9", "9:16", "1:1"]] | None = None

    # New fields for uploaded-audio processing
    narration_audio_path: str | None = None
    transcription_segments: list[dict] | None = None

class BrollJobRequest(BaseModel):
    script: str | None = None
    audio_url: str | None = None
    scenes: list[dict] | None = None

    voice: str = "en-IN-female"
    aspect_ratios: list[Literal["16:9", "9:16", "1:1"]] = Field(
        default_factory=lambda: ["16:9"]
    )
    style: str = "bright, modern, real-world footage"
    avoid: list[str] = Field(default_factory=list)
    captions: dict = Field(
        default_factory=lambda: {"burn_in": False, "srt": True}
    )

    words_per_minute: int = Field(default=150, gt=0)
    minimum_scene_seconds: float = Field(default=2.0, gt=0)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    return {"status": "ready"}


@app.get("/api/v1")
def api_info():
    return {
        "name": "INCUBRIX Script-to-B-roll Video Engine",
        "version": "0.1.0",
    }





@app.post("/api/v1/plan")
def create_scene_plan(
    request: ScriptRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
):
    if not isinstance(idempotency_key, str):
        idempotency_key = None

    payload = request.model_dump()
    endpoint = "/api/v1/plan"

    # Requests without a key retain the normal behavior.
    if not idempotency_key:
        return generate_scene_plan_response(request)

    # Serialize requests that use the same key.
    key_lock = get_idempotency_key_lock(endpoint, idempotency_key)

    with key_lock:
        cached_response = get_idempotent_response(
            endpoint,
            idempotency_key,
            payload,
        )
        if cached_response is not None:
            return cached_response

        response = generate_scene_plan_response(request)

        save_idempotent_response(
            endpoint,
            idempotency_key,
            payload,
            response,
        )

        return response


def generate_scene_plan_response(request: ScriptRequest):
    """Generate the scene plan response."""
    try:
        scenes = plan_scenes(
            script=request.script,
            words_per_minute=request.words_per_minute,
            minimum_scene_seconds=request.minimum_scene_seconds,
        )

        return {
            "scene_count": len(scenes),
            "total_duration": scenes[-1]["end_time"],
            "scenes": scenes,
        }

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc






@app.post("/api/v1/script")
def process_script(
    request: ScriptRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
):
    if not isinstance(idempotency_key, str):
        idempotency_key = None

    payload = request.model_dump()
    endpoint = "/api/v1/script"

    # Requests without a key retain the normal behavior.
    if not idempotency_key:
        return generate_script_response(request)

    key_lock = get_idempotency_key_lock(endpoint, idempotency_key)

    with key_lock:
        # Recheck the cache after acquiring the lock.
        cached_response = get_idempotent_response(
            endpoint,
            idempotency_key,
            payload,
        )
        if cached_response is not None:
            return cached_response

        response = generate_script_response(request)

        save_idempotent_response(
            endpoint,
            idempotency_key,
            payload,
            response,
        )

        return response


def generate_script_response(request: ScriptRequest):
    """Generate scenes and narration for a script."""
    try:
        scenes = plan_scenes(
            script=request.script,
            words_per_minute=request.words_per_minute,
            minimum_scene_seconds=request.minimum_scene_seconds,
        )

        narration_path = generate_speech(
            request.script,
            "outputs/narration.wav",
        )

        return {
            "scene_count": len(scenes),
            "total_planned_duration": scenes[-1]["end_time"],
            "scenes": scenes,
            "narration_path": narration_path,
        }

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc






@app.post("/api/v1/render", status_code=202)
def render_project(
    request: RenderRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
):
    # Normalize the header when called directly by another function or test.
    if not isinstance(idempotency_key, str):
        idempotency_key = None

    payload = request.model_dump()

    # Requests without an idempotency key keep the normal behavior.
    if not idempotency_key:
        return create_render_job(request, background_tasks, payload)

    # Requests with the same endpoint and key must run one at a time.
    key_lock = get_idempotency_key_lock(
        "/api/v1/render",
        idempotency_key,
    )

    with key_lock:
        # Check again after acquiring the lock. Another request may
        # have created and cached the job while this request was waiting.
        cached_response = get_idempotent_response(
            "/api/v1/render",
            idempotency_key,
            payload,
        )
        if cached_response is not None:
            return cached_response

        return create_render_job(
            request,
            background_tasks,
            payload,
            idempotency_key,
        )


def create_render_job(
    request: RenderRequest,
    background_tasks: BackgroundTasks,
    payload: dict,
    idempotency_key: str | None = None,
):
    """Create a render job and cache its response when requested."""
    job_id = uuid.uuid4().hex
    output_dir = Path("outputs") / "jobs" / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "manifest.json"
    manifest = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "rendered": False,
        "video": None,
        "error": None,
        "assets": [],
        "note": "Job accepted and waiting for processing.",
    }
    save_job_manifest(manifest_path, manifest)

    background_tasks.add_task(
        process_render_job_with_cleanup,
        job_id,
        request,
    )

    response = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "message": (
            "Rendering job accepted. "
            "Check the job status endpoint for updates."
        ),
    }

    save_idempotent_response(
        "/api/v1/render",
        idempotency_key,
        payload,
        response,
    )

    return response



@app.post("/api/v1/broll/jobs", status_code=202)
def create_broll_job(
    request: BrollJobRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
):
    if not isinstance(idempotency_key, str):
        idempotency_key = None

    payload = request.model_dump()
    endpoint = "/api/v1/broll/jobs"

    # Requests without a key retain the normal behavior.
    if not idempotency_key:
        return generate_broll_job_response(request, background_tasks)

    key_lock = get_idempotency_key_lock(endpoint, idempotency_key)

    with key_lock:
        cached_response = get_idempotent_response(
            endpoint,
            idempotency_key,
            payload,
        )
        if cached_response is not None:
            return cached_response

        response = generate_broll_job_response(request, background_tasks)

        save_idempotent_response(
            endpoint,
            idempotency_key,
            payload,
            response,
        )

        return response


def generate_broll_job_response(
    request: BrollJobRequest,
    background_tasks: BackgroundTasks,
):
    """Validate B-roll input and create a render job."""
    if not request.script and not request.audio_url and not request.scenes:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one of script, audio_url, or scenes.",
        )

    if not request.script and request.scenes:
        raise HTTPException(
            status_code=422,
            detail=(
                "Scene-only requests are not implemented yet. "
                "Please provide a script or audio URL."
            ),
        )

    audio_path = None
    transcription = None

    if not request.script and request.audio_url:
        try:
            validated_url = validate_audio_url(request.audio_url)
            audio_path = download_audio(validated_url)

            validate_audio_duration(audio_path)
            transcription = transcribe_audio(audio_path)

            if not transcription["text"].strip():
                raise ValueError("No speech could be detected in the audio.")

            request.script = transcription["text"]

        except ValueError as exc:
            if audio_path:
                Path(audio_path).unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        except FileNotFoundError as exc:
            if audio_path:
                Path(audio_path).unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        except Exception as exc:
            if audio_path:
                Path(audio_path).unlink(missing_ok=True)
            raise HTTPException(
                status_code=422,
                detail=(
                    "Audio processing failed. "
                    "Check the audio URL and file format."
                ),
            ) from exc

    render_request = RenderRequest(
        script=request.script,
        words_per_minute=request.words_per_minute,
        minimum_scene_seconds=request.minimum_scene_seconds,
        aspect_ratio=request.aspect_ratios[0],
        aspect_ratios=request.aspect_ratios,
        narration_audio_path=audio_path,
        transcription_segments=(
            transcription["segments"] if transcription else None
        ),
    )

    try:
        return render_project(render_request, background_tasks)
    except Exception:
        if audio_path:
            Path(audio_path).unlink(missing_ok=True)
        raise


@app.get("/api/v1/jobs/{job_id}")
def get_job_status(job_id: str):
    if len(job_id) != 32 or any(
        char not in "0123456789abcdef"
        for char in job_id.lower()
    ):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_job_id",
                "message": "The job ID format is invalid.",
            },
        )
    job_id = job_id.lower()
    # Check both locations: the normal application folder and
    # the relative jobs folder used by the test.
    possible_paths = [
        Path("outputs") / "jobs" / job_id / "manifest.json",
        Path("jobs") / job_id / "manifest.json",
    ]

    manifest_path = next(
        (path for path in possible_paths if path.is_file()),
        None,
    )

    if manifest_path is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "job_not_found",
                "message": "No job was found for this ID.",
            },
        )

    try:
        with manifest_path.open("r", encoding="utf-8") as file:
            manifest = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "manifest_read_failed",
                "message": "The job manifest could not be read.",
            },
        ) from exc

    
    return {
        "job_id": job_id,
        "status": manifest.get("status", "unknown"),
        "progress": manifest.get("progress", 0),
        "rendered": manifest.get("rendered", False),
        "video": manifest.get("video"),
        "videos": manifest.get("videos", []),
        "error": manifest.get("error"),
        "note": manifest.get("note"),
        "scene_count": manifest.get(
            "scene_count",
            len(manifest.get("assets", [])),
        ),
    }




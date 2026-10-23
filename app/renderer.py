"""Minimal FFmpeg renderer for the first PS3 milestone."""
from pathlib import Path
import shutil
import subprocess

DIMENSIONS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
}


class RenderError(RuntimeError):
    """Raised when input validation or FFmpeg rendering fails."""


def _require_file(path: str | Path, label: str) -> Path:
    file_path = Path(path)
    if not file_path.is_file():
        raise RenderError(f"{label} file does not exist: {file_path}")
    return file_path


def render_video(
    video_path: str | Path,
    audio_path: str | Path,
    output_path: str | Path,
    aspect_ratio: str = "16:9",
) -> Path:
    """
    Put narration audio over one B-roll clip and normalize the output.

    This first version is intentionally small: one clip + one audio file.
    Scene matching, captions, timelines, and background jobs will be added next.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RenderError(
            "FFmpeg was not found on PATH. Install FFmpeg and reopen the terminal."
        )

    video = _require_file(video_path, "Video")
    audio = _require_file(audio_path, "Audio")
    if aspect_ratio not in DIMENSIONS:
        raise RenderError(
            f"Unsupported aspect ratio {aspect_ratio!r}; use one of {list(DIMENSIONS)}"
        )

    width, height = DIMENSIONS[aspect_ratio]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Scale to fill the target canvas, then crop the excess. This avoids letterboxing.
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},fps=30,format=yuv420p"
    )
    command = [
        ffmpeg, "-y",
        "-i", str(video),
        "-i", str(audio),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-vf", video_filter,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        # Keep the user-facing error short; full FFmpeg output is useful for debugging.
        tail = (result.stderr or result.stdout)[-1800:]
        raise RenderError(f"FFmpeg render failed:\n{tail}")

    if not output.is_file() or output.stat().st_size == 0:
        raise RenderError("FFmpeg returned success but the output file is missing or empty.")
    return output



def render_scenes(
    clip_paths: list[str | Path],
    durations: list[float],
    audio_path: str | Path,
    output_path: str | Path,
    aspect_ratio: str = "16:9",
) -> Path:
    """
    Join multiple B-roll clips in order and add one narration audio track.

    Each clip is trimmed to its corresponding duration.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RenderError(
            "FFmpeg was not found on PATH. Install FFmpeg and reopen the terminal."
        )

    if not clip_paths:
        raise RenderError("At least one B-roll clip is required.")

    if len(clip_paths) != len(durations):
        raise RenderError("Each B-roll clip must have one matching duration.")

    if any(duration <= 0 for duration in durations):
        raise RenderError("Every scene duration must be greater than zero.")

    if aspect_ratio not in DIMENSIONS:
        raise RenderError(
            f"Unsupported aspect ratio {aspect_ratio!r}; "
            f"use one of {list(DIMENSIONS)}"
        )

    clips = [
        _require_file(path, f"Video clip {index + 1}")
        for index, path in enumerate(clip_paths)
    ]
    audio = _require_file(audio_path, "Audio")

    width, height = DIMENSIONS[aspect_ratio]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    command = [ffmpeg, "-y"]

    for clip in clips:
        command.extend(["-i", str(clip)])

    audio_input_index = len(clips)
    command.extend(["-i", str(audio)])

    filters = []
    video_labels = []

    for index, duration in enumerate(durations):
        label = f"scene{index}"
        video_labels.append(f"[{label}]")

        filters.append(
            f"[{index}:v:0]"
            f"trim=duration={duration},"
            "setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            "fps=30,format=yuv420p"
            f"[{label}]"
        )

    concat_inputs = "".join(video_labels)
    filters.append(
        f"{concat_inputs}concat=n={len(clips)}:v=1:a=0[outv]"
    )

    command.extend([
        "-filter_complex", ";".join(filters),
        "-map", "[outv]",
        "-map", f"{audio_input_index}:a:0",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output),
    ])

    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        tail = (result.stderr or result.stdout)[-1800:]
        raise RenderError(f"Multi-scene FFmpeg render failed:\n{tail}")

    if not output.is_file() or output.stat().st_size == 0:
        raise RenderError(
            "FFmpeg returned success but the output file is missing or empty."
        )

    return output


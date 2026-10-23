from pathlib import Path
import pytest
from app.renderer import RenderError, render_video


def test_missing_video_is_reported(tmp_path: Path):
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"placeholder")
    with pytest.raises(RenderError, match="Video file does not exist"):
        render_video(tmp_path / "missing.mp4", audio, tmp_path / "out.mp4")


def test_invalid_aspect_ratio_is_reported(tmp_path: Path):
    video = tmp_path / "clip.mp4"
    audio = tmp_path / "voice.wav"
    video.write_bytes(b"placeholder")
    audio.write_bytes(b"placeholder")
    with pytest.raises(RenderError, match="Unsupported aspect ratio"):
        render_video(video, audio, tmp_path / "out.mp4", "4:3")



def test_render_scenes_rejects_missing_clip(tmp_path: Path):
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"placeholder")

    with pytest.raises(RenderError, match="Video clip 1 file does not exist"):
        from app.renderer import render_scenes

        render_scenes(
            [tmp_path / "missing.mp4"],
            [2.0],
            audio,
            tmp_path / "out.mp4",
        )


def test_render_scenes_requires_matching_durations(tmp_path: Path):
    from app.renderer import render_scenes

    with pytest.raises(RenderError, match="matching duration"):
        render_scenes(
            ["clip1.mp4", "clip2.mp4"],
            [2.0],
            "voice.wav",
            tmp_path / "out.mp4",
        )


def test_render_scenes_rejects_non_positive_duration(tmp_path: Path):
    from app.renderer import render_scenes

    with pytest.raises(RenderError, match="greater than zero"):
        render_scenes(
            ["clip1.mp4"],
            [0],
            "voice.wav",
            tmp_path / "out.mp4",
        )


def test_render_scenes_rejects_invalid_aspect_ratio(tmp_path: Path):
    from app.renderer import render_scenes

    with pytest.raises(RenderError, match="Unsupported aspect ratio"):
        render_scenes(
            ["clip1.mp4"],
            [2.0],
            "voice.wav",
            tmp_path / "out.mp4",
            "4:3",
        )


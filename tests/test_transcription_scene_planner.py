
import pytest

from app.scene_planner import plan_scenes_from_transcription


def test_scenes_use_actual_transcription_timestamps():
    transcription = {
        "segments": [
            {"start": 0.5, "end": 1.4, "text": "Hello everyone."},
            {"start": 1.4, "end": 2.8, "text": "Welcome to our video."},
            {"start": 2.8, "end": 5.0, "text": "Let's begin today."},
        ]
    }

    scenes = plan_scenes_from_transcription(
        transcription,
        minimum_scene_seconds=2.0,
    )

    assert len(scenes) == 2
    assert scenes[0]["start_time"] == 0.5
    assert scenes[0]["end_time"] == 2.8
    assert scenes[0]["duration"] == 2.3
    assert scenes[1]["start_time"] == 2.8
    assert scenes[1]["end_time"] == 5.0


def test_empty_transcription_segments_are_rejected():
    with pytest.raises(ValueError, match="no timestamped speech segments"):
        plan_scenes_from_transcription({"segments": []})


def test_invalid_transcription_timestamps_are_rejected():
    transcription = {
        "segments": [
            {"start": 2.0, "end": 1.0, "text": "Invalid timing."},
        ]
    }

    with pytest.raises(ValueError, match="invalid timestamps"):
        plan_scenes_from_transcription(transcription)

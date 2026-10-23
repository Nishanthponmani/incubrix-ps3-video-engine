
import pytest

from app.scene_planner import (
    split_sentences,
    extract_keywords,
    plan_scenes,
)


def test_split_sentences():
    script = (
        "AI helps doctors. Robots assist surgeons! "
        "Technology keeps improving?"
    )

    result = split_sentences(script)

    assert len(result) == 3
    assert result[0] == "AI helps doctors."
    assert result[1] == "Robots assist surgeons!"


def test_empty_script_is_rejected():
    with pytest.raises(ValueError, match="Script cannot be empty"):
        plan_scenes("   ")


def test_scene_timing_is_continuous():
    scenes = plan_scenes(
        "AI helps doctors. Robots assist surgeons."
    )

    assert len(scenes) == 2
    assert scenes[0]["start_time"] == 0.0
    assert scenes[0]["end_time"] == scenes[1]["start_time"]
    assert scenes[0]["duration"] >= 2.0


def test_scene_ids_are_unique():
    scenes = plan_scenes(
        "AI helps doctors. Robots assist surgeons. "
        "Computers analyze images."
    )

    ids = [scene["scene_id"] for scene in scenes]

    assert len(ids) == len(set(ids))
    assert ids == ["scene_001", "scene_002", "scene_003"]


def test_invalid_timing_settings_are_rejected():
    with pytest.raises(ValueError):
        plan_scenes("AI helps doctors.", words_per_minute=0)

    with pytest.raises(ValueError):
        plan_scenes("AI helps doctors.", minimum_scene_seconds=0)


def test_keyword_extraction():
    keywords = extract_keywords(
        "Doctors analyze medical images."
    )

    assert "doctors" in keywords
    assert "analyze" in keywords
    assert len(keywords) <= 3

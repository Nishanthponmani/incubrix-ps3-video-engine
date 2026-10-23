
import json
from unittest import result

from app.broll_selector import select_broll


def test_selects_clip_matching_scene_terms(tmp_path):
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()

    clip = clips_dir / "doctors.mp4"
    clip.write_bytes(b"test video")

    result = select_broll(
        [{"search_terms": ["doctors", "medical"]}],
        clips_dir=str(clips_dir),
    )

    assert result[0]["status"] == "matched"
    assert result[0]["clip_path"] == str(clip)
    assert result[0]["matched_keywords"] == ["doctors"]
    assert result[0]["license"] == "unverified"
    assert result[0]["license_verified"] is False


def test_reports_missing_clip(tmp_path):
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    (clips_dir / "sample.mp4").write_bytes(b"test video")

    result = select_broll(
        [{"search_terms": ["robots", "surgeons"]}],
        clips_dir=str(clips_dir),
    )

    assert result[0]["status"] == "missing"
    assert result[0]["clip_path"] is None


def test_does_not_reuse_clip_for_another_scene(tmp_path):
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    (clips_dir / "robots.mp4").write_bytes(b"test video")

    result = select_broll(
        [
            {"search_terms": ["robots"]},
            {"search_terms": ["robots"]},
        ],
        clips_dir=str(clips_dir),
    )

    assert result[0]["status"] == "matched"
    assert result[1]["status"] == "missing"


def test_reads_clip_licence_metadata(tmp_path):
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()

    clip = clips_dir / "medical.mp4"
    clip.write_bytes(b"test video")

    metadata = {
        "source": "Example source",
        "source_url": "https://example.com/clip",
        "creator": "Example creator",
        "license": "Example licence",
        "attribution": "Example creator",
        "license_verified": True,
    }
    clip.with_suffix(".json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    result = select_broll(
        [{"search_terms": ["medical"]}],
        clips_dir=str(clips_dir),
    )

    assert result[0]["status"] == "matched"
    assert result[0]["source"] == "Example source"
    assert result[0]["license"] == "Example licence"
    assert result[0]["attribution"] == "Example creator"
    assert result[0]["license_verified"] is True
    assert result[0]["source_url"] == "https://example.com/clip"
    assert result[0]["creator"] == "Example creator"

    
def test_incomplete_licence_metadata_is_not_verified(tmp_path):
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()

    clip = clips_dir / "medical.mp4"
    clip.write_bytes(b"test video")

    metadata = {
        "source": "Example source",
        "source_url": "https://example.com/clip",
        "creator": "Example creator",
        "license": "",
        "attribution": "Example creator",
        "license_verified": True,
    }

    clip.with_suffix(".json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    result = select_broll(
        [{"search_terms": ["medical"]}],
        clips_dir=str(clips_dir),
    )

    assert result[0]["status"] == "matched"
    assert result[0]["source_url"] == "https://example.com/clip"
    assert result[0]["creator"] == "Example creator"
    assert result[0]["license_verified"] is False
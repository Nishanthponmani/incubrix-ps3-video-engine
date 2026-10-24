
import json
from pathlib import Path

from app.broll_selector import select_broll


def format_srt_time(seconds):
    """Convert seconds into the SRT timestamp format."""
    milliseconds = round(float(seconds) * 1000)

    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1000)

    return (
        f"{hours:02}:{minutes:02}:{seconds:02},"
        f"{milliseconds:03}"
    )


def scene_value(scene, field, default=None):
    """Read a field from either a dictionary or a scene object."""
    if isinstance(scene, dict):
        return scene.get(field, default)

    return getattr(scene, field, default)


def export_project(scenes, narration_path, output_dir="outputs"):
    """
    Export subtitles, timeline, and a manifest with B-roll selections.

    This function does not render a final video. It records whether
    the project has suitable, verified assets available.
    """
    output_folder = Path(output_dir)
    output_folder.mkdir(parents=True, exist_ok=True)

    narration = Path(narration_path)

    # 1. Generate subtitles.
    subtitle_blocks = []

    for index, scene in enumerate(scenes, start=1):
        start = scene_value(scene, "start_time", 0)
        end = scene_value(scene, "end_time", 0)
        text = scene_value(scene, "text", "")

        subtitle_blocks.append(
            f"{index}\n"
            f"{format_srt_time(start)} --> "
            f"{format_srt_time(end)}\n"
            f"{text}"
        )

    subtitles_path = output_folder / "subtitles.srt"
    subtitles_path.write_text(
        "\n\n".join(subtitle_blocks) + ("\n" if subtitle_blocks else ""),
        encoding="utf-8",
    )
    # 2. Select local B-roll clips before building the timeline.
    broll_results = select_broll(scenes)
    assets_by_scene = {
        item["scene_index"]: item
        for item in broll_results
    }

    # 3. Generate the timeline with B-roll metadata.
    timeline_scenes = []

    for index, scene in enumerate(scenes, start=1):
        asset = assets_by_scene.get(index, {})

        timeline_scenes.append({
            "scene_id": scene_value(scene, "scene_id"),
            "text": scene_value(scene, "text", ""),
            "start_time": scene_value(scene, "start_time", 0),
            "end_time": scene_value(scene, "end_time", 0),
            "duration": scene_value(scene, "duration", 0),
            "search_terms": scene_value(scene, "search_terms", []),
            "selected_clip": asset.get("clip_path"),
            "asset_status": asset.get("status", "missing"),
            "matched_keywords": asset.get("matched_keywords", []),
            "source": asset.get("source"),
            "license": asset.get("license"),
            "attribution": asset.get("attribution"),
            "source_url": asset.get("source_url"),
            "creator": asset.get("creator"),
            "description": asset.get("description", ""),
            "license_verified": asset.get("license_verified", False),
            "verification_reason": asset.get("verification_reason"),
        })

    total_duration = max(
        (item["end_time"] for item in timeline_scenes),
        default=0,
    )

    timeline_data = {
        "total_duration": total_duration,
        "scene_count": len(timeline_scenes),
        "scenes": timeline_scenes,
    }

    timeline_path = output_folder / "timeline.json"
    timeline_path.write_text(
        json.dumps(timeline_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    

    # 4. Check whether every scene has a matched, verified asset.
    all_assets_ready = (
        len(broll_results) == len(scenes)
        and all(
            item["status"] == "matched"
            and item["license_verified"] is True
            for item in broll_results
        )
    )

    narration_exists = narration.is_file() and narration.stat().st_size > 0

    # 5. Record the current project state.
    if not narration_exists:
        project_status = "needs_narration"
    elif all_assets_ready:
        project_status = "assets_ready_for_render"
    else:
        project_status = "needs_assets"

    manifest = {
        "status": project_status,
        "narration": str(narration),
        "subtitles": str(subtitles_path),
        "timeline": str(timeline_path),
        "video": None,
        "assets": broll_results,
        "rendered": False,
        "note": (
            "Final video rendering has not been performed. "
            "Every scene needs a matched clip with verified licence "
            "metadata before the project can be considered ready."
        ),
    }

    manifest_path = output_folder / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    
    return {
        "subtitles": str(subtitles_path),
        "timeline": str(timeline_path),
        "manifest": str(manifest_path),
        "status": project_status,
        "scene_count": len(scenes),
        "total_duration": total_duration,
        "assets": broll_results,
    }


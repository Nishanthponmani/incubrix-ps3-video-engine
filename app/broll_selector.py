
from pathlib import Path
import json
import re

from numpy import clip


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}

KEYWORD_ALIASES = {
    "doctors": {"doctor"},
    "doctor": {"doctors"},
    "robots": {"robot", "robotic"},
    "robot": {"robots", "robotic"},
    "robotic": {"robot", "robots"},
    "surgeons": {"surgeon"},
    "surgeon": {"surgeons"},
    "operations": {"operation", "surgery", "surgical"},
    "operation": {"operations", "surgery", "surgical"},
    "medical": {"medicine"},
    "imaging": {"image", "images", "scan", "scans"},
    "artificial": {"medical", "robotic"},
    "intelligence": {"medical", "robotic"},
    "transforming": {"medical", "robotic"},
    "healthcare": {"medical", "doctor", "robotic"},
    "detect": {"medical", "imaging", "scan"},
    "diseases": {"medical", "imaging", "doctor"},
    "disease": {"diseases", "medical", "imaging"},
    "support": {"medical", "doctor"},
}



def normalize_words(text):
    """Convert text into lowercase words for simple filename matching."""
    return set(re.findall(r"[a-z0-9]+", str(text).lower()))


def load_clip_metadata(clip_path):
    """
    Read metadata from a JSON file beside the video.

    Example:
        assets/clips/doctor_surgery.mp4
        assets/clips/doctor_surgery.json

    Metadata is accepted as verified only when required fields are
    present and license_verified is explicitly true.
    """
    metadata_path = clip_path.with_suffix(".json")

    if not metadata_path.exists():
        return {
            "source": "unknown",
            "license": "unverified",
            "attribution": "unknown",
            "license_verified": False,
            "verification_reason": "Metadata file is missing.",
        }

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "source": None,
            "license": None,
            "attribution": None,
            "license_verified": False,
            "verification_reason": "Metadata file is invalid or unreadable.",
        }

    if not isinstance(metadata, dict):
        metadata = {}

    source = metadata.get("source")
    license_name = metadata.get("license")
    attribution = metadata.get("attribution")

    required_fields_present = all(
        isinstance(value, str)
        and value.strip()
        and value.strip().lower() not in {
            "unknown",
            "unverified",
            "none",
            "null",
        }
        for value in (source, license_name, attribution)
    )

    explicitly_verified = metadata.get("license_verified") is True

    verified = required_fields_present and explicitly_verified

    if verified:
        reason = (
            "Metadata fields are present and verification is declared. "
            "The original source and licence terms still require review."
        )
    elif not required_fields_present:
        reason = (
            "Source, licence, and attribution must all contain "
            "meaningful values."
        )
    else:
        reason = (
            "Licence verification has not been explicitly confirmed "
            "in the metadata."
        )

    return {
        "source": source if isinstance(source, str) and source.strip() else "unknown",
        "license": license_name if isinstance(license_name, str) and license_name.strip() else "unverified",
        "attribution": attribution if isinstance(attribution, str) and attribution.strip() else "unknown",
        "source_url": metadata.get("source_url"),
        "creator": metadata.get("creator"),
        "description": metadata.get("description", ""),
        "license_verified": verified,
        "verification_reason": reason,
    }


def select_broll(scenes, clips_dir="assets/clips"):
    """
    Match scene keywords against local video filenames.

    Filename matching is not semantic video understanding.
    A matched clip is not automatically considered licensed or ready.
    """
    clips_folder = Path(clips_dir)

    if not clips_folder.exists():
        raise FileNotFoundError(
            f"Clip folder does not exist: {clips_folder}"
        )

    clips = sorted(
        path
        for path in clips_folder.iterdir()
        if path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
    )

    results = []
    used_clips = set()

    for index, scene in enumerate(scenes, start=1):
        if isinstance(scene, dict):
            keywords = scene.get(
                "search_terms",
                scene.get("keywords", []),
            )
        else:
            keywords = getattr(
                scene,
                "search_terms",
                getattr(scene, "keywords", []),
            )

        keyword_set = set()

        for keyword in keywords:
            keyword_set.update(normalize_words(keyword))

        best_clip = None
        best_matches = set()

        for clip in clips:
            if clip.name in used_clips:
                continue

            #filename_words = normalize_words(clip.stem)
            metadata = load_clip_metadata(clip)

            description_words = normalize_words(
            metadata.get("description", "")
            )

            filename_words = normalize_words(clip.stem) | description_words
            expanded_keywords = set(keyword_set)

            for keyword in keyword_set:
                expanded_keywords.update(KEYWORD_ALIASES.get(keyword, set()))

            matches = expanded_keywords & filename_words

            if len(matches) > len(best_matches):
                best_clip = clip
                best_matches = matches

        if best_clip is None or not best_matches:
            results.append({
                "scene_index": index,
                "keywords": sorted(keyword_set),
                "status": "missing",
                "clip_path": None,
                "matched_keywords": [],
                "source": None,
                "license": None,
                "attribution": None,
                "license_verified": False,
                "verification_reason": (
                    "No unused clip matched the scene keywords."
                ),
            })
            continue

        used_clips.add(best_clip.name)
        metadata = load_clip_metadata(best_clip)

        results.append({
            "scene_index": index,
            "keywords": sorted(keyword_set),
            "status": "matched",
            "clip_path": str(best_clip),
            "matched_keywords": sorted(best_matches),
            **metadata,
        })

    return results

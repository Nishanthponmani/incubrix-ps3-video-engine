
import re

# Common words that are not very useful for finding B-roll.

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "to", "of",
    "and", "or", "in", "on", "for", "with", "by", "from", "at",
    "it", "this", "that", "as", "be", "can", "will", "has", "have",
    "we", "you", "they", "their", "our", "your", "how", "why",
    "helps", "help", "use", "uses", "using", "during", "assist",
    "assists", "perform", "performs", "provide", "provides",
}



def split_sentences(script: str) -> list[str]:
    """Split a script into sentences and remove empty entries."""
    script = script.strip()

    if not script:
        raise ValueError("Script cannot be empty.")

    # Split at sentence-ending punctuation or line breaks.
    parts = re.split(r"(?<=[.!?])\s+|\n+", script)

    return [part.strip() for part in parts if part.strip()]


def extract_keywords(sentence: str, limit: int = 3) -> list[str]:
    """Extract useful search keywords, preserving their order."""
    words = re.findall(r"[A-Za-z0-9]+", sentence.lower())

    keywords = []
    for word in words:
        if word not in STOPWORDS and len(word) > 2:
            if word not in keywords:
                keywords.append(word)

        if len(keywords) == limit:
            break

    return keywords


def plan_scenes(
    script: str,
    words_per_minute: int = 150,
    minimum_scene_seconds: float = 2.0,
) -> list[dict]:
    """Convert a script into a basic, timed scene plan."""
    if words_per_minute <= 0:
        raise ValueError("words_per_minute must be greater than zero.")

    if minimum_scene_seconds <= 0:
        raise ValueError("minimum_scene_seconds must be greater than zero.")

    sentences = split_sentences(script)
    scenes = []
    current_time = 0.0

    for index, sentence in enumerate(sentences, start=1):
        word_count = len(sentence.split())

        duration = max(
            minimum_scene_seconds,
            word_count / words_per_minute * 60,
        )
        duration = round(duration, 2)
        end_time = round(current_time + duration, 2)

        scenes.append({
            "scene_id": f"scene_{index:03d}",
            "text": sentence,
            "start_time": round(current_time, 2),
            "end_time": end_time,
            "duration": duration,
            "search_terms": extract_keywords(sentence),
        })

        current_time = end_time

    return scenes



def plan_scenes_from_transcription(
    transcription: dict,
    minimum_scene_seconds: float = 2.0,
) -> list[dict]:
    """Create scenes using the actual timestamps from audio transcription."""
    if minimum_scene_seconds <= 0:
        raise ValueError("minimum_scene_seconds must be greater than zero.")

    segments = transcription.get("segments", [])

    if not segments:
        raise ValueError("Transcription contains no timestamped speech segments.")

    scenes = []
    current_scene = None

    for segment in segments:
        text = segment.get("text", "").strip()
        start = float(segment["start"])
        end = float(segment["end"])

        if not text:
            continue

        if start < 0 or end <= start:
            raise ValueError("Transcription contains invalid timestamps.")

        # Merge short segments into a scene until the minimum duration is met.
        if current_scene is None:
            current_scene = {
                "text": text,
                "start_time": start,
                "end_time": end,
            }
        else:
            current_scene["text"] += " " + text
            current_scene["end_time"] = end

        duration = current_scene["end_time"] - current_scene["start_time"]

        if duration >= minimum_scene_seconds:
            scenes.append(current_scene)
            current_scene = None

    # Keep any remaining speech as the final scene.
    if current_scene is not None:
        scenes.append(current_scene)

    planned_scenes = []

    for index, scene in enumerate(scenes, start=1):
        text = scene["text"]
        start = round(scene["start_time"], 2)
        end = round(scene["end_time"], 2)

        planned_scenes.append({
            "scene_id": f"scene_{index:03d}",
            "text": text,
            "start_time": start,
            "end_time": end,
            "duration": round(end - start, 2),
            "search_terms": extract_keywords(text),
        })

    return planned_scenes

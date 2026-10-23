
from pathlib import Path

from faster_whisper import WhisperModel


_model = None


def get_model():
    """Load the speech recognition model only when first needed."""
    global _model

    if _model is None:
        _model = WhisperModel(
            "base",
            device="cpu",
            compute_type="int8",
        )

    return _model


def transcribe_audio(audio_path: str) -> dict:
    """Transcribe an audio file and return text with segment timestamps."""
    path = Path(audio_path)

    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    model = get_model()

    segments, info = model.transcribe(
        str(path),
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
    )

    results = []
    full_text = []

    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue

        full_text.append(text)
        results.append({
            "start": round(segment.start, 3),
            "end": round(segment.end, 3),
            "text": text,
        })

    return {
        "text": " ".join(full_text),
        "language": info.language,
        "duration": info.duration,
        "segments": results,
    }

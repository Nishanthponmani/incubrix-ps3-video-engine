
from pathlib import Path
import pyttsx3


def generate_speech(
    text: str,
    output_path: str = "outputs/narration.wav",
) -> str:
    """Generate speech using a locally installed system voice."""
    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    engine = pyttsx3.init()
    engine.setProperty("rate", 165)
    engine.save_to_file(text.strip(), str(output.resolve()))
    engine.runAndWait()
    engine.stop()

    if not output.exists() or output.stat().st_size == 0:
        raise RuntimeError("Speech audio was not generated.")

    return str(output)


if __name__ == "__main__":
    sample_text = (
        "Artificial intelligence is changing healthcare. "
        "Doctors use technology to analyze medical images."
    )
    result = generate_speech(sample_text)
    print(f"Speech saved to: {result}")


import ipaddress
import socket
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
import av

MAX_AUDIO_SECONDS = 10 * 60  # 10 minutes


MAX_AUDIO_BYTES = 100 * 1024 * 1024  # 100 MB
ALLOWED_AUDIO_HOSTS = {"http", "https"}


def validate_audio_url(audio_url: str) -> str:
    """Validate an audio URL and reject local/private network targets."""
    parsed = urlparse(audio_url)

    if parsed.scheme not in ALLOWED_AUDIO_HOSTS:
        raise ValueError("Audio URL must use HTTP or HTTPS.")

    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Invalid audio URL.")

    try:
        addresses = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError("Audio URL hostname could not be resolved.") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("Audio URL must resolve to a public IP address.")

    return audio_url


def download_audio(audio_url: str) -> str:
    """Download audio to a temporary file with a size limit."""
    validate_audio_url(audio_url)

    response = requests.get(
        audio_url,
        stream=True,
        timeout=(5, 30),
        allow_redirects=False,
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    if not (
        content_type.startswith("audio/")
        or "octet-stream" in content_type
    ):
        response.close()
        raise ValueError("The URL did not return an audio content type.")

    content_length = response.headers.get("Content-Length")
    if content_length and int(content_length) > MAX_AUDIO_BYTES:
        response.close()
        raise ValueError("Audio file exceeds the 100 MB download limit.")

    temp_file = tempfile.NamedTemporaryFile(
        prefix="incubrix_audio_",
        suffix=".audio",
        delete=False,
    )

    total_bytes = 0
    try:
        with temp_file as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue

                total_bytes += len(chunk)
                if total_bytes > MAX_AUDIO_BYTES:
                    raise ValueError("Audio file exceeds the 100 MB download limit.")

                output.write(chunk)

        return str(Path(temp_file.name))

    except Exception:
        Path(temp_file.name).unlink(missing_ok=True)
        raise

    finally:
        response.close()

def validate_audio_duration(audio_path: str) -> float:
    """Reject audio files longer than 10 minutes."""
    try:
        with av.open(audio_path) as container:
            if container.duration is None:
                raise ValueError("Could not determine audio duration.")

            duration_seconds = container.duration / av.time_base

    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The audio file is invalid or unreadable.") from exc

    if duration_seconds <= 0:
        raise ValueError("Audio duration must be greater than zero.")

    if duration_seconds > MAX_AUDIO_SECONDS:
        raise ValueError("Audio must not exceed 10 minutes.")

    return duration_seconds
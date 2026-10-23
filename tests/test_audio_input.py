
import pytest

from app.audio_input import validate_audio_url


@pytest.mark.parametrize(
    "url",
    [
        "file:///C:/audio.wav",
        "ftp://example.com/audio.wav",
        "http://127.0.0.1/audio.wav",
        "http://localhost/audio.wav",
        "http://192.168.1.10/audio.wav",
    ],
)
def test_rejects_unsafe_audio_urls(url):
    with pytest.raises(ValueError):
        validate_audio_url(url)


def test_rejects_url_with_credentials():
    with pytest.raises(ValueError):
        validate_audio_url("https://user:password@example.com/audio.wav")


def test_rejects_unresolvable_hostname(monkeypatch):
    import socket

    def fake_getaddrinfo(*args, **kwargs):
        raise socket.gaierror("hostname not found")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(ValueError, match="could not be resolved"):
        validate_audio_url("https://audio.example.invalid/sample.wav")

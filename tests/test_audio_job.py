
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_audio_job_rejects_request_without_inputs():
    response = client.post("/api/v1/broll/jobs", json={})

    assert response.status_code == 422


def test_audio_job_rejects_invalid_audio_url():
    response = client.post(
        "/api/v1/broll/jobs",
        json={"audio_url": "file:///C:/audio.wav"},
    )

    assert response.status_code == 422


def test_audio_job_uses_transcription_text():
    with (
        patch("app.main.validate_audio_url", return_value="https://example.com/audio.wav"),
        patch("app.main.download_audio", return_value="temporary_audio.wav"),
        patch("app.main.validate_audio_duration", return_value=12.0),
        patch(
            "app.main.transcribe_audio",
            return_value={
                "text": "A short test narration.",
                "language": "en",
                "duration": 12.0,
                "segments": [],
            },
        ),
        patch("app.main.render_project") as render_project,
        patch("app.main.Path.unlink") as unlink,
    ):
        render_project.return_value = {"job_id": "test-job"}

        response = client.post(
            "/api/v1/broll/jobs",
            json={"audio_url": "https://example.com/audio.wav"},
        )

    assert response.status_code == 202
    assert render_project.called

    render_request = render_project.call_args.args[0]
    assert render_request.script == "A short test narration."
    unlink.assert_not_called()


def test_audio_cleanup_runs_after_background_job():
    from unittest.mock import Mock
    from app.main import process_render_job_with_cleanup

    request = Mock()
    request.narration_audio_path = "temporary_audio.wav"

    with (
        patch("app.main.process_render_job", side_effect=RuntimeError("Render failed")),
        patch("app.main.Path.unlink") as unlink,
    ):
        try:
            process_render_job_with_cleanup("test-job", request)
        except RuntimeError:
            pass

    unlink.assert_called_once_with(missing_ok=True)

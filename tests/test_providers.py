import base64
import io
import json
import wave
from pathlib import Path

import edge_tts
import httpx
import pytest
from PIL import Image

from kiddy.media import ffmpeg
from kiddy.media.audio import duration
from kiddy.providers.images import CloudflareImages, ImageServiceError
from kiddy.providers.tts import EdgeVoices, GroqVoices, VoiceServiceError, chunks


def fake_cloudflare(answer: dict, status: int = 200) -> tuple[httpx.Client, list[httpx.Request]]:
    sent = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(status, json=answer)

    return httpx.Client(transport=httpx.MockTransport(handle)), sent


def jpeg_b64(size: tuple[int, int]) -> str:
    buffer = io.BytesIO()
    Image.new("RGB", size, (250, 200, 120)).save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode()


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    monkeypatch.setenv("GROQ_API_KEY", "key")


def wav_bytes(seconds: float, rate: int = 44_100) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(int(seconds * rate) * 4))
    return buffer.getvalue()


def fake_groq(*responses: httpx.Response) -> tuple[httpx.Client, list[dict]]:
    sent, queue = [], list(responses)

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return httpx.Client(transport=httpx.MockTransport(handle)), sent


def test_long_lines_are_split_under_the_limit():
    text = "Bees visit many flowers. " * 12
    pieces = chunks(text, 120)
    assert len(pieces) > 1 and all(len(piece) <= 120 for piece in pieces)
    assert " ".join(pieces) == text.strip()


def test_voices_are_directed_split_and_converted(tmp_path):
    client, sent = fake_groq(httpx.Response(200, content=wav_bytes(1.0)))
    voices = GroqVoices("canopylabs/orpheus-v1-english", 6000, client)

    out = voices.speak("Bees visit many flowers. " * 12, "hannah", "warm", tmp_path / "line.wav")

    assert len(sent) > 1 and all(len(body["input"]) <= 200 for body in sent)
    assert all(body["input"].startswith("[warm] ") and body["voice"] == "hannah" for body in sent)
    with wave.open(str(out)) as wav:  # 44.1 kHz stereo in, the shared voice format out
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (24_000, 1, 2)
    assert duration(out) == pytest.approx(len(sent) * 1.0 + (len(sent) - 1) * 0.15, abs=0.05)
    assert [p.name for p in tmp_path.iterdir()] == ["line.wav"]  # no pieces left behind


def test_short_rate_limits_wait_and_retry(tmp_path):
    waits = []
    client, sent = fake_groq(httpx.Response(429, headers={"retry-after": "7"}),
                             httpx.Response(200, content=wav_bytes(0.5)))
    voices = GroqVoices("m", 6000, client)
    voices.sleep = waits.append
    voices.speak("Hello!", "hannah", "", tmp_path / "x.wav")
    assert waits == [7.0] and len(sent) == 2


def test_daily_limit_and_missing_terms_stop_with_a_clear_message(tmp_path):
    client, _ = fake_groq(httpx.Response(429, headers={"retry-after": "7200"}))
    with pytest.raises(VoiceServiceError, match="used up"):
        GroqVoices("m", 6000, client).speak("Hello!", "hannah", "", tmp_path / "x.wav")
    terms = {"error": {"message": "requires terms acceptance", "code": "model_terms_required"}}
    client, _ = fake_groq(httpx.Response(400, json=terms))
    with pytest.raises(VoiceServiceError, match="terms acceptance"):
        GroqVoices("m", 6000, client).speak("Hello!", "hannah", "", tmp_path / "y.wav")


def test_renders_small_sends_references_and_upscales(tmp_path):
    client, sent = fake_cloudflare({"success": True, "result": {"image": jpeg_b64((1024, 576))}})
    reference = tmp_path / "fennel.png"
    Image.new("RGB", (512, 512)).save(reference)
    images = CloudflareImages("@cf/black-forest-labs/flux-2-klein-4b", (1024, 576), client)

    out = images.generate("a fox", [reference], (1920, 1080), tmp_path / "scene.png", seed=7)

    form = sent[0].content.decode("latin-1")
    for field, value in [("prompt", "a fox"), ("width", "1024"), ("height", "576"), ("seed", "7")]:
        assert f'name="{field}"\r\n\r\n{value}\r\n' in form
    assert 'name="input_image_0"; filename="fennel.png"' in form
    assert sent[0].url.path.endswith("/acct/ai/run/@cf/black-forest-labs/flux-2-klein-4b")
    with Image.open(out) as picture:
        assert picture.size == (1920, 1080)


def test_small_pictures_render_at_their_own_size(tmp_path):
    client, sent = fake_cloudflare({"success": True, "result": {"image": jpeg_b64((512, 512))}})
    CloudflareImages("m", (1024, 576), client).generate("sheet", [], (512, 512), tmp_path / "s.png")
    assert 'name="width"\r\n\r\n512\r\n' in sent[0].content.decode("latin-1")


def test_refusals_stop_instead_of_retrying(tmp_path):
    client, _ = fake_cloudflare({"success": False, "errors": [{"message": "daily limit"}]}, 400)
    images = CloudflareImages("m", (1024, 576), client)
    with pytest.raises(ImageServiceError, match="daily limit"):
        images.generate("a", [], (1920, 1080), tmp_path / "x.png")


def test_a_hanging_request_is_sent_again_then_stops_clearly(tmp_path):
    answers = [httpx.ReadTimeout("hung"), httpx.ReadTimeout("hung"),
               httpx.Response(200, json={"success": True, "result": {"image": jpeg_b64((64, 36))}})]

    def busy(request: httpx.Request) -> httpx.Response:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    images = CloudflareImages("m", (1024, 576), httpx.Client(transport=httpx.MockTransport(busy)))
    images.generate("a", [], (64, 36), tmp_path / "x.png")
    assert not answers  # two hangs, then the third try answered

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("hung")

    images = CloudflareImages("m", (1024, 576), httpx.Client(transport=httpx.MockTransport(down)))
    with pytest.raises(ImageServiceError, match="didn't answer"):
        images.generate("a", [], (64, 36), tmp_path / "y.png")


def test_edge_waits_and_tries_again_when_no_audio_comes_back(tmp_path, monkeypatch):
    sent = []

    class FlakyEdge:
        def __init__(self, text, voice, rate, pitch):
            pass

        def save_sync(self, path):
            sent.append(path)
            if len(sent) == 1:
                raise edge_tts.exceptions.NoAudioReceived("No audio was received.")
            Path(path).write_bytes(b"mp3")

    monkeypatch.setattr(edge_tts, "Communicate", FlakyEdge)
    monkeypatch.setattr(ffmpeg, "run", lambda args: None)
    voices, waits = EdgeVoices("-8%", "+0Hz"), []
    voices.sleep = waits.append
    voices.speak("Hello!", "en-US-AndrewNeural", "", tmp_path / "x.wav")
    assert len(sent) == 2 and waits == [EdgeVoices.PAUSE]


def test_server_errors_raise_for_langgraph_to_retry(tmp_path):
    client, _ = fake_cloudflare({"success": False}, 503)
    images = CloudflareImages("m", (1024, 576), client)
    with pytest.raises(httpx.HTTPStatusError):
        images.generate("a", [], (1920, 1080), tmp_path / "x.png")

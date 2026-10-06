"""STT provider switch: the Groq path with a fake client, error mapping, and plain-float output."""
from types import SimpleNamespace

import pytest

from backend.services import llm, stt


class _Result:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return self._payload


def _client(payload=None, error=None, capture=None):
    def create(**kwargs):
        if capture is not None:
            capture.update(kwargs)
        if error:
            raise error
        return _Result(payload)

    return SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))


@pytest.fixture
def audio_file(tmp_path):
    path = tmp_path / "turn.webm"
    path.write_bytes(b"fake-audio-bytes")
    return str(path)


@pytest.fixture
def use_groq(monkeypatch):
    monkeypatch.setattr(stt, "STT_PROVIDER", "groq")


PAYLOAD = {
    "text": " Well, um, I think it was good. ",
    "duration": 4.5,
    "words": [
        {"word": "Well,", "start": 0.0, "end": 0.3},
        {"word": "um,", "start": 0.4, "end": 0.6},
        {"word": "I", "start": 0.9, "end": 1.0},
        {"word": "", "start": 1.0, "end": 1.0},         # empty tokens are dropped
    ],
    "segments": [
        {"avg_logprob": -0.2, "no_speech_prob": 0.01},
        {"avg_logprob": -0.4, "no_speech_prob": 0.02},
    ],
}


def test_provider_selection_and_capabilities(monkeypatch):
    monkeypatch.setattr(stt, "STT_PROVIDER", "local")
    assert stt.provider() == "local" and not stt.supports_fillers() and stt.provides_word_confidence()
    monkeypatch.setattr(stt, "STT_PROVIDER", "groq")
    assert stt.provider() == "groq" and stt.supports_fillers() and not stt.provides_word_confidence()
    monkeypatch.setattr(stt, "STT_PROVIDER", "nonsense")
    assert stt.provider() == "local"        # unknown values fall back safely


def test_groq_result_is_normalised(use_groq, monkeypatch, audio_file):
    captured = {}
    monkeypatch.setattr(llm, "get_client", lambda: _client(PAYLOAD, capture=captured))
    result = stt.transcribe(audio_file)

    assert result["text"] == "Well, um, I think it was good."
    assert result["duration"] == 4.5
    assert [w["word"] for w in result["words"]] == ["Well,", "um,", "I"]
    assert all(w["probability"] is None for w in result["words"])          # the hosted API has none
    assert all(type(w["start"]) is float and type(w["end"]) is float for w in result["words"])
    assert result["avg_logprob"] == pytest.approx(-0.3)
    assert result["latency_ms"] >= 0
    # Sends the audio with its real extension and asks for word timestamps, English, deterministic.
    assert captured["file"][0].endswith(".webm") and captured["file"][1] == b"fake-audio-bytes"
    assert captured["timestamp_granularities"] == ["word", "segment"]
    assert captured["language"] == "en" and captured["temperature"] == 0.0


def test_groq_near_silence_is_treated_as_no_speech(use_groq, monkeypatch, audio_file):
    payload = {"text": " Thank you.", "duration": 2.0, "words": [{"word": "Thank", "start": 0, "end": 0.3}],
               "segments": [{"avg_logprob": -1.5, "no_speech_prob": 0.97}]}
    monkeypatch.setattr(llm, "get_client", lambda: _client(payload))
    result = stt.transcribe(audio_file)
    assert result["text"] == "" and result["words"] == []     # hosted Whisper hallucinated a phrase on silence


class _HTTPError(Exception):
    def __init__(self, status):
        super().__init__(f"http {status}")
        self.status_code = status


def test_groq_400_means_bad_audio(use_groq, monkeypatch, audio_file):
    monkeypatch.setattr(llm, "get_client", lambda: _client(error=_HTTPError(400)))
    with pytest.raises(stt.AudioDecodeError):
        stt.transcribe(audio_file)


@pytest.mark.parametrize("status", [429, 500, 503, None])
def test_groq_outages_are_retryable_not_bad_audio(use_groq, monkeypatch, audio_file, status):
    error = _HTTPError(status) if status else ConnectionError("network down")
    monkeypatch.setattr(llm, "get_client", lambda: _client(error=error))
    with pytest.raises(stt.STTUnavailableError) as info:
        stt.transcribe(audio_file)
    assert "unavailable" in str(info.value)       # a friendly message, not the provider's raw error


def test_groq_empty_file_is_bad_audio(use_groq, monkeypatch, tmp_path):
    empty = tmp_path / "empty.webm"
    empty.write_bytes(b"")
    monkeypatch.setattr(llm, "get_client", lambda: pytest.fail("must not call the API for an empty file"))
    with pytest.raises(stt.AudioDecodeError):
        stt.transcribe(str(empty))


def test_local_provider_returns_plain_floats_and_stripped_words(monkeypatch, audio_file):
    """faster-whisper yields numpy floats and ' word' tokens; both used to leak into stored data."""
    import numpy as np

    class Word:
        def __init__(self, w, s, e, p):
            self.word, self.start, self.end, self.probability = w, np.float64(s), np.float64(e), np.float32(p)

    class Segment:
        text = " Hello there"
        avg_logprob = np.float64(-0.25)
        words = [Word(" Hello", 0.0, 0.4, 0.93), Word(" there", 0.5, 0.9, 0.88)]

    class Model:
        def transcribe(self, path, **kw):
            assert kw["word_timestamps"] is True and kw["language"] == "en"
            assert "initial_prompt" not in kw        # the disfluency prompt makes base.en hallucinate "Umm..."
            return iter([Segment()]), SimpleNamespace(duration=np.float64(1.234))

    monkeypatch.setattr(stt, "STT_PROVIDER", "local")
    monkeypatch.setattr(stt, "_get_model", lambda: Model())
    result = stt.transcribe(audio_file)
    assert [w["word"] for w in result["words"]] == ["Hello", "there"]
    for w in result["words"]:
        assert type(w["start"]) is float and type(w["end"]) is float and type(w["probability"]) is float
    assert type(result["duration"]) is float and type(result["avg_logprob"]) is float
    import json
    json.dumps(result)   # must serialise with the standard library, no numpy types


def test_local_decode_failures_become_audio_errors(monkeypatch, audio_file):
    class Model:
        def transcribe(self, *a, **k):
            raise RuntimeError("av.error.InvalidDataError: End of file")

    monkeypatch.setattr(stt, "STT_PROVIDER", "local")
    monkeypatch.setattr(stt, "_get_model", lambda: Model())
    with pytest.raises(stt.AudioDecodeError) as info:
        stt.transcribe(audio_file)
    assert "End of file" not in str(info.value)


def test_the_real_cause_of_a_local_failure_is_logged_even_though_the_learner_sees_a_friendly_message(monkeypatch, audio_file, caplog):
    """Any model failure is reported as 'could not process that recording'; the log must still say why."""
    class Model:
        def transcribe(self, *a, **k):
            raise MemoryError("std::bad_alloc while decoding")

    monkeypatch.setattr(stt, "STT_PROVIDER", "local")
    monkeypatch.setattr(stt, "_get_model", lambda: Model())
    with caplog.at_level("WARNING", logger="aura.stt"):
        with pytest.raises(stt.AudioDecodeError) as info:
            stt.transcribe(audio_file)
    assert "bad_alloc" not in str(info.value)
    record = next(r for r in caplog.records if r.name == "aura.stt")
    assert "bad_alloc" in record.getMessage() and record.exc_info and record.exc_info[0] is MemoryError


# ── The real audio libraries (everything above uses fakes) ────────────────────

def _tone_wav(path, seconds=1.0, rate=16000):
    import math
    import struct
    import wave

    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(
            struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(int(rate * seconds))
        ))


def _tone_webm_opus(path, seconds=1.0):
    """A recording in the format a browser's MediaRecorder produces (Opus in WebM)."""
    import av
    import numpy as np

    rate, chunk = 48000, 960                                    # Opus wants 20 ms frames
    pcm = (12000 * np.sin(2 * np.pi * 440 * np.arange(int(rate * seconds)) / rate)).astype(np.int16)
    container = av.open(str(path), mode="w", format="webm")
    stream = container.add_stream("libopus", rate=rate)
    stream.layout = "mono"
    for start in range(0, len(pcm), chunk):
        frame = av.AudioFrame.from_ndarray(pcm[start:start + chunk].reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = rate
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode(None):
        container.mux(packet)
    container.close()


@pytest.mark.parametrize("make, name", [(_tone_wav, "turn.wav"), (_tone_webm_opus, "turn.webm")])
def test_the_pinned_audio_libraries_can_really_decode_a_recording(tmp_path, make, name):
    """
    The suite fakes Whisper, so a bad audio-library pin sails through it and then fails EVERY local
    transcription in production ("Could not process that recording"). This is exactly what happened
    with PyAV 19, which removed an argument faster-whisper passes. So decode real recordings, in both the
    formats users send, through the real library, the way faster-whisper does before it listens.
    """
    from faster_whisper.audio import decode_audio

    path = tmp_path / name
    make(path)
    samples = decode_audio(str(path), sampling_rate=16000)
    assert abs(len(samples) - 16000) < 800                      # one second, resampled to 16 kHz
    assert 0.2 < float(abs(samples).max()) < 0.6                # a real tone came out, not silence or noise

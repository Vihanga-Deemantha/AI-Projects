"""
The TTS layer: which model and speaker a companion's sentence is spoken with under each style, when a pair is
reported as unavailable (and why), loading ahead of a session, and, if the voice files are installed, the REAL models
(the rest of the suite fakes Piper, which cannot notice a wrong speaker name or a missing model).
"""
import io
import json
import logging
import wave
from types import SimpleNamespace

import pytest

from backend.personalities import ACCENT_VOICES, STYLES, VOICES
from backend.services import tts

# A speaker id for every VCTK speaker the app uses, as the multi-speaker model would number them.
SPEAKERS = {s: i for i, s in enumerate(sorted({
    spec["speaker"] for by in ACCENT_VOICES.values() for spec in by.values() if spec["speaker"]
}))}


class FakeModel:
    """Stands in for a Piper voice: records what it was asked to say and with which settings."""

    def __init__(self, speakers):
        self.config = SimpleNamespace(speaker_id_map=speakers)
        self.calls = []

    def synthesize_wav(self, text, wav_file, syn_config=None):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x01\x00" * 2000)
        self.calls.append((text, syn_config))


@pytest.fixture
def models(monkeypatch):
    """Replaces model loading with fakes; returns {model file: FakeModel} for the models that got loaded."""
    loaded = {}

    def fake_load(filename, label):
        loaded.setdefault(filename, FakeModel(SPEAKERS if "vctk" in filename else {}))
        return loaded[filename]

    monkeypatch.setattr(tts, "_load_model", fake_load)
    return loaded


# ── Choosing the model and the speaker ───────────────────────────────────────

def test_a_companion_speaks_with_their_own_model_under_standard_english(models):
    tts.synthesize("Hello there", "amy")
    assert list(models) == [VOICES["amy"]["file"].split("/")[-1]]
    assert models["en_US-amy-medium.onnx"].calls[0][1] is None             # nothing to configure


def test_another_accent_uses_the_multi_speaker_model_with_the_right_speaker(models):
    tts.synthesize("Hello there", "amy", style="scottish")
    assert list(models) == ["en_GB-vctk-medium.onnx"]
    _, config = models["en_GB-vctk-medium.onnx"].calls[0]
    assert config.speaker_id == SPEAKERS["p262"] and config.length_scale is None


def test_a_voice_of_its_own_needs_no_speaker(models):
    tts.synthesize("Hello there", "eida", style="scottish")                 # Alba is a model of one speaker
    assert list(models) == ["en_GB-alba-medium.onnx"]
    assert models["en_GB-alba-medium.onnx"].calls[0][1] is None


def test_slow_speech_and_the_speaker_combine(models):
    tts.synthesize("library", "amy", 1.7, "irish")
    _, config = models["en_GB-vctk-medium.onnx"].calls[0]
    assert config.speaker_id == SPEAKERS["p340"] and config.length_scale == 1.7


def test_one_loaded_model_serves_several_companions(models):
    tts.synthesize("a", "amy", style="scottish")
    tts.synthesize("b", "maya", style="scottish")
    tts.synthesize("c", "ryan", style="canadian")
    assert list(models) == ["en_GB-vctk-medium.onnx"]
    assert [c[1].speaker_id for c in models["en_GB-vctk-medium.onnx"].calls] == [SPEAKERS["p262"], SPEAKERS["p234"], SPEAKERS["p302"]]


def test_the_wav_comes_back_complete(models):
    wav = tts.synthesize_text("Hello there", "amy", "scottish")
    with wave.open(io.BytesIO(wav)) as w:
        assert w.getframerate() == 22050 and w.getnframes() == 2000


def test_asking_for_a_voice_that_does_not_exist_is_an_error_not_a_guess(models):
    with pytest.raises(ValueError, match="no voice for the 'australian' style"):
        tts.synthesize("Hello", "eida", style="australian")
    assert models == {}                                                     # nothing was loaded or spoken


def test_a_model_that_lacks_the_speaker_is_an_error(models, monkeypatch):
    monkeypatch.setattr(tts, "_load_model", lambda filename, label: FakeModel({}))
    with pytest.raises(ValueError, match="has no speaker 'p262'"):
        tts.synthesize("Hello", "amy", style="scottish")


def test_words_are_cached_per_accent(models):
    tts.word_audio.cache_clear()
    tts.word_audio("library", "amy", False, "scottish")
    tts.word_audio("library", "amy", False, "scottish")
    tts.word_audio("library", "amy", False, "irish")
    assert len(models["en_GB-vctk-medium.onnx"].calls) == 2
    assert [c[1].speaker_id for c in models["en_GB-vctk-medium.onnx"].calls] == [SPEAKERS["p262"], SPEAKERS["p340"]]


# ── When a pair is unavailable, and why (a real, temporary voices folder) ────

@pytest.fixture
def voices_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tts, "VOICES_DIR", str(tmp_path))
    tts._speaker_names.cache_clear()

    def install(filename, speakers=()):
        (tmp_path / filename).write_bytes(b"model")
        (tmp_path / (filename + ".json")).write_text(json.dumps({"speaker_id_map": {s: i for i, s in enumerate(speakers)}}))

    for filename in tts.VOICE_FILES.values():
        install(filename)
    yield SimpleNamespace(path=tmp_path, install=install)
    tts._speaker_names.cache_clear()


def test_a_pair_with_everything_installed_has_no_problem(voices_dir):
    voices_dir.install("en_GB-vctk-medium.onnx", sorted(SPEAKERS))
    voices_dir.install("en_GB-alba-medium.onnx")
    assert all(tts.style_problem(c, s) is None for s in STYLES for c in VOICES if s != "australian" or c in ("ryan", "alan"))
    assert tts.style_available("amy", "scottish")


def test_a_missing_regional_model_is_reported_not_papered_over(voices_dir):
    assert tts.style_problem("amy", "scottish") == "The voice Amy uses for Scottish English isn't installed on this server."
    assert tts.style_problem("amy", "standard") is None                     # her own voice is there
    assert tts.missing_regional_models() == ["en_GB-vctk-medium.onnx", "en_GB-alba-medium.onnx"]


def test_a_model_without_the_speaker_counts_as_not_installed(voices_dir):
    voices_dir.install("en_GB-vctk-medium.onnx", ["p999"])                  # a model, but not the one we expect
    assert "isn't installed" in tts.style_problem("amy", "scottish")


def test_no_voice_for_the_accent_says_so_and_suggests_a_way_out(voices_dir):
    assert tts.style_problem("eida", "australian") == "Eida doesn't have a voice for Australian English yet. Pick another companion or speaking style."


def test_unknown_companions_and_styles_are_named(voices_dir):
    assert tts.style_problem("nobody", "standard") == "Unknown companion: nobody"
    assert tts.style_problem("amy", "klingon") == "Unknown speaking style: klingon"


def test_the_health_status_counts_regional_models_separately(voices_dir):
    voices_dir.install("en_GB-alba-medium.onnx")
    status = tts.status()
    assert status["installed"] == status["total"] == 6 and status["regional"] == {"installed": 1, "total": 2}


# ── Loading ahead of a session ───────────────────────────────────────────────

def test_a_session_loads_the_model_it_will_speak_with(voices_dir, models):
    voices_dir.install("en_GB-vctk-medium.onnx", sorted(SPEAKERS))
    tts.preload("amy", "scottish")
    assert list(models) == ["en_GB-vctk-medium.onnx"]


def test_preloading_a_voice_that_is_not_there_does_nothing(voices_dir, models):
    tts.preload("amy", "scottish")                                          # no regional model installed
    tts.preload("eida", "australian")                                       # no such voice at all
    assert models == {}


def test_preloading_never_raises(voices_dir, monkeypatch, caplog):
    voices_dir.install("en_GB-vctk-medium.onnx", sorted(SPEAKERS))

    def boom(filename, label):
        raise RuntimeError("out of memory")

    monkeypatch.setattr(tts, "_load_model", boom)
    with caplog.at_level(logging.ERROR, logger="aura.tts"):
        tts.preload("amy", "scottish")
    assert "Preloading the voice" in caplog.text


def test_startup_warns_about_missing_regional_models(voices_dir, models, caplog):
    with caplog.at_level(logging.WARNING, logger="aura.tts"):
        tts.prewarm()
    assert "Regional accent voices are missing" in caplog.text and "vctk" in caplog.text
    assert sorted(models) == sorted(tts.VOICE_FILES.values())                # the companions' own voices only


# ── The real models (skipped where the voice files aren't installed) ─────────

_models_missing = pytest.mark.skipif(
    not all(tts._model_installed(f) for f in tts.ALL_MODEL_FILES),
    reason="the voice models aren't installed here (python scripts/download_voices.py)",
)


def real(test):
    """A test of the genuine models: the suite's stand-in voices folder steps aside (see conftest), and it is skipped where they aren't installed."""
    return pytest.mark.real_voices(_models_missing(test))


@real
def test_every_speaker_in_the_table_exists_in_the_real_model():
    names = tts._speaker_names("en_GB-vctk-medium.onnx")
    assert len(names) == 109
    for by_companion in ACCENT_VOICES.values():
        for companion, spec in by_companion.items():
            if spec["speaker"] is not None:
                assert spec["speaker"] in names, f"{companion}: {spec['speaker']} is not in the VCTK model"


@real
@pytest.mark.parametrize("companion, style", [("amy", "standard"), ("amy", "scottish"), ("eida", "scottish"), ("ryan", "australian"), ("alan", "american")])
def test_real_models_really_speak(companion, style):
    wav = tts.synthesize(f"Hello, this is a test of {style} English.", companion, style=style)["audio_bytes"]
    with wave.open(io.BytesIO(wav)) as w:
        frames = w.readframes(w.getnframes())
        assert w.getnframes() > w.getframerate()                            # more than a second of audio
    assert max(abs(int.from_bytes(frames[i:i + 2], "little", signed=True)) for i in range(0, len(frames), 200)) > 2000

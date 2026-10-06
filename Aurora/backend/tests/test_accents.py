"""
A speaking style is the coach's WORDS and the ACCENT you hear. Which voice each companion uses for each style,
that the table only claims what is true, and what the API offers, refuses and says.
"""
import importlib.util
from pathlib import Path

import pytest

from backend.models.core import User
from backend.personalities import ACCENT_LABELS, ACCENT_VOICES, STYLES, VOICES, accent_of, model_files, voice_for
from backend.services import tts

ROOT = Path(__file__).resolve().parents[2]
COMPANIONS = list(VOICES)
PROFILE = "/api/auth/profile"

# What the VCTK corpus's own speaker table (speaker-info.txt from the University of Edinburgh's CSTR) says
# about every VCTK speaker the app uses: (accent, gender). Adding a speaker to ACCENT_VOICES means checking
# him or her there first and adding the facts here: that is what makes the claim "this is a Canadian voice" true.
VCTK_FACTS = {
    "p225": ("English", "F"), "p226": ("English", "M"), "p229": ("English", "F"), "p234": ("Scottish", "F"),
    "p245": ("Irish", "M"), "p246": ("Scottish", "M"), "p254": ("English", "M"), "p262": ("Scottish", "F"),
    "p268": ("English", "F"), "p272": ("Scottish", "M"), "p281": ("Scottish", "M"), "p283": ("Irish", "F"),
    "p295": ("Irish", "F"), "p298": ("Irish", "M"), "p302": ("Canadian", "M"), "p303": ("Canadian", "F"),
    "p311": ("American", "M"), "p312": ("Canadian", "F"), "p316": ("Canadian", "M"), "p326": ("Australian", "M"),
    "p340": ("Irish", "F"), "p343": ("Canadian", "F"), "p363": ("Canadian", "M"), "p364": ("Irish", "M"),
    "p374": ("Australian", "M"),
}
VCTK_ACCENT = {"american": "American", "british": "English", "scottish": "Scottish", "irish": "Irish",
               "canadian": "Canadian", "australian": "Australian"}

# Who can speak what, written out so a change to the voice table is a deliberate change here too.
CAN_SPEAK = {
    "standard": set(COMPANIONS), "american": set(COMPANIONS), "british": set(COMPANIONS),
    "scottish": set(COMPANIONS), "irish": set(COMPANIONS), "canadian": set(COMPANIONS),
    "australian": {"ryan", "alan"},      # only two Australian speakers exist in the data, both male
}


def spoken_by(style):
    return {c for c in COMPANIONS if voice_for(c, style) is not None}


# ── Which voice a companion uses ──────────────────────────────────────────────

def test_standard_english_uses_everyones_own_voice():
    for companion in COMPANIONS:
        spec = voice_for(companion, "standard")
        assert spec["file"] == VOICES[companion]["file"] and spec["speaker"] is None


def test_a_style_with_the_companions_own_accent_keeps_their_own_voice():
    for companion, voice in VOICES.items():
        spec = voice_for(companion, voice["accent"])
        assert spec["file"] == voice["file"] and spec["speaker"] is None, companion


def test_any_other_accent_uses_a_voice_of_that_accent():
    amy = voice_for("amy", "scottish")
    assert amy["file"].endswith("en_GB-vctk-medium.onnx") and amy["speaker"] == ACCENT_VOICES["scottish"]["amy"]["speaker"]
    eida = voice_for("eida", "scottish")                       # Alba is a Scottish voice of her own: no speaker to pick
    assert eida["file"].endswith("en_GB-alba-medium.onnx") and eida["speaker"] is None
    alan = voice_for("alan", "american")                       # the British companion can speak American too
    assert alan["file"] != VOICES["alan"]["file"] and alan["speaker"] == "p311"


def test_which_companions_can_speak_which_styles():
    assert set(CAN_SPEAK) == set(STYLES)
    for style, who in CAN_SPEAK.items():
        assert spoken_by(style) == who, style


def test_where_no_voice_exists_none_is_offered_rather_than_a_fake():
    for companion in ("eida", "maya", "amy", "lessac"):
        assert voice_for(companion, "australian") is None


def test_an_unknown_style_means_no_particular_accent():
    assert accent_of("not-a-style") is None
    assert voice_for("amy", "not-a-style")["file"] == VOICES["amy"]["file"]


# ── The table only says what is true ─────────────────────────────────────────

def test_every_accent_voice_matches_its_companions_gender():
    for accent, by_companion in ACCENT_VOICES.items():
        for companion, spec in by_companion.items():
            assert spec["gender"] == VOICES[companion]["gender"], (accent, companion)


def test_every_vctk_speaker_really_is_a_speaker_of_the_accent_and_gender_the_table_says():
    seen = set()
    for accent, by_companion in ACCENT_VOICES.items():
        for companion, spec in by_companion.items():
            speaker = spec["speaker"]
            if speaker is None:
                continue
            assert speaker in VCTK_FACTS, f"{speaker}: check VCTK's speaker-info.txt, then add the facts to VCTK_FACTS"
            vctk_accent, vctk_gender = VCTK_FACTS[speaker]
            assert vctk_accent == VCTK_ACCENT[accent], (accent, companion, speaker, vctk_accent)
            assert vctk_gender == spec["gender"][0].upper(), (companion, speaker)
            seen.add(speaker)
    assert seen == set(VCTK_FACTS), "VCTK_FACTS lists speakers the app no longer uses"


def test_no_two_companions_share_a_voice_under_the_same_style():
    for style in STYLES:
        used = [(s["file"], s["speaker"]) for c in COMPANIONS if (s := voice_for(c, style))]
        assert len(used) == len(set(used)), style


def test_the_tables_only_name_known_accents_styles_and_companions():
    assert STYLES["standard"]["accent"] is None
    for style in STYLES.values():
        assert style["accent"] is None or style["accent"] in ACCENT_LABELS
    for voice in VOICES.values():
        assert voice["accent"] in ACCENT_LABELS
    assert set(ACCENT_VOICES) <= set(ACCENT_LABELS)
    for accent, by_companion in ACCENT_VOICES.items():
        assert set(by_companion) <= set(COMPANIONS)
        assert all(VOICES[c]["accent"] != accent for c in by_companion), "a companion's own accent uses their own voice"
    assert accent_of("scottish") == "scottish" and accent_of("standard") is None


def test_every_model_the_app_can_use_can_be_downloaded():
    spec = importlib.util.spec_from_file_location("download_voices", ROOT / "scripts" / "download_voices.py")
    downloader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(downloader)

    files = [Path(f).name for f in model_files()]
    assert len(files) == len(set(files)) and {"en_GB-vctk-medium.onnx", "en_GB-alba-medium.onnx"} <= set(files)
    table = downloader.wanted(None)
    assert set(table.values()) == set(files) and {"vctk", "alba"} <= set(table)     # regional models go by the voice's name
    for filename in files:
        model_url, config_url = downloader.urls_for(filename)                        # raises for a non-Piper file name
        assert model_url.endswith(filename) and config_url.endswith(filename + ".json")


# ── What the API offers, refuses and says ────────────────────────────────────

def options(client):
    return client.get("/api/config/options").json()


def test_options_say_which_styles_each_companion_can_speak(client, ai):
    data = options(client)
    by_id = {v["id"]: v for v in data["voices"]}
    assert by_id["amy"]["accent"] == "American" and by_id["alan"]["accent"] == "British"
    assert "australian" in by_id["ryan"]["styles"] and "australian" not in by_id["eida"]["styles"]
    assert set(by_id["amy"]["styles"]) == set(STYLES) - {"australian"}
    assert set(by_id["alan"]["styles"]) == set(STYLES)
    styles = {s["id"]: s for s in data["styles"]}
    assert styles["scottish"]["accent"] == "Scottish" and styles["standard"]["accent"] is None


def test_a_style_nobody_can_speak_is_not_offered(client, ai, monkeypatch):
    monkeypatch.setattr(tts, "_model_installed", lambda filename: "vctk" not in filename and "alba" not in filename)
    data = options(client)
    assert {s["id"] for s in data["styles"]} == {"standard", "american", "british"}
    by_id = {v["id"]: v for v in data["voices"]}
    assert by_id["amy"]["styles"] == ["standard", "american"]          # her own voice is American; British needs a regional model
    assert by_id["alan"]["styles"] == ["standard", "british"]


def test_a_companion_without_a_voice_for_the_style_cannot_start_that_session(client, user, ai):
    r = client.post("/api/conversation/start", headers=user["headers"], data={"voice": "eida", "style": "australian"})
    assert r.status_code == 400 and "Eida doesn't have a voice for Australian English" in r.json()["detail"]


def test_a_companion_with_a_voice_for_the_style_can_start_it(client, user, ai):
    r = client.post("/api/conversation/start", headers=user["headers"], data={"voice": "ryan", "style": "australian"})
    assert r.status_code == 200 and r.json()["style"] == "australian"


def test_a_style_whose_model_is_not_installed_is_refused_with_that_reason(client, user, ai, monkeypatch):
    monkeypatch.setattr(tts, "_model_installed", lambda filename: "vctk" not in filename)
    r = client.post("/api/conversation/start", headers=user["headers"], data={"voice": "amy", "style": "irish"})
    assert r.status_code == 400 and "isn't installed" in r.json()["detail"]


def test_the_voice_for_a_session_is_loaded_ahead_of_its_first_reply(client, user, ai, monkeypatch):
    calls = []
    monkeypatch.setattr(tts, "preload", lambda voice, style="standard": calls.append((voice, style)))
    client.post("/api/conversation/start", headers=user["headers"], data={"voice": "amy", "style": "scottish"})
    assert calls == [("amy", "scottish")]


def test_replies_are_spoken_in_the_sessions_accent(user, start_session, ai, post_turn):
    post_turn(user["headers"], start_session(user["headers"], voice="amy", style="irish"))
    assert ai.tts_styles and set(ai.tts_styles) == {"irish"}
    assert {voice for _, voice in ai.tts_calls} == {"amy"}             # still Amy: the accent changes, not the companion


def test_a_default_session_is_spoken_in_standard_english(user, start_session, ai, post_turn):
    post_turn(user["headers"], start_session(user["headers"]))
    assert set(ai.tts_styles) == {"standard"}


# ── Hearing a word ────────────────────────────────────────────────────────────

def hear(client, headers, **body):
    return client.post("/api/speech/word", headers=headers, json={"word": "library", **body})


def test_a_word_is_said_in_the_sessions_accent(client, user, ai):
    r = hear(client, user["headers"], voice="amy", style="scottish")
    assert r.status_code == 200 and ai.tts_styles == ["scottish"]


def test_a_word_falls_back_to_the_companions_own_voice_when_they_have_none_for_the_style(client, user, ai):
    r = hear(client, user["headers"], voice="eida", style="australian")
    assert r.status_code == 200 and ai.tts_styles == ["standard"]


def test_a_word_uses_the_saved_style_when_none_is_given(client, user, ai):
    assert client.patch(PROFILE, headers=user["headers"], json={"preferred_style": "canadian"}).status_code == 200
    assert hear(client, user["headers"]).status_code == 200 and ai.tts_styles == ["canadian"]


def test_a_word_in_an_unknown_style_is_refused(client, user, ai):
    r = hear(client, user["headers"], style="klingon")
    assert r.status_code == 400 and "Unknown speaking style" in r.json()["detail"]


def test_the_same_word_in_two_accents_is_two_different_clips(client, user, ai):
    hear(client, user["headers"], voice="amy", style="scottish")
    hear(client, user["headers"], voice="amy", style="irish")
    hear(client, user["headers"], voice="amy", style="irish")           # cached
    assert ai.tts_styles == ["scottish", "irish"]


# ── Saving a companion and style that go together ────────────────────────────

def test_a_saved_companion_and_style_must_be_a_pair_that_works(client, user, ai):
    h = user["headers"]
    assert client.patch(PROFILE, headers=h, json={"preferred_voice": "ryan", "preferred_style": "australian"}).status_code == 200
    r = client.patch(PROFILE, headers=h, json={"preferred_voice": "eida"})      # Eida can't speak the saved Australian style
    assert r.status_code == 400 and "Eida" in r.json()["detail"]
    me = client.get("/api/auth/me", headers=h).json()
    assert (me["preferred_voice"], me["preferred_style"]) == ("ryan", "australian")        # nothing was changed


def test_choosing_a_style_the_saved_companion_cannot_speak_is_refused(client, user, ai):
    h = user["headers"]
    client.patch(PROFILE, headers=h, json={"preferred_voice": "eida"})
    r = client.patch(PROFILE, headers=h, json={"preferred_style": "australian"})
    assert r.status_code == 400 and "doesn't have a voice for Australian English" in r.json()["detail"]


def test_both_can_be_changed_in_one_request_when_the_pair_works(client, user, ai):
    r = client.patch(PROFILE, headers=user["headers"], json={"preferred_voice": "alan", "preferred_style": "australian"})
    assert r.status_code == 200 and (r.json()["preferred_voice"], r.json()["preferred_style"]) == ("alan", "australian")


def test_an_older_saved_pair_that_no_longer_works_does_not_block_other_edits(client, user, ai, db):
    db.query(User).filter_by(id=user["user"]["id"]).update({"preferred_voice": "eida", "preferred_style": "australian"})
    db.commit()
    r = client.patch(PROFILE, headers=user["headers"], json={"display_name": "New name"})
    assert r.status_code == 200 and r.json()["display_name"] == "New name"

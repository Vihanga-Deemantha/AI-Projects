"""Speech history: list, pagination, detail, isolation."""
from datetime import datetime, timedelta, timezone

from backend.database import SessionLocal
from backend.models.core import Conversation, Correction, Message


def _make_session(user_id: str, turns: int = 2, corrections_on_first: int = 1, ended: bool = True, minutes_ago: int = 0) -> str:
    """Builds a finished session straight in the DB."""
    started = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago, seconds=90)
    with SessionLocal() as s:
        c = Conversation(user_id=user_id, scenario="travel", style="british", voice="alan",
                         started_at=started, ended_at=(started + timedelta(seconds=90)) if ended else None, is_complete=ended)
        s.add(c)
        s.flush()
        first_user_id = None
        for i in range(turns):
            u = Message(conversation_id=c.id, role="user", content=f"user turn {i}", created_at=started + timedelta(seconds=10 * (2 * i)))
            a = Message(conversation_id=c.id, role="assistant", content=f"reply {i}", created_at=started + timedelta(seconds=10 * (2 * i + 1)))
            s.add_all([u, a])
            s.flush()
            if i == 0:
                first_user_id = u.id
        for j in range(corrections_on_first):
            s.add(Correction(message_id=first_user_id, user_id=user_id, conversation_id=c.id, category="grammar",
                             subtype="article", original=f"bad {j}", correction=f"good {j}", explanation="because",
                             created_at=started + timedelta(seconds=5 + j)))
        s.commit()
        return c.id


def test_history_requires_auth(client):
    assert client.get("/api/history/sessions").status_code == 401
    assert client.get("/api/history/sessions/abc").status_code == 401


def test_history_list_counts_and_duration(client, user):
    cid = _make_session(user["user"]["id"], turns=3, corrections_on_first=2)
    body = client.get("/api/history/sessions", headers=user["headers"]).json()
    assert body["total"] == 1
    s = body["sessions"][0]
    assert s["id"] == cid
    assert s["turn_count"] == 3                       # user turns only, not assistant replies
    assert s["correction_count"] == 2
    assert s["duration_seconds"] == 90.0 and s["is_complete"] is True
    assert (s["scenario"], s["style"], s["voice"]) == ("travel", "british", "alan")


def test_unfinished_sessions_have_no_duration(client, user):
    _make_session(user["user"]["id"], ended=False)
    s = client.get("/api/history/sessions", headers=user["headers"]).json()["sessions"][0]
    assert s["duration_seconds"] is None and s["is_complete"] is False


def test_history_is_newest_first_and_paginates(client, user):
    ids = [_make_session(user["user"]["id"], minutes_ago=m) for m in (30, 20, 10)]   # oldest created first
    page1 = client.get("/api/history/sessions?limit=2", headers=user["headers"]).json()
    assert page1["total"] == 3 and [s["id"] for s in page1["sessions"]] == [ids[2], ids[1]]
    page2 = client.get("/api/history/sessions?limit=2&offset=2", headers=user["headers"]).json()
    assert [s["id"] for s in page2["sessions"]] == [ids[0]]


def test_history_limit_validation(client, user):
    assert client.get("/api/history/sessions?limit=101", headers=user["headers"]).status_code == 422
    assert client.get("/api/history/sessions?limit=0", headers=user["headers"]).status_code == 422
    assert client.get("/api/history/sessions?offset=-1", headers=user["headers"]).status_code == 422


def test_history_only_shows_your_own_sessions(client, user, make_user):
    other = make_user("other@example.com")
    _make_session(user["user"]["id"])
    assert client.get("/api/history/sessions", headers=other["headers"]).json()["total"] == 0


def test_history_detail_has_ordered_transcript_with_corrections_on_the_right_turn(client, user):
    cid = _make_session(user["user"]["id"], turns=2, corrections_on_first=2)
    d = client.get(f"/api/history/sessions/{cid}", headers=user["headers"]).json()
    assert [m["content"] for m in d["messages"]] == ["user turn 0", "reply 0", "user turn 1", "reply 1"]
    assert [len(m["corrections"]) for m in d["messages"]] == [2, 0, 0, 0]
    assert [c["original"] for c in d["messages"][0]["corrections"]] == ["bad 0", "bad 1"]
    assert d["turn_count"] == 2 and d["correction_count"] == 2


def test_history_detail_404s_for_unknown_and_foreign_sessions(client, user, make_user):
    cid = _make_session(user["user"]["id"])
    other = make_user("other@example.com")
    assert client.get(f"/api/history/sessions/{cid}", headers=other["headers"]).status_code == 404
    assert client.get("/api/history/sessions/does-not-exist", headers=user["headers"]).status_code == 404

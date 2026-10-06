"""
Alembic migrations, exercised on throwaway Postgres databases:
  * a clean `upgrade head` builds a schema identical to the models (no drift);
  * upgrading a database that already holds data preserves and backfills it;
  * downgrade -> upgrade round-trips.

Each runs the real `alembic` CLI in a subprocess, exactly as a deployment would.
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.tests.conftest import TEST_DATABASE_URL, _url

ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_RELEASE = "20e0dbfaef7e"   # last revision before Phase 3d


def _alembic(db_url: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": db_url, "PYTHONPATH": str(ROOT), "PYTHONUTF8": "1"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", *args],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )


@pytest.fixture
def scratch_db():
    name = f"aura_mig_{uuid.uuid4().hex[:8]}_test"
    admin = create_engine(_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(TEST_DATABASE_URL).set(database=name)
    engine = create_engine(url)
    try:
        yield url.render_as_string(hide_password=False), engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def test_upgrade_head_builds_a_schema_identical_to_the_models(scratch_db):
    url, engine = scratch_db
    up = _alembic(url, "upgrade", "head")
    assert up.returncode == 0, up.stderr
    check = _alembic(url, "check")
    assert check.returncode == 0, check.stdout + check.stderr      # any model/migration drift fails here

    from backend.migrations_check import check_schema
    ok, message = check_schema(engine)
    assert ok, message


def test_downgrade_to_base_and_back_up(scratch_db):
    url, _ = scratch_db
    assert _alembic(url, "upgrade", "head").returncode == 0
    down = _alembic(url, "downgrade", "base")
    assert down.returncode == 0, down.stderr
    again = _alembic(url, "upgrade", "head")
    assert again.returncode == 0, again.stderr


def test_a_stale_database_is_reported_as_behind(scratch_db):
    url, engine = scratch_db
    assert _alembic(url, "upgrade", PREVIOUS_RELEASE).returncode == 0
    from backend.migrations_check import check_schema
    ok, message = check_schema(engine)
    assert not ok and "alembic" in message and "upgrade head" in message


def test_an_unmigrated_database_is_reported(scratch_db):
    _, engine = scratch_db
    from backend.migrations_check import check_schema
    ok, message = check_schema(engine)
    assert not ok and "no Alembic version" in message


def test_phase3d_upgrade_preserves_and_backfills_existing_data(scratch_db):
    """Simulates the real dev database: rows written before the Phase 3d columns existed."""
    url, engine = scratch_db
    assert _alembic(url, "upgrade", PREVIOUS_RELEASE).returncode == 0

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO users (id, email, display_name, created_at, password_hash, google_id, reset_otp_attempts, preferred_voice, preferred_style)
            VALUES ('u-pw',  'pw@example.com',  'Pw',  now(), 'hash', NULL,   0, 'amy', 'standard'),
                   ('u-g',   'g@example.com',   'G',   now(), NULL,   'g-1',  0, 'amy', 'standard'),
                   ('u-anon', NULL,             NULL,  now(), NULL,   NULL,   0, 'amy', 'standard')
        """))
        conn.execute(text("""
            INSERT INTO conversations (id, user_id, started_at, scenario, style, voice, is_complete)
            VALUES ('c1', 'u-pw', now(), 'casual', 'standard', 'amy', false)
        """))
        conn.execute(text("""
            INSERT INTO messages (id, conversation_id, created_at, role, content)
            VALUES ('m1', 'c1', now(), 'user', 'hello there my friend')
        """))

    up = _alembic(url, "upgrade", "head")
    assert up.returncode == 0, up.stderr

    with engine.connect() as conn:
        rows = {r[0]: r for r in conn.execute(text("SELECT id, email_verified, token_version, verify_otp_attempts FROM users"))}
        status = conn.execute(text("SELECT analysis_status FROM messages WHERE id = 'm1'")).scalar()
    assert rows["u-pw"][1:] == (False, 0, 0)       # password accounts must still prove their email
    assert rows["u-g"][1] is True                  # Google already vouched for theirs
    assert rows["u-anon"][1] is False
    assert status == "done"                        # pre-existing turns are not "pending" forever

"""
Does a built AURA image actually work? Run this before deploying a new image.

The test suite fakes Whisper, Piper and Groq, so it cannot notice a broken dependency pin or a
missing model file. This starts the real image against a throwaway database and checks, for real:
migrations run from empty, models load, the container is healthy, a recording is transcribed
(Whisper + audio decoding), a voice is synthesised (Piper), and rate limits see real client
addresses behind a proxy. It cleans up after itself and exits 1 if anything fails.

    docker build -t aura-backend .
    python scripts/smoke_container.py                          # from the Aurora/ folder
    python scripts/smoke_container.py --image my/image:tag --stt groq --no-prewarm

Needs: Docker, the project's PostgreSQL running (`docker compose up -d`, container "aura_postgres"),
and `requests`. A dummy Groq key is passed to the container, so nothing here calls the LLM; the
transcript arriving before the (expected) reply error is what proves speech recognition works.
With --stt groq speech recognition is remote, so that check is skipped.
"""
import argparse
import json
import secrets
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "frontend" / "e2e" / "fixtures" / "speech.wav"      # says: "Yesterday I go to the mall..."
POSTGRES = "aura_postgres"
SCRATCH_DB = "aura_smoke_test"

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--image", default="aura-backend", help="image to test (default: aura-backend)")
parser.add_argument("--stt", choices=["local", "groq"], default="local", help="STT_PROVIDER to run the container with")
parser.add_argument("--no-prewarm", action="store_true", help="run with PREWARM_MODELS=false (models load on first use, so far less memory)")
parser.add_argument("--port", type=int, default=8002, help="host port to publish the container on")
parser.add_argument("--startup-timeout", type=int, default=240, help="seconds to wait for the models to load")
parser.add_argument("--keep", action="store_true", help="leave the container and database behind (for debugging)")
args = parser.parse_args()

NAME = "aura-smoke"
BASE = f"http://127.0.0.1:{args.port}"
failures: list[str] = []


def docker(*cmd: str, check: bool = True) -> str:
    out = subprocess.run(["docker", *cmd], capture_output=True, text=True)
    if check and out.returncode != 0:
        sys.exit(f"docker {' '.join(cmd)} failed:\n{out.stdout}\n{out.stderr}")
    return (out.stdout + out.stderr).strip()


def docker_succeeds(*cmd: str) -> bool:
    return subprocess.run(["docker", *cmd], capture_output=True).returncode == 0


def psql(sql: str, database: str = "postgres") -> str:
    return docker("exec", POSTGRES, "psql", "-U", "aura", "-d", database, "-Atc", sql)


def check(label: str, passed: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if passed else 'FAIL'}  {label}" + (f"   ({detail})" if detail else ""))
    if not passed:
        failures.append(label)
    return passed


def skip(label: str, why: str) -> None:
    print(f"  SKIP  {label}   ({why})")


def health(timeout: int = 30) -> requests.Response:
    """/health, tolerating the stalls while the server is busy loading its models."""
    for _ in range(30):
        try:
            return requests.get(f"{BASE}/health", timeout=timeout)
        except requests.RequestException:
            time.sleep(2)
    raise SystemExit("/health never answered")


def cleanup() -> None:
    if args.keep:
        print(f"\nLeft running: container '{NAME}' on port {args.port}, database '{SCRATCH_DB}'.")
        return
    docker("rm", "-f", NAME, check=False)
    psql(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')


if not AUDIO.exists():
    sys.exit(f"Missing the test recording: {AUDIO}")
if docker("inspect", "--format", "{{.State.Running}}", POSTGRES, check=False) != "true":
    sys.exit(f"PostgreSQL isn't running: start it with `docker compose up -d` (container '{POSTGRES}').")
if not docker_succeeds("image", "inspect", args.image):
    sys.exit(f"Image '{args.image}' not found. Build it first: docker build -t {args.image} .")

print(f"Testing image '{args.image}' (STT_PROVIDER={args.stt})\n")
docker("rm", "-f", NAME, check=False)
psql(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')
psql(f'CREATE DATABASE "{SCRATCH_DB}"')
try:
    docker(
        "run", "-d", "--name", NAME, "-p", f"{args.port}:8000",
        "--add-host", "host.docker.internal:host-gateway",
        "-e", "GROQ_API_KEY=dummy-key-not-real",
        "-e", f"DATABASE_URL=postgresql://aura:aura_dev_pass@host.docker.internal:5432/{SCRATCH_DB}",
        "-e", f"JWT_SECRET={secrets.token_urlsafe(32)}",
        "-e", f"STT_PROVIDER={args.stt}",
        "-e", f"PREWARM_MODELS={'false' if args.no_prewarm else 'true'}",
        args.image,
    )

    print("Start-up")
    started = time.time()
    body: dict = {}
    for _ in range(args.startup_timeout):
        response = health()
        body = response.json()
        speech = body.get("speech", {})
        voices = speech.get("voices", {})
        if args.no_prewarm:
            models_ready = response.status_code == 200
        else:
            models_ready = voices.get("loaded") == voices.get("total") and speech.get("stt", {}).get("ready")
        if models_ready:
            break
        time.sleep(1)
    seconds = round(time.time() - started)
    if args.no_prewarm:
        check("the server answers without loading any model", bool(models_ready) and voices.get("loaded") == 0, f"{seconds}s")
    else:
        check("the models finished loading", bool(models_ready), f"{seconds}s")
    print(f"  INFO  memory after start-up: {docker('stats', '--no-stream', '--format', '{{.MemUsage}}', NAME)}")
    response = health()
    body = response.json()
    check("/health says ok", response.status_code == 200 and body["status"] == "ok", f"HTTP {response.status_code}")
    check("migrations ran from an empty database", body["migrations"] == "up to date")
    check("all six voices are installed", body["speech"]["voices"]["installed"] == 6 and not body["speech"]["voices"]["missing"])
    check("both accent voices are installed", body["speech"]["voices"].get("regional") == {"installed": 2, "total": 2}, str(body["speech"]["voices"].get("regional")))
    check("runs as a non-root user", docker("exec", NAME, "id", "-u") != "0")
    check("starts in production mode", docker("exec", NAME, "sh", "-c", "echo $ENVIRONMENT") == "production")

    print("\nWorks for a learner")
    signup = requests.post(f"{BASE}/api/auth/signup", json={"email": f"smoke_{int(time.time())}@example.com", "password": "smoke-test-pass-1"}, timeout=60)
    ok = check("sign up", signup.status_code == 201, f"HTTP {signup.status_code}")
    if not ok:
        raise SystemExit("cannot continue without an account")
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    word = requests.post(f"{BASE}/api/speech/word", headers=headers, json={"word": "comfortable", "voice": "amy"}, timeout=120)
    check("Piper speaks a word", word.status_code == 200 and word.content[:4] == b"RIFF", f"HTTP {word.status_code}, {len(word.content)} bytes")

    # The accents: a speaker picked out of the multi-speaker model, a single-speaker accent model, and a male-only accent.
    for voice, style in (("amy", "scottish"), ("eida", "scottish"), ("ryan", "australian")):
        accented = requests.post(f"{BASE}/api/speech/word", headers=headers, json={"word": "comfortable", "voice": voice, "style": style}, timeout=180)
        check(f"{voice} speaks {style} English", accented.status_code == 200 and accented.content[:4] == b"RIFF", f"HTTP {accented.status_code}, {len(accented.content)} bytes")
    refused = requests.post(f"{BASE}/api/conversation/start", headers=headers, data={"voice": "eida", "style": "australian"}, timeout=30)
    check("a companion with no voice for the accent can't start that session", refused.status_code == 400, f"HTTP {refused.status_code}: {refused.json().get('detail', '')[:80]}")

    conversation = requests.post(f"{BASE}/api/conversation/start", headers=headers, data={}, timeout=30).json()["conversation_id"]
    with open(AUDIO, "rb") as f:
        turn = requests.post(
            f"{BASE}/api/conversation/message-stream", headers=headers, data={"conversation_id": conversation},
            files={"audio_file": ("speech.wav", f, "audio/wav")}, timeout=300,
        )
    events = [json.loads(line) for line in turn.text.splitlines() if line.strip()]
    transcript = next((e["text"] for e in events if e["type"] == "transcript"), "")
    if args.stt == "local":
        check("Whisper transcribes a recording", "mall" in transcript.lower(), repr(transcript[:60]))
    else:
        skip("Whisper transcribes a recording", "STT_PROVIDER=groq sends audio to Groq, and this run uses a dummy key")
    check("the stream always ends with done", bool(events) and events[-1]["type"] == "done")

    print("\nBehind a proxy")
    statuses = {}
    for ip in ("203.0.113.1", "203.0.113.2"):
        statuses[ip] = [
            requests.post(f"{BASE}/api/auth/login", json={"email": "nobody@example.com", "password": "wrong-password-1"},
                          headers={"X-Forwarded-For": ip}, timeout=30).status_code
            for _ in range(6)
        ]
    check(
        "each client address gets its own rate-limit bucket",
        all(codes[:5] == [401] * 5 and codes[5] == 429 for codes in statuses.values()), str(statuses),
    )

    print("\nDocker")
    health_status = "?"
    for _ in range(40):
        health_status = docker("inspect", "--format", "{{.State.Health.Status}}", NAME)
        if health_status == "healthy":
            break
        time.sleep(3)
    check("the image's own HEALTHCHECK passes", health_status == "healthy", health_status)
    print(f"  INFO  memory after a word and a turn: {docker('stats', '--no-stream', '--format', '{{.MemUsage}}', NAME)}")
finally:
    cleanup()

print()
if failures:
    print(f"[X]  {len(failures)} check(s) failed:")
    for label in failures:
        print(f"     - {label}")
    sys.exit(1)
print("[OK]  The image works.")

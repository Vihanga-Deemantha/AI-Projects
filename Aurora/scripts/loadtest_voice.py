"""
Measure the latency of AURA's voice loop on the machine you actually deploy to.

How fast a turn feels depends overwhelmingly on the hardware (speech-to-text and
text-to-speech are CPU-bound) and on network distance to Groq, so numbers from a
laptop say little about a small cloud instance. Run this against the deployed
backend before choosing STT_PROVIDER, instance size or model sizes.

It signs up throwaway users (test accounts stay in the database — use a staging
database, or delete them afterwards), speaks a WAV file at the server, and reports
the server's own timings. "first_audio" is the number users feel: the time from
sending the recording until the first spoken chunk arrives.

Usage (from the Aurora/ folder, backend running):
    python scripts/loadtest_voice.py
    python scripts/loadtest_voice.py --base-url https://api.example.com --users 1 3 5 --turns 2
    python scripts/loadtest_voice.py --audio my_sentence.wav

Needs only `requests`. The default clip is frontend/e2e/fixtures/speech.wav.
"""
import argparse
import json
import statistics
import sys
import threading
import time
import uuid
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIO = ROOT / "frontend" / "e2e" / "fixtures" / "speech.wav"
PASSWORD = "loadtest-password-1"


def new_user(base: str) -> dict:
    email = f"loadtest_{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(f"{base}/api/auth/signup", json={"email": email, "password": PASSWORD}, timeout=30)
    if r.status_code == 429:
        sys.exit("Signup was rate limited (10/hour per IP). Run the backend with RATE_LIMITS_ENABLED=false for load tests.")
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def one_turn(base: str, headers: dict, audio: bytes) -> dict:
    cid = requests.post(f"{base}/api/conversation/start", headers=headers, data={}, timeout=30).json()["conversation_id"]
    resp = requests.post(
        f"{base}/api/conversation/message-stream", headers=headers, data={"conversation_id": cid},
        files={"audio_file": ("turn.wav", audio, "audio/wav")}, stream=True, timeout=180,
    )
    if resp.status_code != 200:
        return {"error": f"HTTP {resp.status_code}: {resp.text[:120]}"}
    for line in resp.iter_lines():
        if not line:
            continue
        event = json.loads(line)
        if event["type"] == "error":
            return {"error": event["message"]}
        if event["type"] == "done":
            t = event["timings"]
            return {"stt": t.get("stt_ms"), "llm_first_sentence": t.get("llm_ttfs_ms"),
                    "first_audio": t.get("first_audio_ms"), "total": t.get("total_ms")}
    return {"error": "stream ended without a done event"}


def summarize(label: str, results: list[dict]) -> None:
    ok = [r for r in results if "error" not in r]
    errors = [r["error"] for r in results if "error" in r]
    print(f"\n{label}: {len(ok)} ok, {len(errors)} failed")
    for message in sorted(set(errors)):
        print(f"   ! {message}")
    for key in ("stt", "llm_first_sentence", "first_audio", "total"):
        values = [r[key] for r in ok if r.get(key) is not None]
        if values:
            print(f"   {key:20s} median {statistics.median(values):6.0f} ms   worst {max(values):6.0f} ms")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--audio", default=str(DEFAULT_AUDIO), help="a WAV/webm clip of someone speaking")
    parser.add_argument("--users", type=int, nargs="+", default=[1, 3], help="concurrency levels to test")
    parser.add_argument("--turns", type=int, default=2, help="turns per user at each level")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    audio = Path(args.audio).read_bytes()
    print(f"Target {base}  |  clip {Path(args.audio).name} ({len(audio) / 1024:.0f} KB)")

    warm = new_user(base)
    one_turn(base, warm, audio)  # first turn pays any lazy model loading — don't count it
    print("(warm-up turn done)")

    for n in args.users:
        users = [new_user(base) for _ in range(n)]
        results: list[dict] = []
        lock = threading.Lock()

        def run(headers: dict) -> None:
            for _ in range(args.turns):
                result = one_turn(base, headers, audio)
                with lock:
                    results.append(result)

        started = time.time()
        threads = [threading.Thread(target=run, args=(u,)) for u in users]
        [t.start() for t in threads]
        [t.join() for t in threads]
        summarize(f"{n} simultaneous user(s), {args.turns} turn(s) each  [{time.time() - started:.0f}s wall]", results)


if __name__ == "__main__":
    main()

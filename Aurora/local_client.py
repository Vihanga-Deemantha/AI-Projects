"""
AURA Local Test Client
Talk to AURA with your microphone and speakers from the terminal, without the
Next.js frontend. Needs the extra packages in backend/requirements-local.txt.

Prerequisites:
    - Docker running:  docker compose up -d
    - Server running:  uvicorn backend.main:app --reload
    - An AURA account (sign up in the web app first)

Usage:
    python local_client.py --email you@example.com          # asks for your password
    python local_client.py --email you@example.com --voice alan --style irish --scenario interview

Credentials can also come from AURA_EMAIL / AURA_PASSWORD, or pass an existing
session token with --token / AURA_TOKEN. The valid --voice/--style/--scenario ids
are listed at GET /api/config/options.
"""
import argparse
import base64
import io
import sys
import tempfile
import getpass
import os
import time
import wave
import queue
import threading
import json
import warnings

# Suppress PyTorch FutureWarnings (e.g. from silero-vad) to prevent UI mangling
warnings.filterwarnings("ignore", category=FutureWarning)

# pyrefly: ignore [missing-import]
import numpy as np
# pyrefly: ignore [missing-import]
import requests
# pyrefly: ignore [missing-import]
import sounddevice as sd

# ── Configuration ──────────────────────────────────────────────────────────────
API_BASE = os.environ.get("AURA_API", "http://localhost:8000")
SAMPLE_RATE = 16_000          # Hz — must match what Whisper expects
BLOCK_SIZE = 512              # Samples per VAD chunk (~32ms at 16kHz)
SILENCE_SECONDS = 0.6         # Stop recording after this much silence
MAX_RECORDING_S = 30          # Safety cap to avoid runaway recordings

# ── CLI Args ───────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="AURA local voice client")
parser.add_argument("--voice", default="amy", help="companion / TTS voice id (see /api/config/options)")
parser.add_argument("--style", default="standard", help="speaking style id")
parser.add_argument("--scenario", default="casual", help="conversation scenario id")
parser.add_argument("--email", default=os.environ.get("AURA_EMAIL"), help="your AURA account email")
parser.add_argument("--token", default=os.environ.get("AURA_TOKEN"), help="an existing session token (skips the password)")
args = parser.parse_args()

AUTH_HEADERS: dict = {}


def authenticate() -> None:
    """Signs in (or accepts --token) and sets the Authorization header for every request."""
    if args.token:
        AUTH_HEADERS["Authorization"] = f"Bearer {args.token}"
        return
    if not args.email:
        print("[ERROR] Pass --email (or AURA_EMAIL), or --token. Sign up in the web app first.")
        sys.exit(1)
    password = os.environ.get("AURA_PASSWORD") or getpass.getpass(f"Password for {args.email}: ")
    resp = requests.post(f"{API_BASE}/api/auth/login", json={"email": args.email, "password": password}, timeout=15)
    if resp.status_code != 200:
        print(f"[ERROR] Sign-in failed: {resp.json().get('detail', resp.status_code)}")
        sys.exit(1)
    AUTH_HEADERS["Authorization"] = f"Bearer {resp.json()['access_token']}"


# ── VAD Setup ─────────────────────────────────────────────────────────────────
def _load_vad():
    """Load Silero VAD model. Prints a user-friendly error if torch is missing."""
    try:
        # pyrefly: ignore [missing-import]
        from silero_vad import load_silero_vad
        print("[VAD] Loading Silero VAD model...")
        model = load_silero_vad()
        print("[VAD] Ready.")
        return model
    except ImportError:
        print("[ERROR] silero-vad not installed. Run: pip install silero-vad torch")
        sys.exit(1)

vad_model = _load_vad()


def record_until_silence() -> np.ndarray:
    """
    Records audio from the default microphone using sounddevice.
    Uses Silero VAD to automatically stop when the user finishes speaking.

    Returns:
        float32 numpy array at SAMPLE_RATE Hz, or empty array if no speech detected.
    """
    print("\n[AURA] Listening...  (speak now — I'll stop when you pause)\n")

    audio_chunks = []
    silence_frames = 0
    silence_limit = int(SILENCE_SECONDS * SAMPLE_RATE / BLOCK_SIZE)
    speech_detected = False

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=BLOCK_SIZE,
    ) as stream:
        while True:
            chunk, _ = stream.read(BLOCK_SIZE)
            chunk_flat = chunk.flatten()
            audio_chunks.append(chunk_flat.copy())

            # Run VAD on this chunk
            # pyrefly: ignore [missing-import]
            import torch
            chunk_tensor = torch.tensor(chunk_flat)
            speech_prob = vad_model(chunk_tensor, SAMPLE_RATE).item()

            if speech_prob > 0.5:
                speech_detected = True
                silence_frames = 0
            elif speech_detected:
                silence_frames += 1
                if silence_frames >= silence_limit:
                    break

            # Safety: don't record forever
            recorded_secs = len(audio_chunks) * BLOCK_SIZE / SAMPLE_RATE
            if recorded_secs > MAX_RECORDING_S:
                print(f"[AURA] Reached max recording length ({MAX_RECORDING_S}s)")
                break

    if not speech_detected:
        return np.array([], dtype="float32")

    audio = np.concatenate(audio_chunks)
    duration = len(audio) / SAMPLE_RATE
    print(f"[AURA] Captured {duration:.1f}s of speech")
    return audio


def save_wav(audio: np.ndarray) -> str:
    """
    Saves a float32 numpy audio array to a temporary WAV file.
    Returns the path to the temp file.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio_int16 = (audio * 32767).astype(np.int16)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)    # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())
    return tmp.name


def play_audio(wav_bytes: bytes):
    """Decodes WAV bytes and plays them through the default audio output device."""
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    audio_int16 = np.frombuffer(frames, dtype=np.int16)
    audio_float = audio_int16.astype(np.float32) / 32767.0
    
    # Windows sounddevice quirk: stream closes instantly when sd.play returns,
    # often dropping the last ~100-300ms of audio still in the OS buffer.
    # We pad the end with 0.3s of silence so only the silence gets dropped.
    silence_padding = np.zeros(int(rate * 0.3), dtype=np.float32)
    padded_audio = np.concatenate([audio_float, silence_padding])
    
    sd.play(padded_audio, samplerate=rate, blocking=True)


def check_server():
    """Verifies the FastAPI server is reachable before starting the loop."""
    try:
        r = requests.get(f"{API_BASE}/health", timeout=10)
        r.raise_for_status()
        data = r.json()
        status = data.get("status", "?")
        db_status = data.get("database", "?")
        if status != "ok":
            print(f"[WARNING] Server status: {status} | database: {db_status}")
        else:
            print(f"[OK] Server is healthy | database: {db_status}")
    except requests.exceptions.ConnectionError:
        print(
            "\n[ERROR] Cannot connect to server.\n"
            "Make sure it is running:\n"
            "  uvicorn backend.main:app --reload\n"
        )
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Health check failed: {e}")
        sys.exit(1)


def start_session() -> str:
    """Creates a new AURA conversation session. Returns the conversation_id."""
    resp = requests.post(
        f"{API_BASE}/api/conversation/start",
        data={
            "scenario": args.scenario,
            "style": args.style,
            "voice": args.voice,
        },
        headers=AUTH_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    print(f"\n  Scenario : {data['scenario']}")
    print(f"  Style    : {data['style']}")
    print(f"  Voice    : {data['voice']}")
    print(f"  Session  : {data['conversation_id'][:8]}...")
    return data["conversation_id"]


def send_audio_streaming(conversation_id: str, wav_path: str) -> dict:
    """
    Sends audio to the streaming endpoint and plays chunks as they arrive.
    Uses a producer-consumer pattern:
        - Main thread: receives NDJSON lines, decodes audio, puts in queue
        - Playback thread: takes chunks from queue, plays them sequentially
    
    Returns:
        {
            "transcript": str,
            "full_reply": str,
            "timings": dict,
        }
    """
    audio_queue = queue.Queue()
    DONE_SENTINEL = None
    result = {}

    def playback_worker():
        """Plays WAV chunks from the queue in order."""
        while True:
            item = audio_queue.get()
            if item is DONE_SENTINEL:
                break
            wav_bytes, chunk_text = item
            # We don't print here because we print as soon as it's received
            # so the user can read along faster than speech
            play_audio(wav_bytes)
            # Brief natural pause between sentences — prevents robotic run-on sound
            # Increased to 0.25s for a more authentic break between thoughts
            time.sleep(0.25)

    # Start playback thread
    player = threading.Thread(target=playback_worker, daemon=True)
    player.start()

    with open(wav_path, "rb") as f:
        resp = requests.post(
            f"{API_BASE}/api/conversation/message-stream",
            data={"conversation_id": conversation_id},
            files={"audio_file": ("audio.wav", f, "audio/wav")},
            headers=AUTH_HEADERS,
            stream=True,
            timeout=180,
        )
        resp.raise_for_status()

        for line in resp.iter_lines():
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "transcript":
                print(f"\n  You  : {msg['text']}")
                result["transcript"] = msg["text"]

            elif msg_type == "audio_chunk":
                wav_bytes = base64.b64decode(msg["data"])
                audio_queue.put((wav_bytes, msg["text"]))

                # First chunk: print it so user sees AURA's reply starting
                if msg["index"] == 0:
                    print(f"  AURA : {msg['text']}", end="", flush=True)
                else:
                    print(f" {msg['text']}", end="", flush=True)

            elif msg_type == "done":
                result["full_reply"] = msg.get("full_reply", "")
                result["timings"] = msg.get("timings", {})
                print()  # newline after AURA's text

            elif msg_type == "warning":
                print(f"\n  [Note] {msg['message']}")

            elif msg_type == "error":
                print(f"\n  [Error] {msg['message']}")
                result["error"] = msg["message"]

    # Signal playback thread to stop after all chunks drain
    audio_queue.put(DONE_SENTINEL)
    player.join()  # Wait for all audio to finish playing

    return result


def print_timings(timings: dict):
    """Prints a formatted latency breakdown."""
    print()
    print(f"  STT         {timings.get('stt_ms') or 0:>6.0f} ms")
    if "llm_ttfs_ms" in timings:
        ttfs = timings.get('llm_ttfs_ms') or 0  # None when reply fit in flush
        print(f"  LLM (1st s) {ttfs:>6.0f} ms  \u2190 time to first sentence")
    else:
        print(f"  LLM         {timings.get('llm_ms') or 0:>6.0f} ms")
    print(f"  Total       {timings.get('total_ms') or 0:>6.0f} ms")


seen_correction_ids = set()

def fetch_and_print_feedback(conversation_id: str, wait_seconds: float = 0.0):
    """
    Prints grammar/vocab feedback not yet shown. If the server reports turns
    still being analysed, waits up to `wait_seconds` for them (analysis takes a
    couple of seconds, so the previous turn's feedback is normally ready by
    the time you finish reading the reply).
    """
    deadline = time.time() + wait_seconds
    while True:
        try:
            resp = requests.get(
                f"{API_BASE}/api/analysis/conversation/{conversation_id}/recent?limit=10",
                headers=AUTH_HEADERS, timeout=5.0,
            )
            if resp.status_code != 200:
                return
            body = resp.json()
        except Exception:
            return  # never let a polling hiccup break the chat

        new_corrections = [c for c in body.get("corrections", []) if c["id"] not in seen_correction_ids]
        if new_corrections:
            print("\n  [Feedback on your recent speech]")
            for c in new_corrections:
                seen_correction_ids.add(c["id"])
                icon = "❌" if c.get("is_error") else "💡"
                print(f"  {icon} {c.get('category', '').title()} ({c.get('subtype', '')})")
                print(f"     You said: \"{c.get('original')}\"")
                print(f"     Better  : \"{c.get('correction')}\"")
                print(f"     Why     : {c.get('explanation')}\n")
        if body.get("pending", 0) > 0 and time.time() < deadline:
            time.sleep(0.5)
            continue
        return


# ── Main Conversation Loop ─────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("=" * 55)
    print("  AURA — AI English Speaking Coach")
    print("  Local Voice Client")
    print("  Press Ctrl+C to end the session")
    print("=" * 55)

    check_server()
    authenticate()

    print("\n[Starting new session...]")
    conversation_id = start_session()
    print("\nReady! Start speaking whenever you like.\n")

    turn = 0
    while True:
        try:
            # Option B: Print any feedback generated from the *previous* turn before we record
            fetch_and_print_feedback(conversation_id)

            audio = record_until_silence()

            if len(audio) == 0:
                print("[AURA] No speech detected. Try again.\n")
                continue

            wav_path = save_wav(audio)
            turn += 1
            print(f"[AURA] Processing turn {turn}...")

            result = send_audio_streaming(conversation_id, wav_path)

            if "error" in result:
                print(f"[AURA] {result['error']}\n")
                continue

            print_timings(result.get("timings", {}))
            print()

        except KeyboardInterrupt:
            print("\n\n[AURA] Wrapping up...")
            fetch_and_print_feedback(conversation_id, wait_seconds=8)   # the last turn's feedback
            try:
                requests.post(f"{API_BASE}/api/conversation/{conversation_id}/end", headers=AUTH_HEADERS, timeout=5)
            except Exception:
                pass
            print("[AURA] Session ended. Great practice! Goodbye!\n")
            break
        except requests.exceptions.HTTPError as e:
            print(f"[ERROR] API error: {e.response.status_code} — {e.response.text}\n")
        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {e}\n")

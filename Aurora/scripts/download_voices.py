"""
Download corrupted Piper TTS voice model files.

Two voice files were found to be truncated/corrupted (exact power-of-2 sizes
indicate the download stopped early):
  - en_US-ryan-high.onnx:     32 MB actual, ~65 MB expected
  - en_US-lessac-medium.onnx: 40 MB actual, ~60 MB expected

This script re-downloads them from the official Piper voices HuggingFace repo.

Usage:
    python scripts/download_voices.py

After downloading, restore the VOICE_FILES mapping in backend/services/tts.py:
    "ryan":   "en_US-ryan-high.onnx",
    "lessac": "en_US-lessac-medium.onnx",

Then restart the server.
"""
import os
import sys
import urllib.request

VOICES_DIR = os.path.join(os.path.dirname(__file__), "..", "voices")

BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

CORRUPTED = {
    "en_US-ryan-high.onnx": {
        "url":      f"{BASE}/en/en_US/ryan/high/en_US-ryan-high.onnx",
        "json_url": f"{BASE}/en/en_US/ryan/high/en_US-ryan-high.onnx.json",
        "expected_mb": 65,
    },
    "en_US-lessac-medium.onnx": {
        "url":      f"{BASE}/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "json_url": f"{BASE}/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
        "expected_mb": 60,
    },
}


def _progress(count, block_size, total):
    pct = min(100, count * block_size * 100 // total) if total > 0 else 0
    mb  = count * block_size / (1024 * 1024)
    print(f"\r    {pct:3d}%  {mb:.1f} MB", end="", flush=True)


def download_file(url: str, dest: str):
    print(f"  -> {os.path.basename(dest)}")
    urllib.request.urlretrieve(url, dest, reporthook=_progress)
    print()  # newline after progress bar
    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"     Saved: {size_mb:.1f} MB")


def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def check_file(path: str) -> tuple[bool, float]:
    """Returns (is_suspicious, size_mb)."""
    if not os.path.exists(path):
        return False, 0.0
    size = os.path.getsize(path)
    return is_power_of_two(size), size / (1024 * 1024)


if __name__ == "__main__":
    print("=" * 60)
    print("Piper Voice File Repair")
    print("=" * 60)
    print()

    os.makedirs(VOICES_DIR, exist_ok=True)

    for filename, info in CORRUPTED.items():
        dest = os.path.join(VOICES_DIR, filename)
        suspicious, size_mb = check_file(dest)

        print(f"File: {filename}")
        if os.path.exists(dest):
            status = "CORRUPTED (truncated)" if suspicious else f"exists ({size_mb:.1f} MB) - may be OK"
            print(f"  Current: {size_mb:.1f} MB  [{status}]")
        else:
            print("  Current: missing")

        # Ask for confirmation if file doesn't look corrupted
        if os.path.exists(dest) and not suspicious:
            ans = input(f"  File looks OK ({size_mb:.1f} MB). Re-download anyway? [y/N] ").strip().lower()
            if ans != "y":
                print("  Skipped.")
                print()
                continue

        # Remove old file
        if os.path.exists(dest):
            os.remove(dest)
            print(f"  Removed old file.")

        # Download .onnx
        print(f"  Downloading from HuggingFace...")
        download_file(info["url"], dest)

        # Download .json config (if missing)
        json_dest = dest + ".json"
        if not os.path.exists(json_dest):
            print(f"  Downloading config...")
            download_file(info["json_url"], json_dest)
        else:
            print(f"  Config already present: {os.path.basename(json_dest)}")

        # Verify
        final_mb = os.path.getsize(dest) / (1024 * 1024)
        if final_mb < info["expected_mb"] * 0.8:
            print(f"  WARNING: File is {final_mb:.1f} MB, expected ~{info['expected_mb']} MB.")
            print(f"           Download may have failed again.")
        else:
            print(f"  OK: {final_mb:.1f} MB (expected ~{info['expected_mb']} MB)")
        print()

    print("=" * 60)
    print("Done! Next steps:")
    print()
    print("1. Edit backend/services/tts.py and restore the voice mappings:")
    print('      "ryan":   "en_US-ryan-high.onnx",')
    print('      "lessac": "en_US-lessac-medium.onnx",')
    print()
    print("2. Restart the server:")
    print("      uvicorn backend.main:app --reload --port 8000")
    print("=" * 60)

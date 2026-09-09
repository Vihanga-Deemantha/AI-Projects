"""
Download Piper TTS voice model files for AURA.

Downloads the required .onnx voice models and their .json config files
from the official Piper voices HuggingFace repository.

Usage:
    python scripts/download_voices.py
"""
import os
import urllib.request

VOICES_DIR = os.path.join(os.path.dirname(__file__), "..", "voices")
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

VOICES = {
    "en_US-amy-medium.onnx": {
        "url":      f"{BASE}/en/en_US/amy/medium/en_US-amy-medium.onnx",
        "json_url": f"{BASE}/en/en_US/amy/medium/en_US-amy-medium.onnx.json",
        "expected_mb": 60,
    },
    "en_US-ryan-high.onnx": {
        "url":      f"{BASE}/en/en_US/ryan/high/en_US-ryan-high.onnx",
        "json_url": f"{BASE}/en/en_US/ryan/high/en_US-ryan-high.onnx.json",
        "expected_mb": 115, # Actually ~65MB or 115MB depending on version, just check it's big
    },
    "en_GB-alan-medium.onnx": {
        "url":      f"{BASE}/en/en_GB/alan/medium/en_GB-alan-medium.onnx",
        "json_url": f"{BASE}/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json",
        "expected_mb": 60,
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
    print()
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
    print("AURA Piper Voice Downloader")
    print("=" * 60)
    print()

    os.makedirs(VOICES_DIR, exist_ok=True)

    for filename, info in VOICES.items():
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
                print("  Skipped.\n")
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
        if final_mb < 50: # All models should be >50MB
            print(f"  WARNING: File is {final_mb:.1f} MB, which is suspiciously small.")
            print(f"           Download may have failed.")
        else:
            print(f"  OK: {final_mb:.1f} MB")
        print()

    print("=" * 60)
    print("Download complete!")
    print("=" * 60)

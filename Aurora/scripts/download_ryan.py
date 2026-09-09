"""
Download the correct en_US-ryan-high.onnx voice model for Piper TTS.

The current file in voices/ is truncated at 32MB (corrupted download).
The correct file is ~65MB. This script re-downloads it from HuggingFace.

Usage:
    python scripts/download_ryan.py
"""
import os
import sys
import urllib.request

VOICES_DIR = os.path.join(os.path.dirname(__file__), "..", "voices")

FILES = {
    "en_US-ryan-high.onnx":      "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx",
    "en_US-ryan-high.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json",
}

def download(url: str, dest: str):
    print(f"Downloading: {os.path.basename(dest)}")
    print(f"  From: {url}")
    print(f"  To:   {dest}")

    def progress(count, block_size, total):
        pct = count * block_size * 100 // total if total > 0 else 0
        mb = count * block_size / (1024 * 1024)
        print(f"\r  {pct:3d}%  {mb:.1f} MB downloaded", end="", flush=True)

    urllib.request.urlretrieve(url, dest, reporthook=progress)
    print()  # newline after progress

    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"  Done. File size: {size_mb:.1f} MB")
    if size_mb < 50:
        print("  WARNING: File seems too small — expected ~65MB. Download may have failed.")
    else:
        print("  OK: File size looks correct.")

if __name__ == "__main__":
    os.makedirs(VOICES_DIR, exist_ok=True)

    for filename, url in FILES.items():
        dest = os.path.join(VOICES_DIR, filename)
        # Remove the old corrupted file if present
        if os.path.exists(dest):
            old_mb = os.path.getsize(dest) / (1024 * 1024)
            print(f"Removing old file ({old_mb:.1f} MB): {dest}")
            os.remove(dest)
        download(url, dest)
        print()

    print("=" * 60)
    print("Download complete!")
    print()
    print("Next steps:")
    print("  1. Edit backend/services/tts.py")
    print("  2. Change: \"ryan\": \"en_US-lessac-medium.onnx\"")
    print("  3. Back to: \"ryan\": \"en_US-ryan-high.onnx\"")
    print("  4. Restart the server: uvicorn backend.main:app --reload --port 8000")

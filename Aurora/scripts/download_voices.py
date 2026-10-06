"""
Download the Piper TTS voice models AURA needs.

The list of voices is read from backend/personalities.py (the companions' own
voices, plus the regional-accent models their speaking styles use), the same source
the server uses — so this script can never fall out of step with the app.
A voice is skipped if its file is already there and the right size; files are
downloaded to a temporary name and only renamed into place once complete, so an
interrupted download can never be mistaken for a good model.

Usage (from the Aurora/ folder):
    python scripts/download_voices.py              # download whatever is missing
    python scripts/download_voices.py --check      # just report; exit 1 if anything is missing
    python scripts/download_voices.py --force      # re-download everything
    python scripts/download_voices.py --only amy ryan      # companions are named by id; the regional
                                                           # models by voice name ("vctk", "alba")
"""
import argparse
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.personalities import VOICES, model_files  # noqa: E402  (pure data, no heavy imports)

VOICES_DIR = ROOT / "voices"
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
# en_US-kristin-medium.onnx -> lang en_US, name kristin, quality medium
FILENAME = re.compile(r"^(?P<lang>[a-z]{2}_[A-Z]{2})-(?P<name>.+)-(?P<quality>x_low|low|medium|high)\.onnx$")
MIN_PLAUSIBLE_MB = 30  # every voice AURA uses is 60+ MB; smaller means a truncated download


def urls_for(filename: str) -> tuple[str, str]:
    m = FILENAME.match(filename)
    if not m:
        raise ValueError(f"Can't derive a download URL from {filename!r}")
    folder = f"{BASE}/{m['lang'][:2]}/{m['lang']}/{m['name']}/{m['quality']}/{filename}"
    return folder, folder + ".json"


def wanted(only: list[str] | None) -> dict[str, str]:
    """
    id -> model filename, from the app's own tables: each companion's voice (by companion id), then the
    extra models regional accents use (by the voice's name, e.g. "vctk").
    """
    table = {vid: Path(v["file"]).name for vid, v in VOICES.items()}
    for filename in (Path(f).name for f in model_files()):
        if filename not in table.values():
            table[FILENAME.match(filename)["name"]] = filename
    if only:
        unknown = [v for v in only if v not in table]
        if unknown:
            sys.exit(f"Unknown voice(s): {', '.join(unknown)}. Known: {', '.join(table)}")
        table = {vid: table[vid] for vid in only}
    return table


def is_installed(filename: str) -> bool:
    model = VOICES_DIR / filename
    config = VOICES_DIR / (filename + ".json")
    return model.exists() and config.exists() and model.stat().st_size >= MIN_PLAUSIBLE_MB * 1024 * 1024


def download(url: str, dest: Path) -> None:
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=60) as response, open(part, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while chunk := response.read(1024 * 256):
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r    {done * 100 // total:3d}%  {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        print()
    if total and part.stat().st_size != total:
        part.unlink(missing_ok=True)
        raise IOError(f"Download of {dest.name} was cut short ({part.stat().st_size if part.exists() else 0} of {total} bytes)")
    part.replace(dest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report status only; exit 1 if any voice is missing")
    parser.add_argument("--force", action="store_true", help="re-download even if the file looks fine")
    parser.add_argument("--only", nargs="+", metavar="VOICE", help="limit to these voice ids")
    args = parser.parse_args()

    table = wanted(args.only)
    VOICES_DIR.mkdir(exist_ok=True)

    missing = [vid for vid, f in table.items() if not is_installed(f)]
    print(f"Voices directory: {VOICES_DIR}")
    for vid, filename in table.items():
        state = "installed" if vid not in missing else "MISSING"
        print(f"  {vid:8s} {filename:36s} {state}")

    if args.check:
        return 1 if missing else 0

    todo = list(table) if args.force else missing
    if not todo:
        print("All voices are installed.")
        return 0

    for vid in todo:
        filename = table[vid]
        model_url, config_url = urls_for(filename)
        print(f"\nDownloading {vid} ({filename})")
        try:
            download(model_url, VOICES_DIR / filename)
            download(config_url, VOICES_DIR / (filename + ".json"))
        except Exception as exc:
            print(f"  FAILED: {exc}")
            return 1
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

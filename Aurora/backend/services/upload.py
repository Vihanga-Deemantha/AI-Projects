"""
Avatar upload — validation + Cloudinary storage.

This is a synchronous, blocking module (like services/tts.py and
services/stt.py) — the router calls it via asyncio.to_thread() rather than
blocking the event loop for the upload+transform round trip.
"""
import io

import cloudinary
import cloudinary.uploader

from backend.config import CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_CLOUD_NAME

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB

_configured = False


class AvatarUploadError(Exception):
    """User-facing validation failure (wrong type, too large) or missing config."""


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return
    if not (CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET):
        raise AvatarUploadError("Avatar upload is not configured on this server")
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )
    _configured = True


def upload_avatar(file_bytes: bytes, content_type: str, user_id: str) -> str:
    """
    Validates and uploads an avatar image, returning its Cloudinary CDN URL.

    Always uploads to the same public_id per user (overwrite=True), so
    re-uploading replaces the previous avatar instead of accumulating
    orphaned images. The eager transformation crops to a 256x256 square with
    face-aware framing, so every avatar the frontend renders is pre-sized —
    no client-side cropping logic needed.
    """
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise AvatarUploadError("Only JPEG, PNG, or WebP images are allowed")
    if len(file_bytes) > MAX_BYTES:
        raise AvatarUploadError("Image must be 5 MB or smaller")

    _ensure_configured()

    result = cloudinary.uploader.upload(
        io.BytesIO(file_bytes),
        public_id=f"aura_avatars/{user_id}",
        overwrite=True,
        transformation=[{"width": 256, "height": 256, "crop": "fill", "gravity": "face"}],
    )
    return result["secure_url"]

"""Vision helpers: turn a captured image into text via the AI client.

Also supports pulling a still frame from a Tapo C201 (or any RTSP camera)
when TAPO_RTSP_URL is configured. OpenCV is imported lazily so the core app
and tests do not require it.
"""

from __future__ import annotations

from .ai_client import AIClient
from .config import get_settings


def image_to_text(image_bytes: bytes, ai: AIClient, mime: str = "image/jpeg") -> str:
    if not image_bytes:
        raise ValueError("empty image")
    return ai.transcribe_image(image_bytes, mime=mime)


def capture_tapo_frame() -> bytes:
    """Grab a single JPEG frame from the configured RTSP camera.

    Requires opencv (see requirements-tapo.txt) and TAPO_RTSP_URL set.
    """
    url = get_settings().tapo_rtsp_url
    if not url:
        raise RuntimeError("TAPO_RTSP_URL is not configured")
    try:
        import cv2  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "opencv is required for Tapo capture: pip install -r requirements-tapo.txt"
        ) from exc

    cap = cv2.VideoCapture(url)
    try:
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("failed to read frame from RTSP stream")
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("failed to encode frame")
        return buf.tobytes()
    finally:
        cap.release()

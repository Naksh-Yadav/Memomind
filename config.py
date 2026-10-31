"""Application settings loaded from the environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _int_setting(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, default)))
    except (TypeError, ValueError):
        return default


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "local-memomind-development-key")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite").strip()
    GEMINI_PRIMARY_TIMEOUT_MS = _int_setting("GEMINI_PRIMARY_TIMEOUT_MS", 25000)
    MAX_CONTENT_LENGTH = _int_setting("MAX_UPLOAD_MB", 12) * 1024 * 1024
    MAX_TEXT_CHARS = _int_setting("MAX_TEXT_CHARS", 30000)
    MAX_FILE_BYTES = MAX_CONTENT_LENGTH
    RATE_LIMIT_REQUESTS = _int_setting("RATE_LIMIT_REQUESTS", 8)
    RATE_LIMIT_WINDOW_SECONDS = _int_setting("RATE_LIMIT_WINDOW_SECONDS", 60)
    GEMINI_TIMEOUT_MS = _int_setting("GEMINI_TIMEOUT_MS", 120000)

"""Environment and path configuration."""

from pathlib import Path

from dotenv import load_dotenv
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / "config.env")

OUTPUT_BASE = Path(os.getenv("OUTPUT_BASE", PROJECT_ROOT / "output"))
MUSIC_BASE = Path(os.getenv("MUSIC_BASE", PROJECT_ROOT / "music"))
SFX_BASE = Path(os.getenv("SFX_BASE", PROJECT_ROOT / "sfx"))
LUT_BASE = Path(os.getenv("LUT_BASE", PROJECT_ROOT / "luts"))
CHANNELS_BASE = Path(os.getenv("CHANNELS_BASE", PROJECT_ROOT / "channels"))
SHORTS_CHANNELS_BASE = Path(
    os.getenv("SHORTS_CHANNELS_BASE", PROJECT_ROOT / "channels" / "shorts")
)
CONTENT_JSON_BASE = Path(os.getenv("CONTENT_JSON_BASE", PROJECT_ROOT / "content_json"))
SHORT_DURATIONS = (30, 60, 90, 120)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
HF_API_KEY = os.getenv("HF_API_KEY", "")
FAL_API_KEY = os.getenv("FAL_API_KEY", "")
FAL_KEY = os.getenv("FAL_KEY", "") or FAL_API_KEY
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
SCRIPT_PROVIDER = os.getenv("SCRIPT_PROVIDER", "groq")  # groq | gemini | ollama
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.3")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

_PLACEHOLDER_KEYS = {"your_groq_key_here", "your_hf_token_here", "your_fal_key_here", ""}


def has_fal_key() -> bool:
    return FAL_KEY not in _PLACEHOLDER_KEYS


if has_fal_key():
    os.environ.setdefault("FAL_KEY", FAL_KEY)

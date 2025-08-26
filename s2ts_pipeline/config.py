import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
INCOMING_DIR = DATA_DIR / "incoming_audio"
PROJECTS_DIR = DATA_DIR / "projects"
PROMPTS_DIR = BASE_DIR / "prompts"
MODELS_DIR = BASE_DIR / "models"
F5_MODELS_DIR = MODELS_DIR / "f5tts"

# ASR Configuration
ASR_EXE = r"C:\Users\follo\AppData\Roaming\OfflineTranscribe\OfflineTranscribe.exe"
ASR_OUTPUT_DIR = Path(r"C:\Users\follo\AppData\Roaming\OfflineTranscribe\TranscribeOutput")

# GUI Automation Settings
PAGE_READY_DELAY = 10
RESPONSE_TIMEOUT = 180
SAMPLE_INTERVAL = 1.2
MIN_STREAM_TIME = 6.0
STABLE_ROUNDS = 3

# Language Options
LANG_LABELS = {
    "Hindi": "Hindi",
    "Kannada": "Kannada", 
    "Telugu": "Telugu",
}

# Default Prompts
DEFAULT_CORRECTOR_PROMPT = (
    "You are a meticulous Tamil copy-editor for ASR output. "
    "Fix mishears, punctuation, casing, numerals, and spacing. "
    "Do NOT add or omit meaning. Return only cleaned Tamil text."
)

DEFAULT_TRANSLATOR_PROMPT = (
    "You are a professional translator. Translate the following **Tamil** text to the target language. "
    "Use natural register, preserve proper nouns, avoid code-mixing, and return only the translation."
)

# UI Settings
APP_TITLE = "Spider『X』 Speech → Translated Speech (S2TS) - Pro"
DARK_BG_GRADIENT = "linear-gradient(135deg, #0f172a, #1e293b)"
THEME_PRIMARY = "cyan"
THEME_SECONDARY = "blue"
THEME_NEUTRAL = "gray"
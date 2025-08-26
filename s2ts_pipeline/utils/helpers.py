import os
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import soundfile as sf
import numpy as np

def read_text(path: str, default: str = "") -> str:
    """Read a text file if it exists, else return the provided default."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return default

def write_text(path: Path, text: str) -> None:
    """Write text to a file, creating parent dirs if necessary."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text or "")

def secfmt(seconds: float) -> str:
    """Format seconds into mm:ss or h:mm:ss style for progress messages."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins, sec = divmod(seconds, 60)
    if mins < 60:
        return f"{mins}m {sec}s"
    hrs, mins = divmod(mins, 60)
    return f"{hrs}h {mins}m {sec}s"

def ensure_dir(path: Path) -> None:
    """Ensure a directory exists (mkdir -p style)."""
    path.mkdir(parents=True, exist_ok=True)

def now_hhmmss() -> str:
    """Return current time as HH:MM:SS string."""
    return time.strftime("%H:%M:%S")

def get_deterministic_hash(input_str: str) -> str:
    """Generate a deterministic hash for caching purposes."""
    return hashlib.md5(input_str.encode()).hexdigest()

def make_project_folder(audio_file: Path) -> Path:
    """Create a project folder for the given audio file."""
    base = audio_file.stem
    proj = Path(config.PROJECTS_DIR) / f"Proj-{base}"
    ensure_dir(proj)
    return proj

def stage_filenames(proj_dir: Path, base: str, lang: str = "") -> Dict[str, Path]:
    """Generate standardized filenames for each pipeline stage."""
    f = {
        "asr": proj_dir / f"{base}-ASR.txt",
        "clean": proj_dir / f"{base}-ASR-Clean.txt",
    }
    if lang:
        f["trans"] = proj_dir / f"{base}-{lang}-Translated.txt"
        f["tts"] = proj_dir / f"{base}-{lang}-TTS.wav"
    return f
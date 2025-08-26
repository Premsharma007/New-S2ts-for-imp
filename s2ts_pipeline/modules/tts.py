import time
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Union
import numpy as np
import soundfile as sf
import torch

from utils.helpers import ensure_dir

# Load once at module level
try:
    from transformers import AutoModel
    repo_id = "6Morpheus6/IndicF5"
    F5_MODEL = AutoModel.from_pretrained(repo_id, trust_remote_code=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    F5_MODEL = F5_MODEL.to(device)
    TTS_AVAILABLE = True
except Exception as e:
    print(f"Warning: Could not load TTS model: {e}")
    F5_MODEL = None
    TTS_AVAILABLE = False

def synthesize_tts(text: str, ref_audio_numpy: Optional[Tuple[int, np.ndarray]],
                  ref_text: str, out_path: Path, progress_callback=None) -> float:
    """
    Generate TTS audio using IndicF5 model.
    """
    if not TTS_AVAILABLE:
        if progress_callback:
            progress_callback(0, "TTS model not available")
        raise RuntimeError("TTS model not available")
    
    if progress_callback:
        progress_callback(10, "Starting TTS generation...")
    
    t0 = time.time()

    # If no ref provided, generate silence
    if ref_audio_numpy is None or not ref_text.strip():
        if progress_callback:
            progress_callback(50, "No reference provided, generating placeholder...")
        
        # Save a blank 1-second audio to indicate missing reference
        sr = 24000
        audio = np.zeros(sr, dtype=np.float32)
        ensure_dir(out_path.parent)
        sf.write(str(out_path), audio, samplerate=sr)
        
        duration = time.time() - t0
        if progress_callback:
            progress_callback(100, f"Placeholder audio generated in {duration:.1f}s")
        return duration

    # Validate tuple
    if not (isinstance(ref_audio_numpy, tuple) and len(ref_audio_numpy) == 2):
        if progress_callback:
            progress_callback(50, "Invalid reference, generating placeholder...")
        
        sr = 24000
        audio = np.zeros(sr, dtype=np.float32)
        ensure_dir(out_path.parent)
        sf.write(str(out_path), audio, samplerate=sr)
        
        duration = time.time() - t0
        if progress_callback:
            progress_callback(100, f"Placeholder audio generated in {duration:.1f}s")
        return duration

    sr_in, audio_np = ref_audio_numpy

    if progress_callback:
        progress_callback(30, "Preparing reference audio...")

    # Write temp reference wav
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, audio_np, samplerate=sr_in, format='WAV')
        tmp.flush()
        ref_path = tmp.name

    try:
        if progress_callback:
            progress_callback(60, "Generating TTS audio...")
        
        audio = F5_MODEL(text, ref_audio_path=ref_path, ref_text=ref_text)
        
        if progress_callback:
            progress_callback(80, "Saving audio file...")
        
        if isinstance(audio, np.ndarray) and audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0

        ensure_dir(out_path.parent)
        sf.write(str(out_path), audio, samplerate=24000)
        
    except Exception as e:
        if progress_callback:
            progress_callback(0, f"TTS generation failed: {e}")
        # On failure, write empty audio
        sr = 24000
        audio = np.zeros(sr, dtype=np.float32)
        sf.write(str(out_path), audio, samplerate=sr)
        raise

    duration = time.time() - t0
    
    if progress_callback:
        progress_callback(100, f"TTS generation completed in {duration:.1f}s")
    
    return duration
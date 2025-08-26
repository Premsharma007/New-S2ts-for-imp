import re
import time
from typing import Optional
from dataclasses import dataclass

from utils.helpers import read_text, write_text
from config import CORRECTOR_PROMPT_FILE, DEFAULT_CORRECTOR_PROMPT

@dataclass
class EngineConfig:
    url: str
    login_required: bool = True
    copy_btn_coords: tuple = (0, 0)

def clean_text_gui(text: str, engine_config: EngineConfig, 
                  progress_callback=None) -> Tuple[str, float]:
    """
    Clean text using GUI automation with the specified engine.
    """
    if progress_callback:
        progress_callback(10, "Starting text cleaning...")
    
    start_time = time.time()
    
    # Load prompt
    corrector_prompt = read_text(CORRECTOR_PROMPT_FILE, DEFAULT_CORRECTOR_PROMPT)
    
    if progress_callback:
        progress_callback(30, "Opening cleaning engine...")
    
    # Import here to avoid dependency issues
    from utils.gui_automation import GuiEngine
    
    # Initialize and run GUI engine
    engine = GuiEngine(engine_config)
    engine.start()
    
    if progress_callback:
        progress_callback(60, "Processing text correction...")
    
    cleaned = engine.send_and_get(corrector_prompt, text)
    engine.stop()
    
    duration = time.time() - start_time
    
    if progress_callback:
        progress_callback(100, f"Text cleaning completed in {duration:.1f}s")
    
    return cleaned, duration

def clean_text_basic(text: str, progress_callback=None) -> str:
    """
    Basic text cleaning without GUI automation.
    """
    if progress_callback:
        progress_callback(10, "Starting basic text cleaning...")
    
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    if progress_callback:
        progress_callback(40, "Fixing punctuation...")
    
    # Fix common punctuation issues
    text = re.sub(r'\.\.+', '.', text)
    text = re.sub(r',\s*,', ',', text)
    
    if progress_callback:
        progress_callback(70, "Finalizing text...")
    
    # Capitalize first letter
    text = text.strip()
    if text:
        text = text[0].upper() + text[1:]
    
    # Ensure it ends with a period
    if text and not text.endswith(('.', '!', '?')):
        text += '.'
    
    if progress_callback:
        progress_callback(100, "Basic text cleaning completed")
    
    return text
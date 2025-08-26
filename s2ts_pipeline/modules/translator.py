import time
from typing import Tuple, Optional
from dataclasses import dataclass

from utils.helpers import read_text, write_text
from config import TRANSLATOR_PROMPT_FILE, DEFAULT_TRANSLATOR_PROMPT

@dataclass
class EngineConfig:
    url: str
    login_required: bool = True
    copy_btn_coords: tuple = (0, 0)

def translate_text(text: str, target_lang: str, engine_config: EngineConfig,
                  progress_callback=None) -> Tuple[str, float]:
    """
    Translate text to target language using GUI automation.
    """
    if progress_callback:
        progress_callback(10, f"Starting translation to {target_lang}...")
    
    start_time = time.time()
    
    # Load prompt
    translator_prompt = read_text(TRANSLATOR_PROMPT_FILE, DEFAULT_TRANSLATOR_PROMPT)
    
    if progress_callback:
        progress_callback(30, "Opening translation engine...")
    
    # Import here to avoid dependency issues
    from utils.gui_automation import GuiEngine
    
    # Initialize and run GUI engine
    engine = GuiEngine(engine_config)
    engine.start()
    
    if progress_callback:
        progress_callback(60, "Processing translation...")
    
    translated = engine.send_and_get(translator_prompt, text, target_lang=target_lang)
    engine.stop()
    
    duration = time.time() - start_time
    
    if progress_callback:
        progress_callback(100, f"Translation to {target_lang} completed in {duration:.1f}s")
    
    return translated, duration
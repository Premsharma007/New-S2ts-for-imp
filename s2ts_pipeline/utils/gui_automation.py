# S2TS/utils/gui_automation.py

import time
import hashlib
import pyautogui
import pyperclip
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Tuple

from config import PAGE_READY_DELAY, RESPONSE_TIMEOUT, SAMPLE_INTERVAL, MIN_STREAM_TIME, STABLE_ROUNDS
from .helpers import ensure_dir

# --- Setup logging ---
log = logging.getLogger(__name__)


@dataclass
class EngineConfig:
    """Configuration for a specific GUI automation engine."""
    url: str
    login_required: bool = True
    copy_btn_coords: Tuple[int, int] = (0, 0)


class RobustGuiEngine:
    """
    Manages GUI automation for interacting with web-based AI engines.
    This class is designed to be resilient, with features for debugging and recovery.
    """

    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg
        self.screenshot_dir = Path("debug_screenshots")
        ensure_dir(self.screenshot_dir)
        self._browser_process: Optional[subprocess.Popen] = None

    def _sleep(self, duration: float) -> None:
        """A simple wrapper for time.sleep for consistency."""
        time.sleep(duration)

    def _capture_screenshot(self, context: str) -> None:
        """Captures a screenshot for debugging purposes."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.screenshot_dir / f"{context}_{timestamp}.png"
            pyautogui.screenshot(filename)
            log.info(f"📸 Screenshot captured: {filename}")
        except Exception as e:
            log.error(f"Failed to capture screenshot for context '{context}': {e}")

    def start(self) -> None:
        """Starts a new Chrome browser instance and navigates to the target URL."""
        log.info(f"Starting Chrome and navigating to {self.cfg.url}...")
        try:
            # Using a common path for Chrome, but this could be made configurable
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            self._browser_process = subprocess.Popen([chrome_path, self.cfg.url])
            self._sleep(PAGE_READY_DELAY)
            log.info("Browser started successfully.")
        except FileNotFoundError:
            log.error(f"Chrome executable not found at '{chrome_path}'. Please check the path.")
            raise
        except Exception as e:
            log.error(f"An unexpected error occurred while starting Chrome: {e}")
            self._capture_screenshot("chrome_start_error")
            raise

    def stop(self) -> None:
        """Terminates the browser process started by this engine instance."""
        if not self._browser_process:
            log.warning("Stop called but no browser process was recorded.")
            return

        log.info("Stopping browser process...")
        try:
            self._browser_process.terminate()
            self._browser_process.wait(timeout=5)
            log.info("Browser process terminated.")
        except subprocess.TimeoutExpired:
            log.warning("Browser did not terminate gracefully, killing process.")
            self._browser_process.kill()
        except Exception as e:
            log.error(f"Error while stopping the browser: {e}")
        finally:
            self._browser_process = None

    def send_and_get(self, prompt: str, text: str, target_lang: Optional[str] = None) -> str:
        """
        Sends a composed prompt and text to the GUI and waits for a stable response.

        Args:
            prompt: The instruction or system prompt.
            text: The user-provided text to be processed.
            target_lang: The target language, if applicable.

        Returns:
            The extracted response from the GUI.
        """
        composed_prompt = self._compose_prompt(prompt, text, target_lang)

        try:
            # --- 1. Send the prompt ---
            pyperclip.copy(composed_prompt)
            self._sleep(2)
            pyautogui.hotkey("ctrl", "v")
            self._sleep(5)
            pyautogui.press("enter")
            log.info("⌨️ Sent prompt and text to the GUI.")
            sent_at = time.time()

            self._sleep(10)

            # --- 2. Monitor for a stable response ---
            best_response = self._monitor_for_response(composed_prompt, sent_at)

            if not best_response:
                log.warning("No valid response was captured before timeout.")
                self._capture_screenshot("empty_response_timeout")

            return best_response

        except Exception as e:
            log.error(f"A critical error occurred in send_and_get: {e}", exc_info=True)
            self._capture_screenshot("send_and_get_critical_error")
            # Attempt to recover by stopping the browser
            self.stop()
            raise

        finally:
            # Always stop/close browser
            self.stop()

    def _compose_prompt(self, prompt: str, text: str, target_lang: Optional[str]) -> str:
        """Constructs the full string to be sent to the GUI."""
        composed = (prompt or "").strip()
        if target_lang:
            composed += f"\n\nTarget language: {target_lang}"
        composed += f"\n\nInput:\n{(text or '').strip()}"
        return composed

    def _monitor_for_response(self, sent_prompt: str, timeout: int = 120):
        start = time.time()
        last_digest = None
        stable_count = 0
        best_seen = ""
        last_update_time = time.time()


        # Initial wait before checking response
        self._sleep(8)


        while time.time() - start < timeout:
            page_text = self._copy_page_content()
            current_reply = self._extract_reply(page_text, sent_prompt)
            if not current_reply:
                self._sleep(2)
                continue


            best_seen = current_reply if len(current_reply) > len(best_seen) else best_seen
            current_digest = hashlib.md5(current_reply.encode()).hexdigest()


            if current_digest == last_digest:
                stable_count += 1
            else:
                stable_count = 0
                last_digest = current_digest
                last_update_time = time.time()


            # Accept if stable long enough OR no updates for 10s
            if stable_count >= 3 or (time.time() - last_update_time > 10):
                log.info("✅ Response stabilized, returning text.")
                return best_seen


            self._sleep(3)


        log.warning("⚠️ Timeout reached, returning best seen text.")
        return best_seen

    def _copy_page_content(self) -> str:
        """Attempts to copy the content of the page, trying multiple methods."""
        # Method 1: Click a predefined 'copy' button
        pyautogui.click(*self.cfg.copy_btn_coords)
        self._sleep(0.25)
        content = pyperclip.paste()
        if content:
            return content.strip()

        # Method 2: Fallback to Ctrl+A, Ctrl+C
        log.debug("Copy button failed, falling back to Select All + Copy.")
        try:
            # Click in the main window area to ensure focus
            w, h = pyautogui.size()
            pyautogui.click(w // 2, h // 2)
            self._sleep(0.1)
            pyautogui.hotkey("ctrl", "a")
            self._sleep(0.1)
            pyautogui.hotkey("ctrl", "c")
            self._sleep(0.2)
            return pyperclip.paste().strip()
        except Exception as e:
            log.error(f"Fallback copy method failed: {e}")
            return ""

    def _extract_reply(self, whole_page_text: str, sent_text: str) -> str:
        """
        Extracts the AI's latest reply by removing the initial prompt/text.
        """
        if not whole_page_text or not sent_text:
            return ""

        # Find the last occurrence of the sent text
        index = whole_page_text.rfind(sent_text)
        if index != -1:
            # Extract everything that comes after the sent text
            reply_text = whole_page_text[index + len(sent_text):].strip()
        else:
            # If the sent text isn't found, assume the whole page is the reply (less reliable)
            reply_text = whole_page_text

        # Filter out common UI noise words
        noise = {"copy", "regenerate", "send message", "stop generating"}
        lines = [
            line.strip() for line in reply_text.splitlines()
            if line.strip() and line.strip().lower() not in noise
        ]
        return "\n".join(lines).strip()
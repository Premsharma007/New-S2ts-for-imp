import time
import hashlib
import pyautogui
import pyperclip
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple
from pathlib import Path

from config import PAGE_READY_DELAY, RESPONSE_TIMEOUT, SAMPLE_INTERVAL, MIN_STREAM_TIME, STABLE_ROUNDS

@dataclass
class EngineConfig:
    url: str
    login_required: bool = True
    copy_btn_coords: Tuple[int, int] = (0, 0)

class GuiEngine:
    """
    GUI-based automation for Gemini/ChatGPT-like UIs.
    Relies on keyboard/mouse (pyautogui) + clipboard (pyperclip).
    """

    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg

    # -------------------- Utilities --------------------

    def _sleep(self, s: float):
        time.sleep(s)

    def _safe_clip_get(self) -> str:
        try:
            return pyperclip.paste() or ""
        except Exception:
            return ""

    def _digest(self, s: str) -> str:
        return hashlib.sha1(s.encode("utf-8", "ignore")).hexdigest()

    def _safe_click_copy(self) -> str:
        """Try clicking the page's Copy button and read clipboard."""
        try:
            pyautogui.click(*self.cfg.copy_btn_coords)
            self._sleep(0.25)
            return self._safe_clip_get().strip()
        except Exception:
            return ""

    def _select_all_copy(self) -> str:
        """
        Fallback: select all visible page text and copy.
        NOTE: This copies prompt+input+UI noise as well, so we will
        trim it later using _extract_last_reply.
        """
        # Click near bottom center to ensure focus inside page
        w, h = pyautogui.size()
        pyautogui.click(w // 2, int(h * 0.85))
        self._sleep(0.15)
        pyautogui.hotkey("ctrl", "a")
        self._sleep(0.05)
        pyautogui.hotkey("ctrl", "c")
        self._sleep(0.2)
        return self._safe_clip_get().strip()

    def _extract_last_reply(self, whole_page: str, sent_blob: str) -> str:
        """
        Heuristic: remove the message we sent (prompt+input) and UI fluff,
        keep the tail as the assistant's last reply.
        """
        page = (whole_page or "").strip()
        blob = (sent_blob or "").strip()
        idx = page.rfind(blob)
        tail = page[idx + len(blob):].strip() if (blob and idx != -1) else page

        # Drop obvious UI lines
        noise = {
            "copy", "regenerate", "send", "stop generating",
            "thumbs up", "thumbs down", "share", "report"
        }
        lines = []
        for ln in tail.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s.lower() in noise:
                continue
            if s.lower().startswith("press") and "enter" in s.lower():
                continue
            lines.append(ln)
        return "\n".join(lines).strip()

    def _focus_input_area(self):
        """Try to get caret into the chat input box reliably."""
        # Escape any omnibox focus then click near bottom center (most UIs place the input there)
        pyautogui.hotkey("ctrl", "l")    # focus address bar
        pyautogui.press("esc")           # leave address bar
        self._sleep(0.1)
        w, h = pyautogui.size()
        pyautogui.click(w // 2, int(h * 0.92))
        self._sleep(0.1)

    # -------------------- Lifecycle --------------------

    def start(self):
        print(f"🌐 Opening {self.cfg.url} ...")
        # If Chrome path differs, change it here:
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        subprocess.Popen([chrome_path, self.cfg.url])
        self._sleep(PAGE_READY_DELAY)

    def stop(self):
        # Close current tab only after we've copied the reply
        pyautogui.hotkey("ctrl", "w")
        self._sleep(0.8)

    # -------------------- Core --------------------

    def send_and_get(self, prompt: str, text: str, target_lang: Optional[str] = None) -> str:
        """
        Paste composed message, send, wait until response stabilizes,
        copy ONLY the assistant's reply (via Copy button if possible),
        fallback to select-all + extract if needed.
        """
        # Compose the exact blob we will send (used for trimming fallback)
        composed = (prompt or "").strip()
        if target_lang:
            composed += f"\n\nTarget language: {target_lang}"
        composed += f"\n\nInput:\n{(text or '').strip()}"

        # Focus input & send
        #self._focus_input_area()
        # Paste + Enter
        pyperclip.copy(composed)
        pyautogui.hotkey("ctrl", "v")
        self._sleep(0.1)
        pyautogui.press("enter")
        print("⌨️ Sent prompt+text.")

        sent_at = time.time()
        deadline = sent_at + RESPONSE_TIMEOUT

        # --- Stabilization state ---
        last_digest = ""
        stable_rounds = 0
        best_seen = ""

        # --- Warm-up wait before first copy ---
        print("⏳ Waiting for model to start responding...")
        self._sleep(8)   # avoid capturing echo of input

        while time.time() < deadline:
            # Always scroll bottom so Copy button belongs to last reply
            pyautogui.hotkey("end")
            self._sleep(0.5)

            # Try primary copy method
            copied = self._safe_click_copy()
            if not copied:
                # fallback: select all and try extracting last reply
                page_text = self._select_all_copy()
                copied = self._extract_last_reply(page_text, composed)

            copied = (copied or "").strip()

            # Ignore if it's identical to our own input (echoed back)
            if copied and copied != composed:
                best_seen = copied
                dg = self._digest(copied)

                if dg == last_digest:
                    stable_rounds += 1
                    print(f"🔄 Stable check {stable_rounds}/{STABLE_ROUNDS}")
                else:
                    stable_rounds = 0
                    last_digest = dg

                # Only accept if model had at least MIN_STREAM_TIME
                if (time.time() - sent_at) >= MIN_STREAM_TIME and stable_rounds >= STABLE_ROUNDS:
                    print("✅ Response stabilized.")
                    return copied
            else:
                print("...still waiting for valid content...")

            self._sleep(SAMPLE_INTERVAL)

        print("⚠️ Timeout: returning best seen reply.")
        return (best_seen or "").strip()
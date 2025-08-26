import time
import shutil
import pyperclip
from pathlib import Path
from typing import Tuple, Optional

# GUI automation imports
try:
    from pywinauto.application import Application
    from pywinauto import keyboard
    import win32gui
    import win32con
except ImportError:
    print("Warning: GUI automation libraries not available")

from utils.helpers import ensure_dir
from config import ASR_EXE, ASR_OUTPUT_DIR

def run_asr(audio_path: Path, out_txt_path: Optional[Path] = None, 
           progress_callback=None) -> Tuple[str, float, str]:
    """
    Automates OfflineTranscribe.exe using pywinauto.
    Queues file while visible, then runs fully minimized in background.
    """
    if progress_callback:
        progress_callback(10, "Starting ASR process...")
    
    start = time.time()
    
    try:
        app = Application(backend="uia").start(ASR_EXE)
        dlg = app.window(title_re=".*OfflineTranscribe.*")
        dlg.wait("visible", timeout=20)
        
        if progress_callback:
            progress_callback(20, "ASR application started")

        # 1. Add audio file
        add_btn = dlg.child_window(title="Avalonia.Controls.Grid", control_type="Button")
        add_btn.click_input()
        time.sleep(1)

        if progress_callback:
            progress_callback(30, "Adding audio file to ASR...")

        print("⌨️ Sending file path via keyboard...")
        keyboard.send_keys(str(audio_path))
        time.sleep(0.5)
        keyboard.send_keys("{ENTER}")
        time.sleep(2)

        # 2. Add to queue
        queue_btn = dlg.child_window(title="Add to transcribe queue", control_type="Button")
        queue_btn.click_input()
        time.sleep(2)

        if progress_callback:
            progress_callback(40, "File queued for transcription")

        # 🔹 Minimize once queued (never restore again)
        hwnd = dlg.handle
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            print("✅ Transcription running minimized in background.")
        except Exception:
            print("⚠️ Could not minimize window.")

        if progress_callback:
            progress_callback(50, "Transcription in progress...")

        # 3. Wait for "Show transcribed text" (up to 2h)
        show_btn = None
        for i in range(3600):  # 7200 sec = 2h
            try:
                show_btn = dlg.child_window(title="Show transcribed text", control_type="Button")
                if show_btn.exists():
                    break
            except Exception:
                pass
            
            if progress_callback and i % 30 == 0:  # Update every minute
                progress_callback(50 + min(40, i/90), f"Transcribing... ({i//60}m elapsed)")
                
            time.sleep(2)

        text = ""
        if show_btn and show_btn.exists():
            if progress_callback:
                progress_callback(90, "Transcription complete, retrieving text...")

            # 🔹 Restore window so popup is accessible
            dlg.restore()
            dlg.set_focus()
            dlg.maximize()  # 🔹 Force fullscreen so all controls are visible
            time.sleep(1)

            # Prefer clipboard method
            show_btn.click_input()
            time.sleep(1)

            # Attach strictly to popup
            popup = app.window(title_re=".*Transcribe.*")
            popup.wait("visible", timeout=60)  # wait up to 1 min for popup

            try:
                copy_btn = popup.child_window(title="Copy to clipboard", control_type="Button")
                copy_btn.wait("enabled", timeout=30)
                copy_btn.click_input()
                time.sleep(1)

                text = pyperclip.paste().strip()
            except Exception as e:
                print(f"⚠️ Could not click Copy button: {e}")
                text = ""

            # Safely close popup
            try:
                close_btns = popup.descendants(control_type="Button", title="Close")
                if close_btns:
                    close_btns[0].click_input()
                    time.sleep(1)
            except Exception:
                print("⚠️ Popup did not close properly")

        else:
            if progress_callback:
                progress_callback(90, "Using fallback text extraction...")
            
            # Fallback: latest file in TranscribeOutput
            latest_folder = max(ASR_OUTPUT_DIR.glob("*"), key=lambda x: x.stat().st_mtime)
            latest_txt = max(Path(latest_folder).glob("*.txt"), key=lambda x: x.stat().st_mtime)
            
            if out_txt_path:
                shutil.copy(latest_txt, out_txt_path)
                text = out_txt_path.read_text(encoding="utf-8").strip()
            else:
                text = latest_txt.read_text(encoding="utf-8").strip()

        # 🔹 Cleanup logs (after popup handling)
        try:
            x_btn = dlg.child_window(title="❌", control_type="Button")
            if x_btn.exists():
                x_btn.click_input()
                time.sleep(1)
        except:
            print("⚠️ Could not clear project log")

        # Close app
        try:
            dlg.close()
        except:
            print("⚠️ Could not close OfflineTranscribe.exe")

    except Exception as e:
        print(f"❌ ASR process failed: {e}")
        if progress_callback:
            progress_callback(0, f"ASR failed: {str(e)}")
        raise

    duration = time.time() - start
    
    if progress_callback:
        progress_callback(100, f"ASR completed in {duration:.1f}s")
        
    return text, duration, str(out_txt_path) if out_txt_path else ""
"""
core/gamer.py — Gamer Mode engine for Ember AI.

Architecture:
  GamerMode.start()      → launches a daemon thread
  GamerMode.set_active() → toggle capture on/off at runtime
  _analysis_loop()       → every INTERVAL seconds:
                             1. find + capture target window
                             2. send to Vision model
                             3. if not [IGNORE] → TTS → push to SSE queue
"""

import base64
import io
import threading
import time
from queue import Empty, Queue

try:
    import pygetwindow as gw
    _HAS_GW = True
except ImportError:
    _HAS_GW = False

try:
    import mss
    _HAS_MSS = True
except ImportError:
    _HAS_MSS = False

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


# ── Gamer Mode vision prompt ──────────────────────────────────────────────────
_GAMER_PROMPT = (
    "You are Ember, a brilliant, sarcastic, and tech-savvy gamer companion. "
    "You are watching the user play a game. Analyze this screenshot carefully.\n"
    "RULE 1: If nothing important or interesting is happening, reply with ONLY the single word: [IGNORE]\n"
    "RULE 2: If there is a major event (low health, a strategic decision, a funny mistake, a big achievement, "
    "or something worth commenting on), reply with ONE short, witty, sarcastic, or helpful sentence. "
    "No asterisks. No greetings. Just the comment."
)


class GamerMode:
    """Singleton-style class that owns the capture thread and SSE event queue."""

    def __init__(self, target_window: str, interval: int, vision_fn, tts_fn):
        """
        Args:
            target_window: Window title substring to search for (e.g. 'Hearts of Iron IV')
            interval:      Seconds between captures
            vision_fn:     Callable(image_b64: str) -> str  — your existing vision function
            tts_fn:        Callable(text: str, provider: str) -> (b64: str, mime: str)
        """
        self.target_window = target_window
        self.interval      = interval
        self._vision_fn    = vision_fn
        self._tts_fn       = tts_fn

        self._active = False
        self._lock   = threading.Lock()
        self._thread: threading.Thread | None = None

        # SSE consumers subscribe to this queue
        # Each item: {"text": str, "audio_base64": str, "audio_mime": str}
        self.event_queue: Queue = Queue(maxsize=20)

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        """Launch the background thread (daemon). Safe to call multiple times."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._analysis_loop, daemon=True, name="GamerMode")
        self._thread.start()
        print("[GamerMode] background thread started.")

    def set_active(self, active: bool):
        with self._lock:
            self._active = active
        state = "ON" if active else "OFF"
        print(f"[GamerMode] toggled {state} (target: '{self.target_window}')")

    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def status(self) -> dict:
        return {
            "active": self.is_active(),
            "target_window": self.target_window,
            "interval_seconds": self.interval,
            "libs_ok": _HAS_GW and _HAS_MSS and _HAS_PIL,
        }

    # ── Window capture ─────────────────────────────────────────────────────────

    def _find_window(self):
        """Return (left, top, width, height) of target window, or None."""
        if not _HAS_GW:
            return None
        try:
            matches = [w for w in gw.getAllWindows()
                       if self.target_window.lower() in (w.title or "").lower()
                       and not w.isMinimized
                       and w.width > 100]
            if not matches:
                return None
            win = matches[0]
            return win.left, win.top, win.width, win.height
        except Exception as e:
            print(f"[GamerMode] window search error: {e}")
            return None

    def _capture_window(self, left, top, width, height) -> str | None:
        """Capture the given bounding box and return a JPEG base64 string."""
        if not (_HAS_MSS and _HAS_PIL):
            return None
        try:
            with mss.mss() as sct:
                monitor = {"left": left, "top": top, "width": width, "height": height}
                raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            # Downscale if very large to keep API costs low
            max_dim = 1280
            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            print(f"[GamerMode] capture error: {e}")
            return None

    # ── Analysis loop (daemon thread) ─────────────────────────────────────────

    def _analysis_loop(self):
        while True:
            try:
                if not self.is_active():
                    time.sleep(2)
                    continue

                bbox = self._find_window()
                if not bbox:
                    print(f"[GamerMode] '{self.target_window}' not found or minimized — sleeping.")
                    time.sleep(5)
                    continue

                left, top, width, height = bbox
                img_b64 = self._capture_window(left, top, width, height)
                if not img_b64:
                    time.sleep(self.interval)
                    continue

                # Call vision model
                comment = self._vision_fn(img_b64)
                if not comment or "[IGNORE]" in comment.upper():
                    print(f"[GamerMode] IGNORE — no comment.")
                else:
                    print(f"[GamerMode] comment: {comment}")
                    audio_b64, audio_mime = self._tts_fn(comment)
                    payload = {
                        "text": comment,
                        "audio_base64": audio_b64,
                        "audio_mime": audio_mime or "audio/wav",
                    }
                    if not self.event_queue.full():
                        self.event_queue.put(payload)

                # Wait for the next capture interval
                time.sleep(self.interval)

            except Exception as e:
                print(f"[GamerMode] loop error: {e}")
                time.sleep(self.interval)

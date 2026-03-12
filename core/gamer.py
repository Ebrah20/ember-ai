"""
core/gamer.py — Gamer Mode engine for Ember AI.

Architecture:
  GamerMode.start()      → launches a daemon thread
  GamerMode.set_active() → toggle capture on/off at runtime
  _analysis_loop()       → every INTERVAL seconds:
                             1. find + capture target window
                             2. send to Vision model
                             3. always produce a comment → TTS → push to SSE queue
"""

import base64
import ctypes
import io
import os
import threading
import time
from datetime import datetime
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
    from PIL import Image, ImageDraw
    _HAS_PIL = True
except ImportError:
    Image = None
    ImageDraw = None
    _HAS_PIL = False

# ── Mouse Tracking (Windows) ────────────────────────────────────────────────
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def _get_mouse_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


# ── Gamer Mode vision prompt ──────────────────────────────────────────────────
# NOTE: Now provided dynamically by brain.get_gamer_vision_prompt(language).
# This local prompt is kept for fallback reference only.
_GAMER_PROMPT = "Gamer Mode active."  # unused — see brain.py


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
        self._notif_fn     = None   # set by app.py — reads top-left notification zone
        self._language     = "Arabic"
        self._profile      = None   # GameProfile — set by app.py after detect_game()

        self._active = False
        self._lock   = threading.Lock()
        self._thread: threading.Thread | None       = None
        self._alert_thread: threading.Thread | None = None

        # ── Attack alert state ────────────────────────────────────────────────
        self._alert_cooldown      = 20
        self._last_alert_time     = 0.0
        self._prev_notif_pixels   = 0     # last measured bright pixel count in notification zone

        # ── Ignore streak counter ──────────────────────────────────────────────
        self._ignore_count = 0

        # SSE
        self.event_queue: Queue = Queue(maxsize=20)

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        """Launch the background thread (daemon). Safe to call multiple times."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._analysis_loop, daemon=True, name="GamerMode")
        self._thread.start()
        # Also start the fast red-alert scanner
        self._alert_thread = threading.Thread(target=self._alert_loop, daemon=True, name="GamerAlertScan")
        self._alert_thread.start()
        print("[GamerMode] background threads started (analysis + red-alert scanner).")

    def set_active(self, active: bool, language: str = "Arabic"):
        with self._lock:
            self._active   = active
            self._language = language
        state = "ON" if active else "OFF"
        print(f"[GamerMode] toggled {state} (target: '{self.target_window}', language: '{language}')")

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

    def debug_capture(self) -> dict:
        """
        One-time instant capture for debugging.
        Returns window bbox, all visible windows, and the screenshot.
        """
        # List all open window titles so user can see what's detected
        all_titles = []
        if _HAS_GW:
            try:
                all_titles = [w.title for w in gw.getAllWindows() if w.title.strip()]
            except Exception:
                all_titles = ["error reading windows"]

        bbox = self._find_window()
        if not bbox:
            return {
                "found": False,
                "target": self.target_window,
                "all_windows": all_titles,
                "message": f"Window '{self.target_window}' not found or minimized.",
            }

        left, top, width, height = bbox
        img_b64 = self._capture_window(left, top, width, height)
        return {
            "found": True,
            "target": self.target_window,
            "bbox": {"left": left, "top": top, "width": width, "height": height},
            "all_windows": all_titles,
            "screenshot_b64": img_b64,
            "message": f"Successfully captured '{self.target_window}' ({width}x{height})",
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
        """Capture the given bounding box, save to disk, and return a JPEG base64 string."""
        if not (_HAS_MSS and _HAS_PIL):
            return None
        try:
            with mss.mss() as sct:
                monitor = {"left": left, "top": top, "width": width, "height": height}
                raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            
            # ── Draw Mouse Cursor ────────────────────────────────────────────
            mx, my = _get_mouse_pos()
            # Check if mouse is within this window's bounds
            if left <= mx < left + width and top <= my < top + height:
                # Local coordinates within the image
                lx, ly = mx - left, my - top
                draw = ImageDraw.Draw(img)
                # Draw a prominent red cursor (crosshair + circle)
                r = 15
                draw.ellipse((lx - r, ly - r, lx + r, ly + r), outline="red", width=3)
                draw.line((lx - r - 5, ly, lx + r + 5, ly), fill="red", width=3)
                draw.line((lx, ly - r - 5, lx, ly + r + 5), fill="red", width=3)
                draw.ellipse((lx - 3, ly - 3, lx + 3, ly + 3), fill="yellow")

            # Downscale if very large to keep API costs low
            max_dim = 1280
            if img.width > max_dim or img.height > max_dim:
                img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            # ── Save screenshot to disk ──────────────────────────────────────
            try:
                save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vision_captures")
                os.makedirs(save_dir, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = os.path.join(save_dir, f"gamer_{ts}.jpg")
                img.save(save_path, format="JPEG", quality=85)
                print(f"[GamerMode] screenshot saved → {save_path}")
            except Exception as save_err:
                print(f"[GamerMode] screenshot save error: {save_err}")
            # ────────────────────────────────────────────────────────────────
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            print(f"[GamerMode] capture error: {e}")
            return None

    # ── Red Alert (minimap) scanner ───────────────────────────────────────────

    def _detect_red_alert(self, win_left: int, win_top: int, win_width: int, win_height: int) -> bool:
        """
        Detect the attack-alert RED BORDER in Generals ZH (and similar RTS).

        Strategy:
          In Generals Zero Hour, an attack triggers a SOLID RED BAR on the
          minimap border (top and right edges flash solid red).
          Normal enemy units appear as small scattered red dots INSIDE the minimap.

          We scan ONLY the thin top border strip (6 px high) of the minimap.
          If >55% of that strip's pixels are pure-red → attack is real.
          Scattered unit dots would never saturate a full horizontal strip.
        """
        if not (_HAS_MSS and _HAS_PIL):\
            return False
        try:
            # Minimap box: bottom-left corner ~22% wide, 22% tall
            mm_w    = max(1, int(win_width  * 0.22))
            mm_h    = max(1, int(win_height * 0.22))
            mm_left = win_left
            mm_top  = win_top + win_height - mm_h

            # ── Scan only the TOP border strip (6 pixels tall) ───────────────
            strip_h = 6
            with mss.mss() as sct:
                raw = sct.grab({
                    "left":   mm_left,
                    "top":    mm_top,          # very top of the minimap border
                    "width":  mm_w,
                    "height": strip_h,
                })
            strip = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

            # Count VERY pure red pixels: R>210, G<60, B<60
            total  = strip.width * strip.height
            red_ct = sum(1 for r, g, b in strip.getdata() if r > 210 and g < 60 and b < 60)
            ratio  = red_ct / max(total, 1)

            if ratio > 0.55:
                print(f"[GamerMode] 🔴 Attack border detected! (border red ratio={ratio:.2f})")
                return True

            # ── Fallback: check the RIGHT border strip (6 px wide) ──────────
            with mss.mss() as sct:
                raw2 = sct.grab({
                    "left":   mm_left + mm_w - 6,
                    "top":    mm_top,
                    "width":  6,
                    "height": mm_h,
                })
            strip2 = Image.frombytes("RGB", raw2.size, raw2.bgra, "raw", "BGRX")
            total2  = strip2.width * strip2.height
            red_ct2 = sum(1 for r, g, b in strip2.getdata() if r > 210 and g < 60 and b < 60)
            ratio2  = red_ct2 / max(total2, 1)

            if ratio2 > 0.55:
                print(f"[GamerMode] 🔴 Attack border detected (right)! (ratio={ratio2:.2f})")
                return True

            return False
        except Exception as e:
            print(f"[GamerMode] alert scan error: {e}")
            return False

    # ── Notification zone helpers ─────────────────────────────────────────────

    def _count_notif_brightness(self, win_left: int, win_top: int, win_width: int) -> int:
        """Count near-white pixels in the notification zone (top-left, below stats line).
        Returns pixel count — a sudden increase means new text appeared."""
        if not (_HAS_MSS and _HAS_PIL):
            return 0
        try:
            # Skip the first ~18px (stats/fps line), read next 55px tall, 400px wide
            zone = {
                "left":   win_left,
                "top":    win_top + 18,
                "width":  min(400, win_width),
                "height": 55,
            }
            with mss.mss() as sct:
                raw = sct.grab(zone)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            # Count near-white pixels (R,G,B all >200 = bright white text)
            return sum(1 for r, g, b in img.getdata() if r > 200 and g > 200 and b > 200)
        except Exception:
            return 0

    def _capture_notification_zone(self, win_left: int, win_top: int, win_width: int) -> str | None:
        """Capture the notification zone as base64 JPEG for vision reading."""
        if not (_HAS_MSS and _HAS_PIL):
            return None
        try:
            zone = {
                "left":   win_left,
                "top":    win_top + 18,
                "width":  min(400, win_width),
                "height": 55,
            }
            with mss.mss() as sct:
                raw = sct.grab(zone)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            return base64.b64encode(buf.getvalue()).decode()
        except Exception as e:
            print(f"[GamerMode] notif zone capture error: {e}")
            return None

    def _alert_loop(self):
        """
        Fast (1-second) loop. Two jobs:
          1. Watch the notification zone (top-left) for new bright text.
          2. If new text appears → read it with vision → TTS if attack, text-only otherwise.
        """
        while True:
            try:
                if not self.is_active():
                    time.sleep(2)
                    continue

                bbox = self._find_window()
                if not bbox:
                    time.sleep(3)
                    continue

                left, top, width, height = bbox

                now = time.time()
                with self._lock:
                    last      = self._last_alert_time
                    cd        = self._alert_cooldown
                    lang      = self._language
                    notif_fn  = self._notif_fn
                    prev_px   = self._prev_notif_pixels
                    profile   = self._profile

                # ── Measure brightness of notification zone ───────────────────
                bright_now = self._count_notif_brightness(left, top, width)
                delta      = bright_now - prev_px
                with self._lock:
                    self._prev_notif_pixels = bright_now

                # A sudden surge of bright pixels = new notification text appeared
                BRIGHTNESS_THRESHOLD = 120  # tweak if needed
                if delta > BRIGHTNESS_THRESHOLD and (now - last) > cd and notif_fn:
                    notif_b64 = self._capture_notification_zone(left, top, width)
                    if notif_b64:
                        result = notif_fn(notif_b64, language=lang, profile=profile)
                        if result and "[IGNORE]" not in result.upper():
                            is_attack = "[ATTACK]" in result.upper()
                            # Strip the [ATTACK] prefix for display
                            display = result.replace("[ATTACK]", "").replace("[attack]", "").strip()
                            if not display:
                                display = "⚠️ هجوم!" if lang == "Arabic" else "⚠️ Under attack!"

                            print(f"[GamerMode] 📢 Notification: {display} (attack={is_attack})")
                            with self._lock:
                                self._last_alert_time = now

                            if is_attack:
                                # Attack → full TTS + text
                                audio_b64, audio_mime = self._tts_fn(display)
                            else:
                                # Info event → text only, no TTS
                                audio_b64, audio_mime = None, None

                            payload = {
                                "text":         display,
                                "audio_base64": audio_b64,
                                "audio_mime":   audio_mime,
                                "alert":        is_attack,
                            }
                            if not self.event_queue.full():
                                self.event_queue.put(payload)

            except Exception as e:
                print(f"[GamerMode] alert loop error: {e}")

            time.sleep(1)

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

                with self._lock:
                    language     = self._language
                    ignore_count = self._ignore_count
                    profile      = self._profile

                comment = self._vision_fn(img_b64, language=language, profile=profile)

                if not comment or "[IGNORE]" in comment.upper():
                    with self._lock:
                        self._ignore_count += 1
                    ic = self._ignore_count

                    if ic >= 5:
                        # Force a real comment — bypass IGNORE rule
                        print(f"[GamerMode] ⚡ Forcing comment after {ic} IGNOREs")
                        with self._lock:
                            self._ignore_count = 0
                        forced_comment = self._vision_fn(img_b64, language=language, forced=True, profile=profile)
                        if forced_comment and "[IGNORE]" not in forced_comment.upper():
                            payload = {
                                "text":         forced_comment,
                                "audio_base64": None,   # text only
                                "audio_mime":   None,
                            }
                            if not self.event_queue.full():
                                self.event_queue.put(payload)
                    else:
                        print(f"[GamerMode] IGNORE ({ic}/5) — skipping.")
                else:
                    print(f"[GamerMode] comment: {comment}")
                    with self._lock:
                        self._ignore_count = 0   # reset streak

                    # Regular commentary → TTS audio + text
                    audio_b64, audio_mime = self._tts_fn(comment)
                    payload = {
                        "text":         comment,
                        "audio_base64": audio_b64,
                        "audio_mime":   audio_mime or "audio/wav",
                    }
                    if not self.event_queue.full():
                        self.event_queue.put(payload)

                time.sleep(self.interval)

            except Exception as e:
                print(f"[GamerMode] loop error: {e}")
                time.sleep(self.interval)


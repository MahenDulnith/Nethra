"""Offline audio feedback: non-blocking text-to-speech and chimes (macOS `say` / `afplay`)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from typing import Dict, Optional


class AudioFeedback:
    CHIMES = {"found": "Glass", "aligned": "Hero", "lost": "Basso", "done": "Purr"}

    def __init__(self, enabled: bool = True, voice_rate: int = 185, min_repeat_interval: float = 4.0):
        self.enabled = enabled and sys.platform in ("darwin", "win32")
        self.voice_rate = voice_rate
        self.min_repeat_interval = min_repeat_interval
        self.muted = False
        self._say = shutil.which("say") if sys.platform == "darwin" else None
        self._afplay = shutil.which("afplay") if sys.platform == "darwin" else None
        self._speech_proc: Optional[subprocess.Popen] = None
        self._last_spoken: Dict[str, float] = {}
        self.last_message: Optional[str] = None
        self.last_message_time = 0.0

    def speak(self, text: str, now: Optional[float] = None, interrupt: bool = True, force: bool = False) -> bool:
        """Speaks text without blocking. The same phrase is not repeated within min_repeat_interval unless force=True."""
        now = time.time() if now is None else now
        last = self._last_spoken.get(text)
        if not force and last is not None and now - last < self.min_repeat_interval:
            return False
        self._last_spoken[text] = now
        self.last_message, self.last_message_time = text, now
        print(f"[Voice] {text}")
        if not self.enabled or self.muted:
            return True

        if interrupt and self._speech_proc is not None and self._speech_proc.poll() is None:
            try:
                self._speech_proc.terminate()
            except Exception:
                pass

        if sys.platform == "darwin" and self._say:
            self._speech_proc = subprocess.Popen(
                [self._say, "-r", str(self.voice_rate), text],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        elif sys.platform == "win32":
            # Native Windows SAPI SpeechSynthesizer via PowerShell
            clean = text.replace("'", " ").replace('"', ' ')
            ps_cmd = (
                f"Add-Type -AssemblyName System.Speech; "
                f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.Rate = 2; $s.Speak('{clean}')"
            )
            self._speech_proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        return True

    def chime(self, name: str) -> None:
        print(f"[Chime] {name}")
        if not self.enabled or self.muted:
            return

        if sys.platform == "darwin" and self._afplay:
            sound = self.CHIMES.get(name)
            if sound:
                path = f"/System/Library/Sounds/{sound}.aiff"
                if os.path.exists(path):
                    subprocess.Popen([self._afplay, path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "win32":
            import threading
            try:
                import winsound
                freq_map = {"found": 1200, "aligned": 1750, "lost": 450, "done": 1000}
                f = freq_map.get(name, 1000)
                threading.Thread(target=winsound.Beep, args=(f, 160), daemon=True).start()
            except Exception:
                pass

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        if self.muted and self._speech_proc is not None and self._speech_proc.poll() is None:
            try:
                self._speech_proc.terminate()
            except Exception:
                pass
        return self.muted

    def shutdown(self) -> None:
        if self._speech_proc is not None and self._speech_proc.poll() is None:
            try:
                self._speech_proc.terminate()
            except Exception:
                pass

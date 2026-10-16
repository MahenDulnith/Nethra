"""L1/L3 Speech Output — Offline TTS Engine via Native macOS `say`, Windows SAPI5 & pyttsx3 fallback.

Uses native macOS `say` / `afplay` on Darwin, native Windows SAPI5 (SpVoice / System.Speech) on Windows,
and pyttsx3 fallback. Non-blocking queued playback, thread-safe, 100% offline.
"""

from __future__ import annotations

import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Optional


class OfflineTtsEngine:
    """Thread-safe, non-blocking offline text-to-speech and earcon chime engine."""

    CHIMES = {"found": "Glass", "aligned": "Hero", "lost": "Basso", "done": "Purr"}

    def __init__(self, rate: int = 185, volume: float = 1.0) -> None:
        self.rate = rate
        self.volume = volume
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._stop_event = threading.Event()
        self._is_speaking = False
        self._thread: Optional[threading.Thread] = None
        self._voice: Any = None
        self._engine: Any = None
        self._say_bin = shutil.which("say") if sys.platform == "darwin" else None
        self._afplay_bin = shutil.which("afplay") if sys.platform == "darwin" else None
        self._active_proc: Optional[subprocess.Popen] = None
        self._init_engine()

    def _init_engine(self) -> None:
        """Initializes background worker thread."""
        self._thread = threading.Thread(target=self._worker, daemon=True, name="Nethra-TTS-Worker")
        self._thread.start()

    def _worker(self) -> None:
        """Background thread handling speech synthesis."""
        voice = None
        engine = None

        if platform.system() == "Windows":
            try:
                import pythoncom
                import win32com.client

                pythoncom.CoInitialize()
                voice = win32com.client.Dispatch("SAPI.SpVoice")
                voice.Rate = 1
                voice.Volume = int(min(1.0, max(0.0, self.volume)) * 100)
                self._voice = voice
                print("[OfflineTTS] Native Windows SAPI5 audio engine ready ✅")
            except Exception as exc:
                print(f"[OfflineTTS] Info: win32com SAPI5 unavailable ({exc}); using PowerShell/pyttsx3 fallback.")
                voice = None

        if voice is None and sys.platform != "darwin":
            try:
                import pyttsx3

                engine = pyttsx3.init()
                engine.setProperty("rate", self.rate)
                engine.setProperty("volume", self.volume)
                self._engine = engine
                print("[OfflineTTS] pyttsx3 audio worker ready ✅")
            except Exception:
                engine = None
        elif sys.platform == "darwin" and self._say_bin:
            print("[OfflineTTS] Native macOS `say` audio engine ready ✅")

        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if text is None:
                break

            self._is_speaking = True
            print(f'[Audio Speaking]: "{text}"')

            if sys.platform == "darwin" and self._say_bin:
                try:
                    self._active_proc = subprocess.Popen(
                        [self._say_bin, "-r", str(self.rate), text],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self._active_proc.wait()
                except Exception as exc:
                    print(f"[OfflineTTS] macOS say error: {exc}")
            elif voice is not None:
                try:
                    voice.Speak(text, 0)
                except Exception as exc:
                    print(f"[OfflineTTS] SAPI5 speech error: {exc}")
            elif engine is not None:
                try:
                    engine.say(text)
                    engine.runAndWait()
                except Exception as exc:
                    print(f"[OfflineTTS] pyttsx3 speech error: {exc}")
            elif sys.platform == "win32":
                clean = text.replace("'", " ").replace('"', " ")
                ps_cmd = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$s.Rate = 2; $s.Speak('{clean}')"
                )
                try:
                    self._active_proc = subprocess.Popen(
                        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self._active_proc.wait()
                except Exception:
                    pass
            else:
                time.sleep(0.2)

            self._is_speaking = False
            self._queue.task_done()

    def speak(self, text: str, interrupt: bool = False) -> None:
        """Enqueues text for spoken output."""
        if not text or not text.strip():
            return

        if interrupt:
            self.stop()

        self._queue.put(text.strip())

    def chime(self, kind: str) -> None:
        """Plays a short non-blocking earcon chime ('found' | 'aligned' | 'lost' | 'done')."""
        if sys.platform == "darwin" and self._afplay_bin:
            sound = f"/System/Library/Sounds/{self.CHIMES.get(kind, 'Tink')}.aiff"
            if os.path.exists(sound):
                subprocess.Popen(
                    [self._afplay_bin, sound],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        elif sys.platform == "win32":
            try:
                import winsound

                freq_map = {"found": 880, "aligned": 1320, "lost": 330, "done": 1046}
                freq = freq_map.get(kind, 700)
                threading.Thread(target=winsound.Beep, args=(freq, 160), daemon=True).start()
            except Exception:
                pass

    def stop(self) -> None:
        """Clears all pending speech in the queue and terminates current utterance immediately."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

        if self._active_proc is not None and self._active_proc.poll() is None:
            try:
                self._active_proc.terminate()
            except Exception:
                pass
        if self._voice is not None:
            try:
                self._voice.Speak("", 3)
            except Exception:
                pass
        elif self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass

    @property
    def is_speaking(self) -> bool:
        """Returns True if the TTS engine is currently outputting audio."""
        return self._is_speaking or not self._queue.empty()

    def shutdown(self) -> None:
        """Gracefully terminates the background TTS worker."""
        self._stop_event.set()
        self.stop()
        self._queue.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

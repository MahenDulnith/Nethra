"""L1/L3 Speech Output — Offline TTS Engine via Native SAPI5 & pyttsx3 fallback.

Uses native Windows SAPI5 (SpVoice) on Windows for zero-latency, glitch-free audio,
and pyttsx3 on macOS / Linux.
Non-blocking queued playback, thread-safe, 100% offline.
"""

from __future__ import annotations

import platform
import queue
import threading
import time
from typing import Any, Optional


class OfflineTtsEngine:
    """Thread-safe, non-blocking offline text-to-speech engine."""

    def __init__(self, rate: int = 180, volume: float = 1.0) -> None:
        self.rate = rate
        self.volume = volume
        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._stop_event = threading.Event()
        self._is_speaking = False
        self._thread: Optional[threading.Thread] = None
        self._voice: Any = None
        self._engine: Any = None
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
                # Map rate to SAPI scale (-10 to 10; 1 is ~180 wpm)
                voice.Rate = 1
                voice.Volume = int(min(1.0, max(0.0, self.volume)) * 100)
                self._voice = voice
                print("[OfflineTTS] Native Windows SAPI5 audio engine ready ✅")
            except Exception as exc:
                print(f"[OfflineTTS] Warning: Could not initialize native SAPI5: {exc}")
                voice = None

        if voice is None:
            try:
                import pyttsx3

                engine = pyttsx3.init()
                engine.setProperty("rate", self.rate)
                engine.setProperty("volume", self.volume)
                self._engine = engine
                print("[OfflineTTS] pyttsx3 audio worker ready ✅")
            except Exception as exc:
                print(f"[OfflineTTS] Warning: Could not initialize pyttsx3: {exc}")
                engine = None

        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if text is None:
                break

            self._is_speaking = True
            print(f"[Audio Speaking]: \"{text}\"")

            if voice is not None:
                try:
                    # Synchronous in background worker: plays aloud immediately without blocking camera pipeline
                    voice.Speak(text, 0)
                except Exception as exc:
                    print(f"[OfflineTTS] SAPI5 speech error: {exc}")
            elif engine is not None:
                try:
                    engine.say(text)
                    engine.runAndWait()
                except Exception as exc:
                    print(f"[OfflineTTS] pyttsx3 speech error: {exc}")
            else:
                time.sleep(0.5)

            self._is_speaking = False
            self._queue.task_done()

    def speak(self, text: str, interrupt: bool = False) -> None:
        """Enqueues text for spoken output.

        If interrupt is True, flushes any queued speech and halts active playback immediately.
        """
        if not text or not text.strip():
            return

        if interrupt:
            self.stop()

        self._queue.put(text.strip())

    def stop(self) -> None:
        """Clears all pending speech in the queue and terminates current utterance immediately."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

        if self._voice is not None:
            try:
                # SVSFPurgeBeforeSpeak | SVSFlagsAsync = 3
                # Instantly stops ongoing speech hardware output
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
        self._queue.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

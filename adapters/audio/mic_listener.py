"""L1 Non-Blocking Push-to-Talk Microphone & Speech-to-Text (STT) Adapter.

Captures a short audio window in a background thread when triggered by the user
(e.g., pressing [V] or [Space]) so the 30 FPS YOLO safety pipeline never blocks.

Supports:
1. `sounddevice` + `speech_recognition` (cross-platform macOS & Windows, no PyAudio needed).
2. macOS `ffmpeg` AVFoundation audio capture fallback.
3. Windows offline `.NET System.Speech.Recognition.SpeechRecognitionEngine` fallback.
4. Direct text injection (`inject_transcript`) for unit tests and CLI simulation.
"""

from __future__ import annotations

import io
import platform
import shutil
import subprocess
import tempfile
import threading
import warnings
import wave
from pathlib import Path
from typing import Optional

import numpy as np

warnings.filterwarnings("ignore", category=DeprecationWarning, module="speech_recognition")


class PushToTalkListener:
    """Thread-safe asynchronous Push-to-Talk microphone listener."""

    def __init__(
        self,
        listen_seconds: float = 3.2,
        sample_rate: int = 16000,
    ) -> None:
        self.listen_seconds = listen_seconds
        self.sample_rate = sample_rate
        self.system = platform.system()

        self._lock = threading.Lock()
        self._listening = False
        self._pending_transcript: Optional[str] = None
        self._pending_error: Optional[str] = None
        self._worker_thread: Optional[threading.Thread] = None

        self.backend = self._detect_backend()
        print(f"[VoiceMic] Push-to-Talk STT backend ready: {self.backend}")

    def _detect_backend(self) -> str:
        has_sr = False
        has_sd = False
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                import speech_recognition  # noqa: F401

            has_sr = True
        except Exception:
            pass

        try:
            import sounddevice  # noqa: F401

            has_sd = True
        except Exception:
            pass

        if has_sr and has_sd:
            return "sounddevice+speech_recognition"
        if has_sr and self.system == "Darwin" and shutil.which("ffmpeg"):
            return "ffmpeg+speech_recognition"
        if self.system == "Windows":
            return "windows-sapi-stt"
        if has_sr:
            return "speech_recognition"
        return "none"

    @property
    def is_listening(self) -> bool:
        with self._lock:
            return self._listening

    def inject_transcript(self, text: str) -> None:
        """Directly injects a transcript string (used by unit tests or CLI simulation)."""
        with self._lock:
            self._pending_transcript = text.strip()
            self._listening = False

    def pop_result(self) -> tuple[Optional[str], Optional[str]]:
        """Returns (transcript, error_msg) if a Push-to-Talk session has completed, else (None, None)."""
        with self._lock:
            transcript = self._pending_transcript
            err = self._pending_error
            self._pending_transcript = None
            self._pending_error = None
            return transcript, err

    def start_listening(self) -> bool:
        """Triggers a non-blocking background microphone capture for `listen_seconds`."""
        with self._lock:
            if self._listening:
                return False
            self._listening = True
            self._pending_transcript = None
            self._pending_error = None

        self._worker_thread = threading.Thread(
            target=self._capture_and_transcribe_worker,
            daemon=True,
        )
        self._worker_thread.start()
        return True

    def _capture_and_transcribe_worker(self) -> None:
        transcript: Optional[str] = None
        error_msg: Optional[str] = None

        try:
            if self.backend == "sounddevice+speech_recognition":
                transcript = self._record_sounddevice_and_recognize()
            elif self.backend == "ffmpeg+speech_recognition":
                transcript = self._record_ffmpeg_and_recognize()
            elif self.backend == "windows-sapi-stt":
                transcript = self._recognize_windows_sapi()
            else:
                error_msg = "Microphone STT library not available."
        except Exception as exc:
            error_msg = str(exc)

        with self._lock:
            self._listening = False
            if transcript:
                self._pending_transcript = transcript.strip()
            else:
                self._pending_error = error_msg or "Could not hear a clear command."

    def _record_sounddevice_and_recognize(self) -> Optional[str]:
        import sounddevice as sd
        import speech_recognition as sr

        num_frames = int(self.listen_seconds * self.sample_rate)
        recording = sd.rec(
            num_frames,
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()

        # Convert int16 numpy buffer to WAV PCM bytes in memory
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit PCM = 2 bytes
            wf.setframerate(self.sample_rate)
            wf.writeframes(np.ascontiguousarray(recording).tobytes())

        wav_bytes = wav_io.getvalue()
        recognizer = sr.Recognizer()
        with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
            audio_data = recognizer.record(source)

        try:
            return str(recognizer.recognize_google(audio_data, language="en-US"))
        except sr.UnknownValueError:
            if self.system == "Windows":
                return self._recognize_windows_sapi()
            return None
        except sr.RequestError:
            # Offline fallback on Windows SAPI if internet is disconnected
            if self.system == "Windows":
                return self._recognize_windows_sapi()
            raise RuntimeError("Speech recognition service offline.")

    def _record_ffmpeg_and_recognize(self) -> Optional[str]:
        import speech_recognition as sr

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "avfoundation",
                    "-i",
                    ":0",
                    "-t",
                    str(self.listen_seconds),
                    "-ar",
                    str(self.sample_rate),
                    "-ac",
                    "1",
                    str(tmp_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=self.listen_seconds + 3.0,
                check=False,
            )
            if not tmp_path.exists() or tmp_path.stat().st_size < 1000:
                return None

            recognizer = sr.Recognizer()
            with sr.AudioFile(str(tmp_path)) as source:
                audio_data = recognizer.record(source)
            try:
                return str(recognizer.recognize_google(audio_data, language="en-US"))
            except sr.UnknownValueError:
                return None
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _recognize_windows_sapi(self) -> Optional[str]:
        """Offline Windows .NET System.Speech.Recognition fallback."""
        ps_script = (
            "Add-Type -AssemblyName System.Speech; "
            "$rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine; "
            "$choices = New-Object System.Speech.Recognition.Choices; "
            "$choices.Add(@("
            "'find the door', 'find door', 'find a bottle', 'find my bottle', "
            "'find a chair', 'find the bed', 'find my laptop', 'find my phone', "
            "'find a person', 'find table', 'find wardrobe', 'find bag', "
            "'where am i', 'what room is this', 'what do you see', "
            "'what is in front of me', 'describe the room', 'stop', 'cancel'"
            ")); "
            "$gb = New-Object System.Speech.Recognition.GrammarBuilder($choices); "
            "$g = New-Object System.Speech.Recognition.Grammar($gb); "
            "$rec.LoadGrammar($g); "
            "$rec.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar)); "
            "$rec.SetInputToDefaultAudioDevice(); "
            "$res = $rec.Recognize([TimeSpan]::FromSeconds(3)); "
            "if ($res) { Write-Output $res.Text }"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
        out = (res.stdout or "").strip()
        return out if out else None

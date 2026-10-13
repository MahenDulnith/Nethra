"""L1 Android Camera Adapter for Windows & Linux (USB ADB Stream, DroidCam, IP Webcam)."""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional, Tuple, Union

import cv2
import numpy as np

from adapters.camera.base import CameraSource, ThreadedFrameGrabber
from adapters.clock.monotonic_clock import MonotonicClock
from contracts.frame import SourceId


def try_setup_adb_port_forward(local_port: int = 8080, remote_port: int = 8080) -> bool:
    """Checks if `adb` is in PATH and forward ports if an Android device is plugged in via USB."""
    if not shutil.which("adb"):
        return False
    try:
        devices_out = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=2).stdout
        lines = [line.strip() for line in devices_out.splitlines() if line.strip() and not line.startswith("List of")]
        if not lines:
            return False
        # Forward TCP port
        subprocess.run(
            ["adb", "forward", f"tcp:{local_port}", f"tcp:{remote_port}"],
            capture_output=True,
            timeout=2,
            check=True,
        )
        print(f"[AndroidCamera] ADB USB forwarding established (tcp:{local_port} -> tcp:{remote_port}) ✅")
        return True
    except Exception as exc:
        print(f"[AndroidCamera] ADB auto-forwarding attempt: {exc}")
        return False


class AndroidCameraSource(CameraSource):
    """Streams from Android phone over USB (ADB port forwarding / DroidCam) or Wi-Fi.

    Uses `ThreadedFrameGrabber` to eliminate OpenCV internal FIFO buffering lag.
    """

    def __init__(
        self,
        stream_url: str = "http://127.0.0.1:8080/video",
        fallback_index: Optional[int] = 1,
        width: int = 640,
        height: int = 480,
        fov_area_scale: float = 0.65,
        bufferless: bool = True,
        auto_adb_forward: bool = True,
        is_usb: bool = True,
    ) -> None:
        source_id = SourceId.ANDROID_USB if is_usb else SourceId.ANDROID_IP
        super().__init__(
            name="Android Phone Camera (USB / DroidCam)" if is_usb else "Android IP Camera (Wi-Fi)",
            source_id=source_id,
            width=width,
            height=height,
            fov_area_scale=fov_area_scale,
        )
        self.stream_url = stream_url
        self.fallback_index = fallback_index
        self.bufferless = bufferless
        self.auto_adb_forward = auto_adb_forward
        self.cap: Optional[cv2.VideoCapture] = None
        self.grabber: Optional[ThreadedFrameGrabber] = None
        self.active_source: Union[str, int] = stream_url

    def start(self) -> bool:
        if self.auto_adb_forward and ("127.0.0.1" in self.stream_url or "localhost" in self.stream_url):
            try_setup_adb_port_forward(8080, 8080)

        # 1. Attempt stream URL
        print(f"[AndroidCamera] Connecting to stream URL: {self.stream_url}...")
        self.cap = cv2.VideoCapture(self.stream_url)
        if self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                self.active_source = self.stream_url
                self._configure_stream()
                return True
            self.cap.release()

        # 2. Attempt fallback device index (DroidCam USB virtual webcam on DirectShow)
        if self.fallback_index is not None:
            print(f"[AndroidCamera] Stream URL failed. Trying device index #{self.fallback_index} (DroidCam USB)...")
            self.cap = cv2.VideoCapture(self.fallback_index)
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    self.active_source = self.fallback_index
                    self._configure_stream()
                    return True
                self.cap.release()

        print("[AndroidCamera Error] Could not connect to Android stream or USB fallback camera.")
        return False

    def _configure_stream(self) -> None:
        assert self.cap is not None
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.is_opened = True

        if self.bufferless:
            print("[AndroidCamera] Starting bufferless threaded frame grabber (<15ms latency)...")
            self.grabber = ThreadedFrameGrabber(self.cap)
            self.grabber.start()

        print(f"[AndroidCamera] Connected successfully to {self.active_source} (FOV scale: {self.fov_area_scale}x).")

    def read(self) -> Tuple[bool, Optional[np.ndarray], int]:
        if not self.is_opened or self.cap is None:
            return False, None, 0

        if self.grabber is not None:
            return self.grabber.read_latest()

        ret, frame = self.cap.read()
        ts = MonotonicClock.now_ns()
        if not ret or frame is None:
            return False, None, ts
        return True, frame, ts

    def release(self) -> None:
        if self.grabber is not None:
            self.grabber.stop()
            self.grabber = None
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_opened = False

"""L1 Camera Factory — Loads config/camera.yaml and instantiates CameraSource."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from adapters.camera.android_camera import AndroidCameraSource
from adapters.camera.base import CameraSource
from adapters.camera.continuity_camera import ContinuityCameraSource
from adapters.camera.file_camera import FileCameraSource
from adapters.camera.mock_camera import MockCameraSource
from adapters.camera.uvc_camera import UvcCameraSource


class CameraFactory:
    """Factory creating configured CameraSource instances based on config/camera.yaml and CLI overrides."""

    @staticmethod
    def load_config(config_path: str = "config/camera.yaml") -> Dict[str, Any]:
        path = Path(config_path)
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @classmethod
    def create(
        cls,
        profile_name: Optional[str] = None,
        config_path: str = "config/camera.yaml",
        cli_overrides: Optional[Dict[str, Any]] = None,
    ) -> CameraSource:
        config = cls.load_config(config_path)
        profiles = config.get("profiles", {})

        # Resolve auto profile based on operating system
        if not profile_name or profile_name == "auto":
            if platform.system() == "Darwin":
                profile_name = "iphone_continuity"
            else:
                profile_name = "android_usb"

        profile_cfg = profiles.get(profile_name, {})
        if cli_overrides:
            profile_cfg.update(cli_overrides)

        source_type = profile_cfg.get("source_type", "mock")
        width = int(profile_cfg.get("width", 640))
        height = int(profile_cfg.get("height", 480))
        fov_area_scale = float(profile_cfg.get("fov_area_scale", 1.0))

        if source_type == "continuity":
            return ContinuityCameraSource(
                device_index=int(profile_cfg.get("device_index", 1)),
                width=width,
                height=height,
                fov_area_scale=fov_area_scale,
            )
        elif source_type in ("android_usb", "android_ip"):
            return AndroidCameraSource(
                stream_url=str(profile_cfg.get("stream_url", "http://127.0.0.1:8080/video")),
                fallback_index=profile_cfg.get("fallback_index", 1),
                width=width,
                height=height,
                fov_area_scale=fov_area_scale,
                bufferless=bool(profile_cfg.get("bufferless", True)),
                auto_adb_forward=bool(profile_cfg.get("auto_adb_forward", True)),
                is_usb=(source_type == "android_usb"),
            )
        elif source_type == "uvc":
            return UvcCameraSource(
                device_index=int(profile_cfg.get("device_index", 0)),
                width=width,
                height=height,
                fov_area_scale=fov_area_scale,
            )
        elif source_type == "file":
            return FileCameraSource(
                file_path=str(profile_cfg.get("file_path", "harness/fixtures/street/sample_walk.mp4")),
                width=width,
                height=height,
                fps=float(profile_cfg.get("fps", 30.0)),
                fov_area_scale=fov_area_scale,
            )
        else:
            return MockCameraSource(
                width=width,
                height=height,
                fov_area_scale=fov_area_scale,
            )

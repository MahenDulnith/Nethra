"""L1 Camera Hardware Abstraction Layer Package."""

from adapters.camera.android_camera import AndroidCameraSource
from adapters.camera.base import CameraSource, ThreadedFrameGrabber, get_camera_name, open_camera
from adapters.camera.continuity_camera import ContinuityCameraSource
from adapters.camera.factory import CameraFactory
from adapters.camera.file_camera import FileCameraSource
from adapters.camera.mock_camera import MockCameraSource, create_mock_frame
from adapters.camera.uvc_camera import UvcCameraSource

__all__ = [
    "CameraSource",
    "ThreadedFrameGrabber",
    "ContinuityCameraSource",
    "AndroidCameraSource",
    "UvcCameraSource",
    "FileCameraSource",
    "MockCameraSource",
    "CameraFactory",
    "get_camera_name",
    "open_camera",
    "create_mock_frame",
]

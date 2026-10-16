"""Unit tests for Nethra L1 Camera Hardware Abstraction Layer."""

import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from adapters.camera.base import CameraSource, ThreadedFrameGrabber, get_camera_name
from adapters.camera.factory import CameraFactory
from adapters.camera.mock_camera import MockCameraSource, create_mock_frame
from contracts.frame import SourceId
from main import parse_arguments, resolve_camera_source
from services.safety.spatial_router import SpatialRoutingEngine


class TestCameraAdapters(unittest.TestCase):

    def test_camera_yaml_profiles_loadable(self) -> None:
        """Verifies all profiles defined in config/camera.yaml are loadable."""
        config = CameraFactory.load_config("config/camera.yaml")
        self.assertIn("profiles", config)
        profiles = config["profiles"]
        self.assertIn("iphone_continuity", profiles)
        self.assertIn("android_usb", profiles)
        self.assertIn("android_ip", profiles)
        self.assertIn("uvc_webcam", profiles)
        self.assertIn("synthetic_mock", profiles)
        self.assertIn("file_replay", profiles)

    def test_mock_camera_source_lifecycle(self) -> None:
        """Verifies MockCameraSource start, read, frame dimensions, and typed FrameData."""
        cam = CameraFactory.create("synthetic_mock")
        self.assertIsInstance(cam, MockCameraSource)
        self.assertEqual(cam.source_id, SourceId.MOCK)
        self.assertEqual(cam.fov_area_scale, 1.0)

        started = cam.start()
        self.assertTrue(started)
        self.assertTrue(cam.is_opened)

        ret, frame, ts = cam.read()
        self.assertTrue(ret)
        self.assertIsNotNone(frame)
        assert frame is not None
        self.assertEqual(frame.shape, (480, 640, 3))
        self.assertGreater(ts, 0)

        # Test typed FrameData contract
        frame_data = cam.read_frame_data()
        self.assertIsNotNone(frame_data)
        assert frame_data is not None
        self.assertEqual(frame_data.width, 640)
        self.assertEqual(frame_data.height, 480)
        self.assertEqual(frame_data.source_id, SourceId.MOCK)

        cam.release()
        self.assertFalse(cam.is_opened)

    def test_factory_profile_instantiation(self) -> None:
        """Verifies each profile generates the appropriate adapter subclass."""
        mock_cam = CameraFactory.create("synthetic_mock")
        self.assertEqual(mock_cam.name, "Synthetic Mock Stream")

        android_usb = CameraFactory.create("android_usb")
        self.assertEqual(android_usb.source_id, SourceId.ANDROID_USB)
        self.assertAlmostEqual(android_usb.fov_area_scale, 0.65)

        android_ip = CameraFactory.create("android_ip")
        self.assertEqual(android_ip.source_id, SourceId.ANDROID_IP)

        uvc_cam = CameraFactory.create("uvc_webcam")
        self.assertEqual(uvc_cam.source_id, SourceId.WEBCAM)
        self.assertAlmostEqual(uvc_cam.fov_area_scale, 0.85)

        iphone_cam = CameraFactory.create("iphone_continuity")
        self.assertEqual(iphone_cam.source_id, SourceId.IPHONE)
        self.assertAlmostEqual(iphone_cam.fov_area_scale, 1.0)

    def test_threaded_frame_grabber(self) -> None:
        """Verifies ThreadedFrameGrabber continuously retrieves frames and eliminates buffer lag."""
        mock_cap = MagicMock()
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cap.isOpened.return_value = True
        mock_cap.grab.return_value = True
        mock_cap.retrieve.return_value = (True, dummy_frame)

        grabber = ThreadedFrameGrabber(mock_cap)
        grabber.start()

        import time
        time.sleep(0.05)

        ret, frame, ts = grabber.read_latest()
        self.assertTrue(ret)
        self.assertIsNotNone(frame)
        self.assertGreater(ts, 0)

        grabber.stop()
        self.assertFalse(grabber.running)

    def test_fov_area_scaling_in_spatial_router(self) -> None:
        """Verifies that an Android phone with 0.65x scale produces scaled PWM intensity."""
        # Baseline iPhone router (1.0x scale)
        iphone_router = SpatialRoutingEngine(min_area_ratio=0.02, max_area_ratio=0.35, fov_area_scale=1.0)
        # Android router (0.65x scale)
        android_router = SpatialRoutingEngine(min_area_ratio=0.02, max_area_ratio=0.35, fov_area_scale=0.65)

        area_ratio = 0.20
        iphone_pwm = iphone_router.calculate_pwm(area_ratio)
        android_pwm = android_router.calculate_pwm(area_ratio)

        # Android 1x lens sees objects larger at same distance, so fov_area_scale scales it down to match Ultra-Wide
        self.assertGreater(iphone_pwm, android_pwm)

    def test_resolve_camera_source_cli(self) -> None:
        """Verifies main.py argument resolver picks the correct camera adapter."""
        with patch("sys.argv", ["main.py", "--mock"]):
            args = parse_arguments()
            cam = resolve_camera_source(args)
            self.assertEqual(cam.source_id, SourceId.MOCK)

        with patch("sys.argv", ["main.py", "--camera-url", "http://127.0.0.1:8080/video"]):
            args = parse_arguments()
            cam = resolve_camera_source(args)
            self.assertEqual(cam.source_id, SourceId.ANDROID_USB)


if __name__ == "__main__":
    unittest.main()

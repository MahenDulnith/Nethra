"""Root test runner for Nethra (`python test_spatial.py`)."""

import unittest

from tests.test_camera_adapters import TestCameraAdapters
from tests.test_mahendulnith_parity import TestMahenDulnithParityAndReadiness
from tests.test_safety_engine_and_arbiter import (
    TestHygieneAndSafetyEngine,
    TestRuleArbiter,
)
from tests.test_spatial_routing import TestContextSceneTracker, TestSpatialRouting

__all__ = [
    "TestSpatialRouting",
    "TestContextSceneTracker",
    "TestMahenDulnithParityAndReadiness",
    "TestCameraAdapters",
    "TestHygieneAndSafetyEngine",
    "TestRuleArbiter",
]

if __name__ == "__main__":
    unittest.main()

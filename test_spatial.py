"""Root unit & parity test runner for Nethra (`python test_spatial.py`)."""

import unittest

from tests.test_mahendulnith_parity import TestMahenDulnithParityAndReadiness
from tests.test_spatial_routing import TestContextSceneTracker, TestSpatialRouting

__all__ = [
    "TestSpatialRouting",
    "TestContextSceneTracker",
    "TestMahenDulnithParityAndReadiness",
]

if __name__ == "__main__":
    unittest.main()

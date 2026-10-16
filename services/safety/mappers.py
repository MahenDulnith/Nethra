"""L2 Direction and Distance Bucket Mappers."""

from __future__ import annotations

from typing import Tuple

from contracts.safety_alert import DirectionSector, DistanceBucket


class DirectionMapper:
    """Maps bounding box center x-coordinate to one of five direction sectors."""

    @staticmethod
    def map_sector(center_x: float, frame_width: int) -> DirectionSector:
        col = frame_width / 5.0
        if center_x < col:
            return DirectionSector.LEFT
        elif center_x < col * 2:
            return DirectionSector.CENTRE_LEFT
        elif center_x < col * 3:
            return DirectionSector.CENTRE
        elif center_x < col * 4:
            return DirectionSector.CENTRE_RIGHT
        else:
            return DirectionSector.RIGHT

    @staticmethod
    def map_clock(center_x: float, frame_width: int) -> str:
        """Returns clock-face position string (e.g. '12 o\'clock', '1 o\'clock')."""
        sector = DirectionMapper.map_sector(center_x, frame_width)
        return sector.clock_face


class BucketMapper:
    """Maps bounding-box area ratio to calibrated distance buckets."""

    def __init__(
        self,
        immediate_ratio: float = 0.45,
        near_ratio: float = 0.22,
        mid_ratio: float = 0.08,
    ) -> None:
        self.immediate_ratio = immediate_ratio
        self.near_ratio = near_ratio
        self.mid_ratio = mid_ratio

    def map_bucket(self, area_ratio: float) -> DistanceBucket:
        if area_ratio >= self.immediate_ratio:
            return DistanceBucket.IMMEDIATE
        elif area_ratio >= self.near_ratio:
            return DistanceBucket.NEAR
        elif area_ratio >= self.mid_ratio:
            return DistanceBucket.MID
        elif area_ratio > 0.0:
            return DistanceBucket.FAR
        return DistanceBucket.UNKNOWN

"""Typed authoring model used by SpatialEngine before indoor_model export."""

from .history import SnapshotHistory
from .model import (
    AuthoringAreaElement,
    AuthoringLineElement,
    BuildingAuthoringState,
    ConnectorEndpoint,
    DetectedSpace,
    LevelAuthoringState,
    VerticalConnector,
    VirtualBoundary,
)
from .space_detection import detect_all_levels, detect_spaces

__all__ = [
    "AuthoringAreaElement",
    "AuthoringLineElement",
    "BuildingAuthoringState",
    "ConnectorEndpoint",
    "DetectedSpace",
    "LevelAuthoringState",
    "SnapshotHistory",
    "VerticalConnector",
    "VirtualBoundary",
    "detect_all_levels",
    "detect_spaces",
]

"""Validate geographic coordinates before saving or centering a map."""

from math import isfinite


def parse_coordinate(value: object, limit: float) -> float:
    """Return a finite coordinate within its inclusive geographic bounds."""
    try:
        coordinate = float(str(value).strip())
    except (ValueError, TypeError, OverflowError):
        raise ValueError("Invalid coordinate") from None
    if not isfinite(coordinate) or not -limit <= coordinate <= limit:
        raise ValueError("Coordinate outside geographic bounds")
    return coordinate


def map_center(latitude: object, longitude: object) -> tuple[float, float]:
    """Use a safe default center when either coordinate is invalid."""
    try:
        return parse_coordinate(latitude, 90), parse_coordinate(longitude, 180)
    except ValueError:
        return 46.5, 2.5

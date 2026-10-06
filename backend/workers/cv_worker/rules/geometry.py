"""Planar geometry helpers for polygon zones.

Zones are stored as an ordered list of vertices. Two coordinate conventions are
supported:

* normalized ``[0, 1]`` vertices, which are resolution independent and are the
  convention the API persists by default;
* pixel vertices, which are what detection bounding boxes arrive in.

:meth:`Polygon.from_vertices` plus :meth:`Polygon.to_pixels` convert between
them so the rule engine never has to care which one a zone was authored in.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

Point = tuple[float, float]


class InvalidPolygonError(ValueError):
    """Raised when a polygon cannot be used for containment tests."""


@dataclass(frozen=True)
class Polygon:
    """An ordered, implicitly closed ring of vertices.

    Vertices may repeat the first point at the end; that is tolerated and
    de-duplicated by :meth:`from_vertices`.
    """

    vertices: tuple[Point, ...]

    def __post_init__(self) -> None:
        if len(self.vertices) < 3:
            raise InvalidPolygonError(
                f"polygon needs at least 3 distinct vertices, got {len(self.vertices)}"
            )

    @classmethod
    def from_vertices(cls, vertices: Iterable[Sequence[float]]) -> Polygon:
        points = [(float(v[0]), float(v[1])) for v in vertices]

        if len(points) > 1 and _almost_equal(points[0], points[-1]):
            points = points[:-1]

        if len(points) < 3:
            raise InvalidPolygonError(
                f"polygon needs at least 3 distinct vertices, got {len(points)}"
            )
        if abs(cls.signed_area(points)) < 1e-9:
            raise InvalidPolygonError("polygon is degenerate (zero area)")

        return cls(tuple(points))

    @classmethod
    def from_normalized(
        cls, vertices: Iterable[Sequence[float]], width: int, height: int
    ) -> Polygon:
        """Build a pixel-space polygon from normalized ``[0, 1]`` vertices."""
        scaled = [(float(v[0]) * width, float(v[1]) * height) for v in vertices]
        return cls.from_vertices(scaled)

    @classmethod
    def from_bbox(cls, x1: float, y1: float, x2: float, y2: float) -> Polygon:
        """Axis-aligned rectangle, mostly for tests and simple admin setup."""
        return cls.from_vertices([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])

    def to_normalized(self, width: int, height: int) -> Polygon:
        if width <= 0 or height <= 0:
            raise InvalidPolygonError(
                f"frame size must be positive, got {width}x{height}"
            )
        return Polygon.from_vertices(
            [(x / width, y / height) for x, y in self.vertices]
        )

    def to_pixels(self, width: int, height: int) -> Polygon:
        """Scale a normalized polygon up to a concrete frame size."""
        if width <= 0 or height <= 0:
            raise InvalidPolygonError(
                f"frame size must be positive, got {width}x{height}"
            )
        return Polygon.from_vertices(
            [(x * width, y * height) for x, y in self.vertices]
        )

    def scaled_about_centroid(self, factor: float) -> Polygon:
        """Scale the ring towards its centroid.

        ``factor < 1`` shrinks the zone, ``factor > 1`` expands it. This is the
        basis of boundary hysteresis: a track must reach the expanded ring to be
        considered inside, and must clear the shrunken ring to be considered
        outside, so a subject hovering on the boundary does not flicker.
        """
        if factor <= 0:
            raise InvalidPolygonError(f"scale factor must be positive, got {factor}")

        cx, cy = self.centroid
        moved = [
            (cx + (x - cx) * factor, cy + (y - cy) * factor) for x, y in self.vertices
        ]
        return Polygon(tuple(moved))

    @property
    def centroid(self) -> Point:
        return self.area_centroid()

    @property
    def area(self) -> float:
        return abs(self.signed_area(self.vertices))

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        return (min(xs), min(ys), max(xs), max(ys))

    def contains(self, point: Point) -> bool:
        """Ray-casting point-in-polygon test.

        Uses an even-odd crossing count, which is correct for concave polygons
        (an L-shaped zone does not swallow the notch outside it).
        """
        x, y = point
        inside = False
        vertices = self.vertices
        n = len(vertices)

        for i in range(n):
            xi, yi = vertices[i]
            xj, yj = vertices[(i + 1) % n]
            if (yi > y) != (yj > y):
                x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
                if x < x_cross:
                    inside = not inside

        return inside

    def area_centroid(self) -> Point:
        """Area-weighted centroid via the shoelace formula.

        The area centroid is preferred over the average of the vertices because
        it stays inside L-shaped and other concave zones, which makes it a
        reliable anchor for symmetric hysteresis scaling.
        """
        vertices = self.vertices
        area = self.signed_area(vertices)
        n = len(vertices)

        if abs(area) < 1e-9:
            xs = [v[0] for v in vertices]
            ys = [v[1] for v in vertices]
            return (sum(xs) / n, sum(ys) / n)

        cx = cy = 0.0
        for i in range(n):
            xi, yi = vertices[i]
            xj, yj = vertices[(i + 1) % n]
            cross = xi * yj - xj * yi
            cx += (xi + xj) * cross
            cy += (yi + yj) * cross

        return (cx / (6.0 * area), cy / (6.0 * area))

    @staticmethod
    def signed_area(vertices: Sequence[Point]) -> float:
        """Shoelace signed area; positive for counter-clockwise winding."""
        total = 0.0
        n = len(vertices)
        for i in range(n):
            xi, yi = vertices[i]
            xj, yj = vertices[(i + 1) % n]
            total += xi * yj - xj * yi
        return total / 2.0


def _almost_equal(a: Point, b: Point, tolerance: float = 1e-9) -> bool:
    return math.isclose(a[0], b[0], abs_tol=tolerance) and math.isclose(
        a[1], b[1], abs_tol=tolerance
    )

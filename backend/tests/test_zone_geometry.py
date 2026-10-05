import math

import pytest

from workers.cv_worker.rules.geometry import InvalidPolygonError, Polygon


class TestPolygonConstruction:
    def test_from_vertices(self):
        poly = Polygon.from_vertices([(0, 0), (100, 0), (100, 100), (0, 100)])
        assert len(poly.vertices) == 4

    def test_duplicate_closing_vertex_is_removed(self):
        poly = Polygon.from_vertices([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])
        assert len(poly.vertices) == 4

    def test_too_few_vertices_rejected(self):
        with pytest.raises(InvalidPolygonError):
            Polygon.from_vertices([(0, 0), (10, 10)])

    def test_collinear_vertices_rejected_as_degenerate(self):
        with pytest.raises(InvalidPolygonError):
            Polygon.from_vertices([(0, 0), (10, 0), (20, 0)])

    def test_from_bbox(self):
        poly = Polygon.from_bbox(10, 20, 110, 220)
        assert poly.bbox == (10.0, 20.0, 110.0, 220.0)
        assert poly.contains((50.0, 100.0))


class TestPointInPolygon:
    @pytest.fixture
    def square(self):
        return Polygon.from_bbox(0, 0, 100, 100)

    def test_point_inside(self, square):
        assert square.contains((50.0, 50.0)) is True

    def test_point_outside(self, square):
        assert square.contains((150.0, 50.0)) is False

    def test_points_just_inside_and_outside_are_correct(self, square):
        # Ray casting is deliberately not asserted on exact edge coordinates:
        # boundary membership is ambiguous under floating point. What must hold
        # is that unambiguous points are classified correctly, and the
        # hysteresis band absorbs anything ambiguous.
        assert square.contains((99.9, 50.0)) is True
        assert square.contains((100.1, 50.0)) is False

    def test_concave_polygon_excludes_notch(self):
        # An L-shape: the notch must NOT be counted as inside.
        poly = Polygon.from_vertices(
            [(0, 0), (100, 0), (100, 40), (40, 40), (40, 100), (0, 100)]
        )
        assert poly.contains((20.0, 80.0)) is True
        assert poly.contains((80.0, 80.0)) is False

    def test_clockwise_winding_same_result(self):
        ccw = Polygon.from_vertices([(0, 0), (100, 0), (100, 100), (0, 100)])
        cw = Polygon.from_vertices([(0, 100), (100, 100), (100, 0), (0, 0)])
        assert ccw.contains((50.0, 50.0)) == cw.contains((50.0, 50.0)) is True

    def test_point_above_all_edges(self, square):
        assert square.contains((50.0, -10.0)) is False

    def test_point_below_all_edges(self, square):
        assert square.contains((50.0, 150.0)) is False


class TestAreaAndCentroid:
    def test_square_area(self):
        poly = Polygon.from_bbox(0, 0, 100, 50)
        assert poly.area == pytest.approx(5000.0)

    def test_square_centroid(self):
        poly = Polygon.from_bbox(0, 0, 100, 50)
        assert poly.centroid == pytest.approx((50.0, 25.0))

    def test_concave_centroid_stays_in_shape(self):
        poly = Polygon.from_vertices(
            [(0, 0), (100, 0), (100, 40), (40, 40), (40, 100), (0, 100)]
        )
        cx, cy = poly.centroid
        assert poly.contains((cx, cy)) is True

    def test_area_independent_of_winding(self):
        ccw = Polygon.from_vertices([(0, 0), (100, 0), (100, 100), (0, 100)])
        cw = Polygon.from_vertices([(0, 100), (100, 100), (100, 0), (0, 0)])
        assert ccw.area == pytest.approx(cw.area)


class TestHysteresisScaling:
    @pytest.fixture
    def square(self):
        return Polygon.from_bbox(0, 0, 100, 100)

    def test_shrink_reduces_area(self, square):
        shrunk = square.scaled_about_centroid(0.8)
        assert shrunk.area < square.area

    def test_expand_increases_area(self, square):
        expanded = square.scaled_about_centroid(1.2)
        assert expanded.area > square.area

    def test_shrink_centroid_unchanged(self, square):
        shrunk = square.scaled_about_centroid(0.5)
        assert shrunk.centroid == pytest.approx(square.centroid)

    def test_non_positive_factor_rejected(self, square):
        with pytest.raises(InvalidPolygonError):
            square.scaled_about_centroid(0.0)

    def test_hysteresis_band_blocks_flicker(self, square):
        """A subject in the boundary band stays 'inside' until it clearly exits.

        The band is the gap between the expanded (-5..105) and shrunken (5..95)
        rings: 103 is outside the zone itself, inside the expanded ring, and
        outside the shrunken ring, so an occupant there counts as present but
        has not yet left.
        """
        expanded = square.scaled_about_centroid(1.1)
        shrunk = square.scaled_about_centroid(0.9)

        probe = (103.0, 50.0)

        assert square.contains(probe) is False
        assert expanded.contains(probe) is True
        assert shrunk.contains(probe) is False

    def test_scale_one_is_identity(self, square):
        scaled = square.scaled_about_centroid(1.0)
        assert len(scaled.vertices) == len(square.vertices)
        for got, want in zip(scaled.vertices, square.vertices):
            assert got == pytest.approx(want)


class TestCoordinateConversion:
    def test_normalized_to_pixels(self):
        poly = Polygon.from_normalized([(0.0, 0.0), (0.5, 0.0), (0.5, 0.5)], 640, 480)
        assert poly.bbox == (0.0, 0.0, 320.0, 240.0)

    def test_pixels_to_normalized_roundtrip(self):
        original = Polygon.from_bbox(64, 48, 320, 240)
        restored = original.to_normalized(640, 480).to_pixels(640, 480)
        for got, want in zip(restored.vertices, original.vertices):
            assert got == pytest.approx(want)

    def test_zero_frame_size_rejected(self):
        poly = Polygon.from_bbox(0, 0, 100, 100)
        with pytest.raises(InvalidPolygonError):
            poly.to_normalized(0, 480)

    def test_to_pixels_helper(self):
        normalized = Polygon.from_vertices([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])
        assert normalized.to_pixels(200, 100).bbox == pytest.approx(
            (0.0, 0.0, 200.0, 100.0)
        )
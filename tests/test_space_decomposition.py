import unittest

from shapely.geometry import Polygon
from shapely.ops import unary_union

from src.indoor_authoring.space_decomposition import decompose_space


class SpaceDecompositionTests(unittest.TestCase):
    def assert_decomposition_valid(self, polygon, min_parts=1, strategy="triangulation"):
        result = decompose_space(polygon, strategy=strategy)
        self.assertGreaterEqual(len(result.parts), min_parts)
        union = unary_union(result.parts)
        self.assertLessEqual(polygon.symmetric_difference(union).area, 1e-6)
        for index, left in enumerate(result.parts):
            self.assertTrue(left.is_valid)
            for right in result.parts[index + 1 :]:
                self.assertLessEqual(left.intersection(right).area, 1e-6)
        return result

    def test_l_shape(self):
        poly = Polygon([(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)])
        result = self.assert_decomposition_valid(poly, min_parts=2)
        self.assertGreaterEqual(len(result.virtual_boundaries), 1)

    def test_t_u_h_o_and_diagonal_concave_shapes(self):
        shapes = [
            Polygon([(0, 0), (3, 0), (3, 1), (2, 1), (2, 3), (1, 3), (1, 1), (0, 1)]),
            Polygon([(0, 0), (4, 0), (4, 4), (3, 4), (3, 1), (1, 1), (1, 4), (0, 4)]),
            Polygon([(0, 0), (1, 0), (1, 1), (3, 1), (3, 0), (4, 0), (4, 4), (3, 4), (3, 3), (1, 3), (1, 4), (0, 4)]),
            Polygon([(0, 0), (5, 0), (5, 5), (0, 5)], holes=[[(2, 2), (3, 2), (3, 3), (2, 3)]]),
            Polygon([(0, 0), (4, 0), (4, 1), (2, 2), (4, 4), (0, 4)]),
        ]
        for shape in shapes:
            with self.subTest(shape=shape.wkt):
                result = self.assert_decomposition_valid(shape, min_parts=2)
                self.assertGreaterEqual(len(result.virtual_boundaries), 1)

    def test_rectilinear_strategy_splits_orthogonal_l_shape(self):
        poly = Polygon([(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)])
        result = self.assert_decomposition_valid(poly, min_parts=2, strategy="rectilinear")

        self.assertEqual(result.report["strategy"], "rectilinear")
        self.assertGreaterEqual(len(result.virtual_boundaries), 1)
        for part in result.parts:
            coords = list(part.exterior.coords)
            for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
                self.assertTrue(abs(x1 - x2) <= 1e-9 or abs(y1 - y2) <= 1e-9)

    def test_none_strategy_preserves_original_polygon(self):
        poly = Polygon([(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)])
        result = self.assert_decomposition_valid(poly, min_parts=1, strategy="none")

        self.assertEqual(len(result.parts), 1)
        self.assertEqual(result.report["strategy"], "none")
        self.assertFalse(result.virtual_boundaries)


if __name__ == "__main__":
    unittest.main()

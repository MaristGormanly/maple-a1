"""Tests for raw-SQL pgvector bind serialization."""

from __future__ import annotations

import math
import unittest

from app.services.vector_serialization import to_pgvector_literal


class PgvectorLiteralTests(unittest.TestCase):
    def test_formats_numeric_sequence_as_pgvector_literal(self) -> None:
        self.assertEqual(to_pgvector_literal([0.1, -0.2, 3]), "[0.1,-0.2,3.0]")

    def test_rejects_empty_vector(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one value"):
            to_pgvector_literal([])

    def test_rejects_non_numeric_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "numeric"):
            to_pgvector_literal([0.1, "bad"])  # type: ignore[list-item]

    def test_rejects_non_finite_value(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            to_pgvector_literal([0.1, math.inf])


if __name__ == "__main__":
    unittest.main()

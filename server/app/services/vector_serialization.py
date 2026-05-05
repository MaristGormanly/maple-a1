"""Helpers for binding pgvector values through raw SQL.

The pgvector SQLAlchemy type can adapt Python lists when used through ORM
columns, but our RAG code uses ``text()`` queries.  asyncpg then sees a plain
``list[float]`` bind value and treats the placeholder as text, which fails
before PostgreSQL can apply the vector operator.  Serialising to pgvector's
literal form and casting in SQL gives raw queries an explicit, portable shape.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def to_pgvector_literal(values: Sequence[float]) -> str:
    """Return a pgvector literal, e.g. ``[0.1,-0.2,3]``.

    Raises:
        ValueError: if *values* is empty or contains non-finite/non-numeric
            elements.  Rejecting bad vectors close to the caller keeps DB
            errors clear and prevents malformed literals.
    """
    if not values:
        raise ValueError("pgvector literal requires at least one value")

    parts: list[str] = []
    for value in values:
        if not isinstance(value, (int, float)):
            raise ValueError("pgvector literal values must be numeric")
        as_float = float(value)
        if not math.isfinite(as_float):
            raise ValueError("pgvector literal values must be finite")
        parts.append(repr(as_float))

    return "[" + ",".join(parts) + "]"

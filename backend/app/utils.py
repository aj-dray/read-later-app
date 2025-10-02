from __future__ import annotations

from typing import Sequence


def vector_to_pg(vec: Sequence[float]) -> str:
    """Serialize a Python vector into pgvector text format: [v1, v2, ...]."""
    return "[" + ", ".join(str(float(v)) for v in vec) + "]"



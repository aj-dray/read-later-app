from __future__ import annotations

import re
from typing import Any, Literal, Sequence

from .. import database as db
from .embedding import embed_query
from . import cross_encoder


# === CONFIGURATION ===

SEMANTIC_SCORE_THRESHOLD = 0.35  # lighter pre-filter; rely more on reranker
SEMANTIC_FETCH_MULTIPLIER = 4    # Get more candidates for cross-encoder
CROSS_ENCODER_THRESHOLD = 0.35   # Raise to crop rankings earlier


# === SEARCH HELPERS ===


def _safe_float(value: Any) -> float:
    """Convert arbitrary values to float, returning 0.0 on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _filter_by_score(
    rows: Sequence[dict[str, Any]],
    min_score: float = SEMANTIC_SCORE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Keep rows whose semantic score meets the threshold."""
    if min_score <= 0:
        return list(rows)

    return [
        row for row in rows
        if _safe_float(row.get("score", 0)) >= min_score
    ]


async def _rank_items_from_chunks(
    rows: Sequence[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    """Pick the best chunk per item to represent each item."""
    seen: set[str] = set()
    results: list[dict[str, Any]] = []

    for row in rows:
        item_id = str(row.get("item_id"))
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)

        # Build result with preview from chunk content
        result = {
            "id": item_id,
            "preview": row.get("content_text"),
        }

        # Include other fields if present
        for key in ["title", "summary", "score", "distance", "url"]:
            if key in row and row[key] is not None:
                result[key] = row[key]

        results.append(result)
        if len(results) >= limit:
            break

    return results


async def lexical(
    *,
    user_id: str,
    query: str,
    mode: Literal["lexical", "semantic"] = "lexical",
    scope: Literal["items", "chunks"],
    limit: int,
    columns: Sequence[str] | None,
) -> list[dict[str, Any]]:
    """Simple lexical search over items or chunks."""
    if scope == "items":
        return await db.lexical_search_items(
            user_id=user_id,
            query_text=query,
            columns=columns,
            limit=limit,
        )

    # scope == "chunks" - search chunks then rank items
    chunk_rows = await db.lexical_search_chunks(
        user_id=user_id,
        query_text=query,
        columns=columns,
        limit=limit * 5,  # fetch extra to ensure enough unique items
    )
    return await _rank_items_from_chunks(chunk_rows, limit)


async def semantic(
    *,
    user_id: str,
    query: str,
    mode: Literal["lexical", "semantic"] = "semantic",
    scope: Literal["items", "chunks"],
    limit: int,
    columns: Sequence[str] | None,
) -> list[dict[str, Any]]:
    """Simplified semantic search with embedding + score filter + lexical fallback."""

    # Get query embedding
    query_vec = await embed_query(query)
    fetch_limit = limit * SEMANTIC_FETCH_MULTIPLIER

    if scope == "items":
        # 1. Semantic search on items (get more candidates)
        # Ensure we retrieve enough text for cross-encoder to judge relevance
        required_cols = {"id", "title", "summary", "content_text"}
        cols = list(required_cols if columns is None else (set(columns) | required_cols))
        rows = await db.semantic_search_items(
            user_id=user_id,
            query_vector=query_vec,
            columns=cols,
            limit=fetch_limit,
        )

        # 2. Light semantic score filter
        semantic_filtered = _filter_by_score(rows)

        # 3. Cross-encoder relevance filtering and reranking
        cross_encoder_filtered = await cross_encoder.filter_by_relevance(
            query=query,
            candidates=semantic_filtered,
            threshold=CROSS_ENCODER_THRESHOLD,
            user_id=user_id,
        )

        # 4. If we have enough good results, return them
        if len(cross_encoder_filtered) >= limit:
            return cross_encoder_filtered[:limit]

        # 5. Lexical fallback for remaining slots
        remaining = limit - len(cross_encoder_filtered)
        lexical_rows = await db.lexical_search_items(
            user_id=user_id,
            query_text=query,
            columns=cols,
            limit=remaining,
        )

        # Combine results, avoiding duplicates
        seen_ids = {str(row.get("id")) for row in cross_encoder_filtered}
        for row in lexical_rows:
            item_id = str(row.get("id"))
            if item_id not in seen_ids:
                cross_encoder_filtered.append(row)
                seen_ids.add(item_id)
                if len(cross_encoder_filtered) >= limit:
                    break

        return cross_encoder_filtered[:limit]

    else:  # scope == "chunks"
        # 1. Semantic search on chunks (get more candidates)
        chunk_rows = await db.semantic_search_chunks(
            user_id=user_id,
            query_vector=query_vec,
            columns=columns,
            limit=fetch_limit * 3,
        )

        # 2. Light semantic score filter and rank items
        semantic_filtered_chunks = _filter_by_score(chunk_rows)
        ranked_items = await _rank_items_from_chunks(semantic_filtered_chunks, fetch_limit)

        # 3. Cross-encoder relevance filtering and reranking
        cross_encoder_filtered = await cross_encoder.filter_by_relevance(
            query=query,
            candidates=ranked_items,
            threshold=CROSS_ENCODER_THRESHOLD,
            user_id=user_id,
        )

        # 4. If we have enough good results, return them
        if len(cross_encoder_filtered) >= limit:
            return cross_encoder_filtered[:limit]

        # 5. Lexical fallback for remaining slots
        remaining = limit - len(cross_encoder_filtered)
        lexical_chunk_rows = await db.lexical_search_chunks(
            user_id=user_id,
            query_text=query,
            columns=columns,
            limit=remaining * 3,
        )

        lexical_ranked = await _rank_items_from_chunks(lexical_chunk_rows, remaining)
        # Apply cross-encoder reranking to lexical fallbacks for better ordering/inspection
        if lexical_ranked:
            lexical_ranked = await cross_encoder.rerank_by_relevance(
                query=query,
                candidates=lexical_ranked,
                user_id=user_id,
            )

        # Combine results, avoiding duplicates
        seen_ids = {str(row.get("id")) for row in cross_encoder_filtered}
        for row in lexical_ranked:
            item_id = str(row.get("id"))
            if item_id not in seen_ids:
                cross_encoder_filtered.append(row)
                seen_ids.add(item_id)
                if len(cross_encoder_filtered) >= limit:
                    break

        return cross_encoder_filtered[:limit]

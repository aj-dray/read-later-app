"""Note that on-device has been kept but commented out"""


from __future__ import annotations


import asyncio
import logging
import os
from typing import Any, Sequence
from functools import lru_cache

import cohere
# from sentence_transformers import CrossEncoder

from aglib import Response

from .. import database as db

logger = logging.getLogger(__name__)


# === CONFIGURATION ===


COHERE_RERANK_MODEL = "rerank-english-v3.0"  # Free tier available
CROSS_ENCODER_MODEL = COHERE_RERANK_MODEL
CROSS_ENCODER_THRESHOLD = 0.3
MAX_BATCH_SIZE = 100  # Cohere supports larger batches
# CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-TinyBERT-L-2-v2"
# _cross_encoder_model = None


# === MODEL MANAGEMENT ===


_cohere_client = None


@lru_cache(maxsize=1)
def _get_cohere_client():
    """Get or create the Cohere client (cached)."""
    global _cohere_client

    if _cohere_client is None:
        # Read API key at call time so late env changes are honored
        api_key = os.getenv("COHERE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "COHERE_API_KEY environment variable not set. "
                "Get a free API key at https://dashboard.cohere.com/api-keys"
            )

        logger.info("Initializing Cohere client for reranking")
        _cohere_client = cohere.Client(api_key)
        logger.info("Cohere client initialized successfully")

    return _cohere_client


# === USAGE LOGGING ===


async def _log_usage(
    operation: str,
    *,
    user_id: str | None,
    request_count: int,
    document_count: int,
) -> None:
    if request_count <= 0:
        return
    if getattr(db, "pool", None) is None:
        return

    usage_payload = {
        "requests": request_count,
        "documents": document_count,
    }

    response = Response(
        content="",
        provider="cohere",
        model=COHERE_RERANK_MODEL,
        usage=usage_payload,
    )

    try:
        await db.create_usage_log(
            response,
            operation,
            user_id=user_id,
            item_id=None,
        )
    except Exception:  # pragma: no cover - logging should not break search
        logger.exception(
            "Failed to log cross-encoder usage",
            extra={"operation": operation},
        )


# @lru_cache(maxsize=1)
# def _get_cross_encoder():
#     """Get or load the cross-encoder model (cached)."""
#     global _cross_encoder_model
#
#     if CrossEncoder is None:
#         raise RuntimeError(
#             "sentence-transformers not available. Install with: "
#             "pip install sentence-transformers"
#         )
#
#     if _cross_encoder_model is None:
#         logger.info(f"Loading cross-encoder model: {CROSS_ENCODER_MODEL}")
#         _cross_encoder_model = CrossEncoder(CROSS_ENCODER_MODEL)
#         logger.info("Cross-encoder model loaded successfully")
#
#     return _cross_encoder_model


# def _prepare_pairs(query: str, candidates: Sequence[dict[str, Any]]) -> list[tuple[str, str]]:
#     """Prepare query-candidate pairs for cross-encoder scoring."""
#     pairs = []
#
#     for candidate in candidates:
#         # Build candidate text from title, summary, and preview
#         candidate_parts = []
#
#         if candidate.get("title"):
#             candidate_parts.append(candidate["title"])
#
#         if candidate.get("summary"):
#             candidate_parts.append(candidate["summary"])
#
#         if candidate.get("preview"):
#             candidate_parts.append(candidate["preview"])
#
#         # Join parts with space, limit length to avoid token limits
#         candidate_text = " ".join(candidate_parts)[:1000]
#
#         if candidate_text.strip():
#             pairs.append((query, candidate_text))
#         else:
#             # Empty candidate text gets lowest score
#             pairs.append((query, ""))
#
#     return pairs


def _prepare_documents(candidates: Sequence[dict[str, Any]]) -> list[str]:
    """Prepare candidate documents for Cohere reranking."""
    documents = []

    for candidate in candidates:
        # Build candidate text from title, summary, and preview
        candidate_parts = []

        if candidate.get("title"):
            candidate_parts.append(candidate["title"])

        if candidate.get("summary"):
            candidate_parts.append(candidate["summary"])

        if candidate.get("preview"):
            candidate_parts.append(candidate["preview"])
        # Fall back to item content_text when preview is not present (items scope)
        if candidate.get("content_text"):
            candidate_parts.append(candidate["content_text"])

        # Join parts with space, limit length to avoid token limits
        candidate_text = " ".join(candidate_parts)[:1000]
        documents.append(candidate_text if candidate_text.strip() else " ")

    return documents


async def score_relevance(
    query: str,
    candidates: Sequence[dict[str, Any]],
    *,
    user_id: str | None = None,
    usage_operation: str = "cross_encoder.score_relevance",
) -> list[float]:
    """Score relevance between query and candidates using Cohere rerank API.

    Returns scores in same order as input candidates.
    Higher scores indicate better relevance.
    """
    if not candidates:
        return []

    if not query.strip():
        return [0.0] * len(candidates)

    try:
        # Prepare documents for Cohere
        documents = _prepare_documents(candidates)

        # Get Cohere client
        client = _get_cohere_client()

        # Score in batches to respect API limits
        all_scores = [0.0] * len(documents)

        for i in range(0, len(documents), MAX_BATCH_SIZE):
            batch_docs = documents[i:i + MAX_BATCH_SIZE]

            # Run rerank in thread to avoid blocking
            response = await asyncio.to_thread(
                client.rerank,
                query=query,
                documents=batch_docs,
                model=COHERE_RERANK_MODEL,
                top_n=len(batch_docs),  # Return all documents with scores
                return_documents=False
            )

            # Extract scores and place them in correct positions
            for result in response.results:
                original_idx = i + result.index
                all_scores[original_idx] = result.relevance_score

            await _log_usage(
                usage_operation,
                user_id=user_id,
                request_count=1,
                document_count=len(batch_docs),
            )

        return all_scores

    except Exception as e:
        logger.error(f"Cohere reranking failed: {e}")
        # Return neutral scores on error
        return [0.5] * len(candidates)


# async def score_relevance_ondevice(
#     query: str,
#     candidates: Sequence[dict[str, Any]]
# ) -> list[float]:
#     """Score relevance using on-device cross-encoder model."""
#     if not candidates:
#         return []
#
#     if not query.strip():
#         return [0.0] * len(candidates)
#
#     try:
#         # Prepare query-candidate pairs
#         pairs = _prepare_pairs(query, candidates)
#
#         # Get cross-encoder model
#         model = _get_cross_encoder()
#
#         # Score in batches to avoid memory issues
#         all_scores = []
#         for i in range(0, len(pairs), MAX_BATCH_SIZE):
#             batch_pairs = pairs[i:i + MAX_BATCH_SIZE]
#
#             # Run prediction in thread to avoid blocking
#             batch_scores = await asyncio.to_thread(model.predict, batch_pairs)
#             all_scores.extend(batch_scores.tolist())
#
#         return all_scores
#
#     except Exception as e:
#         logger.error(f"Cross-encoder scoring failed: {e}")
#         # Return neutral scores on error
#         return [0.5] * len(candidates)


async def filter_by_relevance(
    query: str,
    candidates: Sequence[dict[str, Any]],
    threshold: float = CROSS_ENCODER_THRESHOLD,
    *,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Filter candidates by cross-encoder relevance score."""
    if not candidates:
        return []

    # Score all candidates
    scores = await score_relevance(
        query,
        candidates,
        user_id=user_id,
        usage_operation="cross_encoder.filter",
    )

    # Add scores to candidates and filter
    filtered = []
    for candidate, score in zip(candidates, scores):
        if score >= threshold:
            # Add cross-encoder score to the result
            enhanced_candidate = candidate.copy()
            enhanced_candidate["cross_encoder_score"] = float(score)
            filtered.append(enhanced_candidate)

    # Sort by cross-encoder score (descending)
    filtered.sort(key=lambda x: x.get("cross_encoder_score", 0), reverse=True)

    return filtered


async def rerank_by_relevance(
    query: str,
    candidates: Sequence[dict[str, Any]],
    *,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Rerank candidates by cross-encoder relevance score without filtering."""
    if not candidates:
        return []

    # Score all candidates
    scores = await score_relevance(
        query,
        candidates,
        user_id=user_id,
        usage_operation="cross_encoder.rerank",
    )

    # Add scores and sort
    enhanced = []
    for candidate, score in zip(candidates, scores):
        enhanced_candidate = candidate.copy()
        enhanced_candidate["cross_encoder_score"] = float(score)
        enhanced.append(enhanced_candidate)

    # Sort by cross-encoder score (descending)
    enhanced.sort(key=lambda x: x.get("cross_encoder_score", 0), reverse=True)

    return enhanced

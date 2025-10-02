"""Utilities for generating derived data for items."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from aglib import Client
from pydantic import BaseModel

from .. import database as db


class SummaryData(BaseModel):
    summary: str
    expiry_score: float


def _build_generation_context(item: dict[str, Any]) -> str:
    parts: list[str] = []
    if item.get("title"):
        parts.append(f"Title: {item['title']}")
    if item.get("source_site"):
        parts.append(f"Source: {item['source_site']}")
    if item.get("publication_date"):
        parts.append(f"Published: {item['publication_date']}")
    parts.append(f"URL: {item.get('canonical_url') or item.get('url', '')}")
    if item.get("content_markdown"):
        parts.append(f"\nArticle Content:\n{item['content_markdown']}")
    return "\n".join(parts)


def _request_summary(item: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    prompt = (
        "Your role is to extract key metadata from the scraped data. "
        "Provide a 1-2 sentence summary and an expiry score between 0 and 1 "
        "where 1 decays fastest."
    )

    llm = Client.completion(provider="mistral", model="mistral-medium-latest")
    response = llm.request(
        system_prompt=prompt,
        messages=[{"role": "user", "content": _build_generation_context(item)}],
        response_format=SummaryData,
    )

    summary_data = SummaryData.model_validate(json.loads(response.content))
    payload = {
        "summary": summary_data.summary,
        "expiry_score": summary_data.expiry_score,
    }
    return response, payload


async def generate_data(item: dict[str, Any], user_id: str) -> dict[str, Any]:
    try:
        response, payload = await asyncio.to_thread(_request_summary, item)
    except Exception as exc:
        raise ValueError(f"Failed to generate summary: {exc}") from exc

    await db.create_usage_log(
        response,
        "completion.item_summary",
        user_id=user_id,
        item_id=item.get("id"),
    )

    payload.update(
        {
            "server_status": "summarised",
            "server_status_at": datetime.now(),
        }
    )
    return payload

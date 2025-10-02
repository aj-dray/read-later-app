"""Pricing helpers for computing provider usage costs."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


_PRICING_PATH = Path(__file__).resolve().parent.parent / "pricing.json"
_DEFAULT_TOKEN_UNIT = Decimal("1000000")
_CURRENCY_QUANT = Decimal("0.000001")


@lru_cache(maxsize=1)
def _load_pricing() -> Mapping[str, Any]:
    try:
        with _PRICING_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}
    return {}


def _lookup_provider(provider: str | None) -> Mapping[str, Any] | None:
    if not provider:
        return None
    pricing = _load_pricing()
    # Try exact match then lowercase fallback
    provider_data = pricing.get(provider)
    if isinstance(provider_data, Mapping):
        return provider_data
    provider_data = pricing.get(provider.lower())
    if isinstance(provider_data, Mapping):
        return provider_data
    return None


def _lookup_model(provider: str | None, model: str | None) -> Mapping[str, Any] | None:
    provider_data = _lookup_provider(provider)
    if not provider_data or not model:
        return None
    model_data = provider_data.get(model)
    if isinstance(model_data, Mapping):
        return model_data
    model_data = provider_data.get(model.lower())
    if isinstance(model_data, Mapping):
        return model_data
    return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):  # guard against True/False
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _quantize(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return value.quantize(_CURRENCY_QUANT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return value


def _cost_from_tokens(tokens: int | None, unit_cost: Decimal | None, unit_tokens: Decimal) -> Decimal | None:
    if tokens is None or unit_cost is None:
        return None
    if unit_tokens <= 0:
        unit_tokens = Decimal(1)
    raw = (Decimal(tokens) / unit_tokens) * unit_cost
    return _quantize(raw)


def _sum_costs(*values: Decimal | None) -> Decimal | None:
    total = Decimal("0")
    seen = False
    for value in values:
        if value is None:
            continue
        total += value
        seen = True
    if not seen:
        return None
    return _quantize(total)


def prepare_usage_log(
    provider: str | None,
    model: str | None,
    usage: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Normalise usage values and compute estimated costs for logging.

    Returns a dictionary with keys matching llm_usage_logs columns.
    """
    usage = usage or {}
    prompt_tokens = _to_int(usage.get("prompt_tokens"))
    completion_tokens = _to_int(usage.get("completion_tokens"))

    result: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "prompt_cost": None,
        "completion_cost": None,
        "total_cost": None,
        "currency": usage.get("currency"),
    }

    pricing = _lookup_model(provider, model)
    if not pricing:
        return result

    billing_type = pricing.get("billing_type", "per_token")
    currency = pricing.get("currency") or result["currency"]
    result["currency"] = currency

    if billing_type == "per_token":
        unit_tokens = _to_decimal(pricing.get("unit_tokens")) or _DEFAULT_TOKEN_UNIT
        input_cost = _to_decimal(pricing.get("input_cost") or pricing.get("input"))
        output_cost = _to_decimal(pricing.get("output_cost") or pricing.get("output"))

        prompt_cost = _cost_from_tokens(prompt_tokens, input_cost, unit_tokens)
        completion_cost = _cost_from_tokens(completion_tokens, output_cost, unit_tokens)
        total_cost = _sum_costs(prompt_cost, completion_cost)

        result["prompt_cost"] = prompt_cost
        result["completion_cost"] = completion_cost
        result["total_cost"] = total_cost
        return result

    if billing_type == "per_request":
        request_key = pricing.get("request_key", "requests")
        request_count = _to_decimal(usage.get(request_key)) or Decimal(0)
        cost_per_request = _to_decimal(
            pricing.get("cost_per_request") or pricing.get("unit_cost")
        ) or Decimal(0)

        total_cost = _quantize(request_count * cost_per_request)
        result["prompt_cost"] = total_cost
        result["completion_cost"] = None
        result["total_cost"] = total_cost
        return result

    return result

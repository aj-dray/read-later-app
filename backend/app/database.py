"""Database connectivity and schema management for the Later service."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from contextlib import contextmanager
import logging
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    Literal,
)
import uuid
from aglib import Response  # type: ignore[attr-defined]
from psycopg import errors, sql, OperationalError, InterfaceError
from contextlib import asynccontextmanager
from psycopg import rows
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from datetime import datetime


from . import schemas
from . import utils as app_utils
from . import auth
from . import pricing


logger = logging.getLogger(__name__)


# === VARIABLES ===


EMBEDDING_DIM = 1024
PBKDF2_ITERATIONS = 310_000
# Batch the chunk inserts to reduce payload sizes over SSL connections.
# Tune these as needed.
INSERT_BATCH_SIZE = 16
INSERT_MAX_RETRIES = 3


ITEM_SEARCH_DEFAULT_COLUMNS: tuple[str, ...] = ("id", "title", "summary")

CHUNK_COLUMN_SOURCES: dict[str, str] = {
    "id": "c.id",
    "item_id": "c.item_id",
    "position": "c.position",
    "content_text": "c.content_text",
    "content_token_count": "c.content_token_count",
    "created_at": "c.created_at",
    "title": "i.title",
    "summary": "i.summary",
    "url": "i.url",
    "canonical_url": "i.canonical_url",
    "source_site": "i.source_site",
}

CHUNK_SEARCH_DEFAULT_COLUMNS: tuple[str, ...] = (
    "id",
    "item_id",
    "position",
    "content_text",
    "title",
)


# === CONFIGURATION ===


# Build DATABASE_URL from environment variables
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_DB = os.getenv("POSTGRES_DB", "postgres")
POSTGRES_USER = os.getenv("POSTGRES_USER", "local")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "dev-password")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)
pool: AsyncConnectionPool | None = None


async def init_pool():
    global pool
    if pool is None:
        pool = AsyncConnectionPool(
            conninfo=DATABASE_URL,
            min_size=1, max_size=20,
            kwargs={"row_factory": dict_row,
                "prepare_threshold": None},
            timeout=10, max_lifetime=1800, max_idle=300,
            open=False
        )
        await pool.open()

async def close_pool():
    global pool
    if pool:
        await pool.close()
        pool = None

@asynccontextmanager
async def get_connection():
    assert pool is not None
    async with pool.connection() as conn:
        yield conn


# === INITIALISATION ===


async def init_database() -> None:
    """Create required extensions, types, tables and indexes if they do not exist."""

    sql_statments: list[str] = schemas.get_create_sql()

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            for statement in sql_statments:
                await cur.execute(statement)  # type: ignore
        await conn.commit()


# === USERS ===


async def create_user(username: str, password: str) -> int:
    """Create a user row, returning the generated id."""

    password_hash = auth.hash_password(password)

    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            try:
                await cur.execute(
                    """
                    INSERT INTO users (username, password_hash)
                    VALUES (%(username)s, %(password_hash)s)
                    RETURNING id
                    """,
                    {"username": username, "password_hash": password_hash},
                )
            except errors.UniqueViolation as exc:
                await conn.rollback()
                raise ValueError("Username already exists") from exc

            row = await cur.fetchone()
            if not row:
                await conn.rollback()
                raise RuntimeError("Failed to insert user")

        await conn.commit()

    return row["id"]


async def authenticate_user(username: str, password: str) -> dict[str, str] | None:
    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, username, password_hash
                FROM users
                WHERE username = %(username)s
                """,
                {"username": username},
            )
            row: dict[str, Any] | None = await cur.fetchone()

    if not row:
        return None
    ph = row.get("password_hash")
    if not isinstance(ph, str) or not auth.verify_password(password, ph):
        return None
    return {"user_id": str(row["id"]), "username": str(row["username"])}


async def get_user_by_username(username: str) -> dict[str, Any] | None:
    """Fetch a user row by username."""
    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, username, password_hash, created_at
                FROM users
                WHERE username = %(username)s
                """,
                {"username": username},
            )
            row: dict[str, Any] | None = await cur.fetchone()
    return _normalise_row(row) if row else None


async def update_user_password(*, user_id: str, new_password: str) -> None:
    """Set a new password for the given user id."""
    password_hash = auth.hash_password(new_password)
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE users
                SET password_hash = %(password_hash)s
                WHERE id = %(user_id)s
                """,
                {"password_hash": password_hash, "user_id": user_id},
            )
        await conn.commit()


async def clone_user_data(*, source_user_id: str, target_user_id: str) -> dict[str, int]:
    """
    Clone data from one user to another.

    Copies:
    - items
    - item_chunks (via URL match between source and target items)
    - user_settings (all types/keys)

    Returns a summary dict with counts of copied rows.
    """
    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            # Copy items: insert rows for target user with same content/metadata
            await cur.execute(
                """
                INSERT INTO items (
                    user_id,
                    url,
                    canonical_url,
                    title,
                    source_site,
                    publication_date,
                    favicon_url,
                    content_markdown,
                    content_text,
                    content_token_count,
                    client_status,
                    server_status,
                    summary,
                    expiry_score,
                    mistral_embedding,
                    client_status_at,
                    server_status_at,
                    created_at
                )
                SELECT
                    %(target_user_id)s AS user_id,
                    url,
                    canonical_url,
                    title,
                    source_site,
                    publication_date,
                    favicon_url,
                    content_markdown,
                    content_text,
                    content_token_count,
                    client_status,
                    server_status,
                    summary,
                    expiry_score,
                    mistral_embedding,
                    client_status_at,
                    server_status_at,
                    created_at
                FROM items
                WHERE user_id = %(source_user_id)s
                RETURNING id
                """,
                {"source_user_id": source_user_id, "target_user_id": target_user_id},
            )
            inserted_items = await cur.fetchall()
            inserted_count = len(inserted_items or [])

            # Copy item_chunks by matching items via URL between source and target users
            # This avoids needing an explicit mapping table of old->new item ids.
            await cur.execute(
                """
                INSERT INTO item_chunks (
                    item_id,
                    position,
                    content_text,
                    content_token_count,
                    mistral_embedding,
                    created_at
                )
                SELECT
                    dest.id AS item_id,
                    c.position,
                    c.content_text,
                    c.content_token_count,
                    c.mistral_embedding,
                    c.created_at
                FROM item_chunks AS c
                JOIN items AS src ON src.id = c.item_id AND src.user_id = %(source_user_id)s
                JOIN items AS dest ON dest.user_id = %(target_user_id)s AND dest.url = src.url
                """,
                {"source_user_id": source_user_id, "target_user_id": target_user_id},
            )
            # item_chunks insert count not directly returned; we can query for count
            await cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM item_chunks AS c
                JOIN items AS src ON src.id = c.item_id AND src.user_id = %(source_user_id)s
                """,
                {"source_user_id": source_user_id},
            )
            row = await cur.fetchone()
            chunk_count = int(row["cnt"]) if row and "cnt" in row else 0

            # Copy user settings (all types/keys)
            await cur.execute(
                """
                INSERT INTO user_settings (
                    user_id,
                    setting_type,
                    setting_key,
                    setting_value,
                    created_at,
                    updated_at
                )
                SELECT
                    %(target_user_id)s AS user_id,
                    setting_type,
                    setting_key,
                    setting_value,
                    created_at,
                    updated_at
                FROM user_settings
                WHERE user_id = %(source_user_id)s
                ON CONFLICT (user_id, setting_type, setting_key) DO NOTHING
                RETURNING id
                """,
                {"source_user_id": source_user_id, "target_user_id": target_user_id},
            )
            inserted_settings = await cur.fetchall()
            settings_count = len(inserted_settings or [])
        await conn.commit()

    return {"items": inserted_count, "item_chunks": chunk_count, "user_settings": settings_count}


# === ITEMS ===


async def create_item(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist an item, returning the created row."""

    if not payload.get("user_id"):
        raise ValueError("Item must belong to a user")

    columns = list(payload.keys())
    column_identifiers = [sql.Identifier(col) for col in columns]
    value_placeholders = [sql.Placeholder(col) for col in columns]

    query = sql.SQL("INSERT INTO items ({}) VALUES ({}) RETURNING id").format(
        sql.SQL(", ").join(column_identifiers),
        sql.SQL(", ").join(value_placeholders)
    )

    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            try:
                await cur.execute(query, payload)
            except errors.ForeignKeyViolation as exc:
                await conn.rollback()
                raise ValueError("User does not exist") from exc

            row = await cur.fetchone()
            if not row:
                await conn.rollback()
                raise RuntimeError("Failed to insert item")
        await conn.commit()
    return _normalise_row(row)


async def get_item(item_id: str, cols: list[str], user_id: str) -> dict[str, Any] | None:
    """Return dict of cols for an item by id ensuring ownership."""
    safe_cols = [col for col in cols if col in schemas.ITEM_PUBLIC_COLS]

    if not safe_cols:
        raise ValueError("No valid columns specified")

    column_identifiers = [sql.Identifier(col) for col in safe_cols]
    query = sql.SQL("SELECT {} FROM items WHERE id = %(item_id)s AND user_id = %(user_id)s").format(
        sql.SQL(", ").join(column_identifiers)
    )

    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, {"item_id": item_id, "user_id": user_id})
            row = await cur.fetchone()

    if not row:
        return None
    return _normalise_row(row)


async def get_items(
    columns: list[str],
    filters: list[tuple[str, str, Any]],
    user_id: str,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    order_direction: str | None = None,
) -> list[dict[str, Any]]:
    """
    General purpose select for items with user ownership check.

    Args:
        columns: List of column names to select.
        filters: List of (column, operator, value) tuples for WHERE clause.
        user_id: User ID to ensure ownership.
        limit: Maximum number of rows to return.
        offset: Number of rows to skip.
        order_by: Column to order by.
        order_direction: "asc" or "desc".

    Returns:
        List of dicts mapping column names to values.
    """
    allowed_operators = ["=", "!=", "<", "<=", ">", ">=", "LIKE", "ILIKE", "IN"]

    safe_cols = [col for col in columns if col in schemas.ITEM_PUBLIC_COLS]
    if not safe_cols:
        raise ValueError("No valid columns specified")

    # Validate filters
    safe_filters = []
    params: dict[str, Any] = {"user_id": user_id}
    param_counter = 0

    for col, op, val in filters:
        if col not in schemas.ITEM_PUBLIC_COLS or op.upper() not in allowed_operators:
            continue
        param_key = f"filter_{param_counter}"
        if op.upper() == "IN":
            safe_filters.append((col, op.upper(), param_key))
            params[param_key] = list(val) if isinstance(val, (list, tuple)) else [val]
        else:
            safe_filters.append((col, op.upper(), param_key))
            params[param_key] = val
        param_counter += 1

    # Build query
    column_identifiers = [sql.Identifier(col) for col in safe_cols]
    base_query = sql.SQL("SELECT {} FROM items WHERE user_id = %(user_id)s").format(
        sql.SQL(", ").join(column_identifiers)
    )

    if safe_filters:
        filter_conditions = []
        for col, op, param_key in safe_filters:
            if op == "IN":
                condition = sql.SQL("{} = ANY(%({})s)").format(
                    sql.Identifier(col),
                    sql.SQL(param_key)
                )
            else:
                condition = sql.SQL("{} {} %({})s").format(
                    sql.Identifier(col),
                    sql.SQL(op),
                    sql.SQL(param_key)
                )
            filter_conditions.append(condition)

        filter_clause = sql.SQL(" AND ").join(filter_conditions)
        query = sql.SQL("{} AND {}").format(base_query, filter_clause)
    else:
        query = base_query

    if order_by and order_by in schemas.ITEM_PUBLIC_COLS:
        order_direction_sql = sql.SQL("DESC") if order_direction == "desc" else sql.SQL("ASC")
        query = sql.SQL("{} ORDER BY {} {}").format(
            query, sql.Identifier(order_by), order_direction_sql
        )

    if limit is not None:
        query = sql.SQL("{} LIMIT %(limit)s").format(query)
        params["limit"] = limit
    if offset is not None:
        query = sql.SQL("{} OFFSET %(offset)s").format(query)
        params["offset"] = offset

    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()

    return [_normalise_row(row) for row in rows]


def _ensure_columns(
    requested: Sequence[str] | None,
    allowed: Sequence[str],
    default: Sequence[str],
) -> list[str]:
    """Return a validated list of columns limited to an allow-list."""

    if requested:
        safe = [col for col in requested if col in allowed]
    else:
        safe = list(default)
    if not safe:
        raise ValueError("No valid columns specified")
    return safe


def _vector_to_pg(vec: Sequence[float]) -> str:
    """Deprecated: use app.utils.vector_to_pg. Kept for backward compatibility."""
    return app_utils.vector_to_pg(vec)


def _coerce_numeric(value: Any) -> Any:
    """Normalise numeric values coming back from psycopg row factories."""

    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value


async def update_item(updates: dict[str, Any], item_id: str, user_id: str) -> dict[str, Any] | None:
    allowed_columns = schemas.ITEM_PUBLIC_COLS
    cols = [c for c in updates if c in allowed_columns]
    if not cols:
        raise ValueError("No valid item fields supplied for update")

    payload: dict[str, Any] = {"item_id": item_id}
    payload.update({c: updates[c] for c in cols})
    # Ensure vector fields are serialised in pgvector text format
    if "mistral_embedding" in payload and isinstance(payload["mistral_embedding"], (list, tuple)):
        payload["mistral_embedding"] = app_utils.vector_to_pg(payload["mistral_embedding"])  # type: ignore[arg-type]
    if user_id is not None:
        payload["user_id"] = user_id

    set_parts = [
        sql.SQL("{} = {}").format(sql.Identifier(c), sql.Placeholder(c))
        for c in cols
    ]

    where_parts = [sql.SQL("id = {}").format(sql.Placeholder("item_id"))]
    if user_id is not None:
        where_parts.append(sql.SQL("AND user_id = {}").format(sql.Placeholder("user_id")))

    query = sql.SQL(
        "UPDATE items SET {set_clause} WHERE {where_clause} RETURNING {ret}"
    ).format(
        set_clause=sql.SQL(", ").join(set_parts),
        where_clause=sql.SQL(" ").join(where_parts),
        ret=sql.SQL(", ").join(sql.Identifier(c) for c in allowed_columns),
    )

    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, payload)
            row = await cur.fetchone()
        await conn.commit()

    if not row:
        return None
    return _normalise_row(row)


async def delete_item(item_id: str, user_id: str) -> bool:
    """Delete an item, optionally scoping to a user, returning success status."""

    params: dict[str, Any] = {"item_id": item_id}
    where_parts = [sql.SQL("id = {}").format(sql.Placeholder("item_id"))]

    if user_id:
        where_parts.append(sql.SQL("AND user_id = {}").format(sql.Placeholder("user_id")))
        params["user_id"] = user_id

    query = sql.SQL("DELETE FROM items WHERE {}").format(
        sql.SQL(" ").join(where_parts)
    )

    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            deleted = cur.rowcount > 0
        await conn.commit()

    return deleted


async def lexical_search_items(*, user_id: str, query_text: str, columns: Sequence[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
    if limit <= 0:
        raise ValueError("Limit must be positive")
    safe_columns = _ensure_columns(columns, schemas.ITEM_PUBLIC_COLS, ITEM_SEARCH_DEFAULT_COLUMNS)
    column_select = ", ".join(f"i.{col}" for col in safe_columns)
    if column_select:
        column_select = column_select + ", "
    params: dict[str, Any] = {"user_id": user_id, "limit": limit, "query": query_text.strip()}
    query = f"""
        SELECT {column_select}
               ts_rank(i.ts_embedding, plainto_tsquery('english', %(query)s)) AS score
        FROM items AS i
        WHERE i.user_id = %(user_id)s
          AND i.ts_embedding @@ plainto_tsquery('english', %(query)s)
        ORDER BY score DESC
        LIMIT %(limit)s
    """
    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
    return [_normalise_row(row) for row in rows]


async def semantic_search_items(*, user_id: str, query_vector: Sequence[float], columns: Sequence[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
    if limit <= 0:
        raise ValueError("Limit must be positive")
    safe_columns = _ensure_columns(columns, schemas.ITEM_PUBLIC_COLS, ITEM_SEARCH_DEFAULT_COLUMNS)
    column_select = ", ".join(f"i.{col}" for col in safe_columns)
    if column_select:
        column_select = column_select + ", "
    params: dict[str, Any] = {"user_id": user_id, "limit": limit, "query_vec": _vector_to_pg(query_vector)}
    distance_expr = "i.mistral_embedding <-> %(query_vec)s::vector"
    query = f"""
        SELECT {column_select}
               {distance_expr} AS distance,
               1.0 / (1.0 + ({distance_expr})::float) AS score
        FROM items AS i
        WHERE i.user_id = %(user_id)s
          AND i.mistral_embedding IS NOT NULL
        ORDER BY {distance_expr} ASC
        LIMIT %(limit)s
    """
    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
    return [_normalise_row(row) for row in rows]


# === CHUNKS ===


async def lexical_search_chunks(*, user_id: str, query_text: str, columns: Sequence[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
    if limit <= 0:
        raise ValueError("Limit must be positive")
    allowed_chunk_columns = tuple(CHUNK_COLUMN_SOURCES.keys())
    safe_columns = _ensure_columns(columns, allowed_chunk_columns, CHUNK_SEARCH_DEFAULT_COLUMNS)
    select_parts = [f"{CHUNK_COLUMN_SOURCES[col]} AS {col}" for col in safe_columns]
    column_select = ", ".join(select_parts)
    if column_select:
        column_select = column_select + ", "
    params: dict[str, Any] = {"user_id": user_id, "limit": limit, "query": query_text.strip()}
    query = f"""
        SELECT {column_select}
               ts_rank(c.ts_embedding, plainto_tsquery('english', %(query)s)) AS score
        FROM item_chunks AS c
        JOIN items AS i ON i.id = c.item_id
        WHERE i.user_id = %(user_id)s
          AND c.ts_embedding @@ plainto_tsquery('english', %(query)s)
        ORDER BY score DESC
        LIMIT %(limit)s
    """
    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
    return [_normalise_row(row) for row in rows]


async def semantic_search_chunks(*, user_id: str, query_vector: Sequence[float], columns: Sequence[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
    if limit <= 0:
        raise ValueError("Limit must be positive")
    allowed_chunk_columns = tuple(CHUNK_COLUMN_SOURCES.keys())
    safe_columns = _ensure_columns(columns, allowed_chunk_columns, CHUNK_SEARCH_DEFAULT_COLUMNS)
    select_parts = [f"{CHUNK_COLUMN_SOURCES[col]} AS {col}" for col in safe_columns]
    column_select = ", ".join(select_parts)
    if column_select:
        column_select = column_select + ", "
    params: dict[str, Any] = {"user_id": user_id, "limit": limit, "query_vec": _vector_to_pg(query_vector)}
    distance_expr = "c.mistral_embedding <-> %(query_vec)s::vector"
    query = f"""
        SELECT {column_select}
               {distance_expr} AS distance,
               1.0 / (1.0 + ({distance_expr})::float) AS score
        FROM item_chunks AS c
        JOIN items AS i ON i.id = c.item_id
        WHERE i.user_id = %(user_id)s
          AND c.mistral_embedding IS NOT NULL
        ORDER BY {distance_expr} ASC
        LIMIT %(limit)s
    """
    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
    return [_normalise_row(row) for row in rows]


async def add_item_chunks(*, item_id: str, chunks: Sequence[dict[str, Any]]) -> None:
    """Persist chunk embeddings for an item."""

    if not chunks:
        return

    records: list[dict[str, Any]] = []
    for position, chunk in enumerate(chunks):
        embedding = chunk.get("mistral_embedding")
        if embedding is None:
            raise ValueError("Chunk embedding missing")
        records.append(
            {
                "item_id": item_id,
                "position": position,
                "content_text": chunk.get("content_text"),
                "content_token_count": chunk.get("content_token_count"),
                # Serialize to pgvector text format
                "mistral_embedding": app_utils.vector_to_pg(embedding),
            }
        )

    # Insert in batches with retries to avoid large payloads and handle transient EOF/SSL errors
    stmt = (
        """
        INSERT INTO item_chunks (item_id, position, content_text, content_token_count, mistral_embedding)
        VALUES (%(item_id)s, %(position)s, %(content_text)s, %(content_token_count)s, %(mistral_embedding)s::vector)
        ON CONFLICT (item_id, position) DO UPDATE SET
            content_text = EXCLUDED.content_text,
            content_token_count = EXCLUDED.content_token_count,
            mistral_embedding = EXCLUDED.mistral_embedding
        """
    )

    # Small helper to yield batches
    def _batches(seq: Sequence[dict[str, Any]], size: int) -> Iterator[Sequence[dict[str, Any]]]:
        for i in range(0, len(seq), size):
            yield seq[i : i + size]

    for batch in _batches(records, max(1, INSERT_BATCH_SIZE)):
        attempt = 0
        while True:
            attempt += 1
            try:
                async with get_connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.executemany(stmt, batch)
                    await conn.commit()
                break  # success for this batch
            except (OperationalError, InterfaceError) as exc:
                # Transient connection errors sometimes show up as SSL EOF / bad length
                is_transient = True
                msg = str(exc).lower()
                # A conservative check; still bounded by max retries
                transient_indicators = [
                    "ssl", "eof", "bad length", "server closed the connection",
                    "connection not open", "connection closed"
                ]
                if not any(tok in msg for tok in transient_indicators):
                    is_transient = False

                logger.warning(
                    "Batch insert failed%s (attempt %s/%s); size=%s",
                    " (transient)" if is_transient else "",
                    attempt,
                    INSERT_MAX_RETRIES,
                    len(batch),
                    extra={"item_id": item_id, "error": str(exc)},
                    exc_info=None,
                )
                if not is_transient or attempt >= INSERT_MAX_RETRIES:
                    logger.exception(
                        "Failed to persist chunk embeddings",
                        extra={
                            "item_id": item_id,
                            "chunk_count": len(records),
                            "batch_size": len(batch),
                            "attempt": attempt,
                        },
                    )
                    raise
                # brief async backoff before retrying this batch
                try:
                    import asyncio
                    await asyncio.sleep(0.1 * attempt)
                except Exception:
                    pass
            except Exception:
                logger.exception(
                    "Failed to persist chunk embeddings",
                    extra={"item_id": item_id, "chunk_count": len(records)},
                )
                raise


# === USAGE LOGS ===


async def create_usage_log(
    response: Response,
    operation: str,
    *,
    user_id: str | None,
    item_id: str | None = None,
) -> dict[str, Any]:
    """Create a usage log entry"""
    usage_details = pricing.prepare_usage_log(
        response.provider,
        response.model,
        getattr(response, "usage", {}),
    )

    log = {
        "operation": operation,
        "provider": response.provider,
        "model": response.model,
        "prompt_tokens": usage_details.get("prompt_tokens"),
        "completion_tokens": usage_details.get("completion_tokens"),
        "prompt_cost": usage_details.get("prompt_cost"),
        "completion_cost": usage_details.get("completion_cost"),
        "total_cost": usage_details.get("total_cost"),
        "currency": usage_details.get("currency") or "USD",
        "created_at": datetime.now(),
        "user_id": user_id,
        "item_id": item_id,
    }
    columns = list(log.keys())
    column_identifiers = [sql.Identifier(col) for col in columns]
    value_placeholders = [sql.Placeholder(col) for col in columns]

    query = sql.SQL("INSERT INTO llm_usage_logs ({}) VALUES ({}) RETURNING id").format(
        sql.SQL(", ").join(column_identifiers),
        sql.SQL(", ").join(value_placeholders)
    )

    async with get_connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, log)
            row = await cur.fetchone()
            if not row:
                raise RuntimeError("Failed to insert item")
        await conn.commit()
    return _normalise_row(row)



# === UTILITIES ===


def _normalise_row(row: dict[str, Any]) -> dict[str, Any]:
    """Transform database row values into JSON-serialisable primitives."""

    result: dict[str, Any] = {}
    for column in row.keys():
        value = row.get(column)
        if isinstance(value, uuid.UUID):
            result[column] = str(value)
        elif isinstance(value, Decimal):
            result[column] = str(value) # to keep precision
        else:
            result[column] = value
    return result


# === USER SETTINGS ===


async def get_user_setting(user_id: str, setting_type: str, setting_key: str) -> dict[str, Any] | None:
    """Get a specific user setting."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT setting_value FROM user_settings WHERE user_id = %s AND setting_type = %s AND setting_key = %s",
                (user_id, setting_type, setting_key)
            )
            row = await cur.fetchone()
            if row:
                return row["setting_value"]
            return None


async def set_user_setting(user_id: str, setting_type: str, setting_key: str, setting_value: dict[str, Any]) -> None:
    """Set a user setting."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO user_settings (user_id, setting_type, setting_key, setting_value, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (user_id, setting_type, setting_key)
                DO UPDATE SET
                    setting_value = EXCLUDED.setting_value,
                    updated_at = NOW()
                """,
                (user_id, setting_type, setting_key, json.dumps(setting_value))
            )
        await conn.commit()


async def update_user_setting_field(user_id: str, setting_type: str, setting_key: str, field_key: str, field_value: Any) -> None:
    """Update a single field within a user setting."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            # First try to update existing record
            await cur.execute(
                """
                UPDATE user_settings
                SET setting_value = jsonb_set(setting_value, %s, %s, true),
                    updated_at = NOW()
                WHERE user_id = %s AND setting_type = %s AND setting_key = %s
                """,
                (f'{{{field_key}}}', json.dumps(field_value), user_id, setting_type, setting_key)
            )

            # If no rows were updated, insert a new record
            if cur.rowcount == 0:
                setting_value = {field_key: field_value}
                await cur.execute(
                    """
                    INSERT INTO user_settings (user_id, setting_type, setting_key, setting_value)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (user_id, setting_type, setting_key, json.dumps(setting_value))
                )
        await conn.commit()


async def get_user_settings_by_type(user_id: str, setting_type: str) -> dict[str, dict[str, Any]]:
    """Get all user settings of a specific type."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT setting_key, setting_value FROM user_settings WHERE user_id = %s AND setting_type = %s",
                (user_id, setting_type)
            )
            rows = await cur.fetchall()
            return {row["setting_key"]: row["setting_value"] for row in rows}


# Legacy functions for backward compatibility
async def get_user_controls(user_id: str, page_path: str) -> dict[str, Any] | None:
    """Legacy function: Get control states for a user on a specific page."""
    return await get_user_setting(user_id, "controls", page_path)


async def set_user_controls(user_id: str, page_path: str, control_states: dict[str, Any]) -> None:
    """Legacy function: Set control states for a user on a specific page."""
    await set_user_setting(user_id, "controls", page_path, control_states)


async def update_user_control(user_id: str, page_path: str, control_key: str, control_value: Any) -> None:
    """Legacy function: Update a single control state for a user on a specific page."""
    await update_user_setting_field(user_id, "controls", page_path, control_key, control_value)


__all__ = [
    "get_connection",
    "close_pool",
    "init_database",
    "create_user",
    "authenticate_user",
    "create_item",
    "get_item",
    "get_items",
    "lexical_search_items",
    "semantic_search_items",
    "lexical_search_chunks",
    "semantic_search_chunks",
    "update_item",
    "delete_item",
    "add_item_chunks",
    "create_usage_log",
    "get_user_setting",
    "set_user_setting",
    "update_user_setting_field",
    "get_user_settings_by_type",
    "get_user_controls",
    "set_user_controls",
    "update_user_control",
]

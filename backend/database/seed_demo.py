import json
import os
import sys
from typing import Any, Iterable

import psycopg


DEMO_USERNAME = "demo"
# Precomputed for password: "password" using backend auth (pbkdf2_sha256, 100000 iters)
DEMO_PASSWORD_HASH = (
    "pbkdf2_sha256$100000$LD0dr2Z0AMugGAivOrW4YRo/Zy1EFzzTk2WorRIBBkA=$"
    "wHq+cSI/hL1mTfuJBUW376/cNSCGCdRxklcr8p/PYYM="
)


def get_db_conninfo() -> str:
    host = os.getenv("POSTGRES_HOST", "localhost")
    db = os.getenv("POSTGRES_DB", "postgres")
    user = os.getenv("POSTGRES_USER", "local")
    pwd = os.getenv("POSTGRES_PASSWORD", "dev-password")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"


def ensure_demo_user(conn: psycopg.Connection) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (username, password_hash)
            VALUES (%s, %s)
            ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash
            RETURNING id
            """,
            (DEMO_USERNAME, DEMO_PASSWORD_HASH),
        )
        row = cur.fetchone()
        if not row:
            # Existing row, fetch id
            cur.execute("SELECT id FROM users WHERE username = %s", (DEMO_USERNAME,))
            row = cur.fetchone()
        assert row and row[0], "Failed to upsert demo user"
        return str(row[0])

def _vector_to_pg(vec: Any) -> str | None:
    if vec is None:
        return None
    if isinstance(vec, str):
        # Already in pgvector text format
        return vec
    try:
        return "[" + ", ".join(str(float(v)) for v in vec) + "]"
    except Exception:
        return None


def _is_full_item(item: dict[str, Any], export_chunks: dict[str, list[dict[str, Any]]]) -> bool:
    """Define criteria for a 'full' item we accept into the demo seed."""
    # Must have essential content fields
    if not (item.get("content_text") and item.get("summary")):
        return False
    # Must have chunk data in export
    item_id = item.get("id")
    chunks = export_chunks.get(item_id) if item_id else None
    if not isinstance(chunks, list) or len(chunks) == 0:
        return False
    return True


def seed_items(
    conn: psycopg.Connection,
    user_id: str,
    items: list[dict[str, Any]],
    export_chunks: dict[str, list[dict[str, Any]]],
) -> tuple[int, int, int]:
    """Upsert only 'full' items; skip incomplete entries.

    Returns: (inserted_count, updated_count, skipped_incomplete)
    """
    inserted = 0
    updated = 0
    skipped_incomplete = 0
    first_error: Exception | None = None
    with conn.cursor() as cur:
        for obj in items:
            url = (obj.get("url") or "").strip()
            if not url:
                skipped_incomplete += 1
                continue
            if not _is_full_item(obj, export_chunks):
                skipped_incomplete += 1
                continue

            payload: dict[str, Any] = {
                "user_id": user_id,
                "url": url,
            }
            # Map known fields if present
            for key in (
                "canonical_url",
                "title",
                "source_site",
                "publication_date",
                "favicon_url",
                "content_markdown",
                "content_text",
                "content_token_count",
                "client_status",
                "server_status",
                "summary",
                "expiry_score",
                "client_status_at",
                "server_status_at",
                "created_at",
            ):
                if obj.get(key) is not None:
                    payload[key] = obj[key]
            # Vector field: serialize to pgvector text format
            if obj.get("mistral_embedding") is not None:
                payload["mistral_embedding"] = _vector_to_pg(obj["mistral_embedding"])  # type: ignore[arg-type]

            # Build dynamic upsert
            cols = list(payload.keys())
            placeholders = ["%(" + c + ")s" for c in cols]
            set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in ("user_id", "url"))
            sql = (
                f"INSERT INTO items ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) "
                f"ON CONFLICT (user_id, url) DO UPDATE SET {set_clause}"
            )

            try:
                cur.execute(sql, payload)
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    updated += 1
            except Exception as e:
                # Treat errors as 'skip' but capture the first error for diagnostics
                skipped_incomplete += 1
                if first_error is None:
                    first_error = e
        conn.commit()
    if first_error is not None:
        print(f"Warning: first item upsert error: {first_error}", file=sys.stderr)
    return inserted, updated, skipped_incomplete


def seed_chunks(conn: psycopg.Connection, user_id: str, export_items: list[dict[str, Any]], export_chunks: dict[str, list[dict[str, Any]]]) -> tuple[int, int]:
    """Insert or update item_chunks mapped by URL from export to newly upserted items."""
    # Build mapping from old export item id -> url
    id_to_url = {it.get("id"): it.get("url") for it in export_items if it.get("id") and it.get("url")}
    urls = [u for u in id_to_url.values() if isinstance(u, str)]
    # Get current ids for these URLs under demo user
    url_to_new_id: dict[str, str] = {}
    with conn.cursor() as cur:
        if urls:
            cur.execute(
                "SELECT id, url FROM items WHERE user_id = %s AND url = ANY(%s)",
                (user_id, urls),
            )
            for row in cur.fetchall():
                url_to_new_id[row[1]] = row[0]

    inserted = 0
    updated_or_skipped = 0
    first_error: Exception | None = None
    with conn.cursor() as cur:
        for old_id, chunks in export_chunks.items():
            url = id_to_url.get(old_id)
            if not url:
                continue
            new_item_id = url_to_new_id.get(url)
            if not new_item_id:
                continue
            for ch in chunks:
                payload = {
                    "item_id": new_item_id,
                    "position": ch.get("position"),
                    "content_text": ch.get("content_text"),
                    "content_token_count": ch.get("content_token_count"),
                }
                if ch.get("mistral_embedding") is not None:
                    payload["mistral_embedding"] = _vector_to_pg(ch["mistral_embedding"])  # type: ignore[arg-type]
                cols = list(payload.keys())
                placeholders = ["%(" + c + ")s" for c in cols]
                set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in ("item_id", "position"))
                sql = (
                    f"INSERT INTO item_chunks ({', '.join(cols)}) VALUES ({', '.join(placeholders)}) "
                    f"ON CONFLICT (item_id, position) DO UPDATE SET {set_clause}"
                )
                try:
                    cur.execute(sql, payload)
                    if cur.rowcount == 1:
                        inserted += 1
                    else:
                        updated_or_skipped += 1
                except Exception as e:
                    updated_or_skipped += 1
                    if first_error is None:
                        first_error = e
        conn.commit()
    if first_error is not None:
        print(f"Warning: first chunk upsert error: {first_error}", file=sys.stderr)
    return inserted, updated_or_skipped


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: seed_demo_from_json.py /path/to/items.json", file=sys.stderr)
        return 2
    items_path = sys.argv[1]
    with open(items_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    export_items: list[dict[str, Any]]
    export_chunks: dict[str, list[dict[str, Any]]]
    if isinstance(data, list):
        export_items = data
        export_chunks = {}
    elif isinstance(data, dict) and isinstance(data.get("items"), list):
        export_items = data["items"]
        export_chunks = data.get("item_chunks") or {}
    else:
        print("Unsupported JSON format: expected list or { items: [...] }", file=sys.stderr)
        return 2

    conninfo = get_db_conninfo()
    # Retry loop to wait for schema readiness
    import time
    start = time.time()
    last_err: Exception | None = None
    while True:
        try:
            with psycopg.connect(conninfo) as conn:
                with conn.cursor() as cur:
                    # Ensure required tables exist
                    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'users'")
                    if cur.fetchone() is None:
                        raise RuntimeError("schema not ready: users")
                    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'items'")
                    if cur.fetchone() is None:
                        raise RuntimeError("schema not ready: items")
                    cur.execute("SET client_min_messages TO WARNING;")
                demo_user_id = ensure_demo_user(conn)
                ins_items, up_items, skipped_incomplete = seed_items(conn, demo_user_id, export_items, export_chunks)
                ins_chunks, up_chunks = (0, 0)
                if export_chunks:
                    ins_chunks, up_chunks = seed_chunks(conn, demo_user_id, export_items, export_chunks)
                conn.commit()
            break
        except Exception as e:
            last_err = e
            if time.time() - start > 60:
                print(f"Timed out waiting for schema: {e}", file=sys.stderr)
                return 1
            time.sleep(1.0)
    print(
        f"Seed complete: items(inserted/updated/skipped_incomplete)={ins_items}/{up_items}/{skipped_incomplete}, "
        f"chunks(inserted/updated)={ins_chunks}/{up_chunks}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

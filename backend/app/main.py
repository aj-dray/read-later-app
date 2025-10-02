from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
import json
from typing import Any, AsyncGenerator, Literal

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from dotenv import load_dotenv

# Load environment before importing modules that may read env at import time
load_dotenv()

from . import database as db
from . import services

from . import auth
from . import schemas
from psycopg import errors
import secrets
import string


# === CONFIGURATION ===


# load_dotenv() already called above to ensure env is available during imports


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    await db.init_pool()
    await db.init_database()
    yield
    # Shutdown
    await db.close_pool()


app = FastAPI(title="Later System Service", lifespan=lifespan)

"""Track running background pipeline tasks per item to allow cancellation."""
_RUNNING_PIPELINE_TASKS: dict[str, asyncio.Task[None]] = {}


# === MIDDLEWARE ===


@app.middleware("http")
async def attach_session(request: Request, call_next):
    request.state.session = auth.get_session(request)
    response = await call_next(request)
    return response


# === AUTH ===


@app.post("/auth/login")
async def login(username: str = Body(...), password: str = Body(...)) -> dict[str, Any]:
    user = await db.authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = auth.create_jwt_token(user["user_id"], user["username"])
    return {"access_token": token, "token_type": "bearer"}


# === USERS ===


@app.get("/user/me")
async def get_current_user(session: dict = Depends(auth.require_session)) -> dict:
    return {
        "user_id": session.get("user_id"),
        "username": session.get("username"),
    }


@app.post("/user/add", status_code=201)
async def add_user(username: str = Body(...), password: str = Body(...)) -> dict:
    try:
        user_id = await db.create_user(username, password)
        return {"user_id": user_id, "username": username}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# Removed public change-password endpoint per security requirement.


def _random_password(length: int = 6) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _generate_unique_demo_username() -> str:
    """Generate a unique username of the form 'demo{id}'."""
    # We attempt a simple numeric suffix strategy to keep usernames readable.
    # Try successive integers until insert succeeds (bounded attempts for safety).
    for attempt in range(1, 10000):
        candidate = f"demo{attempt}"
        existing = await db.get_user_by_username(candidate)
        if not existing:
            return candidate
    # Fallback to a random suffix if sequential strategy fails unexpectedly
    return f"demo{secrets.randbelow(10_000_000)}"


@app.post("/demo/request", status_code=201)
async def request_demo_account() -> dict:
    """Provision a new demo account cloned from the base 'demo' user.

    Returns the generated username and a 6-character password.
    """
    source = await db.get_user_by_username("demo")
    if not source:
        raise HTTPException(status_code=404, detail="Base demo account not found")

    username = await _generate_unique_demo_username()
    password = _random_password(6)

    try:
        new_user_id = await db.create_user(username, password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Unable to create demo user") from exc

    # Clone items and item_chunks from base demo user
    try:
        await db.clone_user_data(source_user_id=str(source["id"]), target_user_id=str(new_user_id))
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Failed to clone demo data") from exc

    return {"username": username, "password": password}


# === ITEMS ===


async def _process_item_pipeline(*, item_id: str, url: str, user_id: str) -> None:
    """Run the expensive extraction pipeline asynchronously.

    We fan the work out in a background task so the HTTP response can return
    immediately, allowing clients to poll for incremental updates.
    """

    def _exc_info(exc: BaseException | None):
        if exc is None:
            return None
        return (exc.__class__, exc, exc.__traceback__)

    async def _mark_item_error(
        error_message: str,
        *,
        exc: BaseException | None = None,
    ) -> None:
        """Mark item as failed, log, and persist error state."""
        log_extra = {"item_id": item_id, "user_id": user_id}
        logger.error(error_message, extra=log_extra, exc_info=_exc_info(exc))

        try:
            now = datetime.now()
            await db.update_item(
                {
                    "client_status": "error",
                    "client_status_at": now,
                },
                item_id=item_id,
                user_id=user_id,
            )
        except Exception as update_error:
            logger.error(
                "Failed to mark item as error",
                extra=log_extra,
                exc_info=_exc_info(update_error),
            )

    def _strip_client_status(payload: dict[str, Any]) -> dict[str, Any]:
        if "client_status" in payload:
            copied = dict(payload)
            copied.pop("client_status", None)
            return copied
        return payload

    try:
        item_updates = await services.extract_data(url)
    except Exception as exc:  # pragma: no cover - defensive logging for external services
        await _mark_item_error("Extraction failed", exc=exc)
        return

    if not item_updates:
        await _mark_item_error("Extraction returned no metadata")
        return

    if isinstance(item_updates, dict):
        item_updates = _strip_client_status(item_updates)

    # Abort if the item was deleted during extraction
    try:
        exists = await db.get_item(item_id, ["id"], user_id)
    except Exception:
        exists = None
    if not exists:
        return

    try:
        item = await db.update_item(item_updates, item_id=item_id, user_id=user_id)
    except ValueError as exc:
        await _mark_item_error("Failed to persist extraction updates", exc=exc)
        return
    except Exception as exc:
        await _mark_item_error("Unexpected error updating item metadata", exc=exc)
        return

    if item is None:
        await _mark_item_error("Item missing after extraction stage")
        return

    # Abort if the item was deleted before summary
    try:
        exists = await db.get_item(item_id, ["id"], user_id)
    except Exception:
        exists = None
    if not exists:
        return

    try:
        summary_updates = await services.generate_data(item, user_id=user_id)
        if isinstance(summary_updates, dict):
            summary_updates = _strip_client_status(summary_updates)
        item = await db.update_item(summary_updates, item_id=item_id, user_id=user_id)
    except ValueError as exc:
        await _mark_item_error("Failed to persist summary updates", exc=exc)
        return
    except Exception as exc:  # pragma: no cover - defensive logging for external services
        await _mark_item_error("Summary generation failed", exc=exc)
        return

    if item is None:
        await _mark_item_error("Item missing after summary stage")
        return

    # Abort if the item was deleted before embedding
    try:
        exists = await db.get_item(item_id, ["id"], user_id)
    except Exception:
        exists = None
    if not exists:
        return

    try:
        embed_updates, item_chunks = await services.index_item(
            item, item_id=item_id, user_id=user_id
        )
        if isinstance(embed_updates, dict):
            embed_updates = _strip_client_status(embed_updates)

        # Add client_status update to the same transaction as embedding
        embed_updates.update({
            "client_status": "queued",
            "client_status_at": datetime.now(),
        })

        updated_item = await db.update_item(
            embed_updates,
            item_id=item_id,
            user_id=user_id,
        )
        await db.add_item_chunks(item_id=item_id, chunks=item_chunks)
        if updated_item is None:
            await _mark_item_error("Item missing after embedding stage")
    except ValueError as exc:
        await _mark_item_error("Failed to persist embedding updates", exc=exc)
    except Exception as exc:  # pragma: no cover - defensive logging for external services
        await _mark_item_error("Embedding failed", exc=exc)


@app.post("/items/add", status_code=201)
async def add_item(
    url: str = Body(..., embed=True),
    session: dict = Depends(auth.require_session),
) -> dict[str, str]:
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user context")

    submitted_url = url.strip()
    saved_at = datetime.now()

    base_item = {
        "url": submitted_url,
        "client_status": "adding",
        "client_status_at": saved_at,
        "server_status": "saved",
        "server_status_at": saved_at,
        "user_id": user_id,
    }

    try:
        item = await db.create_item(base_item)
    except errors.UniqueViolation as exc:
        # URL already exists for this user – log for visibility then return 409
        logger.warning(
            "Duplicate item add attempt",
            extra={"user_id": user_id, "url": submitted_url},
            exc_info=None,
        )
        raise HTTPException(status_code=409, detail="URL already exists") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="Unable to create item") from exc

    item_id = item["id"]

    # Trigger the pipeline asynchronously so clients can stream updates
    task = asyncio.create_task(
        _process_item_pipeline(item_id=item_id, url=submitted_url, user_id=user_id),
        name=f"process-item-{item_id}",
    )
    _RUNNING_PIPELINE_TASKS[item_id] = task
    def _cleanup(_):
        _RUNNING_PIPELINE_TASKS.pop(item_id, None)
    task.add_done_callback(_cleanup)

    return {"item_id": item_id}


@app.get("/items/select")
async def get_items(
    *,
    columns: list[str] | None = Query(
        default=None,
        description="Columns to select (defaults to all public columns)",
    ),
    filters: list[str] | None = Query(
        default=None,
        description="Filters in format 'column:operator:value' (e.g., 'client_status:IN:saved,queued')",
        alias="filter"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order_by: str | None = Query(
        default="created_at",
        description="Column to order by",
    ),
    order: Literal["asc", "desc"] = Query("desc"),
    session: dict = Depends(auth.require_session),
) -> list[dict]:
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user context")

    # Use default columns if none specified
    selected_columns = columns if columns else schemas.ITEM_PUBLIC_COLS

    # Validate columns
    invalid_columns = [col for col in selected_columns if col not in schemas.ITEM_PUBLIC_COLS]
    if invalid_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid columns: {invalid_columns}"
        )

    # Parse filters
    parsed_filters = []
    if filters:
        for filter_str in filters:
            try:
                parts = filter_str.split(":", 2)
                if len(parts) != 3:
                    raise ValueError("Filter must have format 'column:operator:value'")

                column, operator, value_str = parts

                # Validate column
                if column not in schemas.ITEM_PUBLIC_COLS:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid filter column: {column}"
                    )

                # Parse value based on operator
                if operator.upper() == "IN":
                    value = value_str.split(",")
                else:
                    value = value_str

                parsed_filters.append((column, operator.upper(), value))

            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid filter format: {filter_str}. {str(e)}"
                )
    # Validate order_by column
    if order_by and order_by not in schemas.ITEM_PUBLIC_COLS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid order_by column: {order_by}"
        )

    rows = await db.get_items(
        columns=selected_columns,
        filters=parsed_filters,
        user_id=user_id,
        limit=limit,
        offset=offset,
        order_by=order_by,
        order_direction=order,
    )
    return rows


@app.post("/items/update")
async def update_items(
    *,
    item_ids: list[str] = Body(..., embed=True),
    updates: dict[str, Any] = Body(..., embed=True),
    session: dict = Depends(auth.require_session),
) -> dict:
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user context")

    if not item_ids:
        raise HTTPException(status_code=400, detail="No item_ids provided")
    if not isinstance(updates, dict) or not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    results: dict[str, dict[str, Any]] = {}
    for item_id in item_ids:
        try:
            item = await db.update_item(updates, item_id=item_id, user_id=user_id)
            if item is None:
                results[item_id] = {"updated": False, "error": "Not found"}
            else:
                results[item_id] = {"updated": True}
        except ValueError as exc:
            results[item_id] = {"updated": False, "error": str(exc)}
        except Exception as exc:
            results[item_id] = {"updated": False, "error": "Unexpected error"}

    return {"results": results}


@app.post("/items/delete")
async def delete_items(
    *,
    item_ids: list[str] = Body(..., embed=True),
    session: dict = Depends(auth.require_session),
) -> dict:
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user context")

    if not item_ids:
        raise HTTPException(status_code=400, detail="No item_ids provided")

    results: dict[str, bool] = {}
    for item_id in item_ids:
        try:
            deleted = await db.delete_item(item_id=item_id, user_id=user_id)
        except Exception:
            deleted = False
        results[item_id] = deleted

        # Cancel any running background task for this item
        task = _RUNNING_PIPELINE_TASKS.pop(item_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    return {"results": results}


# === CLUSTERING ===


@app.get("/clusters/dimensional-reduction")
async def generate_graph(
    request: Request,
    item_ids: list[str] = Query(...),
    mode: Literal["pca", "tsne", "umap"] = Query("umap"),
    session: dict = Depends(auth.require_session),
) -> dict:
    user_id = session.get("user_id")
    rows = await db.get_items(
        columns=["id", "mistral_embedding"],
        filters=[("id", "IN", item_ids)],
        user_id=user_id,
        limit=None
    )
    # Extract extra parameters from query string
    kwargs = {}
    known_params = {"item_ids", "mode"}
    for key, value in request.query_params.items():
        if key not in known_params:
            # Try to convert to appropriate type
            try:
                if '.' in value:
                    kwargs[key] = float(value)
                else:
                    kwargs[key] = int(value)
            except ValueError:
                kwargs[key] = value

    if mode == "pca":
        reduced_embeddings = services.clustering.pca(rows, d=2, **kwargs)
    elif mode == "tsne":
        reduced_embeddings = services.clustering.tsne(rows, d=2, **kwargs)
    elif mode == "umap":
        reduced_embeddings = services.clustering.umap(rows, d=2, **kwargs)

    ordered_ids = [row["id"] for row in rows]

    return {
        "reduced_embeddings": reduced_embeddings.tolist(),
        "item_ids": ordered_ids,
    }


@app.get("/clusters/generate")
async def get_clustering(
    request: Request,
    item_ids: list[str] = Query(...),
    mode: Literal["kmeans", "hca", "dbscan"] = Query("kmeans"),
    session: dict = Depends(auth.require_session),
) -> dict:
    user_id = session.get("user_id")

    rows = await db.get_items(
        columns=["id", "mistral_embedding"],
        filters=[("id", "IN", item_ids)],
        user_id=user_id,
        limit=None
    )

    # Extract extra parameters from query string
    kwargs = {}
    known_params = {"item_ids", "mode"}
    for key, value in request.query_params.items():
        if key not in known_params:
            # Try to convert to appropriate type
            try:
                if '.' in value:
                    kwargs[key] = float(value)
                else:
                    kwargs[key] = int(value)
            except ValueError:
                kwargs[key] = value

    if mode == "kmeans":
        clusters = services.clustering.kmeans(rows, **kwargs)
    elif mode == "hca":
        clusters = services.clustering.hca(rows, **kwargs)
    elif mode == "dbscan":
        clusters = services.clustering.dbscan(rows, **kwargs)

    ordered_ids = [row["id"] for row in rows]

    return {
        "clusters": clusters.tolist(),
        "item_ids": ordered_ids,
    }


@app.get("/clusters/label")
async def get_cluster_labels(
    *,
    item_ids: list[str] = Query(...),
    clusters: str = Query(..., description="JSON encoded list of cluster definitions"),
    session: dict = Depends(auth.require_session)
) -> dict:
    user_id = session.get("user_id")

    rows = await db.get_items(
        columns=["id", "summary"],
        filters=[("id", "IN", item_ids)],
        user_id=user_id,
        limit=None
    )

    try:
        parsed_clusters = json.loads(clusters)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid clusters payload") from exc

    if not isinstance(parsed_clusters, list):
        raise HTTPException(status_code=400, detail="Clusters payload must be a list")

    if len(parsed_clusters) != len(item_ids):
        raise HTTPException(status_code=400, detail="Clusters payload length must match item IDs")

    # Database results for an IN clause are not guaranteed to preserve order, so align them
    # manually with the item_ids sequence the frontend used when preparing clusters.
    rows_by_id = {row["id"]: row for row in rows}
    ordered_rows: list[dict[str, Any]] = []
    ordered_clusters: list[int] = []

    for idx, item_id in enumerate(item_ids):
        row = rows_by_id.get(item_id)
        if row is None:
            # Skip missing rows to avoid misaligning cluster indices with summaries
            continue
        ordered_rows.append(row)
        ordered_clusters.append(parsed_clusters[idx])

    labels = services.clustering.label(ordered_clusters, ordered_rows)

    return {"labels": labels}


# === SEARCH ===


@app.get("/items/search")
async def search_items(
    query: str = Query(...),
    mode: Literal["lexical", "semantic"] = Query("lexical"),
    scope: Literal["items", "chunks"] = Query("items"),
    limit: int = Query(10, ge=1, le=100),
    columns: list[str] | None = Query(None),
    session: dict = Depends(auth.require_session),
) -> dict:
    user_id = session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user context")

    if mode == "lexical":
        search_results = await services.searching.lexical(
            user_id=user_id,
            query=query,
            mode=mode,
            scope=scope,
            limit=limit,
            columns=columns,
        )
    elif mode == "semantic":
        search_results = await services.searching.semantic(
            user_id=user_id,
            query=query,
            scope=scope,
            limit=limit,
            columns=columns,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Invalid search mode: {mode}")

    return {"results": search_results}


# === USER SETTINGS ===


@app.get("/user/settings/{setting_type}/{setting_key}")
async def get_user_setting(
    setting_type: str,
    setting_key: str,
    session: dict = Depends(auth.require_session)
) -> dict[str, Any]:
    """Get a specific user setting."""
    user_id = session.get("user_id")
    setting_value = await db.get_user_setting(user_id, setting_type, setting_key)
    return {"setting_value": setting_value or {}}


@app.get("/user/settings/{setting_type}")
async def get_user_settings_by_type(
    setting_type: str,
    session: dict = Depends(auth.require_session)
) -> dict[str, Any]:
    """Get all user settings of a specific type."""
    user_id = session.get("user_id")
    settings = await db.get_user_settings_by_type(user_id, setting_type)
    return {"settings": settings}


@app.put("/user/settings/{setting_type}/{setting_key}")
async def set_user_setting(
    setting_type: str,
    setting_key: str,
    setting_value: dict[str, Any] = Body(...),
    session: dict = Depends(auth.require_session),
) -> dict[str, Any]:
    """Set a user setting."""
    user_id = session.get("user_id")
    await db.set_user_setting(user_id, setting_type, setting_key, setting_value)
    return {"success": True}


@app.patch("/user/settings/{setting_type}/{setting_key}")
async def update_user_setting_field(
    setting_type: str,
    setting_key: str,
    field_key: str = Body(...),
    field_value: Any = Body(...),
    session: dict = Depends(auth.require_session),
) -> dict[str, Any]:
    """Update a single field within a user setting."""
    user_id = session.get("user_id")
    await db.update_user_setting_field(user_id, setting_type, setting_key, field_key, field_value)
    return {"success": True}


if __name__ == "__main__":
    pass

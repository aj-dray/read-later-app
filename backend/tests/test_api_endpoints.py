"""API endpoint tests for Later System backend using pytest-asyncio."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_authentication_required(async_client: AsyncClient):
    """Test that authentication is required for protected endpoints."""
    response = await async_client.get("/items/select")
    assert response.status_code == 401, response.text


@pytest.mark.asyncio
async def test_user_registration_and_login(async_client: AsyncClient, database):
    """Test user registration and login flow."""
    # Generate unique username for test
    username = f"user_{uuid.uuid4().hex[:12]}"
    password = "testpass123"
    
    # Register user
    response = await async_client.post(
        "/user/add", json={"username": username, "password": password}
    )
    assert response.status_code == 201, response.text
    user_payload = response.json()
    user_id = user_payload.get("user_id")
    assert user_id, f"Missing user_id in response: {user_payload}"
    
    # Login with created user
    login_response = await async_client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert login_response.status_code == 200, login_response.text
    token_payload = login_response.json()
    token = token_payload.get("access_token")
    assert token, f"Missing access_token in response: {token_payload}"


@pytest.mark.asyncio
async def test_items_crud_flow(async_client: AsyncClient, database):
    """Test complete item CRUD operations flow."""
    # Setup user
    username = f"user_{uuid.uuid4().hex[:12]}"
    password = "testpass123"
    
    # Register user
    reg_response = await async_client.post(
        "/user/add", json={"username": username, "password": password}
    )
    assert reg_response.status_code == 201
    user_id = reg_response.json().get("user_id")
    
    # Login
    login_response = await async_client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert login_response.status_code == 200
    token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create item
    now = datetime.now(timezone.utc)
    item_url = f"https://example.com/{uuid.uuid4().hex}"
    item_payload = {
        "url": item_url,
        "client_status": "adding",
        "client_status_at": now.isoformat(),
        "server_status": "saved",
        "server_status_at": now.isoformat(),
        "user_id": user_id,
        "title": "Testing article",
        "content_text": "This content is used for verifying item flows.",
    }
    
    created_item = await database.create_item(item_payload)
    item_id = str(created_item.get("id"))
    assert item_id, f"Failed to create item with payload: {item_payload}"
    
    # Select items
    select_response = await async_client.get("/items/select", headers=headers)
    assert select_response.status_code == 200, select_response.text
    items = select_response.json()
    assert any(row.get("id") == item_id for row in items), f"Created item {item_id} not in items list"
    
    # Update item
    update_response = await async_client.post(
        "/items/update",
        headers=headers,
        json={
            "item_ids": [item_id],
            "updates": {"client_status": "completed"},
        },
    )
    assert update_response.status_code == 200, update_response.text
    update_payload = update_response.json()["results"][item_id]
    assert update_payload["updated"] is True, f"Update failed: {update_payload}"
    
    # Verify update with filtered select
    filtered_response = await async_client.get(
        "/items/select",
        headers=headers,
        params=[("filter", f"id:=:{item_id}"), ("columns", "id"), ("columns", "client_status")],
    )
    assert filtered_response.status_code == 200, filtered_response.text
    filtered_items = filtered_response.json()
    assert filtered_items and filtered_items[0]["client_status"] == "completed", \
           f"Item update not reflected: {filtered_items}"
    
    # Delete item
    delete_response = await async_client.post(
        "/items/delete",
        headers=headers,
        json={"item_ids": [item_id]},
    )
    assert delete_response.status_code == 200, delete_response.text
    delete_payload = delete_response.json()["results"]
    assert delete_payload[item_id] is True, f"Delete operation failed: {delete_payload}"
    
    # Verify deletion
    final_response = await async_client.get("/items/select", headers=headers)
    assert final_response.status_code == 200, final_response.text
    assert not any(item.get("id") == item_id for item in final_response.json()), \
           "Item still exists after deletion"


@pytest.mark.asyncio
async def test_items_search_lexical(async_client: AsyncClient, database):
    """Test lexical search functionality."""
    # Setup user
    username = f"user_{uuid.uuid4().hex[:12]}"
    password = "testpass123"
    
    # Register and login
    reg_response = await async_client.post(
        "/user/add", json={"username": username, "password": password}
    )
    user_id = reg_response.json().get("user_id")
    
    login_response = await async_client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create test item
    now = datetime.now(timezone.utc)
    item_payload = {
        "url": f"https://example.com/{uuid.uuid4().hex}",
        "client_status": "adding",
        "client_status_at": now.isoformat(),
        "server_status": "saved",
        "server_status_at": now.isoformat(),
        "user_id": user_id,
        "title": "Python Testing",
        "content_text": "Python testing strategies and fixtures are useful.",
        "summary": "Notes on Python testing.",
    }
    
    created_item = await database.create_item(item_payload)
    item_id = str(created_item.get("id"))
    assert item_id
    
    # Perform lexical search
    search_response = await async_client.get(
        "/items/search",
        headers=headers,
        params={
            "query": "testing",  # lexical search should find the content text
            "mode": "lexical",
            "scope": "items",
            "limit": 5,
        },
    )
    assert search_response.status_code == 200, search_response.text
    results = search_response.json()["results"]
    assert results, "Expected at least one search result"
    assert any(row.get("id") == item_id for row in results), \
           f"Search didn't return expected item {item_id}"
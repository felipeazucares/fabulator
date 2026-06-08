"""Integration tests for the normalised adjacency-list node model.

These tests exercise the new Work CRUD, Node CRUD, Node Navigation,
Node Update/Delete, Reorder, and Duplicate endpoints.

Requires live MongoDB Atlas and Redis. Run with:
    pytest tests/test_integration_normalised.py -v --timeout=60
"""

import asyncio
import os
import re
import uuid

import httpx
import motor.motor_asyncio
import pytest
from fastapi.encoders import jsonable_encoder
from httpx import ASGITransport
from passlib.context import CryptContext

import app.api as api
import app.database as database

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_work(ac, headers, title="Test Work", author=None, tags=None):
    body = {"title": title}
    if author:
        body["author"] = author
    if tags:
        body["tags"] = tags
    resp = await ac.post("/works", json=body, headers=headers)
    return resp


async def _create_node(ac, headers, work_id, node_type, tag, parent_id=None):
    body = {
        "work_id": work_id,
        "node_type": node_type,
        "tag": tag,
    }
    if parent_id is not None:
        body["parent_id"] = parent_id
    resp = await ac.post("/nodes", json=body, headers=headers)
    return resp


async def _create_hierarchy(ac, headers, work_id, depth=4):
    """Create Part -> Chapter -> Scene -> Beat and return list of node_ids."""
    ids = []
    r = await _create_node(ac, headers, work_id, "part", "Part One")
    assert r.status_code == 201
    part_id = r.json()["node_id"]
    ids.append(part_id)

    r = await _create_node(ac, headers, work_id, "chapter", "Chapter 1", parent_id=part_id)
    assert r.status_code == 201
    ch_id = r.json()["node_id"]
    ids.append(ch_id)

    r = await _create_node(ac, headers, work_id, "scene", "Scene 1", parent_id=ch_id)
    assert r.status_code == 201
    sc_id = r.json()["node_id"]
    ids.append(sc_id)

    r = await _create_node(ac, headers, work_id, "beat", "Beat 1", parent_id=sc_id)
    assert r.status_code == 201
    ids.append(r.json()["node_id"])

    return ids  # [part_id, chapter_id, scene_id, beat_id]


async def _create_work_and_hierarchy(ac, headers, author=None):
    """Create a work with a full hierarchy. Returns (work_id, ids)."""
    r = await _create_work(ac, headers, title="Test Novel", author=author)
    assert r.status_code == 201
    work_id = r.json()["work_id"]
    ids = await _create_hierarchy(ac, headers, work_id)
    return work_id, ids


async def _count_nodes(motor_client, work_id=None, account_id=None):
    db = motor_client.fabulator
    query = {}
    if work_id:
        query["work_id"] = work_id
    if account_id:
        query["account_id"] = account_id
    return await db.node_collection.count_documents(query)


async def _delete_user(motor_client, username):
    db_storage = database.UserStorage(collection_name="user_collection", client=motor_client)
    user = await db_storage.get_user_details_by_username(username)
    if user is not None:
        await db_storage.delete_user_details_by_account_id(account_id=user.account_id)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def motor_client():
    client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGO_DETAILS"))
    yield client
    client.close()


@pytest.fixture(autouse=True)
def setup_app_state(motor_client):
    api.app.state.motor_client = motor_client
    api.oauth.set_client(motor_client)


_FULL_SCOPES = "user:reader user:writer tree:reader tree:writer usertype:writer"


def _make_main_user_dict():
    suffix = os.urandom(4).hex()
    return {
        "name": {"firstname": "Test", "surname": "User"},
        "username": f"int_test_user_{suffix}",
        "password": "test_password",
        "account_id": None,
        "email": f"test_{suffix}@example.com",
        "disabled": False,
        "user_role": _FULL_SCOPES,
        "user_type": "free",
    }


def _make_iso_user_dict():
    suffix = os.urandom(4).hex()
    return {
        "name": {"firstname": "Isolation", "surname": "User"},
        "username": f"int_iso_user_{suffix}",
        "password": "iso_password",
        "account_id": None,
        "email": f"iso_{suffix}@example.com",
        "disabled": False,
        "user_role": _FULL_SCOPES,
        "user_type": "free",
    }


@pytest.fixture
async def main_user(motor_client):
    """Create test user, return (headers, username)."""
    user = _make_main_user_dict()
    await _delete_user(motor_client, user["username"])
    async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
        resp = await ac.post("/users", json=jsonable_encoder(user))
    assert resp.status_code == 200
    form_data = {
        "username": user["username"],
        "password": user["password"],
        "scope": user["user_role"],
    }
    async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
        resp = await ac.post("/get_token", data=form_data)
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user["username"]


@pytest.fixture
async def iso_user(motor_client):
    """Create isolation user with full scopes. Returns headers."""
    user = _make_iso_user_dict()
    await _delete_user(motor_client, user["username"])
    async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
        resp = await ac.post("/users", json=jsonable_encoder(user))
    assert resp.status_code == 200
    form_data = {
        "username": user["username"],
        "password": user["password"],
        "scope": user["user_role"],
    }
    async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
        resp = await ac.post("/get_token", data=form_data)
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(params=["user:reader", "user:writer", "tree:reader", "tree:writer", "usertype:writer"])
async def scoped_user(motor_client, request):
    """Create user with a single scope. Yields (headers, scope_string)."""
    scope = request.param
    suffix = os.urandom(4).hex()
    user = {
        "name": {"firstname": "Scoped", "surname": "User"},
        "username": f"int_scoped_{suffix}",
        "password": "scoped_pass",
        "account_id": None,
        "email": f"scoped_{suffix}@example.com",
        "disabled": False,
        "user_role": scope,
        "user_type": "free",
    }
    await _delete_user(motor_client, user["username"])
    async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
        resp = await ac.post("/users", json=jsonable_encoder(user))
    assert resp.status_code == 200
    form_data = {
        "username": user["username"],
        "password": user["password"],
        "scope": scope,
    }
    async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
        resp = await ac.post("/get_token", data=form_data)
    assert resp.status_code == 200
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return headers, scope


@pytest.fixture
async def work_id(main_user, motor_client):
    """Create a work and return its work_id. Cleans up on teardown."""
    headers, _ = main_user
    async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
        r = await _create_work(ac, headers)
    assert r.status_code == 201
    wid = r.json()["work_id"]
    yield wid


# ===========================================================================
# T-46: Work CRUD (22 tests)
# ===========================================================================


class TestWorkCRUD:
    """T-46: Integration tests for Work CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_t_work_01_create_work_happy(self, main_user):
        """T-WORK-01: POST /works returns 201 with valid WorkResponse."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_work(ac, headers, title="My Novel", author="Jane Doe", tags=["fiction"])
        assert r.status_code == 201
        body = r.json()
        assert "work_id" in body
        assert re.match(UUID_PATTERN, body["work_id"])
        assert body["title"] == "My Novel"
        assert body["author"] == "Jane Doe"
        assert body["tags"] == ["fiction"]
        assert "account_id" not in body
        assert body.get("created_at") is not None
        assert body.get("updated_at") is not None

    @pytest.mark.asyncio
    async def test_t_work_02_create_work_whitespace_title(self, main_user):
        """T-WORK-02: POST /works with whitespace-only title returns 422."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post("/works", json={"title": "   "}, headers=headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_t_work_03_create_work_empty_title(self, main_user):
        """T-WORK-03: POST /works with empty title returns 422."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post("/works", json={"title": ""}, headers=headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_t_work_04_create_work_51_tags(self, main_user):
        """T-WORK-04: POST /works with 51 tags returns 422."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post("/works", json={"title": "X", "tags": [f"t{i}" for i in range(51)]}, headers=headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_t_work_05_create_work_empty_tag(self, main_user):
        """T-WORK-05: POST /works with empty tag in list returns 422."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post("/works", json={"title": "X", "tags": ["valid", ""]}, headers=headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_t_work_06_create_work_no_auth(self):
        """T-WORK-06: POST /works without auth returns 401."""
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post("/works", json={"title": "X"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_t_work_07_create_work_reader_scope(self, scoped_user):
        """T-WORK-07: POST /works with tree:reader only returns 403."""
        headers, scope = scoped_user
        if "tree:writer" in scope:
            pytest.skip("token has tree:writer scope")
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post("/works", json={"title": "X"}, headers=headers)
        assert r.status_code == 403

    # --- List Works ---

    @pytest.mark.asyncio
    async def test_t_work_08_list_works_multiple(self, main_user, motor_client):
        """T-WORK-08: GET /works returns works ordered by created_at desc."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r1 = await _create_work(ac, headers, title="First")
            assert r1.status_code == 201
            import asyncio
            await asyncio.sleep(0.01)
            r2 = await _create_work(ac, headers, title="Second")
            assert r2.status_code == 201
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get("/works", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        assert data[0]["created_at"] >= data[1]["created_at"]

    @pytest.mark.asyncio
    async def test_t_work_09_list_works_no_auth(self):
        """T-WORK-09: GET /works without auth returns 401."""
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get("/works")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_t_work_10_list_works_reader_missing(self, scoped_user):
        """T-WORK-10: GET /works without tree:reader returns 403."""
        headers, scope = scoped_user
        if "tree:reader" in scope:
            pytest.skip("token has tree:reader scope")
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get("/works", headers=headers)
        assert r.status_code == 403

    # --- Get Single Work ---

    @pytest.mark.asyncio
    async def test_t_work_11_get_work_happy(self, work_id, main_user):
        """T-WORK-11: GET /works/{id} returns 200 with WorkResponse."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["work_id"] == work_id
        assert "account_id" not in r.json()

    @pytest.mark.asyncio
    async def test_t_work_12_get_work_not_found(self, main_user):
        """T-WORK-12: GET /works/{nonexistent} returns 404."""
        headers, _ = main_user
        fake_id = str(uuid.uuid4())
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{fake_id}", headers=headers)
        assert r.status_code == 404
        assert r.json()["detail"] == "Work not found"

    @pytest.mark.asyncio
    async def test_t_work_13_get_work_isolation(self, work_id, iso_user):
        """T-WORK-13: GET /works/{other's id} returns 404 (isolation)."""
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}", headers=iso_user)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_work_14_get_work_invalid_uuid(self, main_user):
        """T-WORK-14: GET /works/not-a-uuid returns 422."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get("/works/not-a-uuid", headers=headers)
        assert r.status_code == 422

    # --- Update Work ---

    @pytest.mark.asyncio
    async def test_t_work_15_update_work_happy(self, work_id, main_user):
        """T-WORK-15: PUT /works/{id} returns 200 with updated fields."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/works/{work_id}", json={"title": "Updated"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["title"] == "Updated"

    @pytest.mark.asyncio
    async def test_t_work_16_update_work_author_cascade(self, work_id, main_user, motor_client):
        """T-WORK-16: PUT /works/{id} author updates all child nodes."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            await _create_node(ac, headers, work_id, "part", "P1")
            r = await ac.put(f"/works/{work_id}", json={"author": "New Author"}, headers=headers)
        assert r.status_code == 200
        db = motor_client.fabulator
        nodes = await db.node_collection.find({"work_id": work_id}).to_list(None)
        assert len(nodes) > 0
        for n in nodes:
            assert n["author"] == "New Author"

    @pytest.mark.asyncio
    async def test_t_work_17_update_work_not_found(self, main_user):
        """T-WORK-17: PUT /works/{nonexistent} returns 404."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/works/{str(uuid.uuid4())}", json={"title": "X"}, headers=headers)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_work_18_update_work_isolation(self, work_id, iso_user):
        """T-WORK-18: PUT /works/{other's id} returns 404."""
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/works/{work_id}", json={"title": "X"}, headers=iso_user)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_work_19_update_work_empty_title(self, work_id, main_user):
        """T-WORK-19: PUT /works/{id} with empty title returns 422."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/works/{work_id}", json={"title": ""}, headers=headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_t_work_20_update_work_writer_scope(self, work_id, scoped_user):
        """T-WORK-20: PUT /works/{id} with tree:reader only returns 403."""
        headers, scope = scoped_user
        if "tree:writer" in scope:
            pytest.skip("token has tree:writer scope")
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/works/{work_id}", json={"title": "X"}, headers=headers)
        assert r.status_code == 403

    # --- Delete Work ---

    @pytest.mark.asyncio
    async def test_t_work_21_delete_work_with_nodes(self, main_user, motor_client):
        """T-WORK-21: DELETE /works/{id} removes work and all nodes."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_work(ac, headers, title="ToDelete")
            work_id = r.json()["work_id"]
            for i in range(3):
                await _create_node(ac, headers, work_id, "part", f"P{i}")
            r = await ac.delete(f"/works/{work_id}", headers=headers)
        assert r.status_code == 200
        assert "3 node(s) removed" in r.json()["detail"]
        db = motor_client.fabulator
        assert await db.work_collection.count_documents({"work_id": work_id}) == 0
        assert await db.node_collection.count_documents({"work_id": work_id}) == 0

    @pytest.mark.asyncio
    async def test_t_work_22_delete_work_no_nodes(self, work_id, main_user):
        """T-WORK-22: DELETE /works/{id} with 0 nodes returns 200."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.delete(f"/works/{work_id}", headers=headers)
        assert r.status_code == 200
        assert "0 node(s) removed" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_t_work_23_delete_work_not_found(self, main_user):
        """T-WORK-23: DELETE /works/{nonexistent} returns 404."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.delete(f"/works/{str(uuid.uuid4())}", headers=headers)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_work_24_delete_work_isolation(self, work_id, iso_user):
        """T-WORK-24: DELETE /works/{other's id} returns 404."""
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.delete(f"/works/{work_id}", headers=iso_user)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_work_25_delete_work_writer_scope(self, work_id, scoped_user):
        """T-WORK-25: DELETE /works/{id} with tree:reader only returns 403."""
        headers, scope = scoped_user
        if "tree:writer" in scope:
            pytest.skip("token has tree:writer scope")
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.delete(f"/works/{work_id}", headers=headers)
        assert r.status_code == 403


# ===========================================================================
# T-47: Node CRUD — Create + List + Read (25 tests)
# ===========================================================================


class TestNodeCreate:
    """T-47: Integration tests for Node creation, listing, and reading."""

    # --- Create Node ---

    @pytest.mark.asyncio
    async def test_t_create_01_root_part(self, work_id, main_user):
        """T-CREATE-01: POST /nodes creates root Part with position 0."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "part", "Part One")
        assert r.status_code == 201
        body = r.json()
        assert body["node_type"] == "part"
        assert body["parent_id"] is None
        assert body["position"] == 0
        assert re.match(UUID_PATTERN, body["node_id"])
        assert "account_id" not in body

    @pytest.mark.asyncio
    async def test_t_create_02_child_chapter(self, work_id, main_user):
        """T-CREATE-02: POST /nodes creates child Chapter under Part."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "part", "P1")
            part_id = r.json()["node_id"]
            r = await _create_node(ac, headers, work_id, "chapter", "Ch1", parent_id=part_id)
        assert r.status_code == 201
        body = r.json()
        assert body["node_type"] == "chapter"
        assert body["parent_id"] == part_id
        assert body["position"] == 0

    @pytest.mark.asyncio
    async def test_t_create_03_author_copied_from_work(self, main_user, motor_client):
        """T-CREATE-03: Node author is copied from Work."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_work(ac, headers, title="Authored", author="Alice")
            assert r.status_code == 201
            work_id = r.json()["work_id"]
            r = await _create_node(ac, headers, work_id, "part", "P1")
        assert r.status_code == 201
        assert r.json()["author"] == "Alice"

    @pytest.mark.asyncio
    async def test_t_create_04_position_increment(self, work_id, main_user):
        """T-CREATE-04: Third sibling gets position 2."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            for i in range(3):
                r = await _create_node(ac, headers, work_id, "part", f"P{i}")
                assert r.status_code == 201
                assert r.json()["position"] == i

    @pytest.mark.asyncio
    async def test_t_create_05_work_not_found(self, main_user):
        """T-CREATE-05: POST /nodes with nonexistent work_id returns 404."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, str(uuid.uuid4()), "part", "P1")
        assert r.status_code == 404
        assert r.json()["detail"] == "Work not found"

    @pytest.mark.asyncio
    async def test_t_create_06_work_isolation(self, work_id, iso_user):
        """T-CREATE-06: POST /nodes with cross-account work_id returns 404."""
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, iso_user, work_id, "part", "P1")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_create_07_parent_not_found(self, work_id, main_user):
        """T-CREATE-07: POST /nodes with nonexistent parent_id returns 404."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "chapter", "Ch1", parent_id=str(uuid.uuid4()))
        assert r.status_code == 404
        assert r.json()["detail"] == "Parent node not found"

    @pytest.mark.asyncio
    async def test_t_create_08_hierarchy_violation(self, work_id, main_user):
        """T-CREATE-08: Scene under Part returns 422."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "part", "P1")
            part_id = r.json()["node_id"]
            r = await _create_node(ac, headers, work_id, "scene", "S1", parent_id=part_id)
        assert r.status_code == 422
        assert "scene" in r.json()["detail"] and "part" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_t_create_09_no_parent_non_part(self, work_id, main_user):
        """T-CREATE-09: Chapter without parent_id returns 422."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "chapter", "Ch1")
        assert r.status_code == 422
        assert r.json()["detail"] == "Only 'part' nodes may have no parent"

    @pytest.mark.asyncio
    async def test_t_create_10_whitespace_tag(self, work_id, main_user):
        """T-CREATE-10: POST /nodes with whitespace-only tag returns 422."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "part", "   ")
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_t_create_11_no_auth(self, work_id):
        """T-CREATE-11: POST /nodes without auth returns 401."""
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, {}, work_id, "part", "P1")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_t_create_12_reader_scope(self, work_id, scoped_user):
        """T-CREATE-12: POST /nodes with tree:reader only returns 403."""
        headers, scope = scoped_user
        if "tree:writer" in scope:
            pytest.skip("token has tree:writer scope")
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "part", "P1")
        assert r.status_code == 403

    # --- List Nodes ---

    @pytest.mark.asyncio
    async def test_t_create_13_list_all_nodes(self, work_id, main_user):
        """T-CREATE-13: GET /works/{id}/nodes returns all nodes."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            for i in range(3):
                await _create_node(ac, headers, work_id, "part", f"P{i}")
            r = await ac.get(f"/works/{work_id}/nodes", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 3

    @pytest.mark.asyncio
    async def test_t_create_14_list_filter_by_type(self, work_id, main_user):
        """T-CREATE-14: GET /works/{id}/nodes?node_type=part filters correctly."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            await _create_node(ac, headers, work_id, "part", "P1")
            r = await _create_node(ac, headers, work_id, "part", "P2")
            p2_id = r.json()["node_id"]
            r = await _create_node(ac, headers, work_id, "chapter", "Ch1", parent_id=p2_id)
            assert r.status_code == 201
            r = await ac.get(f"/works/{work_id}/nodes?node_type=part", headers=headers)
        assert r.status_code == 200
        assert len(r.json()) == 2

    @pytest.mark.asyncio
    async def test_t_create_15_list_invalid_type(self, work_id, main_user):
        """T-CREATE-15: GET with invalid node_type returns 422."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}/nodes?node_type=invalid", headers=headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_t_create_16_list_work_not_found(self, main_user):
        """T-CREATE-16: GET /works/{id}/nodes with nonexistent work_id returns 404."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{str(uuid.uuid4())}/nodes", headers=headers)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_create_17_list_isolation(self, work_id, iso_user):
        """T-CREATE-17: GET /works/{other's id}/nodes returns 404."""
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}/nodes", headers=iso_user)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_create_18_list_empty(self, work_id, main_user):
        """T-CREATE-18: GET /works/{id}/nodes with no nodes returns []."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}/nodes", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

    # --- Get Single Node ---

    @pytest.mark.asyncio
    async def test_t_create_19_get_node_happy(self, work_id, main_user):
        """T-CREATE-19: GET /nodes/{id} returns 200 with NodeResponse."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "part", "P1")
            node_id = r.json()["node_id"]
            r = await ac.get(f"/nodes/{node_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["node_id"] == node_id
        assert "account_id" not in r.json()

    @pytest.mark.asyncio
    async def test_t_create_20_get_node_not_found(self, main_user):
        """T-CREATE-20: GET /nodes/{nonexistent} returns 404."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{str(uuid.uuid4())}", headers=headers)
        assert r.status_code == 404
        assert r.json()["detail"] == "Node not found"

    @pytest.mark.asyncio
    async def test_t_create_21_get_node_isolation(self, work_id, main_user, iso_user):
        """T-CREATE-21: GET /nodes/{other's id} returns 404."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "part", "P1")
            node_id = r.json()["node_id"]
            r = await ac.get(f"/nodes/{node_id}", headers=iso_user)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_create_22_get_node_invalid_uuid(self, main_user):
        """T-CREATE-22: GET /nodes/not-a-uuid returns 422."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get("/nodes/not-a-uuid", headers=headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_t_create_23_get_node_no_auth(self, work_id, main_user):
        """T-CREATE-23: GET /nodes/{id} without auth returns 401."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "part", "P1")
            node_id = r.json()["node_id"]
            r = await ac.get(f"/nodes/{node_id}")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_t_create_24_get_node_reader_scope(self, work_id, main_user, scoped_user):
        """T-CREATE-24: GET /nodes/{id} without tree:reader returns 403."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "part", "P1")
            node_id = r.json()["node_id"]
        s_headers, scope = scoped_user
        if "tree:reader" in scope:
            pytest.skip("token has tree:reader scope")
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{node_id}", headers=s_headers)
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_t_create_25_beat_no_children_guard(self, main_user):
        """T-CREATE-25: Cannot create child under a Beat node."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            work_id, ids = await _create_work_and_hierarchy(ac, headers)
            beat_id = ids[3]
            r = await _create_node(ac, headers, work_id, "beat", "sub-beat", parent_id=beat_id)
        assert r.status_code == 422


# ===========================================================================
# T-48: Node Navigation (23 tests)
# ===========================================================================


class TestNodeNavigation:
    """T-48: Integration tests for Node Navigation endpoints."""

    @pytest.fixture
    async def work_and_nodes(self, main_user):
        """Create work + full hierarchy. Returns (headers, work_id, ids)."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            work_id, ids = await _create_work_and_hierarchy(ac, headers)
        return headers, work_id, ids

    # --- Children ---

    @pytest.mark.asyncio
    async def test_t_nav_01_children_happy(self, work_and_nodes):
        """T-NAV-01: GET /nodes/{id}/children returns direct children ordered."""
        headers, _, ids = work_and_nodes
        part_id = ids[0]
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{part_id}/children", headers=headers)
        assert r.status_code == 200
        children = r.json()
        assert len(children) == 1
        assert children[0]["node_type"] == "chapter"
        assert children[0]["position"] == 0

    @pytest.mark.asyncio
    async def test_t_nav_02_children_beat_empty(self, work_and_nodes):
        """T-NAV-02: GET /nodes/{beat_id}/children returns []."""
        headers, _, ids = work_and_nodes
        beat_id = ids[3]
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{beat_id}/children", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_t_nav_03_children_not_found(self, work_and_nodes):
        """T-NAV-03: GET /nodes/{nonexistent}/children returns 404."""
        headers, _, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{str(uuid.uuid4())}/children", headers=headers)
        assert r.status_code == 404
        assert r.json()["detail"] == "Node not found"

    @pytest.mark.asyncio
    async def test_t_nav_04_children_isolation(self, work_and_nodes, iso_user):
        """T-NAV-04: GET /nodes/{other's id}/children returns 404."""
        headers, _, ids = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{ids[0]}/children", headers=iso_user)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_nav_05_children_invalid_uuid(self, work_and_nodes):
        """T-NAV-05: GET /nodes/not-a-uuid/children returns 422."""
        headers, _, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get("/nodes/not-a-uuid/children", headers=headers)
        assert r.status_code == 422

    # --- Parent ---

    @pytest.mark.asyncio
    async def test_t_nav_06_parent_happy(self, work_and_nodes):
        """T-NAV-06: GET /nodes/{id}/parent returns parent node."""
        headers, _, ids = work_and_nodes
        chapter_id = ids[1]
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{chapter_id}/parent", headers=headers)
        assert r.status_code == 200
        parent = r.json()
        assert parent["node_id"] == ids[0]
        assert parent["node_type"] == "part"

    @pytest.mark.asyncio
    async def test_t_nav_07_parent_root_is_null(self, work_and_nodes):
        """T-NAV-07: GET /nodes/{part_id}/parent returns null."""
        headers, _, ids = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{ids[0]}/parent", headers=headers)
        assert r.status_code == 200
        assert r.json() is None

    @pytest.mark.asyncio
    async def test_t_nav_08_parent_not_found(self, work_and_nodes):
        """T-NAV-08: GET /nodes/{nonexistent}/parent returns 404."""
        headers, _, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{str(uuid.uuid4())}/parent", headers=headers)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_nav_09_parent_isolation(self, work_and_nodes, iso_user):
        """T-NAV-09: GET /nodes/{other's id}/parent returns 404."""
        headers, _, ids = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{ids[1]}/parent", headers=iso_user)
        assert r.status_code == 404

    # --- Ancestors ---

    @pytest.mark.asyncio
    async def test_t_nav_10_ancestors_deep(self, work_and_nodes):
        """T-NAV-10: GET /nodes/{beat_id}/ancestors returns root-first chain."""
        headers, _, ids = work_and_nodes
        beat_id = ids[3]
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{beat_id}/ancestors", headers=headers)
        assert r.status_code == 200
        ancestors = r.json()["ancestors"]
        assert len(ancestors) == 3
        assert ancestors[0]["node_type"] == "part"
        assert ancestors[1]["node_type"] == "chapter"
        assert ancestors[2]["node_type"] == "scene"

    @pytest.mark.asyncio
    async def test_t_nav_11_ancestors_root_empty(self, work_and_nodes):
        """T-NAV-11: GET /nodes/{part_id}/ancestors returns []."""
        headers, _, ids = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{ids[0]}/ancestors", headers=headers)
        assert r.status_code == 200
        assert r.json()["ancestors"] == []

    @pytest.mark.asyncio
    async def test_t_nav_12_ancestors_mid(self, work_and_nodes):
        """T-NAV-12: GET /nodes/{chapter_id}/ancestors returns [part]."""
        headers, _, ids = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{ids[1]}/ancestors", headers=headers)
        assert r.status_code == 200
        assert len(r.json()["ancestors"]) == 1
        assert r.json()["ancestors"][0]["node_type"] == "part"

    @pytest.mark.asyncio
    async def test_t_nav_13_ancestors_not_found(self, work_and_nodes):
        """T-NAV-13: GET /nodes/{nonexistent}/ancestors returns 404."""
        headers, _, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{str(uuid.uuid4())}/ancestors", headers=headers)
        assert r.status_code == 404

    # --- Siblings ---

    @pytest.mark.asyncio
    async def test_t_nav_14_siblings_happy(self, main_user, work_id):
        """T-NAV-14: GET /nodes/{id}/siblings returns other siblings."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            ids = []
            for i in range(3):
                r = await _create_node(ac, headers, work_id, "part", f"P{i}")
                ids.append(r.json()["node_id"])
            r = await ac.get(f"/nodes/{ids[1]}/siblings", headers=headers)
        assert r.status_code == 200
        siblings = r.json()
        assert len(siblings) == 2
        sibling_ids = [s["node_id"] for s in siblings]
        assert ids[1] not in sibling_ids

    @pytest.mark.asyncio
    async def test_t_nav_15_siblings_single_empty(self, main_user, work_id):
        """T-NAV-15: GET /nodes/{only_child}/siblings returns []."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "part", "P1")
            nid = r.json()["node_id"]
            r = await ac.get(f"/nodes/{nid}/siblings", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_t_nav_16_siblings_not_found(self, work_and_nodes):
        """T-NAV-16: GET /nodes/{nonexistent}/siblings returns 404."""
        headers, _, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{str(uuid.uuid4())}/siblings", headers=headers)
        assert r.status_code == 404

    # --- Root Nodes ---

    @pytest.mark.asyncio
    async def test_t_nav_17_roots_happy(self, work_and_nodes):
        """T-NAV-17: GET /works/{id}/nodes/root returns Part nodes."""
        headers, work_id, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}/nodes/root", headers=headers)
        assert r.status_code == 200
        roots = r.json()
        assert len(roots) == 1
        assert roots[0]["node_type"] == "part"
        assert roots[0]["parent_id"] is None

    @pytest.mark.asyncio
    async def test_t_nav_18_roots_empty(self, main_user, work_id):
        """T-NAV-18: GET /works/{id}/nodes/root with no nodes returns []."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}/nodes/root", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_t_nav_19_roots_not_found(self, work_and_nodes):
        """T-NAV-19: GET /works/{nonexistent}/nodes/root returns 404."""
        headers, _, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{str(uuid.uuid4())}/nodes/root", headers=headers)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_nav_20_roots_isolation(self, work_and_nodes, iso_user):
        """T-NAV-20: GET /works/{other's id}/nodes/root returns 404."""
        headers, work_id, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}/nodes/root", headers=iso_user)
        assert r.status_code == 404

    # --- Leaves ---

    @pytest.mark.asyncio
    async def test_t_nav_21_leaves_happy(self, work_and_nodes):
        """T-NAV-21: GET /works/{id}/nodes/leaves returns Beat nodes."""
        headers, work_id, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}/nodes/leaves", headers=headers)
        assert r.status_code == 200
        leaves = r.json()
        assert len(leaves) == 1
        assert leaves[0]["node_type"] == "beat"

    @pytest.mark.asyncio
    async def test_t_nav_22_leaves_empty(self, main_user, work_id):
        """T-NAV-22: GET /works/{id}/nodes/leaves with no beats returns []."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}/nodes/leaves", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

    # --- Stats ---

    @pytest.mark.asyncio
    async def test_t_nav_23_stats_happy(self, work_and_nodes):
        """T-NAV-23: GET /works/{id}/stats returns aggregate counts."""
        headers, work_id, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}/stats", headers=headers)
        assert r.status_code == 200
        stats = r.json()
        assert stats["total_nodes"] == 4
        assert stats["by_type"]["part"] == 1
        assert stats["by_type"]["chapter"] == 1
        assert stats["by_type"]["scene"] == 1
        assert stats["by_type"]["beat"] == 1
        assert stats["max_depth"] >= 3

    @pytest.mark.asyncio
    async def test_t_nav_24_stats_empty(self, main_user, work_id):
        """T-NAV-24: GET /works/{id}/stats with no nodes returns zeros."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}/stats", headers=headers)
        assert r.status_code == 200
        stats = r.json()
        assert stats["total_nodes"] == 0
        assert stats["max_depth"] == 0

    @pytest.mark.asyncio
    async def test_t_nav_25_stats_not_found(self, work_and_nodes):
        """T-NAV-25: GET /works/{nonexistent}/stats returns 404."""
        headers, _, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{str(uuid.uuid4())}/stats", headers=headers)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_nav_26_stats_isolation(self, work_and_nodes, iso_user):
        """T-NAV-26: GET /works/{other's id}/stats returns 404."""
        headers, work_id, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/works/{work_id}/stats", headers=iso_user)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_nav_27_invalid_uuid_path(self, work_and_nodes):
        """T-NAV-27: Invalid UUID in navigation path returns 422."""
        headers, _, _ = work_and_nodes
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get("/works/not-a-uuid/nodes/root", headers=headers)
        assert r.status_code == 422


# ===========================================================================
# T-49: Node Update + Delete (21 tests)
# ===========================================================================


class TestNodeUpdateDelete:
    """T-49: Integration tests for Node Update and Delete."""

    @pytest.fixture
    async def work_and_node(self, main_user):
        """Create work + single Part node. Returns (headers, work_id, node_id)."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_work(ac, headers, title="Test")
            work_id = r.json()["work_id"]
            r = await _create_node(ac, headers, work_id, "part", "P1")
            node_id = r.json()["node_id"]
        return headers, work_id, node_id

    @pytest.fixture
    async def two_parts(self, main_user):
        """Create work + 2 Part nodes. Returns (headers, work_id, part1_id, part2_id)."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_work(ac, headers, title="Test")
            work_id = r.json()["work_id"]
            r = await _create_node(ac, headers, work_id, "part", "P1")
            p1 = r.json()["node_id"]
            r = await _create_node(ac, headers, work_id, "part", "P2")
            p2 = r.json()["node_id"]
        return headers, work_id, p1, p2

    @pytest.fixture
    async def part_with_child(self, main_user):
        """Create work + Part with Chapter child. Returns (headers, work_id, part_id, ch_id)."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_work(ac, headers, title="Test")
            work_id = r.json()["work_id"]
            r = await _create_node(ac, headers, work_id, "part", "P1")
            p1 = r.json()["node_id"]
            r = await _create_node(ac, headers, work_id, "chapter", "Ch1", parent_id=p1)
            ch = r.json()["node_id"]
        return headers, work_id, p1, ch

    # --- Update ---

    @pytest.mark.asyncio
    async def test_t_update_01_tag_update(self, work_and_node):
        """T-UPDATE-01: PUT /nodes/{id} updates tag and refreshes updated_at."""
        headers, _, node_id = work_and_node
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{node_id}", json={"tag": "Revised"}, headers=headers)
        assert r.status_code == 200
        assert r.json()["tag"] == "Revised"
        assert r.json()["updated_at"] is not None

    @pytest.mark.asyncio
    async def test_t_update_02_reparent(self, two_parts):
        """T-UPDATE-02: PUT /nodes/{id} reparents node to new parent."""
        headers, work_id, p1, p2 = two_parts
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "chapter", "Ch1", parent_id=p1)
            ch_id = r.json()["node_id"]
            r = await ac.put(f"/nodes/{ch_id}", json={"parent_id": p2}, headers=headers)
        assert r.status_code == 200
        assert r.json()["parent_id"] == p2

    @pytest.mark.asyncio
    async def test_t_update_03_cycle_detection(self, part_with_child):
        """T-UPDATE-03: PUT /nodes/{part} with parent_id=child returns 422."""
        headers, _, part_id, ch_id = part_with_child
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{part_id}", json={"parent_id": ch_id}, headers=headers)
        assert r.status_code == 422
        assert "cycle" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_t_update_04_hierarchy_violation(self, two_parts):
        """T-UPDATE-04: PUT /nodes/{part} with scene parent returns 422."""
        headers, work_id, p1, _ = two_parts
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "chapter", "Ch1", parent_id=p1)
            ch_id = r.json()["node_id"]
            r = await _create_node(ac, headers, work_id, "scene", "S1", parent_id=ch_id)
            sc_id = r.json()["node_id"]
            r = await ac.put(f"/nodes/{p1}", json={"parent_id": sc_id}, headers=headers)
        assert r.status_code == 422
        assert "hierarchy" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_t_update_05_parent_not_found(self, work_and_node):
        """T-UPDATE-05: PUT /nodes/{id} with nonexistent parent_id returns 404."""
        headers, _, node_id = work_and_node
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{node_id}", json={"parent_id": str(uuid.uuid4())}, headers=headers)
        assert r.status_code == 404
        assert r.json()["detail"] == "Parent node not found"

    @pytest.mark.asyncio
    async def test_t_update_06_node_not_found(self, main_user):
        """T-UPDATE-06: PUT /nodes/{nonexistent} returns 404."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{str(uuid.uuid4())}", json={"tag": "X"}, headers=headers)
        assert r.status_code == 404
        assert r.json()["detail"] == "Node not found"

    @pytest.mark.asyncio
    async def test_t_update_07_isolation(self, work_and_node, iso_user):
        """T-UPDATE-07: PUT /nodes/{other's id} returns 404."""
        headers, _, node_id = work_and_node
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{node_id}", json={"tag": "X"}, headers=iso_user)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_update_08_empty_tag(self, work_and_node):
        """T-UPDATE-08: PUT /nodes/{id} with empty tag returns 422."""
        headers, _, node_id = work_and_node
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{node_id}", json={"tag": ""}, headers=headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_t_update_09_writer_scope(self, work_and_node, scoped_user):
        """T-UPDATE-09: PUT /nodes/{id} with tree:reader only returns 403."""
        headers, _, node_id = work_and_node
        s_headers, scope = scoped_user
        if "tree:writer" in scope:
            pytest.skip("token has tree:writer scope")
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{node_id}", json={"tag": "X"}, headers=s_headers)
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_t_update_10_hierarchy_before_cycle(self, two_parts):
        """T-UPDATE-10: Hierarchy check fires before cycle check."""
        headers, work_id, p1, p2 = two_parts
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_node(ac, headers, work_id, "chapter", "Ch1", parent_id=p1)
            ch_id = r.json()["node_id"]
            r = await _create_node(ac, headers, work_id, "scene", "S1", parent_id=ch_id)
            sc_id = r.json()["node_id"]
            r = await ac.put(f"/nodes/{p1}", json={"parent_id": sc_id}, headers=headers)
        assert r.status_code == 422
        assert "hierarchy" in r.json()["detail"].lower()

    # --- Delete ---

    @pytest.mark.asyncio
    async def test_t_delete_01_cascade(self, main_user, motor_client):
        """T-DELETE-01: DELETE /nodes/{part} removes all descendants."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            work_id, ids = await _create_work_and_hierarchy(ac, headers)
            r = await ac.delete(f"/nodes/{ids[0]}", headers=headers)
        assert r.status_code == 200
        assert "3 descendant(s) removed" in r.json()["detail"]
        db = motor_client.fabulator
        remaining = await db.node_collection.count_documents({"work_id": work_id})
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_t_delete_02_leaf_node(self, main_user):
        """T-DELETE-02: DELETE /nodes/{beat} removes 0 descendants."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            work_id, ids = await _create_work_and_hierarchy(ac, headers)
            r = await ac.delete(f"/nodes/{ids[3]}", headers=headers)
        assert r.status_code == 200
        assert "0 descendant(s) removed" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_t_delete_03_not_found(self, main_user):
        """T-DELETE-03: DELETE /nodes/{nonexistent} returns 404."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.delete(f"/nodes/{str(uuid.uuid4())}", headers=headers)
        assert r.status_code == 404
        assert r.json()["detail"] == "Node not found"

    @pytest.mark.asyncio
    async def test_t_delete_04_isolation(self, work_and_node, iso_user):
        """T-DELETE-04: DELETE /nodes/{other's id} returns 404."""
        headers, _, node_id = work_and_node
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.delete(f"/nodes/{node_id}", headers=iso_user)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_delete_05_writer_scope(self, work_and_node, scoped_user):
        """T-DELETE-05: DELETE /nodes/{id} with tree:reader only returns 403."""
        headers, _, node_id = work_and_node
        s_headers, scope = scoped_user
        if "tree:writer" in scope:
            pytest.skip("token has tree:writer scope")
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.delete(f"/nodes/{node_id}", headers=s_headers)
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_t_delete_06_no_auth(self, main_user):
        """T-DELETE-06: DELETE /nodes/{id} without auth returns 401."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_work(ac, headers, title="Test")
            work_id = r.json()["work_id"]
            r = await _create_node(ac, headers, work_id, "part", "P1")
            node_id = r.json()["node_id"]
            r = await ac.delete(f"/nodes/{node_id}")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_t_delete_07_node_type_immutable(self, work_and_node):
        """T-DELETE-07: node_type unchanged after PUT with extra fields."""
        headers, _, node_id = work_and_node
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{node_id}", headers=headers)
        original_type = r.json()["node_type"]
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{node_id}", json={"tag": "Changed"}, headers=headers)
        assert r.status_code == 200
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{node_id}", headers=headers)
        assert r.json()["node_type"] == original_type


# ===========================================================================
# T-50: Reorder + Duplicate (18 tests)
# ===========================================================================


class TestReorderDuplicate:
    """T-50: Integration tests for Reorder and Duplicate endpoints."""

    @pytest.fixture
    async def three_siblings(self, main_user):
        """Create work + 3 Part siblings. Returns (headers, work_id, ids)."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_work(ac, headers, title="Reorder Work")
            work_id = r.json()["work_id"]
            ids = []
            for i in range(3):
                r = await _create_node(ac, headers, work_id, "part", f"P{i}")
                ids.append(r.json()["node_id"])
        return headers, work_id, ids

    @pytest.fixture
    async def part_with_children(self, main_user):
        """Create work + Part with Chapter and Scene children."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_work(ac, headers, title="Dup Work")
            work_id = r.json()["work_id"]
            r = await _create_node(ac, headers, work_id, "part", "P1")
            part_id = r.json()["node_id"]
            ch_ids = []
            for i in range(2):
                r = await _create_node(ac, headers, work_id, "chapter", f"Ch{i}", parent_id=part_id)
                ch_ids.append(r.json()["node_id"])
                for j in range(2):
                    r = await _create_node(ac, headers, work_id, "scene", f"S{j}", parent_id=ch_ids[-1])
            r = await ac.get(f"/nodes/{part_id}/children", headers=headers)
        return headers, work_id, part_id, ch_ids

    # --- Reorder ---

    @pytest.mark.asyncio
    async def test_t_reorder_01_move_to_start(self, three_siblings):
        """T-REORDER-01: Move last sibling to position 0 succeeds."""
        headers, _, ids = three_siblings
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{ids[2]}/reorder", json={"position": 0}, headers=headers)
        assert r.status_code == 200
        assert r.json()["position"] == 0

    @pytest.mark.asyncio
    async def test_t_reorder_02_move_to_end(self, three_siblings):
        """T-REORDER-02: Move first sibling to last position succeeds."""
        headers, _, ids = three_siblings
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{ids[0]}/reorder", json={"position": 2}, headers=headers)
        assert r.status_code == 200
        assert r.json()["position"] == 2

    @pytest.mark.asyncio
    async def test_t_reorder_03_clamp_high(self, three_siblings):
        """T-REORDER-03: Position beyond max clamped to last index."""
        headers, _, ids = three_siblings
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{ids[0]}/reorder", json={"position": 999}, headers=headers)
        assert r.status_code == 200
        assert r.json()["position"] == 2

    @pytest.mark.asyncio
    async def test_t_reorder_04_single_node(self, main_user):
        """T-REORDER-04: Single sibling group clamps to 0."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await _create_work(ac, headers, title="Test")
            work_id = r.json()["work_id"]
            r = await _create_node(ac, headers, work_id, "part", "P1")
            nid = r.json()["node_id"]
            r = await ac.put(f"/nodes/{nid}/reorder", json={"position": 5}, headers=headers)
        assert r.status_code == 200
        assert r.json()["position"] == 0

    @pytest.mark.asyncio
    async def test_t_reorder_05_negative_position(self, three_siblings):
        """T-REORDER-05: Negative position returns 422."""
        headers, _, ids = three_siblings
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{ids[0]}/reorder", json={"position": -1}, headers=headers)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_t_reorder_06_not_found(self, three_siblings):
        """T-REORDER-06: Non-existent node returns 404."""
        headers, _, _ = three_siblings
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{str(uuid.uuid4())}/reorder", json={"position": 0}, headers=headers)
        assert r.status_code == 404
        assert r.json()["detail"] == "Node not found"

    @pytest.mark.asyncio
    async def test_t_reorder_07_isolation(self, three_siblings, iso_user):
        """T-REORDER-07: Cross-account reorder returns 404."""
        headers, _, ids = three_siblings
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{ids[0]}/reorder", json={"position": 1}, headers=iso_user)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_reorder_08_writer_scope(self, three_siblings, scoped_user):
        """T-REORDER-08: tree:reader only returns 403 on reorder."""
        headers, _, ids = three_siblings
        s_headers, scope = scoped_user
        if "tree:writer" in scope:
            pytest.skip("token has tree:writer scope")
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.put(f"/nodes/{ids[0]}/reorder", json={"position": 1}, headers=s_headers)
        assert r.status_code == 403

    # --- Duplicate (shallow) ---

    @pytest.mark.asyncio
    async def test_t_dup_01_shallow_position_and_tag(self, three_siblings):
        """T-DUP-01: Shallow duplicate at position+1 with (copy) suffix."""
        headers, _, ids = three_siblings
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{ids[1]}", headers=headers)
        original_tag = r.json()["tag"]
        original_pos = r.json()["position"]
        r = await ac.post(f"/nodes/{ids[1]}/duplicate", headers=headers)
        assert r.status_code == 201
        body = r.json()
        assert body["tag"] == f"{original_tag} (copy)"
        assert body["position"] == original_pos + 1

    @pytest.mark.asyncio
    async def test_t_dup_02_shallow_no_children(self, three_siblings):
        """T-DUP-02: Shallow duplicate has no children."""
        headers, _, ids = three_siblings
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post(f"/nodes/{ids[0]}/duplicate", headers=headers)
        assert r.status_code == 201
        new_id = r.json()["node_id"]
        r = await ac.get(f"/nodes/{new_id}/children", headers=headers)
        assert r.json() == []

    # --- Duplicate (deep) ---

    @pytest.mark.asyncio
    async def test_t_dup_03_deep_preserves_subtree(self, part_with_children):
        """T-DUP-03: Deep duplicate preserves full subtree."""
        headers, work_id, part_id, _ = part_with_children
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{part_id}/children", headers=headers)
        children_before = len(r.json())
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post(f"/nodes/{part_id}/duplicate?deep=true", headers=headers)
        assert r.status_code == 201
        new_id = r.json()["node_id"]
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.get(f"/nodes/{new_id}/children", headers=headers)
        assert len(r.json()) == children_before

    @pytest.mark.asyncio
    async def test_t_dup_04_deep_fresh_uuids(self, part_with_children):
        """T-DUP-04: Deep duplicate has fresh UUIDs distinct from originals."""
        headers, work_id, part_id, ch_ids = part_with_children
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post(f"/nodes/{part_id}/duplicate?deep=true", headers=headers)
        assert r.status_code == 201
        new_id = r.json()["node_id"]
        assert new_id != part_id
        # Collect all original IDs
        original_ids = {part_id, *ch_ids}
        r = await ac.get(f"/works/{work_id}/nodes", headers=headers)
        all_after = {n["node_id"] for n in r.json()}
        new_ids = all_after - original_ids
        assert new_id in new_ids
        assert len(new_ids) >= 4  # part + 2 chapters + scenes

    @pytest.mark.asyncio
    async def test_t_dup_05_beat_guard(self, main_user):
        """T-DUP-05: Beat node duplicate returns 400."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            work_id, ids = await _create_work_and_hierarchy(ac, headers)
            r = await ac.post(f"/nodes/{ids[3]}/duplicate", headers=headers)
        assert r.status_code == 400
        assert r.json()["detail"] == "Beat nodes cannot be duplicated"

    @pytest.mark.asyncio
    async def test_t_dup_06_beat_guard_deep(self, main_user):
        """T-DUP-06: Beat deep duplicate returns 400."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            work_id, ids = await _create_work_and_hierarchy(ac, headers)
            r = await ac.post(f"/nodes/{ids[3]}/duplicate?deep=true", headers=headers)
        assert r.status_code == 400
        assert r.json()["detail"] == "Beat nodes cannot be duplicated"

    @pytest.mark.asyncio
    async def test_t_dup_07_beat_no_write(self, main_user, motor_client):
        """T-DUP-07: Beat duplicate writes no documents."""
        headers, _ = main_user
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            work_id, ids = await _create_work_and_hierarchy(ac, headers)
        count_before = await _count_nodes(motor_client, work_id=work_id)
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post(f"/nodes/{ids[3]}/duplicate", headers=headers)
        assert r.status_code == 400
        count_after = await _count_nodes(motor_client, work_id=work_id)
        assert count_after == count_before

    @pytest.mark.asyncio
    async def test_t_dup_08_not_found(self, three_siblings):
        """T-DUP-08: Duplicate nonexistent node returns 404."""
        headers, _, _ = three_siblings
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post(f"/nodes/{str(uuid.uuid4())}/duplicate", headers=headers)
        assert r.status_code == 404
        assert r.json()["detail"] == "Node not found"

    @pytest.mark.asyncio
    async def test_t_dup_09_isolation(self, three_siblings, iso_user):
        """T-DUP-09: Cross-account duplicate returns 404."""
        headers, _, ids = three_siblings
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post(f"/nodes/{ids[0]}/duplicate", headers=iso_user)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_t_dup_10_writer_scope(self, three_siblings, scoped_user):
        """T-DUP-10: tree:reader only returns 403 on duplicate."""
        headers, _, ids = three_siblings
        s_headers, scope = scoped_user
        if "tree:writer" in scope:
            pytest.skip("token has tree:writer scope")
        async with httpx.AsyncClient(transport=ASGITransport(app=api.app)) as ac:
            r = await ac.post(f"/nodes/{ids[0]}/duplicate", headers=s_headers)
        assert r.status_code == 403

"""
Unit tests — no MongoDB or Redis required.

Covers:
  - Pydantic model validation (models.py)
  - users_saves_helper (models.py)
  - Authentication helpers: verify_password, get_password_hash, create_access_token
"""

import os
import uuid
import pytest
from datetime import timedelta
from bson.objectid import ObjectId
from pydantic import ValidationError
import motor.motor_asyncio

# Ensure .env is loaded before importing app modules
import app.config  # noqa: F401

from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.models import (
    RequestAddSchema,
    RequestUpdateSchema,
    UserType,
    UpdateUserType,
    users_saves_helper,
    NODE_NAME_MAX_LEN,
    DESCRIPTION_MAX_LEN,
    TEXT_MAX_LEN,
    LINK_FIELD_MAX_LEN,
    TAGS_MAX_COUNT,
    TAG_MAX_LEN,
    DemoSeedResponse,
    CreateWorkRequest,
)
from app.database import NodeStorage, is_valid_parent_child
from app.authentication import Authentication


# ---------------------------------------------------------------------------
# Pydantic model validation — RequestAddSchema
# ---------------------------------------------------------------------------

class TestRequestAddSchema:

    def test_valid_parent_uuid_accepted(self):
        schema = RequestAddSchema(parent="d22e5e28-ca11-11eb-b437-f01898e87167")
        assert schema.parent == "d22e5e28-ca11-11eb-b437-f01898e87167"

    def test_invalid_parent_uuid_rejected(self):
        with pytest.raises(ValidationError):
            RequestAddSchema(parent="not-a-uuid")

    def test_parent_none_accepted(self):
        schema = RequestAddSchema(parent=None)
        assert schema.parent is None

    def test_description_at_limit_accepted(self):
        schema = RequestAddSchema(description="x" * DESCRIPTION_MAX_LEN)
        assert len(schema.description) == DESCRIPTION_MAX_LEN

    def test_description_over_limit_rejected(self):
        with pytest.raises(ValidationError):
            RequestAddSchema(description="x" * (DESCRIPTION_MAX_LEN + 1))

    def test_text_at_limit_accepted(self):
        schema = RequestAddSchema(text="x" * TEXT_MAX_LEN)
        assert len(schema.text) == TEXT_MAX_LEN

    def test_text_over_limit_rejected(self):
        with pytest.raises(ValidationError):
            RequestAddSchema(text="x" * (TEXT_MAX_LEN + 1))

    def test_previous_at_limit_accepted(self):
        schema = RequestAddSchema(previous="x" * LINK_FIELD_MAX_LEN)
        assert len(schema.previous) == LINK_FIELD_MAX_LEN

    def test_previous_over_limit_rejected(self):
        with pytest.raises(ValidationError):
            RequestAddSchema(previous="x" * (LINK_FIELD_MAX_LEN + 1))

    def test_tags_at_limit_accepted(self):
        schema = RequestAddSchema(tags=[f"tag{i}" for i in range(TAGS_MAX_COUNT)])
        assert len(schema.tags) == TAGS_MAX_COUNT

    def test_tags_over_limit_rejected(self):
        with pytest.raises(ValidationError):
            RequestAddSchema(tags=[f"tag{i}" for i in range(TAGS_MAX_COUNT + 1)])

    def test_tag_at_max_length_accepted(self):
        schema = RequestAddSchema(tags=["x" * TAG_MAX_LEN])
        assert len(schema.tags[0]) == TAG_MAX_LEN

    def test_tag_over_max_length_rejected(self):
        with pytest.raises(ValidationError):
            RequestAddSchema(tags=["x" * (TAG_MAX_LEN + 1)])

    def test_empty_tag_rejected(self):
        with pytest.raises(ValidationError):
            RequestAddSchema(tags=[""])

    def test_whitespace_only_tag_rejected(self):
        with pytest.raises(ValidationError):
            RequestAddSchema(tags=["   "])

    def test_non_string_tag_rejected(self):
        with pytest.raises(ValidationError):
            RequestAddSchema(tags=[123])

    def test_all_none_fields_accepted(self):
        schema = RequestAddSchema()
        assert schema.parent is None
        assert schema.description is None
        assert schema.text is None
        assert schema.tags is None


# ---------------------------------------------------------------------------
# Pydantic model validation — RequestUpdateSchema
# ---------------------------------------------------------------------------

class TestRequestUpdateSchema:

    def test_name_at_limit_accepted(self):
        schema = RequestUpdateSchema(name="x" * NODE_NAME_MAX_LEN)
        assert len(schema.name) == NODE_NAME_MAX_LEN

    def test_name_over_limit_rejected(self):
        with pytest.raises(ValidationError):
            RequestUpdateSchema(name="x" * (NODE_NAME_MAX_LEN + 1))

    def test_name_empty_string_rejected(self):
        with pytest.raises(ValidationError):
            RequestUpdateSchema(name="")

    def test_parent_uuid_accepted(self):
        schema = RequestUpdateSchema(parent="d22e5e28-ca11-11eb-b437-f01898e87167")
        assert schema.parent == "d22e5e28-ca11-11eb-b437-f01898e87167"

    def test_parent_invalid_uuid_rejected(self):
        with pytest.raises(ValidationError):
            RequestUpdateSchema(parent="bad-uuid")


# ---------------------------------------------------------------------------
# Pydantic model validation — UserType enum
# ---------------------------------------------------------------------------

class TestUserType:

    def test_free_accepted(self):
        ut = UpdateUserType(user_type=UserType.free)
        assert ut.user_type == UserType.free

    def test_premium_accepted(self):
        ut = UpdateUserType(user_type=UserType.premium)
        assert ut.user_type == UserType.premium

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            UpdateUserType(user_type="gold")


# ---------------------------------------------------------------------------
# users_saves_helper
# ---------------------------------------------------------------------------

class TestUsersSavesHelper:

    def _raw_user(self):
        return {
            "_id": ObjectId(),
            "name": {"firstname": "Test", "surname": "User"},
            "username": "testuser",
            "account_id": "acc_hash_123",
            "email": "test@example.com",
            "disabled": False,
            "user_role": "user:reader user:writer",
            "user_type": "free",
        }

    def test_returns_retrieved_user_details(self):
        from app.models import RetrievedUserDetails
        result = users_saves_helper(self._raw_user())
        assert isinstance(result, RetrievedUserDetails)

    def test_username_preserved(self):
        result = users_saves_helper(self._raw_user())
        assert result.username == "testuser"

    def test_disabled_preserved(self):
        result = users_saves_helper(self._raw_user())
        assert result.disabled == False


# ---------------------------------------------------------------------------
# Authentication helpers — no DB needed
# ---------------------------------------------------------------------------

class TestAuthHelpers:

    def test_hash_and_verify_roundtrip(self):
        auth = Authentication(client=None)
        hashed = auth.get_password_hash("secret")
        assert auth.verify_password("secret", hashed)

    def test_wrong_password_fails_verify(self):
        auth = Authentication(client=None)
        hashed = auth.get_password_hash("correct")
        assert not auth.verify_password("wrong", hashed)

    def test_create_access_token_contains_sub(self):
        from jose import jwt
        auth = Authentication(client=None)
        token = auth.create_access_token(
            data={"sub": "test_account", "scopes": ["tree:reader"]},
            expires_delta=timedelta(minutes=30),
        )
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        assert payload["sub"] == "test_account"

    def test_create_access_token_contains_scopes(self):
        from jose import jwt
        auth = Authentication(client=None)
        token = auth.create_access_token(
            data={"sub": "acc", "scopes": ["tree:reader", "user:writer"]},
            expires_delta=timedelta(minutes=5),
        )
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        assert "tree:reader" in payload["scopes"]

    def test_create_access_token_has_expiry(self):
        from jose import jwt
        auth = Authentication(client=None)
        token = auth.create_access_token(
            data={"sub": "acc", "scopes": []},
            expires_delta=timedelta(minutes=15),
        )
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        assert "exp" in payload


# ---------------------------------------------------------------------------
# Demo seeding tests
# ---------------------------------------------------------------------------

class TestDemoSeedResponse:
    def test_demo_seed_response_model(self):
        """Test that DemoSeedResponse model accepts correct data structure"""
        response = DemoSeedResponse(
            work_id="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
            title="Demo: The Lighthouse at the End of the World",
            total_nodes=10,
            by_type={"part": 2, "chapter": 2, "scene": 6}
        )
        assert response.work_id == "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
        assert response.title == "Demo: The Lighthouse at the End of the World"
        assert response.total_nodes == 10
        assert response.by_type == {"part": 2, "chapter": 2, "scene": 6}


class TestBuildDemoTree:
    def test_build_demo_tree_returns_correct_structure(self):
        """Test that build_demo_tree function returns correct structure"""
        from app.demo import build_demo_tree
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        assert isinstance(work_data, CreateWorkRequest)
        assert isinstance(node_list, list)
        assert len(node_list) == 10
        
        first_node = node_list[0]
        assert hasattr(first_node, "work_id")
        assert hasattr(first_node, "node_type")
        assert hasattr(first_node, "parent_id")
        assert hasattr(first_node, "tag")
        assert hasattr(first_node, "description")
        assert hasattr(first_node, "text")
        assert hasattr(first_node, "previous")
        assert hasattr(first_node, "next")
        assert hasattr(first_node, "tags")

    def test_build_demo_tree_node_counts(self):
        """Test that build_demo_tree returns correct node counts by type"""
        from app.demo import build_demo_tree
        from app.models import NodeType
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        assert len(node_list) == 10
        
        by_type = {}
        for node in node_list:
            nt = node.node_type if isinstance(node.node_type, str) else node.node_type.value
            by_type[nt] = by_type.get(nt, 0) + 1
        
        assert by_type["part"] == 2
        assert by_type["chapter"] == 2
        assert by_type["scene"] == 6
        assert sum(by_type.values()) == 10

    def test_build_demo_tree_parent_references_valid(self):
        """Test that every parent_id references an existing node in the tree"""
        from app.demo import build_demo_tree
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        node_ids = {node.node_id for node in node_list}
        for node in node_list:
            parent_id = node.parent_id
            if parent_id is not None:
                assert parent_id in node_ids, f"parent_id {parent_id} not found in tree nodes"

    def test_build_demo_tree_sibling_groups_correct(self):
        """Test that sibling groups are correctly formed by parent_id"""
        from app.demo import build_demo_tree
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        siblings = {}
        for node in node_list:
            key = node.parent_id
            siblings.setdefault(key, []).append(node)
        
        # Root group (parent_id=None): 1 part
        assert len(siblings[None]) == 1
        
        # Under Part 1: 3 children (Scene 1, Chapter 1, Chapter 2)
        part_parent_id = siblings[None][0].node_id
        assert len(siblings[part_parent_id]) == 3

        # Chapter 1 has 3 children (Part 2, Scene 3, Scene 4)
        # Chapter 2 has 2 children (Scene 5, Scene 6)
        chapter_ids = [n.node_id for n in siblings[part_parent_id] if n.node_type.value == 'chapter']
        assert len(siblings[chapter_ids[0]]) == 3
        assert len(siblings[chapter_ids[1]]) == 2

    def test_build_demo_tree_previous_next_chains_valid(self):
        """Test that previous/next form unbroken linked lists within each sibling group"""
        from app.demo import build_demo_tree

        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")

        by_id = {node.node_id: node for node in node_list}

        siblings = {}
        for node in node_list:
            siblings.setdefault(node.parent_id, []).append(node)

        for parent_key, group in siblings.items():
            if len(group) == 1:
                assert group[0].previous is None
                assert group[0].next is None
                continue

            # Walk the linked list from head (previous=None) to tail
            heads = [n for n in group if n.previous is None]
            assert len(heads) == 1, f"Expected 1 head in group under {parent_key}, got {len(heads)}"
            tails = [n for n in group if n.next is None]
            assert len(tails) == 1, f"Expected 1 tail in group under {parent_key}, got {len(tails)}"

            visited = []
            current = heads[0]
            while current is not None:
                visited.append(current.node_id)
                next_id = current.next
                if next_id is not None:
                    assert next_id in by_id, f"next pointer {next_id} not in node list"
                    nxt = by_id[next_id]
                    assert nxt.previous == current.node_id, "back-pointer mismatch"
                    current = nxt
                else:
                    current = None

            assert len(visited) == len(group), "chain length != group size"
            assert set(visited) == {n.node_id for n in group}, "chain does not cover all nodes"

    def test_build_demo_tree_root_has_no_parent(self):
        """Test that the root Part node has parent_id=None"""
        from app.demo import build_demo_tree
        from app.models import NodeType
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        parts = [n for n in node_list if n.node_type == NodeType.part]
        assert len(parts) == 2
        roots = [p for p in parts if p.parent_id is None]
        assert len(roots) == 1
        assert roots[0].parent_id is None

    def test_build_demo_tree_author_propagated(self):
        """Test that the author from build_demo_tree matches the input"""
        from app.demo import build_demo_tree
        
        work_data, node_list = build_demo_tree("mock_account_id", "Alice")
        
        assert work_data.author == "Alice"

    def test_build_demo_tree_work_tags_no_demo(self):
        """Test that the demo work does not include 'demo' tag in initial tags"""
        from app.demo import build_demo_tree
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        assert "demo" not in work_data.tags

    def test_build_demo_tree_pure_function(self):
        """Test that build_demo_tree is pure — two calls return independent trees"""
        from app.demo import build_demo_tree
        
        work1, nodes1 = build_demo_tree("account_a", "Author A")
        work2, nodes2 = build_demo_tree("account_b", "Author B")
        
        assert work1.title == work2.title
        assert len(nodes1) == len(nodes2)
        
        # Different authors
        assert work1.author == "Author A"
        assert work2.author == "Author B"

    def test_build_demo_tree_all_tags_present(self):
        """Test that every node has a non-empty tags list"""
        from app.demo import build_demo_tree
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        for node in node_list:
            assert isinstance(node.tags, list)
            assert len(node.tags) > 0

    def test_build_demo_tree_all_descriptions_present(self):
        """Test that every node has a description and text"""
        from app.demo import build_demo_tree
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        for node in node_list:
            assert node.description is not None
            assert len(node.description) > 0
            assert node.text is not None
            assert len(node.text) > 0

    def test_build_demo_tree_hierarchy_depth(self):
        """Test that the tree respects flexible hierarchy rules (part/chapter/scene)"""
        from app.demo import build_demo_tree
        from app.models import NodeType
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        # Build parent->children map
        children_map = {}
        for node in node_list:
            parent_key = node.parent_id
            children_map.setdefault(parent_key, []).append(node)
        
        # Root (parent_id=None) -> exactly 1 part
        root = [n for n in node_list if n.parent_id is None]
        assert len(root) == 1
        assert root[0].node_type == NodeType.part

        # Part 1 children: scene + chapters (exercises Part->Scene and Part->Chapter)
        part1_children = children_map.get(root[0].node_id, [])
        assert any(n.node_type == NodeType.scene for n in part1_children)
        assert any(n.node_type == NodeType.chapter for n in part1_children)

        # Chapter 1 children: part + scenes (exercises Chapter->Part and Chapter->Scene)
        ch1 = [n for n in part1_children if n.tag == 'The Investigation'][0]
        ch1_children = children_map.get(ch1.node_id, [])
        assert any(n.node_type == NodeType.part for n in ch1_children)
        assert any(n.node_type == NodeType.scene for n in ch1_children)

        # Part 2 (nested) children: scene (exercises Part->Scene in nested context)
        part2 = [n for n in ch1_children if n.node_type == NodeType.part][0]
        part2_children = children_map.get(part2.node_id, [])
        assert all(n.node_type == NodeType.scene for n in part2_children)

        # No scene has children
        for node in node_list:
            if node.node_type == NodeType.scene:
                assert node.node_id not in children_map or len(children_map[node.node_id]) == 0


# ---------------------------------------------------------------------------
# Reading order — NodeStorage.get_reading_order  (E-89b)
# ---------------------------------------------------------------------------

class TestNodeStorageGetReadingOrder:

    def _make_node(self, node_id, parent_id, position, **kw):
        base = {
            "_id": ObjectId(),
            "node_id": node_id,
            "work_id": "w-1",
            "account_id": "a-1",
            "author": None,
            "node_type": "part",
            "parent_id": parent_id,
            "position": position,
            "tag": f"N-{node_id[:8]}",
            "description": None,
            "text": None,
            "previous": None,
            "next": None,
            "tags": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        base.update(kw)
        return base

    def _storage_with_nodes(self, nodes: list[dict]) -> NodeStorage:
        """Build a NodeStorage with its node_collection.find().to_list() mocked."""
        client = MagicMock()
        storage = NodeStorage(client)
        mock_cursor = AsyncMock()
        mock_cursor.to_list.return_value = [dict(n) for n in nodes]
        storage.node_collection.find = MagicMock(return_value=mock_cursor)
        return storage

    async def test_empty_work_returns_empty_list(self):
        storage = self._storage_with_nodes([])
        result = await storage.get_reading_order("w-1", "a-1")
        assert result == []

    async def test_single_root_node(self):
        node = self._make_node("n-1", None, 0)
        storage = self._storage_with_nodes([node])
        result = await storage.get_reading_order("w-1", "a-1")
        assert len(result) == 1
        assert result[0]["node_id"] == "n-1"
        assert "_id" not in result[0]

    async def test_pre_order_traversal_shape(self):
        n_part  = self._make_node("part-1", None, 0, node_type="part")
        n_ch0   = self._make_node("ch-0", "part-1", 0, node_type="chapter")
        n_ch1   = self._make_node("ch-1", "part-1", 1, node_type="chapter")
        n_sc0   = self._make_node("sc-0", "ch-0", 0, node_type="scene")
        n_sc1   = self._make_node("sc-1", "ch-0", 1, node_type="scene")
        nodes = [n_part, n_ch1, n_ch0, n_sc1, n_sc0]
        storage = self._storage_with_nodes(nodes)
        result = await storage.get_reading_order("w-1", "a-1")
        ids = [n["node_id"] for n in result]
        assert ids == ["part-1", "ch-0", "sc-0", "sc-1", "ch-1"]

    async def test_children_sorted_by_position(self):
        n_root  = self._make_node("root", None, 0)
        n_child_a = self._make_node("c-a", "root", 2, node_type="chapter")
        n_child_b = self._make_node("c-b", "root", 0, node_type="chapter")
        n_child_c = self._make_node("c-c", "root", 1, node_type="chapter")
        nodes = [n_root, n_child_a, n_child_b, n_child_c]
        storage = self._storage_with_nodes(nodes)
        result = await storage.get_reading_order("w-1", "a-1")
        ids = [n["node_id"] for n in result]
        assert ids == ["root", "c-b", "c-c", "c-a"]

    async def test_cycle_guard_skips_revisited_node(self):
        """A node that appears as its own ancestor is skipped with a log."""
        n_root = self._make_node("root", None, 0)
        n_child = self._make_node("child", "root", 0, node_type="chapter")
        # Simulate cycle: root appears again as child of child
        n_cycle = self._make_node("root", "child", 1, node_type="chapter", tag="cycle-dup")
        nodes = [n_root, n_child, n_cycle]
        storage = self._storage_with_nodes(nodes)
        result = await storage.get_reading_order("w-1", "a-1")
        ids = [n["node_id"] for n in result]
        assert ids == ["root", "child"]
        assert len(result) == 2

    async def test_id_stripped_from_every_node(self):
        n1 = self._make_node("n-1", None, 0)
        n2 = self._make_node("n-2", "n-1", 0)
        storage = self._storage_with_nodes([n1, n2])
        result = await storage.get_reading_order("w-1", "a-1")
        for node in result:
            assert "_id" not in node


# ---------------------------------------------------------------------------
# E-112: DB-level `beat` rejection test (CP 30)
# ---------------------------------------------------------------------------

class TestBeatRejectionDBLevel:
    """E-112: Verify MongoDB validator rejects node_type 'beat' at the database level."""

    @pytest.fixture
    def motor_client(self):
        client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGO_DETAILS"))
        yield client
        client.close()

    async def test_t_db_beat_rejected(self, motor_client):
        """T-DB-BEAT-01: Inserting node_type='beat' raises WriteError via MongoDB validator."""
        from pymongo import MongoClient
        from pymongo.errors import OperationFailure

        # Check if validator exists first (skip if not)
        client = MongoClient(os.getenv("MONGO_DETAILS"))
        db = client.fabulator
        try:
            info = db.node_collection.options()
            has_validator = "validator" in info and info["validator"] is not None
        except OperationFailure:
            pytest.skip("Cannot read collection options (no collMod permission)")
        finally:
            client.close()

        if not has_validator:
            pytest.skip("node_collection has no validator — cannot test beat rejection")

        # Attempt to insert a document with node_type='beat'
        try:
            await motor_client.fabulator.node_collection.insert_one({
                "node_id": str(uuid.uuid4()),
                "work_id": str(uuid.uuid4()),
                "account_id": "test_account",
                "author": None,
                "node_type": "beat",
                "parent_id": None,
                "position": 0,
                "tag": "Test Beat",
                "description": None,
                "text": None,
                "previous": None,
                "next": None,
                "tags": [],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
        except OperationFailure as e:
            assert "beat" in str(e).lower() or "validator" in str(e).lower(), (
                f"Expected validator rejection for 'beat', got: {e}"
            )
            return

        pytest.fail("Expected WriteError/OperationFailure for node_type='beat' but insert succeeded")


# ---------------------------------------------------------------------------
# Hierarchy validation — is_valid_parent_child  (DD-11 rules)
# ---------------------------------------------------------------------------

class TestHierarchyValidator:
    """DD-11 flexible hierarchy rules via is_valid_parent_child()."""

    def test_none_to_part_valid(self):
        assert is_valid_parent_child(None, "part") is True

    def test_part_to_part_valid(self):
        assert is_valid_parent_child("part", "part") is True

    def test_part_to_chapter_valid(self):
        assert is_valid_parent_child("part", "chapter") is True

    def test_part_to_scene_valid(self):
        assert is_valid_parent_child("part", "scene") is True

    def test_chapter_to_part_valid(self):
        assert is_valid_parent_child("chapter", "part") is True

    def test_chapter_to_chapter_valid(self):
        assert is_valid_parent_child("chapter", "chapter") is True

    def test_chapter_to_scene_valid(self):
        assert is_valid_parent_child("chapter", "scene") is True

    def test_scene_has_no_children(self):
        assert is_valid_parent_child("scene", "part") is False
        assert is_valid_parent_child("scene", "chapter") is False
        assert is_valid_parent_child("scene", "scene") is False

    def test_none_to_non_part_invalid(self):
        assert is_valid_parent_child(None, "chapter") is False
        assert is_valid_parent_child(None, "scene") is False

    def test_unknown_parent_types_return_false(self):
        assert is_valid_parent_child("invalid", "part") is False
        assert is_valid_parent_child(None, "invalid") is False


# ---------------------------------------------------------------------------
# Cycle detection — NodeStorage.would_create_cycle  (migrated from Phase 10)
# ---------------------------------------------------------------------------

class TestNodeStorageWouldCreateCycle:
    """Tests for NodeStorage.would_create_cycle() using mocked DB."""

    def _mock_motor_client(self):
        mongo_client = MagicMock()
        db = MagicMock()
        collection = MagicMock()
        mongo_client.__getitem__ = lambda self, name: db
        db.__getitem__ = lambda self, name: collection
        return mongo_client, collection

    def _make_storage(self):
        mongo_client, collection = self._mock_motor_client()
        storage = NodeStorage(client=mongo_client)
        storage.node_collection = collection
        return storage

    async def test_direct_cycle_returns_true(self):
        """Reparent A under B when B is child of A -> cycle detected."""
        storage = self._make_storage()
        storage.node_collection.find_one = AsyncMock(
            return_value={"parent_id": "node-A"}
        )
        result = await storage.would_create_cycle(
            node_id="node-A", new_parent_id="node-B", account_id="acc1",
        )
        assert result is True

    async def test_indirect_cycle_returns_true(self):
        """Chain A->B->C->D: reparenting A under D creates indirect cycle."""
        storage = self._make_storage()
        storage.node_collection.find_one = AsyncMock(
            side_effect=[
                {"parent_id": "node-B"},
                {"parent_id": "node-C"},
                {"parent_id": "node-D"},
                {"parent_id": "node-A"},
            ]
        )
        result = await storage.would_create_cycle(
            node_id="node-A", new_parent_id="node-E", account_id="acc1",
        )
        assert result is True

    async def test_no_cycle_returns_false(self):
        """Unrelated subtree -> no cycle."""
        storage = self._make_storage()
        storage.node_collection.find_one = AsyncMock(
            side_effect=[
                {"parent_id": "node-B"},
                {"parent_id": "node-C"},
                {"parent_id": None},
            ]
        )
        result = await storage.would_create_cycle(
            node_id="node-A", new_parent_id="node-X", account_id="acc1",
        )
        assert result is False

    async def test_no_cycle_unrelated_subtree_returns_false(self):
        """Node with entirely separate ancestry -> no cycle."""
        storage = self._make_storage()
        storage.node_collection.find_one = AsyncMock(
            return_value={"parent_id": None}
        )
        result = await storage.would_create_cycle(
            node_id="node-A", new_parent_id="node-Z", account_id="acc1",
        )
        assert result is False

    async def test_node_not_in_collection_breaks_search(self):
        """If node not found, walk ends and returns False (no cycle)."""
        storage = self._make_storage()
        storage.node_collection.find_one = AsyncMock(return_value=None)
        result = await storage.would_create_cycle(
            node_id="node-A", new_parent_id="node-Q", account_id="acc1",
        )
        assert result is False


# ---------------------------------------------------------------------------
# Sibling renumbering — NodeStorage.reorder_siblings  (migrated from Phase 10)
# ---------------------------------------------------------------------------

class TestNodeStorageReorderSiblings:
    """Tests for NodeStorage.reorder_siblings() using mocked DB."""

    def _node(self, node_id, position, parent_id="p-1", node_type="chapter"):
        return {
            "node_id": node_id,
            "work_id": "w-1",
            "account_id": "a-1",
            "node_type": node_type,
            "parent_id": parent_id,
            "position": position,
            "tag": f"N-{node_id[:8]}",
            "author": None,
            "description": None,
            "text": None,
            "previous": None,
            "next": None,
            "tags": [],
        }

    def _make_storage(self):
        client = MagicMock()
        storage = NodeStorage(client)
        storage.node_collection.update_one = AsyncMock()
        return storage

    async def test_insert_at_end_clamped(self):
        """Position > max index clamps to end of list."""
        storage = self._make_storage()
        storage.get_node = AsyncMock(return_value=self._node("A", 0))
        cursor = AsyncMock()
        cursor.to_list.return_value = [
            self._node("A", 0), self._node("B", 1), self._node("C", 2),
        ]
        storage.node_collection.find = MagicMock(return_value=cursor)
        result = await storage.reorder_siblings(
            node_id="A", account_id="a-1", new_position=999,
        )
        assert result is not None
        assert result["node_id"] == "A"

    async def test_insert_at_start(self):
        """Moving node from end to start shifts others right."""
        storage = self._make_storage()
        storage.get_node = AsyncMock(return_value=self._node("C", 2))
        cursor = AsyncMock()
        cursor.to_list.return_value = [
            self._node("C", 2), self._node("A", 0), self._node("B", 1),
        ]
        storage.node_collection.find = MagicMock(return_value=cursor)
        result = await storage.reorder_siblings(
            node_id="C", account_id="a-1", new_position=0,
        )
        assert result is not None
        assert result["node_id"] == "C"

    async def test_node_not_found_returns_none(self):
        """If the source node is not found, return None."""
        storage = self._make_storage()
        storage.get_node = AsyncMock(return_value=None)
        result = await storage.reorder_siblings(
            node_id="X", account_id="a-1", new_position=0,
        )
        assert result is None

    async def test_remove_from_middle(self):
        """Removing middle node and inserting at end."""
        storage = self._make_storage()
        storage.get_node = AsyncMock(return_value=self._node("B", 1))
        cursor = AsyncMock()
        cursor.to_list.return_value = [
            self._node("B", 1), self._node("C", 2), self._node("A", 0),
        ]
        storage.node_collection.find = MagicMock(return_value=cursor)
        result = await storage.reorder_siblings(
            node_id="B", account_id="a-1", new_position=2,
        )
        assert result is not None
        assert result["node_id"] == "B"

    async def test_single_node_clamped_to_zero(self):
        """Only node stays at position 0."""
        storage = self._make_storage()
        storage.get_node = AsyncMock(return_value=self._node("A", 0))
        cursor = AsyncMock()
        cursor.to_list.return_value = [self._node("A", 0)]
        storage.node_collection.find = MagicMock(return_value=cursor)
        result = await storage.reorder_siblings(
            node_id="A", account_id="a-1", new_position=999,
        )
        assert result is not None
        assert result["node_id"] == "A"


# ---------------------------------------------------------------------------
# Duplicate — NodeStorage.duplicate_shallow / duplicate_deep  (migrated from Phase 10)
# ---------------------------------------------------------------------------

class TestNodeStorageDuplicate:
    """Tests for NodeStorage.duplicate_shallow() and duplicate_deep()."""

    def _make_storage(self):
        mongo_client = MagicMock()
        db = MagicMock()
        collection = MagicMock()
        mongo_client.__getitem__ = lambda self, name: db
        db.__getitem__ = lambda self, name: collection
        storage = NodeStorage(client=mongo_client)
        storage.node_collection = collection
        return storage

    def _make_node(self, node_id, node_type, position, tag,
                   parent_id="parent-1", work_id="work-1"):
        return {
            "node_id": node_id,
            "node_type": node_type,
            "parent_id": parent_id,
            "work_id": work_id,
            "account_id": "acc1",
            "position": position,
            "tag": tag,
            "author": None,
            "description": None,
            "text": None,
            "previous": None,
            "next": None,
            "tags": [],
        }

    async def test_shallow_duplicate_position(self):
        """Copy is placed at original.position + 1."""
        storage = self._make_storage()
        source = self._make_node("node-A", "chapter", 2, "Chapter One")
        storage.get_node = AsyncMock(return_value=source)
        storage.node_collection.update_many = AsyncMock()
        storage.node_collection.insert_one = AsyncMock()
        result = await storage.duplicate_shallow(
            node_id="node-A", account_id="acc1",
        )
        assert result is not None
        assert result["position"] == 3
        storage.node_collection.update_many.assert_called_once()
        storage.node_collection.insert_one.assert_called_once()

    async def test_shallow_duplicate_tag_suffix(self):
        """Copy tag is '{source.tag} (copy)'; node_id is a fresh UUID."""
        storage = self._make_storage()
        source = self._make_node("node-A", "chapter", 0, "Chapter One")
        storage.get_node = AsyncMock(return_value=source)
        storage.node_collection.update_many = AsyncMock()
        storage.node_collection.insert_one = AsyncMock()
        result = await storage.duplicate_shallow(
            node_id="node-A", account_id="acc1",
        )
        assert result is not None
        assert result["tag"] == "Chapter One (copy)"
        assert result["node_id"] != "node-A"

    async def test_deep_duplicate_root_position_and_tag(self):
        """duplicate_deep root copy is at original.position + 1 with ' (copy)' suffix."""
        storage = self._make_storage()
        source = self._make_node("node-A", "chapter", 0, "Chapter One")
        storage.get_node = AsyncMock(return_value=source)
        storage.node_collection.find = MagicMock()
        cursor = AsyncMock()
        cursor.to_list.return_value = []
        storage.node_collection.find.return_value = cursor
        storage.node_collection.update_many = AsyncMock()
        storage.node_collection.insert_one = AsyncMock()
        result = await storage.duplicate_deep(
            node_id="node-A", account_id="acc1",
        )
        assert result is not None
        assert result["position"] == 1
        assert result["tag"] == "Chapter One (copy)"
        assert result["node_id"] != "node-A"

    async def test_scene_shallow_duplicate_permitted(self):
        """Scene nodes can be shallow-duplicated (returns copy)."""
        storage = self._make_storage()
        source = self._make_node("node-S", "scene", 0, "Scene One")
        storage.get_node = AsyncMock(return_value=source)
        storage.node_collection.update_many = AsyncMock()
        storage.node_collection.insert_one = AsyncMock()
        result = await storage.duplicate_shallow(
            node_id="node-S", account_id="acc1",
        )
        assert result is not None
        assert result["tag"] == "Scene One (copy)"


# ---------------------------------------------------------------------------
# Author propagation — NodeStorage (migrated from Phase 10)
# ---------------------------------------------------------------------------

class TestNodeStorageAuthorPropagation:
    """Tests for author field propagation during node creation."""

    def _make_storage(self):
        client = MagicMock()
        storage = NodeStorage(client)
        storage.node_collection.find_one = AsyncMock(return_value=None)
        storage.node_collection.insert_one = AsyncMock()
        return storage

    async def test_non_null_author_propagates_to_node(self):
        """Author from Work is copied onto the node when non-null."""
        storage = self._make_storage()
        work_doc = {"work_id": "w-1", "account_id": "a-1", "author": "Alice", "title": "Test"}
        data = {"work_id": "w-1", "node_type": "part", "parent_id": None, "tag": "Root"}
        result = await storage.create_node(
            account_id="a-1", work_doc=work_doc, data=data,
        )
        assert result["author"] == "Alice"

    async def test_null_author_handled(self):
        """None author from Work is propagated to the node."""
        storage = self._make_storage()
        work_doc = {"work_id": "w-1", "account_id": "a-1", "author": None, "title": "Test"}
        data = {"work_id": "w-1", "node_type": "part", "parent_id": None, "tag": "Root"}
        result = await storage.create_node(
            account_id="a-1", work_doc=work_doc, data=data,
        )
        assert result["author"] is None



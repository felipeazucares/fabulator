"""
Unit tests — no MongoDB or Redis required.

Covers:
  - Pydantic model validation (models.py)
  - users_saves_helper (models.py)
  - Authentication helpers: verify_password, get_password_hash, create_access_token
"""

import pytest
from datetime import timedelta
from bson.objectid import ObjectId
from pydantic import ValidationError

# Ensure .env is loaded before importing app modules
import app.config  # noqa: F401

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
            total_nodes=11,
            by_type={"part": 1, "chapter": 2, "scene": 4, "beat": 4}
        )
        assert response.work_id == "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
        assert response.title == "Demo: The Lighthouse at the End of the World"
        assert response.total_nodes == 11
        assert response.by_type == {"part": 1, "chapter": 2, "scene": 4, "beat": 4}


class TestBuildDemoTree:
    def test_build_demo_tree_returns_correct_structure(self):
        """Test that build_demo_tree function returns correct structure"""
        from app.demo import build_demo_tree
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        assert isinstance(work_data, CreateWorkRequest)
        assert isinstance(node_list, list)
        assert len(node_list) > 0
        
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
        """Test that build_demo_tree returns exactly 11 nodes with correct type distribution"""
        from app.demo import build_demo_tree
        from app.models import NodeType
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        assert len(node_list) == 11
        
        by_type = {}
        for node in node_list:
            nt = node.node_type if isinstance(node.node_type, str) else node.node_type.value
            by_type[nt] = by_type.get(nt, 0) + 1
        
        assert by_type["part"] == 1
        assert by_type["chapter"] == 2
        assert by_type["scene"] == 4
        assert by_type["beat"] == 4

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
        
        # Chapter group (under Part): 2 chapters
        part_parent_id = siblings[None][0].node_id
        assert len(siblings[part_parent_id]) == 2

        # Scene groups: 2 scenes under ch1, 2 scenes under ch2
        chapter_ids = [n.node_id for n in siblings[part_parent_id]]
        scene_counts = {ch_id: len(siblings[ch_id]) for ch_id in chapter_ids}
        assert scene_counts[chapter_ids[0]] == 2
        assert scene_counts[chapter_ids[1]] == 2

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
        """Test that the single Part node has parent_id=None"""
        from app.demo import build_demo_tree
        from app.models import NodeType
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        parts = [n for n in node_list if n.node_type == NodeType.part]
        assert len(parts) == 1
        assert parts[0].parent_id is None

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
        """Test that the tree has exactly 4 levels: part -> chapter -> scene -> beat"""
        from app.demo import build_demo_tree
        from app.models import NodeType
        
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        # Build parent->children map
        children_map = {}
        for node in node_list:
            parent_key = node.parent_id
            children_map.setdefault(parent_key, []).append(node)
        
        # Part (root) -> chapters
        part = [n for n in node_list if n.node_type == NodeType.part][0]
        chapters = children_map.get(part.node_id, [])
        assert all(n.node_type == NodeType.chapter for n in chapters)

        # Chapters -> scenes
        scene_count = 0
        for ch in chapters:
            scenes = children_map.get(ch.node_id, [])
            assert all(n.node_type == NodeType.scene for n in scenes)
            scene_count += len(scenes)
        assert scene_count == 4

        # Scenes -> beats
        beat_count = 0
        for node in node_list:
            if node.node_type == NodeType.scene:
                beats = children_map.get(node.node_id, [])
                assert all(n.node_type == NodeType.beat for n in beats)
                beat_count += len(beats)
        assert beat_count == 4



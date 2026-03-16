"""
Unit tests — no MongoDB or Redis required.

Covers:
  - Pydantic model validation (models.py)
  - saves_helper / users_saves_helper (models.py)
  - Authentication helpers: verify_password, get_password_hash, create_access_token
  - Tree operations: build_tree_from_dict, add_a_node, TreeDepthLimitExceeded
"""

import os
import pytest
from datetime import timedelta
from bson.objectid import ObjectId
from pydantic import ValidationError
from treelib import Tree
from fastapi.encoders import jsonable_encoder

# Ensure .env is loaded before importing app modules
import app.config  # noqa: F401

from app.models import (
    RequestAddSchema,
    RequestUpdateSchema,
    NodePayload,
    UserDetails,
    UserType,
    UpdateUserType,
    saves_helper,
    users_saves_helper,
    UUID_PATTERN,
    NODE_NAME_MAX_LEN,
    DESCRIPTION_MAX_LEN,
    TEXT_MAX_LEN,
    LINK_FIELD_MAX_LEN,
    TAGS_MAX_COUNT,
    TAG_MAX_LEN,
)
from app.authentication import Authentication, pwd_context
from app.database import TreeStorage, TreeDepthLimitExceeded, MAX_TREE_DEPTH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_motor_client():
    """Return a Motor client connected to the configured MongoDB instance.

    The unit tests that call build_tree_from_dict never await any DB
    operation — they only use the synchronous tree-building methods on
    TreeStorage.  We still need a real client to satisfy __init__, but
    no network calls are made during these tests.
    """
    import motor.motor_asyncio
    return motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGO_DETAILS"))


def _make_tree_storage() -> TreeStorage:
    return TreeStorage(collection_name="tree_collection", client=_minimal_motor_client())


def _serialised_tree(depth: int) -> dict:
    """Return a jsonable_encoder'd treelib Tree with a linear chain of `depth` nodes."""
    tree = Tree()
    parent_id = None
    for i in range(depth):
        node = tree.create_node(tag=f"node_{i}", parent=parent_id)
        parent_id = node.identifier
    return jsonable_encoder(tree)


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
# saves_helper
# ---------------------------------------------------------------------------

class TestSavesHelper:

    def test_returns_expected_keys(self):
        raw = {
            "account_id": "acc123",
            "tree": {"root": "abc", "_nodes": {}},
            "date_time": "2026-01-01T00:00:00",
        }
        result = saves_helper(raw)
        assert result["account_id"] == "acc123"
        assert result["tree"] == {"root": "abc", "_nodes": {}}
        assert result["date_time"] == "2026-01-01T00:00:00"

    def test_account_id_coerced_to_string(self):
        raw = {"account_id": 42, "tree": {}, "date_time": "2026-01-01"}
        result = saves_helper(raw)
        assert isinstance(result["account_id"], str)


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
# Tree operations — build_tree_from_dict / add_a_node
# ---------------------------------------------------------------------------

class TestBuildTreeFromDict:

    def test_round_trip_single_node(self):
        storage = _make_tree_storage()
        tree = Tree()
        tree.create_node(tag="root")
        tree_dict = jsonable_encoder(tree)
        result = storage.build_tree_from_dict(tree_dict=tree_dict)
        assert result.size() == 1
        assert result.root is not None

    def test_round_trip_parent_child(self):
        storage = _make_tree_storage()
        tree = Tree()
        root = tree.create_node(tag="root")
        tree.create_node(tag="child", parent=root.identifier)
        tree_dict = jsonable_encoder(tree)
        result = storage.build_tree_from_dict(tree_dict=tree_dict)
        assert result.size() == 2

    def test_round_trip_preserves_tags(self):
        storage = _make_tree_storage()
        tree = Tree()
        tree.create_node(tag="my_root_node")
        tree_dict = jsonable_encoder(tree)
        result = storage.build_tree_from_dict(tree_dict=tree_dict)
        root_node = result.get_node(result.root)
        assert root_node.tag == "my_root_node"

    def test_missing_root_raises_key_error(self):
        storage = _make_tree_storage()
        with pytest.raises(KeyError):
            storage.build_tree_from_dict(tree_dict={"_identifier": "abc", "_nodes": {}})

    def test_depth_limit_exceeded_raises(self):
        storage = _make_tree_storage()
        deep_dict = _serialised_tree(MAX_TREE_DEPTH + 2)
        with pytest.raises(TreeDepthLimitExceeded) as exc_info:
            storage.build_tree_from_dict(tree_dict=deep_dict)
        assert exc_info.value.depth > exc_info.value.limit

    def test_depth_at_limit_succeeds(self):
        storage = _make_tree_storage()
        boundary_dict = _serialised_tree(MAX_TREE_DEPTH)
        result = storage.build_tree_from_dict(tree_dict=boundary_dict)
        assert result.size() == MAX_TREE_DEPTH

    def test_depth_under_limit_succeeds(self):
        storage = _make_tree_storage()
        shallow_dict = _serialised_tree(MAX_TREE_DEPTH - 1)
        result = storage.build_tree_from_dict(tree_dict=shallow_dict)
        assert result.size() == MAX_TREE_DEPTH - 1

    def test_depth_limit_exception_carries_values(self):
        storage = _make_tree_storage()
        deep_dict = _serialised_tree(MAX_TREE_DEPTH + 5)
        with pytest.raises(TreeDepthLimitExceeded) as exc_info:
            storage.build_tree_from_dict(tree_dict=deep_dict)
        exc = exc_info.value
        assert exc.limit == MAX_TREE_DEPTH
        assert "exceeds" in str(exc)

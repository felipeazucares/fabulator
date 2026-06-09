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
        
        # Test with a mock account_id and author
        work_data, node_list = build_demo_tree("mock_account_id", "Mock Author")
        
        # Should return a tuple of (work_data, list_of_nodes)
        assert isinstance(work_data, CreateWorkRequest)
        assert isinstance(node_list, list)
        assert len(node_list) > 0
        
        # Check that first node has expected structure
        first_node = node_list[0]
        assert "work_id" in first_node
        assert "node_type" in first_node
        assert "parent_id" in first_node
        assert "tag" in first_node
        assert "description" in first_node
        assert "text" in first_node
        assert "previous" in first_node
        assert "next" in first_node
        assert "tags" in first_node



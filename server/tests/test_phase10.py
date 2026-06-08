"""
Phase 10 unit tests: T-41 (hierarchy validator) and T-42 (cycle detection).

These are standalone tests that do not require the rest of the test suite's
dependencies to be satisfied.
"""

import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock

from app.database import (
    is_valid_parent_child,
    NodeStorage,
)


# ===========================================================================
# T-41: Hierarchy validator - is_valid_parent_child
# ===========================================================================


class TestIsValidParentChild:
    """Tests for the _VALID_CHILD hierarchy map via is_valid_parent_child().

    The valid parent->child pairs are:
        None          -> "part"
          "part"        -> "chapter"
          "chapter"     -> "scene"
          "scene"       -> "beat"
          "beat"        -> None
    """

    # --- Valid pairs ---

    def test_none_to_part_valid(self):
        assert is_valid_parent_child(None, "part") is True

    def test_part_to_chapter_valid(self):
        assert is_valid_parent_child("part", "chapter") is True

    def test_chapter_to_scene_valid(self):
        assert is_valid_parent_child("chapter", "scene") is True

    def test_scene_to_beat_valid(self):
        assert is_valid_parent_child("scene", "beat") is True

    def test_beat_to_none_valid(self):
        assert is_valid_parent_child("beat", None) is True

    # --- Invalid pairs: direct negations of valid rules ---

    def test_none_to_non_part_invalid(self):
        assert is_valid_parent_child(None, "chapter") is False

    def test_none_to_beat_invalid(self):
        assert is_valid_parent_child(None, "beat") is False

    def test_part_to_non_chapter_invalid(self):
        assert is_valid_parent_child("part", "scene") is False

    def test_chapter_to_non_scene_invalid(self):
        assert is_valid_parent_child("chapter", "beat") is False

    def test_scene_to_non_beat_invalid(self):
        assert is_valid_parent_child("scene", "part") is False

    def test_beat_to_non_none_invalid(self):
        assert is_valid_parent_child("beat", "chapter") is False

    # --- Invalid pairs: cross-level violations ---

    def test_part_to_part_invalid(self):
        assert is_valid_parent_child("part", "part") is False

    def test_chapter_to_part_invalid(self):
        assert is_valid_parent_child("chapter", "part") is False

    def test_scene_to_part_invalid(self):
        assert is_valid_parent_child("scene", "part") is False

    def test_beat_to_chapter_invalid(self):
        assert is_valid_parent_child("beat", "chapter") is False

    def test_beat_to_scene_invalid(self):
        assert is_valid_parent_child("beat", "scene") is False

    def test_part_to_scene_invalid(self):
        assert is_valid_parent_child("part", "scene") is False

    def test_chapter_to_scene_valid_recheck(self):
        """chapter -> scene is actually valid per _VALID_CHILD."""
        assert is_valid_parent_child("chapter", "scene") is True


# ===========================================================================
# T-42: Cycle detection - NodeStorage.would_create_cycle
# ===========================================================================


class TestWouldCreateCycle(unittest.TestCase):
    """Tests for NodeStorage.would_create_cycle().

    Simulates MongoDB node_collection.find_one() responses to trace
    parent_id chains and verify cycle detection logic.
    """

    def _mock_motor_client(self):
        mongo_client = MagicMock()
        db = MagicMock()
        collection = MagicMock()
        mongo_client.__getitem__ = lambda self, name: db
        db.__getitem__ = lambda self, name: collection
        return mongo_client, collection

    def _make_node_storage(self):
        mongo_client, collection = self._mock_motor_client()
        storage = NodeStorage(client=mongo_client)
        storage.node_collection = collection
        return storage

    def test_direct_cycle_returns_true(self):
        """Reparent A under B when B is child of A -> cycle detected."""
        storage = self._make_node_storage()
        collection = storage.node_collection

        async def _test():
            collection.find_one = AsyncMock(
                return_value={"parent_id": "node-A"}
            )
            result = await storage.would_create_cycle(
                node_id="node-A",
                new_parent_id="node-B",
                account_id="acc1",
            )
            self.assertEqual(result, True)

        asyncio.get_event_loop().run_until_complete(_test())

    def test_indirect_cycle_returns_true(self):
        """Chain A->B->C->D: reparenting A under D creates indirect cycle."""
        storage = self._make_node_storage()
        collection = storage.node_collection

        async def _test():
            collection.find_one = AsyncMock(side_effect=[
                {"parent_id": "node-C"},
                {"parent_id": "node-B"},
                {"parent_id": "node-A"},
            ])
            result = await storage.would_create_cycle(
                node_id="node-A",
                new_parent_id="node-D",
                account_id="acc1",
            )
            self.assertEqual(result, True)
            self.assertEqual(collection.find_one.call_count, 3)

        asyncio.get_event_loop().run_until_complete(_test())

    def test_no_cycle_returns_false(self):
        """Reparenting A under unrelated subtree returns False."""
        storage = self._make_node_storage()
        collection = storage.node_collection

        async def _test():
            collection.find_one = AsyncMock(side_effect=[
                {"parent_id": "node-Y"},
                None,
            ])
            result = await storage.would_create_cycle(
                node_id="node-A",
                new_parent_id="node-X",
                account_id="acc1",
            )
            self.assertEqual(result, False)
            self.assertEqual(collection.find_one.call_count, 2)

        asyncio.get_event_loop().run_until_complete(_test())

    def test_no_cycle_unrelated_subtree_returns_false(self):
        """Reparenting X under Y when they share no ancestor returns False."""
        storage = self._make_node_storage()
        collection = storage.node_collection

        async def _test():
            collection.find_one = AsyncMock(side_effect=[
                {"parent_id": "node-Y"},
                None,
            ])
            result = await storage.would_create_cycle(
                node_id="node-X",
                new_parent_id="node-Z",
                account_id="acc1",
            )
            self.assertEqual(result, False)

        asyncio.get_event_loop().run_until_complete(_test())

    def test_node_not_in_collection_breaks_search(self):
        """If node not in collection, walk ends and returns False (no cycle)."""
        storage = self._make_node_storage()
        collection = storage.node_collection

        async def _test():
            collection.find_one = AsyncMock(side_effect=[None])
            result = await storage.would_create_cycle(
                node_id="node-A",
                new_parent_id="node-B",
                account_id="acc1",
            )
            self.assertEqual(result, False)

        asyncio.get_event_loop().run_until_complete(_test())

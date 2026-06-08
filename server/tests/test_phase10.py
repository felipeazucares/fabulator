"""
Phase 10 unit tests: T-41 (hierarchy validator) and T-42 (cycle detection).

These are standalone tests that do not require the rest of the test suite's
dependencies to be satisfied.
"""

import asyncio
import re
import unittest
from unittest.mock import MagicMock, AsyncMock, call

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


# ===========================================================================
# T-43: Sibling renumbering - NodeStorage.reorder_siblings
# ===========================================================================


class TestReorderSiblings(unittest.TestCase):
    """Tests for NodeStorage.reorder_siblings().

    T-UNIT-05: insert at start — move last sibling to position 0
    T-UNIT-06: insert at end — position clamped when request exceeds max
    T-UNIT-07: remove from middle — move middle sibling to last position
    T-UNIT-08: single-node group clamped to position 0
    T-UNIT-09: node not found returns None without touching collection
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

    def _make_node(self, node_id, position, parent_id="parent-1", work_id="work-1"):
        return {
            "node_id": node_id,
            "parent_id": parent_id,
            "work_id": work_id,
            "account_id": "acc1",
            "position": position,
        }

    def _wire_find(self, storage, siblings):
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=siblings)
        storage.node_collection.find = MagicMock(return_value=cursor)

    def test_insert_at_start(self):
        """T-UNIT-05: Move last sibling (position 2) to position 0.
        Expected order after reorder: [C, A, B] → positions 0, 1, 2."""
        storage = self._make_node_storage()
        node_a = self._make_node("node-A", 0)
        node_b = self._make_node("node-B", 1)
        node_c = self._make_node("node-C", 2)
        siblings = [node_a, node_b, node_c]

        storage.get_node = AsyncMock(side_effect=[node_c, {**node_c, "position": 0}])
        self._wire_find(storage, siblings)
        storage.node_collection.update_one = AsyncMock()

        async def _test():
            result = await storage.reorder_siblings(
                node_id="node-C",
                account_id="acc1",
                new_position=0,
            )
            self.assertEqual(storage.node_collection.update_one.call_count, 3)
            self.assertEqual(storage.node_collection.update_one.call_args_list, [
                call({"node_id": "node-C"}, {"$set": {"position": 0}}),
                call({"node_id": "node-A"}, {"$set": {"position": 1}}),
                call({"node_id": "node-B"}, {"$set": {"position": 2}}),
            ])
            self.assertEqual(result["position"], 0)

        asyncio.get_event_loop().run_until_complete(_test())

    def test_insert_at_end_clamped(self):
        """T-UNIT-06: Move first sibling (position 0) to position 99.
        Expected: clamped to 2 → order [B, C, A] → positions 0, 1, 2."""
        storage = self._make_node_storage()
        node_a = self._make_node("node-A", 0)
        node_b = self._make_node("node-B", 1)
        node_c = self._make_node("node-C", 2)
        siblings = [node_a, node_b, node_c]

        storage.get_node = AsyncMock(side_effect=[node_a, {**node_a, "position": 2}])
        self._wire_find(storage, siblings)
        storage.node_collection.update_one = AsyncMock()

        async def _test():
            result = await storage.reorder_siblings(
                node_id="node-A",
                account_id="acc1",
                new_position=99,
            )
            self.assertEqual(storage.node_collection.update_one.call_count, 3)
            self.assertEqual(storage.node_collection.update_one.call_args_list, [
                call({"node_id": "node-B"}, {"$set": {"position": 0}}),
                call({"node_id": "node-C"}, {"$set": {"position": 1}}),
                call({"node_id": "node-A"}, {"$set": {"position": 2}}),
            ])
            self.assertEqual(result["position"], 2)

        asyncio.get_event_loop().run_until_complete(_test())

    def test_remove_from_middle(self):
        """T-UNIT-07: Move middle sibling (position 1) to last position (3).
        Expected: order [A, C, D, B] → positions 0, 1, 2, 3."""
        storage = self._make_node_storage()
        node_a = self._make_node("node-A", 0)
        node_b = self._make_node("node-B", 1)
        node_c = self._make_node("node-C", 2)
        node_d = self._make_node("node-D", 3)
        siblings = [node_a, node_b, node_c, node_d]

        storage.get_node = AsyncMock(side_effect=[node_b, {**node_b, "position": 3}])
        self._wire_find(storage, siblings)
        storage.node_collection.update_one = AsyncMock()

        async def _test():
            result = await storage.reorder_siblings(
                node_id="node-B",
                account_id="acc1",
                new_position=3,
            )
            self.assertEqual(storage.node_collection.update_one.call_count, 4)
            self.assertEqual(storage.node_collection.update_one.call_args_list, [
                call({"node_id": "node-A"}, {"$set": {"position": 0}}),
                call({"node_id": "node-C"}, {"$set": {"position": 1}}),
                call({"node_id": "node-D"}, {"$set": {"position": 2}}),
                call({"node_id": "node-B"}, {"$set": {"position": 3}}),
            ])
            self.assertEqual(result["position"], 3)

        asyncio.get_event_loop().run_until_complete(_test())

    def test_single_node_clamped_to_zero(self):
        """T-UNIT-08: Single-sibling group; request position 5 clamped to 0."""
        storage = self._make_node_storage()
        node_a = self._make_node("node-A", 0)

        storage.get_node = AsyncMock(side_effect=[node_a, {**node_a, "position": 0}])
        self._wire_find(storage, [node_a])
        storage.node_collection.update_one = AsyncMock()

        async def _test():
            result = await storage.reorder_siblings(
                node_id="node-A",
                account_id="acc1",
                new_position=5,
            )
            self.assertEqual(storage.node_collection.update_one.call_count, 1)
            self.assertEqual(storage.node_collection.update_one.call_args_list, [
                call({"node_id": "node-A"}, {"$set": {"position": 0}}),
            ])
            self.assertEqual(result["position"], 0)

        asyncio.get_event_loop().run_until_complete(_test())

    def test_node_not_found_returns_none(self):
        """T-UNIT-09: get_node returns None → method returns None immediately;
        node_collection.find is never called."""
        storage = self._make_node_storage()
        storage.get_node = AsyncMock(return_value=None)
        storage.node_collection.find = MagicMock()

        async def _test():
            result = await storage.reorder_siblings(
                node_id="missing-node",
                account_id="acc1",
                new_position=0,
            )
            self.assertIsNone(result)
            storage.node_collection.find.assert_not_called()

        asyncio.get_event_loop().run_until_complete(_test())


# ===========================================================================
# T-44: Duplicate - NodeStorage.duplicate_shallow / duplicate_deep
# ===========================================================================


class TestDuplicateNode(unittest.TestCase):
    """Tests for NodeStorage.duplicate_shallow() and NodeStorage.duplicate_deep().

    T-UNIT-08: shallow duplicate places copy at original.position + 1
    T-UNIT-09: shallow duplicate appends ' (copy)' to the source tag
    T-UNIT-10: Beat guard returns None for both shallow and deep without writing
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

    def _wire_find(self, storage, documents):
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=documents)
        storage.node_collection.find = MagicMock(return_value=cursor)

    def test_shallow_duplicate_position(self):
        """T-UNIT-08: Copy is placed at original.position + 1."""
        storage = self._make_node_storage()
        source = self._make_node("node-A", "chapter", 2, "Chapter One")
        storage.get_node = AsyncMock(return_value=source)
        storage.node_collection.update_many = AsyncMock()
        storage.node_collection.insert_one = AsyncMock()

        async def _test():
            result = await storage.duplicate_shallow(
                node_id="node-A",
                account_id="acc1",
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["position"], 3)
            storage.node_collection.update_many.assert_called_once()
            storage.node_collection.insert_one.assert_called_once()

        asyncio.get_event_loop().run_until_complete(_test())

    def test_shallow_duplicate_tag_suffix(self):
        """T-UNIT-09: Copy tag is '{source.tag} (copy)'; node_id is a fresh UUID."""
        storage = self._make_node_storage()
        source = self._make_node("node-A", "chapter", 0, "Chapter One")
        storage.get_node = AsyncMock(return_value=source)
        storage.node_collection.update_many = AsyncMock()
        storage.node_collection.insert_one = AsyncMock()

        async def _test():
            result = await storage.duplicate_shallow(
                node_id="node-A",
                account_id="acc1",
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["tag"], "Chapter One (copy)")
            self.assertNotEqual(result["node_id"], "node-A")

        asyncio.get_event_loop().run_until_complete(_test())

    def test_beat_guard_shallow_returns_none(self):
        """T-UNIT-10a: duplicate_shallow returns None for Beat; no writes occur."""
        storage = self._make_node_storage()
        source = self._make_node("node-B", "beat", 0, "Beat One")
        storage.get_node = AsyncMock(return_value=source)
        storage.node_collection.update_many = AsyncMock()
        storage.node_collection.insert_one = AsyncMock()

        async def _test():
            result = await storage.duplicate_shallow(
                node_id="node-B",
                account_id="acc1",
            )
            self.assertIsNone(result)
            storage.node_collection.update_many.assert_not_called()
            storage.node_collection.insert_one.assert_not_called()

        asyncio.get_event_loop().run_until_complete(_test())

    def test_beat_guard_deep_returns_none(self):
        """T-UNIT-10b: duplicate_deep returns None for Beat; no writes occur."""
        storage = self._make_node_storage()
        source = self._make_node("node-B", "beat", 0, "Beat One")
        storage.get_node = AsyncMock(return_value=source)
        storage.node_collection.update_many = AsyncMock()
        storage.node_collection.insert_one = AsyncMock()

        async def _test():
            result = await storage.duplicate_deep(
                node_id="node-B",
                account_id="acc1",
            )
            self.assertIsNone(result)
            storage.node_collection.update_many.assert_not_called()
            storage.node_collection.insert_one.assert_not_called()

        asyncio.get_event_loop().run_until_complete(_test())

    def test_deep_duplicate_root_position_and_tag(self):
        """T-UNIT-10c: duplicate_deep root copy is at original.position + 1
        with ' (copy)' suffix; node_id is a fresh UUID."""
        storage = self._make_node_storage()
        source = self._make_node("node-P", "part", 1, "Part One")
        storage.get_node = AsyncMock(return_value=source)
        storage.node_collection.update_many = AsyncMock()
        storage.node_collection.insert_one = AsyncMock()
        self._wire_find(storage, [])

        async def _test():
            result = await storage.duplicate_deep(
                node_id="node-P",
                account_id="acc1",
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["position"], 2)
            self.assertEqual(result["tag"], "Part One (copy)")
            self.assertNotEqual(result["node_id"], "node-P")

        asyncio.get_event_loop().run_until_complete(_test())


# ===========================================================================
# T-45: Author propagation - NodeStorage.create_node author handling
# ===========================================================================


class TestAuthorPropagation(unittest.TestCase):
    """Tests for NodeStorage.create_node() author propagation.

    T-UNIT-11: Non-null author from Work document is copied to node
    T-UNIT-12: Null/missing author on Work results in node author None
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

    def _minimal_data(self) -> dict:
        return {
            "work_id":   "550e8400-e29b-41d4-a716-446655440000",
            "node_type": "part",
            "tag":       "Part One",
        }

    def test_non_null_author_propagates_to_node(self):
        """T-UNIT-11: work_doc has author='Alice' → node author is 'Alice'."""
        storage = self._make_node_storage()
        storage.node_collection.find_one = AsyncMock(return_value=None)
        storage.node_collection.insert_one = AsyncMock()

        async def _test():
            result = await storage.create_node(
                account_id="acc1",
                work_doc={"author": "Alice"},
                data=self._minimal_data(),
            )
            self.assertIsNotNone(result)
            self.assertEqual(result["author"], "Alice")
            storage.node_collection.insert_one.assert_called_once()
            inserted = storage.node_collection.insert_one.call_args[0][0]
            self.assertEqual(inserted["author"], "Alice")

        asyncio.get_event_loop().run_until_complete(_test())

    def test_null_author_handled(self):
        """T-UNIT-12: work_doc has no author → node author is None."""
        storage = self._make_node_storage()
        storage.node_collection.find_one = AsyncMock(return_value=None)
        storage.node_collection.insert_one = AsyncMock()

        async def _test():
            result = await storage.create_node(
                account_id="acc1",
                work_doc={},
                data=self._minimal_data(),
            )
            self.assertIsNotNone(result)
            self.assertIsNone(result["author"])
            storage.node_collection.insert_one.assert_called_once()
            inserted = storage.node_collection.insert_one.call_args[0][0]
            self.assertIsNone(inserted["author"])

        asyncio.get_event_loop().run_until_complete(_test())

    def test_null_author_explicit_handled(self):
        """T-UNIT-12b: work_doc has author=None → node author is None."""
        storage = self._make_node_storage()
        storage.node_collection.find_one = AsyncMock(return_value=None)
        storage.node_collection.insert_one = AsyncMock()

        async def _test():
            result = await storage.create_node(
                account_id="acc1",
                work_doc={"author": None},
                data=self._minimal_data(),
            )
            self.assertIsNotNone(result)
            self.assertIsNone(result["author"])
            storage.node_collection.insert_one.assert_called_once()
            inserted = storage.node_collection.insert_one.call_args[0][0]
            self.assertIsNone(inserted["author"])

        asyncio.get_event_loop().run_until_complete(_test())

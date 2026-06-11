from __future__ import annotations

import os
import uuid
import motor.motor_asyncio
from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder
from app.helpers import get_logger
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import (
    ConnectionFailure,
    InvalidOperation,
    OperationFailure,
    DuplicateKeyError,
)
from bson.errors import InvalidId

from .models import (
    UserDetails,
    UpdateUserDetails,
    UpdateUserPassword,
    UpdateUserType,
    users_saves_helper,
)


MONGO_DETAILS = os.getenv(key="MONGO_DETAILS")
MAX_TREE_DEPTH = int(os.getenv("MAX_TREE_DEPTH", "100"))

logger = get_logger(__name__)


class TreeDepthLimitExceeded(Exception):
    """Raised when tree reconstruction exceeds MAX_TREE_DEPTH."""

    def __init__(self, depth: int, limit: int):
        self.depth = depth
        self.limit = limit
        super().__init__(f"Tree depth {depth} exceeds maximum allowed depth of {limit}")



class UserStorage:
    def __init__(
        self, collection_name: str, client: motor.motor_asyncio.AsyncIOMotorClient
    ):
        self.client = client
        self.database = self.client.fabulator
        self.user_collection = self.database.get_collection(collection_name)
        self.tree_collection = self.database.get_collection("tree_collection")

    async def does_account_exist(self, account_id: str):
        """return true or false based on account_id existence"""
        logger.debug(f"does_account_exist({account_id}) called")
        try:
            user_deets = await self.user_collection.find_one({"account_id": account_id})
            if user_deets is not None:
                account_exists = True
            else:
                account_exists = False
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving user details from the database account_id was: {account_id}",
                exc_info=True,
            )
            raise
        return account_exists

    async def get_user_details_by_id(self, id: str):
        """return the a user's details given the document id"""
        logger.debug(f"get_user_details_by_id({id}) called")
        try:
            user_deets = await self.user_collection.find_one({"_id": ObjectId(id)})
            if user_deets is not None:
                user_details = UserDetails(**user_deets)
            else:
                user_details = None
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving user details from the database id was: {id}",
                exc_info=True,
            )
            raise
        return user_details

    async def get_user_details_by_account_id(self, account_id: str):
        """return the a user's details given their account_id"""
        logger.debug(f"get_user_details_by_account({account_id}) called")
        try:
            user_deets = await self.user_collection.find_one({"account_id": account_id})
            if user_deets is not None:
                user_details = UserDetails(**user_deets)
            else:
                user_details = None
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving user details from the database account_id was: {account_id}",
                exc_info=True,
            )
            raise
        return user_details

    async def get_user_details_by_username(self, username: str):
        """return the a user's details given their username - used for log in"""
        logger.debug(f"get_user_details_by_username({username}) called")
        try:
            user_deets = await self.user_collection.find_one({"username": username})
            if user_deets is not None:
                user_details = UserDetails(**user_deets)
            else:
                user_details = None
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving user details from the database username was: {username}",
                exc_info=True,
            )
            raise
        return user_details

    async def save_user_details(self, user: UserDetails) -> dict:
        """save a user's details into the user collection"""
        user_to_save = UserDetails(
            name={"firstname": user.name.firstname, "surname": user.name.surname},
            username=user.username,
            password=user.password,
            account_id=user.account_id,
            disabled=user.disabled,
            user_role=user.user_role,
            email=user.email,
            user_type=user.user_type,
        )

        logger.debug(f"save_user_details({user_to_save.account_id}) called")
        try:
            save_response = await self.user_collection.insert_one(
                jsonable_encoder(user_to_save)
            )
        except (DuplicateKeyError, ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured saving user details account_id was: {user_to_save.account_id}",
                exc_info=True,
            )
            raise
        try:
            new_user = await self.user_collection.find_one(
                {"_id": ObjectId(save_response.inserted_id)}
            )
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving new user from the database _id was: {save_response.inserted_id}",
                exc_info=True,
            )
            raise

        return users_saves_helper(new_user)

    async def update_user_details(
        self, account_id: str, user: UpdateUserDetails
    ) -> dict:
        """save a user's details into the user collection"""
        if user.email is not None and user.name is not None:
            logger.debug(f"update_user_details({account_id}) called")
            try:
                await self.user_collection.update_one(
                    {"account_id": account_id},
                    {
                        "$set": {
                            "name": {
                                "firstname": user.name.firstname,
                                "surname": user.name.surname,
                            },
                            "email": user.email,
                        }
                    },
                )
            except (ConnectionFailure, OperationFailure) as e:
                logger.error(
                    f"Exception occured updating user details id was: {account_id}",
                    exc_info=True,
                )
                raise
            try:
                updated_user = await self.user_collection.find_one(
                    {"account_id": account_id}
                )
            except (ConnectionFailure, OperationFailure) as e:
                logger.error(
                    f"Exception occured retrieving updated user from the database id was: {account_id}",
                    exc_info=True,
                )
                raise
        else:
            logger.error("Nothing to change")
            raise
        return users_saves_helper(updated_user)

    async def update_user_password(self, account_id, user: UpdateUserPassword) -> dict:
        """save a user's details into the user collection"""
        if user.new_password is not None:
            logger.debug(f"update_upassword({account_id}) called")
            try:
                await self.user_collection.update_one(
                    {"account_id": account_id},
                    {"$set": {"password": user.new_password}},
                )
            except (ConnectionFailure, OperationFailure) as e:
                logger.error(
                    f"Exception occured updating user password id was: {account_id}",
                    exc_info=True,
                )
                raise
            try:
                updated_user = await self.user_collection.find_one(
                    {"account_id": account_id}
                )
            except (ConnectionFailure, OperationFailure) as e:
                logger.error(
                    f"Exception occured retrieving updated user from the database id was: {account_id}",
                    exc_info=True,
                )
                raise
        else:
            logger.error("Nothing to change")
            raise
        return users_saves_helper(updated_user)

    async def update_user_type(self, account_id, user: UpdateUserType) -> dict:
        """update a user's type (free / premium) into the user collection"""
        if user.user_type is not None:
            logger.debug(f"update_type({account_id}) called")
            try:
                await self.user_collection.update_one(
                    {"account_id": account_id}, {"$set": {"user_type": user.user_type}}
                )
            except (ConnectionFailure, OperationFailure) as e:
                logger.error(
                    f"Exception occured updating user type id was: {account_id}",
                    exc_info=True,
                )
                raise
            try:
                updated_user = await self.user_collection.find_one(
                    {"account_id": account_id}
                )
            except (ConnectionFailure, OperationFailure) as e:
                logger.error(
                    f"Exception occured retrieving updated user from the database id was: {account_id}",
                    exc_info=True,
                )
                raise
        else:
            logger.error("Nothing to change")
            raise
        return users_saves_helper(updated_user)

    async def delete_user_details(self, id: str) -> dict:
        """delete a user's details from the user collection by document id"""
        logger.debug(f"delete_user_details({id}) called")
        try:
            delete_response = await self.user_collection.delete_one(
                {"_id": ObjectId(id)}
            )
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured delete user details from the database _id was: {id}",
                exc_info=True,
            )
            raise

        return delete_response.deleted_count

    async def delete_user_details_by_account_id(self, account_id: str) -> dict:
        """delete a user's details from the user collection"""
        logger.debug(f"delete_user_details({account_id}) called")
        try:
            delete_response = await self.user_collection.delete_many(
                {"account_id": account_id}
            )
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured delete user details from the database account_id was: {account_id}",
                exc_info=True,
            )
            raise
        # now remove any documents belonging to the users
        logger.debug(f"Removing documents for {account_id}")
        try:
            await self.tree_collection.delete_many({"account_id": account_id})
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured removing all documents for user account_id was: {account_id}",
                exc_info=True,
            )
            raise
        return delete_response.deleted_count

    async def check_if_user_exists(self, user_id: str) -> int:
        """return count of save documents in the user_collection for supplied user_id"""
        logger.debug(f"check_if_user_exists({user_id}) called")
        try:
            user_count = await self.user_collection.count_documents(
                {"_id": ObjectId(user_id)}
            )
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving user document count user_id was: {user_id}",
                exc_info=True,
            )
            raise
        return user_count


# ================================================================
#  Normalised adjacency-list model — shared helpers
# ================================================================

_UUID4_RE = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

# Maps parent node_type → the only valid child node_type.
# None key = root level (only "part" may have no parent).
_VALID_CHILD: dict[str | None, str | None] = {
    None: "part",
    "part": "chapter",
    "chapter": "scene",
    "scene": "beat",
    "beat": None,
}


def is_valid_parent_child(parent_type: str | None, child_type: str) -> bool:
    """Return True if child_type is the valid child of parent_type per hierarchy rules."""
    return _VALID_CHILD.get(parent_type) == child_type


def _strip_id(doc: dict) -> dict:
    """Remove the MongoDB _id field from a document dict in-place and return it."""
    doc.pop("_id", None)
    return doc


# ----------------------------------------------------------------
# MongoDB collection validators and indexes  (T-09)
# ----------------------------------------------------------------

_WORK_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["work_id", "account_id", "title", "tags"],
        "properties": {
            "work_id":    {"bsonType": "string", "pattern": _UUID4_RE},
            "account_id": {"bsonType": "string", "minLength": 1},
            "title":      {"bsonType": "string", "minLength": 1},
            "tags":       {"bsonType": "array", "items": {"bsonType": "string"}},
        },
    }
}

_NODE_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["node_id", "work_id", "account_id", "tag", "node_type", "position", "tags"],
        "properties": {
            "node_type":  {"bsonType": "string", "enum": ["part", "chapter", "scene", "beat"]},
            "node_id":    {"bsonType": "string", "pattern": _UUID4_RE},
            "work_id":    {"bsonType": "string", "pattern": _UUID4_RE},
            "account_id": {"bsonType": "string", "minLength": 1},
            "tag":        {"bsonType": "string", "minLength": 1},
            "position":   {"bsonType": ["int", "long"], "minimum": 0},
            "tags":       {"bsonType": "array", "items": {"bsonType": "string"}},
        },
    }
}


async def setup_collections(db) -> None:
    """Create work_collection and node_collection with validators and indexes.

    Idempotent: creates collections that don't exist, updates validators on
    those that do. Indexes use create_index which is a no-op if already present.
    """
    logger.debug("setup_collections() called")
    existing = await db.list_collection_names()

    for name, validator in [
        ("work_collection", _WORK_VALIDATOR),
        ("node_collection", _NODE_VALIDATOR),
    ]:
        if name not in existing:
            try:
                await db.create_collection(name, validator=validator)
                logger.debug(f"Created collection: {name}")
            except OperationFailure as e:
                if e.code in (8000, 13):
                    try:
                        await db.create_collection(name)
                        logger.warning(
                            f"Created {name} without validator: Atlas user lacks dbAdmin "
                            f"(collMod requires dbAdmin). Pydantic enforces schema at the API layer."
                        )
                    except OperationFailure:
                        logger.error(f"Failed to create collection {name}", exc_info=True)
                        raise
                else:
                    logger.error(f"Failed to create collection {name}", exc_info=True)
                    raise
        else:
            try:
                await db.command("collMod", name, validator=validator)
                logger.debug(f"Updated validator for existing collection: {name}")
            except OperationFailure as e:
                if e.code in (8000, 13):
                    logger.warning(
                        f"Skipping validator update for {name}: Atlas user lacks dbAdmin "
                        f"(collMod requires dbAdmin). Pydantic enforces schema at the API layer."
                    )
                else:
                    logger.error(f"Failed to update validator for {name}", exc_info=True)
                    raise

    work_col = db.get_collection("work_collection")
    await work_col.create_index([("work_id", 1)], unique=True)
    await work_col.create_index([("account_id", 1)])

    node_col = db.get_collection("node_collection")
    await node_col.create_index([("node_id", 1)], unique=True)
    await node_col.create_index([("account_id", 1), ("work_id", 1)])
    await node_col.create_index([("account_id", 1), ("parent_id", 1)])
    await node_col.create_index([("account_id", 1), ("node_type", 1)])
    await node_col.create_index([("account_id", 1), ("node_id", 1)])

    # Tier 3 — Search indexes
    await node_col.create_index(
        [("description", "text"), ("text", "text")],
        name="node_text_idx",
    )
    await node_col.create_index(
        [("account_id", 1), ("tags", 1)],
        name="node_tags_idx",
    )

    logger.debug("setup_collections() complete")


# ================================================================
#  WorkStorage  (T-05)
# ================================================================

class WorkStorage:
    def __init__(self, client: motor.motor_asyncio.AsyncIOMotorClient):
        self.client = client
        self.database = self.client.fabulator
        self.work_collection = self.database.get_collection("work_collection")
        self.node_collection = self.database.get_collection("node_collection")

    async def create_work(self, account_id: str, data: dict, session=None) -> dict:
        """Insert a new Work document and return it."""
        logger.debug(f"create_work({account_id}) called")
        now = datetime.now(timezone.utc)
        doc = {
            "work_id":     str(uuid.uuid4()),
            "account_id":  account_id,
            "title":       data["title"],
            "description": data.get("description"),
            "author":      data.get("author"),
            "tags":        data.get("tags") or [],
            "created_at":  now,
            "updated_at":  now,
        }
        try:
            await self.work_collection.insert_one(doc, session=session)
        except (DuplicateKeyError, ConnectionFailure, OperationFailure):
            logger.error("Exception occurred inserting work document", exc_info=True)
            raise
        return _strip_id(doc)

    async def get_work(self, work_id: str, account_id: str) -> dict | None:
        """Return a Work document or None if not found / wrong account."""
        logger.debug(f"get_work({work_id}) called")
        try:
            doc = await self.work_collection.find_one(
                {"work_id": work_id, "account_id": account_id}
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred retrieving work {work_id}", exc_info=True)
            raise
        return _strip_id(doc) if doc else None

    async def list_works(
        self, account_id: str, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict], str | None]:
        """Return Works for account with cursor pagination, newest first.

        Returns (stripped_docs, next_cursor). next_cursor is None when no more pages.
        """
        logger.debug(f"list_works({account_id}) called")
        query: dict = {"account_id": account_id}
        if cursor is not None:
            try:
                query["_id"] = {"$lt": ObjectId(cursor)}
            except InvalidId:
                pass
        works: list[dict] = []
        next_cursor: str | None = None
        try:
            async for doc in self.work_collection.find(
                query, sort=[("_id", -1)]
            ).limit(limit + 1):
                works.append(doc)
        except (ConnectionFailure, OperationFailure):
            logger.error("Exception occurred listing works for account", exc_info=True)
            raise
        if len(works) > limit:
            works.pop()
            next_cursor = str(works[-1]["_id"])
        for doc in works:
            doc.pop("_id", None)
        return works, next_cursor

    async def update_work(
        self, work_id: str, account_id: str, updates: dict, session=None
    ) -> dict | None:
        """Apply field updates to a Work; cascade author to all child nodes if changed.
        Returns the updated document or None if not found."""
        logger.debug(f"update_work({work_id}) called")
        updates["updated_at"] = datetime.now(timezone.utc)
        try:
            result = await self.work_collection.find_one_and_update(
                {"work_id": work_id, "account_id": account_id},
                {"$set": updates},
                return_document=ReturnDocument.AFTER,
                session=session,
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred updating work {work_id}", exc_info=True)
            raise
        if result is None:
            return None
        if "author" in updates:
            await self.cascade_author_to_nodes(
                work_id=work_id,
                account_id=account_id,
                author=updates["author"],
                session=session,
            )
        return _strip_id(result)

    async def cascade_author_to_nodes(
        self, work_id: str, account_id: str, author: str | None, session=None
    ) -> int:
        """Bulk-update author on every node belonging to this Work. Returns count updated."""
        logger.debug(f"cascade_author_to_nodes({work_id}) called")
        try:
            result = await self.node_collection.update_many(
                {"work_id": work_id, "account_id": account_id},
                {"$set": {"author": author}},
                session=session,
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(
                f"Exception occurred cascading author for work {work_id}", exc_info=True
            )
            raise
        return result.modified_count

    async def delete_work(
        self, work_id: str, account_id: str, session=None
    ) -> tuple[bool, int]:
        """Delete a Work and all its nodes. Returns (found, nodes_deleted)."""
        logger.debug(f"delete_work({work_id}) called")
        try:
            work_result = await self.work_collection.delete_one(
                {"work_id": work_id, "account_id": account_id},
                session=session,
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred deleting work {work_id}", exc_info=True)
            raise
        if work_result.deleted_count == 0:
            return False, 0
        try:
            node_result = await self.node_collection.delete_many(
                {"work_id": work_id, "account_id": account_id},
                session=session,
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(
                f"Exception occurred deleting nodes for work {work_id}", exc_info=True
            )
            raise
        return True, node_result.deleted_count


# ================================================================
#  NodeStorage  (T-06, T-07, T-08)
# ================================================================

class NodeStorage:
    def __init__(self, client: motor.motor_asyncio.AsyncIOMotorClient):
        self.client = client
        self.database = self.client.fabulator
        self.node_collection = self.database.get_collection("node_collection")
        self.work_collection = self.database.get_collection("work_collection")

    # ----------------------------------------------------------
    # Core CRUD  (T-06)
    # ----------------------------------------------------------

    async def create_node(self, account_id: str, work_doc: dict, data: dict, session=None) -> dict:
        """Insert a new node; copies author from Work; auto-assigns position.
        Returns the inserted document."""
        logger.debug(f"create_node({account_id}) called")
        parent_id = data.get("parent_id")

        # Position = max(sibling positions) + 1, or 0 if no siblings exist.
        sibling_filter = (
            {"account_id": account_id, "parent_id": parent_id}
            if parent_id
            else {"account_id": account_id, "work_id": data["work_id"], "parent_id": None}
        )
        try:
            latest = await self.node_collection.find_one(
                sibling_filter, sort=[("position", -1)], session=session
            )
        except (ConnectionFailure, OperationFailure):
            logger.error("Exception occurred querying sibling positions", exc_info=True)
            raise
        position = (latest["position"] + 1) if latest else 0

        now = datetime.now(timezone.utc)
        doc = {
            "node_id":     data.get("node_id") or str(uuid.uuid4()),
            "work_id":     data["work_id"],
            "account_id":  account_id,
            "author":      work_doc.get("author"),
            "node_type":   data["node_type"],
            "parent_id":   parent_id,
            "position":    position,
            "tag":         data["tag"],
            "description": data.get("description"),
            "text":        data.get("text"),
            "previous":    data.get("previous"),
            "next":        data.get("next"),
            "tags":        data.get("tags") or [],
            "created_at":  now,
            "updated_at":  now,
        }
        try:
            await self.node_collection.insert_one(doc, session=session)
        except (DuplicateKeyError, ConnectionFailure, OperationFailure):
            logger.error("Exception occurred inserting node document", exc_info=True)
            raise
        return _strip_id(doc)

    async def get_node(self, node_id: str, account_id: str) -> dict | None:
        """Return a node document or None if not found / wrong account."""
        logger.debug(f"get_node({node_id}) called")
        try:
            doc = await self.node_collection.find_one(
                {"node_id": node_id, "account_id": account_id}
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred retrieving node {node_id}", exc_info=True)
            raise
        return _strip_id(doc) if doc else None

    async def list_nodes(
        self, work_id: str, account_id: str, node_type: str | None = None,
        limit: int = 50, cursor: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """Return nodes for a Work with cursor pagination, optionally filtered by node_type.

        Returns (stripped_docs, next_cursor). next_cursor is None when no more pages.
        """
        logger.debug(f"list_nodes({work_id}) called")
        query: dict = {"work_id": work_id, "account_id": account_id}
        if node_type is not None:
            query["node_type"] = node_type
        if cursor is not None:
            try:
                query["_id"] = {"$gt": ObjectId(cursor)}
            except InvalidId:
                pass
        nodes: list[dict] = []
        next_cursor: str | None = None
        try:
            async for doc in self.node_collection.find(
                query, sort=[("_id", 1)]
            ).limit(limit + 1):
                nodes.append(doc)
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred listing nodes for work {work_id}", exc_info=True)
            raise
        if len(nodes) > limit:
            nodes.pop()
            next_cursor = str(nodes[-1]["_id"])
        for doc in nodes:
            doc.pop("_id", None)
        return nodes, next_cursor

    async def update_node(
        self, node_id: str, account_id: str, updates: dict
    ) -> dict | None:
        """Apply updates to a node. Auto-assigns end position when parent_id changes.
        Returns updated document or None if not found."""
        logger.debug(f"update_node({node_id}) called")
        updates["updated_at"] = datetime.now(timezone.utc)

        if "parent_id" in updates:
            new_parent_id = updates["parent_id"]
            sibling_filter = (
                {"account_id": account_id, "parent_id": new_parent_id,
                 "node_id": {"$ne": node_id}}
                if new_parent_id
                else {"account_id": account_id, "parent_id": None,
                      "node_id": {"$ne": node_id}}
            )
            try:
                latest = await self.node_collection.find_one(
                    sibling_filter, sort=[("position", -1)]
                )
            except (ConnectionFailure, OperationFailure):
                logger.error("Exception occurred querying sibling positions for reparent", exc_info=True)
                raise
            updates["position"] = (latest["position"] + 1) if latest else 0

        try:
            result = await self.node_collection.find_one_and_update(
                {"node_id": node_id, "account_id": account_id},
                {"$set": updates},
                return_document=ReturnDocument.AFTER,
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred updating node {node_id}", exc_info=True)
            raise
        return _strip_id(result) if result else None

    async def delete_node_cascade(
        self, node_id: str, account_id: str
    ) -> tuple[bool, int]:
        """Delete a node and all its descendants via BFS.
        Returns (found, descendants_deleted). Descendants count excludes the node itself."""
        logger.debug(f"delete_node_cascade({node_id}) called")
        node = await self.get_node(node_id, account_id)
        if node is None:
            return False, 0

        # BFS to collect all descendant IDs (node_id is the frontier seed).
        all_ids = [node_id]
        frontier = [node_id]
        while frontier:
            try:
                children = await self.node_collection.find(
                    {"account_id": account_id, "parent_id": {"$in": frontier}},
                    {"node_id": 1},
                ).to_list(None)
            except (ConnectionFailure, OperationFailure):
                logger.error("Exception occurred collecting descendants for deletion", exc_info=True)
                raise
            frontier = [c["node_id"] for c in children]
            all_ids.extend(frontier)

        try:
            result = await self.node_collection.delete_many(
                {"account_id": account_id, "node_id": {"$in": all_ids}}
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred in cascade delete for {node_id}", exc_info=True)
            raise
        return True, result.deleted_count - 1

    # ----------------------------------------------------------
    # Navigation  (T-07)
    # ----------------------------------------------------------

    async def get_children(self, node_id: str, account_id: str) -> list[dict]:
        """Return direct children ordered by position ascending."""
        logger.debug(f"get_children({node_id}) called")
        children: list[dict] = []
        try:
            async for doc in self.node_collection.find(
                {"parent_id": node_id, "account_id": account_id},
                sort=[("position", 1)],
            ):
                children.append(_strip_id(doc))
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred getting children of {node_id}", exc_info=True)
            raise
        return children

    async def get_parent(self, node_id: str, account_id: str) -> dict | None:
        """Return the parent node, or None for Part (root) nodes."""
        logger.debug(f"get_parent({node_id}) called")
        node = await self.get_node(node_id, account_id)
        if node is None or node.get("parent_id") is None:
            return None
        try:
            doc = await self.node_collection.find_one(
                {"node_id": node["parent_id"], "account_id": account_id}
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred getting parent of {node_id}", exc_info=True)
            raise
        return _strip_id(doc) if doc else None

    async def get_ancestors(self, node_id: str, account_id: str) -> list[dict]:
        """Return ancestors ordered from root to immediate parent (inclusive).
        Returns empty list for Part (root) nodes."""
        logger.debug(f"get_ancestors({node_id}) called")
        node = await self.get_node(node_id, account_id)
        if node is None or node.get("parent_id") is None:
            return []
        ancestors: list[dict] = []
        current_id: str | None = node["parent_id"]
        visited: set[str] = set()
        while current_id is not None:
            if current_id in visited:
                break
            visited.add(current_id)
            try:
                doc = await self.node_collection.find_one(
                    {"node_id": current_id, "account_id": account_id}
                )
            except (ConnectionFailure, OperationFailure):
                logger.error(
                    f"Exception occurred traversing ancestors of {node_id}", exc_info=True
                )
                raise
            if doc is None:
                break
            ancestors.append(_strip_id(doc))
            current_id = doc.get("parent_id")
        ancestors.reverse()
        return ancestors

    async def get_siblings(self, node_id: str, account_id: str) -> list[dict]:
        """Return sibling nodes (same parent_id), excluding self, ordered by position."""
        logger.debug(f"get_siblings({node_id}) called")
        node = await self.get_node(node_id, account_id)
        if node is None:
            return []
        siblings: list[dict] = []
        try:
            async for doc in self.node_collection.find(
                {
                    "parent_id":  node["parent_id"],
                    "account_id": account_id,
                    "node_id":    {"$ne": node_id},
                },
                sort=[("position", 1)],
            ):
                siblings.append(_strip_id(doc))
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred getting siblings of {node_id}", exc_info=True)
            raise
        return siblings

    async def get_roots(
        self, work_id: str, account_id: str,
        limit: int = 50, cursor: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """Return Part (root) nodes for a Work with cursor pagination, ordered by position.

        Returns (stripped_docs, next_cursor). next_cursor is None when no more pages.
        """
        logger.debug(f"get_roots({work_id}) called")
        query: dict = {"work_id": work_id, "account_id": account_id, "parent_id": None}
        if cursor is not None:
            try:
                query["_id"] = {"$gt": ObjectId(cursor)}
            except InvalidId:
                pass
        roots: list[dict] = []
        next_cursor: str | None = None
        try:
            async for doc in self.node_collection.find(
                query, sort=[("position", 1), ("_id", 1)]
            ).limit(limit + 1):
                roots.append(doc)
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred getting roots for work {work_id}", exc_info=True)
            raise
        if len(roots) > limit:
            roots.pop()
            next_cursor = str(roots[-1]["_id"])
        for doc in roots:
            doc.pop("_id", None)
        return roots, next_cursor

    async def get_leaves(
        self, work_id: str, account_id: str,
        limit: int = 50, cursor: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """Return Beat (leaf) nodes for a Work with cursor pagination, ordered by position.

        Returns (stripped_docs, next_cursor). next_cursor is None when no more pages.
        """
        logger.debug(f"get_leaves({work_id}) called")
        query: dict = {"work_id": work_id, "account_id": account_id, "node_type": "beat"}
        if cursor is not None:
            try:
                query["_id"] = {"$gt": ObjectId(cursor)}
            except InvalidId:
                pass
        leaves: list[dict] = []
        next_cursor: str | None = None
        try:
            async for doc in self.node_collection.find(
                query, sort=[("position", 1), ("_id", 1)]
            ).limit(limit + 1):
                leaves.append(doc)
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred getting leaves for work {work_id}", exc_info=True)
            raise
        if len(leaves) > limit:
            leaves.pop()
            next_cursor = str(leaves[-1]["_id"])
        for doc in leaves:
            doc.pop("_id", None)
        return leaves, next_cursor

    # ----------------------------------------------------------
    # Reading order  (E-89)
    # ----------------------------------------------------------

    async def get_reading_order(self, work_id: str, account_id: str) -> list[dict]:
        """Return all nodes of a Work in depth-first pre-order, siblings by position.

        Single {account_id, work_id} fetch; uses existing compound index.
        Builds an in-memory parent→children map and performs a DFS pre-order walk.
        A visited set guards against cycles defensively (the parent_id chain is
        guaranteed acyclic by spec). Returns list of node dicts with _id stripped.
        """
        logger.debug(f"get_reading_order({work_id}) called")
        try:
            cursor = self.node_collection.find(
                {"account_id": account_id, "work_id": work_id}
            )
            all_nodes: list[dict] = await cursor.to_list(length=None)
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception in get_reading_order({work_id})", exc_info=True)
            raise

        if not all_nodes:
            return []

        node_map: dict[str, dict] = {}
        parent_to_children: dict[str | None, list[str]] = {}
        for doc in all_nodes:
            nid = doc["node_id"]
            node_map[nid] = doc
            pid: str | None = doc.get("parent_id")
            parent_to_children.setdefault(pid, []).append(nid)

        for pid in parent_to_children:
            parent_to_children[pid].sort(key=lambda nid: node_map[nid]["position"])

        ordered: list[dict] = []
        visited: set[str] = set()
        stack: list[str] = list(parent_to_children.get(None, []))

        while stack:
            node_id = stack.pop()
            if node_id in visited:
                logger.error(f"Cycle detected: node {node_id} already visited")
                continue
            visited.add(node_id)
            ordered.append(node_map[node_id])
            children = parent_to_children.get(node_id, [])
            for child in reversed(children):
                stack.append(child)

        for doc in ordered:
            doc.pop("_id", None)

        return ordered

    # ----------------------------------------------------------
    # Stats and operation helpers  (T-08)
    # ----------------------------------------------------------

    async def get_stats(self, work_id: str, account_id: str) -> dict:
        """Return WorkStatsResponse-shaped dict with node counts by type and max depth."""
        logger.debug(f"get_stats({work_id}) called")
        by_type: dict[str, int] = {"part": 0, "chapter": 0, "scene": 0, "beat": 0}
        pipeline = [
            {"$match": {"work_id": work_id, "account_id": account_id}},
            {"$group": {"_id": "$node_type", "count": {"$sum": 1}}},
        ]
        try:
            async for doc in self.node_collection.aggregate(pipeline):
                if doc["_id"] in by_type:
                    by_type[doc["_id"]] = doc["count"]
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred aggregating stats for work {work_id}", exc_info=True)
            raise
        max_depth = await self._calculate_max_depth(work_id, account_id)
        return {
            "work_id":     work_id,
            "total_nodes": sum(by_type.values()),
            "by_type":     by_type,
            "max_depth":   max_depth,
        }

    async def _calculate_max_depth(self, work_id: str, account_id: str) -> int:
        """BFS from all root nodes to compute maximum depth (0-indexed at roots)."""
        roots, _ = await self.get_roots(work_id, account_id)
        if not roots:
            return 0
        max_depth = 0
        queue: list[tuple[str, int]] = [(r["node_id"], 0) for r in roots]
        while queue:
            current_id, depth = queue.pop(0)
            max_depth = max(max_depth, depth)
            try:
                children = await self.node_collection.find(
                    {"account_id": account_id, "parent_id": current_id},
                    {"node_id": 1},
                ).to_list(None)
            except (ConnectionFailure, OperationFailure):
                logger.error("Exception occurred during max-depth BFS traversal", exc_info=True)
                raise
            for child in children:
                queue.append((child["node_id"], depth + 1))
        return max_depth

    async def would_create_cycle(
        self, node_id: str, new_parent_id: str, account_id: str
    ) -> bool:
        """Return True if setting new_parent_id as the parent of node_id would create a cycle.
        Walks up the tree from new_parent_id; True if node_id is encountered."""
        current_id: str | None = new_parent_id
        visited: set[str] = set()
        while current_id is not None:
            if current_id == node_id:
                return True
            if current_id in visited:
                return True
            visited.add(current_id)
            try:
                doc = await self.node_collection.find_one(
                    {"node_id": current_id, "account_id": account_id},
                    {"parent_id": 1},
                )
            except (ConnectionFailure, OperationFailure):
                logger.error("Exception occurred during cycle detection", exc_info=True)
                raise
            if doc is None:
                break
            current_id = doc.get("parent_id")
        return False

    async def reorder_siblings(
        self, node_id: str, account_id: str, new_position: int
    ) -> dict | None:
        """Move node to new_position among its siblings (clamped to valid range).
        Renumbers all siblings to maintain a contiguous zero-based sequence.
        Returns the updated node or None if not found."""
        logger.debug(f"reorder_siblings({node_id}, {new_position}) called")
        node = await self.get_node(node_id, account_id)
        if node is None:
            return None
        try:
            siblings = await self.node_collection.find(
                {
                    "account_id": account_id,
                    "parent_id":  node["parent_id"],
                    "work_id":    node["work_id"],
                },
                sort=[("position", 1)],
            ).to_list(None)
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred fetching siblings for reorder of {node_id}", exc_info=True)
            raise

        clamped = min(new_position, max(0, len(siblings) - 1))
        ordered = [s for s in siblings if s["node_id"] != node_id]
        ordered.insert(clamped, node)

        for i, sibling in enumerate(ordered):
            try:
                await self.node_collection.update_one(
                    {"node_id": sibling["node_id"]},
                    {"$set": {"position": i}},
                )
            except (ConnectionFailure, OperationFailure):
                logger.error(
                    f"Exception occurred renumbering sibling {sibling['node_id']}", exc_info=True
                )
                raise
        return await self.get_node(node_id, account_id)

    async def duplicate_shallow(self, node_id: str, account_id: str) -> dict | None:
        """Shallow-copy a node (no children). New tag gets ' (copy)' suffix.
        Placed immediately after original; subsequent siblings shift up by one.
        Returns the new document or None if source not found."""
        logger.debug(f"duplicate_shallow({node_id}) called")
        node = await self.get_node(node_id, account_id)
        if node is None:
            return None

        # Beat nodes are leaves and must not be duplicated
        if node["node_type"] == "beat":
            logger.debug(
                f"duplicate_shallow rejects Beat type node {node_id}"
            )
            return None

        try:
            await self.node_collection.update_many(
                {
                    "account_id": account_id,
                    "parent_id":  node["parent_id"],
                    "work_id":    node["work_id"],
                    "position":   {"$gt": node["position"]},
                },
                {"$inc": {"position": 1}},
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred shifting siblings for duplicate of {node_id}", exc_info=True)
            raise

        now = datetime.now(timezone.utc)
        new_doc = {
            "node_id":     str(uuid.uuid4()),
            "work_id":     node["work_id"],
            "account_id":  node["account_id"],
            "author":      node.get("author"),
            "node_type":   node["node_type"],
            "parent_id":   node["parent_id"],
            "position":    node["position"] + 1,
            "tag":         f"{node['tag']} (copy)",
            "description": node.get("description"),
            "text":        node.get("text"),
            "previous":    node.get("previous"),
            "next":        node.get("next"),
            "tags":        list(node.get("tags") or []),
            "created_at":  now,
            "updated_at":  now,
        }
        try:
            await self.node_collection.insert_one(new_doc)
        except (DuplicateKeyError, ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred inserting shallow duplicate of {node_id}", exc_info=True)
            raise
        return _strip_id(new_doc)

    async def duplicate_deep(
        self,
        node_id: str,
        account_id: str,
        _new_parent_id: str | None = None,
        _position: int = 0,
        _is_root_call: bool = True,
    ) -> dict | None:
        """Recursively copy a node and all descendants with fresh node_ids.
        Root copy tag gets ' (copy)' suffix and is placed after the original.
        Child copies preserve their original tags.
        Returns the root new node or None if source not found."""
        logger.debug(f"duplicate_deep({node_id}) called")
        node = await self.get_node(node_id, account_id)
        if node is None:
            return None

        # Beat nodes are leaves and must not be duplicated
        if node["node_type"] == "beat":
            logger.debug(
                f"duplicate_deep rejects Beat type node {node_id}"
             )
            return None

        if _is_root_call:
            try:
                await self.node_collection.update_many(
                    {
                        "account_id": account_id,
                        "parent_id":  node["parent_id"],
                        "work_id":    node["work_id"],
                        "position":   {"$gt": node["position"]},
                    },
                    {"$inc": {"position": 1}},
                )
            except (ConnectionFailure, OperationFailure):
                logger.error("Exception occurred shifting siblings for deep duplicate", exc_info=True)
                raise
            new_parent_id = node["parent_id"]
            new_position = node["position"] + 1
            new_tag = f"{node['tag']} (copy)"
        else:
            new_parent_id = _new_parent_id
            new_position = _position
            new_tag = node["tag"]

        now = datetime.now(timezone.utc)
        new_node_id = str(uuid.uuid4())
        new_doc = {
            "node_id":     new_node_id,
            "work_id":     node["work_id"],
            "account_id":  node["account_id"],
            "author":      node.get("author"),
            "node_type":   node["node_type"],
            "parent_id":   new_parent_id,
            "position":    new_position,
            "tag":         new_tag,
            "description": node.get("description"),
            "text":        node.get("text"),
            "previous":    node.get("previous"),
            "next":        node.get("next"),
            "tags":        list(node.get("tags") or []),
            "created_at":  now,
            "updated_at":  now,
        }
        try:
            await self.node_collection.insert_one(new_doc)
        except (DuplicateKeyError, ConnectionFailure, OperationFailure):
            logger.error("Exception occurred inserting deep duplicate node", exc_info=True)
            raise

        try:
            children = await self.node_collection.find(
                {"account_id": account_id, "parent_id": node_id},
                sort=[("position", 1)],
            ).to_list(None)
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred fetching children for deep duplicate of {node_id}", exc_info=True)
            raise

        for i, child in enumerate(children):
            await self.duplicate_deep(
                node_id=child["node_id"],
                account_id=account_id,
                _new_parent_id=new_node_id,
                _position=i,
                _is_root_call=False,
            )

        return _strip_id(new_doc)


# ================================================================
#  SearchStorage  (Tier 3 — search-query/feature.md)
# ================================================================

class SearchStorage:
    def __init__(self, client: motor.motor_asyncio.AsyncIOMotorClient):
        self.client = client
        self.database = self.client.fabulator
        self.node_collection = self.database.get_collection("node_collection")

    async def search_nodes(
        self,
        account_id: str,
        query: str,
        work_id: str | None = None,
        node_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Full-text search over description and text fields.

        Returns a list of node dicts (with _id stripped) ordered by descending textScore.
        """
        logger.debug(f"search_nodes(account_id={account_id}, query={query!r}) called")
        filter_doc: dict = {"account_id": account_id, "$text": {"$search": query}}
        if work_id is not None:
            filter_doc["work_id"] = work_id
        if node_type is not None:
            filter_doc["node_type"] = node_type

        results: list[dict] = []
        try:
            async for doc in self.node_collection.find(
                filter_doc,
                {"score": {"$meta": "textScore"}},
            ).sort([("score", {"$meta": "textScore"})]).limit(limit):
                _strip_id(doc)
                results.append(doc)
        except (ConnectionFailure, OperationFailure):
            logger.error(
                f"Exception occurred during text search for query {query!r}",
                exc_info=True,
            )
            raise
        return results

    async def find_nodes_by_tags(
        self,
        account_id: str,
        tags: list[str],
        match: str = "any",
        work_id: str | None = None,
        node_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query nodes by tag(s).

        *match* == 'any' → $in; *match* == 'all' → $all.
        Returns a list of node dicts (with _id stripped) ordered by created_at descending.
        """
        logger.debug(f"find_nodes_by_tags(account_id={account_id}, tags={tags!r}) called")
        filter_doc: dict = {"account_id": account_id}
        if match == "any":
            filter_doc["tags"] = {"$in": tags}
        else:
            filter_doc["tags"] = {"$all": tags}
        if work_id is not None:
            filter_doc["work_id"] = work_id
        if node_type is not None:
            filter_doc["node_type"] = node_type

        results: list[dict] = []
        try:
            async for doc in self.node_collection.find(filter_doc).sort(
                [("created_at", -1)]
            ).limit(limit):
                _strip_id(doc)
                results.append(doc)
        except (ConnectionFailure, OperationFailure):
            logger.error(
                f"Exception occurred during tag query for tags {tags!r}",
                exc_info=True,
            )
            raise
        return results


# ================================================================
#  DemoStorage  (Phase 17)
# ================================================================

class DemoStorage:
    def __init__(
        self,
        client: motor.motor_asyncio.AsyncIOMotorClient,
        work_storage: WorkStorage | None = None,
        node_storage: NodeStorage | None = None,
    ):
        self.client = client
        self._work_storage = work_storage or WorkStorage(client)
        self._node_storage = node_storage or NodeStorage(client)

    @property
    def work_storage(self) -> WorkStorage:
        return self._work_storage

    @property
    def node_storage(self) -> NodeStorage:
        return self._node_storage

    async def delete_demo_works(self, account_id: str, session=None) -> int:
        """Delete all demo-tagged Works and their nodes for the given account.
        
        Returns count of works deleted.
        """
        logger.debug(f"delete_demo_works({account_id}) called")
        try:
            # Find all demo works via list_works + Python tag filter
            demo_works: list[dict] = []
            cursor: str | None = None
            while True:
                works, next_cursor = await self._work_storage.list_works(
                    account_id, limit=200, cursor=cursor
                )
                for w in works:
                    if "demo" in w.get("tags", []):
                        demo_works.append(w)
                if next_cursor is None:
                    break
                cursor = next_cursor

            if not demo_works:
                return 0

            deleted = 0
            for w in demo_works:
                found, _ = await self._work_storage.delete_work(
                    w["work_id"], account_id, session=session
                )
                if found:
                    deleted += 1

            return deleted

        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred deleting demo works for account {account_id}", exc_info=True)
            raise

    async def seed_demo(
        self, 
        account_id: str, 
        author: str, 
        reset: bool = False,
        session=None
    ) -> dict:
        """Seed a demo Work and tree into the database within a transaction.
        
        Uses a multi-document transaction for atomicity. If transactions are
        unavailable, falls back to compensating cleanup (create Work last,
        delete-by-work_id on failure).
        
        Args:
            account_id: The user's account ID
            author: Author attribution for the demo work
            reset: If True, delete existing demo works before seeding
            session: Optional MongoDB session for transaction
            
        Returns:
            dict with demo work details including work_id, title, total_nodes, and by_type
            
        Raises:
            Exception: Propagated from underlying storage operations
        """
        logger.debug(f"seed_demo({account_id}, reset={reset}) called")
        
        # Generate the demo content using build_demo_tree function
        from app.demo import build_demo_tree
        work_data, node_list = build_demo_tree(account_id, author)
        
        try:
            return await self._seed_with_transaction(
                account_id, author, reset, work_data, node_list
            )
        except (InvalidOperation, OperationFailure) as e:
            # InvalidOperation covers standalone servers ("Transactions are not supported
            # on standalone servers").  OperationFailure code 20 (IllegalOperation) covers
            # the same condition reported by the server on some configurations.
            unsupported = isinstance(e, InvalidOperation) or (
                isinstance(e, OperationFailure) and e.code == 20
            )
            if unsupported:
                logger.warning("Transactions not supported, using compensating cleanup fallback")
                return await self._seed_with_compensating_cleanup(
                    account_id, author, reset, work_data, node_list
                )
            raise

    async def _seed_with_transaction(
        self,
        account_id: str,
        author: str,
        reset: bool,
        work_data,
        node_list,
    ) -> dict:
        """Seed using a multi-document transaction for atomicity."""
        client = self.client
        async with await client.start_session() as session:
            async with session.start_transaction():
                if reset:
                    await self.delete_demo_works(account_id, session=session)

                work_dict = work_data.model_dump()
                work_dict["tags"] = list(work_dict.get("tags") or []) + ["demo"]
                work_doc = await self.work_storage.create_work(
                    account_id, work_dict, session=session
                )

                created_nodes = []
                for node_data in node_list:
                    # Overwrite placeholder work_id with the real one from create_work
                    node_doc = await self.node_storage.create_node(
                        account_id,
                        work_doc,
                        {**node_data.model_dump(), "account_id": account_id, "work_id": work_doc["work_id"]},
                        session=session,
                    )
                    created_nodes.append(node_doc)

                by_type = {"part": 0, "chapter": 0, "scene": 0, "beat": 0}
                for node in created_nodes:
                    by_type[node["node_type"]] += 1

                return {
                    "work_id": work_doc["work_id"],
                    "title": work_data.title,
                    "total_nodes": len(created_nodes),
                    "by_type": by_type,
                }

    async def _seed_with_compensating_cleanup(
        self,
        account_id: str,
        author: str,
        reset: bool,
        work_data,
        node_list,
    ) -> dict:
        """Compensating-cleanup fallback when transactions are unavailable.

        Creates Work first to obtain the real work_id, then creates nodes using
        it.  On any failure after Work creation, deletes Work + all created nodes
        by work_id so no partial data remains.
        """
        if reset:
            await self.delete_demo_works(account_id)

        work_dict = work_data.model_dump()
        work_dict["tags"] = list(work_dict.get("tags") or []) + ["demo"]
        work_doc = await self.work_storage.create_work(account_id, work_dict)

        try:
            created_nodes = []
            for node_data in node_list:
                node_doc = await self.node_storage.create_node(
                    account_id,
                    work_doc,
                    {**node_data.model_dump(), "account_id": account_id, "work_id": work_doc["work_id"]},
                )
                created_nodes.append(node_doc)

            by_type = {"part": 0, "chapter": 0, "scene": 0, "beat": 0}
            for node in created_nodes:
                by_type[node["node_type"]] += 1

            return {
                "work_id": work_doc["work_id"],
                "title": work_data.title,
                "total_nodes": len(created_nodes),
                "by_type": by_type,
            }
        except Exception:
            await self._work_storage.delete_work(work_doc["work_id"], account_id)
            raise

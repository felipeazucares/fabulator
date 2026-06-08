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
    OperationFailure,
    DuplicateKeyError,
)
from bson.errors import InvalidId
from treelib import Tree

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


# ----------------------------------------------------
#  Functions for saving and loading the tree structure
# ----------------------------------------------------


class TreeStorage:
    def __init__(
        self, collection_name: str, client: motor.motor_asyncio.AsyncIOMotorClient
    ):
        self.client = client
        self.database = self.client.fabulator
        self.tree_collection = self.database.get_collection(collection_name)

    async def save_working_tree(self, account_id: str, tree: Tree) -> dict:
        """Save the current working tree to a document in the tree_collection for supplied account_id"""
        logger.debug(f"save_working_tree({account_id}, tree) called")
        tree_to_save = TreeSaveSchema(account_id=account_id, tree=tree)
        try:
            save_response = await self.tree_collection.insert_one(
                jsonable_encoder(tree_to_save)
            )
        except (ConnectionFailure, OperationFailure) as e:
            logger.error("Exception occured writing to the database", exc_info=True)
            raise
        try:
            await self.tree_collection.find_one(
                {"_id": ObjectId(save_response.inserted_id)}
            )
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving details for save operation _id: {save_response.inserted_id}",
                exc_info=True,
            )
            raise
        return str(ObjectId(save_response.inserted_id))

    async def list_all_saved_trees(self, account_id: str) -> dict:
        """return a dict of all the saves in the tree_collection for supplied account_id"""
        logger.debug(f"list_all_saved_trees({account_id}) called")
        saves = []
        try:
            async for save in self.tree_collection.find({"account_id": account_id}):
                saves.append(saves_helper(save))
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured reading all database saves account_id {account_id}",
                exc_info=True,
            )
            raise
        return saves

    async def delete_all_saves(self, account_id: str) -> int:
        """delete all the saved documents in the tree_collection for supplied account_id"""
        logger.debug(f"delete_all_saves({account_id}) called")
        try:
            delete_result = await self.tree_collection.delete_many(
                {"account_id": account_id}
            )
            # delete_result object contains a deleted_count & acknowledged properties
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured deleting saves from the database account_id was: {account_id}",
                exc_info=True,
            )
            raise
        return delete_result.deleted_count

    async def number_of_saves_for_account(self, account_id: str) -> int:
        """return count of save documents in the tree_collection for supplied account_id"""
        logger.debug(f"number_of_saves_for_account({account_id}) called")
        try:
            save_count = await self.tree_collection.count_documents(
                {"account_id": account_id}
            )
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving document count account_id was: {account_id}",
                exc_info=True,
            )
            raise
        return save_count

    async def return_latest_save(self, account_id: str) -> dict:
        """return the latest save document from the tree_collection for supplied account_id"""
        logger.debug(f"return_latest_save({account_id}) called")
        try:
            last_save = await self.tree_collection.find_one(
                {"account_id": account_id}, sort=[("date_time", -1)]
            )
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving latest save from the database account_id was: {account_id}",
                exc_info=True,
            )
            raise
        return saves_helper(last_save)

    async def check_if_document_exists(
        self, save_id: str, account_id: str = None
    ) -> int:
        """return count of save documents in the tree_collection for supplied save_id.
        If account_id is provided, also verify the document belongs to that account."""
        logger.debug(
            f"check_if_document_exists({save_id}, account_id={account_id}) called"
        )
        try:
            # Build query - always include save_id, optionally include account_id for ownership check
            query = {"_id": ObjectId(save_id)}
            if account_id is not None:
                query["account_id"] = account_id
            save_count = await self.tree_collection.count_documents(query)
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving document count save_id was: {save_id}",
                exc_info=True,
            )
            raise
        return save_count

    async def return_save(self, save_id: str) -> dict:
        """return save document from the tree_collection for supplied save_id"""
        logger.debug(f"return_save({save_id}) called")
        try:
            save = await self.tree_collection.find_one({"_id": ObjectId(save_id)})
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving save from the database save_id was: {save_id}",
                exc_info=True,
            )
            raise
        return saves_helper(save)

    async def load_save_into_working_tree(self, save_id: str) -> Tree:
        """return a tree containing the latest saved tree"""
        logger.debug(f"load_save_into_working_tree({save_id}) called")
        try:
            save = await self.return_save(save_id=save_id)
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving save from the database save_id was: {save_id}",
                exc_info=True,
            )
            raise
        # get the tree dict from the saved document
        try:
            save_tree = save["tree"]
        except KeyError as e:
            logger.error(
                f"Exception occured retrieving tree structure from save", exc_info=True
            )
            raise

        return self.build_tree_from_dict(tree_dict=save_tree)

    async def load_latest_into_working_tree(self, account_id: str) -> Tree:
        """return a tree containing the latest saved tree"""
        logger.debug(f"load_latest_into_working_tree({account_id}) called")
        try:
            last_save = await self.return_latest_save(account_id=account_id)
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(
                f"Exception occured retrieving latest save from the database account_id was: {account_id}",
                exc_info=True,
            )
            raise
        # get the tree dict from the saved document
        try:
            last_save_tree = last_save["tree"]
        except KeyError as e:
            logger.error(
                "Exception occured retrieving tree structure from last save",
                exc_info=True,
            )
            raise

        return self.build_tree_from_dict(tree_dict=last_save_tree)

    def build_tree_from_dict(self, tree_dict: dict) -> Tree:
        """return a tree built from provided dict structure"""
        # Looks like there is no root in the subtree
        try:
            root_node = tree_dict["root"]
            if root_node is None:
                raise ValueError(
                    "Tree document has null root node — document may be corrupt"
                )
        except KeyError as e:
            logger.error(
                "Exception occured retrieving root object from dict", exc_info=True
            )
            raise
        # create the root node
        try:
            new_tree = Tree(identifier=tree_dict["_identifier"])
        except (KeyError, ValueError) as e:
            logger.error(
                f"Exception occured creating new tree with _identifier:{tree_dict['_identifier']}",
                exc_info=True,
            )
            raise

        return self.add_a_node(
            tree_id=tree_dict["_identifier"],
            loaded_tree=tree_dict,
            new_tree=new_tree,
            node_id=root_node,
            depth=0,
        )

    def add_a_node(
        self, tree_id, loaded_tree, new_tree, node_id, depth: int = 0
    ) -> Tree:
        """Traverse the dict in mongo and rebuild the tree a node at a time (recursive)"""
        if depth > MAX_TREE_DEPTH:
            logger.error(f"Tree depth {depth} exceeds MAX_TREE_DEPTH={MAX_TREE_DEPTH}")
            raise TreeDepthLimitExceeded(depth=depth, limit=MAX_TREE_DEPTH)

        logger.debug("add_a_node() called")

        # get name of node that's been passed to the routine
        try:
            name = loaded_tree["_nodes"][node_id]["_tag"]
            logger.debug(f"Current Node is: {name}")
        except KeyError as e:
            logger.error(
                f"Exception occurred unable to find _tag for node_id: {node_id}",
                exc_info=True,
            )
            raise
        # get the id of the current node
        try:
            node_identifier = loaded_tree["_nodes"][node_id]["_identifier"]
            logger.debug(f"Current id is: {node_identifier}")
        except KeyError as e:
            logger.error(
                f"Exception occurred unable to find _identifier for node_id: {node_id}",
                exc_info=True,
            )
            raise
        # set payload for new node to what's in the current node
        try:
            payload = loaded_tree["_nodes"][node_id]["data"]
        except KeyError as e:
            logger.error("Exception occurred unable to get node data", exc_info=True)
            raise

        # for some reason the children of a node are stored under the tree_id key
        try:
            children = loaded_tree["_nodes"][node_id]["_successors"][tree_id]
            logger.debug(f"{name}'s children: {children}")
        except KeyError:
            # sometimes the _successors field has no key - so if we can't find it set to None
            children = None
            logger.debug(f"{name}'s children: None")
        except (TypeError, IndexError) as e:
            logger.error(
                "Exception occurred retrieving the _successors field", exc_info=True
            )
            raise

        logger.debug(
            f"creating node with - name: {name}, identifier: {node_identifier}"
        )

        try:
            new_tree.create_node(
                tag=name,
                identifier=node_identifier,
                parent=loaded_tree["_nodes"][node_id]["_predecessor"][tree_id],
                data=payload,
            )
        except (KeyError, ValueError) as e:
            logger.error(
                f"Exception occurred adding a node to the working tree. name: {name}, identifier: {node_identifier}",
                exc_info=True,
            )
            raise

        if children is not None:
            logger.debug("recursive call")
            for child_id in children:
                self.add_a_node(
                    tree_id=tree_id,
                    loaded_tree=loaded_tree,
                    new_tree=new_tree,
                    node_id=child_id,
                    depth=depth + 1,
                )

        else:
            logger.debug("base_case")

        return new_tree


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
            except OperationFailure:
                logger.error(f"Failed to create collection {name}", exc_info=True)
                raise
        else:
            try:
                await db.command("collMod", name, validator=validator)
                logger.debug(f"Updated validator for existing collection: {name}")
            except OperationFailure:
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

    async def create_work(self, account_id: str, data: dict) -> dict:
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
            await self.work_collection.insert_one(doc)
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

    async def list_works(self, account_id: str) -> list[dict]:
        """Return all Works for account ordered by created_at descending."""
        logger.debug(f"list_works({account_id}) called")
        works: list[dict] = []
        try:
            async for doc in self.work_collection.find(
                {"account_id": account_id}, sort=[("created_at", -1)]
            ):
                works.append(_strip_id(doc))
        except (ConnectionFailure, OperationFailure):
            logger.error("Exception occurred listing works for account", exc_info=True)
            raise
        return works

    async def update_work(
        self, work_id: str, account_id: str, updates: dict
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
            )
        return _strip_id(result)

    async def cascade_author_to_nodes(
        self, work_id: str, account_id: str, author: str | None
    ) -> int:
        """Bulk-update author on every node belonging to this Work. Returns count updated."""
        logger.debug(f"cascade_author_to_nodes({work_id}) called")
        try:
            result = await self.node_collection.update_many(
                {"work_id": work_id, "account_id": account_id},
                {"$set": {"author": author}},
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(
                f"Exception occurred cascading author for work {work_id}", exc_info=True
            )
            raise
        return result.modified_count

    async def delete_work(
        self, work_id: str, account_id: str
    ) -> tuple[bool, int]:
        """Delete a Work and all its nodes. Returns (found, nodes_deleted)."""
        logger.debug(f"delete_work({work_id}) called")
        try:
            work_result = await self.work_collection.delete_one(
                {"work_id": work_id, "account_id": account_id}
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred deleting work {work_id}", exc_info=True)
            raise
        if work_result.deleted_count == 0:
            return False, 0
        try:
            node_result = await self.node_collection.delete_many(
                {"work_id": work_id, "account_id": account_id}
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

    async def create_node(self, account_id: str, work_doc: dict, data: dict) -> dict:
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
                sibling_filter, sort=[("position", -1)]
            )
        except (ConnectionFailure, OperationFailure):
            logger.error("Exception occurred querying sibling positions", exc_info=True)
            raise
        position = (latest["position"] + 1) if latest else 0

        now = datetime.now(timezone.utc)
        doc = {
            "node_id":     str(uuid.uuid4()),
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
            await self.node_collection.insert_one(doc)
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
        self, work_id: str, account_id: str, node_type: str | None = None
    ) -> list[dict]:
        """Return all nodes for a Work, optionally filtered by node_type."""
        logger.debug(f"list_nodes({work_id}) called")
        query: dict = {"work_id": work_id, "account_id": account_id}
        if node_type is not None:
            query["node_type"] = node_type
        nodes: list[dict] = []
        try:
            async for doc in self.node_collection.find(query):
                nodes.append(_strip_id(doc))
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred listing nodes for work {work_id}", exc_info=True)
            raise
        return nodes

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

    async def get_roots(self, work_id: str, account_id: str) -> list[dict]:
        """Return all Part nodes (parent_id == None) for a Work, ordered by position."""
        logger.debug(f"get_roots({work_id}) called")
        roots: list[dict] = []
        try:
            async for doc in self.node_collection.find(
                {"work_id": work_id, "account_id": account_id, "parent_id": None},
                sort=[("position", 1)],
            ):
                roots.append(_strip_id(doc))
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred getting roots for work {work_id}", exc_info=True)
            raise
        return roots

    async def get_leaves(self, work_id: str, account_id: str) -> list[dict]:
        """Return all Beat nodes for a Work, ordered by position."""
        logger.debug(f"get_leaves({work_id}) called")
        leaves: list[dict] = []
        try:
            async for doc in self.node_collection.find(
                {"work_id": work_id, "account_id": account_id, "node_type": "beat"},
                sort=[("position", 1)],
            ):
                leaves.append(_strip_id(doc))
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception occurred getting leaves for work {work_id}", exc_info=True)
            raise
        return leaves

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
        roots = await self.get_roots(work_id, account_id)
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

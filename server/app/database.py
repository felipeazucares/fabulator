
import os
import motor.motor_asyncio
from treelib import Tree
from fastapi.encoders import jsonable_encoder
from app.helpers import get_logger
from bson.objectid import ObjectId
from pymongo.errors import (
    ConnectionFailure,
    OperationFailure,
    DuplicateKeyError,
)
from bson.errors import InvalidId

from .models import (
    UserDetails,
    UpdateUserDetails,
    UpdateUserPassword,
    UpdateUserType,
    TreeSaveSchema,
    saves_helper,
    users_saves_helper
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

    def __init__(self, collection_name: str, client: motor.motor_asyncio.AsyncIOMotorClient):
        self.client = client
        self.database = self.client.fabulator
        self.tree_collection = self.database.get_collection(collection_name)

    async def save_working_tree(self, account_id: str, tree: Tree) -> dict:
        """ Save the current working tree to a document in the tree_collection for supplied account_id """
        logger.debug(f"save_working_tree({account_id}, tree) called")
        tree_to_save = TreeSaveSchema(account_id=account_id, tree=tree)
        try:
            save_response = await self.tree_collection.insert_one(jsonable_encoder(tree_to_save))
        except (ConnectionFailure, OperationFailure) as e:
            logger.error("Exception occured writing to the database", exc_info=True)
            raise
        try:
            await self.tree_collection.find_one({"_id": ObjectId(save_response.inserted_id)})
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving details for save operation _id: {save_response.inserted_id}", exc_info=True)
            raise
        return str(ObjectId(save_response.inserted_id))

    async def list_all_saved_trees(self, account_id: str) -> dict:
        """ return a dict of all the saves in the tree_collection for supplied account_id """
        logger.debug(f"list_all_saved_trees({account_id}) called")
        saves = []
        try:
            async for save in self.tree_collection.find({"account_id": account_id}):
                saves.append(saves_helper(save))
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured reading all database saves account_id {account_id}", exc_info=True)
            raise
        return saves

    async def delete_all_saves(self, account_id: str) -> int:
        """ delete all the saved documents in the tree_collection for supplied account_id """
        logger.debug(f"delete_all_saves({account_id}) called")
        try:
            delete_result = await self.tree_collection.delete_many({"account_id": account_id})
            # delete_result object contains a deleted_count & acknowledged properties
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured deleting saves from the database account_id was: {account_id}", exc_info=True)
            raise
        return delete_result.deleted_count

    async def number_of_saves_for_account(self, account_id: str) -> int:
        """ return count of save documents in the tree_collection for supplied account_id """
        logger.debug(f"number_of_saves_for_account({account_id}) called")
        try:
            save_count = await self.tree_collection.count_documents({"account_id": account_id})
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving document count account_id was: {account_id}", exc_info=True)
            raise
        return save_count

    async def return_latest_save(self, account_id: str) -> dict:
        """ return the latest save document from the tree_collection for supplied account_id """
        logger.debug(f"return_latest_save({account_id}) called")
        try:
            last_save = await self.tree_collection.find_one({"account_id": account_id}, sort=[("date_time", -1)])
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving latest save from the database account_id was: {account_id}", exc_info=True)
            raise
        return saves_helper(last_save)

    async def check_if_document_exists(self, save_id: str, account_id: str = None) -> int:
        """ return count of save documents in the tree_collection for supplied save_id.
            If account_id is provided, also verify the document belongs to that account. """
        logger.debug(f"check_if_document_exists({save_id}, account_id={account_id}) called")
        try:
            # Build query - always include save_id, optionally include account_id for ownership check
            query = {"_id": ObjectId(save_id)}
            if account_id is not None:
                query["account_id"] = account_id
            save_count = await self.tree_collection.count_documents(query)
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving document count save_id was: {save_id}", exc_info=True)
            raise
        return save_count

    async def return_save(self, save_id: str) -> dict:
        """ return save document from the tree_collection for supplied save_id """
        logger.debug(f"return_save({save_id}) called")
        try:
            save = await self.tree_collection.find_one({"_id": ObjectId(save_id)})
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving save from the database save_id was: {save_id}", exc_info=True)
            raise
        return saves_helper(save)

    async def load_save_into_working_tree(self, save_id: str) -> Tree:
        """ return a tree containing the latest saved tree """
        logger.debug(f"load_save_into_working_tree({save_id}) called")
        try:
            save = await self.return_save(save_id=save_id)
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving save from the database save_id was: {save_id}", exc_info=True)
            raise
        # get the tree dict from the saved document
        try:
            save_tree = save["tree"]
        except KeyError as e:
            logger.error(f"Exception occured retrieving tree structure from save", exc_info=True)
            raise

        return self.build_tree_from_dict(tree_dict=save_tree)

    async def load_latest_into_working_tree(self, account_id: str) -> Tree:
        """ return a tree containing the latest saved tree """
        logger.debug(f"load_latest_into_working_tree({account_id}) called")
        try:
            last_save = await self.return_latest_save(account_id=account_id)
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving latest save from the database account_id was: {account_id}", exc_info=True)
            raise
        # get the tree dict from the saved document
        try:
            last_save_tree = last_save["tree"]
        except KeyError as e:
            logger.error("Exception occured retrieving tree structure from last save", exc_info=True)
            raise

        return self.build_tree_from_dict(tree_dict=last_save_tree)

    def build_tree_from_dict(self, tree_dict: dict) -> Tree:
        """ return a tree built from provided dict structure  """
        # Looks like there is no root in the subtree
        try:
            root_node = tree_dict["root"]
        except KeyError as e:
            logger.error("Exception occured retrieving root object from dict", exc_info=True)
            raise
        # create the root node
        try:
            new_tree = Tree(identifier=tree_dict["_identifier"])
        except (KeyError, ValueError) as e:
            logger.error(f"Exception occured creating new tree with _identifier:{tree_dict['_identifier']}", exc_info=True)
            raise

        return self.add_a_node(tree_id=tree_dict["_identifier"], loaded_tree=tree_dict,
                               new_tree=new_tree, node_id=root_node, depth=0)

    def add_a_node(self, tree_id, loaded_tree, new_tree, node_id, depth: int = 0) -> Tree:
        """ Traverse the dict in mongo and rebuild the tree a node at a time (recursive) """
        if depth > MAX_TREE_DEPTH:
            logger.error(f"Tree depth {depth} exceeds MAX_TREE_DEPTH={MAX_TREE_DEPTH}")
            raise TreeDepthLimitExceeded(depth=depth, limit=MAX_TREE_DEPTH)

        logger.debug("add_a_node() called")

        # get name of node that's been passed to the routine
        try:
            name = loaded_tree["_nodes"][node_id]["_tag"]
            logger.debug(f"Current Node is: {name}")
        except KeyError as e:
            logger.error(f"Exception occurred unable to find _tag for node_id: {node_id}", exc_info=True)
            raise
        # get the id of the current node
        try:
            node_identifier = loaded_tree["_nodes"][node_id]["_identifier"]
            logger.debug(f"Current id is: {node_identifier}")
        except KeyError as e:
            logger.error(f"Exception occurred unable to find _identifier for node_id: {node_id}", exc_info=True)
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
            logger.error("Exception occurred retrieving the _successors field", exc_info=True)
            raise

        logger.debug(f"creating node with - name: {name}, identifier: {node_identifier}")

        try:
            new_tree.create_node(tag=name, identifier=node_identifier,
                                 parent=loaded_tree["_nodes"][node_id]["_predecessor"][tree_id], data=payload)
        except (KeyError, ValueError) as e:
            logger.error(f"Exception occurred adding a node to the working tree. name: {name}, identifier: {node_identifier}", exc_info=True)
            raise

        if children is not None:
            logger.debug("recursive call")
            for child_id in children:
                self.add_a_node(tree_id=tree_id, loaded_tree=loaded_tree,
                                new_tree=new_tree, node_id=child_id, depth=depth + 1)

        else:
            logger.debug("base_case")

        return new_tree


class UserStorage:

    def __init__(self, collection_name: str, client: motor.motor_asyncio.AsyncIOMotorClient):
        self.client = client
        self.database = self.client.fabulator
        self.user_collection = self.database.get_collection(collection_name)
        self.tree_collection = self.database.get_collection("tree_collection")

    async def does_account_exist(self, account_id: str):
        """ return true or false based on account_id existence """
        logger.debug(f"does_account_exist({account_id}) called")
        try:
            user_deets = await self.user_collection.find_one({"account_id": account_id})
            if user_deets is not None:
                account_exists = True
            else:
                account_exists = False
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving user details from the database account_id was: {account_id}", exc_info=True)
            raise
        return account_exists

    async def get_user_details_by_id(self, id: str):
        """ return the a user's details given the document id """
        logger.debug(f"get_user_details_by_id({id}) called")
        try:
            user_deets = await self.user_collection.find_one({"_id": ObjectId(id)})
            if user_deets is not None:
                user_details = UserDetails(**user_deets)
            else:
                user_details = None
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving user details from the database id was: {id}", exc_info=True)
            raise
        return user_details

    async def get_user_details_by_account_id(self, account_id: str):
        """ return the a user's details given their account_id """
        logger.debug(f"get_user_details_by_account({account_id}) called")
        try:
            user_deets = await self.user_collection.find_one(
                {"account_id": account_id})
            if user_deets is not None:
                user_details = UserDetails(**user_deets)
            else:
                user_details = None
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving user details from the database account_id was: {account_id}", exc_info=True)
            raise
        return user_details

    async def get_user_details_by_username(self, username: str):
        """ return the a user's details given their username - used for log in """
        logger.debug(f"get_user_details_by_username({username}) called")
        try:
            user_deets = await self.user_collection.find_one({"username": username})
            if user_deets is not None:
                user_details = UserDetails(**user_deets)
            else:
                user_details = None
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving user details from the database username was: {username}", exc_info=True)
            raise
        return user_details

    async def save_user_details(self, user: UserDetails) -> dict:
        """ save a user's details into the user collection """
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
            save_response = await self.user_collection.insert_one(jsonable_encoder(user_to_save))
        except (DuplicateKeyError, ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured saving user details account_id was: {user_to_save.account_id}", exc_info=True)
            raise
        try:
            new_user = await self.user_collection.find_one({"_id": ObjectId(save_response.inserted_id)})
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving new user from the database _id was: {save_response.inserted_id}", exc_info=True)
            raise

        return users_saves_helper(new_user)

    async def update_user_details(self, account_id: str, user: UpdateUserDetails) -> dict:
        """ save a user's details into the user collection """
        if user.email is not None and user.name is not None:

            logger.debug(f"update_user_details({account_id}) called")
            try:
                await self.user_collection.update_one({"account_id": account_id}, {'$set': {"name": {"firstname": user.name.firstname, "surname": user.name.surname}, "email": user.email}})
            except (ConnectionFailure, OperationFailure) as e:
                logger.error(f"Exception occured updating user details id was: {account_id}", exc_info=True)
                raise
            try:
                updated_user = await self.user_collection.find_one({"account_id": account_id})
            except (ConnectionFailure, OperationFailure) as e:
                logger.error(f"Exception occured retrieving updated user from the database id was: {account_id}", exc_info=True)
                raise
        else:
            logger.error("Nothing to change")
            raise
        return users_saves_helper(updated_user)

    async def update_user_password(self, account_id, user: UpdateUserPassword) -> dict:
        """ save a user's details into the user collection """
        if user.new_password is not None:

            logger.debug(f"update_upassword({account_id}) called")
            try:
                await self.user_collection.update_one({"account_id": account_id}, {'$set': {"password": user.new_password}})
            except (ConnectionFailure, OperationFailure) as e:
                logger.error(f"Exception occured updating user password id was: {account_id}", exc_info=True)
                raise
            try:
                updated_user = await self.user_collection.find_one({"account_id": account_id})
            except (ConnectionFailure, OperationFailure) as e:
                logger.error(f"Exception occured retrieving updated user from the database id was: {account_id}", exc_info=True)
                raise
        else:
            logger.error("Nothing to change")
            raise
        return users_saves_helper(updated_user)

    async def update_user_type(self, account_id, user: UpdateUserType) -> dict:
        """ update a user's type (free / premium) into the user collection """
        if user.user_type is not None:

            logger.debug(f"update_type({account_id}) called")
            try:
                await self.user_collection.update_one({"account_id": account_id}, {'$set': {"user_type": user.user_type}})
            except (ConnectionFailure, OperationFailure) as e:
                logger.error(f"Exception occured updating user type id was: {account_id}", exc_info=True)
                raise
            try:
                updated_user = await self.user_collection.find_one({"account_id": account_id})
            except (ConnectionFailure, OperationFailure) as e:
                logger.error(f"Exception occured retrieving updated user from the database id was: {account_id}", exc_info=True)
                raise
        else:
            logger.error("Nothing to change")
            raise
        return users_saves_helper(updated_user)

    async def delete_user_details(self, id: str) -> dict:
        """ delete a user's details from the user collection by document id"""
        logger.debug(f"delete_user_details({id}) called")
        try:
            delete_response = await self.user_collection.delete_one({"_id": ObjectId(id)})
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured delete user details from the database _id was: {id}", exc_info=True)
            raise

        return delete_response.deleted_count

    async def delete_user_details_by_account_id(self, account_id: str) -> dict:
        """ delete a user's details from the user collection """
        logger.debug(f"delete_user_details({account_id}) called")
        try:
            delete_response = await self.user_collection.delete_many({"account_id": account_id})
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured delete user details from the database account_id was: {account_id}", exc_info=True)
            raise
        # now remove any documents belonging to the users
        logger.debug(f"Removing documents for {account_id}")
        try:
            await self.tree_collection.delete_many({"account_id": account_id})
        except (ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured removing all documents for user account_id was: {account_id}", exc_info=True)
            raise
        return delete_response.deleted_count

    async def check_if_user_exists(self, user_id: str) -> int:
        """ return count of save documents in the user_collection for supplied user_id """
        logger.debug(f"check_if_user_exists({user_id}) called")
        try:
            user_count = await self.user_collection.count_documents({"_id": ObjectId(user_id)})
        except (InvalidId, ConnectionFailure, OperationFailure) as e:
            logger.error(f"Exception occured retrieving user document count user_id was: {user_id}", exc_info=True)
            raise
        return user_count

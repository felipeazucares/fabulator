import motor.motor_asyncio
from bson.objectid import ObjectId
from treelib import Tree, Node
from fastapi.encoders import jsonable_encoder
import json
from bson import json_util

from .models import (
    UserDetails,
    TreeSaveSchema,
    saves_helper
)

MONGO_DETAILS = "mongodb://localhost:27017"
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
database = client.fabulator
tree_collection = database.get_collection("tree_collection")


# ----------------------------------------------------
#  Functions for saving and loading the tree structure
# ----------------------------------------------------


async def save_working_tree(user: UserDetails, tree: Tree) -> dict:
    """ Save the current working tree to a document in the tree_collection for supplied account_id """

    tree_to_save = TreeSaveSchema(user=user, tree=tree)
    save_response = await tree_collection.insert_one(jsonable_encoder(tree_to_save))
    return save_response


async def list_all_saved_trees(user: UserDetails) -> dict:
    """ return a dict of all the saves in the tree_collection for supplied account_id """
    saves = []
    async for save in tree_collection.find({"account_id": user}):
        saves.append(saves_helper(save))
    return saves


async def delete_all_saves(user: UserDetails) -> int:
    """ delete all the saved documents in the tree_collection for supplied account_id """
    delete_result = await tree_collection.delete_many({"account_id": user})
    # delete_result object contains a deleted_count & acknowledged properties
    return delete_result.deleted_count


async def return_latest_save(user: UserDetails) -> dict:
    """ return the latest save document from the tree_collection for supplied account_id """
    last_save = await tree_collection.find_one({"account_id": user}, sort=[("date_time", -1)])
    return saves_helper(last_save)


async def load_latest_into_working_tree(user: UserDetails):
    """ return a tree containing the latest saved tree """
    tree_to_load = await return_latest_save(user)
    print(f"tree_to_load:{tree_to_load['tree']}")
    working_tree = Tree(json.loads(tree_to_load['tree'].to_json()))
    return working_tree

    # see if you can write out with the jsonEncondder and read with the loads - or the jsonable_encoder/decoder
    # todo actually take monog out of the equation and try with a precreated tree to see if it works at all

import motor.motor_asyncio
from bson.objectid import ObjectId
from treelib import Tree, Node
from fastapi.encoders import jsonable_encoder

from .models import (
    TreeSchema,
    saves_helper
)

MONGO_DETAILS = "mongodb://localhost:27017"
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
database = client.fabulator
tree_collection = database.get_collection("tree_collection")


# ----------------------------------------------------
#  Functions for saving and loading the tree structure
# ----------------------------------------------------


async def save_working_tree(tree: Tree) -> dict:
    """ Save the current working tree to a document in the tree_collection """
    tree_to_save = jsonable_encoder(TreeSchema(tree))
    save_response = await tree_collection.insert_one(tree_to_save)
    return save_response


async def list_all_saved_trees() -> dict:
    """ return a dict of all the saves in the tree_collection """
    saves = []
    async for save in tree_collection.find():
        saves.append(saves_helper(save))
    return saves


async def delete_all_saves() -> int:
    """ delete all the saved documents in the tree_collection """
    delete_result = await tree_collection.delete_many({})
    # delete_result object contains a deleted_count & acknowledged properties
    return delete_result.deleted_count


async def return_latest_save() -> dict:
    """ return the latest save document from the tree_collection """
    last_save = await tree_collection.find_one(sort=[("date_time", -1)])
    return saves_helper(last_save)

# todo: load the latest save into a tree


async def load_latest_into_working_tree():
    """ return a tree containing the latest saved tree """
    tree_to_load = await return_latest_save()
    working_tree = Tree()

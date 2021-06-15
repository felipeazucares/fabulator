from datetime import date, datetime, time, timedelta
import motor.motor_asyncio
from bson.objectid import ObjectId
from treelib import Tree
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

# Save the tree to a database document


async def save_working_tree(tree: Tree) -> dict:
    tree_to_save = jsonable_encoder(TreeSchema(tree))
    save_response = await tree_collection.insert_one(tree_to_save)
    return save_response

# return all the saves in the database


async def list_all_saved_trees() -> dict:
    saves = []
    async for save in tree_collection.find():
        saves.append(saves_helper(save))
    return saves

# delete all the saves in the collection


async def delete_all_saves() -> int:
    delete_result = await tree_collection.delete_many({})
    # delete_result object contains a deleted_count & acknowledged properties
    return delete_result.deleted_count


async def list_latest_save() -> dict:
    last_save = await tree_collection.find_one(sort=[("date_time", -1)])
    return saves_helper(last_save)

# todo: load the latest save into a tree

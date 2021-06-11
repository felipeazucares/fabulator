from datetime import date, datetime, time, timedelta
import motor.motor_asyncio
from bson.objectid import ObjectId
from treelib import Tree
from fastapi.encoders import jsonable_encoder

from .models import (
    TreeSchema
)

MONGO_DETAILS = "mongodb://localhost:27017"
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
database = client.fabulator
tree_collection = database.get_collection("tree_collection")


# ----------------------------------------------------
#  Functions for saving and loading the tree structure
# ----------------------------------------------------


def student_helper(student) -> dict:
    return {
        "id": str(student["_id"]),
        "fullname": student["fullname"],
        "email": student["email"],
        "course_of_study": student["course_of_study"],
        "year": student["year"],
        "GPA": student["gpa"],
    }

# Save the tree to a database document


async def save_working_tree(tree: Tree) -> dict:
    tree_to_save = jsonable_encoder(TreeSchema(tree))
    print(f"saving: {tree_to_save}")
    save_response = await tree_collection.insert_one(tree_to_save)
    return save_response

# return all the saves in the database


async def return_all_saves() -> dict:
    saves = []
    async for saves in tree_collection.find():
        saves.append(saves)
    return saves

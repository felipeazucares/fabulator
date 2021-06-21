import motor.motor_asyncio
from bson.objectid import ObjectId
from treelib import Tree, Node
from fastapi.encoders import jsonable_encoder
import json
from bson import json_util
from types import SimpleNamespace

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


async def load_latest_into_working_tree(user: UserDetails) -> dict:

    """ return a tree containing the latest saved tree """
    str = '{"identifier": "2e1c8abc-d272-11eb-ad82-f01898e87167", "nodes": {"6020c438-d272-11eb-ad82-f01898e87167": {"identifier": "6020c438-d272-11eb-ad82-f01898e87167", "tag": "TCA_Shame", "expanded": "True", "predecessor": {"2e1c8abc-d272-11eb-ad82-f01898e87167": "None", "6020c550-d272-11eb-ad82-f01898e87167": "None"}, "successors": {"2e1c8abc-d272-11eb-ad82-f01898e87167": [], "6020c550-d272-11eb-ad82-f01898e87167": []}, "data": {"description": "John meets his evil twin in a bar", "previous": "308fdfae-ca09-11eb-b437-f01898e87167", "next": "308fdfae-ca09-11eb-b437-f01898e87167", "text": "John walked into the bar. He pulled up a stool and sat down", "tags": ["main plot", "john", "evil twin"]}, "initial_tree_id": "2e1c8abc-d272-11eb-ad82-f01898e87167"}}, "root": "6020c438-d272-11eb-ad82-f01898e87167"}'
    dictx = SimpleNamespace(** json.loads(str))
    print(f"dictx:{dictx.root}")

    # save_record = await return_latest_save(user)
    # tree_to_load = save_record['tree'].replace("'", '"')
    # tree_to_load = tree_to_load.replace("None", '""')
    # print(f"tree root:{tree_to_load}")
    # print(f"tree root:{type(tree_to_load)}")
    # print(f"length:{len(tree_to_load)}")
    # x = json.loads(tree_to_load)
    # x = ast.literal_eval(tree_to_load)
    # print(f"eval:{x}")
    # print(f"tree root:{tree_to_load['tree']['root']}")
    working_tree = Tree(tree=dictx)
    #working_tree = tree_to_load
    return working_tree

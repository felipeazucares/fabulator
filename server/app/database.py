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


async def load_latest_into_working_tree(user: UserDetails) -> Tree:
    """ return a tree containing the latest saved tree """
    last_save = await return_latest_save(user=user)
    # get the tree dict from the saved document
    last_save_tree = last_save["tree"]
    # get the root node id
    root_node = last_save_tree["root"]
    # create the root node
    new_tree = Tree(identifier=last_save_tree["_identifier"])
    final_tree = add_a_node(last_save_tree["_identifier"], last_save_tree,
                            new_tree, root_node, None)
    return final_tree


def add_a_node(tree_id, loaded_tree, new_tree, node_id, parent_id) -> Tree:
    """ Traverse the dict in mongo and rebuild the tree (recursive) """
    print(f"tree: {loaded_tree['_nodes']}")
    name = loaded_tree["_nodes"][node_id]["_tag"]
    id = loaded_tree["_nodes"][node_id]["_identifier"]
    payload = loaded_tree["_nodes"][node_id]["data"]
    # for some reason the children of a node are stored under the tree_id key
    children = loaded_tree["_nodes"][node_id]["_successors"][tree_id]

    print(f"Children: {children}")

    new_tree.create_node(tag=name, identifier=id,
                         parent=parent_id, data=payload)
    if children != None:
        print(f"recursive call")
        for child_id in children:
            add_a_node(tree_id, loaded_tree, new_tree, child_id, id)
    else:
        print("base_case")
        new_tree.show(line_type="ascii-em")

    return new_tree

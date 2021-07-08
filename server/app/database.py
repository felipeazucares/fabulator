
import dns.resolver
import os
import motor.motor_asyncio
from treelib import Tree
from fastapi.encoders import jsonable_encoder
from app.helpers import ConsoleDisplay

from .models import (
    TreeSaveSchema,
    saves_helper
)


MONGO_DETAILS = os.getenv(key="MONGO_DETAILS")
DEBUG = os.getenv(key="DEBUG")

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
database = client.fabulator
tree_collection = database.get_collection("tree_collection")

console_display = ConsoleDisplay()

# ----------------------------------------------------
#  Functions for saving and loading the tree structure
# ----------------------------------------------------


async def save_working_tree(account_id: str, tree: Tree) -> dict:
    """ Save the current working tree to a document in the tree_collection for supplied account_id """
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
    database = client.fabulator
    tree_collection = database.get_collection("tree_collection")
    tree_to_save = TreeSaveSchema(account_id=account_id, tree=tree)
    try:
        save_response = await tree_collection.insert_one(jsonable_encoder(tree_to_save))
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Exception occured, writing to the database")
        print(e)
        raise
    return save_response


async def list_all_saved_trees(account_id: str) -> dict:
    """ return a dict of all the saves in the tree_collection for supplied account_id """
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
    database = client.fabulator
    tree_collection = database.get_collection("tree_collection")
    saves = []
    try:
        async for save in tree_collection.find({"account_id": account_id}):
            saves.append(saves_helper(save))
    except Exception as e:
        console_display.show_exception_message(
            message_to_show=f"Exception occured, reading all database saves to the database account_id {account_id}")
        print(e)
        raise
    return saves


async def delete_all_saves(account_id: str) -> int:
    """ delete all the saved documents in the tree_collection for supplied account_id """
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
    database = client.fabulator
    tree_collection = database.get_collection("tree_collection")
    try:
        delete_result = await tree_collection.delete_many({"account_id": account_id})
        # delete_result object contains a deleted_count & acknowledged properties
    except Exception as e:
        console_display.show_exception_message(
            message_to_show=f"Exception occured, deleting a save from the database account_id was: {account_id}")
        print(e)
        raise
    return delete_result.deleted_count


async def return_latest_save(account_id: str) -> dict:
    """ return the latest save document from the tree_collection for supplied account_id """
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
    database = client.fabulator
    tree_collection = database.get_collection("tree_collection")
    try:
        last_save = await tree_collection.find_one({"account_id": account_id}, sort=[("date_time", -1)])
    except Exception as e:
        console_display.show_exception_message(
            message_to_show=f"Exception occured, retrieving latest save from the database account_id was: {account_id}")
        print(e)
        raise
    return saves_helper(last_save)


async def load_latest_into_working_tree(account_id: str) -> Tree:
    """ return a tree containing the latest saved tree """
    try:
        last_save = await return_latest_save(account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show=f"Exception occured, retrieving latest save from the database account_id was: {account_id}")
        print(e)
        raise
    # get the tree dict from the saved document
    try:
        last_save_tree = last_save["tree"]
    except Exception as e:
        console_display.show_exception_message(
            message_to_show=f"Exception occured, retrieving tree structure from last save, last_save: {last_save}")
        print(e)
        raise
    # get the root node id
    try:
        root_node = last_save_tree["root"]
    except Exception as e:
        console_display.show_exception_message(
            message_to_show=f"Exception occured, retrieving root object from last save, last_save: {last_save}")
        print(e)
        raise
    # create the root node
    try:
        new_tree = Tree(identifier=last_save_tree["_identifier"])
    except Exception as e:
        console_display.show_exception_message(
            message_to_show=f"Exception occured, creating new tree. _identifier:{last_save_tree['_identifier']}")
        print(e)
        raise

    final_tree = add_a_node(last_save_tree["_identifier"], last_save_tree,
                            new_tree, root_node, None)
    return final_tree


def add_a_node(tree_id, loaded_tree, new_tree, node_id, parent_id) -> Tree:
    """ Traverse the dict in mongo and rebuild the tree (recursive) """
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"add_a_node({tree_id}, {loaded_tree}, {new_tree}, {node_id}, {parent_id}")

    try:
        name = loaded_tree["_nodes"][node_id]["_tag"]
    except KeyError as e:
        console_display.show_exception_message(
            message_to_show=f"Exception occurred, unable to find _tag for {loaded_tree['_nodes'][node_id]}")
        console_display.show_exception_message(
            message_to_show=f"loaded_tree['_nodes'][node_id]['_tag']: {loaded_tree['_nodes'][node_id]['_tag']}")
        print(e)
        raise

    try:
        id = loaded_tree["_nodes"][node_id]["_identifier"]
    except KeyError as e:
        console_display.show_exception_message(
            message_to_show=f"Exception occurred, unable to find _identifier for {loaded_tree['_nodes'][node_id]}")
        console_display.show_exception_message(
            message_to_show=f"loaded_tree['_nodes'][node_id]['_identifier']: {loaded_tree['_nodes'][node_id]['_identifier']}")
        print(e)
        raise

    try:
        payload = loaded_tree["_nodes"][node_id]["data"]
    except KeyError as e:
        console_display.show_exception_message(
            message_to_show=f"Exception occurred, unable to get node data")
        console_display.show_exception_message(
            message_to_show=f"loaded_tree['_nodes'][node_id]['data']: {loaded_tree['_nodes'][node_id]['data']}")
        print(e)
        raise

    # for some reason the children of a node are stored under the tree_id key

    try:
        children = loaded_tree["_nodes"][node_id]["_successors"][tree_id]
    except KeyError:
        # sometimes the _successors field has no key - so if we can't find it set to None
        children = None
    except Exception as e:
        console_display.show_exception_message(
            message_to_show=f"Exception occurred, retrieving the _successors field")
        console_display.show_exception_message(
            message_to_show=f"id:{loaded_tree['_nodes'][node_id]['_identifier']}")
        print(e)
        raise

    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"Node children: {children}")

    try:
        new_tree.create_node(tag=name, identifier=id,
                             parent=parent_id, data=payload)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show=f"Exception occurred adding a node to the working tree.")
        console_display.show_exception_message(
            message_to_show=f"name: {name}, identifier: {id}, data: {payload}, parent_d: {parent_id}")
        print(e)
        raise

    if children != None:

        if DEBUG:
            console_display.show_debug_message(
                message_to_show=f"recursive call")
        for child_id in children:
            add_a_node(tree_id, loaded_tree, new_tree, child_id, id)

    else:
        if DEBUG:
            console_display.show_debug_message(
                message_to_show="base_case")

    return new_tree


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

DEBUG = True

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
database = client.fabulator
tree_collection = database.get_collection("tree_collection")

console_display = ConsoleDisplay()

# ----------------------------------------------------
#  Functions for saving and loading the tree structure
# ----------------------------------------------------


class DatabaseStorage:

    def __init__(self, collection_name):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
        self.database = self.client.fabulator
        self.tree_collection = self.database.get_collection(collection_name)

    async def save_working_tree(self, account_id: str, tree: Tree) -> dict:
        """ Save the current working tree to a document in the tree_collection for supplied account_id """
        self.account_id = account_id
        self.tree = tree
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"save_working_tree({account_id}, tree) called")
        self.tree_to_save = TreeSaveSchema(
            account_id=self.account_id, tree=self.tree)
        try:
            self.save_response = await self.tree_collection.insert_one(jsonable_encoder(self.tree_to_save))
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show="Exception occured writing to the database")
            print(e)
            raise
        return self.save_response

    async def list_all_saved_trees(self, account_id: str) -> dict:
        """ return a dict of all the saves in the tree_collection for supplied account_id """
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"list_all_saved_trees({self.account_id}) called")
        self.saves = []
        try:
            async for save in self.tree_collection.find({"account_id": self.account_id}):
                self.saves.append(saves_helper(save))
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured reading all database saves to the database account_id {self.account_id}")
            print(e)
            raise
        return self.saves

    async def delete_all_saves(self, account_id: str) -> int:
        """ delete all the saved documents in the tree_collection for supplied account_id """
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"delete_all_saves({self.account_id}) called")
        try:
            self.delete_result = await self.tree_collection.delete_many({"account_id": self.account_id})
            # delete_result object contains a deleted_count & acknowledged properties
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured deleting a save from the database account_id was: {self.account_id}")
            print(e)
            raise
        return self.delete_result.deleted_count

    async def return_latest_save(self, account_id: str) -> dict:
        """ return the latest save document from the tree_collection for supplied account_id """
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"return_latest_save({self.account_id}) called")
        try:
            self.last_save = await self.tree_collection.find_one({"account_id": account_id}, sort=[("date_time", -1)])
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving latest save from the database account_id was: {self.account_id}")
            print(e)
            raise
        return saves_helper(self.last_save)

    async def load_latest_into_working_tree(self, account_id: str) -> Tree:
        """ return a tree containing the latest saved tree """
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"load_latest_into_working_tree({self.account_id}) called")
        try:
            self.last_save = await self.return_latest_save(account_id=self.account_id)
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving latest save from the database account_id was: {self.account_id}")
            print(e)
            raise
        # get the tree dict from the saved document
        try:
            self.last_save_tree = self.last_save["tree"]
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving tree structure from last save, last_save: {self.last_save}")
            print(e)
            raise
        # get the root node id
        try:
            self.root_node = self.last_save_tree["root"]
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving root object from last save, last_save: {self.last_save}")
            print(e)
            raise
        # create the root node
        try:
            self.new_tree = Tree(identifier=self.last_save_tree["_identifier"])
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured creating new tree. _identifier:{self.last_save_tree['_identifier']}")
            print(e)
            raise

        self.final_tree = self.add_a_node(self.last_save_tree["_identifier"], self.last_save_tree,
                                          self.new_tree, self.root_node, None)
        return self.final_tree

    def add_a_node(self, tree_id, loaded_tree, new_tree, node_id, parent_id) -> Tree:
        """ Traverse the dict in mongo and rebuild the tree (recursive) """
        self.tree_id = tree_id
        self.loaded_tree = loaded_tree
        self.new_tree = new_tree
        self.node_id = node_id
        self.parent_id = parent_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"add_a_node() called")

        try:
            self.name = self.loaded_tree["_nodes"][node_id]["_tag"]
        except KeyError as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred unable to find _tag for {self.loaded_tree['_nodes'][node_id]}")
            console_display.show_exception_message(
                message_to_show=f"loaded_tree['_nodes'][node_id]['_tag']: {self.loaded_tree['_nodes'][node_id]['_tag']}")
            print(e)
            raise

        try:
            self.id = self.loaded_tree["_nodes"][node_id]["_identifier"]
        except KeyError as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred unable to find _identifier for {self.loaded_tree['_nodes'][node_id]}")
            self.console_display.show_exception_message(
                message_to_show=f"loaded_tree['_nodes'][node_id]['_identifier']: {self.loaded_tree['_nodes'][node_id]['_identifier']}")
            print(e)
            raise

        try:
            self.payload = self.loaded_tree["_nodes"][node_id]["data"]
        except KeyError as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred unable to get node data")
            self.console_display.show_exception_message(
                message_to_show=f"loaded_tree['_nodes'][node_id]['data']: {self.loaded_tree['_nodes'][node_id]['data']}")
            print(e)
            raise

        # for some reason the children of a node are stored under the tree_id key

        try:
            self.children = self.loaded_tree["_nodes"][node_id]["_successors"][tree_id]
        except KeyError:
            # sometimes the _successors field has no key - so if we can't find it set to None
            self.children = None
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred retrieving the _successors field")
            self.console_display.show_exception_message(
                message_to_show=f"id:{self.loaded_tree['_nodes'][node_id]['_identifier']}")
            print(e)
            raise

        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"Node children: {self.children}")

        try:
            self.new_tree.create_node(tag=self.name, identifier=self.id,
                                      parent=self.parent_id, data=self.payload)
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred adding a node to the working tree.")
            self.console_display.show_exception_message(
                message_to_show=f"name: {self.name}, identifier: {self.id}, data: {self.payload}, parent_d: {self.parent_id}")
            print(e)
            raise

        if self.children != None:

            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"recursive call")
            for self.child_id in self.children:
                self.add_a_node(self.tree_id, self.loaded_tree,
                                self.new_tree, self.child_id, self.id)

        else:
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show="base_case")

        return self.new_tree

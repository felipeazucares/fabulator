
import os
# import hashlib
# import dns.resolver
import motor.motor_asyncio
from treelib import Tree
from fastapi.encoders import jsonable_encoder
from app.helpers import ConsoleDisplay
from bson.objectid import ObjectId

from .models import (
    UserDetails,
    TreeSaveSchema,
    saves_helper,
    users_saves_helper
)


MONGO_DETAILS = os.getenv(key="MONGO_DETAILS")
DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')

# client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
# database = client.fabulator
# tree_collection = database.get_collection("tree_collection")

console_display = ConsoleDisplay()

# ----------------------------------------------------
#  Functions for saving and loading the tree structure
# ----------------------------------------------------


class TreeStorage:

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
        try:
            self.new_save = await self.tree_collection.find_one({"_id": ObjectId(self.save_response.inserted_id)})
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retriving details for save operation to the database _id: {self.save_response.inserted_id}")
            print(e)
            raise
        return str(ObjectId(self.save_response.inserted_id))

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

    async def number_of_saves_for_account(self, account_id: str) -> int:
        """ return count of save documents in the tree_collection for supplied account_id """
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"number_of_saves_for_account({self.account_id}) called")
        try:
            self.save_count = await self.tree_collection.count_documents({"account_id": self.account_id})
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving document count account_id was: {self.account_id}")
            print(e)
            raise
        return self.save_count

    async def return_latest_save(self, account_id: str) -> dict:
        """ return the latest save document from the tree_collection for supplied account_id """
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"return_latest_save({self.account_id}) called")
        try:
            self.last_save = await self.tree_collection.find_one({"account_id": self.account_id}, sort=[("date_time", -1)])
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving latest save from the database account_id was: {self.account_id}")
            print(e)
            raise
        return saves_helper(self.last_save)

    async def check_if_document_exists(self, save_id: str) -> int:
        """ return count of save documents in the tree_collection for supplied save_id """
        self.save_id = save_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"check_if_document_exists({self.save_id}) called")
        try:
            self.save_count = await self.tree_collection.count_documents({"_id": ObjectId(self.save_id)})
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving document count save_id was: {self.save_id}")
            print(e)
            raise
        return self.save_count

    async def return_save(self, save_id: str) -> dict:
        """ return save document from the tree_collection for supplied save_id """
        self.save_id = save_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"return_save({self.save_id}) called")
        try:
            self.save = await self.tree_collection.find_one({"_id": ObjectId(self.save_id)})
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving save from the database save_id was: {self.save_id}")
            print(e)
            raise
        return saves_helper(self.save)

    async def load_save_into_working_tree(self, save_id: str) -> Tree:
        """ return a tree containing the latest saved tree """
        self.save_id = save_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"load_save_into_working_tree({self.save_id}) called")
        try:
            self.save = await self.return_save(save_id=self.save_id)
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving latest save from the database account_id was: {self.save_id}")
            print(e)
            raise
        # get the tree dict from the saved document
        try:
            self.save_tree = self.save["tree"]
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving tree structure from last save, last_save: {self.save}")
            print(e)
            raise

        return self.build_tree_from_dict(tree_dict=self.save_tree)

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

        return self.build_tree_from_dict(tree_dict=self.last_save_tree)

    def build_tree_from_dict(self, tree_dict: dict) -> Tree:
        """ return a tree built from provided dict structure  """
        self.tree_dict = tree_dict
        # Looks like there is no root in the subtree
        try:
            self.root_node = self.tree_dict["root"]
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving root object from dict, self.tree_dict: {self.tree_dict} {e}")
            raise
        # create the root node
        try:
            self.new_tree = Tree(identifier=self.tree_dict["_identifier"])
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured creating new tree with _identifier:{self.tree_dict['_identifier']} {e}")
            raise

        self.final_tree = self.add_a_node(tree_id=self.tree_dict["_identifier"], loaded_tree=self.tree_dict,
                                          new_tree=self.new_tree, node_id=self.root_node)
        return self.final_tree

    def add_a_node(self, tree_id, loaded_tree, new_tree, node_id) -> Tree:
        """ Traverse the dict in mongo and rebuild the tree a node at a time (recursive) """
        self.tree_id = tree_id
        self.loaded_tree = loaded_tree
        self.new_tree = new_tree
        self.node_id = node_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"add_a_node() called")

        # get name of node that's been passed to the routine
        try:
            self.name = self.loaded_tree["_nodes"][node_id]["_tag"]
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"Current Node is: {self.name}")
        except KeyError as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred unable to find _tag for {self.loaded_tree['_nodes'][node_id]}")
            self.console_display.show_exception_message(
                message_to_show=f"loaded_tree['_nodes'][node_id]['_tag']: {self.loaded_tree['_nodes'][node_id]['_tag']}")
            print(e)
            raise
        # get the id of the current node
        try:
            self.id = self.loaded_tree["_nodes"][node_id]["_identifier"]
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"Current id is: {self.id}")
        except KeyError as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred unable to find _identifier for {self.loaded_tree['_nodes'][node_id]}")
            self.console_display.show_exception_message(
                message_to_show=f"loaded_tree['_nodes'][node_id]['_identifier']: {self.loaded_tree['_nodes'][node_id]['_identifier']}")
            print(e)
            raise
        # set payload for new node to what's in the current node
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
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"{self.name}'s children: {self.children}")
        except KeyError:
            # sometimes the _successors field has no key - so if we can't find it set to None
            self.children = None
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"{self.name}'s children: None")
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred retrieving the _successors field")
            self.console_display.show_exception_message(
                message_to_show=f"id:{self.loaded_tree['_nodes'][node_id]['_identifier']}")
            print(e)
            raise

        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"creating node with - name: {self.name}, identifier: {self.id}")

        try:
            self.new_tree.create_node(tag=self.name, identifier=self.id,
                                      parent=self.loaded_tree["_nodes"][node_id]["_predecessor"][tree_id], data=self.payload)
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred adding a node to the working tree.")
            self.console_display.show_exception_message(
                message_to_show=f"name: {self.name}, identifier: {self.id}, data: {self.payload}")
            print(e)
            raise

        if self.children != None:

            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"recursive call")
            for self.child_id in self.children:
                self.add_a_node(tree_id=self.tree_id, loaded_tree=self.loaded_tree,
                                new_tree=self.new_tree, node_id=self.child_id)

        else:
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show="base_case")

        return self.new_tree


class UserStorage:

    def __init__(self, collection_name):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
        self.database = self.client.fabulator
        self.user_collection = self.database.get_collection(collection_name)

    async def does_account_exist(self, account_id: str):
        """ return true or false based on account_id existence """
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"does_account_exist({self.account_id}) called")
        try:
            user_deets = await self.user_collection.find_one({"account_id": self.account_id})
            if user_deets is not None:
                account_exists = True
            else:
                account_exists = False
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving user details from the database account_id was: {self.account_id}")
            print(e)
            raise
        return account_exists

    async def get_user_details_by_id(self, id: str):
        """ return the a user's details given the document id """
        self.id = id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"get_user_details_by_id({self.id}) called")
        try:
            user_deets = await self.user_collection.find_one({"_id": ObjectId(self.id)})
            if user_deets is not None:
                self.user_details = UserDetails(**user_deets)
            else:
                self.user_details = None
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving user details from the database account_id was: {self.id}")
            print(e)
            raise
        return self.user_details

    async def get_user_details_by_account_id(self, account_id: str):
        """ return the a user's details given their account_id """
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"get_user_details_by_account({self.account_id}) called")
        try:
            user_deets = await self.user_collection.find_one(
                {"account_id": self.account_id})
            if user_deets is not None:
                self.user_details = UserDetails(**user_deets)
            else:
                self.user_details = None
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving user details from the database account_id was: {self.account_id}")
            print(e)
            raise
        return self.user_details

    async def get_user_details_by_username(self, username: str):
        """ return the a user's details given their username - used for log in """
        # have to have this in there to avoid event_loop_closed errors during testing
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
        self.database = self.client.fabulator
        self.user_collection = self.database.get_collection("user_collection")
        self.username = username
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"get_user_details_by_username({self.username}) called")
        try:
            user_deets = await self.user_collection.find_one({"username": self.username})
            if user_deets is not None:
                print(f"user_deets:{user_deets}")
                self.user_details = UserDetails(**user_deets)
            else:
                self.user_details = None
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving user details from the database username was: {self.username}")
            print(e)
            raise
        return self.user_details

    async def save_user_details(self, user: UserDetails) -> dict:
        """ save a user's details into the user collection """
        self.username = user.username
        self.firstname = user.name.firstname
        self.password = user.password
        self.surname = user.name.surname
        self.email = user.email
        self.account_id = user.account_id
        self.disabled = user.disabled
        self.user_role = user.user_role
        self.user_type = user.user_type
        self.user = UserDetails(name={"firstname": self.firstname, "surname": self.surname},
                                username=self.username, password=self.password,
                                account_id=self.account_id, disabled=self.disabled, user_role=self.user_role,
                                email=self.email, user_type=self.user_type)
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"user: {self.user}")
            self.console_display.show_debug_message(
                message_to_show=f"save_user_details({self.user.account_id}) called")
        try:
            self.save_response = await self.user_collection.insert_one(jsonable_encoder(self.user))
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured saving user details from the database account_id was: {self.user.account_id}")
            print(e)
            raise
        try:
            self.new_user = await self.user_collection.find_one({"_id": ObjectId(self.save_response.inserted_id)})
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retreiving new user from the database _id was: {self.save_response.inserted_id}")
            print(e)
            raise

        return users_saves_helper(self.new_user)

    async def update_user_details(self, account_id: str, user: UserDetails) -> dict:
        """ save a user's details into the user collection """
        self.account_id_to_update = account_id
        # self.username = user.username
        # self.firstname = user.name.firstname
        # self.surname = user.name.surname
        # self.password = user.password
        # self.email = user.email
        # self.account_id = user.account_id
        # self.disabled = user.disabled
        # self.user_role = user.user_role
        self.user = user
        # self.user = UserDetails(name={"firstname": self.firstname, "surname": self.surname},
        #                         username=self.username,
        #                         password=self.password,
        #                         account_id=self.account_id, disabled=self.disabled, user_role=self.user_role,
        #                         email=self.email)
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"update_user_details({self.account_id_to_update}) called")
        try:
            self.update_response = await self.user_collection.replace_one({"account_id": self.account_id_to_update}, jsonable_encoder(self.user))
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured updating user details id was: {self.account_id_to_update}")
            print(e)
            raise
        try:
            self.updated_user = await self.user_collection.find_one({"account_id": self.account_id_to_update})
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retreiving updated user from the database _id was: {self.account_id_to_update}")
            print(e)
            raise
        return users_saves_helper(self.updated_user)

    async def delete_user_details(self, id: str) -> dict:
        """ delete a user's details from the user collection """
        self.id_to_delete = id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"delete_user_details({self.id_to_delete}) called")
        try:
            self.delete_response = await self.user_collection.delete_one({"_id": ObjectId(self.id_to_delete)})
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured delete user details from the database _id was: {self.id_to_delete}")
            print(e)
            raise
        return self.delete_response.deleted_count

    async def delete_user_details_by_account_id(self, account_id: str) -> dict:
        """ delete a user's details from the user collection """
        self.account_id_to_delete = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"delete_user_details({self.account_id_to_delete}) called")
        try:
            self.delete_response = await self.user_collection.delete_many({"account_id": self.account_id_to_delete})
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured delete user details from the database account_id was: {self.account_id_to_delete}")
            print(e)
            raise
        return self.delete_response.deleted_count

    async def delete_user_details(self, id: str) -> dict:
        """ delete a user's details from the user collection """
        self.id_to_delete = id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"delete_user_details({self.id_to_delete}) called")
        try:
            self.delete_response = await self.user_collection.delete_one({"_id": ObjectId(self.id_to_delete)})
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured delete user details from the database _id was: {self.id_to_delete}")
            print(e)
            raise
        return self.delete_response.deleted_count

    async def check_if_user_exists(self, user_id: str) -> int:
        """ return count of save documents in the user_collection for supplied user_id """
        self.user_id = user_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"check_if_user_exists({self.user_id}) called")
        try:
            self.user_count = await self.user_collection.count_documents({"_id": ObjectId(self.user_id)})
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving user document count user_id was: {self.user_id}")
            print(e)
            raise
        return self.user_count

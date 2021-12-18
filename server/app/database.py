import os
import motor.motor_asyncio
from treelib import Tree
from fastapi.encoders import jsonable_encoder
from app.helpers import ConsoleDisplay
from bson.objectid import ObjectId
import datetime

from .models import (
    UserDetails,
    UpdateUserDetails,
    UpdateUserPassword,
    UpdateUserType,
    TreeSaveSchema,
    RetrieveProject,
    UpdateProject,
    CreateProject,
    project_saves_helper,
    project_errors_helper,
    saves_helper,
    users_saves_helper,
    users_errors_helper,
)


MONGO_DETAILS = os.getenv(key="MONGO_DETAILS")
DEBUG = bool(os.getenv("DEBUG", "False") == "True")


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
        """Save the current working tree to a document in the tree_collection for supplied account_id"""
        self.account_id = account_id
        self.tree = tree
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"save_working_tree({account_id}, tree) called"
            )
        self.tree_to_save = TreeSaveSchema(account_id=self.account_id, tree=self.tree)
        try:
            self.save_response = await self.tree_collection.insert_one(
                jsonable_encoder(self.tree_to_save)
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show="Exception occured writing to the database"
            )
            print(e)
            raise
        try:
            self.new_save = await self.tree_collection.find_one(
                {"_id": ObjectId(self.save_response.inserted_id)}
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retriving details for save operation to the database _id: {self.save_response.inserted_id}"
            )
            print(e)
            raise
        return str(ObjectId(self.save_response.inserted_id))

    async def create_tree(self, account_id: str, root_node_tag: str) -> str:
        self.account_id = account_id
        self.root_node_tag = root_node_tag
        self.console_display = ConsoleDisplay()
        # create the new tree object
        try:
            self.new_tree = Tree()
            self.new_tree.create_node(self.root_node_tag)
            self.new_tree.show()
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured creating new tree details for account_id: {self.account_id}"
            )
            print(e)
            raise
        # now save it
        try:
            self.save_response = await self.save_working_tree(
                account_id=self.account_id, tree=self.new_tree
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured saving new tree details for account_id: {self.account_id}"
            )
            print(e)
            raise
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"new_tree_identifier:{self.new_tree.identifier}"
            )
        return self.new_tree.identifier

    async def list_all_saved_trees(self, account_id: str) -> dict:
        """return a dict of all the saves in the tree_collection for supplied account_id"""
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"list_all_saved_trees({self.account_id}) called"
            )
        self.saves = []
        try:
            async for save in self.tree_collection.find(
                {"account_id": self.account_id}
            ):
                self.saves.append(saves_helper(save))
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured reading all database saves to the database account_id {self.account_id}"
            )
            print(e)
            raise
        return self.saves

    async def delete_all_saves(self, account_id: str) -> int:
        """delete all the saved documents in the tree_collection for supplied account_id"""
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"delete_all_saves({self.account_id}) called"
            )
        try:
            self.delete_result = await self.tree_collection.delete_many(
                {"account_id": self.account_id}
            )
            # delete_result object contains a deleted_count & acknowledged properties
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured deleting a save from the database account_id was: {self.account_id}"
            )
            print(e)
            raise
        return self.delete_result.deleted_count

    async def number_of_saves_for_account(self, account_id: str) -> int:
        """return count of save documents in the tree_collection for supplied account_id"""
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"number_of_saves_for_account({self.account_id}) called"
            )
        try:
            self.save_count = await self.tree_collection.count_documents(
                {"account_id": self.account_id}
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving document count account_id was: {self.account_id}"
            )
            print(e)
            raise
        return self.save_count

    async def return_latest_save(self, account_id: str) -> dict:
        """return the latest save document from the tree_collection for supplied account_id"""
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"return_latest_save({self.account_id}) called"
            )
        try:
            self.last_save = await self.tree_collection.find_one(
                {"account_id": self.account_id}, sort=[("date_time", -1)]
            )

        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving latest save from the database account_id was: {self.account_id}"
            )
            print(e)
            raise
        if self.last_save is None:
            return None
        else:
            return saves_helper(self.last_save)

    async def check_if_document_exists(self, save_id: str) -> int:
        """return count of save documents in the tree_collection for supplied save_id"""
        self.save_id = save_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"check_if_document_exists({self.save_id}) called"
            )
        try:
            self.save_count = await self.tree_collection.count_documents(
                {"_id": ObjectId(self.save_id)}
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving document count save_id was: {self.save_id}"
            )
            print(e)
            raise
        return self.save_count

    async def return_save(self, save_id: str) -> dict:
        """return save document from the tree_collection for supplied save_id"""
        self.save_id = save_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"return_save({self.save_id}) called"
            )
        try:
            self.save = await self.tree_collection.find_one(
                {"_id": ObjectId(self.save_id)}
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving save from the database save_id was: {self.save_id}"
            )
            print(e)
            raise
        return saves_helper(self.save)

    async def load_save_into_working_tree(self, save_id: str) -> Tree:
        """return a tree containing the latest saved tree"""
        self.save_id = save_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"load_save_into_working_tree({self.save_id}) called"
            )
        try:
            self.save = await self.return_save(save_id=self.save_id)
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving latest save from the database account_id was: {self.save_id}"
            )
            print(e)
            raise
        # get the tree dict from the saved document
        try:
            self.save_tree = self.save["tree"]
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving tree structure from last save, last_save: {self.save}"
            )
            print(e)
            raise

        return self.build_tree_from_dict(tree_dict=self.save_tree)

    async def load_latest_into_working_tree(self, account_id: str) -> Tree:
        """return a tree containing the latest saved tree"""
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"load_latest_into_working_tree({self.account_id}) called"
            )
        try:
            self.last_save = await self.return_latest_save(account_id=self.account_id)
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving latest save from the database account_id was: {self.account_id}"
            )
            print(e)
            raise
        # get the tree dict from the saved document
        if self.last_save:
            try:
                self.last_save_tree = self.last_save["tree"]
                self.tree = self.build_tree_from_dict(tree_dict=self.last_save_tree)
            except Exception as e:
                self.console_display.show_exception_message(
                    message_to_show=f"Exception occured retrieving tree structure from last save, last_save: {self.last_save}"
                )
                print(e)
                raise
        else:
            self.tree = Tree()
        return self.tree

    def build_tree_from_dict(self, tree_dict: dict) -> Tree:
        """return a tree built from provided dict structure"""
        self.tree_dict = tree_dict
        # Looks like there is no root in the subtree
        try:
            self.root_node = self.tree_dict["root"]
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving root object from dict, self.tree_dict: {self.tree_dict} {e}"
            )
            raise
        # create the root node
        try:
            self.new_tree = Tree(identifier=self.tree_dict["_identifier"])
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured creating new tree with _identifier:{self.tree_dict['_identifier']} {e}"
            )
            raise

        self.final_tree = self.add_a_node(
            tree_id=self.tree_dict["_identifier"],
            loaded_tree=self.tree_dict,
            new_tree=self.new_tree,
            node_id=self.root_node,
        )
        return self.final_tree

    def add_a_node(self, tree_id, loaded_tree, new_tree, node_id) -> Tree:
        """Traverse the dict in mongo and rebuild the tree a node at a time (recursive)"""
        self.tree_id = tree_id
        self.loaded_tree = loaded_tree
        self.new_tree = new_tree
        self.node_id = node_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"add_a_node() called"
            )

        # get name of node that's been passed to the routine
        try:
            self.name = self.loaded_tree["_nodes"][node_id]["_tag"]
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"Current Node is: {self.name}"
                )
        except KeyError as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred unable to find _tag for {self.loaded_tree['_nodes'][node_id]}"
            )
            self.console_display.show_exception_message(
                message_to_show=f"loaded_tree['_nodes'][node_id]['_tag']: {self.loaded_tree['_nodes'][node_id]['_tag']}"
            )
            print(e)
            raise
        # get the id of the current node
        try:
            self.id = self.loaded_tree["_nodes"][node_id]["_identifier"]
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"Current id is: {self.id}"
                )
        except KeyError as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred unable to find _identifier for {self.loaded_tree['_nodes'][node_id]}"
            )
            self.console_display.show_exception_message(
                message_to_show=f"loaded_tree['_nodes'][node_id]['_identifier']: {self.loaded_tree['_nodes'][node_id]['_identifier']}"
            )
            print(e)
            raise
        # set payload for new node to what's in the current node
        try:
            self.payload = self.loaded_tree["_nodes"][node_id]["data"]
        except KeyError as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred unable to get node data"
            )
            self.console_display.show_exception_message(
                message_to_show=f"loaded_tree['_nodes'][node_id]['data']: {self.loaded_tree['_nodes'][node_id]['data']}"
            )
            print(e)
            raise

        # for some reason the children of a node are stored under the tree_id key

        try:
            self.children = self.loaded_tree["_nodes"][node_id]["_successors"][tree_id]
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"{self.name}'s children: {self.children}"
                )
        except KeyError:
            # sometimes the _successors field has no key - so if we can't find it set to None
            self.children = None
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"{self.name}'s children: None"
                )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred retrieving the _successors field"
            )
            self.console_display.show_exception_message(
                message_to_show=f"id:{self.loaded_tree['_nodes'][node_id]['_identifier']}"
            )
            print(e)
            raise

        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"creating node with - name: {self.name}, identifier: {self.id}"
            )

        try:
            self.new_tree.create_node(
                tag=self.name,
                identifier=self.id,
                parent=self.loaded_tree["_nodes"][node_id]["_predecessor"][tree_id],
                data=self.payload,
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occurred adding a node to the working tree."
            )
            self.console_display.show_exception_message(
                message_to_show=f"name: {self.name}, identifier: {self.id}, data: {self.payload}"
            )
            print(e)
            raise

        if self.children != None:

            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"recursive call"
                )
            for self.child_id in self.children:
                self.add_a_node(
                    tree_id=self.tree_id,
                    loaded_tree=self.loaded_tree,
                    new_tree=self.new_tree,
                    node_id=self.child_id,
                )

        else:
            if DEBUG:
                self.console_display.show_debug_message(message_to_show="base_case")

        return self.new_tree


class UserStorage:
    def __init__(self, collection_name):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
        self.database = self.client.fabulator
        self.user_collection = self.database.get_collection(collection_name)
        self.tree_collection = self.database.get_collection("tree_collection")

    async def does_account_exist(self, account_id: str):
        """return true or false based on account_id existence"""
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"does_account_exist({self.account_id}) called"
            )
        try:
            user_deets = await self.user_collection.find_one(
                {"account_id": self.account_id}
            )
            if user_deets is not None:
                account_exists = True
            else:
                account_exists = False
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving user details from the database account_id was: {self.account_id}"
            )
            print(e)
            raise
        return account_exists

    async def get_user_details_by_id(self, id: str):
        """return the a user's details given the document id"""
        self.id = id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"get_user_details_by_id({self.id}) called"
            )
        try:
            user_deets = await self.user_collection.find_one({"_id": ObjectId(self.id)})
            if user_deets is not None:
                self.user_details = UserDetails(**user_deets)
            else:
                self.user_details = None
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving user details from the database account_id was: {self.id}"
            )
            print(e)
            raise
        return self.user_details

    async def get_user_details_by_account_id(self, account_id: str):
        """return the a user's details given their account_id"""
        self.account_id = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"get_user_details_by_account({self.account_id}) called"
            )
        try:
            user_deets = await self.user_collection.find_one(
                {"account_id": self.account_id}
            )
            if user_deets is not None:
                self.user_details = UserDetails(**user_deets)
            else:
                self.user_details = None
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving user details from the database account_id was: {self.account_id}"
            )
            print(e)
            raise
        return self.user_details

    async def get_user_details_by_username(self, username: str):
        """return the a user's details given their username - used for log in"""
        # have to have this in there to avoid event_loop_closed errors during testing
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
        self.database = self.client.fabulator
        self.user_collection = self.database.get_collection("user_collection")
        self.username = username
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"get_user_details_by_username({self.username}) called"
            )
        try:
            user_deets = await self.user_collection.find_one(
                {"username": self.username}
            )
            if user_deets is not None:
                self.user_details = UserDetails(**user_deets)

            else:
                self.user_details = None
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving user details from the database username was: {self.username}"
            )
            print(e)
            raise
        return self.user_details

    async def save_user_details(self, user: UserDetails) -> dict:
        """save a user's details into the user collection"""
        # check if username already exists
        if await self.get_user_details_by_username(username=user.username) is None:
            # check if email already exists
            if await self.user_collection.find_one({"email": user.email}) is None:
                self.username = user.username
                self.firstname = user.name.firstname
                self.password = user.password
                self.surname = user.name.surname
                self.email = user.email
                self.account_id = user.account_id
                self.disabled = user.disabled
                self.user_role = user.user_role
                self.user_type = user.user_type
                self.projects = user.projects
                self.current_project = user.current_project
                self.user = UserDetails(
                    name={"firstname": self.firstname, "surname": self.surname},
                    username=self.username,
                    password=self.password,
                    account_id=self.account_id,
                    disabled=self.disabled,
                    user_role=self.user_role,
                    email=self.email,
                    user_type=self.user_type,
                    projects=self.projects,
                    current_project=self.current_project,
                )
                self.console_display = ConsoleDisplay()
                if DEBUG:
                    self.console_display.show_debug_message(
                        message_to_show=f"user: {self.user}"
                    )
                    self.console_display.show_debug_message(
                        message_to_show=f"save_user_details({self.user.account_id}) called"
                    )
                try:
                    self.save_response = await self.user_collection.insert_one(
                        jsonable_encoder(self.user)
                    )
                except Exception as e:
                    self.console_display.show_exception_message(
                        message_to_show=f"Exception occured saving user details from the database account_id was: {self.user.account_id}"
                    )
                    print(e)
                    raise
                try:
                    self.new_user = await self.user_collection.find_one(
                        {"_id": ObjectId(self.save_response.inserted_id)}
                    )
                except Exception as e:
                    self.console_display.show_exception_message(
                        message_to_show=f"Exception occured retreiving new user from the database _id was: {self.save_response.inserted_id}"
                    )
                    print(e)
                    raise
                return users_saves_helper(self.new_user)
            else:
                return users_errors_helper(
                    {
                        "error": "unable to save user",
                        "message": "email already registered",
                    }
                )
        else:
            return users_errors_helper(
                {
                    "error": "unable to save user",
                    "message": "username already registered",
                }
            )

    async def update_user_details(
        self, account_id: str, user: UpdateUserDetails
    ) -> dict:
        """save a user's details into the user collection"""
        self.account_id_to_update = account_id
        self.user = user
        if self.user.email is not None and self.user.name is not None:
            self.console_display = ConsoleDisplay()
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"update_user_details({self.account_id_to_update}) called"
                )
            try:
                self.update_response = await self.user_collection.update_one(
                    {"account_id": self.account_id_to_update},
                    {
                        "$set": {
                            "name": {
                                "firstname": self.user.name.firstname,
                                "surname": self.user.name.surname,
                            },
                            "email": self.user.email,
                        }
                    },
                )
            except Exception as e:
                self.console_display.show_exception_message(
                    message_to_show=f"Exception occured updating user details id was: {self.account_id_to_update}"
                )
                print(e)
                raise
            try:
                self.updated_user = await self.user_collection.find_one(
                    {"account_id": self.account_id_to_update}
                )
            except Exception as e:
                self.console_display.show_exception_message(
                    message_to_show=f"Exception occured retreiving updated user from the database _id was: {self.account_id_to_update}"
                )
                print(e)
                raise
        else:
            self.console_display.show_exception_message("Nothing to change")
            raise
        return users_saves_helper(self.updated_user)

    async def update_user_project(
        self, account_id: str, current_project_id: str
    ) -> dict:
        """change the current_project setting for a user"""
        self.account_id_to_update = account_id
        self.current_project_id = current_project_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"update_user_project(account:{self.account_id_to_update},project:{self.current_project_id}) called"
            )
        if self.current_project_id is not None:
            # check to see if we can get this project - if not then its doesn't exist or
            # we're not the owner
            try:
                db_storage = ProjectStorage(collection_name="project_collection")
                project_details = await db_storage.get_project_details(
                    account_id=account_id, project_id=current_project_id
                )
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show=f"Error occured getting project document with id :{current_project_id} make sure it exists and that you are the owner"
                )
                raise
            # if we can see it and we're the owner then update the current project
            if not (hasattr(project_details, "error")):
                try:
                    self.update_response = await self.user_collection.update_one(
                        {"account_id": self.account_id_to_update},
                        {
                            "$set": {
                                "current_project": self.current_project_id,
                            }
                        },
                    )
                except Exception as e:
                    self.console_display.show_exception_message(
                        message_to_show=f"Exception occured updating current_project user details id was: {self.account_id_to_update}, project:{self.current_project_id}"
                    )
                    print(e)
                    raise
                # now that its been updated let's get it so that we can return the updated record
                try:
                    self.updated_user = await self.user_collection.find_one(
                        {"account_id": self.account_id_to_update}
                    )
                    if DEBUG:
                        self.console_display.show_debug_message(
                            message_to_show=f"updated user details: {self.updated_user}"
                        )
                except Exception as e:
                    self.console_display.show_exception_message(
                        message_to_show=f"Exception occured retreiving updated user from the database _id was: {self.account_id_to_update}"
                    )
                    print(e)
                    raise
            else:
                # we can't find the project
                if DEBUG:
                    self.console_display.show_debug_message("Unable to find project")
                return project_errors_helper(
                    {
                        "error": "Unable to update project",
                        "message": "Project does not belong to user",
                    }
                )
        else:
            if DEBUG:
                self.console_display.show_debug_message("Nothing to change")
                return project_errors_helper(
                    {
                        "error": "Invalid project id",
                        "message": "No project id provided",
                    }
                )

        return {"current_project": self.updated_user["current_project"]}

    async def update_user_password(self, account_id, user: UpdateUserPassword) -> dict:
        """save a user's details into the user collection"""
        self.account_id_to_update = account_id
        self.user = user
        if self.user.new_password is not None:
            self.console_display = ConsoleDisplay()
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"update_upassword({self.account_id_to_update}) called"
                )
            try:
                self.update_response = await self.user_collection.update_one(
                    {"account_id": self.account_id_to_update},
                    {"$set": {"password": self.user.new_password}},
                )
            except Exception as e:
                self.console_display.show_exception_message(
                    message_to_show=f"Exception occured updating user password id was: {self.account_id_to_update}"
                )
                print(e)
                raise
            try:
                self.updated_user = await self.user_collection.find_one(
                    {"account_id": self.account_id_to_update}
                )
            except Exception as e:
                self.console_display.show_exception_message(
                    message_to_show=f"Exception occured retreiving updated user from the database _id was: {self.account_id_to_update}"
                )
                print(e)
                raise
        else:
            self.console_display.show_exception_message("Nothing to change")
            raise
        return users_saves_helper(self.updated_user)

    async def update_user_type(self, account_id, user: UpdateUserType) -> dict:
        """update a user's type (free / premium) into the user collection"""
        self.account_id_to_update = account_id
        self.user = user
        if self.user.user_type is not None:
            self.console_display = ConsoleDisplay()
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"update_type({self.account_id_to_update}) called"
                )
            try:
                self.update_response = await self.user_collection.update_one(
                    {"account_id": self.account_id_to_update},
                    {"$set": {"user_type": self.user.user_type}},
                )
            except Exception as e:
                self.console_display.show_exception_message(
                    message_to_show=f"Exception occured updating user type id was: {self.account_id_to_update}"
                )
                print(e)
                raise
            try:
                self.updated_user = await self.user_collection.find_one(
                    {"account_id": self.account_id_to_update}
                )
            except Exception as e:
                self.console_display.show_exception_message(
                    message_to_show=f"Exception occured retreiving updated user from the database _id was: {self.account_id_to_update}"
                )
                print(e)
                raise
        else:
            self.console_display.show_exception_message("Nothing to change")
            raise
        return users_saves_helper(self.updated_user)

    async def delete_user_details(self, id: str) -> dict:
        """delete a user's details from the user collection by document id"""
        self.id_to_delete = id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"delete_user_details({self.id_to_delete}) called"
            )
        try:
            self.delete_response = await self.user_collection.delete_one(
                {"_id": ObjectId(self.id_to_delete)}
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured delete user details from the database _id was: {self.id_to_delete}"
            )
            print(e)
            raise

        return self.delete_response.deleted_count

    async def delete_user_details_by_account_id(self, account_id: str) -> dict:
        """delete a user's details from the user collection"""
        self.account_id_to_delete = account_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"delete_user_details({self.account_id_to_delete}) called"
            )
        try:
            self.delete_response = await self.user_collection.delete_many(
                {"account_id": self.account_id_to_delete}
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured delete user details from the database account_id was: {self.account_id_to_delete}"
            )
            print(e)
            raise
        # now remove any documents belonging to the users
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"Removing documents for {self.account_id_to_delete}"
            )
        try:
            await self.tree_collection.delete_many(
                {"account_id": self.account_id_to_delete}
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured removing all documents for user account_id was: {self.account_id_to_delete}"
            )
            print(e)
            raise
        return self.delete_response.deleted_count

    async def delete_user_details(self, id: str) -> dict:
        """delete a user's details from the user collection"""
        self.id_to_delete = id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"delete_user_details({self.id_to_delete}) called"
            )
        try:
            self.delete_response = await self.user_collection.delete_one(
                {"_id": ObjectId(self.id_to_delete)}
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured delete user details from the database _id was: {self.id_to_delete}"
            )
            print(e)
            raise
        return self.delete_response.deleted_count

    async def check_if_user_exists(self, user_id: str) -> int:
        """return count of save documents in the user_collection for supplied user_id"""
        self.user_id = user_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"check_if_user_exists({self.user_id}) called"
            )
        try:
            self.user_count = await self.user_collection.count_documents(
                {"_id": ObjectId(self.user_id)}
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving user document count user_id was: {self.user_id}"
            )
            print(e)
            raise
        return self.user_count


class ProjectStorage:
    def __init__(self, collection_name):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
        self.database = self.client.fabulator
        self.project_collection = self.database.get_collection(collection_name)
        self.user_collection = self.database.get_collection("user_collection")
        self.tree_collection = self.database.get_collection("tree_collection")

    async def create_project(self, project=RetrieveProject) -> dict:
        # check if username already exists
        self.project = project
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"create_project({self.project.name}) called"
            )
        # create a new tree and store it
        try:
            self.tree_functions = TreeStorage("tree_collection")
            self.tree_id = await self.tree_functions.create_tree(
                account_id=self.project.owner_id, root_node_tag=self.project.name
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured creating new tree, owner_id was: {self.project.owner_id}"
            )
            print(e)
            raise
        # add the new tree to the projects object provided
        try:
            self.project.trees = set([self.tree_id])
            if DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"self.project.trees:{self.project.trees}"
                )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured adding tree: {self.save_response} to project, owner_id was: {self.project.owner_id}"
            )
            print(e)
            raise

        # create a new project document
        try:
            self.save_response = await self.project_collection.insert_one(
                jsonable_encoder(self.project)
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured saving project, owner_id was: {self.project.owner_id}"
            )
            print(e)
            raise
        # update the associated user document with the project_id
        try:
            self.update_response = await self.user_collection.update_one(
                {"account_id": self.project.owner_id},
                {"$push": {"projects": self.project.project_id}},
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured adding project, to user: {self.project.owner_id}"
            )
            print(e)
            raise

        try:
            self.new_project = await self.project_collection.find_one(
                {"_id": ObjectId(self.save_response.inserted_id)}
            )
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retreiving new user from the database _id was: {self.save_response.inserted_id}"
            )
            print(e)
            raise
        return project_saves_helper(self.new_project)

    async def get_project_details(self, account_id: str, project_id: str):
        """return the a user's details given their username - used for log in"""
        # have to have this in there to avoid event_loop_closed errors during testing
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
        self.database = self.client.fabulator
        self.user_collection = self.database.get_collection("user_collection")
        self.account_id = account_id
        self.project_id = project_id
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"get_project_details({self.account_id,self.project_id}) called"
            )
        try:
            user_deets = await self.user_collection.find_one(
                {"account_id": self.account_id}
            )
            if user_deets is not None:
                self.user_details = UserDetails(**user_deets)
            else:
                self.user_details = None
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving user details from the database account_id was: {self.account_id}"
            )
            print(e)
            raise
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"self.user_details.projects: {self.user_details.projects}"
            )
        # check that the user owns this project - if they don't return an error message can we raise an exception
        if project_id in self.user_details.projects:
            try:
                self.project_details = await self.project_collection.find_one(
                    {"project_id": self.project_id}
                )
                if DEBUG:
                    self.console_display.show_debug_message(
                        message_to_show=f"self.project_details: {self.project_details}"
                    )
            except Exception as e:
                self.console_display.show_exception_message(
                    message_to_show=f"Exception occured retrieving user details from the database username was: {self.project_id}"
                )
                print(e)
                raise
            return project_saves_helper(self.project_details)
        else:
            # return an error
            return project_errors_helper(
                {
                    "error": "Unable to retrieve project",
                    "message": "project does not belong to user",
                }
            )

    async def update_project_details(
        self,
        account_id: str,
        project_id: str,
        modified_date: datetime.datetime,
        project: UpdateProject,
    ):
        """update project details for a given project"""
        # have to have this in there to avoid event_loop_closed errors during testing
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
        self.database = self.client.fabulator
        self.user_collection = self.database.get_collection("user_collection")
        self.account_id = account_id
        self.project_update = project
        self.project_id = project_id
        self.modified_date = modified_date
        self.console_display = ConsoleDisplay()
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"update_project_details({self.account_id,self.project_id}) called"
            )
        try:
            user_deets = await self.user_collection.find_one(
                {"account_id": self.account_id}
            )
            if user_deets is not None:
                self.user_details = UserDetails(**user_deets)
            else:
                self.user_details = None
        except Exception as e:
            self.console_display.show_exception_message(
                message_to_show=f"Exception occured retrieving user details from the database account_id was: {self.account_id}"
            )
            print(e)
            raise
        if DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"self.user_details.projects: {self.user_details.projects}"
            )
        # check that the user owns this project - if they don't return an error message can we raise an exception
        if self.project_id in self.user_details.projects:
            try:
                if self.project_update.name:
                    self.update_details = await self.project_collection.update_one(
                        {"project_id": self.project_id},
                        {"$set": {"name": self.project_update.name}},
                    )
                if self.project_update.description:
                    self.update_details = await self.project_collection.update_one(
                        {"project_id": self.project_id},
                        {"$set": {"description": self.project_update.description}},
                    )
                if self.modified_date:
                    self.update_details = await self.project_collection.update_one(
                        {"project_id": self.project_id},
                        {"$set": {"modified_date": self.modified_date}},
                    )
                if DEBUG:
                    self.console_display.show_debug_message(
                        message_to_show=f"self.update_details: {self.update_details}"
                    )
            except Exception as e:
                self.console_display.show_exception_message(
                    message_to_show=f"Exception occured updating user details from the database username was: {self.project_id}"
                )
                print(e)
                raise
            try:
                self.project_details = await self.project_collection.find_one(
                    {"project_id": self.project_id}
                )
                if DEBUG:
                    self.console_display.show_debug_message(
                        message_to_show=f"self.project_details: {self.project_details}"
                    )
            except Exception as e:
                self.console_display.show_exception_message(
                    message_to_show=f"Exception occured retrieving user details from the database username was: {self.project_id}"
                )
                print(e)
                raise
            return project_saves_helper(self.project_details)
        else:
            # return an error
            return project_errors_helper(
                {
                    "error": "Unable to update project",
                    "message": "project does not belong to user",
                }
            )

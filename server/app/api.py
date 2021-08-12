from logging import exception
import os
import app.config  # loads the load_env lib to access .env file
import app.helpers as helpers
from treelib import Tree
from fastapi import FastAPI, HTTPException, Body
from typing import Optional
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    SubTree,
    RequestAddSchema,
    RequestUpdateSchema,
    NodePayload,
    UserDetails,
    ResponseModel
)

from .database import (
    TreeStorage,
    UserStorage
)

# set DEBUG flag

DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
console_display = helpers.ConsoleDisplay()

if DEBUG:
    console_display.show_debug_message(
        message_to_show=f"Environment variable DEBUG is :{DEBUG}")
    console_display.show_debug_message(
        message_to_show=f"Environment variable DEBUG is type :{type(DEBUG)}")

# ------------------------
#      FABULATOR
# ------------------------
app = FastAPI()
version = "0.0.7"

origins = [
    "http://localhost:8000",
    "localhost:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ------------------------
#     API Helper Class
# ------------------------


class RoutesHelper():
    """ helper class containg API route utility functions"""

    def __init__(self):
        # probably create an instance of db_storeage
        self.db_storage = TreeStorage(collection_name="tree_collection")
        self.user_storage = UserStorage(collection_name="user_collection")
        self.console_display = helpers.ConsoleDisplay()
        self.DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')

    async def account_id_exists(self, account_id):
        self.account_id = account_id
        if self.DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"account_id_exists({self.account_id}) called")
        try:
            number_saves = await self.db_storage.number_of_saves_for_account(account_id=self.account_id)
            if self.DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"number_of_saves_for_account returned: {number_saves}")
            if number_saves > 0:
                return True
            else:
                return False
        except Exception as e:
            console_display.show_exception_message(
                message_to_show=f"Error occured retrieving count of saves for {self.account_id}")
            print(e)
            raise HTTPException(
                status_code=500, detail=f"Error occured retrieving count of save documents for {account_id} : {e}")

    async def save_document_exists(self, document_id):
        self.document_id = document_id
        if self.DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"save_document_exists({self.document_id}) called")
        try:
            saves_count = await self.db_storage.check_if_document_exists(save_id=self.document_id)
            if self.DEBUG:
                console_display.show_debug_message(
                    message_to_show=f"check_if_document_exists returned: {saves_count}")
            if saves_count > 0:
                return True
            else:
                return False
        except Exception as e:
            console_display.show_exception_message(
                message_to_show=f"Error occured retrieving count of saves for {self.document_id}")
            print(e)
            raise HTTPException(
                status_code=500, detail=f"Error occured retrieving count of save documents for document save_id: {self.document_id}: {e}")

    async def user_document_exists(self, user_id):
        self.user_id = user_id
        if self.DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"user_document_exists({self.user_id}) called")
        try:
            document_count = await self.user_storage.check_if_user_exists(user_id=self.user_id)
            if self.DEBUG:
                console_display.show_debug_message(
                    message_to_show=f"check_if_document_exists returned: {self.user_id}")
            if document_count > 0:
                return True
            else:
                return False
        except Exception as e:
            console_display.show_exception_message(
                message_to_show=f"Error occured retrieving user document for {self.user_id}")
            print(e)
            raise HTTPException(
                status_code=500, detail=f"Error occured retrieving count of user documents user_id: {self.user_id}: {e}")

# ------------------------
#       API Routes
# ------------------------

# ------------------------
#         Misc
# ------------------------


def initialise_tree():
    """ Create a new Tree and return it"""
    global tree
    tree = Tree()
    return tree


@ app.get("/")
async def get() -> dict:
    """ Return the API version """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            message_to_show="debug message - Get() Called")
    return ResponseModel(data={"version": version}, message="Success")

# ------------------------
#         Trees
# ------------------------


@ app.get("/trees/root")
async def get_tree_root() -> dict:
    """ return the id of the root node on current tree if there is one"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_tree_root() called")
    try:
        root_node = tree.root
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured calling tree.root on current tree")
        print(e)
        raise
    data = root_node
    return ResponseModel(data={"root": data}, message="Success")


@ app.get("/trees/{account_id}/{id}")
async def prune_subtree(account_id: str, id: str) -> dict:
    """ cut a node & children specified by supplied id"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    # first check if the account_id exists - if it doesn't do nothing
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        if DEBUG:
            routes_helper.console_display.show_debug_message(
                f"prune_subtree({account_id},{id}) called")
        if tree.contains(id):
            try:
                response = tree.remove_subtree(id)
                message = "Success"
            except Exception as e:
                routes_helper.console_display.show_exception_message(
                    message_to_show="Error occured removing a subtree from the working tree. id: {id}")
                print(e)
                raise
            try:
                db_storage = TreeStorage(
                    collection_name="tree_collection")
                await db_storage.save_working_tree(tree=tree, account_id=account_id)
            except Exception as e:
                routes_helper.console_display.show_exception_message(
                    message_to_show="Error occured saving the working tree to the database after delete.")
                print(e)
                raise
        else:
            raise HTTPException(
                status_code=404, detail="Node not found in current tree")
        return ResponseModel(response, message)
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")


@ app.post("/trees/{account_id}/{id}")
async def graft_subtree(account_id: str, id: str, request: SubTree = Body(...)) -> dict:
    """ paste a subtree & beneath the node specified"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    # first check if the account_id exists - if it doesn't do nothing
    routes_helper = RoutesHelper()
    db_storage = TreeStorage(collection_name="tree_collection")
    if await routes_helper.account_id_exists(account_id=account_id):
        if DEBUG:
            routes_helper.console_display.show_debug_message(
                f"graft_subtree({account_id},{id}) called")
        if tree.contains(id):
            # turn dict object into a Tree
            try:
                sub_tree = db_storage.build_tree_from_dict(
                    tree_dict=request.sub_tree)
            except Exception as e:
                routes_helper.console_display.show_exception_message(
                    message_to_show=f"Error occured building the subtree from the request dict object. {e}")
                raise HTTPException(
                    status_code=500, detail=f"Error occured building the subtree from the request dict object. {e}")
            try:
                if DEBUG:
                    tree.save2file(
                        'dump.txt', line_type=u'ascii-ex', idhidden=False)
                tree.paste(nid=id, new_tree=sub_tree, deep=False)
                message = "Success"
            except Exception as e:
                routes_helper.console_display.show_exception_message(
                    message_to_show=f"Error occured grafting the subtree into the working tree. id: {id} {e}")
                raise
            try:
                await db_storage.save_working_tree(tree=tree, account_id=account_id)
            except Exception as e:
                routes_helper.console_display.show_exception_message(
                    message_to_show="Error occured saving the working tree to the database after paste action.{e}")
                raise
        else:
            raise HTTPException(
                status_code=404, detail="Node not found in current tree")
        return ResponseModel("Graft complete", message)
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")

# ------------------------
#          Nodes
# ------------------------


@ app.get("/nodes/{account_id}")
async def get_all_nodes(account_id: str, filterval: Optional[str] = None) -> dict:
    """ Get a list of all the nodes in the working tree"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        if DEBUG:
            console_display.show_debug_message(
                message_to_show=f"get_all_nodes({filterval}) called")
        if filterval:
            data = []
            for node in tree.all_nodes():
                if filterval in node.data.tags:
                    data.append(node)
            if DEBUG:
                console_display.show_debug_message(
                    message_to_show=f"Nodes filtered on {filterval}")
        else:
            try:
                tree.show(line_type="ascii-em")
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show="Error occured calling tree.show on tree")
                raise HTTPException(
                    status_code=500, detail="Error occured calling tree.show on tree")
            data = tree.all_nodes()
        return ResponseModel(data=data, message="Success")
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")


@ app.get("/nodes/{account_id}/{id}")
async def get_a_node(account_id: str, id: str) -> dict:
    """ Return a node specified by supplied id"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        if DEBUG:
            console_display.show_debug_message(
                message_to_show=f"get_a_node({id}) called")
            console_display.show_debug_message(
                message_to_show=f"node: {tree.get_node(id)}")
        if tree.contains(id):
            node = tree.get_node(id)
        else:
            raise HTTPException(
                status_code=404, detail="Node not found in current tree")
        return ResponseModel(node, "Success")
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")


@ app.post("/nodes/{account_id}/{name}")
async def create_node(account_id: str, name: str, request: RequestAddSchema = Body(...)) -> dict:
    """ Add a node to the working tree using name supplied """
    # todo: check for pre-existence of account
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    # map the incoming fields from the https request to the fields required by the treelib API
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"create_node({account_id},{name}) called")
    global tree
    try:
        request = jsonable_encoder(request)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured encoding request with jsonable_encoder")
        print(e)
        raise HTTPException(
            status_code=500, detail="Error occured encoding request with jsonable_encoder: {e}")

    node_payload = NodePayload()

    if request["description"]:
        node_payload.description = request["description"]
    if request["next"]:
        node_payload.next = request["next"]
    if request["previous"]:
        node_payload.previous = request["previous"]
    if request["text"]:
        node_payload.text = request["text"]
    if request["tags"]:
        node_payload.tags = request["tags"]

    if request["parent"]:
        # check that the parent node exists before updating
        if tree.contains(request["parent"]):
            try:
                new_node = tree.create_node(
                    name, parent=request["parent"], data=node_payload)
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show="Error occured adding child node to working tree")
                console_display.show_exception_message(
                    message_to_show=f"request['name']:{request['name']}, data:{node_payload}, request['parent']:{request['parent']}")
                print(e)
                raise HTTPException(
                    status_code=500, detail=f"request['name']:{request['name']}, data:{node_payload}, request['parent']:{request['parent']}:{e} ")
        else:
            raise HTTPException(
                status_code=422, detail=f"Parent {request['parent']} is missing from tree")
    else:
        # No parent so check if we already have a root
        if tree.root == None:
            try:
                new_node = tree.create_node(
                    name, data=node_payload)
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show="Error occured adding root node to working tree")
                console_display.show_exception_message(
                    message_to_show=f"request['name']:{request['name']}, data:{node_payload}")
                print(e)
                raise HTTPException(
                    status_code=500, detail=f"request['name']:{request['name']}, data:{node_payload}:{e}")
        else:
            raise HTTPException(
                status_code=422, detail="Tree already has a root node")
    try:
        db_storage = TreeStorage(collection_name="tree_collection")
        save_result = await db_storage.save_working_tree(tree=tree, account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured saving the working tree to the database")
        print(e)
        raise HTTPException(
            status_code=500, detail=f"Error occured saving the working tree to the database: {e}")
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"mongo save: {save_result}")
    return ResponseModel({"node": new_node, "object_id": save_result}, "Success")


@ app.put("/nodes/{account_id}/{id}")
async def update_node(account_id: str, id: str, request: RequestUpdateSchema = Body(...)) -> dict:
    """ Update a node in the working tree identified by supplied id"""
    # generate a new id for the node if we have a parent
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    if DEBUG:
        console_display.show_debug_message(
            f"update_node({account_id},{id}) called")
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        # test if node exists
        if tree.contains(id):
            node_payload = NodePayload(description=request.description,
                                       previous=request.previous, next=request.next, tags=request.tags, text=request.text)
            if request.name:
                # if a parent is specified in the request ensure that it exists
                if request.parent:
                    if tree.contains(request.parent):
                        try:
                            tree.update_node(
                                id, _tag=request.name, data=node_payload, parent=request.parent)
                        except Exception as e:
                            console_display.show_exception_message(
                                message_to_show="Error occured updating node in the working tree")
                            console_display.show_exception_message(
                                message_to_show=f"id:{id}, request.name:{request.name}, data:{node_payload}")
                            print(e)
                            raise
                    else:
                        raise HTTPException(
                            status_code=422, detail=f"Parent {request.parent} is missing from tree")
                else:
                    try:
                        tree.update_node(
                            id, _tag=request.name, data=node_payload)
                    except Exception as e:
                        console_display.show_exception_message(
                            message_to_show="Error occured updating node in the working tree")
                        console_display.show_exception_message(
                            message_to_show=f"id:{id}, request.name:{request.name}, data:{node_payload}")
                        print(e)
                        raise

            else:
                if request.parent:
                    if tree.contains(request.parent):
                        try:
                            tree.update_node(
                                id, data=node_payload, parent=request.parent)
                        except Exception as e:
                            console_display.show_exception_message(
                                message_to_show="Error occured updating node in the working tree")
                            console_display.show_exception_message(
                                message_to_show=f"id:{id}, request.name:{request.name}, data:{node_payload}")
                            print(e)
                            raise
                    else:
                        raise HTTPException(
                            status_code=422, detail=f"Parent {request.parent} is missing from tree")

            try:
                db_storage = TreeStorage(collection_name="tree_collection")
                save_result = await db_storage.save_working_tree(tree=tree, account_id=account_id)
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show="Error occured saving the working_tree to the database")
                print(e)
                raise

            if DEBUG:
                console_display.show_debug_message(
                    message_to_show=f"save_result: {save_result}")
            return ResponseModel({"object_id": save_result}, "Success")
        else:
            raise HTTPException(
                status_code=404, detail="Node not found in current tree")
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")


@ app.delete("/nodes/{account_id}/{id}")
async def delete_node(id: str, account_id: str = None) -> dict:
    """ Delete a node from the working tree identified by supplied id """
    # remove the node with the supplied id
    # todo: probably want to stash the children somewhere first in a sub tree for later use
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    routes_helper = RoutesHelper()
    global tree
    if await routes_helper.account_id_exists(account_id=account_id):
        if DEBUG:
            console_display.show_debug_message(
                f"delete_node({account_id},{id}) called")
        if tree.contains(id):
            try:
                response = tree.remove_node(id)
                message = "Success"
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show="Error occured removing a node from the working tree. id: {id}")
                print(e)
                raise
            else:
                try:
                    db_storage = TreeStorage(collection_name="tree_collection")
                    await db_storage.save_working_tree(tree=tree, account_id=account_id)
                except Exception as e:
                    console_display.show_exception_message(
                        message_to_show="Error occured saving the working tree to the database after delete.")
                    print(e)
                    raise
        else:
            raise HTTPException(
                status_code=404, detail="Node not found in current tree")
        return ResponseModel(response, message)
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")


# ------------------------
#          Loads
# ------------------------


@ app.get("/loads/{account_id}")
async def get_latest_save(account_id: str) -> dict:
    """ Return the latest saved tree in the db collection"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_latest_save({account_id} called")
    global tree
    # check to see if the account_id exists in the db
    db_storage = TreeStorage(collection_name="tree_collection")
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        try:
            tree = await db_storage.load_latest_into_working_tree(account_id=account_id)
        except Exception as e:
            console_display.show_exception_message(
                message_to_show="Error occured loading latest save into working tree")
            print(e)
            raise HTTPException(
                status_code=500, detail=f"Error occured loading latest save into working tree: {e}")
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to locate saves for account_id:{account_id}")

    return ResponseModel(jsonable_encoder(tree), "Success")


@ app.get("/loads/{account_id}/{save_id}")
async def get_a_save(account_id: str, save_id: str) -> dict:
    """ Return the specfied saved tree in the db collection"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_a_save({account_id}/{save_id} called")
    global tree
    db_storage = TreeStorage(collection_name="tree_collection")
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        if await routes_helper.save_document_exists(document_id=save_id):
            try:
                db_storage = TreeStorage(collection_name="tree_collection")
                tree = await db_storage.load_save_into_working_tree(save_id=save_id)
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show=f"Error occured loading specified save into working tree. save_id:{save_id}")
                print(e)
                raise HTTPException(
                    status_code=500, detail=f"Error occured loading specified save into working tree. save_id: {save_id}: {e}")
        else:
            raise HTTPException(
                status_code=404, detail=f"Unable to retrieve save document with id: {save_id}")
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")

    return ResponseModel(jsonable_encoder(tree), "Success")

# ------------------------
#          Saves
# ------------------------


@ app.get("/saves/{account_id}")
async def get_all_saves(account_id: str) -> dict:
    """ Return a dict of all the trees saved in the db collection """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    try:
        db_storage = TreeStorage(collection_name="tree_collection")
        all_saves = await db_storage.list_all_saved_trees(account_id=account_id)
        # all_saves = await list_all_saved_trees(account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured loading all saves")
        raise HTTPException(
            status_code=500, detail="Error occured loading all saves: {e}")
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_all_saves{account_id} called")

    return ResponseModel(jsonable_encoder(all_saves), "Success")


@ app.delete("/saves/{account_id}")
async def delete_saves(account_id: str) -> dict:
    """ Delete all saves from the db trees collection """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            f"delete_saves({account_id},{id}) called")
    global tree
    try:
        db_storage = TreeStorage(collection_name="tree_collection")
        delete_result = await db_storage.delete_all_saves(account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured deleting  all saves for account_id:{account_id}")
        print(e)
        raise
    result = ResponseModel(delete_result, "Documents removed.")
    return result


# ------------------------
#          Users
# ------------------------

@ app.post("/users")
async def save_user(request: UserDetails = Body(...)) -> dict:
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    """ save 
    a user to users collection """
    if DEBUG:
        console_display.show_debug_message(
            f"save_user({request}) called")
    try:
        db_storage = UserStorage(collection_name="user_collection")
        save_result = await db_storage.save_user_details(user=request)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured saving user details:{account_id}")
        raise
    result = ResponseModel(save_result, "new user added")
    return result


@ app.get("/users/{id}")
async def get_user(id: str) -> dict:
    """ get a user's details from users collection """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            f"get_user({id}) called")
    routes_helper = RoutesHelper()
    if await routes_helper.user_document_exists(user_id=id):
        try:
            db_storage = UserStorage(collection_name="user_collection")
            get_result = await db_storage.get_user_details_by_id(id=id)
        except Exception as e:
            console_display.show_exception_message(
                message_to_show="Error occured getting user details:{id}")
            raise
        result = ResponseModel(get_result, "user found")
        return result
    else:
        raise HTTPException(
            status_code=404, detail=f"No user record found for id:{id}")


@ app.put("/users/{id}")
async def save_user(id: str, request: UserDetails = Body(...)) -> dict:
    """ update a user document """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            f"update_user({request}) called")
    routes_helper = RoutesHelper()
    if await routes_helper.user_document_exists(user_id=id):
        try:
            db_storage = UserStorage(collection_name="user_collection")
            update_result = await db_storage.update_user_details(id=id, user=request)
        except Exception as e:
            console_display.show_exception_message(
                message_to_show="Error occured updating user details:{account_id}")
            raise
        result = ResponseModel(update_result, f"user {id} updated")
        return result
    else:
        raise HTTPException(
            status_code=404, detail=f"No user record found for id:{id}")


@ app.delete("/users/{id}")
async def delete_user(id: str) -> dict:
    """ delete a user from users collection """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            f"delete_user({id}) called")
    routes_helper = RoutesHelper()
    if await routes_helper.user_document_exists(user_id=id):
        try:
            db_storage = UserStorage(collection_name="user_collection")
            delete_result = await db_storage.delete_user_details(id=id)
        except Exception as e:
            console_display.show_exception_message(
                message_to_show="Error occured deleteing user details:{id}")
            raise
        result = ResponseModel(delete_result, "new user added")
        return result
    else:
        raise HTTPException(
            status_code=404, detail=f"No user record found for id:{id}")

# Create global tree & subtrees
tree = initialise_tree()
sub_tree = tree

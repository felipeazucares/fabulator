import os
import app.config  # loads the load_env lib to access .env file
import app.helpers as helpers
from treelib import Tree
from fastapi import FastAPI, HTTPException, Body
from typing import Optional
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    RequestAddSchema,
    RequestUpdateSchema,
    NodePayload,
    UserDetails,
    ResponseModel,
    ErrorResponseModel
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
version = "0.0.1"

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
#       API Routes
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


@ app.get("/tree/root")
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


@ app.get("/nodes/")
async def get_all_nodes(filterval: Optional[str] = None) -> dict:
    """ Get a list of all the nodes in the working tree"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_all_nodes({filterval}) called")
    if filterval:
        data = []
        for node in tree.all_nodes():
            if filterval in node.data.tags:
                data.append(node)
                # todo: how do we deal with no nodes being returned?
                # todo: maybe return the count as well as the nodes?
        if DEBUG:
            console_display.show_debug_message(
                message_to_show=f"Nodes filtered on {filterval}")
    else:
        try:
            tree.show(line_type="ascii-em")
        except Exception as e:
            console_display.show_exception_message(
                message_to_show="Error occured calling tree.show on tree")
            raise
        data = tree.all_nodes()
    return ResponseModel(data=data, message="Success")


@ app.get("/nodes/{id}")
async def get_a_node(id: str) -> dict:
    """ Return a node specified by supplied id"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
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
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_all_saves{account_id} called")

    return ResponseModel(jsonable_encoder(all_saves), "Success")


@ app.get("/loads/{account_id}")
async def get_latest_save(account_id: str) -> dict:
    """ Return the latest saved tree in the db collection"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    try:
        db_storage = TreeStorage(collection_name="tree_collection")
        tree = await db_storage.load_latest_into_working_tree(account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured loading latest save into working tree")
        print(e)
        raise
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_latest_save({account_id} called")

    return ResponseModel(jsonable_encoder(tree), "Success")


@ app.get("/loads/{account_id}/{save_id}")
async def get_a_save(account_id: str, save_id: str) -> dict:
    """ Return the specfied saved tree in the db collection"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    try:
        db_storage = TreeStorage(collection_name="tree_collection")
        tree = await db_storage.load_save_into_working_tree(save_id=save_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show=f"Error occured loading specified save into working tree. save_id:{save_id}")
        print(e)
        raise
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_a_save({account_id}/{save_id} called")

    return ResponseModel(jsonable_encoder(tree), "Success")


@ app.post("/nodes/{account_id}/{name}")
async def create_node(account_id: str, name: str, request: RequestAddSchema = Body(...)) -> dict:
    """ Add a node to the working tree using name supplied """
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
        raise
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
        try:
            new_node = tree.create_node(
                name, parent=request["parent"], data=node_payload)
        except Exception as e:
            console_display.show_exception_message(
                message_to_show="Error occured adding child node to working tree")
            console_display.show_exception_message(
                message_to_show=f"request['name']:{request['name']}, data:{node_payload}, request['parent']:{request['parent']}")
            print(e)
            raise

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
                raise
        else:
            return ErrorResponseModel("Unable to add node", 422, "Tree already has a root node")
    try:
        db_storage = TreeStorage(collection_name="tree_collection")
        save_result = await db_storage.save_working_tree(tree=tree, account_id=account_id)

        # save_result = await save_working_tree(tree=tree, account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured saving the working tree to the database")
        print(e)
        raise
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

    node_payload = NodePayload(description=request.description,
                               previous=request.previous, next=request.next, tags=request.tags, text=request.text)
    if request.name:
        try:
            update_node = tree.update_node(
                id, _tag=request.name, data=node_payload)
        except Exception as e:
            console_display.show_exception_message(
                message_to_show="Error occured updating node in the working tree")
            console_display.show_exception_message(
                message_to_show=f"id:{id}, request.name:{request.name}, data:{node_payload}")
            print(e)
            raise
    else:
        try:
            update_node = tree.update_node(
                id, data=node_payload)
        except Exception as e:
            console_display.show_exception_message(
                message_to_show="Error occured updating node in the working tree")
            console_display.show_exception_message(
                message_to_show=f"id:{id}, request.name:{request.name}, data:{node_payload}")
            print(e)
            raise
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
            message_to_show=f"save_result: {update_node}")
    return ResponseModel({"object_id": save_result}, "Success")


@ app.delete("/nodes/{account_id}/{id}")
async def delete_node(id: str, account_id: str = None) -> dict:
    """ Delete a node from the working tree identified by supplied id """
    # remove the node with the supplied id
    # todo: probably want to stash the children somewhere first in a sub tree for later use
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            f"delete_node({account_id},{id}) called")
    global tree
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
        message = "No nodes removed"
        response = 0
    return ResponseModel(response, message)


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
        # save_result = await db_storage.save_working_tree(tree=tree, account_id=account_id)
        delete_result = await db_storage.delete_all_saves(account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured deleting  all saves for account_id:{account_id}")
        print(e)
        raise
    result = ResponseModel(delete_result, "Documents removed.")
    return result


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
    try:
        db_storage = UserStorage(collection_name="user_collection")
        get_result = await db_storage.get_user_details_by_id(id=id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured getting user details:{id}")
        raise
    result = ResponseModel(get_result, "user found")
    return result


@ app.put("/users/{id}")
async def save_user(id: str, request: UserDetails = Body(...)) -> dict:
    """ update a user document """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            f"update_user({request}) called")
    try:
        db_storage = UserStorage(collection_name="user_collection")
        update_result = await db_storage.update_user_details(id=id, user=request)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured updating user details:{account_id}")
        raise
    result = ResponseModel(update_result, f"user {id} updated")
    return result


@ app.delete("/users/{id}")
async def delete_user(id: str) -> dict:
    """ delete a user from users collection """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            f"delete_user({id}) called")
    try:
        db_storage = UserStorage(collection_name="user_collection")
        delete_result = await db_storage.delete_user_details(id=id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured deleteing user details:{id}")
        raise
    result = ResponseModel(delete_result, "new user added")
    return result

# Create tree
tree = initialise_tree()

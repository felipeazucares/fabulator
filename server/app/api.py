
import os
import hashlib
from app.helpers import ConsoleDisplay
import app.config  # loads the load_env lib to access .env file
import app.helpers as helpers
from treelib import Tree, Node
from fastapi import FastAPI, Body
from typing import Optional
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    ErrorResponseModel,
    RequestAddSchema,
    RequestUpdateSchema,
    NodePayload,
    ResponseModel,
    UserDetails
)

from .database import (
    DatabaseStorage,
    save_working_tree,
    list_all_saved_trees,
    delete_all_saves,
    load_latest_into_working_tree
)

# set DEBUG flag

DEBUG = os.getenv(key="DEBUG")
console_display = helpers.ConsoleDisplay()

# ------------------------
#      FABULATOR
# ------------------------
app = FastAPI()
version = "v.0.0.1"

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
#    Dummy user details
# ------------------------

# initialise dummy user details
username = "felipeazucares"
firstname = "Philip"
surname = "Suggars"
username_hash = hashlib.sha256(username.encode('utf-8')).hexdigest()

user = UserDetails(
    name={"firstname": firstname, "surname": surname}, username="felipeazucares", account_id=username_hash)

# ------------------------
#       API Routes
# ------------------------


def initialise_tree():
    """ Create a new Tree and return it"""
    global tree
    tree = Tree()
    return tree


@ app.get("/account")
async def get_account_id(username) -> dict:
    """ Return the API version """
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"Get_account_id ({username}) Called")
        console_display.show_debug_message(
            message_to_show=f"Using dummy vars for firstname and lastname")
    firstname = "Philip"
    surname = "Suggars"
    username_hash = hashlib.sha256(username.encode('utf-8')).hexdigest()
    data = UserDetails(
        name={"firstname": firstname, "surname": surname}, username="username", account_id=username_hash)

    return ResponseModel(data, "Success")


@ app.get("/")
async def get() -> dict:
    """ Return the API version """
    if DEBUG:
        console_display.show_debug_message(
            message_to_show="debug message - Get() Called")
    return {"message": f"Fabulator {version}"}


@ app.get("/tree/root")
async def get_tree_root() -> dict:
    """ return the id of the root node on current tree if there is one"""
    global tree
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
    return ResponseModel(data, "Success")


@ app.get("/nodes/")
async def get_all_nodes(filterval: Optional[str] = None) -> dict:
    """ Get a list of all the nodes in the working tree"""
    global tree
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
            print(e)
            raise
        data = tree.all_nodes()
    return ResponseModel(data, "Success")


@ app.get("/nodes/{id}")
async def get_a_node(id: str) -> dict:
    """ Return a node specified by supplied id"""
    global tree
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_a_node({id}) called")
    return ResponseModel(tree.get_node(id), "Success")


@ app.get("/saves/{account_id}")
async def get_all_saves(account_id: str) -> dict:
    """ Return a dict of all the trees saved in the db collection """
    try:
        db_storage = DatabaseStorage(collection_name="tree_collection")
        all_saves = await db_storage.list_all_saved_trees(account_id=account_id)
        # all_saves = await list_all_saved_trees(account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured loading all saves")
        print(e)
        e
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_all_saves{account_id} called")

    return ResponseModel(jsonable_encoder(all_saves), "Success")


@ app.get("/load/{account_id}")
async def get_latest_save(account_id: str) -> dict:
    """ Return the latest saved tree in the db collection"""
    global tree
    try:
        tree = await load_latest_into_working_tree(account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured loading latest save into working tree")
        print(e)
        raise
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_latest_save({account_id} called")

    return ResponseModel(jsonable_encoder(tree), "Success")


@ app.post("/nodes/{account_id}/{name}")
async def create_node(account_id: str, name: str, request: RequestAddSchema = Body(...)) -> dict:
    """ Add a node to the working tree using name supplied """
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
        db_storage = DatabaseStorage(collection_name="tree_collection")
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
    return ResponseModel(new_node, "Success")


@ app.put("/nodes/{account_id}/{id}")
async def update_node(account_id: str, id: str, request: RequestUpdateSchema = Body(...)) -> dict:
    """ Update a node in the working tree identified by supplied id"""
    # generate a new id for the node if we have a parent
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
        await save_working_tree(tree=tree, account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured saving the working_tree to the database")
        print(e)
        raise

    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"updated node: {update_node}")
    return ResponseModel(update_node, "Success")


@ app.delete("/nodes/{account_id}/{id}")
async def delete_node(id: str, account_id: str = None) -> dict:
    """ Delete a node from the working tree identified by supplied id """
    # remove the node with the supplied id
    # todo: probably want to stash the children somewhere first in a sub tree for later use
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
                await save_working_tree(tree=tree, account_id=account_id)
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
    if DEBUG:
        console_display.show_debug_message(
            f"delete_saves({account_id},{id}) called")
    global tree
    try:
        db_storage = DatabaseStorage(collection_name="tree_collection")
        # save_result = await db_storage.save_working_tree(tree=tree, account_id=account_id)
        delete_result = await db_storage.delete_all_saves(account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured updating node in the working tree - account_id:{account_id}")
        print(e)
        raise
    result = ResponseModel(delete_result, "Documents removed.")
    return result


# Create tree
tree = initialise_tree()

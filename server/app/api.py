
import sys
import os
import hashlib
import app.config  # loads the load_env lib to access .env file
from treelib import Tree
from fastapi import FastAPI, Body
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    RequestAddSchema,
    RequestUpdateSchema,
    NodePayload,
    ResponseModel,
    UserDetails
)

from .database import (
    save_working_tree,
    list_all_saved_trees,
    delete_all_saves,
    load_latest_into_working_tree
)

# set DEBUG flag

DEBUG = os.getenv(key="DEBUG")

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


@ app.get("/")
async def get() -> dict:
    """ Return the API version """
    if DEBUG:
        print(f"get()")
    return {"message": f"Fabulator {version}"}


@ app.get("/nodes/")
async def get_all_nodes() -> dict:
    """ Get a list of all the nodes in the working tree"""
    global tree
    if DEBUG:
        print(f"get_all_nodes()")
    try:
        tree.show(line_type="ascii-em")
    except Exception as e:
        print("Error occured calling tree.show on tree.")
        print(e)
        sys.exit(1)
    return {"code": 200, "data": [tree.all_nodes()], "message": "Success"}


@ app.get("/nodes/{id}")
async def get_a_node(id: str) -> dict:
    """ Return a node specified by supplied id"""
    global tree
    if DEBUG:
        print(f"get_a_node()")
        print(f"id:{id}")
    return ResponseModel(tree.get_node(id), "Success")


@ app.get("/saves/{account_id}")
async def get_all_saves(account_id: str) -> dict:
    """ Return a dict of all the trees saved in the db collection """
    try:
        all_saves = await list_all_saved_trees(account_id=account_id)
    except Exception as e:
        print("Error occured loading all saves")
        print(e)
        sys.exit(1)
    if DEBUG:
        print(f"get_all_saves()")
        print(f"all_saves:{all_saves}")

    return ResponseModel(jsonable_encoder(all_saves), "Success")


@ app.get("/save/{account_id}")
async def get_latest_save(account_id: str) -> dict:
    """ Return the latest saved tree in the db collection"""
    global tree
    try:
        tree = await load_latest_into_working_tree(account_id=account_id)
    except Exception as e:
        print("Error occured loading latest save into working tree")
        print(e)
        sys.exit(1)
    if DEBUG:
        print(f"get_latest_save()")
        print(f"latest:{tree}")

    return ResponseModel(jsonable_encoder(tree), "Success")


@ app.post("/nodes/{account_id}/{name}")
async def create_node(account_id: str, name: str, request: RequestAddSchema = Body(...)) -> dict:
    """ Add a node to the working tree using name supplied """
    # map the incoming fields from the https request to the fields required by the treelib API
    global tree
    try:
        request = jsonable_encoder(request)
    except Exception as e:
        print("Error occured encoding request with jsonable_encoder")
        print(e)
        sys.exit(1)
    if DEBUG:
        print(f"create_node())")
        print(f"req: {request}")
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
            print("Error occured adding child node to working tree")
            print(
                "request['name']:{request['name']}, data:{node_payload}, request['parent']:{request['parent']}")
            print(e)
            sys.exit(1)

    else:
        # No parent so check if we already have a root
        if tree.root == None:
            try:
                new_node = tree.create_node(
                    name, data=node_payload)
            except Exception as e:
                print("Error occured adding root node to working tree")
                print("request['name']:{request['name']}, data:{node_payload}")
                print(e)
                sys.exit(1)
        else:
            return {"message": "Tree already has a root node"}
    try:
        save_result = await save_working_tree(tree=tree, account_id=account_id)
    except Exception as e:
        print("Error occured saving the working tree to the database")
        print(e)
        sys.exit(1)
    if DEBUG:
        print(f"mongo save: {save_result}")
    return ResponseModel(new_node, "Success")


@ app.put("/nodes/{account_id}/{id}")
async def update_node(account_id: str, id: str, request: RequestUpdateSchema = Body(...)) -> dict:
    """ Update a node in the working tree identified by supplied id"""
    # generate a new id for the node if we have a parent
    global tree
    if DEBUG:
        print(f"req: {request}")

    node_payload = NodePayload(description=request.description,
                               previous=request.previous, next=request.next, tags=request.tags, text=request.text)
    if request.name:
        try:
            update_node = tree.update_node(
                id, _tag=request.name, data=node_payload)
        except Exception as e:
            print("Error occured updating node in the working tree")
            print("id:{id}, request.name:{request.name}, data:{data}")
            print(e)
            sys.exit(1)
    else:
        try:
            update_node = tree.update_node(
                id, data=node_payload)
        except Exception as e:
            print("Error occured updating node in the working tree")
            print("id:{id}, request.name:{request.name}, data:{data}")
            print(e)
            sys.exit(1)
    try:
        await save_working_tree(tree=tree, account_id=account_id)
    except Exception as e:
        print("Error occured saving the working_tree to the database")
        print(e)
        sys.exit(1)

    if DEBUG:
        print(f"updated node: {update_node }")
    return ResponseModel(update_node, "Success")


@ app.delete("/nodes/{account_id}/{id}/")
async def delete_node(id: str, account_id) -> dict:
    """ Delete a node from the working tree identified by supplied id """
    # remove the node with the supplied id
    # todo: probably want to stash the children somewhere first in a sub tree for later use
    global tree
    try:
        response = tree.remove_node(id)
    except Exception as e:
        print("Error occured removing a node from the working tree.")
        print("id:{id}")
        print(e)
        sys.exit(1)
    try:
        await save_working_tree(tree=tree, account_id=account_id)
    except Exception as e:
        print("Error occured saving the working tree to the database after delete.")
        print("tree:{tree}")
        print(e)
        sys.exit(1)
    return ResponseModel(response, "Documents Deleted")


@ app.delete("/saves/{account_id}")
async def delete_node(account_id: str) -> dict:
    """ Delete all saves from the db trees collection """
    global tree
    try:
        delete_result = await delete_all_saves(account_id=account_id)
    except Exception as e:
        print("Error occured updating node in the working tree.")
        print("id:{account_id}")
        print(e)
        sys.exit(1)
    result = ResponseModel(delete_result, "Documents removed.")
    return result


# Create tree
tree = initialise_tree()

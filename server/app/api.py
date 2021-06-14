
import motor.motor_asyncio
from typing import Optional
from treelib import Tree
from fastapi import FastAPI, Body, APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from bson.objectid import ObjectId
from pydantic import BaseModel, Field


from .models import (
    RequestAddSchema,
    RequestUpdateSchema,
    NodePayload,
    ResponseModel,
    ErrorResponseModel
)

from .database import (
    save_working_tree,
    list_all_saved_trees,
    delete_all_saves
)

# set debug flag
debug = True

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
#       API Routes
# ------------------------


def initialise_tree():
    """ Create a new Tree and return it"""
    tree = Tree()
    return tree


@ app.get("/")
async def get() -> dict:
    """ Return the API version """
    if debug:
        print(f"get()")
    return {"message": f"Fabulator {version}"}


@ app.get("/nodes")
async def get_all_nodes() -> dict:
    """ Get a list of all the nodes in the working tree"""
    if debug:
        print(f"get_all_nodes()")
    tree.show(line_type="ascii-em")
    return tree.all_nodes()


@ app.get("/nodes/{id}")
async def get_a_node() -> dict:
    """ Return a node specified by an id"""
    if debug:
        print(f"get_a_node()")
        print(f"id:{id}")
    return tree.get_node(id)


@ app.get("/saves/")
async def get_all_saves() -> dict:
    """ Return a dict of all the trees saved in the db collection """
    all_saves = await list_all_saved_trees()
    if debug:
        print(f"get_all_saves()")
        print(f"all_saves:{all_saves}")

    return jsonable_encoder(all_saves)


@ app.post("/nodes/{name}")
async def create_node(name: str, request: RequestAddSchema = Body(...)) -> dict:
    """ Add a node to the working tree """
    # map the incoming fields from the https request to the fields required by the treelib API
    request = jsonable_encoder(request)
    if debug:
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
        new_node = tree.create_node(
            name, parent=request["parent"], data=node_payload)
    else:
        # No parent so check if we already have a root
        if tree.root == None:
            new_node = tree.create_node(
                name, data=node_payload)
        else:
            return {"message": "Tree already has a root node"}
    save_result = await save_working_tree(tree)
    if debug:
        print(f"mongo save: {save_result}")
    return{new_node}


@ app.put("/nodes/{id}")
async def update_node(id: str, request: RequestUpdateSchema = Body(...)) -> dict:
    """ Update a node in the working tree identified by an id"""
    # generate a new id for the node if we have a parent
    if debug:
        print(f"req: {request}")
    node_payload = NodePayload(description=request.description,
                               previous=request.previous, next=request.next, tags=request.tags, text=request.text)
    if request.name:
        update_node = tree.update_node(
            id, _tag=request.name, data=node_payload)
    else:
        update_node = tree.update_node(
            id, data=node_payload)
    save_result = await save_working_tree(tree)
    if debug:
        print(f"updated node: {update_node }")
    return{update_node}


@ app.delete("/nodes/{id}")
async def delete_node(id: str) -> dict:
    """ Delete a node from the working tree identified by an id """
    # remove the node with the supplied id
    # todo: probably want to stash the children somewhere first in a sub tree for later use
    response = tree.remove_node(id)
    save_result = await save_working_tree(tree)
    return response


@ app.delete("/saves/")
async def delete_node() -> dict:
    """ Delete all saves from the db trees collection """
    delete_result = await delete_all_saves()

    result = ResponseModel(delete_result, "Documents removed")
    return result


# Create tree
tree = initialise_tree()

import uuid
from typing import Optional
from treelib import Node, Tree
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient

import db

# local modules here

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


def initialise_tree():
    tree = Tree()
    return tree


class Payload():
    def __init__(self, description: Optional[str] = None,
                 prev: Optional[str] = None,
                 next: Optional[str] = None,
                 tags: Optional[str] = None,
                 text: Optional[str] = None):
        self.description = description
        self.text = text
        self.prev = prev
        self.next = next
        self.tags = tags


@app.get("/nodes")
async def get_all_nodes() -> dict:
    tree.show(line_type="ascii-em")
    return tree.all_nodes()


@app.get("/nodes/{id}")
async def get_all_nodes() -> dict:
    return tree.get_node(id)


@app.get("/")
async def get() -> dict:
    return {"message": f"Fabulator {version}"}


@app.post("/nodes/{name}")
async def create_node(name: str, parent_node: Optional[str] = None,
                      description: Optional[str] = None,
                      prev: Optional[str] = None,
                      next: Optional[str] = None,
                      tags: Optional[str] = None,
                      text: Optional[str] = None) -> dict:
    # generate a new id for the node if we have a parent

    node_payload = Payload(description=description,
                           prev=prev, next=next, tags=tags, text=text)
    if parent_node:
        new_node = tree.create_node(
            name, parent=parent_node, data=node_payload)
    else:
        # No parent so check if we already have a root
        if tree.root == None:
            new_node = tree.create_node(
                name, data=node_payload)
        else:
            return {"message": "Tree already has a root node"}

    return{"id": new_node}


@app.put("/nodes/{id}")
async def update_node(id: str, name: str,
                      description: Optional[str] = None,
                      prev: Optional[str] = None,
                      next: Optional[str] = None,
                      tags: Optional[str] = None,
                      text: Optional[str] = None) -> dict:
    # generate a new id for the node if we have a parent

    node_payload = Payload(description=description,
                           prev=prev, next=next, tags=tags, text=text)
    if name:
        update_node = tree.update_node(
            id, _tag=name, data=node_payload)
    else:
        update_node = tree.update_node(
            id, data=node_payload)

    return{update_node}


@app.delete("/nodes/{id}")
async def delete_node(id: str) -> dict:
    # remove the node with the supplied id
    # probably want to stash the children somewhere first in a sub tree for later use
    response = tree.remove_node(id)
    return response

# Create tree
tree = initialise_tree()

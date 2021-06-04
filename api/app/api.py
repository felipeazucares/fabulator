import uuid
from typing import Optional
from treelib import Node, Tree
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient

# local modules here

app = FastAPI()

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
    def __init__(self, description: Optional[str] = None, prev: Optional[str] = None, next: Optional[str] = None, tags: Optional[list] = None, text: Optional[str] = None):
        self.description = description
        self.text = text
        self.prev = prev
        self.next = next
        self.tags = tags


@app.get("/nodes")
async def treeDump() -> dict:
    tree.show(line_type="ascii-em")
    return tree.all_nodes()


@app.get("/")
async def treeDump() -> dict:
    return {"message": "Welcome to Fabulator"}


@app.post("/nodes/{name}")
async def create_new(name: str, parent_node: Optional[str] = None, description: Optional[str] = None, prev: Optional[str] = None, next: Optional[str] = None, tags: Optional[list] = None, text: Optional[str] = None) -> dict:
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

# Create tree
tree = initialise_tree()

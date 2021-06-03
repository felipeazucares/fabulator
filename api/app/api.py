import uuid
from typing import Optional
from treelib import Node, Tree
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


class payload():
    def __init__(self, description, prev, next, tags):
        self.description = description
        self.prev = prev
        self.next = next
        self.tags = tags


@app.get("/nodes")
async def treeDump() -> dict:
    tree.show(line_type="ascii-em")
    return tree.all_nodes()


@app.post("/nodes/{name}")
async def create_new(name: str, parent_node: Optional[str] = None) -> dict:
    # generate a new id for the node if we have a parent
    if parent_node:
        new_node = tree.create_node(
            name, parent=parent_node)
    else:
        # No parent so check if we already have a root
        if tree.root == None:
            new_node = tree.create_node(
                name)
        else:
            return {"message": "Tree already has a root node"}

    return{"id": new_node}

# Create tree
tree = initialise_tree()

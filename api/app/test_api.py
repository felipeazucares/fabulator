import json

from fastapi import datastructures
import pytest
import httpx

import api

# Main test suite for Fabulator
# Philip Suggars
# Red Robot Labs - June 2021

# application settings
base_port = "8000"
root_url = f"http://localhost:{base_port}"


def test_tree_create():
    tree = api.initialise_tree()
    assert tree != None

# create a populated payload


def test_payload_create():
    test_description = "This is the node's description"
    test_text = "This is the node's test text content"
    test_prev = "Previous node id"
    test_next = "Next node id"
    test_tags = ["test_tag1", "test_tag2", "test_tag3"]
    test_payload = api.Payload(
        description=test_description, text=test_text, prev=test_prev, next=test_next, tags=test_tags)
    assert test_payload != None
    assert test_payload.text == test_text
    assert test_payload.prev == test_prev
    assert test_payload.next == test_next
    assert test_payload.tags == test_tags


# create a unpopulated payload

def test_payload_create_null():
    test_description = None
    test_text = None
    test_prev = None
    test_next = None
    test_tags = None
    test_payload = api.Payload(
        description=test_description, text=test_text, prev=test_prev, next=test_next, tags=test_tags)
    assert test_payload != None
    assert test_payload.text == test_text
    assert test_payload.prev == test_prev
    assert test_payload.next == test_next
    assert test_payload.tags == test_tags

# Now run async tests


@pytest.mark.asyncio
async def test_root_path():
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Fabulator"}

# Add root node


@pytest.fixture
@pytest.mark.asyncio
async def test_create_root_node():
    data = {"description": "Unit test description",
            "prev": "previous node", "next": "next node", "text": "Unit test text for root node",
            "tags": ["tag 1", "tag 2", "tag 3"]}
    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post("http://127.0.0.1:8000/nodes/Unit test root node", params=data)
    assert response.status_code == 200
    assert response.json()["id"]["_tag"] == "Unit test root node"
    return(response.json()["id"]["_identifier"])


# add and remove root node
@ pytest.mark.asyncio
async def test_remove_node(test_create_root_node):
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
        response = await ac.delete("/nodes/" + test_create_root_node)
    assert response.status_code == 200
    # test that the root node is removed as expected
    assert int(response.json()) == 1

# get all nodes - test root node


@ pytest.mark.asyncio
async def test_get_all_nodes(test_create_root_node):
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get("/nodes")
    assert response.status_code == 200
    # test that the root node is configured as expected
    assert response.json()[0]["_identifier"] == test_create_root_node
    assert response.json()[0]["_tag"] == "Unit test root node"
    assert response.json()[0]["data"]["description"] == "Unit test description"
    assert response.json()[0]["data"]["prev"] == "previous node"
    assert response.json()[0]["data"]["next"] == "next node"
    assert response.json()[0]["data"]["text"] == "Unit test text for root node"
    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
        response = await ac.delete("/nodes/" + test_create_root_node)

    # add and remove root node


@ pytest.mark.asyncio
async def test_add_child_node(test_create_root_node):
    data = {
        "parent_node": test_create_root_node,
        "description": "Unit test child description",
        "prev": "previous child node", "next": "next child node", "text": "Unit test text for child node",
        "tags": ["tag 1", "tag 2", "tag 3"]
    }
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/", params=data) as ac:
        response = await ac.post("/nodes/unit test child node")
    assert response.status_code == 200
    assert response.json()["id"]["_tag"] == "unit test child node"
    assert response.json()["id"][
        "data"]["description"] == "Unit test child description"
    assert response.json()["id"]["data"]["prev"] == "previous child node"
    assert response.json()["id"]["data"]["next"] == "next child node"
    assert response.json()[
        "id"]["data"]["text"] == "Unit test text for child node"
    assert response.json()["id"]["data"]["tags"] == ["tag 1", "tag 2", "tag 3"]
    # remove the root & child node we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
        response = await ac.delete("/nodes/" + test_create_root_node)
# get all nodes - test root node

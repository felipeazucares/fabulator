
import pytest
import httpx
from api.app import api
from typing import Optional
from fastapi import FastAPI
app = FastAPI()


# Main test suite for Fabulator
# Philip Suggars
# Red Robot Labs - June 2021

# application settings
base_port = "8000"
root_url = f"http://localhost:{base_port}"


def test_tree_create():
    """ initialise a tree and return it"""
    tree = api.initialise_tree()
    assert tree != None
    return tree


def test_payload_create():
    """ Set up a test payload & return it"""
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
    return test_payload


def test_payload_create_null():
    """ Set up an empty test payload & return it"""
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
    return test_payload


@pytest.mark.asyncio
async def test_root_path():
    """ return version number"""
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json()["message"] != None


@pytest.fixture
@pytest.mark.asyncio
async def test_create_root_node():
    """ Create a root node and return it """
    data = {"description": "Unit test description",
            "prev": "previous node", "next": "next node", "text": "Unit test text for root node",
            "tags": "['tag 1', 'tag 2', 'tag 3']"}
    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post("http://127.0.0.1:8000/nodes/Unit test root node", params=data)
    assert response.status_code == 200
    assert response.json()["id"]["_tag"] == "Unit test root node"
    return(response.json()["id"]["_identifier"])


@ pytest.mark.asyncio
async def test_remove_node(test_create_root_node):
    """ generate a root node and remove it """
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
        response = await ac.delete("/nodes/" + test_create_root_node)
    assert response.status_code == 200
    # test that the root node is removed as expected
    assert int(response.json()) == 1


@ pytest.mark.asyncio
async def test_update_node(test_create_root_node):
    """ generate a root node and update it"""
    data = {
        "name": "Unit test root node updated name",
        "description": "Unit test updated description",
        "prev": "previous updated node",
        "next": "next updated node",
        "text": "Unit test text for updated node",
        "tags": "['updated tag 1', 'updated tag 2', 'updated tag 3']"
    }

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/", params=data) as ac:
        response = await ac.put("/nodes/" + test_create_root_node)
    assert response.status_code == 200

    # now check it updated
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", params=test_create_root_node) as ac:
        response = await ac.get("/nodes/")
    assert response.status_code == 200
    # test that the root node is updated as expected
    assert response.json()[0]["_identifier"] == test_create_root_node
    assert response.json()[0]["_tag"] == "Unit test root node updated name"
    assert response.json()[
        0]["data"]["description"] == "Unit test updated description"
    assert response.json()[0]["data"]["prev"] == "previous updated node"
    assert response.json()[0]["data"]["next"] == "next updated node"
    assert response.json()[
        0]["data"]["text"] == "Unit test text for updated node"
    assert response.json()[
        0]["data"]["tags"] == "['updated tag 1', 'updated tag 2', 'updated tag 3']"

    # now remove the node we just added
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
        response = await ac.delete("/nodes/" + test_create_root_node)
    assert response.status_code == 200


@ pytest.mark.asyncio
async def test_get_a_node(test_create_root_node):
    """ get a single node by id"""
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", params=test_create_root_node) as ac:
        response = await ac.get("/nodes/")
    assert response.status_code == 200
    # test that the root node is configured as expected
    assert response.json()[0]["_identifier"] == test_create_root_node
    assert response.json()[0]["_tag"] == "Unit test root node"
    assert response.json()[0]["data"]["description"] == "Unit test description"
    assert response.json()[0]["data"]["prev"] == "previous node"
    assert response.json()[0]["data"]["next"] == "next node"
    assert response.json()[0]["data"]["text"] == "Unit test text for root node"
    assert response.json()[0]["data"]["tags"] == "['tag 1', 'tag 2', 'tag 3']"

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
        response = await ac.delete("/nodes/" + test_create_root_node)


@ pytest.mark.asyncio
async def test_add_child_node(test_create_root_node):
    """ Add a child node"""
    data = {
        "parent_node": test_create_root_node,
        "description": "unit test child description",
        "prev": "previous child node", "next": "next child node", "text": "unit test text for child node",
        "tags": "['tag 1', 'tag 2', 'tag 3']"
    }
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
        response = await ac.post("/nodes/unit test child node", params=data)
    assert response.status_code == 200
    assert response.json()["id"]["_tag"] == "unit test child node"
    assert response.json()["id"][
        "data"]["description"] == "unit test child description"
    assert response.json()["id"]["data"]["prev"] == "previous child node"
    assert response.json()["id"]["data"]["next"] == "next child node"
    assert response.json()[
        "id"]["data"]["text"] == "unit test text for child node"
    assert response.json()[
        "id"]["data"]["tags"] == "['tag 1', 'tag 2', 'tag 3']"

    # remove the root & child node we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
        response = await ac.delete("/nodes/" + test_create_root_node)


@ pytest.mark.asyncio
async def test_get_all_nodes(test_create_root_node):
    """ get all nodes and test the root"""
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
    assert response.json()[0]["data"]["tags"] == "['tag 1', 'tag 2', 'tag 3']"

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
        response = await ac.delete("/nodes/" + test_create_root_node)

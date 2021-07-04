
import pytest
import os
import asyncio
import httpx
import app.api as api
import app.database as database
import motor.motor_asyncio
import hashlib
import asyncio
from typing import Optional
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder


app = FastAPI()


# Main test suite for Fabulator
# Philip Suggars
# Red Robot Labs - June 2021

# application settings
base_port = "8000"
root_url = f"http://localhost:{base_port}"

# the mongo save returns a save object - but how do I deconstruct one of those


class MockResponse:
    @staticmethod
    def json():
        {
            "data": [
                {
                    "_identifier": "399a95ee-d9c7-11eb-b6de-f01898e87167",
                    "_tag": "Automatic Shoes",
                    "expanded": True,
                    "_predecessor": {
                        "64eb660e-d343-11eb-b051-f01898e87167": "8de508ee-d343-11eb-b051-f01898e87167"
                    },
                    "_successors": {},
                    "data": {
                        "description": "John gets an unexpected message from @TheRealEmpressSeb",
                        "previous": None,
                        "next": None,
                        "text": "I stare at the glass like it’s bitten me. I should just ignore this, but like all good lab rats I know the buttons to push to get the good stuff.",
                        "tags": [
                            "Chapter",
                            "Maginot"
                        ]
                    },
                    "_initial_tree_id": "64eb660e-d343-11eb-b051-f01898e87167"
                }
            ],
            "code": 200,
            "message": "Success"
        }


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture
@pytest.mark.asyncio
def get_dummy_user_account_id():
    # set up unit test user
    username = "unittestuser"
    firstname = "John"
    surname = "Maginot"
    username_hash = hashlib.sha256(username.encode('utf-8')).hexdigest()
    print(f"account_id:{username_hash}")
    return username_hash


def test_tree_create():
    """ initialise a tree and return it"""
    tree = api.initialise_tree()
    assert tree != None
    return tree


def test_payload_create():
    """ Set up a test payload & return it"""
    test_description = "This is the node's description"
    test_text = "This is the node's test text content"
    test_previous = "Previous node id"
    test_next = "Next node id"
    test_tags = ["test_tag1", "test_tag2", "test_tag3"]
    test_payload = api.NodePayload(
        description=test_description, text=test_text, previous=test_previous, next=test_next, tags=test_tags)
    assert test_payload != None
    assert test_payload.text == test_text
    assert test_payload.previous == test_previous
    assert test_payload.next == test_next
    assert test_payload.tags == test_tags
    return test_payload


def test_payload_create_null():
    """ Set up an empty test payload & return it"""
    test_description = None
    test_text = None
    test_previous = None
    test_next = None
    test_tags = None
    test_payload = api.NodePayload(
        description=test_description, text=test_text, previous=test_previous, next=test_next, tags=test_tags)
    assert test_payload != None
    assert test_payload.text == test_text
    assert test_payload.previous == test_previous
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


@pytest.mark.asyncio
@pytest.fixture
async def test_create_root_node(get_dummy_user_account_id):
    """ Create a root node and return it """
    data = jsonable_encoder({
                            "description": "Unit test description",
                            "previous": "previous node",
                            "next": "next node",
                            "text": "Unit test text for root node",
                            "tags": ['tag 1', 'tag 2', 'tag 3']
                            })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post(f"http://localhost:8000/nodes/{get_dummy_user_account_id}/Unit test root node", json=data)
    print(f"create root node response:{response.json()}")

    assert response.status_code == 200
    assert response.json()["data"][0]["_tag"] == "Unit test root node"
    return({
        "node_id": response.json()["data"][0]["_identifier"],
        "user_id": get_dummy_user_account_id
    })


@ pytest.mark.asyncio
async def test_remove_node(test_create_root_node: list):
    """ generate a root node and remove it """
    print(
        f"dummy account object:{test_create_root_node['user_id']}")
    print(
        "http://localhost:8000/nodes/"+test_create_root_node['user_id']+"/"+test_create_root_node['node_id'])
    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.get("http://localhost:8000/nodes/"+test_create_root_node['user_id']+"/"+test_create_root_node['node_id'])
    assert response.status_code == 200
    print(f"response:{response}")
    # test that the root node is removed as expected
    assert int(response.json()) == 1


# @ pytest.mark.asyncio
# async def test_update_node(test_create_root_node):
#     """ generate a root node and update it"""
#     data = jsonable_encoder({
#         "name": "Unit test root node updated name",
#         "description": "Unit test updated description",
#         "previous": "previous updated node",
#         "next": "next updated node",
#         "text": "Unit test text for updated node",
#         "tags": ['updated tag 1', 'updated tag 2', 'updated tag 3']
#     })

#     async with httpx.AsyncClient(app=api.app) as ac:
#         response = await ac.put("http://127.0.0.1:8000/nodes/" + test_create_root_node, json=data)
#     assert response.status_code == 200

#     # now get what we just created it updated
#     async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", params=test_create_root_node) as ac:
#         response = await ac.get("/nodes/")
#     assert response.status_code == 200
#     # test that the root node is updated as expected
#     assert response.json()[0]["_identifier"] == test_create_root_node
#     assert response.json()[0]["_tag"] == "Unit test root node updated name"
#     assert response.json()[
#         0]["data"]["description"] == "Unit test updated description"
#     assert response.json()[0]["data"]["previous"] == "previous updated node"
#     assert response.json()[0]["data"]["next"] == "next updated node"
#     assert response.json()[
#         0]["data"]["text"] == "Unit test text for updated node"
#     assert response.json()[
#         0]["data"]["tags"] == ['updated tag 1', 'updated tag 2', 'updated tag 3']

#     # now remove the node we just added
#     async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
#         response = await ac.delete("/nodes/" + test_create_root_node)
#     assert response.status_code == 200


@ pytest.mark.asyncio
async def test_get_a_node(test_create_root_node):
    """ get a single node by id"""
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", params=test_create_root_node) as ac:
        response = await ac.get("/nodes/")
    print(f"get a node response:{response.json()}")
    assert response.status_code == 200
    # test that the root node is configured as expected
    assert response.json()[
        "data"][0]["_tag"]["_identifier"] == test_create_root_node
    assert response.json()[
        "data"][0]["_tag"]["_tag"] == "Unit test root node"
    assert response.json()[
        "data"][0]["_tag"]["description"] == "Unit test description"
    assert response.json()[
        "data"][0]["_tag"]["data"]["previous"] == "previous node"
    assert response.json()[
        "data"][0]["_tag"]["data"]["next"] == "next node"
    assert response.json()[
        "data"][0]["_tag"]["data"]["text"] == "Unit test text for root node"
    assert response.json()[
        "data"][0]["_tag"]["data"]["tags"] == [
        'tag 1', 'tag 2', 'tag 3']

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
        response = await ac.delete("/nodes/" + test_create_root_node)


# @ pytest.mark.asyncio
# async def test_add_child_node(test_create_root_node):
#     """ Add a child node"""
#     data = jsonable_encoder({
#         "parent": test_create_root_node,
#         "description": "unit test child description",
#         "previous": "previous child node",
#         "next": "next child node",
#         "text": "unit test text for child node",
#         "tags": ['tag 1', 'tag 2', 'tag 3']
#     })
#     async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
#         response = await ac.post("/nodes/unit test child node", json=data)
#     assert response.status_code == 200
#     assert response.json()[0]["_tag"] == "unit test child node"
#     assert response.json()[0][
#         "data"]["description"] == "unit test child description"
#     assert response.json()[0]["data"]["previous"] == "previous child node"
#     assert response.json()[0]["data"]["next"] == "next child node"
#     assert response.json()[
#         0]["data"]["text"] == "unit test text for child node"
#     assert response.json()[0]["data"]["tags"] == ['tag 1', 'tag 2', 'tag 3']

#     # remove the root & child node we just created
#     async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
#         response = await ac.delete("/nodes/" + test_create_root_node)


@ pytest.mark.asyncio
async def test_get_all_nodes(test_create_root_node):
    """ get all nodes and test the root"""
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get("/nodes")
    print(f"get all nodes response:{response.json()}")
    assert response.status_code == 200
    # test that the root node is configured as expected
    assert response.json()["data"][0]["_identifier"] == test_create_root_node
    assert response.json()["data"][0]["_tag"] == "Unit test root node"
    assert response.json()[
        "data"][0]["data"]["description"] == "Unit test description"
    assert response.json()["data"][0]["data"]["previous"] == "previous node"
    assert response.json()["data"][0]["data"]["next"] == "next node"
    assert response.json()[
        "data"][0]["data"]["text"] == "Unit test text for root node"
    assert response.json()["data"][0]["data"]["tags"] == [
        'tag 1', 'tag 2', 'tag 3']

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000/") as ac:
        response = await ac.delete("/nodes/" + test_create_root_node)


# @pytest.fixture
# def db(event_loop):
#     MONGO_DETAILS = os.getenv(key="MONGO_DETAILS")
#     client = motor.motor_asyncio.AsyncIOMotorClient(
#         MONGO_DETAILS, io_loop=event_loop)
#     # client = AsyncIOMotorClient('mongodb://localhost', io_loop=event_loop)
#     yield client['mydb']
#     client.close()


# @ pytest.mark.asyncio
# async def test_save_working_tree(get_dummy_user_account_id):
#     saves = await database.save_working_tree(account_id=get_dummy_user_account_id, tree=None)
#     assert saves == None

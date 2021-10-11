
# from fastapi.param_functions import Form
from app.api import TEST_USERNAME_TO_ADD, TEST_PASSWORD_TO_ADD, TEST_USERNAME_TO_ADD2, TEST_PASSWORD_TO_ADD2, TEST_PASSWORD_TO_CHANGE
import pytest
import asyncio
import os
import httpx
import app.api as api
import app.database as database
import hashlib
import asyncio
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from jose import jwt
from passlib.context import CryptContext


app = FastAPI()

# Main test suite for Fabulator
# Philip Suggars
# Red Robot Labs - June 2021

# application settings
base_port = "8000"
root_url = f"http://localhost:{base_port}"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ------------------------
#   User Tests fixtures
# ------------------------

@pytest.fixture
@pytest.mark.asyncio
def get_dummy_user_account_id():
    # set up unit test user
    username = TEST_USERNAME_TO_ADD
    username_hash = hashlib.sha256(username.encode('utf-8')).hexdigest()
    return username_hash


@pytest.fixture
def dummy_user_to_add():
    return {
        "name": {"firstname": "John", "surname": "Maginot"},
        "username": TEST_USERNAME_TO_ADD,
        "password": TEST_PASSWORD_TO_ADD,
        "account_id": None,
        "email": "john_maginot@fictional.com",
        "disabled": False,
        "user_role": "user:reader user:writer tree:reader tree:writer usertype:writer",
        "user_type": "free"
    }


@pytest.fixture
@pytest.mark.asyncio
async def test_add_user(dummy_user_to_add):
    """ Add a new user so that we can authorise against it"""
    data = jsonable_encoder(dummy_user_to_add)
    # first check to see if the user exists
    db_storage = database.UserStorage(collection_name="user_collection")
    user = await db_storage.get_user_details_by_username(dummy_user_to_add['username'])
    if user is not None:
        result = await db_storage.delete_user_details_by_account_id(account_id=user.account_id)
        assert result == 1
    # now post a new dummy user
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.post(f"/users", json=data)
    assert response.status_code == 200
    assert response.json()[
        "data"]["name"]["firstname"] == dummy_user_to_add["name"]["firstname"]
    assert response.json()[
        "data"]["name"]["surname"] == dummy_user_to_add["name"]["surname"]
    assert response.json()[
        "data"]["username"] == dummy_user_to_add["username"]
    assert pwd_context.verify(dummy_user_to_add["username"], response.json()[
        "data"]["account_id"]) == True
    # assert pwd_context.verify(dummy_user_to_add["password"], response.json()[
    #     "data"]["password"]) == True
    assert response.json()[
        "data"]["email"] == dummy_user_to_add["email"]
    assert response.json()[
        "data"]["disabled"] == dummy_user_to_add["disabled"]
    assert response.json()[
        "data"]["user_role"] == dummy_user_to_add["user_role"]
    assert response.json()[
        "data"]["user_type"] == dummy_user_to_add["user_type"]
    # return id of record created
    return(response.json()["data"]["id"])


@pytest.mark.asyncio
@pytest.fixture(params=["", "user:reader", "user:writer", "tree:reader", "tree:writer", "usertype:writer"])
async def return_scoped_token(request):
    """ Add a new user so that we can authorise against it"""

    if request.param != "user:reader":
        user_scopes = f"{request.param} user:reader"
    else:
        user_scopes = request.param

    dummy_user_to_add_scoped = jsonable_encoder({
        "name": {"firstname": "Telly", "surname": "Scopes"},
        "username": TEST_USERNAME_TO_ADD2,
        "password": TEST_PASSWORD_TO_ADD2,
        "account_id": None,
        "email": "tscoped@fictional.com",
        "disabled": False,
        "user_role": user_scopes,
        "user_type": "free"
    })
    data = jsonable_encoder(dummy_user_to_add_scoped)
    # first check to see if the user exists
    db_storage = database.UserStorage(collection_name="user_collection")
    user = await db_storage.get_user_details_by_username(dummy_user_to_add_scoped['username'])
    if user is not None:
        result = await db_storage.delete_user_details_by_account_id(account_id=user.account_id)
        assert result == 1

    # now post a new dummy user
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.post(f"/users", json=data)
    assert response.status_code == 200
    assert response.json()[
        "data"]["name"]["firstname"] == dummy_user_to_add_scoped["name"]["firstname"]
    assert response.json()[
        "data"]["name"]["surname"] == dummy_user_to_add_scoped["name"]["surname"]
    assert response.json()[
        "data"]["username"] == dummy_user_to_add_scoped["username"]
    assert pwd_context.verify(dummy_user_to_add_scoped["username"], response.json()[
        "data"]["account_id"]) == True
    # assert pwd_context.verify(dummy_user_to_add_scoped["password"], response.json()[
    #     "data"]["password"]) == True
    assert response.json()[
        "data"]["email"] == dummy_user_to_add_scoped["email"]
    assert response.json()[
        "data"]["disabled"] == dummy_user_to_add_scoped["disabled"]
    assert response.json()[
        "data"]["user_role"] == dummy_user_to_add_scoped["user_role"]
    assert response.json()[
        "data"]["user_type"] == dummy_user_to_add_scoped["user_type"]

    form_data = {
        "username": dummy_user_to_add_scoped["username"],
        "password": dummy_user_to_add_scoped["password"],
        "scope": dummy_user_to_add_scoped["user_role"].replace(",", " ")
    }
    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post(f"http://localhost:8000/get_token", data=form_data)
    assert response.status_code == 200
    return {"token": {"Authorization": "Bearer " + str(response.json()["access_token"])},
            "scopes": form_data["scope"]}


@pytest.mark.asyncio
@pytest.fixture(params=["", "user:reader", "user:writer", "tree:reader", "tree:writer"])
async def return_simple_scoped_token(request):
    """ Add a new user so that we can authorise against it"""

    user_scopes = request.param

    dummy_user_to_add_scoped = jsonable_encoder({
        "name": {"firstname": "Telly", "surname": "Scopes"},
        "username": TEST_USERNAME_TO_ADD2,
        "password": TEST_PASSWORD_TO_ADD2,
        "account_id": None,
        "email": "tscoped@fictional.com",
        "disabled": False,
        "user_role": user_scopes,
        "user_type": "free"
    })
    data = jsonable_encoder(dummy_user_to_add_scoped)
    # first check to see if the user exists
    db_storage = database.UserStorage(collection_name="user_collection")
    user = await db_storage.get_user_details_by_username(dummy_user_to_add_scoped['username'])
    if user is not None:
        result = await db_storage.delete_user_details_by_account_id(account_id=user.account_id)
        assert result == 1

    # now post a new dummy user
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.post(f"/users", json=data)
    assert response.status_code == 200
    assert response.json()[
        "data"]["name"]["firstname"] == dummy_user_to_add_scoped["name"]["firstname"]
    assert response.json()[
        "data"]["name"]["surname"] == dummy_user_to_add_scoped["name"]["surname"]
    assert response.json()[
        "data"]["username"] == dummy_user_to_add_scoped["username"]
    assert pwd_context.verify(dummy_user_to_add_scoped["username"], response.json()[
        "data"]["account_id"]) == True
    # assert pwd_context.verify(dummy_user_to_add_scoped["password"], response.json()[
    #     "data"]["password"]) == True
    assert response.json()[
        "data"]["email"] == dummy_user_to_add_scoped["email"]
    assert response.json()[
        "data"]["disabled"] == dummy_user_to_add_scoped["disabled"]
    assert response.json()[
        "data"]["user_role"] == dummy_user_to_add_scoped["user_role"]
    assert response.json()[
        "data"]["user_type"] == dummy_user_to_add_scoped["user_type"]

    form_data = {
        "username": dummy_user_to_add_scoped["username"],
        "password": dummy_user_to_add_scoped["password"],
        "scope": dummy_user_to_add_scoped["user_role"].replace(",", " ")
    }
    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post(f"http://localhost:8000/get_token", data=form_data)
    assert response.status_code == 200
    return {"token": {"Authorization": "Bearer " + str(response.json()["access_token"])},
            "scopes": form_data["scope"]}


@pytest.fixture
async def dummy_user_update():
    # read user collection to get the account_id of the user we added earlier so we can simulate
    # data provided by UI
    db_storage = database.UserStorage(collection_name="user_collection")
    user = await db_storage.get_user_details_by_username(TEST_USERNAME_TO_ADD)
    assert user is not None
    return {
        "name": {"firstname": "Jango", "surname": "Fett"},
        "email": "jango_fett@runsheadless.com"
    }


# --------------------------
#   Authentication fixtures
# --------------------------


@pytest.mark.asyncio
@pytest.fixture
async def return_token(test_add_user, dummy_user_to_add):
    """ test user login """
    assert test_add_user is not None
    form_data = {
        "username": dummy_user_to_add["username"],
        "password": dummy_user_to_add["password"],
        "scope": dummy_user_to_add["user_role"].replace(",", " ")
    }
    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post(f"http://localhost:8000/get_token", data=form_data)
    assert response.status_code == 200
    return {"Authorization": "Bearer " + str(response.json()["access_token"])}


@pytest.mark.asyncio
@pytest.fixture
def test_unit_tree_create():
    """ initialise a tree and return it"""
    tree = api.initialise_tree()
    assert tree != None
    return tree


def test_unit_payload_create():
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


def test_unit_payload_create_null():
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
@pytest.fixture
async def test_get_root_node(return_token):
    """ get the root node if it exists"""
    headers = return_token
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.get("/trees/root")
    assert response.status_code == 200
    # return id of root node or None
    return response.json()["data"]["root"]


# ------------------------
#      Node Fixtures
# ------------------------


@pytest.mark.asyncio
@pytest.fixture
async def test_create_root_node(return_token, get_dummy_user_account_id, test_get_root_node):
    """ Create a root node and return it """
    headers = return_token
    # first test if there's already a root node - if there is remove it
    if test_get_root_node != None:
        async with httpx.AsyncClient(app=api.app) as client:
            response = await client.delete(f"http://localhost:8000/nodes/{test_get_root_node}", headers=headers)
        assert response.status_code == 200
        # test that the root node is removed as expected
        assert int(response.json()['data']) >= 1

    data = jsonable_encoder({
                            "description": "Unit test description",
                            "previous": "previous node",
                            "next": "next node",
                            "text": "Unit test text for root node",
                            "tags": ['tag 1', 'tag 2', 'tag 3']
                            })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post(f"http://localhost:8000/nodes/Unit test root node", json=data, headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["node"]["_tag"] == "Unit test root node"
    return({
        "node_id": response.json()["data"]["node"]["_identifier"],
        "account_id": get_dummy_user_account_id,
        "save_id": response.json()["data"]["object_id"]
    })


# ------------------------
#      Root Node Tests
# ------------------------


@pytest.mark.asyncio
async def test_root_path(return_token):
    """ return version number"""
    headers = return_token
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json()["data"]["version"] == "0.1.0"
    assert response.json()["message"] == "Success"


@pytest.mark.asyncio
async def test_nodes_add_another_root_node(test_create_root_node, return_token):
    """ generate a root node then try to add another"""
    assert test_create_root_node is not None
    headers = return_token
    data = jsonable_encoder({
        "description": "Unit test description for second root node",
        "previous": "previous node",
        "next": "next node",
        "text": "Unit test text for adding another root node",
                            "tags": ['tag 1', 'tag 2', 'tag 3']
                            })
    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post(f"http://localhost:8000/nodes/this should fail", json=data, headers=headers)
    assert response.status_code == 422
    # test that the root node is removed as expected
    assert response.json()["detail"] == "Tree already has a root node"

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.delete(f"/users")
    assert response.status_code == 200
    assert response.json()[
        "data"] == 1

# ------------------------
#      Remove Node Tests
# ------------------------


@pytest.mark.asyncio
async def test_nodes_remove_node(return_token, test_create_root_node: list):
    """ generate a root node and remove it """
    headers = return_token
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
    assert response.status_code == 200
    # test that the root node is removed as expected
    assert int(response.json()["data"]) > 0

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.delete(f"/users")
    assert response.status_code == 200
    assert response.json()[
        "data"] == 1


@pytest.mark.asyncio
async def test_nodes_remove_non_existent_node(return_token, test_create_root_node: list):
    """ generate a root node and remove it """
    headers = return_token
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/XXXX", headers=headers)
    assert response.status_code == 404
    # test that the root node is removed as expected
    assert response.json()["detail"] == "Node not found in current tree"
    # now remove the node we just added
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
    assert response.status_code == 200

# ------------------------
#   Update Node Tests
# ------------------------


@pytest.mark.asyncio
async def test_nodes_update_node(test_create_root_node, return_token):
    """ generate a root node and update it"""
    headers = return_token
    data = jsonable_encoder({
        "name": "Unit test root node updated name",
        "description": "Unit test updated description",
        "previous": "previous updated node",
        "next": "next updated node",
        "text": "Unit test text for updated node",
        "tags": ['updated tag 1', 'updated tag 2', 'updated tag 3']
    })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.put(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", json=data, headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["object_id"] != None

    # now get what we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get(f"/nodes/{test_create_root_node['node_id']}", headers=headers)
    assert response.status_code == 200
    # test that the root node is updated as expected

    assert response.json()[
        "data"]["_identifier"] == test_create_root_node["node_id"]
    assert response.json()[
        "data"]["_tag"] == "Unit test root node updated name"
    assert response.json()[
        "data"]["data"]["description"] == "Unit test updated description"
    assert response.json()[
        "data"]["data"]["previous"] == "previous updated node"
    assert response.json()["data"]["data"]["next"] == "next updated node"
    assert response.json()[
        "data"]["data"]["text"] == "Unit test text for updated node"
    assert response.json()["data"]["data"]["tags"] == [
        'updated tag 1', 'updated tag 2', 'updated tag 3']

    # now remove the node we just added
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_nodes_update_node_for_non_existent_node(test_create_root_node, return_token):
    """ generate a root node and update it"""
    headers = return_token
    data = jsonable_encoder({
        "name": "Unit test root node updated name",
        "description": "Unit test updated description",
        "previous": "previous updated node",
        "next": "next updated node",
        "text": "Unit test text for updated node",
        "tags": ['updated tag 1', 'updated tag 2', 'updated tag 3']
    })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.put(f"http://localhost:8000/nodes/XXXX", json=data, headers=headers)
    assert response.status_code == 404
    # test that an error state is generated as expected
    assert response.json()[
        "detail"] == "Node not found in current tree"

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_nodes_update_node_with_bad_payload(test_create_root_node, return_token):
    """ update a node with a bad payload"""
    headers = return_token
    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.put(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
    assert response.status_code == 422
    # test that an error state is generated as expected

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_nodes_update_node_with_non_existent_parent(test_create_root_node, return_token):
    """ generate a root node and update it with a non existent parent"""
    headers = return_token
    data = jsonable_encoder({
        "parent": "XXXX",
        "name": "Unit test root node updated name",
        "description": "Unit test updated description",
        "previous": "previous updated node",
        "next": "next updated node",
        "text": "Unit test text for updated node",
        "tags": ['updated tag 1', 'updated tag 2', 'updated tag 3']
    })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.put(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", json=data, headers=headers)
    assert response.status_code == 422
    assert response.json()[
        'detail'] == "Parent XXXX is missing from tree"

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)

    assert response.status_code == 200

# ------------------------
#   Get Node Tests
# ------------------------


@pytest.mark.asyncio
async def test_nodes_get_a_node(test_create_root_node, return_token):
    """ get a single node by id"""
    headers = return_token
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get(f"/nodes/{test_create_root_node['node_id']}", headers=headers)
    assert response.status_code == 200
    # test that the root node is configured as expected
    assert response.json()[
        "data"]["_identifier"] == test_create_root_node["node_id"]
    assert response.json()[
        "data"]["_tag"] == "Unit test root node"
    assert response.json()[
        "data"]["data"]["description"] == "Unit test description"
    assert response.json()[
        "data"]["data"]["previous"] == "previous node"
    assert response.json()[
        "data"]["data"]["next"] == "next node"
    assert response.json()[
        "data"]["data"]["text"] == "Unit test text for root node"
    assert response.json()[
        "data"]["data"]["tags"] == [
        'tag 1', 'tag 2', 'tag 3']

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)


@pytest.mark.asyncio
async def test_nodes_get_a_non_existent_node(test_create_root_node, return_token):
    """ get a non-existent node by id"""
    headers = return_token
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.get(f"/nodes/xxx")
    assert response.status_code == 404
    # test that an error state is generated as expected
    assert response.json()[
        "detail"] == "Node not found in current tree"

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")


@pytest.mark.asyncio
async def test_nodes_get_all_nodes(test_create_root_node, return_token):
    """ get all nodes and test the root"""
    headers = return_token
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.get(f"/nodes")
    assert response.status_code == 200
    # test that the root node is configured as expected
    assert response.json()[
        "data"][0]["_identifier"] == test_create_root_node["node_id"]
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
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)


@pytest.mark.asyncio
async def test_nodes_get_filtered_nodes(test_create_root_node, return_token):
    """ get all nodes and test the root"""
    headers = return_token
    params = {"filterval": "tag 1"}
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", params=params, headers=headers) as ac:
        response = await ac.get(f"/nodes")
    print(f"filter:{response.json()}")
    assert response.status_code == 200
    # test that the root node is configured as expected
    assert len(response.json()[
        "data"]) == 1
    assert response.json()[
        "data"][0]["_identifier"] == test_create_root_node["node_id"]
    assert response.json()["data"][0]["_tag"] == "Unit test root node"
    assert response.json()[
        "data"][0]["data"]["description"] == "Unit test description"
    assert response.json()[
        "data"][0]["data"]["previous"] == "previous node"
    assert response.json()["data"][0]["data"]["next"] == "next node"
    assert response.json()[
        "data"][0]["data"]["text"] == "Unit test text for root node"
    assert response.json()["data"][0]["data"]["tags"] == [
        'tag 1', 'tag 2', 'tag 3']

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)

# ------------------------
#   Add Node Tests
# ------------------------


@pytest.mark.asyncio
async def test_nodes_add_child_node(test_create_root_node, return_token):
    """ Add a child node"""
    headers = return_token
    data = jsonable_encoder({
        "parent": test_create_root_node["node_id"],
        "description": "unit test child description",
        "previous": "previous child node",
        "next": "next child node",
        "text": "unit test text for child node",
        "tags": ['tag 1', 'tag 2', 'tag 3']
    })
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.post(f"/nodes/unit test child node", json=data, headers=headers)
    assert response.status_code == 200
    assert response.json()[
        "data"]["node"]["_tag"] == "unit test child node"
    assert response.json()[
        "data"]["node"][
        "data"]["description"] == "unit test child description"
    assert response.json()[
        "data"]["node"]["data"]["previous"] == "previous child node"
    assert response.json()[
        "data"]["node"]["data"]["next"] == "next child node"
    assert response.json()[
        "data"]["node"]["data"]["text"] == "unit test text for child node"
    assert response.json()[
        "data"]["node"]["data"]["tags"] == ['tag 1', 'tag 2', 'tag 3']

    # remove the root & child node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)


@pytest.mark.asyncio
async def test_nodes_add_child_node_with_invalid_parent(test_create_root_node, return_token):
    """ Add a child node with invalid parent"""
    headers = return_token
    data = jsonable_encoder({
        "parent": "XXXX",
        "description": "unit test child description",
        "previous": "previous child node",
        "next": "next child node",
        "text": "unit test text for child node",
        "tags": ['tag 1', 'tag 2', 'tag 3']
    })
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.post(f"/nodes/unit test child node", json=data, headers=headers)
    assert response.status_code == 422
    assert response.json()[
        "detail"] == "Parent XXXX is missing from tree"

    # remove the root & child node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)

# ------------------------
#   Remove Subtree Tests
# ------------------------


@pytest.fixture
@pytest.mark.asyncio
async def test_setup_remove_and_return_subtree(test_create_root_node, return_token):
    """ Add a child node"""
    headers = return_token
    child_data = jsonable_encoder({
        "name": "Unit test child node",
        "parent": test_create_root_node["node_id"],
        "description": "Unit test child description",
        "previous": "previous child node",
        "next": "next child node",
        "text": "Unit test text for child node",
        "tags": ['tag 1', 'tag 2', 'tag 3']
    })

    # add child node to root
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.post(f"/nodes/{child_data['name']}", json=child_data, headers=headers)
    assert response.status_code == 200
    # add the child_node_id to the dict that we will return to calling functions for testing
    child_data["child_node_id"] = response.json()[
        "data"]["node"]["_identifier"]
    # now build grandchild data using item returned from above post

    grandchild_data = jsonable_encoder({
        "name": "Unit test grandchild node",
        "parent": child_data["child_node_id"],
        "description": "Unit test grandchild description",
        "previous": "nothing",
        "next": "nothing",
        "text": "Unit test text for grandchild node",
        "tags": ['tag 4', 'tag 5', 'tag 6']
    })
    # create grandchild node
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.post(f"/nodes/{grandchild_data['name']}", json=grandchild_data, headers=headers)
    assert response.status_code == 200
    # add the grandchild_node_id to the dict that we will return to calling functions for testing
    grandchild_data["grandchild_node_id"] = response.json()[
        "data"]["node"]["_identifier"]

    return {"test data": {"child_data": child_data,
                          "grandchild_data": grandchild_data},
            "response": response.json(),
            "original_root": test_create_root_node["node_id"],
            "account_id": test_create_root_node['account_id']}


@pytest.mark.asyncio
async def test_subtrees_remove_subtree(test_setup_remove_and_return_subtree, return_token):
    # set these two shortcuts up for ledgibility purposes
    headers = return_token
    child_node_id = test_setup_remove_and_return_subtree["test data"]["child_data"]["child_node_id"]
    grandchild_node_id = test_setup_remove_and_return_subtree[
        "test data"]["grandchild_data"]["grandchild_node_id"]
    # remove the specified child
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.get(f"/trees/{child_node_id}", headers=headers)
    assert response.status_code == 200
    assert child_node_id in response.json()["data"]["_nodes"]
    assert grandchild_node_id in response.json()["data"]["_nodes"]
    # check the root of the subtree we have is the child of the original
    assert child_node_id == response.json()["data"]["root"]
    # check the child payload
    assert response.json()["data"]["_nodes"][
        child_node_id]["data"]["description"] == test_setup_remove_and_return_subtree["test data"]["child_data"]["description"]
    assert response.json()["data"]["_nodes"][
        child_node_id]["data"]["previous"] == test_setup_remove_and_return_subtree["test data"]["child_data"]["previous"]
    assert response.json()["data"]["_nodes"][
        child_node_id]["data"]["next"] == test_setup_remove_and_return_subtree["test data"]["child_data"]["next"]
    assert response.json()["data"]["_nodes"][
        child_node_id]["data"]["text"] == test_setup_remove_and_return_subtree["test data"]["child_data"]["text"]
    assert response.json()["data"]["_nodes"][
        child_node_id]["data"]["tags"] == test_setup_remove_and_return_subtree["test data"]["child_data"]["tags"]
    # check the grandchild payload
    assert response.json()["data"]["_nodes"][
        grandchild_node_id]["data"]["description"] == test_setup_remove_and_return_subtree["test data"]["grandchild_data"]["description"]
    assert response.json()["data"]["_nodes"][
        grandchild_node_id]["data"]["previous"] == test_setup_remove_and_return_subtree["test data"]["grandchild_data"]["previous"]
    assert response.json()["data"]["_nodes"][
        grandchild_node_id]["data"]["next"] == test_setup_remove_and_return_subtree["test data"]["grandchild_data"]["next"]
    assert response.json()["data"]["_nodes"][
        grandchild_node_id]["data"]["text"] == test_setup_remove_and_return_subtree["test data"]["grandchild_data"]["text"]
    assert response.json()["data"]["_nodes"][
        grandchild_node_id]["data"]["tags"] == test_setup_remove_and_return_subtree["test data"]["grandchild_data"]["tags"]

    # remove the root & child node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_setup_remove_and_return_subtree['original_root']}", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_subtrees_add_subtree(test_setup_remove_and_return_subtree, return_token):
    headers = return_token
    child_node_id = test_setup_remove_and_return_subtree["test data"]["child_data"]["child_node_id"]
    child_data = test_setup_remove_and_return_subtree["test data"]["child_data"]
    # account_id = test_setup_remove_and_return_subtree["account_id"]
    grandchild_data = test_setup_remove_and_return_subtree["test data"]["grandchild_data"]
    grandchild_node_id = test_setup_remove_and_return_subtree[
        "test data"]["grandchild_data"]["grandchild_node_id"]
    original_root_id = test_setup_remove_and_return_subtree["original_root"]
    # prune ndde
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000", headers=headers) as ac:
        response = await ac.get(f"/trees/{child_node_id}")
    assert response.status_code == 200

    data = jsonable_encoder(
        {"sub_tree": response.json()["data"]})

    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.post(f"/trees/{test_setup_remove_and_return_subtree['original_root']}", json=data, headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Success"
    assert response.json()["data"] == "Graft complete"

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.get(f"/nodes")
    assert response.status_code == 200
    # test that the root node is configured as expected
    assert response.json()[
        "data"][0]["_identifier"] == original_root_id
    assert response.json()["data"][0]["_tag"] == "Unit test root node"
    assert response.json()[
        "data"][0]["data"]["description"] == "Unit test description"
    assert response.json()["data"][0]["data"]["previous"] == "previous node"
    assert response.json()["data"][0]["data"]["next"] == "next node"
    assert response.json()[
        "data"][0]["data"]["text"] == "Unit test text for root node"
    assert response.json()["data"][0]["data"]["tags"] == [
        'tag 1', 'tag 2', 'tag 3']

    # child node tests
    assert response.json()[
        "data"][1]["_identifier"] == child_node_id
    assert response.json()["data"][1]["_tag"] == child_data["name"]
    assert response.json()[
        "data"][1]["data"]["description"] == child_data["description"]
    assert response.json()[
        "data"][1]["data"]["previous"] == child_data["previous"]
    assert response.json()[
        "data"][1]["data"]["next"] == child_data["next"]
    assert response.json()[
        "data"][1]["data"]["text"] == child_data["text"]
    assert response.json()[
        "data"][1]["data"]["tags"] == child_data["tags"]

    # grandchild node tests
    assert response.json()[
        "data"][2]["_identifier"] == grandchild_node_id
    assert response.json()["data"][2]["_tag"] == grandchild_data["name"]
    assert response.json()[
        "data"][2]["data"]["description"] == grandchild_data["description"]
    assert response.json()[
        "data"][2]["data"]["previous"] == grandchild_data["previous"]
    assert response.json()[
        "data"][2]["data"]["next"] == grandchild_data["next"]
    assert response.json()[
        "data"][2]["data"]["text"] == grandchild_data["text"]
    assert response.json()[
        "data"][2]["data"]["tags"] == grandchild_data["tags"]

    # remove the remaining root node in the tree
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_setup_remove_and_return_subtree['original_root']}", headers=headers)
    assert response.status_code == 200

# ------------------------
#   Saves Tests
# ------------------------


@pytest.mark.asyncio
async def test_saves_list_all_saves(test_create_root_node, return_token):
    """ generate a list of all the saved tries for given account_id"""
    headers = return_token
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/saves", headers=headers)
    assert response.status_code == 200
    # test that the root node is removed as expected
    assert int(len(response.json()['data'][0])) > 0
    # remove node we created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)


@pytest.mark.asyncio
async def test_saves_get_latest_save(test_create_root_node, return_token):
    """ load the latest save into the tree for a given user """
    headers = return_token
    # the test_create_root_node fixture creates a new root node which gets saved
    # now we've loaded that into the tree, we can get the node from the tree
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads", headers=headers)
    assert response.status_code == 200
    # test that the root node is configured as expected
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["_identifier"] == test_create_root_node["node_id"]
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["_tag"] == "Unit test root node"
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["data"]["description"] == "Unit test description"
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["data"]["previous"] == "previous node"
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["data"]["next"] == "next node"
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["data"]["text"] == "Unit test text for root node"
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["data"]["tags"] == [
        'tag 1', 'tag 2', 'tag 3']

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)


@pytest.mark.asyncio
async def test_saves_get_save(test_create_root_node, return_token):
    """ load the named save into the tree for a given user """
    headers = return_token
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads/{test_create_root_node['save_id']}", headers=headers)
    assert response.status_code == 200
    # test that the root node is configured as expected
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["_identifier"] == test_create_root_node["node_id"]
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["_tag"] == "Unit test root node"
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["data"]["description"] == "Unit test description"
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["data"]["previous"] == "previous node"
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["data"]["next"] == "next node"
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["data"]["text"] == "Unit test text for root node"
    assert response.json()[
        "data"]["_nodes"][test_create_root_node["node_id"]]["data"]["tags"] == [
        'tag 1', 'tag 2', 'tag 3']

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_saves_get_a_save_for_a_valid_account_with_non_existent_document(test_create_root_node, return_token):
    """ try and load a save for a valid account_id but non-existent document id """
    headers = return_token
    # note this is a random 24 char hex string - should not exist in the target db - 16c361eff3b15de33f6a66b8
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads/16c361eff3b15de33f6a66b8", headers=headers)
    assert response.status_code == 404
    assert response.json()[
        'detail'] == "Unable to retrieve save document with id: 16c361eff3b15de33f6a66b8"
    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)


@pytest.mark.asyncio
async def test_saves_delete_all_saves(return_token):
    headers = return_token
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete("http://localhost:8000/saves", headers=headers)
    assert response.status_code == 200


# ------------------------
#       User Tests
# ------------------------

@pytest.mark.asyncio
async def test_users_update_user(return_token, dummy_user_update):
    """ Add a new user so that we can update it and delete it"""
    headers = return_token
    data = jsonable_encoder(dummy_user_update)

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.put("/users", json=data, headers=headers)
    assert response.status_code == 200
    assert response.json()[
        "data"]["name"]["firstname"] == dummy_user_update["name"]["firstname"]
    assert response.json()[
        "data"]["name"]["surname"] == dummy_user_update["name"]["surname"]
    assert response.json()[
        "data"]["email"] == dummy_user_update["email"]


@pytest.mark.asyncio
async def test_users_update_user_with_bad_payload(return_token):
    """ Add a new user so that we can update it and delete it"""
    headers = return_token
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.put(f"/users")
    assert response.status_code == 422

    # remove the user document we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.delete(f"/users")
    assert response.status_code == 200
    assert response.json()["data"] == 1


@pytest.mark.asyncio
async def test_users_delete_user(return_token):
    """ delete a user """
    headers = return_token
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.delete(f"/users")
    assert response.status_code == 200
    assert response.json()[
        "data"] == 1


@pytest.mark.asyncio
async def test_users_get_user_by_username(dummy_user_to_add, return_token):
    """ test retrieving a user document from the collection by username - no route for this"""
    headers = return_token
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.get(f"/users/me")
    assert response.json()[
        "name"]["firstname"] == dummy_user_to_add["name"]["firstname"]
    assert response.json()[
        "name"]["surname"] == dummy_user_to_add["name"]["surname"]
    assert response.json()["username"] == dummy_user_to_add["username"]
    assert pwd_context.verify(
        dummy_user_to_add["password"], response.json()["password"]) == True
    assert pwd_context.verify(
        dummy_user_to_add["username"], response.json()["account_id"]) == True
    assert response.json()["email"] == dummy_user_to_add["email"]
    assert response.json()["disabled"] == dummy_user_to_add["disabled"]
    assert response.json()["user_role"] == dummy_user_to_add["user_role"]
    assert response.json()["user_type"] == dummy_user_to_add["user_type"]
    # remove the user document we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.delete(f"/users")
    assert response.status_code == 200
    assert response.json()["data"] == 1


@pytest.mark.asyncio
async def test_users_update_password(dummy_user_to_add, return_token):
    """ test changing a user password"""

    headers = return_token
    data = jsonable_encoder({"new_password": TEST_PASSWORD_TO_CHANGE})

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.put("/users/password", json=data, headers=headers)

    assert response.status_code == 200
    assert response.is_error == False

    # login in with new password

    form_data = {
        "username": dummy_user_to_add["username"],
        "password": TEST_PASSWORD_TO_CHANGE,
        "scope": dummy_user_to_add["user_role"].replace(",", " ")
    }
    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post(f"http://localhost:8000/get_token", headers=headers, data=form_data)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_users_update_type(dummy_user_to_add, return_token):
    """ test changing a user type """

    headers = return_token
    data = jsonable_encoder({"user_type": "premium"})

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.put("/users/type", json=data, headers=headers)

    assert response.status_code == 200
    assert response.is_error == False
    assert response.json()["data"]["user_type"] == data["user_type"]


@pytest.mark.asyncio
async def test_users_logout(return_token):
    """ test changing a user type """
    headers = return_token
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get("/logout", headers=headers)

    assert response.status_code == 200
    assert response.is_error == False
    assert response.json()["data"]["Logout"] == True

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.get(f"/users/me")

    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Could not validate credentials'}

# --------------------------
#   Authentication tests
# --------------------------


@ pytest.mark.asyncio
async def test_unauth_root_path():
    """ Unauthorized return version number should fail with a 401"""
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get("/")
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}


@ pytest.mark.asyncio
async def test_unauth_create_root_node(return_token,
                                       test_get_root_node):
    """ Unauthorized Create a root node - should fail with 401"""
    headers = return_token
    # first test if there's already a root node - if there is remove it
    if test_get_root_node != None:
        async with httpx.AsyncClient(app=api.app) as client:
            response = await client.delete(f"http://localhost:8000/nodes/{test_get_root_node}", headers=headers)
        assert response.status_code == 200
        # test that the root node is removed as expected
        assert int(response.json()['data']) >= 1

    data = jsonable_encoder({
        "description": "Unit test description",
        "previous": "previous node",
                            "next": "next node",
                            "text": "Unit test text for root node",
                            "tags": ['tag 1', 'tag 2', 'tag 3']
                            })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post(f"http://localhost:8000/nodes/Unit test root node", json=data)
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}


@ pytest.mark.asyncio
async def test_unauth_remove_node(return_token, test_create_root_node: list):
    """ unauthorized generate a root node and remove it should fail with a 401"""
    headers = return_token
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}")
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}
    # remove the node we've created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
    assert response.status_code == 200


@ pytest.mark.asyncio
async def test_unauth_update_node(test_create_root_node, return_token):
    """ Unauthorised generate a root node and update it should fail with a 401"""
    headers = return_token
    data = jsonable_encoder({
        "name": "Unit test root node updated name",
        "description": "Unit test updated description",
        "previous": "previous updated node",
        "next": "next updated node",
        "text": "Unit test text for updated node",
        "tags": ['updated tag 1', 'updated tag 2', 'updated tag 3']
    })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.put(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", json=data)
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}

    # now remove the node we just added
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
    assert response.status_code == 200


@ pytest.mark.asyncio
async def test_unauth_get_a_node(test_create_root_node, return_token):
    """ Unauthorised get a single node by id should fail with a 401 """
    headers = return_token
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get(f"/nodes/{test_create_root_node['node_id']}")
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
    assert response.status_code == 200


@ pytest.mark.asyncio
async def test_unauth_add_child_node(test_create_root_node, return_token):
    """ Unauthorised add a child node should fail with a 401 """
    headers = return_token
    data = jsonable_encoder({
        "parent": test_create_root_node["node_id"],
        "description": "unit test child description",
        "previous": "previous child node",
        "next": "next child node",
        "text": "unit test text for child node",
        "tags": ['tag 1', 'tag 2', 'tag 3']
    })
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.post(f"/nodes/unit test child node", json=data)
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}

    # remove the root & child node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)


@ pytest.mark.asyncio
async def test_unauth_remove_subtree(test_setup_remove_and_return_subtree, return_token):
    """ Unauthorised remove_subtree should fail with a 401 """
    # set these two shortcuts up for ledgibility purposes
    headers = return_token
    child_node_id = test_setup_remove_and_return_subtree["test data"]["child_data"]["child_node_id"]

    # remove the specified child
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.get(f"/trees/{child_node_id}")
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}

    # remove the root & child node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_setup_remove_and_return_subtree['original_root']}", headers=headers)
    assert response.status_code == 200


@ pytest.mark.asyncio
async def test_unauth_add_subtree(test_setup_remove_and_return_subtree, return_token):
    """ Unauthorised add subtree should fail with a 401 """
    headers = return_token
    child_node_id = test_setup_remove_and_return_subtree["test data"]["child_data"]["child_node_id"]

    # prune node
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000", headers=headers) as ac:
        response = await ac.get(f"/trees/{child_node_id}")
    assert response.status_code == 200

    data = jsonable_encoder(
        {"sub_tree": response.json()["data"]})

    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.post(f"/trees/{test_setup_remove_and_return_subtree['original_root']}", json=data)
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}

    # remove the remaining root node in the tree
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_setup_remove_and_return_subtree['original_root']}", headers=headers)
    assert response.status_code == 200


@ pytest.mark.asyncio
async def test_unauth_list_all_saves(test_create_root_node, return_token):
    """ Unauthorizd generate a list of all the saves - should fail with a 401 """
    headers = return_token
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/saves")
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}
    # remove node we created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)


@ pytest.mark.asyncio
async def test_unauth_get_latest_save(test_create_root_node, return_token):
    """ load the latest save into the tree for a given user """
    headers = return_token
    # the test_create_root_node fixture creates a new root node which gets saved
    # now we've loaded that into the tree, we can get the node from the tree
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads")
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)


@ pytest.mark.asyncio
async def test_unauth_get_save(test_create_root_node, return_token):
    """ load the named save into the tree for a given user """
    headers = return_token
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads/{test_create_root_node['save_id']}")
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
    assert response.status_code == 200


@ pytest.mark.asyncio
async def test_unauth_delete_all_saves(return_token):
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete("http://localhost:8000/saves")
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}


@ pytest.mark.asyncio
async def test_unauth_update_user(return_token, dummy_user_update):
    """ Add a new user so that we can update it and delete it"""
    data = jsonable_encoder(dummy_user_update)

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.put("/users", json=data)
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}


@ pytest.mark.asyncio
async def test_unauth_delete_user(return_token):
    """ delete a user """
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.delete(f"/users")
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}


@ pytest.mark.asyncio
async def test_unauth_get_user_by_username(test_add_user, dummy_user_to_add, return_token):
    """ test retrieving a user document from the collection by username - no route for this"""
    headers = return_token
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get(f"/users/me")
    assert response.status_code == 401
    assert response.is_error == True
    assert response.json() == {'detail': 'Not authenticated'}
    # remove the user document we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.delete(f"/users")
    assert response.status_code == 200
    assert response.json()["data"] == 1


@pytest.mark.asyncio
async def test_unauth_update_password(dummy_user_to_add, return_token):
    """ test unauthorized changing a user password - should fail with 401"""

    data = jsonable_encoder({"new_password": TEST_PASSWORD_TO_CHANGE})

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.put("/users/password", json=data)

    assert response.status_code == 401
    assert response.is_error == True


@pytest.mark.asyncio
async def test_unauth_update_type(dummy_user_to_add, return_token):
    """ test changing a user type """

    headers = return_token
    data = jsonable_encoder({"user_type": "premium"})

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.put("/users/type", json=data)

    assert response.status_code == 401
    assert response.is_error == True

# -------------------------------
#   Scope (authentication) tests
# -------------------------------


@ pytest.mark.asyncio
async def test_scope_root_path(return_scoped_token):
    """ Unauthorized return version number should fail with a 403 for everything other than user:reader"""
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.get("/")
    if scopes == "tree:reader user:reader":
        assert response.status_code == 200
    else:
        assert response.status_code == 403
        assert response.is_error == True
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}


@ pytest.mark.asyncio
async def test_scope_create_root_node(return_token, return_scoped_token):
    """ Unscoped Create a root node - should fail with 403"""
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    data = jsonable_encoder({
        "description": "Unit test description",
        "previous": "previous node",
                            "next": "next node",
                            "text": "Unit test text for root node",
                            "tags": ['tag 1', 'tag 2', 'tag 3']
                            })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post(f"http://localhost:8000/nodes/Unit test root node", json=data, headers=headers)
    if scopes == "tree:writer user:reader":
        assert response.status_code == 200
        id_to_delete = response.json()["data"]["node"]["_identifier"]
        # now remove node
        headers = return_token
        async with httpx.AsyncClient(app=api.app) as ac:
            response = await ac.delete(f"http://localhost:8000/nodes/{id_to_delete}", headers=headers)
        assert response.status_code == 200
        # test that the root node is removed as expected
        assert int(response.json()['data']) >= 1
    else:
        assert response.status_code == 403
        assert response.is_error == True
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}


@ pytest.mark.asyncio
async def test_scope_remove_node(return_token, test_create_root_node, return_scoped_token):
    """ unscoped generate a root node and remove it should fail with a 403"""
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
    if scopes == "tree:writer user:reader":
        assert response.status_code == 200
    else:
        assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}
        # now remove the node
        headers = return_token
        async with httpx.AsyncClient(app=api.app) as client:
            response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
        assert response.status_code == 200


@ pytest.mark.asyncio
async def test_scope_update_node(test_create_root_node, return_token, return_scoped_token):
    """ Unscoped generate a root node and update it should fail with a 403"""
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    data = jsonable_encoder({
        "name": "Unit test root node updated name",
        "description": "Unit test updated description",
        "previous": "previous updated node",
        "next": "next updated node",
        "text": "Unit test text for updated node",
        "tags": ['updated tag 1', 'updated tag 2', 'updated tag 3']
    })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.put(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers, json=data)
    if scopes == "tree:writer user:reader":
        assert response.status_code == 200
    else:
        assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}
        # now remove the node
        headers = return_token
        async with httpx.AsyncClient(app=api.app) as client:
            response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
        assert response.status_code == 200


@ pytest.mark.asyncio
async def test_scope_get_a_node(test_create_root_node, return_token, return_scoped_token):
    """ Unscoped get a single node by id should fail with a 403 """
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.get(f"/nodes/{test_create_root_node['node_id']}")
    if scopes == "tree:reader user:reader":
        assert response.status_code == 200
    else:
        assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}
        # now remove the node
        headers = return_token
        async with httpx.AsyncClient(app=api.app) as client:
            response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
        assert response.status_code == 200


@ pytest.mark.asyncio
async def test_scope_add_child_node(test_create_root_node, return_token, return_scoped_token):
    """ Unscoped add a child node should fail with a 403 """
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    data = jsonable_encoder({
        "parent": test_create_root_node["node_id"],
        "description": "unit test child description",
        "previous": "previous child node",
        "next": "next child node",
        "text": "unit test text for child node",
        "tags": ['tag 1', 'tag 2', 'tag 3']
    })
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000", headers=headers) as ac:
        response = await ac.post(f"/nodes/unit test child node", json=data)
    if scopes == "tree:writer user:reader":
        assert response.status_code == 200
    else:
        assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}
        # now remove the node
        headers = return_token
        async with httpx.AsyncClient(app=api.app) as client:
            response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
        assert response.status_code == 200


@ pytest.mark.asyncio
async def test_scope_remove_subtree(test_setup_remove_and_return_subtree, return_token, return_scoped_token):
    """ Unscoped remove_subtree should fail with a 403 """
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    child_node_id = test_setup_remove_and_return_subtree["test data"]["child_data"]["child_node_id"]

    # remove the specified child
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000", headers=headers) as ac:
        response = await ac.get(f"/trees/{child_node_id}")
    if scopes == "tree:writer user:reader":
        assert response.status_code == 200
    else:
        assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}
        # now remove the node
        headers = return_token
        async with httpx.AsyncClient(app=api.app) as client:
            response = await client.delete(f"http://localhost:8000/nodes/{child_node_id}", headers=headers)
        assert response.status_code == 200


@ pytest.mark.asyncio
async def test_scope_add_subtree(test_setup_remove_and_return_subtree, return_token, return_scoped_token):
    """ Unscoped add subtree should fail with a 403 """
    scoped_headers = return_scoped_token["token"]
    all_scoped_headers = return_token
    scopes = return_scoped_token["scopes"]
    child_node_id = test_setup_remove_and_return_subtree["test data"]["child_data"]["child_node_id"]

    # prune node
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000", headers=all_scoped_headers) as ac:
        response = await ac.get(f"/trees/{child_node_id}")
    data = jsonable_encoder(
        {"sub_tree": response.json()["data"]})
    # now add the subtree back in
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000", headers=scoped_headers) as ac:
        response = await ac.post(f"/trees/{test_setup_remove_and_return_subtree['original_root']}", json=data)
    if scopes == "tree:writer user:reader":
        assert response.status_code == 200
    else:
        assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}
    # now remove the node regardless of success or failure of the above
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_setup_remove_and_return_subtree['original_root']}", headers=all_scoped_headers)
    assert response.status_code == 200


@ pytest.mark.asyncio
async def test_scope_list_all_saves(return_scoped_token):
    """ Unscoped generate a list of all the saves - should fail with a 403 """
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/saves", headers=headers)
    if scopes == "tree:reader user:reader":
        assert response.status_code == 200
    else:
        assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}


@ pytest.mark.asyncio
async def test_scope_get_latest_save(return_scoped_token):
    """ unscopd load the latest save into the tree for a given user should fail with a 403"""
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    # the test_create_root_node fixture creates a new root node which gets saved
    # now we've loaded that into the tree, we can get the node from the tree
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads", headers=headers)
    if scopes == "tree:reader user:reader":
        assert response.status_code == 200
    else:
        assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}


@ pytest.mark.asyncio
async def test_scope_get_save(test_create_root_node, return_token, return_scoped_token):
    """ Unscoped load the named save into the tree for a given user """
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads/{test_create_root_node['save_id']}", headers=headers)
    if scopes == "tree:reader user:reader":

        assert response.status_code == 200
    else:
        assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        headers = return_token
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['node_id']}", headers=headers)
    assert response.status_code == 200


@ pytest.mark.asyncio
async def test_scope_delete_all_saves(return_scoped_token):
    """ Unscoped delete all saves should fail with a 403 """
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete("http://localhost:8000/saves", headers=headers)
    if scopes == "tree:writer user:reader":
        assert response.status_code == 200
    else:
        assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}


@ pytest.mark.asyncio
async def test_scope_update_user(return_token, return_scoped_token, dummy_user_update):
    """ Add a new user so that we can update it and delete it"""
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    data = jsonable_encoder(dummy_user_update)

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.put("/users", json=data)
    if scopes == "user:writer user:reader":
        assert response.status_code == 200
    else:
        assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}


@ pytest.mark.asyncio
async def test_scope_delete_user(return_token, return_scoped_token):
    """ unscoped delete a user should fail with a 403"""
    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.delete(f"/users")
    if scopes == "user:writer user:reader":
        assert response.status_code == 200
    else:
        assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}


@ pytest.mark.asyncio
async def test_scope_get_user_by_username(return_simple_scoped_token):
    """ unscoped test retrieving a user document from the collection by username should fail with 403"""

    headers = return_simple_scoped_token["token"]
    scopes = return_simple_scoped_token["scopes"]
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.get(f"/users/me")

    if scopes == "user:reader":
        assert response.status_code == 200
    else:
        # assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}


@ pytest.mark.asyncio
async def test_scope_update_password(return_scoped_token):
    """ unscoped test retrieving a user document from the collection by username should fail with 403"""

    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    data = jsonable_encoder({"new_password": TEST_PASSWORD_TO_CHANGE})
    print(f"data:{data}")
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.put("/users/password", json=data, headers=headers)

    if scopes == "user:writer user:reader":
        assert response.status_code == 200
    else:
        # assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}


@pytest.mark.asyncio
async def test_scope_update_type(dummy_user_to_add, return_scoped_token):
    """ test changing a user type """

    headers = return_scoped_token["token"]
    scopes = return_scoped_token["scopes"]
    data = jsonable_encoder({"user_type": "premium"})

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", headers=headers) as ac:
        response = await ac.put("/users/type", json=data)
    if scopes == "usertype:writer user:reader":
        assert response.status_code == 200
    else:
        # assert response.is_error == True
        assert response.status_code == 403
        assert response.json() == {
            'detail': 'Insufficient permissions to complete action'}

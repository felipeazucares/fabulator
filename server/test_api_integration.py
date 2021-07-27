
import pytest
import asyncio
import httpx
import app.api as api
import app.database as database
import hashlib
import asyncio
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
    # firstname = "John"
    # surname = "Maginot"
    username_hash = hashlib.sha256(username.encode('utf-8')).hexdigest()
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
    assert response.json()["data"]["version"] == "0.0.1"
    assert response.json()["message"] == "Success"


@pytest.mark.asyncio
@pytest.fixture
async def test_get_root_node():
    """ get the root node if it exists"""
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get("/trees/root")
    assert response.status_code == 200
    # return id of root node or None
    return response.json()["data"]["root"]


@pytest.mark.asyncio
@pytest.fixture
async def test_create_root_node(get_dummy_user_account_id, test_get_root_node):
    """ Create a root node and return it """

    # first test if there's already a root node - if there is remove it
    if test_get_root_node != None:
        async with httpx.AsyncClient(app=api.app) as client:
            response = await client.delete(f"http://localhost:8000/nodes/{get_dummy_user_account_id}/{test_get_root_node}")
        assert response.status_code == 200
        # test that the root node is removed as expected
        assert int(response.json()['data']) == 1

    data = jsonable_encoder({
                            "description": "Unit test description",
                            "previous": "previous node",
                            "next": "next node",
                            "text": "Unit test text for root node",
                            "tags": ['tag 1', 'tag 2', 'tag 3']
                            })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post(f"http://localhost:8000/nodes/{get_dummy_user_account_id}/Unit test root node", json=data)

    assert response.status_code == 200
    assert response.json()["data"]["node"]["_tag"] == "Unit test root node"
    return({
        "node_id": response.json()["data"]["node"]["_identifier"],
        "account_id": get_dummy_user_account_id,
        "save_id": response.json()["data"]["object_id"]
    })


@pytest.mark.asyncio
async def test_remove_node(test_create_root_node: list):
    """ generate a root node and remove it """
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")
    assert response.status_code == 200
    # test that the root node is removed as expected
    assert int(response.json()["data"]) > 0


@pytest.mark.asyncio
async def test_add_another_root_node(test_create_root_node: list):
    """ generate a root node then try to add another"""
    data = jsonable_encoder({
        "description": "Unit test description for second root node",
        "previous": "previous node",
        "next": "next node",
        "text": "Unit test text for adding another root node",
                            "tags": ['tag 1', 'tag 2', 'tag 3']
                            })
    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.post(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/this should fail", json=data)
    assert response.status_code == 422
    # test that the root node is removed as expected
    assert response.json()["detail"] == "Tree already has a root node"


@pytest.mark.asyncio
async def test_remove_non_existent_node(test_create_root_node: list):
    """ generate a root node and remove it """
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/XXXX")
    assert response.status_code == 404
    # test that the root node is removed as expected
    assert response.json()["detail"] == "Node not found in current tree"
    # now remove the node we just added
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_remove_node_for_non_existent_user(test_create_root_node: list):
    """ generate a root node and remove it """
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/XXXX/{test_create_root_node['node_id']}")
    assert response.status_code == 404
    # test that the root node is removed as expected
    assert response.json()[
        "detail"] == "Unable to retrieve documents with account_id: XXXX"
    # now remove the node we just added
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_node(test_create_root_node):
    """ generate a root node and update it"""
    data = jsonable_encoder({
        "name": "Unit test root node updated name",
        "description": "Unit test updated description",
        "previous": "previous updated node",
        "next": "next updated node",
        "text": "Unit test text for updated node",
        "tags": ['updated tag 1', 'updated tag 2', 'updated tag 3']
    })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.put(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}", json=data)
    assert response.status_code == 200
    assert response.json()["data"]["object_id"] != None

    # now get what we just created it updated
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get(f"/nodes/{test_create_root_node['node_id']}")
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
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_node_for_non_existent_account(test_create_root_node):
    """ generate a root node and update it"""
    data = jsonable_encoder({
        "name": "Unit test root node updated name",
        "description": "Unit test updated description",
        "previous": "previous updated node",
        "next": "next updated node",
        "text": "Unit test text for updated node",
        "tags": ['updated tag 1', 'updated tag 2', 'updated tag 3']
    })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.put(f"http://localhost:8000/nodes/XXXX/{test_create_root_node['node_id']}", json=data)
    assert response.status_code == 404
    assert response.json()[
        'detail'] == "Unable to retrieve documents with account_id: XXXX"

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_node_for_non_existent_node(test_create_root_node):
    """ generate a root node and update it"""
    data = jsonable_encoder({
        "name": "Unit test root node updated name",
        "description": "Unit test updated description",
        "previous": "previous updated node",
        "next": "next updated node",
        "text": "Unit test text for updated node",
        "tags": ['updated tag 1', 'updated tag 2', 'updated tag 3']
    })

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.put(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/XXXX", json=data)
    assert response.status_code == 404
    # test that an error state is generated as expected
    assert response.json()[
        "detail"] == "Node not found in current tree"

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_node_with_bad_payload(test_create_root_node):
    """ update a node with a bad payload"""

    async with httpx.AsyncClient(app=api.app) as ac:
        response = await ac.put(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")
    assert response.status_code == 422
    # test that an error state is generated as expected

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_node_with_non_existent_parent(test_create_root_node):
    """ generate a root node and update it with a non existent parent"""
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
        response = await ac.put(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}", json=data)
    assert response.status_code == 422
    assert response.json()[
        'detail'] == "Parent XXXX is missing from tree"

    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_a_node(test_create_root_node):
    """ get a single node by id"""
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get(f"/nodes//nodes{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")
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
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")


@pytest.mark.asyncio
async def test_get_a_non_existent_node():
    """ get a non-existent node by id"""
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get(f"/nodes/{test_create_root_node['account_id']}/xxx")
    assert response.status_code == 404
    # test that an error state is generated as expected
    assert response.json()[
        "detail"] == "Node not found in current tree"


@pytest.mark.asyncio
async def test_add_child_node(test_create_root_node):
    """ Add a child node"""
    data = jsonable_encoder({
        "parent": test_create_root_node["node_id"],
        "description": "unit test child description",
        "previous": "previous child node",
        "next": "next child node",
        "text": "unit test text for child node",
        "tags": ['tag 1', 'tag 2', 'tag 3']
    })
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.post(f"/nodes/{test_create_root_node['account_id']}/unit test child node", json=data)
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
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")


@pytest.mark.asyncio
async def test_add_child_node_with_invalid_parent(test_create_root_node):
    """ Add a child node with invalid parent"""
    data = jsonable_encoder({
        "parent": "XXXX",
        "description": "unit test child description",
        "previous": "previous child node",
        "next": "next child node",
        "text": "unit test text for child node",
        "tags": ['tag 1', 'tag 2', 'tag 3']
    })
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.post(f"/nodes/{test_create_root_node['account_id']}/unit test child node", json=data)
    assert response.status_code == 422
    assert response.json()[
        "detail"] == "Parent XXXX is missing from tree"

    # remove the root & child node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")


@pytest.mark.asyncio
async def test_remove_subtree(test_create_root_node):
    """ Add a child node"""
    child_data = jsonable_encoder({
        "parent": test_create_root_node["node_id"],
        "description": "unit test child description",
        "previous": "previous child node",
        "next": "next child node",
        "text": "unit test text for child node",
        "tags": ['tag 1', 'tag 2', 'tag 3']
    })

    # add child node to root
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.post(f"/nodes/{test_create_root_node['account_id']}/unit test child node", json=child_data)
    assert response.status_code == 200
    child_node_id = response.json()["data"]["node"]["_identifier"]
    # now build grandchild data using item returned from above post

    grandchild_data = jsonable_encoder({
        "parent": child_node_id,
        "description": "unit test grandchild description",
        "previous": "nothing",
        "next": "nothing",
        "text": "unit test text for grandchild node",
        "tags": ['tag 4', 'tag 5', 'tag 6']
    })
    # create grandchild node
    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.post(f"/nodes/{test_create_root_node['account_id']}/unit test grandchild node", json=grandchild_data)
    assert response.status_code == 200
    grandchild_node_id = response.json()["data"]["node"]["_identifier"]

    # now remove the child & grandchild subtree

    async with httpx.AsyncClient(app=api.app, base_url=f"http://localhost:8000") as ac:
        response = await ac.get(f"/trees/{test_create_root_node['account_id']}/{child_node_id}")
    assert response.status_code == 200

    assert child_node_id in response.json()[
        "data"]["_nodes"]
    assert grandchild_node_id in response.json()[
        "data"]["_nodes"]
    assert response.json()["data"]["root"] == child_node_id
    assert response.json()[
        "data"]["_nodes"][child_node_id][
        "data"]["description"] == child_data["description"]
    assert response.json()[
        "data"]["_nodes"][child_node_id]["data"]["previous"] == child_data["previous"]
    assert response.json()[
        "data"]["_nodes"][child_node_id]["data"]["next"] == child_data["next"]
    assert response.json()[
        "data"]["_nodes"][child_node_id]["data"]["text"] == child_data["text"]
    assert response.json()[
        "data"]["_nodes"][child_node_id]["data"]["tags"] == child_data["tags"]

    assert response.json()[
        "data"]["_nodes"][grandchild_node_id][
        "data"]["description"] == grandchild_data["description"]
    assert response.json()[
        "data"]["_nodes"][grandchild_node_id]["data"]["previous"] == grandchild_data["previous"]
    assert response.json()[
        "data"]["_nodes"][grandchild_node_id]["data"]["next"] == grandchild_data["next"]
    assert response.json()[
        "data"]["_nodes"][grandchild_node_id]["data"]["text"] == grandchild_data["text"]
    assert response.json()[
        "data"]["_nodes"][grandchild_node_id]["data"]["tags"] == grandchild_data["tags"]
    # remove the root & child node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")


@pytest.mark.asyncio
async def test_get_all_nodes(test_create_root_node):
    """ get all nodes and test the root"""
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get(f"/nodes{test_create_root_node['account_id']}")
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
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")


@pytest.mark.asyncio
async def test_get_filtered_nodes(test_create_root_node):
    """ get all nodes and test the root"""
    params = {"filterval": "tag 1"}
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000", params=params) as ac:
        response = await ac.get(f"/nodes{test_create_root_node['account_id']}")
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
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")


@pytest.mark.asyncio
async def test_list_all_saves(get_dummy_user_account_id):
    """ generate a list of all the saved tries for given account_id"""
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/saves/{get_dummy_user_account_id}")
    assert response.status_code == 200
    # test that the root node is removed as expected
    assert int(len(response.json()['data'][0])) > 0


@pytest.mark.asyncio
async def test_get_latest_save(test_create_root_node):
    """ load the latest save into the tree for a given user """

    # the test_create_root_node fixture creates a new root node which gets saved
    # now we've loaded that into the tree, we can get the node from the tree
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads/{test_create_root_node['account_id']}")
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
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")


@pytest.mark.asyncio
async def test_get_latest_save_for_non_existent_user():
    """ load the latest save into the tree for a given user """
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads/XXXX")
    assert response.status_code == 404
    assert response.json()[
        'detail'] == "Unable to locate saves for account_id:XXXX"


@pytest.mark.asyncio
async def test_get_save(test_create_root_node):
    """ load the named save into the tree for a given user """

    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads/{test_create_root_node['account_id']}/{test_create_root_node['save_id']}")
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
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")


@pytest.mark.asyncio
async def test_get_a_save_for_non_existent_user(test_create_root_node):
    """ try and load a specified save for an invalid account_id"""
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads/XXXX/{test_create_root_node['save_id']}")
    assert response.status_code == 404
    assert response.json()[
        'detail'] == "Unable to retrieve documents with account_id: XXXX"
    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")


@pytest.mark.asyncio
async def test_get_a_save_for_a_valid_account_with_non_existent_document(test_create_root_node):
    """ try and load a save for a valid account_id but non-existent document id """
    # note this is a random 24 char hex string - should not exist in the target db - 16c361eff3b15de33f6a66b8
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads/{test_create_root_node['account_id']}/16c361eff3b15de33f6a66b8")
    assert response.status_code == 404
    assert response.json()[
        'detail'] == "Unable to retrieve save document with id: 16c361eff3b15de33f6a66b8"
    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")


@pytest.mark.asyncio
async def test_get_a_save_for_an_invalid_account_with_invalid_document(test_create_root_node):
    """ try and load a save for a valid account_id but invalid document id """
    # note this is a random 24 char hex string - should not exist in the target db
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.get(f"http://localhost:8000/loads/{test_create_root_node['account_id']}/xxxx")
    assert response.status_code == 500
    assert response.json()[
        'detail'] == "Error occured retrieving count of save documents for document save_id: xxxx: 'xxxx' is not a valid ObjectId, it must be a 12-byte input or a 24-character hex string"
    # remove the root node we just created
    async with httpx.AsyncClient(app=api.app) as client:
        response = await client.delete(f"http://localhost:8000/nodes/{test_create_root_node['account_id']}/{test_create_root_node['node_id']}")


@pytest.mark.asyncio
async def test_delete_all_saves(get_dummy_user_account_id):
    db_storage = database.TreeStorage(
        collection_name="tree_collection")
    remove_response = await db_storage.delete_all_saves(account_id=get_dummy_user_account_id)
    assert remove_response > 0


@pytest.fixture
def dummy_user_to_add():
    return {
        "name": {"firstname": "John", "surname": "Maginot"},
        "username": "unittestuser",
        "account_id": None,
        "email": "john_maginot@fictional.com"
    }


@pytest.fixture
def dummy_user_update():
    username = "unittestuser2"
    return {
        "name": {"firstname": "Jango", "surname": "Fett"},
        "username": username,
        "account_id": hashlib.sha256(username.encode('utf-8')).hexdigest(),
        "email": "jango_fett@runsheadless.com"
    }


@pytest.fixture
@pytest.mark.asyncio
async def test_add_user(dummy_user_to_add):
    """ Add a new user so that we can update it and delete it"""

    username = "unittestuser"
    username_hash = hashlib.sha256(username.encode('utf-8')).hexdigest()
    data = jsonable_encoder(dummy_user_to_add)

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.post(f"/users", json=data)
    assert response.status_code == 200
    assert response.json()[
        "data"]["name"]["firstname"] == dummy_user_to_add["name"]["firstname"]
    assert response.json()[
        "data"]["name"]["surname"] == dummy_user_to_add["name"]["surname"]
    assert response.json()[
        "data"]["username"] == dummy_user_to_add["username"]
    assert response.json()[
        "data"]["account_id"] == username_hash
    assert response.json()[
        "data"]["email"] == dummy_user_to_add["email"]
    # return id of record created
    return(response.json()["data"]["id"])


@pytest.mark.asyncio
async def test_get_user(test_add_user, dummy_user_to_add):
    """ test reading a user document from the collection """
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get(f"/users/{test_add_user}")
    assert response.status_code == 200
    assert response.json()[
        "data"]["name"]["firstname"] == dummy_user_to_add["name"]["firstname"]
    assert response.json()[
        "data"]["name"]["surname"] == dummy_user_to_add["name"]["surname"]
    assert response.json()[
        "data"]["username"] == dummy_user_to_add["username"]
    assert response.json()[
        "data"]["account_id"] == hashlib.sha256(
        dummy_user_to_add["username"].encode('utf-8')).hexdigest()
    assert response.json()[
        "data"]["email"] == dummy_user_to_add["email"]
    # remove the user document we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.delete(f"/users/{test_add_user}")
    assert response.status_code == 200
    assert response.json()["data"] == 1


@pytest.mark.asyncio
async def test_get_non_existent_user(test_add_user):
    """ test reading a user document from the collection """
    # note this string is random 24 char hex code but should exist as a user record - 16c361eff3b15de33f6a66b8
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.get(f"/users/16c361eff3b15de33f6a66b8")
    assert response.status_code == 404
    assert response.json()[
        "detail"] == "No user record found for id:16c361eff3b15de33f6a66b8"
    # remove the user document we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.delete(f"/users/{test_add_user}")
    assert response.status_code == 200
    assert response.json()["data"] == 1


@pytest.mark.asyncio
async def test_update_user(test_add_user, dummy_user_update):
    """ Add a new user so that we can update it and delete it"""
    # set up unit test user

    username_hash = hashlib.sha256(
        dummy_user_update["username"].encode('utf-8')).hexdigest()

    data = jsonable_encoder(dummy_user_update)

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.put(f"/users/{test_add_user}", json=data)
    assert response.status_code == 200
    assert response.json()[
        "data"]["name"]["firstname"] == dummy_user_update["name"]["firstname"]
    assert response.json()[
        "data"]["name"]["surname"] == dummy_user_update["name"]["surname"]
    assert response.json()[
        "data"]["username"] == dummy_user_update["username"]
    assert response.json()[
        "data"]["account_id"] == username_hash
    assert response.json()[
        "data"]["email"] == dummy_user_update["email"]

    # remove the user document we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.delete(f"/users/{test_add_user}")
    assert response.status_code == 200
    assert response.json()["data"] == 1


@pytest.mark.asyncio
async def test_update_user_with_bad_payload(test_add_user):
    """ Add a new user so that we can update it and delete it"""

    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.put(f"/users/{test_add_user}")
    assert response.status_code == 422

    # remove the user document we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.delete(f"/users/{test_add_user}")
    assert response.status_code == 200
    assert response.json()["data"] == 1


@pytest.mark.asyncio
async def test_update_non_existent_user(test_add_user, dummy_user_update):
    """ test updating a non_existing user document from the collection """
    data = jsonable_encoder(dummy_user_update)
    # note this string is random 24 char hex code but should exist as a user record - 16c361eff3b15de33f6a66b8
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.put(f"/users/16c361eff3b15de33f6a66b8", json=data)
    assert response.status_code == 404
    assert response.json()[
        "detail"] == "No user record found for id:16c361eff3b15de33f6a66b8"
    # remove the user document we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.delete(f"/users/{test_add_user}")
    assert response.status_code == 200
    assert response.json()["data"] == 1


@pytest.mark.asyncio
async def test_delete_user(test_add_user):
    """ delete a user """
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.delete(f"/users/{test_add_user}")
    assert response.status_code == 200
    assert response.json()[
        "data"] == 1


@pytest.mark.asyncio
async def test_delete_non_existent_user(test_add_user):
    """ test deleting a non_existing user document from the collection """
    # note this string is random 24 char hex code but should exist as a user record - 16c361eff3b15de33f6a66b8
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.delete(f"/users/16c361eff3b15de33f6a66b8")
    assert response.status_code == 404
    assert response.json()[
        "detail"] == "No user record found for id:16c361eff3b15de33f6a66b8"
    # remove the user document we just created
    async with httpx.AsyncClient(app=api.app, base_url="http://localhost:8000") as ac:
        response = await ac.delete(f"/users/{test_add_user}")
    assert response.status_code == 200
    assert response.json()["data"] == 1

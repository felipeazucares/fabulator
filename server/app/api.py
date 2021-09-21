from logging import currentframe
import os
import app.config  # loads the load_env lib to access .env file
import app.helpers as helpers
from app.authentication import Authentication
from treelib import Tree
from fastapi import FastAPI, HTTPException, Body, Depends, status
from typing import Optional
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer

from .database import (
    TreeStorage,
    UserStorage
)
from .models import (
    SubTree,
    RequestAddSchema,
    RequestUpdateSchema,
    NodePayload,
    UserDetails,
    UserAccount,
    Token,
    TokenData,
    ResponseModel
)


# set env variables flag

DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = os.getenv('ALGORITHM')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES'))
TEST_USERNAME_TO_ADD = os.getenv(key="TESTUSERTOADD")
TEST_PASSWORD_TO_ADD = os.getenv(key="TESTPWDTOADD")
TEST_USERNAME_TO_UPDATE = os.getenv(key="TESTUSERTOUPDATE")
TEST_PASSWORD_TO_UPDATE = os.getenv(key="TESTPWDTOUPDATE")

console_display = helpers.ConsoleDisplay()

if DEBUG:
    console_display.show_debug_message(
        message_to_show=f"Environment variable DEBUG is :{DEBUG}")


# ------------------------
#      FABULATOR
# ------------------------
app = FastAPI()
version = "0.1.0"

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
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="get_token")
oauth = Authentication()


# ------------------------
#     API Helper Class
# ------------------------


class RoutesHelper():
    """ helper class containg API route utility functions"""

    def __init__(self):
        # probably create an instance of db_storeage
        self.db_storage = TreeStorage(collection_name="tree_collection")
        self.user_storage = UserStorage(collection_name="user_collection")
        self.console_display = helpers.ConsoleDisplay()
        self.DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')

    async def account_id_exists(self, account_id):
        self.account_id = account_id
        if self.DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"account_id_exists({self.account_id}) called")
        try:
            does_account_exist = await self.user_storage.does_account_exist(account_id=self.account_id)
            if self.DEBUG:
                self.console_display.show_debug_message(
                    message_to_show=f"account_exists: {does_account_exist}")
            return does_account_exist
        except Exception as e:
            console_display.show_exception_message(
                message_to_show=f"Error occured retrieving count of saves for {self.account_id}")
            print(e)
            raise HTTPException(
                status_code=500, detail=f"Error occured retrieving details for {account_id} : {e}")

    async def save_document_exists(self, document_id):
        self.document_id = document_id
        if self.DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"save_document_exists({self.document_id}) called")
        try:
            saves_count = await self.db_storage.check_if_document_exists(save_id=self.document_id)
            if self.DEBUG:
                console_display.show_debug_message(
                    message_to_show=f"check_if_document_exists returned: {saves_count}")
            if saves_count > 0:
                return True
            else:
                return False
        except Exception as e:
            console_display.show_exception_message(
                message_to_show=f"Error occured retrieving count of saves for {self.document_id}")
            print(e)
            raise HTTPException(
                status_code=500, detail=f"Error occured retrieving count of save documents for document save_id: {self.document_id}: {e}")

    async def user_document_exists(self, user_id):
        self.user_id = user_id
        if self.DEBUG:
            self.console_display.show_debug_message(
                message_to_show=f"user_document_exists({self.user_id}) called")
        try:
            document_count = await self.user_storage.check_if_user_exists(user_id=self.user_id)
            if self.DEBUG:
                console_display.show_debug_message(
                    message_to_show=f"check_if_document_exists returned: {self.user_id}")
            if document_count > 0:
                return True
            else:
                return False
        except Exception as e:
            console_display.show_exception_message(
                message_to_show=f"Error occured retrieving user document for {self.user_id}")
            print(e)
            raise HTTPException(
                status_code=500, detail=f"Error occured retrieving count of user documents user_id: {self.user_id}: {e}")


# ------------------------
#       API Routes
# ------------------------

# ----------------------------
#     Authenticaton routines
# ----------------------------

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY,
                             algorithms=[ALGORITHM])
        account_id: str = payload.get("sub")
        print(f"account_id:{account_id}")
        if account_id is None:
            raise credentials_exception
        token_data = TokenData(username=account_id)
    except JWTError:
        raise credentials_exception
    user = await oauth.get_user_by_account_id(account_id=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: UserDetails = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_active_user_account(current_user: UserDetails = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user.account_id


@app.post("/get_token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await oauth.authenticate_user(
        form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # creates a token for a given user with an expiry in minutes
    access_token = oauth.create_access_token(
        data={"sub": user.account_id}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me/", response_model=UserDetails)
async def read_users_me(current_user: UserDetails = Depends(get_current_active_user)):
    return current_user


# ------------------------
#         Misc
# ------------------------


def initialise_tree():
    """ Create a new Tree and return it"""
    global tree
    tree = Tree()
    return tree


@ app.get("/")
async def get(current_user: UserDetails = Depends(get_current_active_user)) -> dict:
    """ Return the API version """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if current_user:
        if DEBUG:
            console_display.show_debug_message(
                message_to_show="debug message - Get() Called")

    return ResponseModel(data={"version": version, "username": current_user.username}, message="Success")

# ------------------------
#         Trees
# ------------------------


@ app.get("/trees/root")
async def get_tree_root(account_id: UserAccount = Depends(get_current_active_user_account)) -> dict:
    """ return the id of the root node on current tree if there is one"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_tree_root() called")
    try:
        root_node = tree.root
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured calling tree.root on current tree")
        print(e)
        raise
    data = root_node
    return ResponseModel(data={"root": data}, message="Success")


@ app.get("/trees/{id}")
async def prune_subtree(id: str, account_id: UserAccount = Depends(get_current_active_user_account)) -> dict:
    """ cut a node & children specified by supplied id"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    # first check if the account_id exists - if it doesn't do nothing
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        if DEBUG:
            routes_helper.console_display.show_debug_message(
                f"prune_subtree({id}) called")
        if tree.contains(id):
            try:
                response = tree.remove_subtree(id)
                message = "Success"
            except Exception as e:
                routes_helper.console_display.show_exception_message(
                    message_to_show="Error occured removing a subtree from the working tree. id: {id}")
                print(e)
                raise
            try:
                db_storage = TreeStorage(
                    collection_name="tree_collection")
                await db_storage.save_working_tree(tree=tree, account_id=account_id)
            except Exception as e:
                routes_helper.console_display.show_exception_message(
                    message_to_show="Error occured saving the working tree to the database after delete.")
                print(e)
                raise
        else:
            raise HTTPException(
                status_code=404, detail="Node not found in current tree")
        return ResponseModel(response, message)
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")


@ app.post("/trees/{id}")
async def graft_subtree(id: str, request: SubTree = Body(...), account_id: UserAccount = Depends(get_current_active_user_account)) -> dict:
    """ paste a subtree & beneath the node specified"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    # first check if the account_id exists - if it doesn't do nothing
    routes_helper = RoutesHelper()
    db_storage = TreeStorage(collection_name="tree_collection")
    if await routes_helper.account_id_exists(account_id=account_id):
        if DEBUG:
            routes_helper.console_display.show_debug_message(
                f"graft_subtree({id}) called")
        if tree.contains(id):
            # turn dict object into a Tree
            try:
                sub_tree = db_storage.build_tree_from_dict(
                    tree_dict=request.sub_tree)
            except Exception as e:
                routes_helper.console_display.show_exception_message(
                    message_to_show=f"Error occured building the subtree from the request dict object. {e}")
                raise HTTPException(
                    status_code=500, detail=f"Error occured building the subtree from the request dict object. {e}")
            try:
                if DEBUG:
                    tree.save2file(
                        'dump.txt', line_type=u'ascii-ex', idhidden=False)
                tree.paste(nid=id, new_tree=sub_tree, deep=False)
                message = "Success"
            except Exception as e:
                routes_helper.console_display.show_exception_message(
                    message_to_show=f"Error occured grafting the subtree into the working tree. id: {id} {e}")
                raise
            try:
                await db_storage.save_working_tree(tree=tree, account_id=account_id)
            except Exception as e:
                routes_helper.console_display.show_exception_message(
                    message_to_show="Error occured saving the working tree to the database after paste action.{e}")
                raise
        else:
            raise HTTPException(
                status_code=404, detail="Node not found in current tree")
        return ResponseModel("Graft complete", message)
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")

# ------------------------
#          Nodes
# ------------------------


@ app.get("/nodes")
async def get_all_nodes(filterval: Optional[str] = None, account_id: UserAccount = Depends(get_current_active_user_account)) -> dict:
    """ Get a list of all the nodes in the working tree"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        if DEBUG:
            console_display.show_debug_message(
                message_to_show=f"get_all_nodes({filterval}) called")
        if filterval:
            data = []
            for node in tree.all_nodes():
                if filterval in node.data.tags:
                    data.append(node)
            if DEBUG:
                console_display.show_debug_message(
                    message_to_show=f"Nodes filtered on {filterval}")
        else:
            try:
                tree.show(line_type="ascii-em")
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show="Error occured calling tree.show on tree")
                raise HTTPException(
                    status_code=500, detail="Error occured calling tree.show on tree")
            data = tree.all_nodes()
        return ResponseModel(data=data, message="Success")
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")


@ app.get("/nodes/{id}")
async def get_a_node(id: str, account_id: UserAccount = Depends(get_current_active_user_account)) -> dict:
    """ Return a node specified by supplied id"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        if DEBUG:
            console_display.show_debug_message(
                message_to_show=f"get_a_node({id}) called")
            console_display.show_debug_message(
                message_to_show=f"node: {tree.get_node(id)}")
        if tree.contains(id):
            node = tree.get_node(id)
        else:
            raise HTTPException(
                status_code=404, detail="Node not found in current tree")
        return ResponseModel(node, "Success")
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")


@ app.post("/nodes/{name}")
async def create_node(name: str, request: RequestAddSchema = Body(...), account_id: UserAccount = Depends(get_current_active_user_account)) -> dict:
    """ Add a node to the working tree using name supplied """
    # todo: check for pre-existence of account
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    # map the incoming fields from the https request to the fields required by the treelib API
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"create_node({name}) called")
    global tree
    try:
        request = jsonable_encoder(request)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured encoding request with jsonable_encoder")
        print(e)
        raise HTTPException(
            status_code=500, detail="Error occured encoding request with jsonable_encoder: {e}")

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
        # check that the parent node exists before updating
        if tree.contains(request["parent"]):
            try:
                new_node = tree.create_node(
                    name, parent=request["parent"], data=node_payload)
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show="Error occured adding child node to working tree")
                console_display.show_exception_message(
                    message_to_show=f"request['name']:{request['name']}, data:{node_payload}, request['parent']:{request['parent']}")
                print(e)
                raise HTTPException(
                    status_code=500, detail=f"request['name']:{request['name']}, data:{node_payload}, request['parent']:{request['parent']}:{e} ")
        else:
            raise HTTPException(
                status_code=422, detail=f"Parent {request['parent']} is missing from tree")
    else:
        # No parent so check if we already have a root
        if tree.root == None:
            try:
                new_node = tree.create_node(
                    name, data=node_payload)
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show="Error occured adding root node to working tree")
                console_display.show_exception_message(
                    message_to_show=f"request['name']:{request['name']}, data:{node_payload}")
                print(e)
                raise HTTPException(
                    status_code=500, detail=f"request['name']:{request['name']}, data:{node_payload}:{e}")
        else:
            raise HTTPException(
                status_code=422, detail="Tree already has a root node")
    try:
        db_storage = TreeStorage(collection_name="tree_collection")
        save_result = await db_storage.save_working_tree(tree=tree, account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured saving the working tree to the database")
        print(e)
        raise HTTPException(
            status_code=500, detail=f"Error occured saving the working tree to the database: {e}")
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"mongo save: {save_result}")
    return ResponseModel({"node": new_node, "object_id": save_result}, "Success")


@ app.put("/nodes/{id}")
async def update_node(id: str, request: RequestUpdateSchema = Body(...), account_id: UserAccount = Depends(get_current_active_user_account)) -> dict:
    """ Update a node in the working tree identified by supplied id"""
    # generate a new id for the node if we have a parent
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    global tree
    if DEBUG:
        console_display.show_debug_message(
            f"update_node({id}) called")
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        # test if node exists
        if tree.contains(id):
            node_payload = NodePayload(description=request.description,
                                       previous=request.previous, next=request.next, tags=request.tags, text=request.text)
            if request.name:
                # if a parent is specified in the request ensure that it exists
                if request.parent:
                    if tree.contains(request.parent):
                        try:
                            tree.update_node(
                                id, _tag=request.name, data=node_payload, parent=request.parent)
                        except Exception as e:
                            console_display.show_exception_message(
                                message_to_show="Error occured updating node in the working tree")
                            console_display.show_exception_message(
                                message_to_show=f"id:{id}, request.name:{request.name}, data:{node_payload}")
                            print(e)
                            raise
                    else:
                        raise HTTPException(
                            status_code=422, detail=f"Parent {request.parent} is missing from tree")
                else:
                    try:
                        tree.update_node(
                            id, _tag=request.name, data=node_payload)
                    except Exception as e:
                        console_display.show_exception_message(
                            message_to_show="Error occured updating node in the working tree")
                        console_display.show_exception_message(
                            message_to_show=f"id:{id}, request.name:{request.name}, data:{node_payload}")
                        print(e)
                        raise

            else:
                if request.parent:
                    if tree.contains(request.parent):
                        try:
                            tree.update_node(
                                id, data=node_payload, parent=request.parent)
                        except Exception as e:
                            console_display.show_exception_message(
                                message_to_show="Error occured updating node in the working tree")
                            console_display.show_exception_message(
                                message_to_show=f"id:{id}, request.name:{request.name}, data:{node_payload}")
                            print(e)
                            raise
                    else:
                        raise HTTPException(
                            status_code=422, detail=f"Parent {request.parent} is missing from tree")

            try:
                db_storage = TreeStorage(collection_name="tree_collection")
                save_result = await db_storage.save_working_tree(tree=tree, account_id=account_id)
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show="Error occured saving the working_tree to the database")
                print(e)
                raise

            if DEBUG:
                console_display.show_debug_message(
                    message_to_show=f"save_result: {save_result}")
            return ResponseModel({"object_id": save_result}, "Success")
        else:
            raise HTTPException(
                status_code=404, detail="Node not found in current tree")
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")


@ app.delete("/nodes/{id}")
async def delete_node(id: str, account_id: UserAccount = Depends(get_current_active_user_account)) -> dict:
    """ Delete a node from the working tree identified by supplied id """
    # remove the node with the supplied id
    # todo: probably want to stash the children somewhere first in a sub tree for later use
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    routes_helper = RoutesHelper()
    global tree
    if await routes_helper.account_id_exists(account_id=account_id):
        if DEBUG:
            console_display.show_debug_message(
                f"delete_node({id}) called")
        if tree.contains(id):
            try:
                response = tree.remove_node(id)
                message = "Success"
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show="Error occured removing a node from the working tree. id: {id}")
                print(e)
                raise
            else:
                try:
                    db_storage = TreeStorage(collection_name="tree_collection")
                    await db_storage.save_working_tree(tree=tree, account_id=account_id)
                except Exception as e:
                    console_display.show_exception_message(
                        message_to_show="Error occured saving the working tree to the database after delete.")
                    print(e)
                    raise
        else:
            raise HTTPException(
                status_code=404, detail="Node not found in current tree")
        return ResponseModel(response, message)
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")


# ------------------------
#          Loads
# ------------------------


@ app.get("/loads")
async def get_latest_save(account_id: UserDetails = Depends(get_current_active_user_account)) -> dict:
    """ Return the latest saved tree in the db collection"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_latest_save()called")
    global tree
    # check to see if the account_id exists in the db
    db_storage = TreeStorage(collection_name="tree_collection")
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        try:
            tree = await db_storage.load_latest_into_working_tree(account_id=account_id)
        except Exception as e:
            console_display.show_exception_message(
                message_to_show="Error occured loading latest save into working tree")
            print(e)
            raise HTTPException(
                status_code=500, detail=f"Error occured loading latest save into working tree: {e}")
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to locate saves for account_id:{account_id}")

    return ResponseModel(jsonable_encoder(tree), "Success")


@ app.get("/loads/{save_id}")
async def get_a_save(save_id: str, account_id: UserDetails = Depends(get_current_active_user_account)) -> dict:
    """ Return the specfied saved tree in the db collection"""
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_a_save({save_id} called")
    global tree
    db_storage = TreeStorage(collection_name="tree_collection")
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        if await routes_helper.save_document_exists(document_id=save_id):
            try:
                db_storage = TreeStorage(collection_name="tree_collection")
                tree = await db_storage.load_save_into_working_tree(save_id=save_id)
            except Exception as e:
                console_display.show_exception_message(
                    message_to_show=f"Error occured loading specified save into working tree. save_id:{save_id}")
                print(e)
                raise HTTPException(
                    status_code=500, detail=f"Error occured loading specified save into working tree. save_id: {save_id}: {e}")
        else:
            raise HTTPException(
                status_code=404, detail=f"Unable to retrieve save document with id: {save_id}")
    else:
        raise HTTPException(
            status_code=404, detail=f"Unable to retrieve documents with account_id: {account_id}")

    return ResponseModel(jsonable_encoder(tree), "Success")

# ------------------------
#          Saves
# ------------------------


@ app.get("/saves")
async def get_all_saves(account_id: UserDetails = Depends(get_current_active_user_account)) -> dict:
    """ Return a dict of all the trees saved in the db collection """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    try:
        db_storage = TreeStorage(collection_name="tree_collection")
        all_saves = await db_storage.list_all_saved_trees(account_id=account_id)
        # all_saves = await list_all_saved_trees(account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured loading all saves")
        raise HTTPException(
            status_code=500, detail="Error occured loading all saves: {e}")
    if DEBUG:
        console_display.show_debug_message(
            message_to_show=f"get_all_saves{account_id} called")

    return ResponseModel(jsonable_encoder(all_saves), "Success")


@ app.delete("/saves")
async def delete_saves(account_id: UserDetails = Depends(get_current_active_user_account)) -> dict:
    """ Delete all saves from the db trees collection """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            f"delete_saves({account_id},{id}) called")
    global tree
    try:
        db_storage = TreeStorage(collection_name="tree_collection")
        delete_result = await db_storage.delete_all_saves(account_id=account_id)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured deleting  all saves for account_id:{account_id}")
        print(e)
        raise
    result = ResponseModel(delete_result, "Documents removed.")
    return result


# ------------------------
#          Users
# ------------------------

@ app.post("/users")
async def save_user(request: UserDetails = Body(...)) -> dict:
    """ save a user to users collection """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    # hash the password & username before storage
    request.account_id = pwd_context.hash(request.username)
    request.password = pwd_context.hash(request.password)
    if DEBUG:
        console_display.show_debug_message(
            f"save_user({request}) called")
    try:
        db_storage = UserStorage(collection_name="user_collection")
        save_result = await db_storage.save_user_details(user=request)
    except Exception as e:
        console_display.show_exception_message(
            message_to_show="Error occured saving user details:{account_id}")
        raise
    result = ResponseModel(save_result, "new user added")
    return result


@ app.get("/users/{id}")
async def get_user(id: str, account_id: UserDetails = Depends(get_current_active_user_account)) -> dict:
    """ get a user's details from users collection """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            f"get_user({id}) called")
    routes_helper = RoutesHelper()
    if await routes_helper.user_document_exists(user_id=id):
        try:
            db_storage = UserStorage(collection_name="user_collection")
            get_result = await db_storage.get_user_details_by_id(id=id)
        except Exception as e:
            console_display.show_exception_message(
                message_to_show="Error occured getting user details:{id}")
            raise
        result = ResponseModel(get_result, "user found")
        return result
    else:
        raise HTTPException(
            status_code=404, detail=f"No user record found for id:{id}")


@ app.put("/users/{id}")
async def update_user(id: str, request: UserDetails = Body(...), account_id: UserDetails = Depends(get_current_active_user_account)) -> dict:
    """ update a user document """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    # if there's a password in the update then hash it
    if request.password:
        request.password = pwd_context.hash(request.password)
    if DEBUG:
        console_display.show_debug_message(
            f"update_user({request}) called")
    routes_helper = RoutesHelper()
    if await routes_helper.user_document_exists(user_id=id):
        try:
            db_storage = UserStorage(collection_name="user_collection")
            update_result = await db_storage.update_user_details(id=id, user=request)
        except Exception as e:
            console_display.show_exception_message(
                message_to_show="Error occured updating user details:{account_id}")
            raise
        result = ResponseModel(update_result, f"user {id} updated")
        return result
    else:
        raise HTTPException(
            status_code=404, detail=f"No user record found for id:{id}")


@ app.delete("/users")
async def delete_user(account_id: UserDetails = Depends(get_current_active_user_account)) -> dict:
    """ delete a user from users collection """
    DEBUG = bool(os.getenv('DEBUG', 'False') == 'True')
    if DEBUG:
        console_display.show_debug_message(
            f"delete_user({account_id}) called")
    routes_helper = RoutesHelper()
    if await routes_helper.account_id_exists(account_id=account_id):
        try:
            db_storage = UserStorage(collection_name="user_collection")
            delete_result = await db_storage.delete_user_details_by_account_id(account_id=account_id)
        except Exception as e:
            console_display.show_exception_message(
                message_to_show="Error occured deleteing user details:{account_id}")
            raise
        result = ResponseModel(delete_result, "new user added")
        return result
    else:
        raise HTTPException(
            status_code=404, detail=f"No user record found for id:{account_id}")

# Create global tree & subtrees
tree = initialise_tree()
sub_tree = tree

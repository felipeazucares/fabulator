import os
from contextlib import asynccontextmanager
from pydantic import ValidationError
import app.config  # loads the load_env lib to access .env file
from app.helpers import get_logger
from app.authentication import Authentication
from treelib import Tree
from fastapi import FastAPI, HTTPException, Body, Depends, Security, status, Path
from typing import Optional
import motor.motor_asyncio
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from zoneinfo import ZoneInfo
from datetime import timedelta, datetime
from jose import JWTError, jwt
import pymongo.errors
import pymongo.monitoring
import treelib.exceptions
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from passlib.context import CryptContext
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    SecurityScopes,
)

from .database import MONGO_DETAILS, TreeStorage, TreeDepthLimitExceeded, UserStorage
from .models import (
    SubTree,
    RequestAddSchema,
    RequestUpdateSchema,
    NodePayload,
    UserDetails,
    UpdateUserDetails,
    UpdateUserPassword,
    UpdateUserType,
    Token,
    TokenData,
    ResponseModel,
    UUID_PATTERN,
    NODE_NAME_MAX_LEN,
)


# set env variables flag
DEBUG = bool(os.getenv("DEBUG", "False") == "True")
LOGIN_RATE_LIMIT = os.getenv("LOGIN_RATE_LIMIT", "5/minute")
MONGO_MAX_POOL_SIZE = int(os.getenv("MONGO_MAX_POOL_SIZE", "100"))
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
TEST_USERNAME_TO_ADD = os.getenv(key="TESTUSERTOADD")
TEST_PASSWORD_TO_ADD = os.getenv(key="TESTPWDTOADD")
TEST_USERNAME_TO_ADD2 = os.getenv(key="TESTUSERTOADD2")
TEST_PASSWORD_TO_ADD2 = os.getenv(key="TESTPWDTOADD2")
TEST_PASSWORD_TO_CHANGE = os.getenv(key="TESTPWDTOCHANGE")

logger = get_logger(__name__)
logger.debug(f"Environment variable DEBUG is :{DEBUG}")


# ------------------------
#  Connection pool monitor
# ------------------------


class _PoolEventLogger(pymongo.monitoring.ConnectionPoolListener):
    """Logs Motor/PyMongo connection pool events.
    Registered at startup when DEBUG=True.  Produces INFO-level entries
    for connection lifecycle events (created/closed) and DEBUG-level
    entries for checkout/checkin churn, making it easy to confirm that
    connections are being reused rather than recreated per request.
    """

    def pool_created(self, event):
        logger.info(f"[pool] created: address={event.address}")

    def pool_cleared(self, event):
        logger.info(f"[pool] cleared: address={event.address}")

    def pool_closed(self, event):
        logger.info(f"[pool] closed: address={event.address}")

    def connection_created(self, event):
        logger.info(
            f"[pool] connection created: address={event.address}, id={event.connection_id}"
        )

    def connection_ready(self, event):
        logger.debug(
            f"[pool] connection ready: address={event.address}, id={event.connection_id}"
        )

    def connection_checked_out(self, event):
        logger.debug(
            f"[pool] checked out: address={event.address}, id={event.connection_id}"
        )

    def connection_check_out_failed(self, event):
        logger.warning(
            f"[pool] check out failed: address={event.address}, reason={event.reason}"
        )

    def connection_checked_in(self, event):
        logger.debug(
            f"[pool] checked in: address={event.address}, id={event.connection_id}"
        )

    def connection_closed(self, event):
        logger.info(
            f"[pool] connection closed: address={event.address}, id={event.connection_id}, reason={event.reason}"
        )


if DEBUG:
    pymongo.monitoring.register(_PoolEventLogger())


# ------------------------
#      FABULATOR
# ------------------------
REDISHOST = os.getenv("REDISHOST", "redis://localhost:6379")
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=REDISHOST,
    storage_options={"socket_keepalive": True, "health_check_interval": 30},
)

# Authentication singleton — user_storage is wired up in the lifespan
oauth = Authentication()


@asynccontextmanager
async def lifespan(app: FastAPI):
    motor_client = motor.motor_asyncio.AsyncIOMotorClient(
        MONGO_DETAILS,
        maxPoolSize=MONGO_MAX_POOL_SIZE,
    )
    app.state.motor_client = motor_client
    oauth.set_client(motor_client)
    yield
    motor_client.close()


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
version = "0.1.0"

_cors_origins_raw = os.getenv("CORS_ORIGINS", "")
if not _cors_origins_raw.strip():
    raise RuntimeError(
        "CORS_ORIGINS environment variable is not set. Add it to your .env file."
    )
origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/get_token",
    scopes={
        "user:reader": "Read account details",
        "user:writer": "write account details",
        "tree:reader": "Read trees & nodes",
        "tree:writer": "Write trees & nodes",
        "usertype:writer": "Update user_types",
    },
)


# ------------------------
#   Storage dependencies
# ------------------------


def get_tree_storage(request: Request) -> TreeStorage:
    return TreeStorage(
        collection_name="tree_collection", client=request.app.state.motor_client
    )


def get_user_storage(request: Request) -> UserStorage:
    return UserStorage(
        collection_name="user_collection", client=request.app.state.motor_client
    )


# ------------------------
#     API Helper Class
# ------------------------


class RoutesHelper:
    """helper class containg API route utility functions"""

    def __init__(self, db_storage: TreeStorage, user_storage: UserStorage):
        self.db_storage = db_storage
        self.user_storage = user_storage

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    async def account_id_exists(self, account_id):
        self.account_id = account_id
        logger.debug(f"account_id_exists({self.account_id}) called")
        try:
            does_account_exist = await self.user_storage.does_account_exist(
                account_id=self.account_id
            )
            logger.debug(f"account_exists: {does_account_exist}")
            return does_account_exist
        except pymongo.errors.PyMongoError as e:
            logger.error(
                f"Error occured retrieving count of saves for {self.account_id}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500, detail="An error occurred processing your request"
            )

    async def save_document_exists(self, document_id, account_id=None):
        """Check if save document exists. If account_id provided, also verify ownership."""
        self.document_id = document_id
        logger.debug(
            f"save_document_exists({self.document_id}, account_id={account_id}) called"
        )
        try:
            saves_count = await self.db_storage.check_if_document_exists(
                save_id=self.document_id, account_id=account_id
            )
            logger.debug(f"check_if_document_exists returned: {saves_count}")
            if saves_count > 0:
                return True
            else:
                return False
        except pymongo.errors.PyMongoError as e:
            logger.error(
                f"Error occured retrieving count of saves for {self.document_id}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500, detail="An error occurred processing your request"
            )

    async def user_document_exists(self, user_id):
        self.user_id = user_id
        logger.debug(f"user_document_exists({self.user_id}) called")
        try:
            document_count = await self.user_storage.check_if_user_exists(
                user_id=self.user_id
            )
            logger.debug(f"check_if_document_exists returned: {self.user_id}")
            if document_count > 0:
                return True
            else:
                return False
        except pymongo.errors.PyMongoError as e:
            logger.error(
                f"Error occured retrieving user document for {self.user_id}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500, detail="An error occurred processing your request"
            )

    async def get_tree_for_account(self, account_id: str) -> Tree:
        """
        Load the latest tree for an account from MongoDB.
        If no saves exist for the account, returns a new empty Tree.
        This is the single source of truth - eliminates global tree state.
        """
        logger.debug(f"get_tree_for_account({account_id}) called")

        # Check if account has any saves
        save_count = await self.db_storage.number_of_saves_for_account(
            account_id=account_id
        )
        if save_count > 0:
            try:
                tree = await self.db_storage.load_latest_into_working_tree(
                    account_id=account_id
                )
                logger.debug(f"Loaded tree from database for account: {account_id}")
                return tree
            except TreeDepthLimitExceeded as e:
                logger.error(f"Tree for account exceeds depth limit: {e}")
                raise HTTPException(
                    status_code=422,
                    detail=f"Tree exceeds maximum allowed depth of {e.limit}",
                )
            except pymongo.errors.PyMongoError as e:
                logger.error(
                    f"Error loading tree for account {account_id}", exc_info=True
                )
                raise HTTPException(
                    status_code=500, detail="An error occurred loading the tree"
                )
        else:
            # No saves exist - return a new empty tree
            logger.debug(f"No saves found for account {account_id}, creating new tree")
            return Tree()


# ------------------------
#       API Routes
# ------------------------

# ----------------------------
#     Authenticaton routines
# ----------------------------


async def get_current_user(
    security_scopes: SecurityScopes, token: str = Depends(oauth2_scheme)
):
    """authenticate user and scope and return token"""
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = f"Bearer"

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        account_id: str = payload.get("sub")
        if account_id is None:
            raise credentials_exception
        token_scopes = payload.get("scopes", [])
        expires = payload.get("exp")
        token_data = TokenData(
            scopes=token_scopes, username=account_id, expires=expires
        )
    except (JWTError, ValidationError):
        raise credentials_exception
    user = await oauth.get_user_by_account_id(account_id=token_data.username)
    if user is None:
        raise credentials_exception
    # check token expiration
    if expires is None:
        raise credentials_exception
    if datetime.now(ZoneInfo("GMT")) > token_data.expires:
        raise credentials_exception
    # check if the token is blacklisted
    if await oauth.is_token_blacklisted(token):
        raise credentials_exception
    # if we have a valid user and the token is not expired get the scopes
    token_data.scopes = list(set(token_data.scopes) & set(user.user_role.split(" ")))
    logger.debug(f"requested scopes in token:{token_scopes}")
    logger.debug(f"Required endpoint scopes:{security_scopes.scopes}")

    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions to complete action",
                headers={"WWW-Authenticate": authenticate_value},
            )
    return user


async def get_current_active_user(
    current_user: UserDetails = Security(get_current_user, scopes=["user:reader"]),
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_active_user_account(
    current_user: UserDetails = Security(get_current_user, scopes=["user:reader"]),
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user.account_id


@app.post(
    "/get_token",
    response_model=Token,
    summary="Login",
    description=(
        "Authenticate with username and password. Returns a JWT access token scoped to the "
        "requested permissions. Rate-limited (default 5 requests/minute per IP, configurable "
        "via `LOGIN_RATE_LIMIT`)."
    ),
    tags=["Authentication"],
)
@limiter.limit(LOGIN_RATE_LIMIT)
async def login_for_access_token(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends()
):
    user = await oauth.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # creates a token for a given user with an expiry in minutes
    access_token = oauth.create_access_token(
        data={"sub": user.account_id, "scopes": form_data.scopes},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}


async def get_current_user_token(token: str = Depends(oauth2_scheme)):
    return token


@app.get(
    "/logout",
    summary="Logout",
    description=(
        "Blacklist the current bearer token. The token will be rejected on all subsequent "
        "requests until it expires naturally."
    ),
    tags=["Authentication"],
)
async def logout(token: str = Depends(get_current_user_token)):
    if await oauth.add_blacklist_token(token):
        return {"result": True}


@app.get(
    "/users/me",
    response_model=UserDetails,
    summary="Get current user",
    description="Return the full profile of the currently authenticated user.",
    tags=["Users"],
)
async def read_users_me(current_user: UserDetails = Depends(get_current_active_user)):
    return current_user


# ------------------------
#         Misc
# ------------------------


def initialise_tree():
    """Create a new Tree and return it"""
    return Tree()


@app.get(
    "/",
    summary="API version",
    description="Return the API version and the authenticated user's username.",
    tags=["Meta"],
)
async def get(
    current_user: UserDetails = Security(
        get_current_user, scopes=["tree:reader", "user:reader"]
    ),
) -> dict:
    """Return the API version"""
    logger.debug("Get() Called")
    return ResponseModel(
        data={"version": version, "username": current_user.username}, message="Success"
    )


# ------------------------
#         Trees
# ------------------------


@app.get(
    "/trees/root",
    summary="Get root node ID",
    description=(
        "Return the identifier of the root node in the current user's tree. "
        "Returns 404 if no tree has been saved yet."
    ),
    tags=["Trees"],
)
async def get_tree_root(
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """return the id of the root node on current tree if there is one"""
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    logger.debug(f"get_tree_root({account_id}) called")
    tree = await routes_helper.get_tree_for_account(account_id=account_id)
    root_node = tree.root
    if root_node is None:
        raise HTTPException(
            status_code=404, detail="No saved trees found for this account"
        )
    return ResponseModel(data={"root": root_node}, message="Success")


@app.get(
    "/trees/{id}",
    summary="Prune subtree",
    description=(
        "Remove the subtree rooted at the given node from the current tree and return it as a "
        "serialized structure. The main tree is saved after removal. "
        "**Note:** this is a mutating GET — it modifies the stored tree."
    ),
    tags=["Trees"],
)
async def prune_subtree(
    id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """cut a node & children specified by supplied id"""
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    logger.debug(f"prune_subtree({account_id},{id}) called")
    # Load tree from database for this account
    tree = await routes_helper.get_tree_for_account(account_id=account_id)
    if tree.root is None:
        raise HTTPException(status_code=404, detail="No tree found for this account")
    if tree.contains(id):
        try:
            response = tree.remove_subtree(id)
            message = "Success"
        except treelib.exceptions.NodeIDAbsentError as e:
            logger.error(
                f"Error occured removing a subtree from the working tree. id: {id}",
                exc_info=True,
            )
            raise
        try:
            await db_storage.save_working_tree(tree=tree, account_id=account_id)
        except pymongo.errors.PyMongoError as e:
            logger.error(
                "Error occured saving the working tree to the database after delete.",
                exc_info=True,
            )
            raise
    else:
        raise HTTPException(status_code=404, detail="Node not found in current tree")
    return ResponseModel(jsonable_encoder(response), message)


@app.post(
    "/trees/{id}",
    summary="Graft subtree",
    description=(
        "Attach a previously pruned subtree as a child of the specified node. "
        "The subtree must be provided as a serialized tree dict in the request body."
    ),
    tags=["Trees"],
)
async def graft_subtree(
    id: str = Path(..., pattern=UUID_PATTERN),
    request: SubTree = Body(...),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """paste a subtree & beneath the node specified"""
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    logger.debug(f"graft_subtree({account_id},{id}) called")
    # Load tree from database for this account
    tree = await routes_helper.get_tree_for_account(account_id=account_id)
    if tree.root is None:
        raise HTTPException(status_code=404, detail="No tree found for this account")
    if tree.contains(id):
        # turn dict object into a Tree
        try:
            sub_tree = db_storage.build_tree_from_dict(tree_dict=request.sub_tree)
        except TreeDepthLimitExceeded as e:
            logger.error(f"Subtree exceeds depth limit: {e}")
            raise HTTPException(
                status_code=422,
                detail=f"Subtree exceeds maximum allowed depth of {e.limit}",
            )
        except (KeyError, ValueError) as e:
            logger.error(
                f"Error occured building the subtree from the request dict object.",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500, detail="An error occurred building the subtree"
            )
        try:
            if DEBUG:
                tree.save2file("dump.txt", line_type="ascii-ex", idhidden=False)
            tree.paste(nid=id, new_tree=sub_tree, deep=False)
            message = "Success"
        except (
            treelib.exceptions.NodeIDAbsentError,
            treelib.exceptions.DuplicatedNodeIdError,
        ) as e:
            logger.error(
                f"Error occured grafting the subtree into the working tree. id: {id}",
                exc_info=True,
            )
            raise
        try:
            await db_storage.save_working_tree(tree=tree, account_id=account_id)
        except pymongo.errors.PyMongoError as e:
            logger.error(
                "Error occured saving the working tree to the database after paste action.",
                exc_info=True,
            )
            raise
    else:
        raise HTTPException(status_code=404, detail="Node not found in current tree")
    return ResponseModel("Graft complete", message)


# ------------------------
#          Nodes
# ------------------------


@app.get(
    "/nodes",
    summary="List all nodes",
    description=(
        "Return all nodes in the current tree. Pass `filterval` as a query parameter to return "
        "only nodes whose tags contain that value."
    ),
    tags=["Nodes"],
)
async def get_all_nodes(
    filterval: Optional[str] = None,
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """Get a list of all the nodes in the working tree"""
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    logger.debug(f"get_all_nodes({account_id}, {filterval}) called")
    # Load tree from database for this account
    tree = await routes_helper.get_tree_for_account(account_id=account_id)
    if filterval:
        data = []
        for node in tree.all_nodes():
            if node.data:
                # Handle both dict (from DB) and object (NodePayload) cases
                tags = (
                    node.data.get("tags")
                    if isinstance(node.data, dict)
                    else getattr(node.data, "tags", None)
                )
                if tags and filterval in tags:
                    data.append(jsonable_encoder(node))
        logger.debug(f"Nodes filtered on {filterval}")
    else:
        try:
            tree.show(line_type="ascii-em")
        except treelib.exceptions.NodeIDAbsentError as e:
            logger.error("Error occured calling tree.show on tree", exc_info=True)
            raise HTTPException(
                status_code=500, detail="Error occured calling tree.show on tree"
            )
        data = [jsonable_encoder(node) for node in tree.all_nodes()]
    return ResponseModel(data=data, message="Success")


@app.get(
    "/nodes/{id}",
    summary="Get a node",
    description="Return a single node identified by its UUID.",
    tags=["Nodes"],
)
async def get_a_node(
    id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """Return a node specified by supplied id"""
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    logger.debug(f"get_a_node({account_id}, {id}) called")
    # Load tree from database for this account
    tree = await routes_helper.get_tree_for_account(account_id=account_id)
    logger.debug(f"node: {tree.get_node(id)}")
    if tree.contains(id):
        node = tree.get_node(id)
    else:
        raise HTTPException(status_code=404, detail="Node not found in current tree")
    return ResponseModel(jsonable_encoder(node), "Success")


@app.post(
    "/nodes/{name}",
    summary="Create a node",
    description=(
        "Create a new node with the given name. If `parent` is provided in the request body "
        "the node is created as a child of that node. Omit `parent` to create the root node — "
        "only one root is allowed per tree."
    ),
    tags=["Nodes"],
)
async def create_node(
    name: str = Path(..., min_length=1, max_length=NODE_NAME_MAX_LEN),
    request: RequestAddSchema = Body(...),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """Add a node to the working tree using name supplied"""
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    # map the incoming fields from the https request to the fields required by the treelib API
    logger.debug(f"create_node({account_id},{name}) called")
    # Load tree from database for this account (or create new if none exists)
    tree = await routes_helper.get_tree_for_account(account_id=account_id)
    try:
        request = jsonable_encoder(request)
    except ValueError as e:
        logger.error(
            "Error occured encoding request with jsonable_encoder", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Error occured encoding request with jsonable_encoder: {e}",
        )

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
                    name, parent=request["parent"], data=node_payload
                )
            except (
                treelib.exceptions.NodeIDAbsentError,
                treelib.exceptions.DuplicatedNodeIdError,
            ) as e:
                logger.error(
                    f"Error occured adding child node to working tree. name:{name}, parent:{request['parent']}",
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500, detail="An error occurred creating the node"
                )
        else:
            raise HTTPException(
                status_code=422,
                detail=f"Parent {request['parent']} is missing from tree",
            )
    else:
        # No parent so check if we already have a root
        if tree.root is None:
            try:
                new_node = tree.create_node(name, data=node_payload)
            except (
                treelib.exceptions.DuplicatedNodeIdError,
                treelib.exceptions.MultipleRootError,
            ) as e:
                logger.error(
                    f"Error occured adding root node to working tree. name:{name}",
                    exc_info=True,
                )
                raise HTTPException(
                    status_code=500, detail="An error occurred creating the root node"
                )
        else:
            raise HTTPException(status_code=422, detail="Tree already has a root node")
    try:
        save_result = await db_storage.save_working_tree(
            tree=tree, account_id=account_id
        )
    except pymongo.errors.PyMongoError as e:
        logger.error(
            "Error occured saving the working tree to the database", exc_info=True
        )
        raise HTTPException(status_code=500, detail="An error occurred saving the tree")
    logger.debug(f"mongo save: {save_result}")
    return ResponseModel(
        {"node": jsonable_encoder(new_node), "object_id": save_result}, "Success"
    )


@app.put(
    "/nodes/{id}",
    summary="Update a node",
    description=(
        "Update the name, payload (description, text, tags, previous, next), and/or parent of "
        "an existing node. Providing a different `parent` UUID reparents the node within the tree."
    ),
    tags=["Nodes"],
)
async def update_node(
    id: str = Path(..., pattern=UUID_PATTERN),
    request: RequestUpdateSchema = Body(...),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """Update a node in the working tree identified by supplied id"""
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    logger.debug(f"update_node({account_id},{id}) called")
    # Load tree from database for this account
    tree = await routes_helper.get_tree_for_account(account_id=account_id)
    if tree.root is None:
        raise HTTPException(status_code=404, detail="No tree found for this account")
    # test if node exists
    if tree.contains(id):
        node_payload = NodePayload(
            description=request.description,
            previous=request.previous,
            next=request.next,
            tags=request.tags,
            text=request.text,
        )
        if request.name:
            # if a parent is specified in the request ensure that it exists
            if request.parent:
                if tree.contains(request.parent):
                    try:
                        tree.update_node(
                            id,
                            _tag=request.name,
                            data=node_payload,
                            parent=request.parent,
                        )
                    except (
                        treelib.exceptions.NodeIDAbsentError,
                        treelib.exceptions.LoopError,
                    ) as e:
                        logger.error(
                            f"Error occured updating node in the working tree. id:{id}",
                            exc_info=True,
                        )
                        raise
                else:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Parent {request.parent} is missing from tree",
                    )
            else:
                try:
                    tree.update_node(id, _tag=request.name, data=node_payload)
                except treelib.exceptions.NodeIDAbsentError as e:
                    logger.error(
                        f"Error occured updating node in the working tree. id:{id}",
                        exc_info=True,
                    )
                    raise

        else:
            if request.parent:
                if tree.contains(request.parent):
                    try:
                        tree.update_node(id, data=node_payload, parent=request.parent)
                    except (
                        treelib.exceptions.NodeIDAbsentError,
                        treelib.exceptions.LoopError,
                    ) as e:
                        logger.error(
                            f"Error occured updating node in the working tree. id:{id}",
                            exc_info=True,
                        )
                        raise
                else:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Parent {request.parent} is missing from tree",
                    )

        try:
            save_result = await db_storage.save_working_tree(
                tree=tree, account_id=account_id
            )
        except pymongo.errors.PyMongoError as e:
            logger.error(
                "Error occured saving the working_tree to the database", exc_info=True
            )
            raise

        logger.debug(f"save_result: {save_result}")
        return ResponseModel({"object_id": save_result}, "Success")
    else:
        raise HTTPException(status_code=404, detail="Node not found in current tree")


@app.delete(
    "/nodes/{id}",
    summary="Delete a node",
    description=(
        "Remove the specified node and all its descendants from the tree permanently. "
        "Historical saves are unaffected."
    ),
    tags=["Nodes"],
)
async def delete_node(
    id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """Delete a node from the working tree identified by supplied id"""
    # remove the node with the supplied id
    # todo: probably want to stash the children somewhere first in a sub tree for later use
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    logger.debug(f"delete_node({account_id},{id}) called")
    # Load tree from database for this account
    tree = await routes_helper.get_tree_for_account(account_id=account_id)
    if tree.root is None:
        raise HTTPException(status_code=404, detail="No tree found for this account")
    if tree.contains(id):
        try:
            response = tree.remove_node(id)
            message = "Success"
        except treelib.exceptions.NodeIDAbsentError as e:
            logger.error(
                f"Error occured removing a node from the working tree. id: {id}",
                exc_info=True,
            )
            raise
        else:
            try:
                await db_storage.save_working_tree(tree=tree, account_id=account_id)
            except pymongo.errors.PyMongoError as e:
                logger.error(
                    "Error occured saving the working tree to the database after delete.",
                    exc_info=True,
                )
                raise
    else:
        raise HTTPException(status_code=404, detail="Node not found in current tree")
    return ResponseModel(response, message)


# ------------------------
#          Loads
# ------------------------


@app.get(
    "/loads",
    summary="Load latest save",
    description="Return the most recent saved tree snapshot for the current account as a serialized tree structure.",
    tags=["Saves"],
)
async def get_latest_save(
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """Return the latest saved tree in the db collection"""
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    logger.debug(f"get_latest_save({account_id}) called")
    # Load tree from database for this account
    if not await routes_helper.account_id_exists(account_id=account_id):
        raise HTTPException(status_code=404, detail="No saves found for this account")
    tree = await routes_helper.get_tree_for_account(account_id=account_id)
    return ResponseModel(jsonable_encoder(tree), "Success")


@app.get(
    "/loads/{save_id}",
    summary="Load a specific save",
    description=(
        "Return a historical tree snapshot by its save ID. "
        "Ownership is verified — you cannot load another user's save."
    ),
    tags=["Saves"],
)
async def get_a_save(
    save_id: str,
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """Return the specified saved tree in the db collection"""
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    logger.debug(f"get_a_save({account_id}/{save_id}) called")
    if not await routes_helper.account_id_exists(account_id=account_id):
        raise HTTPException(status_code=404, detail="No saves found for this account")
    if not await routes_helper.save_document_exists(
        document_id=save_id, account_id=account_id
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Unable to retrieve save document with id: {save_id}",
        )
    try:
        tree = await db_storage.load_save_into_working_tree(save_id=save_id)
    except TreeDepthLimitExceeded as e:
        logger.error(f"Save {save_id} exceeds depth limit: {e}")
        raise HTTPException(
            status_code=422, detail=f"Tree exceeds maximum allowed depth of {e.limit}"
        )
    except pymongo.errors.PyMongoError as e:
        logger.error(
            f"Error occured loading specified save into working tree. save_id:{save_id}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="An error occurred loading the specified save"
        )
    return ResponseModel(jsonable_encoder(tree), "Success")


# ------------------------
#          Saves
# ------------------------


@app.get(
    "/saves",
    summary="List all saves",
    description="Return metadata for all saved tree snapshots belonging to the current account.",
    tags=["Saves"],
)
async def get_all_saves(
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
) -> dict:
    """Return a dict of all the trees saved in the db collection"""
    try:
        all_saves = await db_storage.list_all_saved_trees(account_id=account_id)
    except pymongo.errors.PyMongoError as e:
        logger.error("Error occured loading all saves", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Error occured loading all saves: {e}"
        )
    logger.debug(f"get_all_saves{account_id} called")

    return ResponseModel(jsonable_encoder(all_saves), "Success")


@app.delete(
    "/saves",
    summary="Delete all saves",
    description="Permanently delete every saved snapshot for the current account. This cannot be undone.",
    tags=["Saves"],
)
async def delete_saves(
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
) -> dict:
    """Delete all saves from the db trees collection"""
    logger.debug(f"delete_saves({account_id}) called")
    try:
        delete_result = await db_storage.delete_all_saves(account_id=account_id)
    except pymongo.errors.PyMongoError as e:
        logger.error(
            f"Error occured deleting all saves for account_id:{account_id}",
            exc_info=True,
        )
        raise
    result = ResponseModel(delete_result, "Documents removed.")
    return result


# ------------------------
#          Users
# ------------------------


@app.post(
    "/users",
    summary="Register a user",
    description=(
        "Create a new user account. Password and username are hashed before storage. "
        "No authentication required."
    ),
    tags=["Users"],
)
async def save_user(
    request: UserDetails = Body(...),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """save a user to users collection"""
    # hash the password & username before storage
    request.account_id = pwd_context.hash(request.username)
    request.password = pwd_context.hash(request.password)
    logger.debug(f"save_user({request.username}) called")
    try:
        save_result = await user_storage.save_user_details(user=request)
    except pymongo.errors.PyMongoError as e:
        logger.error("Error occured saving user details", exc_info=True)
        raise
    result = ResponseModel(save_result, "new user added")
    return result


@app.get(
    "/users",
    summary="Get user details",
    description="Return the profile of the currently authenticated user from the user collection.",
    tags=["Users"],
)
async def get_user(
    account_id: str = Security(get_current_active_user_account, scopes=["user:reader"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """get a user's details from users collection"""
    logger.debug(f"get_user({account_id}) called")
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    # use the accounts_id checker here replace id references
    if await routes_helper.account_id_exists(account_id=account_id):
        try:
            get_result = await user_storage.get_user_details_by_account_id(
                account_id=account_id
            )
        except pymongo.errors.PyMongoError as e:
            logger.error("Error occured getting user details", exc_info=True)
            raise
        result = ResponseModel(get_result, "user found")
        return result
    else:
        raise HTTPException(status_code=404, detail="No user record found")


@app.put(
    "/users",
    summary="Update user details",
    description="Update the display name (first name, surname) and email address of the current user.",
    tags=["Users"],
)
async def update_user(
    account_id: str = Security(get_current_active_user_account, scopes=["user:writer"]),
    request: UpdateUserDetails = Body(...),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """update a user document"""
    logger.debug(f"update_user({request}) called")
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    # use the accounts_id checker here replace id references
    if await routes_helper.account_id_exists(account_id=account_id):
        try:
            update_result = await user_storage.update_user_details(
                account_id=account_id, user=request
            )
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error occured updating user details", exc_info=True)
            raise
        result = ResponseModel(update_result, f"user {account_id} updated")
        return result
    else:
        raise HTTPException(status_code=404, detail="No user record found")


@app.put(
    "/users/password",
    summary="Change password",
    description="Update the password for the current user. The new password is hashed before storage.",
    tags=["Users"],
)
async def update_password(
    account_id: str = Security(get_current_active_user_account, scopes=["user:writer"]),
    request: UpdateUserPassword = Body(...),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """update a user document"""
    logger.debug(f"update_password({request}) called")
    print(f"request:{request}")
    # make sure that payload account_id is the same as the one that we're logged in under
    request.new_password = pwd_context.hash(request.new_password)
    if account_id is not None:
        try:
            update_result = await user_storage.update_user_password(
                account_id=account_id, user=request
            )
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error occured updating user password", exc_info=True)
            raise
        result = ResponseModel(update_result, f"user password for {account_id} updated")
        return result
    else:
        raise HTTPException(status_code=401, detail=f"Invalid account_id requested")


@app.put(
    "/users/type",
    summary="Change user type",
    description=(
        "Update the subscription type for the current user (`free` or `premium`). "
        "Requires the `usertype:writer` scope."
    ),
    tags=["Users"],
)
async def update_type(
    account_id: str = Security(
        get_current_active_user_account, scopes=["usertype:writer"]
    ),
    request: UpdateUserType = Body(...),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """update a user type"""
    logger.debug(f"update_type({request}) called")

    if account_id is not None:
        try:
            update_result = await user_storage.update_user_type(
                account_id=account_id, user=request
            )
        except pymongo.errors.PyMongoError as e:
            logger.error(f"Error occured updating user type", exc_info=True)
            raise
        result = ResponseModel(update_result, f"user password for {account_id} updated")
        return result
    else:
        raise HTTPException(status_code=401, detail=f"Invalid account_id requested")


@app.delete(
    "/users",
    summary="Delete account",
    description="Permanently delete the current user's account and all associated tree saves.",
    tags=["Users"],
)
async def delete_user(
    account_id: str = Security(get_current_active_user_account, scopes=["user:writer"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    """delete a user from users collection"""
    logger.debug(f"delete_user({account_id}) called")
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    if await routes_helper.account_id_exists(account_id=account_id):
        try:
            delete_result = await user_storage.delete_user_details_by_account_id(
                account_id=account_id
            )
        except pymongo.errors.PyMongoError as e:
            logger.error("Error occured deleting user details", exc_info=True)
            raise
        result = ResponseModel(delete_result, "new user added")
        return result
    else:
        raise HTTPException(status_code=404, detail="No user record found")

import os
from contextlib import asynccontextmanager
from pydantic import ValidationError
import app.config   # loads the load_env lib to access .env file
from app.helpers import get_logger
from app.authentication import Authentication
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

from .database import (
    MONGO_DETAILS,
    TreeDepthLimitExceeded,
    UserStorage,
    WorkStorage,
    NodeStorage,
    setup_collections,
    is_valid_parent_child,
)
from .models import (
    UserDetails,
    UpdateUserDetails,
    UpdateUserPassword,
    UpdateUserType,
    Token,
    TokenData,
    ResponseModel,
    UUID_PATTERN,
    CreateWorkRequest,
    UpdateWorkRequest,
    WorkResponse,
    CreateNodeRequest,
    UpdateNodeRequest,
    ReorderRequest,
    NodeResponse,
    AncestorsResponse,
    WorkStatsResponse,
    NodeType,
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
    await setup_collections(motor_client.fabulator)
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


def get_user_storage(request: Request) -> UserStorage:
    return UserStorage(
        collection_name="user_collection", client=request.app.state.motor_client
     )


def get_work_storage(request: Request) -> WorkStorage:
    return WorkStorage(client=request.app.state.motor_client)


def get_node_storage(request: Request) -> NodeStorage:
    return NodeStorage(client=request.app.state.motor_client)


# ── Work endpoints ──────────────────────────────────────────────


@app.post(
     "/works",
    response_model=WorkResponse,
    status_code=201,
    summary="Create a work",
    description=(
         "Create a new narrative work for the authenticated user. "
         "A work is the top-level container for a node hierarchy (parts, chapters, scenes, beats). "
         "Returns HTTP 201 on success."
     ),
    tags=["Works"],
)
async def create_work(
    request: CreateWorkRequest,
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    work_storage: WorkStorage = Depends(get_work_storage),
) -> dict:
    logger.debug(f"create_work({account_id}) called")
    try:
        work = await work_storage.create_work(
            account_id=account_id,
            data=request.model_dump(),
         )
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error("Database error in create_work", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    return work


@app.get(
     "/works",
    response_model=list[WorkResponse],
    summary="List works",
    description=(
         "Return all works belonging to the authenticated user, ordered by creation date "
         "descending (most recent first)."
     ),
    tags=["Works"],
)
async def list_works(
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    work_storage: WorkStorage = Depends(get_work_storage),
) -> list[dict]:
    logger.debug(f"list_works({account_id}) called")
    try:
        works = await work_storage.list_works(account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error("Database error in list_works", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    return works


@app.get(
     "/works/{work_id}",
    response_model=WorkResponse,
    summary="Get a work",
    description=(
         "Return a single work by its UUID. Returns 404 if the work does not exist "
         "or belongs to a different account."
     ),
    tags=["Works"],
)
async def get_work(
    work_id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    work_storage: WorkStorage = Depends(get_work_storage),
) -> dict:
    logger.debug(f"get_work({work_id}) called")
    try:
        work = await work_storage.get_work(work_id=work_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error in get_work for {work_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    return work


@app.put(
     "/works/{work_id}",
    response_model=WorkResponse,
    summary="Update a work",
    description=(
         "Update one or more fields of an existing work. Omitted fields are left unchanged. "
         "If `author` is updated, the new value is cascaded to all nodes belonging to this work. "
         "Returns 404 if the work does not exist or belongs to a different account."
     ),
    tags=["Works"],
)
async def update_work(
    work_id: str = Path(..., pattern=UUID_PATTERN),
    request: UpdateWorkRequest = Body(...),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    work_storage: WorkStorage = Depends(get_work_storage),
) -> dict:
    logger.debug(f"update_work({work_id}) called")
    updates = request.model_dump(exclude_unset=True)
    try:
        work = await work_storage.update_work(
            work_id=work_id,
            account_id=account_id,
            updates=updates,
         )
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error in update_work for {work_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    return work


@app.delete(
     "/works/{work_id}",
    summary="Delete a work",
    description=(
         "Permanently delete a work and all of its nodes. "
         "Returns the count of nodes removed alongside the confirmation. "
         "Returns 404 if the work does not exist or belongs to a different account."
     ),
    tags=["Works"],
)
async def delete_work(
    work_id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    work_storage: WorkStorage = Depends(get_work_storage),
) -> dict:
    logger.debug(f"delete_work({work_id}) called")
    try:
        found, nodes_deleted = await work_storage.delete_work(
            work_id=work_id,
            account_id=account_id,
         )
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error in delete_work for {work_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if not found:
        raise HTTPException(status_code=404, detail="Work not found")
    return {"detail": f"Work deleted. {nodes_deleted} node(s) removed."}


# ── Node endpoints — core CRUD ──────────────────────────────────


@app.post(
     "/nodes",
    response_model=NodeResponse,
    status_code=201,
    summary="Create a node",
    description=(
         "Create a new node within a work. The `work_id` and `node_type` are required. "
         "Provide `parent_id` to attach the node under an existing parent; omit it to create "
         "a root-level `part` node. Hierarchy rules are enforced: "
         "part → chapter → scene → beat. Returns HTTP 201 on success."
     ),
    tags=["Nodes"],
)
async def create_normalised_node(
    request: CreateNodeRequest = Body(...),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    work_storage: WorkStorage = Depends(get_work_storage),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> dict:
    logger.debug(f"create_normalised_node({account_id}) called")

     # Validate that the work exists and belongs to this account.
    try:
        work = await work_storage.get_work(work_id=request.work_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error("Database error fetching work in create_normalised_node", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")

     # Validate parent exists (when supplied) and hierarchy rules.
    if request.parent_id is not None:
        try:
            parent = await node_storage.get_node(
                node_id=request.parent_id, account_id=account_id
             )
        except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
            logger.error("Database error fetching parent node in create_normalised_node", exc_info=True)
            raise HTTPException(status_code=503, detail="Database error")
        if parent is None:
            raise HTTPException(status_code=404, detail="Parent node not found")
        if not is_valid_parent_child(parent["node_type"], request.node_type):
            raise HTTPException(
                status_code=422,
                detail=f"A {request.node_type} cannot be a child of a {parent['node_type']}",
             )
    else:
         # No parent: only "part" may be a root node.
        if not is_valid_parent_child(None, request.node_type):
            raise HTTPException(
                status_code=422,
                detail="Only 'part' nodes may have no parent",
             )

    try:
        node = await node_storage.create_node(
            account_id=account_id,
            work_doc=work,
            data=request.model_dump(),
         )
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error("Database error in create_normalised_node", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    return node


@app.get(
     "/works/{work_id}/nodes",
    response_model=list[NodeResponse],
    summary="List nodes for a work",
    description=(
         "Return all nodes belonging to the specified work. "
         "Pass `node_type` as a query parameter to filter by type "
         "(one of: `part`, `chapter`, `scene`, `beat`). "
         "Returns 404 if the work does not exist or belongs to a different account."
     ),
    tags=["Nodes"],
)
async def list_normalised_nodes(
    work_id: str = Path(..., pattern=UUID_PATTERN),
    node_type: Optional[NodeType] = None,
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    work_storage: WorkStorage = Depends(get_work_storage),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> list[dict]:
    logger.debug(f"list_normalised_nodes({work_id}, node_type={node_type}) called")

     # Confirm the work exists and belongs to this account before listing its nodes.
    try:
        work = await work_storage.get_work(work_id=work_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error fetching work {work_id} in list_normalised_nodes", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")

    try:
        nodes = await node_storage.list_nodes(
            work_id=work_id,
            account_id=account_id,
            node_type=node_type.value if node_type is not None else None,
         )
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error listing nodes for work {work_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    return nodes


@app.get(
     "/nodes/{node_id}",
    response_model=NodeResponse,
    summary="Get a node",
    description=(
         "Return a single node by its UUID. "
         "Returns 404 if the node does not exist or belongs to a different account."
     ),
    tags=["Nodes"],
)
async def get_normalised_node(
    node_id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> dict:
    logger.debug(f"get_normalised_node({node_id}) called")
    try:
        node = await node_storage.get_node(node_id=node_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error in get_normalised_node for {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@app.put(
     "/nodes/{node_id}",
    response_model=NodeResponse,
    summary="Update a node",
    description=(
         "Partially update a node. Only fields present in the request body are changed; "
         "omitted fields are left as-is. "
         "Providing a new `parent_id` reparents the node — hierarchy rules are enforced "
         "and cycle detection prevents invalid restructuring. "
         "Returns 404 if the node does not exist or belongs to a different account."
     ),
    tags=["Nodes"],
)
async def update_normalised_node(
    node_id: str = Path(..., pattern=UUID_PATTERN),
    request: UpdateNodeRequest = Body(...),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> dict:
    logger.debug(f"update_normalised_node({node_id}) called")

    updates = request.model_dump(exclude_unset=True)

     # When reparenting, validate the new parent exists, hierarchy is valid, and no cycle forms.
    if "parent_id" in updates:
        new_parent_id = updates["parent_id"]
        if new_parent_id is not None:
            try:
                parent = await node_storage.get_node(
                    node_id=new_parent_id, account_id=account_id
                 )
            except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
                logger.error(
                    f"Database error fetching new parent {new_parent_id} in update_normalised_node",
                    exc_info=True,
                 )
                raise HTTPException(status_code=503, detail="Database error")
            if parent is None:
                raise HTTPException(status_code=404, detail="Parent node not found")

            try:
                node = await node_storage.get_node(
                    node_id=node_id, account_id=account_id
                 )
            except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
                logger.error(
                    f"Database error fetching node {node_id} in update_normalised_node",
                    exc_info=True,
                 )
                raise HTTPException(status_code=503, detail="Database error")
            if node is None:
                raise HTTPException(status_code=404, detail="Node not found")

            if not is_valid_parent_child(parent["node_type"], node["node_type"]):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Invalid hierarchy: a {node['node_type']} cannot be a child "
                        f"of a {parent['node_type']}"
                     ),
                 )

            try:
                cycle = await node_storage.would_create_cycle(
                    node_id=node_id,
                    new_parent_id=new_parent_id,
                    account_id=account_id,
                 )
            except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
                logger.error(
                    f"Database error during cycle detection for {node_id}",
                    exc_info=True,
                 )
                raise HTTPException(status_code=503, detail="Database error")
            if cycle:
                raise HTTPException(
                    status_code=422,
                    detail="Reparenting would create a cycle",
                 )

    try:
        result = await node_storage.update_node(
            node_id=node_id, account_id=account_id, updates=updates
         )
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error in update_normalised_node for {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if result is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return result


@app.delete(
     "/nodes/{node_id}",
    summary="Delete a node",
    description=(
         "Permanently delete the specified node and all of its descendants. "
         "Returns the count of descendant nodes removed alongside the confirmation. "
         "Returns 404 if the node does not exist or belongs to a different account."
     ),
    tags=["Nodes"],
)
async def delete_normalised_node(
    node_id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> dict:
    logger.debug(f"delete_normalised_node({node_id}) called")
    try:
        found, descendants_deleted = await node_storage.delete_node_cascade(
            node_id=node_id, account_id=account_id
         )
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error in delete_normalised_node for {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if not found:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"detail": f"Node deleted. {descendants_deleted} descendant(s) removed."}


# ------------------------
#       API Routes
# ------------------------

# ----------------------------
#     Authentication routines
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
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
     """get a user's details from users collection"""
    logger.debug(f"get_user({account_id}) called")
    if await user_storage.does_account_exist(account_id=account_id):
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
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
     """update a user document"""
    logger.debug(f"update_user({request}) called")
    if await user_storage.does_account_exist(account_id=account_id):
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
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
     """delete a user from users collection"""
    logger.debug(f"delete_user({account_id}) called")
    if await user_storage.does_account_exist(account_id=account_id):
        try:
            delete_result = await user_storage.delete_user_details_by_account_id(
                account_id=account_id
             )
        except pymongo.errors.PyMongoError as e:
            logger.error("Error occured deleting user details", exc_info=True)
            raise
        result = ResponseModel(delete_result, "User account deleted")
        return result
    else:
        raise HTTPException(status_code=404, detail="No user record found")

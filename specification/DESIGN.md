# Fabulator — Design Document
## Spec-Driven Architecture Reference
 
**Version:** 1.0
**Date:** 2026-06-06
**Companion documents:** `CONSTITUTION.md` (rules), `CLAUDE.md` (AI workflow context), `README.md` (setup)
 
---
 
## How to Use This Document
 
This document describes *how* Fabulator is built: its architecture, component interfaces, data schemas, behavioral specifications, and the rationale behind every significant design decision. It is prescriptive — it describes what the system does and how it must behave, not merely what it currently happens to do.
 
Read `CONSTITUTION.md` first for the rules. This document describes the design that satisfies those rules.
 
---
 
## Part I — System Context
 
### I.1 — What Fabulator Is
 
Fabulator is a multi-user, hierarchical narrative editing tool. Users construct tree structures where each node represents a story beat, scene, or chapter. The tree is visualised and navigated in a browser. Nodes carry content (description, text, previous/next narrative links, tags).
 
### I.2 — System Context Diagram
 
```
+-------------------+        HTTPS          +------------------------+
|   Browser Client  | <-------------------> |  FastAPI Backend       |
|  (React / D3)     |    JWT in header      |  (port 8000)           |
+-------------------+                       +------------------------+
                                                     |          |
                                             async Motor    redis-py
                                                     |          |
                                            +--------+  +-------+
                                            |MongoDB |  | Redis |
                                            |Atlas   |  | Cloud |
                                            +--------+  +-------+
```
 
**External actors:**
| Actor | Role |
|-------|------|
| Browser user | Reads and writes narrative tree content via JWT-authenticated HTTP |
| MongoDB Atlas | Persistent storage for tree snapshots and user accounts |
| Redis Cloud | JWT token blacklist; login rate-limit counter |
 
### I.3 — Deployment Units
 
| Unit | Image | Started by |
|------|-------|------------|
| `fabulator-api` | `python:3.12-slim-bookworm` | `docker compose up` |
| `claude-code` | `node:20-slim` | `docker compose --profile dev up` (dev only) |
 
No local database containers. MongoDB Atlas and Redis Cloud are always external.
 
---
 
## Part II — Backend Architecture
 
### II.1 — Layer Diagram
 
```
+--------------------------------------------------------------+
|  HTTP Layer  (FastAPI routes — api.py)                       |
|  - 22 route handlers                                         |
|  - CORS middleware                                           |
|  - SlowAPI rate-limit middleware                             |
|  - OAuth2 / Security dependency injection                    |
+--------------------------------------------------------------+
|  Application Layer  (RoutesHelper — api.py)                  |
|  - account_id_exists(), save_document_exists()               |
|  - user_document_exists()                                    |
+--------------------------------------------------------------+
|  Domain Layer  (database.py, authentication.py)              |
|  - WorkStorage: Work CRUD (work_collection); NodeStorage: node CRUD (node_collection) |
|  - UserStorage: user CRUD                                    |
|  - Authentication: JWT, bcrypt, Redis blacklist              |
+--------------------------------------------------------------+
|  Schema Layer  (models.py)                                   |
|  - Pydantic request/response models                          |
|  - Validation constants (UUID_PATTERN, length limits)        |
+--------------------------------------------------------------+
|  Infrastructure Layer                                        |
|  - AsyncIOMotorClient (shared singleton via app.state)       |
|  - Redis (lazy connection per operation)                     |
|  - Python logging (get_logger factory — helpers.py)          |
+--------------------------------------------------------------+
```
 
### II.2 — Dependency Injection Chain
 
The dependency chain for every authenticated tree route is:
 
```
Request arrives
  -> FastAPI resolves Security(get_current_active_user_account, scopes=[...])
       -> decodes JWT, checks Redis blacklist, verifies scopes
       -> returns account_id: str
  -> FastAPI resolves Depends(get_work_storage)
       -> calls WorkStorage(app.state.motor_client)
       -> returns work_storage: WorkStorage
  -> FastAPI resolves Depends(get_node_storage)
       -> calls NodeStorage(app.state.motor_client)
       -> returns node_storage: NodeStorage
  -> FastAPI resolves Depends(get_user_storage)
       -> calls UserStorage(USER_COLLECTION, app.state.motor_client)
       -> returns user_storage: UserStorage
  -> Route handler executes with (account_id, work_storage, node_storage, user_storage)
```
 
`app.state.motor_client` is the single shared `AsyncIOMotorClient` created once in the lifespan context manager. All storage instances share the same underlying connection pool.
 
### II.3 — Application Startup Sequence
 
```
uvicorn starts
  -> FastAPI lifespan (async context manager) begins
       -> AsyncIOMotorClient created with MONGO_DETAILS, maxPoolSize=MONGO_MAX_POOL_SIZE
       -> Client stored: app.state.motor_client = client
       -> Authentication.set_client(client) wired
       -> If DEBUG=True: _PoolEventLogger registered with pymongo.monitoring
  -> CORS middleware added (origins from CORS_ORIGINS env var — RuntimeError if absent)
  -> SlowAPI rate limiter added (LOGIN_RATE_LIMIT on POST /get_token)
  -> Routes registered
  -> Application ready
```
 
On shutdown (lifespan exit), the Motor client is closed.
 
---
 
## Part III — Component Specifications
 
### III.1 — WorkStorage (`database.py`)
 
**Responsibility:** CRUD for narrative Work documents in `work_collection`. Author propagation to child nodes.
 
**Constructor:**
```python
WorkStorage(client: AsyncIOMotorClient)
```
The client is injected — never created internally.
 
**Key methods:**
 
| Method | Signature | Behaviour |
|--------|-----------|-----------|
| `create_work` | `(account_id, data) -> dict` | Inserts a new Work document; auto-generates UUID work_id and timestamps |
| `get_work` | `(work_id, account_id) -> dict\|None` | Returns Work by UUID; returns None for wrong account |
| `list_works` | `(account_id) -> list[dict]` | All Works for account, ordered by created_at descending |
| `update_work` | `(work_id, account_id, updates) -> dict\|None` | Partial update; cascades author change to all child nodes via `update_many` on `node_collection` |
| `delete_work` | `(work_id, account_id) -> (bool, int)` | Deletes Work document + bulk-deletes all child nodes; returns (found, nodes_deleted) |
 
### III.1b — NodeStorage (`database.py`)
 
**Responsibility:** CRUD for individual node documents in `node_collection`. Navigation, reorder, duplicate, cycle detection.
 
**Constructor:**
```python
NodeStorage(client: AsyncIOMotorClient)
```
The client is injected — never created internally.
 
**Key methods — Core CRUD:**
 
| Method | Signature | Behaviour |
|--------|-----------|-----------|
| `create_node` | `(account_id, work_doc, data) -> dict` | Inserts node; copies author from Work; auto-assigns position (max sibling + 1) |
| `get_node` | `(node_id, account_id) -> dict\|None` | Returns node by UUID; None if wrong account |
| `list_nodes` | `(work_id, account_id, node_type?) -> list[dict]` | All nodes for a Work, optionally filtered by type |
| `update_node` | `(node_id, account_id, updates) -> dict\|None` | Partial update; auto-assigns end position on reparent |
| `delete_node_cascade` | `(node_id, account_id) -> (bool, int)` | BFS cascade delete; returns (found, descendants_deleted) |
 
**Key methods — Navigation:**
 
| Method | Signature | Behaviour |
|--------|-----------|-----------|
| `get_children` | `(node_id, account_id) -> list[dict]` | Direct children ordered by position ascending |
| `get_parent` | `(node_id, account_id) -> dict\|None` | Parent node; None for Part roots |
| `get_ancestors` | `(node_id, account_id) -> list[dict]` | Ancestors root-to-parent; empty for roots |
| `get_siblings` | `(node_id, account_id) -> list[dict]` | Siblings (same parent_id, excluding self) |
| `get_roots` | `(work_id, account_id) -> list[dict]` | All Part nodes for a Work |
| `get_leaves` | `(work_id, account_id) -> list[dict]` | All Beat nodes for a Work |
 
**Key methods — Operations:**
 
| Method | Signature | Behaviour |
|--------|-----------|-----------|
| `get_stats` | `(work_id, account_id) -> dict` | Counts by node_type + max depth (BFS) |
| `would_create_cycle` | `(node_id, new_parent_id, account_id) -> bool` | Walks parent_id chain from new_parent; True if node_id encountered |
| `reorder_siblings` | `(node_id, account_id, new_position) -> dict\|None` | Clamps position; renumbers all siblings to zero-based contiguous sequence |
| `duplicate_shallow` | `(node_id, account_id) -> dict\|None` | Copies node (no children); tag gets " (copy)" suffix; placed after original |
| `duplicate_deep` | `(node_id, account_id) -> dict\|None` | Recursive subtree copy with fresh UUIDs; tag "(copy)" suffix on root only |
 
### III.2 — UserStorage (`database.py`)
 
**Responsibility:** CRUD for user documents in `user_collection`.
 
**Constructor:** Same pattern as WorkStorage/NodeStorage — client injected, never created internally.
 
**Key methods:**
 
| Method | Signature | Behaviour |
|--------|-----------|-----------|
| `get_user_details` | `(account_id) -> dict` | Returns user document or None |
| `save_user_details` | `(user: UserDetails) -> InsertOneResult` | Creates user with bcrypt-hashed account_id |
| `update_user_details` | `(account_id, update_fields) -> UpdateResult` | Partial update of user document |
| `delete_user_details` | `(account_id) -> DeleteResult` | Removes user and all associated saves |
 
### III.3 — Authentication (`authentication.py`)
 
**Responsibility:** JWT creation and validation, bcrypt password operations, Redis token blacklisting.
 
**Design:** Instantiated once. Motor client wired post-construction via `set_client()` from the lifespan context.
 
**Redis connection pattern:** Lazy — a fresh connection is opened per operation and closed with `await conn.aclose()` immediately after. This avoids stale connections across async contexts.
 
**Key operations:**
 
| Operation | Behaviour |
|-----------|-----------|
| `create_access_token(data, scopes, expires_delta)` | Signs JWT with SECRET_KEY/ALGORITHM; encodes `sub`, `scopes`, `exp` |
| `get_current_user(token, security_scopes)` | Decodes JWT, checks Redis blacklist, verifies all required scopes present; raises `HTTPException(401)` or `403` |
| `hash_password(password)` | bcrypt hash with auto-generated salt |
| `verify_password(plain, hashed)` | bcrypt comparison |
| `add_blacklist_token(token)` | Writes token to Redis with TTL = remaining JWT lifetime |
| `is_token_blacklisted(token)` | EXISTS check in Redis |
 
**JWT payload structure:**
```json
{
  "sub": "<username>",
  "scopes": ["user:reader", "user:writer", "tree:reader", "tree:writer", "usertype:writer"],
  "exp": <unix timestamp>
}
```
 
### III.4 — Models (`models.py`)
 
**Responsibility:** All Pydantic request/response schemas and validation constants.
 
**Validation constants:**
```python
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
NODE_NAME_MAX_LEN = 100
DESCRIPTION_MAX_LEN = 500
TEXT_MAX_LEN = 5000
LINK_MAX_LEN = 200
TAG_MAX_LEN = 100
TAG_MAX_COUNT = 50
```
 
**Annotated type aliases** (used in all request schemas):
```python
UuidStr = Annotated[str, Field(pattern=UUID_PATTERN)]
NodeNameStr = Annotated[str, Field(min_length=1, max_length=NODE_NAME_MAX_LEN)]
DescriptionStr = Annotated[Optional[str], Field(max_length=DESCRIPTION_MAX_LEN)]
TextStr = Annotated[Optional[str], Field(max_length=TEXT_MAX_LEN)]
LinkStr = Annotated[Optional[str], Field(max_length=LINK_MAX_LEN)]
```
 
### III.5 — Helpers (`helpers.py`)
 
**Responsibility:** Logger factory only.
 
```python
def get_logger(name: str) -> logging.Logger:
    """Returns a named logger with stream handler.
    Log level: DEBUG if env DEBUG=True, else INFO."""
```
 
Every module obtains its logger via `logger = get_logger(__name__)`. No module creates loggers directly.
 
---
 
## Part IV — Data Schemas
 
### IV.1 — MongoDB: tree_collection Document
 
```
{
  "_id":        ObjectId,          // MongoDB auto-generated — the "save_id"
  "account_id": str,               // bcrypt hash of username — tenant partition key
  "date_time":  datetime (UTC),    // timestamp used to find "latest" save
  "tree": {
    "_identifier": str (UUID4),    // treelib tree identifier
    "root":        str (UUID4),    // node_id of root node
    "_nodes": {
      "<UUID4>": {                 // keyed by node identifier
        "_tag":          str,      // display name (e.g. "Chapter 1")
        "_identifier":   str (UUID4),
        "_predecessor":  str|null, // parent node_id (null for root)
        "_successors":   list[str],// child node_ids
        "data": {
          "description": str|null,
          "text":        str|null,
          "previous":    str|null, // app-level narrative order hint (not UUID)
          "next":        str|null, // app-level narrative order hint (not UUID)
          "tags":        list[str]
        }
      }
    }
  }
}
```
 
### IV.2 — MongoDB: user_collection Document
 
```
{
  "_id":        ObjectId,
  "account_id": str,         // bcrypt hash of username
  "username":   str,
  "full_name":  str|null,
  "email":      str|null,
  "password":   str,         // bcrypt hash of password
  "user_type":  str,         // "free" | "premium"
  "disabled":   bool
}
```
 
### IV.3 — Pydantic Request Schemas
 
| Schema | Used by | Key fields |
|--------|---------|------------|
| `NodePayload` | PUT /nodes/{id}, POST /nodes/{name} | `description`, `text`, `previous`, `next`, `tags` |
| `NodeRequest` | POST /nodes/{name} | `parent: UuidStr|None`, `payload: NodePayload|None` |
| `NodeUpdateRequest` | PUT /nodes/{id} | `tag: NodeNameStr|None`, `parent: UuidStr|None`, `payload: NodePayload|None` |
| `UserDetails` | POST /users, PUT /users | `username`, `full_name`, `email`, `password`, `user_type` |
| `PasswordRequest` | PUT /users/password | `old_password`, `new_password` |
| `UserTypeRequest` | PUT /users/type | `user_type: Literal["free","premium"]` |
 
### IV.4 — Pydantic Response Schemas
 
| Schema | Wraps |
|--------|-------|
| `ResponseModel(data, message)` | Standard wrapper for all route responses |
| `UserDetailsPublic` | User data excluding the `password` field |
| `Token` | `access_token: str`, `token_type: str` |
 
---
 
## Part V — API Behavioural Specification
 
### V.1 — Authentication Routes
 
#### POST /get_token
- **Auth:** None (public)
- **Rate limit:** `LOGIN_RATE_LIMIT` per IP per minute (SlowAPI + Redis)
- **Input:** OAuth2 `username`, `password` form fields
- **Behaviour:** Verify username exists → verify bcrypt password → generate JWT with full scopes → return `Token`
- **Errors:** 401 if credentials invalid; 429 if rate limited
#### POST /users (registration)
- **Auth:** None (public)
- **Input:** `UserDetails` body
- **Behaviour:** Check username not already taken → hash password → derive `account_id` as bcrypt hash of username → insert user document → return created user (without password)
- **Errors:** 409 if username exists
#### GET /logout
- **Auth:** Bearer JWT (any valid token)
- **Behaviour:** Add token to Redis blacklist with TTL = remaining JWT lifetime → return success
- **Errors:** 401 if token already invalid
### V.2 — User Routes
 
All require valid JWT. Operate on the authenticated user's own account only.
 
| Method | Path | Scopes | Behaviour |
|--------|------|--------|-----------|
| GET | /users/me | user:reader | Return current user (no password field) |
| GET | /users | user:reader | Return user details |
| PUT | /users | user:writer | Update full_name, email |
| PUT | /users/password | user:writer | Verify old password → hash new → update |
| PUT | /users/type | usertype:writer | Set user_type to free or premium |
| DELETE | /users | user:writer | Delete user document + all saves for account |
 
### V.3 — Node Routes
 
All require `tree:reader` (reads) or `tree:writer` (writes). All load the full tree from the latest save before operating.
 
| Method | Path | Scopes | Write? | Behaviour |
|--------|------|--------|--------|-----------|
| GET | /nodes | tree:reader | No | Load tree → return all nodes as list; filter by tag if `?filterval=` |
| GET | /nodes/{id} | tree:reader | No | Load tree → return single node by UUID |
| POST | /nodes/{name} | tree:writer | Yes | Load tree → add node (root if no parent, child if parent given) → save → return updated tree |
| PUT | /nodes/{id} | tree:writer | Yes | Load tree → update node fields and/or reparent → save → return updated tree |
| DELETE | /nodes/{id} | tree:writer | Yes | Load tree → remove node and all descendants → save → return updated tree |
 
**Path parameter validation:** `{id}` MUST match `UUID_PATTERN` via `Path(pattern=UUID_PATTERN)`. `{name}` MUST satisfy `Path(min_length=1, max_length=NODE_NAME_MAX_LEN)`.
 
### V.4 — Tree Routes
 
| Method | Path | Scopes | Write? | Behaviour |
|--------|------|--------|--------|-----------|
| GET | /trees/root | tree:reader | No | Load tree → return root node ID |
| GET | /trees/{id} | tree:writer | **Yes** | Load tree → prune subtree at node → save pruned tree → return removed subtree |
| POST | /trees/{id} | tree:writer | Yes | Load tree → graft submitted subtree under node {id} → save → return updated tree |
 
Note: `GET /trees/{id}` is a mutating GET — a known legacy quirk. It requires `tree:writer` scope despite being a GET.
 
### V.5 — Save/Load Routes
 
| Method | Path | Scopes | Behaviour |
|--------|------|--------|-----------|
| GET | /saves | tree:reader | Return list of save metadata (account_id, date_time, _id) for the account |
| DELETE | /saves | tree:writer | Delete all save documents for the account |
| GET | /loads | tree:reader | Load the most recent save document → return full tree |
| GET | /loads/{save_id} | tree:reader | Verify `save_id` belongs to account → load that specific save → return full tree |
 
**Security note on `/loads/{save_id}`:** The route MUST call `check_if_document_exists(save_id, account_id)` before loading. Returning another user's save as a 200 is a data isolation violation.
 
---
 
## Part VI — Key Sequence Flows
 
### VI.1 — User Registration and Login
 
```
Client                    FastAPI                  MongoDB              Redis
  |                          |                        |                    |
  |-- POST /users ---------->|                        |                    |
  |   {username, password}   |                        |                    |
  |                          |-- find_one(username) ->|                    |
  |                          |<- None (not found) ----|                    |
  |                          |   hash password (bcrypt)                    |
  |                          |   derive account_id = bcrypt(username)      |
  |                          |-- insert_one(user) --->|                    |
  |<- 200 {user (no pwd)} ---|                        |                    |
  |                          |                        |                    |
  |-- POST /get_token ------->|                        |                    |
  |   {username, password}   |-- SlowAPI check ----------------------->|  |
  |                          |<- under limit --------------------------------|
  |                          |-- find_one(username) ->|                    |
  |                          |<- user doc ------------|                    |
  |                          |   verify_password (bcrypt)                  |
  |                          |   create_access_token(sub, scopes, exp)     |
  |<- 200 {access_token} ----|                        |                    |
```
 
### VI.2 — Authenticated Write (Create Node)
 
```
Client                    FastAPI                  MongoDB
  |                          |                        |
  |-- POST /nodes/{name} --->|                        |
  |   Authorization: Bearer  |                        |
  |   {parent, payload}      |                        |
  |                          |-- decode JWT            |
  |                          |-- Redis blacklist check  |
  |                          |-- verify scopes          |
  |                          |   -> account_id resolved |
  |                          |                        |
  |                          |-- find latest save ---->|
  |                          |<- tree document --------|
  |                          |   build_tree_from_dict() (recursive)
  |                          |   tree.create_node(name, parent=parent_id)
  |                          |-- insert_one(new snapshot) ->|
  |<- 200 {updated tree} ----|                        |
```
 
### VI.3 — Token Blacklisting on Logout
 
```
Client              FastAPI            Redis
  |                    |                  |
  |-- GET /logout ---->|                  |
  |   Bearer token     |                  |
  |                    |-- decode JWT      |
  |                    |   calc TTL = exp - now
  |                    |-- SET token TTL ->|
  |<- 200 -------------|                  |
  |                    |                  |
  |-- GET /nodes ------>|                  |
  |   (same token)     |-- EXISTS token ->|
  |                    |<- true ----------|
  |<- 401 -------------|                  |
```
 
---
 
## Part VII — Frontend Design Specification
 
### VII.1 — Component Architecture
 
```
App.jsx  (router, AuthGuard)
  |
  +-- LoginPage.jsx
  |     POST /get_token -> authStore.setToken()
  |
  +-- WorkspacePage.jsx  (main shell)
        |
        +-- AppShell.jsx  (layout grid, top nav)
        |     +-- Toolbar.jsx  (collapse all, save status, undo/redo)
        |
        +-- TreeVisualiser.jsx   [D3 BOUNDARY — React stops here]
        |     useRef(svgRef)      D3 owns everything inside svgRef
        |     useD3Tree.js        D3 update/collapse/zoom logic
        |     TreeControls.jsx    zoom in/out, reset, collapse all
        |
        +-- NodeDetailPanel.jsx
              NodeHeader.jsx     name, id, depth, dirty indicator
              NodeFields.jsx     description, text, previous, next
              NodeTags.jsx       tag display + add/remove
              NodeActions.jsx    add child, duplicate, delete (scope-gated)
```
 
### VII.2 — State Management
 
Three Zustand stores. All are independent — no store imports another.
 
**authStore:**
```
{
  token: string | null,         // JWT — in memory only, never localStorage
  user: object | null,          // decoded token payload
  scopes: string[],             // extracted from JWT for usePermissions()
  setToken(token),
  clearAuth()                   // called on logout and 401
}
```
 
**treeStore:**
```
{
  nodes: Node[],                // flat list from GET /nodes
  selectedNodeId: string | null,
  dirtyNodeId: string | null,   // node with unsaved changes
  setNodes(nodes),
  selectNode(id),
  markDirty(id),
  clearDirty()
}
```
 
**undoStore:**
```
{
  stack: Command[],             // max 50 entries (FIFO eviction)
  push(command),
  undo(),
  redo()
}
```
 
### VII.3 — API Layer
 
`src/api/client.js` — Axios instance with two interceptors:
 
**Request interceptor:**
```
Attach Authorization: Bearer <token> header to every request
```
 
**Response interceptor:**
```
On 401: authStore.clearAuth() -> navigate("/login", {state: {reason: "session_expired"}})
On other errors: re-throw for caller to handle
```
 
API modules are pure async functions — no React, no Zustand, no side effects:
```
auth.js    — login(credentials), logout()
nodes.js   — getNodes(), getNode(id), createNode(name, body), updateNode(id, body), deleteNode(id)
trees.js   — getRoot(), getSubtree(id), graftSubtree(id, body)
saves.js   — listSaves(), loadSave(id), loadLatest(), deleteSaves()
```
 
### VII.4 — Data Flow
 
```
FastAPI (port 8000)
  | axios (JWT header, 401 interceptor)
api/ layer (pure async functions)
  | transforms API responses to app-friendly shapes
Zustand stores (treeStore, authStore, undoStore)
  | selectors / subscriptions
Custom hooks (useTree, usePermissions, useNodeDetail, useAutoSave)
  | props + callbacks
WorkspacePage
  | treeStore.nodes -> D3 hierarchy data
TreeVisualiser (D3)        NodeDetailPanel (React)
  node click -> treeStore.selectNode()
                           treeStore.selectedNodeId -> useNodeDetail()
                           field change -> useAutoSave() -> PUT /nodes/{id}
```
 
### VII.5 — D3/React DOM Boundary Specification
 
```
WorkspacePage renders:
  <TreeVisualiser ref={svgRef} nodes={nodes} onNodeClick={selectNode} />
 
Inside TreeVisualiser:
  useEffect(() => {
    const svg = d3.select(svgRef.current)
    // All D3 operations — join, enter, update, exit — happen here
    // React NEVER touches svgRef.current children
  }, [nodes, selectedNodeId])
```
 
D3 owns: all `<g>`, `<circle>`, `<line>`, `<text>` inside the SVG.
React owns: the `<svg>` element itself, all sibling components.
 
Neither layer renders into the other's territory.
 
### VII.6 — Auto-Save Behaviour
 
```
User edits field
  -> useAutoSave: debounce 2500ms
  -> treeStore.markDirty(nodeId)   // show dot indicator
  -> after 2500ms idle: PUT /nodes/{id} {payload}
  -> on success: treeStore.clearDirty()
  -> on 401: authStore.clearAuth() (handled by Axios interceptor)
 
Navigation away from dirty node:
  -> confirm dialog: "You have unsaved changes. Leave anyway?"
```
 
---
 
## Part VIII — Infrastructure Design
 
### VIII.1 — Docker Compose Services
 
```yaml
services:
  fabulator-api:
    image: python:3.12-slim-bookworm
    ports: ["8000:8000"]
    env_file: .env
    healthcheck: GET /health every 10s
 
  claude-code:
    image: node:20-slim
    profiles: [dev]
    depends_on:
      fabulator-api: {condition: service_healthy}
    volumes:
      - .:/workspace
    env:
      CLAUDE_CODE_OAUTH_TOKEN: from .env   # NOT ANTHROPIC_API_KEY
```
 
The `dev` profile ensures `claude-code` never starts in production.
 
### VIII.2 — Network Topology
 
```
Host machine (macOS M-series)
  Colima VM (Linux/ARM64, Apple VZ, virtiofs mount)
    Docker daemon
      fabulator-api container  -- port 8000 exposed to host
      claude-code container    -- no exposed ports (workspace only)
    -> external: MongoDB Atlas (TLS)
    -> external: Redis Cloud (TLS)
```
 
The containers communicate via Docker's default bridge network. `claude-code` calls the API on `http://fabulator-api:8000` (service name resolution).
 
### VIII.3 — Environment Configuration Matrix
 
| Variable | API container | Claude Code container | Notes |
|----------|--------------|----------------------|-------|
| `MONGO_DETAILS` | Yes | No | Atlas connection string |
| `REDISHOST` | Yes | No | Redis URL |
| `SECRET_KEY` | Yes | No | JWT signing key |
| `ANTHROPIC_API_KEY` | Yes | **No** | Never in claude-code container |
| `CLAUDE_CODE_OAUTH_TOKEN` | No | **Yes** | Never in api container |
| `CORS_ORIGINS` | Yes | No | Required — startup fails without it |
| `DEBUG` | Optional | No | Enables pool event logging |
 
---
 
## Part IX — Design Decisions
 
Each decision records the choice made, the alternatives considered, and the rationale. This log exists so future contributors understand *why*, not just *what*.
 
---
 
### DD-01 — Append-Only Save Model
 
**Decision:** Every write operation inserts a new complete tree snapshot. No in-place updates.
 
**Alternatives considered:**
- In-place MongoDB update of the current tree document
- Delta/patch storage (store only the diff per write)
**Rationale:** Simplicity of implementation (no merge logic), implicit full revision history as a free side-effect, clean rollback by loading any historical save. Trade-off: linear collection growth with edits. Acceptable at current user scale. Pagination/cleanup is a future concern.
 
---
 
### DD-02 — account_id as bcrypt Hash of Username
 
**Decision:** `account_id` is derived as `bcrypt(username)` at registration and used as the universal tenant partition key.
 
**Alternatives considered:**
- Random UUID assigned at registration
- MongoDB `_id` used as tenant key
**Rationale:** Deterministically derivable from username without a lookup (useful for operations that need the key but only have the username). bcrypt provides one-way hashing so the username cannot be reverse-derived from the key stored in documents.
 
**Trade-off:** Username cannot be changed without migrating all documents (account_id would change). Acceptable — username change is not a planned feature.
 
---
 
### DD-03 — Per-Request Tree Loading (No Cache)
 
**Decision:** Every request that touches tree data loads the full tree from MongoDB.
 
**Alternatives considered:**
- In-memory LRU cache keyed by account_id
- Redis cache of serialised tree
**Rationale:** Eliminates stale-read bugs entirely. No cache invalidation logic. Concurrent requests from the same user always see the most recent state. At current scale (single-user narrative tool, sub-second tree operations), the per-request load is acceptable. Revisit with load tests if latency becomes a problem.
 
---
 
### DD-04 — JWT in Memory (Not localStorage) on Frontend
 
**Decision:** JWT stored only in Zustand memory store (lost on page refresh → forces re-login).
 
**Alternatives considered:**
- `localStorage` persistence (survives refresh)
- httpOnly cookie set by the server
**Rationale:** `localStorage` is readable by any JavaScript on the page (XSS risk). httpOnly cookie is the gold standard but requires server-side changes and same-site origin config. For a solo writing tool, re-login on refresh is an acceptable UX trade-off in exchange for simpler, more secure token handling.
 
**Future path:** If re-login becomes a friction point, migrate to httpOnly cookie auth — this requires FastAPI changes but the frontend change is isolated to `api/client.js` and `authStore`.
 
---
 
### DD-05 — D3 Owns the SVG
 
**Decision:** D3 has full, exclusive control of the SVG element inside `TreeVisualiser`. React never renders inside it.
 
**Alternatives considered:**
- React renders tree nodes as SVG elements; D3 used only for layout math
- A pure React tree library (e.g. react-d3-tree)
**Rationale:** D3's collapsible tree layout, zoom/pan, and transition APIs are significantly more mature than React-native SVG tree solutions. The DOM conflict risk is real but fully manageable by maintaining a strict `useRef` boundary. Using D3 only for math and React for rendering would lose D3's animation and interaction primitives.
 
**Migration path:** For React Native, `TreeVisualiser` is swapped for `TreeVisualiserNative` using `react-native-svg` + custom layout. The props interface is identical — the rest of the app is unaffected.
 
---
 
### DD-06 — Single Motor Client via Lifespan
 
**Decision:** One `AsyncIOMotorClient` per process, created in FastAPI's lifespan context manager, stored on `app.state`, injected via `Depends()`.
 
**Alternatives considered:**
- Create client per-request (original pattern — rejected: no connection reuse, pool not effective)
- Module-level global variable (rejected: harder to test, lifecycle not tied to app)
**Rationale:** Motor's connection pooling only works if the same client instance is reused. The lifespan pattern gives deterministic startup/shutdown. `app.state` is the idiomatic FastAPI location for process-scoped state. `Depends()` injection keeps storage classes testable without a running server.
 
---
 
### DD-07 — Redis Lazy Connection (Per-Operation)
 
**Decision:** Redis connection opened fresh per operation, closed immediately with `aclose()`.
 
**Alternatives considered:**
- Persistent Redis connection stored on `Authentication` instance
- Connection pool for Redis
**Rationale:** Redis token blacklisting is low-frequency (login, logout, per-request auth check). A persistent connection created in `__init__` becomes stale across async context boundaries (the original bug: `RuntimeError: Event loop is closed`). Lazy connection per operation is simple, correct, and performs adequately for this access pattern.
 
---
 
### DD-08 — Zustand Over Redux or React Query
 
**Decision:** Zustand for frontend state management.
 
**Alternatives considered:**
- Redux Toolkit (rejected: excessive boilerplate for a single-user app)
- React Query (rejected: adds complexity; Zustand + Axios achieves the same result with less abstraction)
- Context API (rejected: performance concerns on tree re-renders, no RN-equivalent)
**Rationale:** Zustand is lightweight, has no boilerplate, works identically in React Native, and is sufficient for the three stores needed (auth, tree, undo). It does not require a provider wrapper.
 
---
 
### DD-09 — Vite Over Create React App
 
**Decision:** Vite as the build tool.
 
**Rationale:** Faster HMR, simpler config, no CRA maintenance burden. Vite's dev proxy eliminates the CORS friction during development (proxy `/api` to `http://localhost:8000`).
 
---
 
### DD-10 — CSS Modules Over Tailwind/Styled Components
 
**Decision:** CSS Modules for web styling.
 
**Rationale:** Scoped styles without runtime overhead. The migration path to React Native (`StyleSheet`) is straightforward — CSS Modules and RN StyleSheet share the same mental model of co-located, named style objects. Tailwind has no React Native equivalent. Styled Components adds runtime overhead and an extra dependency.
 
---
 
---

### DD-11 — Flexible Node Hierarchy (Drop Beat, Relax Parent-Child Enforcement)

**Decision:** Replace the fixed five-tier chain (`Work → Part → Chapter → Scene → Beat`) with a flexible three-type model: `Part`, `Chapter`, and `Scene` are the only node types. Any of the three may be a direct child of any other, or a direct child of a Work. `Scene` is always a leaf — it may not have children. `Part` (with `parent_id == null`) remains the only valid root node. `Beat` is removed entirely.

**Alternatives considered:**
- Retain the fixed chain but make intermediate levels optional (skip-level allowed): rejected — this still requires encoding a strict ordering and does not reflect how narrative planning actually works.
- Label-free nodes with user-defined depth: rejected — type labels carry semantic meaning (Part = major division, Chapter = grouping, Scene = atomic unit) and are needed for filtering, display, and export.

**Rationale:** In practice, a writer planning a novel may have Parts containing Scenes directly (no Chapters), or a short story with only Scenes under a single Part, or a complex work with all three levels. The enforced chain prevented valid structures and added friction. Beat was removed because it represents a level of granularity below what is useful for planning — individual beats are better captured as prose within a Scene's `text` field. Scene becomes the atomic narrative unit.

**New valid parent-child rules:**

| Parent type | Valid child types |
|-------------|------------------|
| `null` (root) | `part` only |
| `part` | `part`, `chapter`, `scene` |
| `chapter` | `part`, `chapter`, `scene` |
| `scene` | _(none — leaf)_ |

**Impact:**
- `_VALID_CHILD` dict replaced by `_VALID_CHILDREN` set-valued dict in `database.py`
- `NodeType` enum in `models.py`: remove `beat`
- `_NODE_VALIDATOR` JSON Schema in `database.py`: update `node_type` enum to `["part", "chapter", "scene"]`
- `is_valid_parent_child` function updated to check set membership
- Beat guard in duplicate and hierarchy checks: removed
- `CONSTITUTION.md` I.5 and IV.3 updated
- `REQUIREMENTS.md` glossary, CP 12, CP 13, CP 15, CP 17, CP 19, CP 20, CP 27, CP 30 updated

**Trade-off:** Removing Beat means any existing data with `node_type: "beat"` requires migration. Acceptable — no production data exists at this stage.

## Part X — Open Design Questions
 
These are unresolved decisions that will need answers before the affected features are built.
 
| # | Question | Affects | Options |
|---|----------|---------|---------|
| OD-01 | How should `PUT /nodes/{id}/reorder` define position? Index among siblings? Before/after a specific sibling UUID? | Tier 1 roadmap | (a) integer index (b) `{before: uuid}` / `{after: uuid}` |
| OD-02 | Should `POST /nodes/{id}/duplicate` deep-copy children recursively or shallow-copy the node only? | Tier 1 roadmap | (a) flag `?include_children=true` (b) always deep (c) always shallow |
| OD-03 | Full-text search: MongoDB Atlas Search index or in-memory filter of loaded tree? | Tier 3 roadmap | Atlas Search is accurate but requires index creation; in-memory is simpler but loads full tree |
| OD-04 | Export format: generate server-side (Python) or client-side (browser)? | Tier 4 roadmap | Server-side enables complex formats (DOCX); client-side avoids new dependencies |
| OD-05 | Auto-save conflict resolution: last-write-wins, or optimistic locking with version field? | Frontend | Current model is last-write-wins; version field would require API change |
 
---
 
*Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>*
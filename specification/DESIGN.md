# Fabulator — Design Document
## Spec-Driven Architecture Reference
 
**Version:** 1.1
**Date:** 2026-06-10
**Companion documents:** `CONSTITUTION.md` (rules), `CLAUDE.md` (AI workflow context), `README.md` (setup)

> **v1.1 migration note:** This revision realigns the document with the normalised adjacency-list model that replaced the treelib snapshot model (CONSTITUTION Part I). The retired `tree_collection`, save/load and `/trees/*` surface, `RoutesHelper` layer, and per-request whole-tree loading are removed; the live Work/Node/Search/Demo surface, Tier-2 navigation, and Tier-3 query endpoints (including `GET /works/{work_id}/nodes/ordered`) are now described. Superseded design decisions are retained and marked.
 
---
 
## How to Use This Document
 
This document describes *how* Fabulator is built: its architecture, component interfaces, data schemas, behavioral specifications, and the rationale behind every significant design decision. It is prescriptive — it describes what the system does and how it must behave, not merely what it currently happens to do.
 
Read `CONSTITUTION.md` first for the rules. This document describes the design that satisfies those rules.
 
---
 
## Part I — System Context
 
### I.1 — What Fabulator Is
 
Fabulator is a multi-user, hierarchical narrative editing tool. Users construct tree structures where each node represents a story beat, scene, or chapter. The tree is visualised and navigated in a browser. Each node is stored as an independent document in `node_collection` with a `parent_id` pointer to its parent (normalised adjacency list); a Work is a separate document in `work_collection`. Nodes carry content (description, text, previous/next narrative hints, tags).

**Ordering authority:** Reading order is derived from the `parent_id` hierarchy + `position` only (depth-first pre-order, siblings by `position`). The node `previous` / `next` fields are currently free-text narrative hints (not UUIDs) and are **not** an ordering authority. (See `specification/work-reading-order/feature.md`.)
 
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
| MongoDB Atlas | Persistent storage for Work and node documents (adjacency list) and user accounts |
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
|  - Route handlers grouped: Authentication, Meta, Works,      |
|    Nodes, Search, Demo, Users (count maintained in api.py)   |
|  - CORS middleware                                           |
|  - SlowAPI rate-limit middleware                             |
|  - OAuth2 / Security dependency injection                    |
+--------------------------------------------------------------+
|  Domain Layer  (database.py, authentication.py)              |
|  - WorkStorage:   Work CRUD (work_collection), author cascade |
|  - NodeStorage:   node CRUD, navigation, reorder, duplicate, |
|                   reading order (node_collection)            |
|  - SearchStorage: $text search + tag query (node_collection) |
|  - DemoStorage:   transactional demo-tree seed               |
|  - UserStorage:   user CRUD (user_collection)                |
|  - Authentication: JWT, bcrypt, Redis blacklist             |
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

> `RoutesHelper` (an earlier application-layer indirection) is **retired**; storage classes are injected directly into handlers via `Depends()` (CONSTITUTION III.1).
 
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
| `get_reading_order` | `(work_id, account_id) -> list[dict]` | All nodes of a Work in depth-first pre-order, siblings by `position`; in-memory traversal over one `{account_id, work_id}` fetch, `visited` cycle-guard |
 
**Key methods — Operations:**
 
| Method | Signature | Behaviour |
|--------|-----------|-----------|
| `get_stats` | `(work_id, account_id) -> dict` | Counts by node_type + max depth (BFS) |
| `would_create_cycle` | `(node_id, new_parent_id, account_id) -> bool` | Walks parent_id chain from new_parent; True if node_id encountered |
| `reorder_siblings` | `(node_id, account_id, new_position) -> dict\|None` | Clamps position; renumbers all siblings to zero-based contiguous sequence |
| `duplicate_shallow` | `(node_id, account_id) -> dict\|None` | Copies node (no children); tag gets " (copy)" suffix; placed after original |
| `duplicate_deep` | `(node_id, account_id) -> dict\|None` | Recursive subtree copy with fresh UUIDs; tag "(copy)" suffix on root only |
 
### III.1c — SearchStorage (`database.py`)

**Responsibility:** Read-only discovery over `node_collection`. Strictly account-scoped; mutates nothing.

| Method | Signature | Behaviour |
|--------|-----------|-----------|
| `search_nodes` | `(account_id, query, work_id=None, node_type=None, limit=50) -> list[dict]` | `$text` search over `description` + `text`; projects/sorts by `textScore` descending; uses `node_text_idx` |
| `find_nodes_by_tags` | `(account_id, tags, match="any", work_id=None, node_type=None, limit=50) -> list[dict]` | Tag query via `$in` (any) / `$all` (all); uses `node_tags_idx` |

### III.1d — DemoStorage (`database.py`)

**Responsibility:** Seed a complete demo narrative tree for the authenticated account as a single transactional operation.

| Method | Signature | Behaviour |
|--------|-----------|-----------|
| `seed_demo` | `(account_id, author, reset=False) -> dict` | Builds a demo Work + node tree via `build_demo_tree`; writes under a multi-document transaction with a compensating-delete fallback for atomicity; optional `reset` clears existing demo data first |

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
 
### IV.1 — MongoDB: work_collection and node_collection Documents

The treelib `tree_collection` snapshot document is **retired** (CONSTITUTION I.1) and MUST NOT be written to. Narrative state is stored normalised across two collections.

**work_collection document:**
```
{
  "_id":         ObjectId,          // MongoDB auto-generated (never used for lookups)
  "work_id":     str (UUID4),       // application identifier — all lookups use this
  "account_id":  str,               // bcrypt hash of username — tenant partition key
  "title":       str,
  "description": str|null,
  "author":      str|null,          // denormalised onto every child node at creation
  "tags":        list[str],
  "created_at":  datetime (UTC),
  "updated_at":  datetime (UTC)
}
```

**node_collection document (adjacency list):**
```
{
  "_id":         ObjectId,          // never used for lookups
  "node_id":     str (UUID4),       // application identifier
  "work_id":     str (UUID4),       // FK to work_collection; every query scopes by this
  "account_id":  str,               // tenant partition key
  "author":      str|null,          // copied from the Work (CONSTITUTION I.7)
  "node_type":   str,               // "part" | "chapter" | "scene" | "beat"
  "parent_id":   str|null,          // parent node_id; null only for Part roots
  "position":    int,               // zero-based, contiguous among siblings (CONSTITUTION IV.5)
  "tag":         str,               // display name (e.g. "Chapter 1")
  "description": str|null,
  "text":        str|null,
  "previous":    str|null,          // free-text narrative hint (not a UUID; not ordering authority)
  "next":        str|null,          // free-text narrative hint (not a UUID; not ordering authority)
  "tags":        list[str],
  "created_at":  datetime (UTC),
  "updated_at":  datetime (UTC)
}
```

Both collections are created with a JSON Schema validator enforcing field types and the `node_type` enum (CONSTITUTION IV.7; REQUIREMENTS Req 26–28). The hierarchy `Work → Part → Chapter → Scene → Beat` is enforced at the application level on every create/reparent and at the schema level (CONSTITUTION I.5).

**Indexes** (created idempotently in `setup_collections`):

| Collection | Index | Purpose |
|------------|-------|---------|
| work_collection | `{account_id, work_id}` | Work lookup by id, account-scoped |
| work_collection | `{account_id}` | List Works for an account |
| node_collection | `{account_id, node_id}` | Single node lookup |
| node_collection | `{account_id, work_id}` | List/traverse a Work's nodes (also serves reading order) |
| node_collection | `{account_id, parent_id}` | Children / sibling navigation |
| node_collection | `{account_id, node_type}` | Roots / leaves / type filters |
| node_collection | `node_text_idx` (`$text` on `description`, `text`) | Full-text search |
| node_collection | `node_tags_idx` (`{account_id, tags}`) | Tag query |
 
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
| `CreateWorkRequest` | POST /works | `title` (1–200), `description?` (≤2000), `author?` (≤200), `tags?` (≤50×≤100) |
| `UpdateWorkRequest` | PUT /works/{work_id} | all of the above, every field optional (partial update; `author` change cascades to nodes) |
| `CreateNodeRequest` | POST /nodes | `work_id`, `node_type`, `parent_id?`, `tag` (1–200), `description?`, `text?` (≤50000), `previous?`/`next?` (≤200), `tags?` |
| `UpdateNodeRequest` | PUT /nodes/{node_id} | all node content fields plus `parent_id` (reparent), every field optional |
| `ReorderRequest` | PUT /nodes/{node_id}/reorder | `position: int` (≥0; clamped to `len(siblings)-1`) |
| `UserDetails` | POST /users, PUT /users | `username`, `full_name`, `email`, `password`, `user_type` |
| `PasswordRequest` | PUT /users/password | `old_password`, `new_password` |
| `UserTypeRequest` | PUT /users/type | `user_type: Literal["free","premium"]` |
 
### IV.4 — Pydantic Response Schemas
 
| Schema | Shape |
|--------|-------|
| `WorkResponse` | Work document **excluding** `account_id` |
| `NodeResponse` | `node_id`, `work_id`, `author`, `node_type`, `parent_id`, `position`, `tag`, `description`, `text`, `previous`, `next`, `tags`, `created_at`, `updated_at` (**no** `account_id`) |
| `AncestorsResponse` | `{ancestors: list[NodeResponse]}` (root-first) |
| `WorkStatsResponse` | `{work_id, total_nodes, by_type: {part, chapter, scene, beat}, max_depth}` |
| `NodeSearchResponse` | `{results: list[NodeResponse], count: int}` (search: `textScore` desc; by-tag: `created_at` desc) |
| `OrderedNodesResponse` | `{work_id, nodes: list[NodeResponse], count, next_cursor: str\|null}` (reading order; cursor-paginated) |
| `DemoSeedResponse` | `{work_id, title, total_nodes, by_type}` (**no** `account_id`) |
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
 
### V.3 — Work Routes

Operate on `work_collection`, account-scoped. Cross-account or missing Work returns **404** (`"Work not found"`), never 403.

| Method | Path | Scopes | Resp | Behaviour |
|--------|------|--------|------|-----------|
| POST | /works | tree:writer | 201 `WorkResponse` | Create a Work (auto `work_id`, timestamps) |
| GET | /works | tree:reader | 200 `list[WorkResponse]` | List the account's Works, `created_at` desc |
| GET | /works/{work_id} | tree:reader | 200 `WorkResponse` | Fetch one Work |
| PUT | /works/{work_id} | tree:writer | 200 `WorkResponse` | Partial update; `author` change cascades to all child nodes |
| DELETE | /works/{work_id} | tree:writer | 200 `{detail}` | Delete Work + bulk-delete all its nodes |
| GET | /works/{work_id}/stats | tree:reader | 200 `WorkStatsResponse` | Type counts + max depth |
| GET | /works/{work_id}/nodes | tree:reader | 200 `list[NodeResponse]` | All nodes of a Work (flat) |
| GET | /works/{work_id}/nodes/root | tree:reader | 200 `list[NodeResponse]` | All Part (root) nodes |
| GET | /works/{work_id}/nodes/leaves | tree:reader | 200 `list[NodeResponse]` | All Beat (leaf) nodes |
| GET | /works/{work_id}/nodes/ordered | tree:reader | 200 `OrderedNodesResponse` | All nodes in reading order (pre-order, siblings by `position`); `limit` (default 50, max 200) + opaque `node_id` `cursor` pagination |

### V.4 — Node Routes

Operate directly on individual node documents (CONSTITUTION I.2 — no save/load round-trip). Reads require `tree:reader`; writes `tree:writer`. `{node_id}` MUST match `UUID_PATTERN` via `Path(pattern=UUID_PATTERN)`.

| Method | Path | Scopes | Resp | Behaviour |
|--------|------|--------|------|-----------|
| POST | /nodes | tree:writer | 201 `NodeResponse` | Create a node; validates Work + parent + hierarchy; auto-assigns end `position` |
| GET | /nodes/{node_id} | tree:reader | 200 `NodeResponse` | Fetch one node |
| PUT | /nodes/{node_id} | tree:writer | 200 `NodeResponse` | Partial update and/or reparent (cycle-checked) |
| DELETE | /nodes/{node_id} | tree:writer | 200 `{detail}` | Cascade-delete node + all descendants |
| PUT | /nodes/{node_id}/reorder | tree:writer | 200 `NodeResponse` | Move to a position among siblings; renumbers the sibling group contiguously |
| POST | /nodes/{node_id}/duplicate | tree:writer | 201 `NodeResponse` | Duplicate as next sibling; `?deep=true` copies the subtree, else shallow |
| GET | /nodes/{node_id}/children | tree:reader | 200 `list[NodeResponse]` | Direct children, `position` asc |
| GET | /nodes/{node_id}/parent | tree:reader | 200 `NodeResponse\|null` | Parent (null for Part roots) |
| GET | /nodes/{node_id}/ancestors | tree:reader | 200 `AncestorsResponse` | Root-to-parent chain |
| GET | /nodes/{node_id}/siblings | tree:reader | 200 `list[NodeResponse]` | Same-parent nodes excluding self |

### V.5 — Search & Demo Routes

| Method | Path | Scopes | Resp | Behaviour |
|--------|------|--------|------|-----------|
| GET | /nodes/search | tree:reader | 200 `NodeSearchResponse` | `$text` search over `description`/`text`; `query` (req), `work_id?`, `node_type?`, `limit?`; `textScore` desc |
| GET | /nodes/by-tag | tree:reader | 200 `NodeSearchResponse` | Tag query; `tags` (req, repeated), `match=any\|all`, `work_id?`, `node_type?`, `limit?` |
| POST | /demo/seed | tree:writer | 201 `DemoSeedResponse` | Transactionally seed a demo Work + node tree; optional `reset` bool |

The retired `/trees/*` and `/saves`, `/loads` routes (treelib save/load model) are **removed** (CONSTITUTION I.1–I.2).

### V.6 — Meta Routes

| Method | Path | Auth | Behaviour |
|--------|------|------|-----------|
| GET | /health | None | Liveness probe → `{"status": "ok"}` |
| GET | /metrics | None | Uptime, connection-pool, request counters |
 
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
Client                    FastAPI                          MongoDB
  |                          |                                |
  |-- POST /nodes ---------->|                                |
  |   Authorization: Bearer  |                                |
  |   CreateNodeRequest      |                                |
  |                          |-- decode JWT                    |
  |                          |-- Redis blacklist check          |
  |                          |-- verify scopes (tree:writer)    |
  |                          |   -> account_id resolved         |
  |                          |                                |
  |                          |-- get_work(work_id, account) -->|
  |                          |<- Work doc (or 404) ------------|
  |                          |-- (if parent_id) get_node ----->|
  |                          |<- parent doc (or 404) ----------|
  |                          |   validate hierarchy (else 422)  |
  |                          |   author = Work.author           |
  |                          |   position = max(sibling)+1      |
  |                          |-- insert_one(node document) --->|
  |<- 201 NodeResponse ------|                                |
```

No tree snapshot is loaded or written: the node document is inserted directly (CONSTITUTION I.1–I.2).
 
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
  |-- GET /works ----->|                  |
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
  nodes: Node[],                // flat list from GET /works/{work_id}/nodes
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
works.js   — listWorks(), getWork(id), createWork(body), updateWork(id, body), deleteWork(id), getStats(id), getOrderedNodes(id, {limit, cursor})
nodes.js   — listWorkNodes(workId), getNode(id), createNode(body), updateNode(id, body), deleteNode(id), reorder(id, position), duplicate(id, {deep}), getChildren(id), getParent(id), getAncestors(id), getSiblings(id)
search.js  — searchNodes(params), nodesByTag(params)
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
 
### DD-01 — Append-Only Save Model  *(SUPERSEDED by DD-11)*

> **Status:** Superseded by the normalised adjacency-list refactor (CONSTITUTION I.1–I.2). Retained for historical rationale only; the snapshot/save model is no longer in use — node documents are the persistent state, updated in place.
 
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
 
### DD-03 — Per-Request Tree Loading (No Cache)  *(SUPERSEDED by DD-11)*

> **Status:** Superseded. Whole-tree-per-request loading no longer occurs; the adjacency-list model serves single-document lookups and targeted, account-scoped queries. The no-cache stance still holds (each request reads current state from MongoDB).
 
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
 
### DD-11 — Normalised Adjacency-List Storage

**Decision:** Each node is an independent `node_collection` document with a `parent_id` pointer; Works live in `work_collection`. No single-document tree snapshots; treelib is removed.

**Alternatives considered:**
- Append-only whole-tree snapshots (the original model — see superseded DD-01)
- Materialised-path or nested-set encodings

**Rationale:** Independent node documents allow single-document lookups, targeted in-place updates, and account-scoped cascade deletes without loading the full tree, which the snapshot model could not do efficiently. `position` gives gap-free sibling ordering; reading order is recovered by pre-order traversal (`specification/work-reading-order/feature.md`). Trade-off: multi-node operations (cascade delete, author cascade, deep duplicate) now span several documents and rely on application-level invariants (hierarchy, no-cycles, contiguous positions) enforced on every write, plus MongoDB JSON Schema validation. Accepted as the architectural foundation (CONSTITUTION Part I).
 
---
 
## Part X — Open Design Questions
 
These are unresolved decisions that will need answers before the affected features are built.
 
**Resolved:**
- **OD-01** (reorder position semantics) → **integer index among siblings**, clamped to `len(siblings)-1`, with the sibling group renumbered contiguously. (`specification/node-reorder/feature.md`)
- **OD-02** (duplicate depth) → **single endpoint with `?deep=true`**; default shallow, deep copies the subtree with fresh UUIDs. (`specification/node-duplicate/feature.md`)
- **OD-03** (full-text search) → **native MongoDB `$text` index** (`node_text_idx`), not Atlas Search — Atlas Search on M0 needs out-of-band async `createSearchIndex` provisioning rather than the idempotent `create_index` path in `setup_collections`. (`specification/search-query/feature.md`)
 
**Open:**
 
| # | Question | Affects | Options |
|---|----------|---------|---------|
| OD-04 | Export format: generate server-side (Python) or client-side (browser)? | Tier 4 roadmap | Server-side enables complex formats (DOCX); client-side avoids new dependencies |
| OD-05 | Auto-save conflict resolution: last-write-wins, or optimistic locking with version field? | Frontend | Current model is last-write-wins; version field would require API change |
| OD-06 | Should `previous`/`next` become typed UUID4 links (indexed, chain-validated on write) so they can drive cross-hierarchy narrative ordering? | Data model | (a) keep as free-text hints (b) migrate to nullable UUID4 with validation + backfill |
 
---
 
*Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>*
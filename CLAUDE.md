# CLAUDE.md - AI Assistant Context for Fabulator

## Project Overview

Fabulator is a FastAPI-based backend for a collaborative tree-editing application (narrative/story writing tool). Users create hierarchical tree structures where each node contains story content (description, text, tags). The system supports multiple users with authentication and role-based access control.

## Tech Stack

- **Framework:** FastAPI (async Python web framework)
- **Database:** MongoDB via Motor (async driver)
- **Cache/Sessions:** Redis (token blacklisting)
- **Authentication:** JWT tokens with OAuth2, bcrypt password hashing
- **Data Model:** Normalised adjacency-list (WorkStorage, NodeStorage, UserStorage)
- **Python Version:** 3.12+

## Project Structure

```
fabulator/
├── server/
│   ├── app/
│   │   ├── api.py           # Main FastAPI app, all routes
│   │   ├── database.py      # MongoDB operations — WorkStorage, NodeStorage, UserStorage
│   │   ├── authentication.py # JWT creation, password hashing, token blacklist
│   │   ├── models.py        # Pydantic schemas for requests/responses
│   │   ├── helpers.py       # get_logger() factory (Python logging module)
│   │   └── config.py        # Environment loading (load_dotenv only)
│   ├── tests/
│   │   └── test_unit.py     # Unit tests (no live DB required)
│   │   └── test_integration_normalised.py  # Integration tests (117 tests)
│   ├── main.py              # Entry point (runs uvicorn)
│   ├── test_api_integration.py  # Legacy integration tests (treelib era)
│   ├── pytest.ini           # pytest config (asyncio_mode = auto)
│   └── requirements.txt     # Python dependencies
├── specification/           # Design docs, PROGRESS, feature specs
├── README.md                # Setup, env vars, API reference
├── .env.example             # Environment template
├── CODEBASE_ASSESSMENT.md   # Known issues and work areas
└── TODO_DEPENDENCY_UPDATES.md
```

## Key Concepts

### Tree Structure
- Each user has an `account_id` (bcrypt hash of username)
- Trees are stored as normalised adjacency-list documents in MongoDB `work_collection` and `node_collection`
- `work_collection`: one document per narrative work, contains metadata (title, author, tags)
- `node_collection`: one document per node, contains `parent_id` to form the tree, plus content fields (description, text, tags)
- Hierarchy is enforced: Part → Chapter → Scene → Beat (max 4 levels)
- Nodes are loaded via per-request MongoDB queries (no global state)

### Authentication Flow
1. User registers via `POST /users`
2. User gets token via `POST /get_token` (OAuth2 password flow)
3. Token includes scopes: `user:reader`, `user:writer`, `tree:reader`, `tree:writer`, `usertype:writer`
4. Protected routes use `Security(oauth2_scheme, scopes=[...])` dependency
5. Logout blacklists token in Redis

### Database Classes
- `TreeStorage(collection_name, client)` - CRUD for tree documents
- `UserStorage(collection_name, client)` - CRUD for user documents
- `WorkStorage(client)` — CRUD for work documents in `work_collection`; author cascade updates all child nodes
- `NodeStorage(client)` — CRUD for nodes in `node_collection`; BFS cascade delete, sibling renumbering, cycle detection, duplicate (shallow/deep)
- All storage classes receive a shared `AsyncIOMotorClient` injected via FastAPI `Depends()` — client created once in the lifespan context manager and stored on `app.state.motor_client`

## Environment Variables

Required in `.env`:
```
MONGO_DETAILS=mongodb+srv://user:pass@cluster/db
SECRET_KEY=<jwt-secret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REDISHOST=redis://localhost:6379
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
LOGIN_RATE_LIMIT=5/minute          # use 1000/minute in test environments
MAX_TREE_DEPTH=100
MONGO_MAX_POOL_SIZE=100       # max Motor connections to MongoDB (tune for concurrency)
DEBUG=False
```

## Running the Project

```bash
cd server
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Option 1: Run via main.py
python main.py

# Option 2: Run uvicorn directly
uvicorn app.api:app --reload
```

## Running Tests

```bash
cd server
pytest  # Requires MongoDB Atlas and Redis running (171 tests: 160 pass, 10 skip)

# Unit tests only — no live DB required
pytest tests/test_unit.py
```

Tests use `asyncio_mode = auto` - no need for `@pytest.mark.asyncio` decorators.
Set `LOGIN_RATE_LIMIT=1000/minute` in `.env` to avoid 429 errors during integration test runs.

## API Endpoints

### Authentication
- `POST /get_token` - Login, returns JWT
- `GET /logout` - Blacklist current token
- `POST /users` - Register new user

### Works (require auth + tree scopes)
- `GET /works` - List works for account
- `GET /works/{work_id}` - Get single work
- `POST /works` - Create a work
- `PUT /works/{work_id}` - Update work (author change cascades to nodes)
- `DELETE /works/{work_id}` - Delete work and all its nodes
- `GET /works/{work_id}/stats` - Node counts by type + max depth

### Nodes (require auth + tree scopes)
- `GET /works/{work_id}/nodes` - List nodes (optional `?node_type=` filter)
- `GET /works/{work_id}/nodes/root` - Get root (Part) nodes
- `GET /works/{work_id}/nodes/leaves` - Get leaf (Beat) nodes
- `POST /nodes` - Create node (hierarchy enforced)
- `GET /nodes/{node_id}` - Get single node
- `PUT /nodes/{node_id}` - Update node (supports reparenting)
- `DELETE /nodes/{node_id}` - Delete node and descendants
- `GET /nodes/{node_id}/children` - Get direct children
- `GET /nodes/{node_id}/parent` - Get parent node (null for root)
- `GET /nodes/{node_id}/ancestors` - Get root-to-parent path
- `GET /nodes/{node_id}/siblings` - Get sibling nodes
- `PUT /nodes/{node_id}/reorder` - Change position among siblings
- `POST /nodes/{node_id}/duplicate` - Copy node (`?deep=true` for subtree)

### Users (require auth)
- `GET /users/me` - Get current user
- `GET /users` - Get user details
- `PUT /users` - Update user details
- `PUT /users/password` - Change password
- `PUT /users/type` - Change user type (free/premium)
- `DELETE /users` - Delete current user

### Meta
- `GET /` - API version and username

## Code Patterns

### Route Pattern
```python
@app.get("/endpoint", response_model=ResponseModel2)
async def endpoint_name(
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    # ... operations
    return ResponseModel(data=result, message="Success")
```

### Normalised Model Route Pattern (Work/Node endpoints)
```python
@app.get("/works/{work_id}", response_model=WorkResponse)
async def get_work(
    work_id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    work_storage: WorkStorage = Depends(get_work_storage),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> dict:
    work = await work_storage.get_work(work_id=work_id, account_id=account_id)
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    return work
```

### Database Pattern
```python
class TreeStorage:
    def __init__(self, collection_name: str, client: motor.motor_asyncio.AsyncIOMotorClient):
        self.client = client  # shared client injected — do not create here
        self.database = self.client.fabulator
        self.tree_collection = self.database.get_collection(collection_name)

    async def some_operation(self, param: str) -> dict:
        try:
            result = await self.tree_collection.find_one({"field": param})
        except (ConnectionFailure, OperationFailure) as e:
            logger.error("Description of operation that failed", exc_info=True)
            raise
        return result
```

### Normalised Model Database Pattern (WorkStorage / NodeStorage)
```python
class NodeStorage:
    def __init__(self, client: motor.motor_asyncio.AsyncIOMotorClient):
        self.client = client
        self.database = self.client.fabulator
        self.node_collection = self.database.get_collection("node_collection")

    async def get_node(self, node_id: str, account_id: str) -> dict | None:
        try:
            doc = await self.node_collection.find_one(
                {"node_id": node_id, "account_id": account_id}
            )
        except (ConnectionFailure, OperationFailure):
            logger.error(f"Exception in get_node({node_id})", exc_info=True)
            raise
        return doc.pop("_id", None) or doc if doc else None
```

### Logging Pattern
```python
from app.helpers import get_logger
logger = get_logger(__name__)

logger.debug("Called with param: ...")   # DEBUG env var controls visibility
logger.error("Something went wrong", exc_info=True)  # includes traceback
```

### Pydantic Model Pattern
```python
class SomeSchema(BaseModel):
    field: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"field": "value"}
        }
    )
```

## Known Issues (See CODEBASE_ASSESSMENT.md)

All critical, high, and medium-priority issues are resolved. Remaining open items:

### Low Priority
- **4.3** — No performance/load tests
- Pre-commit hook calls `sudo` (unavailable in some environments)

### Recently Fixed
- **Save isolation bug** (2026-02-09): `/loads/{save_id}` now verifies account ownership
- **Redis connections** (2026-02-09): Closed with `await conn.aclose()` after each operation
- **CORS** (2026-03-15): `CORS_ORIGINS` env var required; methods/headers explicitly restricted
- **Exception handling** (2026-03-15): All broad `except Exception` replaced with specific types
- **ConsoleDisplay** (2026-03-15): Removed per-method instantiations; module-level instance
- **Rate limiting** (2026-03-15): SlowAPI on `/get_token`, configurable via `LOGIN_RATE_LIMIT`
- **DB connection pooling H4** (2026-03-16): Single shared `AsyncIOMotorClient` via lifespan + `Depends()` — PR #12
- **Input validation H5** (2026-03-16): UUID/length/tag constraints via Pydantic `Annotated` types and FastAPI `Path()` — PR #13
- **Tree depth limit M2** (2026-03-16): `MAX_TREE_DEPTH` env var; `TreeDepthLimitExceeded` exception; HTTP 422 on breach — PR #14
- **Structured logging L3** (2026-03-16): `ConsoleDisplay` replaced with Python `logging` via `get_logger()` — PR #16
- **Exception leaking M5** (2026-03-16): HTTPException details no longer embed raw `{e}` — PR #16
- **Unit tests L4** (2026-03-16): `server/tests/test_unit.py` — 33 tests, no live DB required — PR #16
- **README L2** (2026-03-16): `README.md` added at repo root — PR #16
- **Self-assignment pattern 4.5** (2026-03-16): 71 `self.x = param` assignments removed from 22 methods; local variables used throughout — PR #17
- **Motor pool observability 4.1** (2026-03-16): `MONGO_MAX_POOL_SIZE` env var (default 100) wired into `AsyncIOMotorClient`; `_PoolEventLogger` registered when `DEBUG=True`; 2 concurrent-request tests confirm pool reuse — PR #18
- **OpenAPI annotations 4.4** (2026-03-16): `summary`, `description`, and `tags` added to all 22 route handlers; routes grouped as Authentication / Meta / Trees / Nodes / Saves / Users — PR #19

## Missing API Functionality (Roadmap)

The following features are missing from the current API. Prioritized by importance for a narrative structure tool.

**Note:** Node reparenting IS supported via `PUT /nodes/{id}` with `parent` in request body.

### Tier 1 - Core CRUD Gaps (High Priority)

These are fundamental operations missing from basic CRUD:

| Endpoint | Purpose |
|----------|---------|
| `DELETE /saves/{save_id}` | Delete a **specific** save (currently only delete-all) |
| `GET /saves/{save_id}` | Get save **metadata** without loading full tree |
| ~~`POST /nodes/{id}/duplicate`~~ | ~~**Copy** a node with optional children~~ ✅ Implemented |
| ~~`PUT /nodes/{id}/reorder`~~ | ~~Change **position among siblings**~~ ✅ Implemented |

### Tier 2 - Tree Navigation (High Priority)

Essential for frontend tree visualization and navigation:

| Endpoint | Purpose |
|----------|---------|
| ~~`GET /nodes/{id}/children`~~ | ~~Get **direct children** of a node~~ ✅ Implemented |
| ~~`GET /nodes/{id}/parent`~~ | ~~Get **parent** node~~ ✅ Implemented |
| ~~`GET /nodes/{id}/siblings`~~ | ~~Get **sibling** nodes~~ ✅ Implemented |
| ~~`GET /nodes/{id}/ancestors`~~ | ~~Get **path from root** to node~~ ✅ Implemented |
| ~~`GET /trees/leaves`~~ | ~~Get all **leaf nodes** (story branch endpoints)~~ ✅ `/works/{id}/nodes/leaves` |
| ~~`GET /trees/stats`~~ | ~~Tree **depth, node count**, branch statistics~~ ✅ `/works/{id}/stats` |

### Tier 3 - Search & Query (Medium Priority)

For finding content in large narrative structures:

| Endpoint | Purpose |
|----------|---------|
| `GET /nodes/search?query=<text>` | **Full-text search** in description/text |
| `GET /nodes/by-tag?tags=<list>` | Query nodes by **multiple tags** |

### Tier 4 - Enhanced Features (Medium Priority)

| Feature | Endpoints |
|---------|-----------|
| **Cross-Node Relationships** | `POST/GET/DELETE /nodes/{id}/relationships` - foreshadowing, callbacks |
| **Node Comments** | `POST/GET /nodes/{id}/comments` - editorial notes |
| **Export** | `GET /export/{format}` - PDF, Markdown, DOCX, JSON |
| **Bulk Operations** | `POST /nodes/bulk-create`, `PUT /nodes/bulk-update` |

### Tier 5 - Advanced Features (Lower Priority)

| Feature | Endpoints |
|---------|-----------|
| **Character Tracking** | CRUD `/characters`, `GET /characters/{id}/appearances` |
| **Timeline Support** | `POST /nodes/{id}/timeline-entry`, `GET /timeline` |
| **Story Templates** | `POST /templates`, `POST /trees/from-template/{id}` |
| **Revision History** | `GET /nodes/{id}/history`, `POST /nodes/{id}/restore` |
| **Analytics** | `GET /analytics/pacing`, word counts, tag frequency |
| **Tree Sharing** | `POST /trees/{id}/share`, permissions management |

### Implementation Notes

**Quick Wins (all Tier 1 & 2 implemented):**
- Navigation endpoints (children, parent, siblings) — use `NodeStorage` adjacency-list queries
- Tree stats — aggregation pipeline + BFS depth calculation
- Node duplication — recursive deep copy with fresh UUIDs
- Reorder — position-based sibling renumbering with clamp

**New MongoDB Collections Needed:**
- `characters`, `comments`, `relationships`, `revisions`, `templates`

**Database Indexes Needed:**
- Text search index on node description/text fields
- Index on tags for tag-based queries

## Coding Guidelines

### Do
- Use async/await for all I/O operations
- Use Pydantic models for request/response validation
- Use `Optional[type] = None` for optional fields
- Use `list[str]` not `List[str]` (Python 3.9+)
- Use `datetime.now(timezone.utc)` not `datetime.utcnow()`
- Use `ZoneInfo("UTC")` not `pytz.timezone("gmt")`
- Use `is None` not `== None`

### Don't
- Don't use global state for tree data (load per-request)
- Don't catch bare `Exception` - use specific exceptions
- Don't create new DB clients per-method (use instance variable)
- Don't hardcode CORS origins (use environment variables)

## Testing Guidelines

- Tests are integration tests requiring live MongoDB/Redis
- Use fixtures for test data setup
- Clean up created data after tests
- Test both success and failure (401/403) scenarios
- No `@pytest.mark.asyncio` needed (auto mode enabled)

### Test Types

**Isolation Tests (`test_isolation_*`):**
- Verify User B cannot access User A's data
- Expected response: 404 (data not found)
- Use `return_isolation_token` fixture (full permissions, separate user)

**Scope Tests (`test_scope_*`):**
- Verify user with limited scopes cannot perform restricted operations on their OWN data
- Expected response: 403 (insufficient permissions)
- Use `return_scoped_token` fixture (parameterized with 6 scope values)
- Tests `pytest.skip()` when the token has the required scope — only insufficient-permission cases run
- 10 tests, each with ~5 passing parametrizations and ~1 skipped (the sufficient-scope case)

## Git Workflow

**IMPORTANT: Always use feature branches. Never commit directly to `main`.**

Workflow for all changes:
1. Create a feature branch: `git checkout -b feature/description` or `fix/issue-name`
2. Make changes and commit to the feature branch
3. Push the feature branch: `git push -u origin feature/description`
4. Create a pull request for review
5. Merge to `main` after approval

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates

## Commit Style

```
<action> <subject>

<optional body>

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

Examples:
- `Fix duplicate method definition in database.py`
- `Add rate limiting to login endpoint`
- `Update dependencies to latest versions (2024/2025)`

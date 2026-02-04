# CLAUDE.md - AI Assistant Context for Fabulator

## Project Overview

Fabulator is a FastAPI-based backend for a collaborative tree-editing application (narrative/story writing tool). Users create hierarchical tree structures where each node contains story content (description, text, tags). The system supports multiple users with authentication and role-based access control.

## Tech Stack

- **Framework:** FastAPI (async Python web framework)
- **Database:** MongoDB via Motor (async driver)
- **Cache/Sessions:** Redis (token blacklisting)
- **Authentication:** JWT tokens with OAuth2, bcrypt password hashing
- **Tree Structure:** treelib library
- **Python Version:** 3.9+

## Project Structure

```
fabulator/
├── server/
│   ├── app/
│   │   ├── api.py           # Main FastAPI app, all routes (924 lines)
│   │   ├── database.py      # MongoDB operations - TreeStorage, UserStorage classes
│   │   ├── authentication.py # JWT creation, password hashing, token blacklist
│   │   ├── models.py        # Pydantic schemas for requests/responses
│   │   ├── helpers.py       # ConsoleDisplay logging utility
│   │   └── config.py        # Environment loading
│   ├── main.py              # Entry point (runs uvicorn)
│   ├── test_api_integration.py  # Integration tests (1,700+ lines)
│   ├── pytest.ini           # pytest config (asyncio_mode = auto)
│   └── requirements.txt     # Python dependencies
├── .env.example             # Environment template
├── CODEBASE_ASSESSMENT.md   # Known issues and work areas
└── TODO_DEPENDENCY_UPDATES.md
```

## Key Concepts

### Tree Structure
- Each user has an `account_id` (bcrypt hash of username)
- Trees are stored as JSON documents in MongoDB `tree_collection`
- Trees have nodes with: `_tag` (name), `_identifier` (UUID), `data` (payload)
- Node payload contains: `description`, `text`, `previous`, `next`, `tags`
- Trees are loaded from database per-request (no global state)

### Authentication Flow
1. User registers via `POST /users`
2. User gets token via `POST /get_token` (OAuth2 password flow)
3. Token includes scopes: `user:reader`, `user:writer`, `tree:reader`, `tree:writer`, `usertype:writer`
4. Protected routes use `Security(oauth2_scheme, scopes=[...])` dependency
5. Logout blacklists token in Redis

### Database Classes
- `TreeStorage(collection_name)` - CRUD for tree documents
- `UserStorage(collection_name)` - CRUD for user documents
- Both create new Motor client in `__init__` (connection pooling concern noted)

## Environment Variables

Required in `.env`:
```
MONGO_DETAILS=mongodb+srv://user:pass@cluster/db
SECRET_KEY=<jwt-secret>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REDISHOST=redis://localhost:6379
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
pytest  # Requires MongoDB Atlas and Redis running
```

Tests use `asyncio_mode = auto` - no need for `@pytest.mark.asyncio` decorators.

## API Endpoints

### Authentication
- `POST /get_token` - Login, returns JWT
- `GET /logout` - Blacklist current token
- `POST /users` - Register new user

### Users (require auth)
- `GET /users/me` - Get current user
- `PUT /users` - Update user details
- `PUT /users/password` - Change password
- `PUT /users/type` - Change user type (free/premium)
- `DELETE /users` - Delete current user

### Nodes (require auth + tree scopes)
- `GET /nodes` - List all nodes (optional `filterval` query param)
- `GET /nodes/{node_id}` - Get single node
- `POST /nodes/{node_name}` - Create node (root if no parent in body)
- `PUT /nodes/{node_id}` - Update node
- `DELETE /nodes/{node_id}` - Delete node and children

### Trees (require auth + tree scopes)
- `GET /trees/root` - Get root node ID
- `GET /trees/{node_id}` - Get subtree from node
- `POST /trees/{parent_id}` - Graft subtree onto parent

### Saves (require auth + tree scopes)
- `GET /saves` - List all saves for account
- `GET /loads` - Load latest save
- `GET /loads/{save_id}` - Load specific save
- `DELETE /saves` - Delete all saves

## Code Patterns

### Route Pattern
```python
@app.get("/endpoint", response_model=ResponseModel2)
async def endpoint_name(
    current_user: UserDetails = Security(get_current_user, scopes=["tree:reader"])
):
    tree_storage = TreeStorage(collection_name="tree_collection")
    # ... operations
    return ResponseModel(data=result, message="Success")
```

### Database Pattern
```python
class TreeStorage:
    def __init__(self, collection_name):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
        self.database = self.client.fabulator
        self.tree_collection = self.database.get_collection(collection_name)

    async def some_operation(self, param: str) -> dict:
        try:
            result = await self.tree_collection.find_one({"field": param})
        except Exception as e:
            # Log and re-raise
            raise
        return result
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

### Critical
- `database.py:554,598` - Duplicate `delete_user_details()` method
- `api.py:67-78` - CORS allows all methods/headers with credentials

### High Priority
- Broad `except Exception` catching (63 instances in database.py)
- No rate limiting on login endpoint
- `ConsoleDisplay()` instantiated per-method (should be instance var)

### Medium Priority
- `api.py` still uses deprecated `pytz` (line 13, 235)
- Tree recursion has no depth limit
- Redis connections not explicitly closed

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

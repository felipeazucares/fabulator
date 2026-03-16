# Fabulator

A FastAPI backend for a collaborative hierarchical tree-editing application. Users create and edit tree structures where each node contains narrative content (description, text, tags, links). The system supports multiple users with JWT authentication and role-based access control.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI (async Python) |
| Database | MongoDB Atlas via Motor (async driver) |
| Cache / Token blacklist | Redis |
| Authentication | JWT (OAuth2 password flow), bcrypt |
| Tree structure | treelib |
| Python | 3.9+ |

## Prerequisites

- Python 3.9 or higher
- A [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) cluster (or local MongoDB)
- A Redis instance — [Redis Cloud](https://redis.com/redis-enterprise-cloud/) free tier or local `redis-server`
- pip / venv

## Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/felipeazucares/fabulator.git
cd fabulator

# 2. Create and activate a virtual environment
cd server
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate.bat     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp ../.env.example ../.env
# Edit .env and fill in your MongoDB, Redis, and JWT values
```

## Environment Variables

All variables are defined in `.env.example`. Copy it to `.env` and fill in your values.

| Variable | Required | Description |
|----------|----------|-------------|
| `MONGO_DETAILS` | Yes | MongoDB Atlas connection string |
| `REDISHOST` | Yes | Redis connection URL |
| `SECRET_KEY` | Yes | JWT signing secret — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ALGORITHM` | Yes | JWT algorithm, e.g. `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | Token lifetime in minutes, e.g. `30` |
| `CORS_ORIGINS` | Yes | Comma-separated list of allowed frontend origins |
| `LOGIN_RATE_LIMIT` | No | Max login attempts per minute per IP (default `5/minute`) |
| `MAX_TREE_DEPTH` | No | Maximum tree reconstruction depth (default `100`) |
| `DEBUG` | No | Set to `True` for verbose logging (default `False`) |

## Running the Server

```bash
cd server

# Option 1: via main.py
python main.py

# Option 2: via uvicorn directly (with auto-reload for development)
uvicorn app.api:app --reload
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Running Tests

Tests are **integration tests** — they require a live MongoDB Atlas cluster and Redis instance configured in your `.env` file.

```bash
cd server
pytest
```

To avoid rate-limit 429s during test runs, set `LOGIN_RATE_LIMIT=1000/minute` in your `.env`.

The unit tests in `tests/test_unit.py` cover models, authentication helpers, and tree operations without needing a running database.

```bash
cd server
pytest tests/test_unit.py
```

## API Endpoints

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/get_token` | Login — returns JWT access token |
| `GET` | `/logout` | Blacklist current token |
| `POST` | `/users` | Register a new user |

### Users (require auth)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/users/me` | Get current user profile |
| `GET` | `/users` | Get user details |
| `PUT` | `/users` | Update name / email |
| `PUT` | `/users/password` | Change password |
| `PUT` | `/users/type` | Change user type (free / premium) |
| `DELETE` | `/users` | Delete account and all saves |

### Nodes (require auth + tree scopes)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/nodes` | List all nodes (optional `?filterval=<tag>`) |
| `GET` | `/nodes/{id}` | Get a single node |
| `POST` | `/nodes/{name}` | Create a node (root if no parent in body) |
| `PUT` | `/nodes/{id}` | Update a node (supports reparenting) |
| `DELETE` | `/nodes/{id}` | Delete a node and all its children |

### Trees (require auth + tree scopes)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/trees/root` | Get the root node ID |
| `GET` | `/trees/{id}` | Prune a subtree rooted at node |
| `POST` | `/trees/{id}` | Graft a subtree onto a node |

### Saves & Loads (require auth + tree scopes)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/saves` | List all saves for the current account |
| `DELETE` | `/saves` | Delete all saves |
| `GET` | `/loads` | Load the latest saved tree |
| `GET` | `/loads/{save_id}` | Load a specific save |

## Project Structure

```
fabulator/
├── server/
│   ├── app/
│   │   ├── api.py            # FastAPI app and all route handlers
│   │   ├── database.py       # MongoDB operations (TreeStorage, UserStorage)
│   │   ├── authentication.py # JWT creation, bcrypt hashing, token blacklist
│   │   ├── models.py         # Pydantic request/response schemas
│   │   ├── helpers.py        # Logging configuration
│   │   └── config.py         # Loads .env via python-dotenv
│   ├── tests/
│   │   └── test_unit.py      # Unit tests (no live DB required)
│   ├── main.py               # Entry point (runs uvicorn)
│   ├── test_api_integration.py  # Integration test suite
│   ├── pytest.ini            # pytest config
│   └── requirements.txt
├── .env.example              # Environment variable template
└── README.md
```

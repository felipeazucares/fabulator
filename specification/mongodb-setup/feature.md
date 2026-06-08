# Feature Specification: MongoDB Setup

**Implementation status:** COMPLETE — `setup_collections`, `_WORK_VALIDATOR`, `_NODE_VALIDATOR`, and all 7 indexes are committed in database.py (lines 641–710). `setup_collections` is called in the FastAPI lifespan startup (api.py:156). This document is authoritative for verification and test authoring.

**Files in scope:**
- `server/app/database.py` — `_WORK_VALIDATOR` (line 641), `_NODE_VALIDATOR` (line 654), `setup_collections` async function (line 671)
- `server/app/api.py` — lifespan startup call `await setup_collections(motor_client.fabulator)` (line 156)

---

## Introduction

MongoDB collections do not enforce schema by default. Fabulator creates `work_collection` and `node_collection` with JSON Schema validators and composite indexes at application startup. This ensures:

1. No invalid documents can enter the collections (even via direct MongoDB access)
2. All queries used by the application hit indexed fields
3. `work_id` and `node_id` are globally unique within their collections

`setup_collections` is idempotent: it creates collections that don't exist, and updates validators on existing ones via `collMod`. Indexes use `create_index` which is a no-op if the index already exists. This means restarting the server is safe with no data loss or duplicate index errors. (CONSTITUTION IV.7, I.3)

---

## Glossary

| Term | Definition |
|------|-----------|
| **work_collection** | MongoDB collection storing Work documents. Created with JSON Schema validator and 2 indexes. |
| **node_collection** | MongoDB collection storing node documents. Created with JSON Schema validator and 5 indexes. |
| **JSON Schema validator** | MongoDB-level schema enforcement via `$jsonSchema`. Applied at collection creation or via `collMod`. Rejects inserts/updates that violate constraints. |
| **collMod** | MongoDB command to modify a collection's options (including validator) without recreating it. Used on existing collections. |
| **idempotent** | Calling `setup_collections` multiple times produces the same result as calling it once. No errors, no duplicate indexes, no data loss. |
| **setup_collections(db)** | `async def setup_collections(db) -> None`. Receives the Motor database object. Creates/updates both collections and all indexes. |
| **_WORK_VALIDATOR** | The `$jsonSchema` dict applied to `work_collection`. Enforces: `work_id` (UUID4 string), `account_id` (non-empty string), `title` (non-empty string), `tags` (array of strings). |
| **_NODE_VALIDATOR** | The `$jsonSchema` dict applied to `node_collection`. Enforces: `node_id`, `work_id`, `account_id`, `tag`, `node_type` (enum), `position` (integer >= 0), `tags` (array). |
| **_UUID4_RE** | Regex pattern used in validators: `r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"`. |

---

## Functional Requirements

### Requirement 1: Create work_collection with Validator and Indexes

**User Story:** As a system administrator, I want `work_collection` to be created with a schema validator and indexes at startup, so that Work documents are always structurally valid and queries are fast.

**Maps to:** `setup_collections` function (database.py:671) called from lifespan (api.py:156). (CONSTITUTION IV.7, IV.1)

**Validator enforced on work_collection (`_WORK_VALIDATOR` — do not modify):**
```python
{
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["work_id", "account_id", "title", "tags"],
        "properties": {
            "work_id":    {"bsonType": "string", "pattern": _UUID4_RE},
            "account_id": {"bsonType": "string", "minLength": 1},
            "title":      {"bsonType": "string", "minLength": 1},
            "tags":       {"bsonType": "array", "items": {"bsonType": "string"}},
        },
    }
}
```

**Indexes on work_collection (do not modify):**
```python
await work_col.create_index([("work_id", 1)], unique=True)
await work_col.create_index([("account_id", 1)])
```

**Lifespan call (api.py:149–158 — do not modify):**
```python
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
```

#### Acceptance Criteria

1. GIVEN the FastAPI server starts WHEN `setup_collections` completes THEN `work_collection` exists in the `fabulator` database.
2. GIVEN `work_collection` exists WHEN a document is inserted directly (bypassing the API) without the `title` field THEN MongoDB rejects the insert with a validation error.
3. GIVEN `work_collection` exists WHEN a document is inserted with `work_id: "not-a-uuid"` (fails UUID4 pattern) THEN MongoDB rejects the insert with a validation error.
4. GIVEN a valid work document is inserted WHEN a second document with the same `work_id` is inserted THEN MongoDB rejects it with a duplicate key error (unique index on `work_id`).
5. GIVEN `setup_collections` is called twice (e.g. server restart) THEN no error is raised — `collMod` updates the validator on the existing collection and `create_index` is a no-op.

**Definition of Done:**
- `work_collection` created with `_WORK_VALIDATOR` enforced
- Unique index on `work_id`
- Non-unique index on `account_id`
- All 5 acceptance criteria pass

---

### Requirement 2: Create node_collection with Validator and Indexes

**User Story:** As a system administrator, I want `node_collection` to be created with schema enforcement and optimised indexes, so that node documents are always valid and relationship queries are efficient.

**Maps to:** `setup_collections` function (database.py:671). (CONSTITUTION IV.7, IV.2, IV.3)

**Validator enforced on node_collection (`_NODE_VALIDATOR` — do not modify):**
```python
{
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["node_id", "work_id", "account_id", "tag", "node_type", "position", "tags"],
        "properties": {
            "node_type":  {"bsonType": "string", "enum": ["part", "chapter", "scene", "beat"]},
            "node_id":    {"bsonType": "string", "pattern": _UUID4_RE},
            "work_id":    {"bsonType": "string", "pattern": _UUID4_RE},
            "account_id": {"bsonType": "string", "minLength": 1},
            "tag":        {"bsonType": "string", "minLength": 1},
            "position":   {"bsonType": ["int", "long"], "minimum": 0},
            "tags":       {"bsonType": "array", "items": {"bsonType": "string"}},
        },
    }
}
```

**Indexes on node_collection — all 5 (do not modify):**
```python
await node_col.create_index([("node_id", 1)], unique=True)
await node_col.create_index([("account_id", 1), ("work_id", 1)])
await node_col.create_index([("account_id", 1), ("parent_id", 1)])
await node_col.create_index([("account_id", 1), ("node_type", 1)])
await node_col.create_index([("account_id", 1), ("node_id", 1)])
```

**Index usage by operation:**
| Index | Used by |
|-------|---------|
| `{node_id: 1}` unique | `get_node`, `update_node`, delete, all single-node lookups |
| `{account_id, work_id}` | `list_nodes`, `get_stats`, `cascade_author_to_nodes`, `delete_work` |
| `{account_id, parent_id}` | `get_children`, `get_roots`, `get_siblings`, sibling position queries |
| `{account_id, node_type}` | `get_leaves` (filters by `"beat"`), type-filtered `list_nodes` |
| `{account_id, node_id}` | `get_node` when called with both fields, cycle detection traversal |

#### Acceptance Criteria

1. GIVEN the FastAPI server starts WHEN `setup_collections` completes THEN `node_collection` exists in the `fabulator` database.
2. GIVEN `node_collection` exists WHEN a document is inserted without the `node_type` field THEN MongoDB rejects the insert with a validation error.
3. GIVEN `node_collection` exists WHEN a document is inserted with `node_type: "volume"` (not in the enum) THEN MongoDB rejects the insert with a validation error.
4. GIVEN `node_collection` exists WHEN a document is inserted with `position: -1` THEN MongoDB rejects the insert (minimum 0 constraint).
5. GIVEN `node_collection` exists WHEN a document is inserted with a valid `node_id` THEN a second document with the same `node_id` is rejected by the unique index.
6. GIVEN `node_collection` exists and has 1000 node documents WHEN `list_nodes(work_id, account_id)` is called THEN the query uses the `{account_id, work_id}` index (verify via `explain()`).
7. GIVEN `setup_collections` is called on an existing `node_collection` THEN no error is raised and existing documents are unchanged.

**Definition of Done:**
- `node_collection` created with `_NODE_VALIDATOR` enforced
- All 5 indexes created
- `node_type` enum enforced at DB level (rejects anything not in `["part", "chapter", "scene", "beat"]`)
- Unique index on `node_id`
- All 7 acceptance criteria pass

---

### Requirement 3: Idempotent Setup and Startup Integration

**User Story:** As an operator, I want `setup_collections` to be safe to call on every server restart, so that I can redeploy without manual database migration.

**Maps to:** `setup_collections` conditional logic (database.py:680–708) and lifespan startup (api.py:156). (CONSTITUTION I.3, II.3)

**How idempotency works (do not modify):**
```python
existing = await db.list_collection_names()
for name, validator in [...]:
    if name not in existing:
        await db.create_collection(name, validator=validator)
    else:
        await db.command("collMod", name, validator=validator)
# Then create_index calls (no-ops if index already exists)
```

#### Acceptance Criteria

1. GIVEN a fresh database with no collections WHEN `setup_collections` is called THEN both `work_collection` and `node_collection` are created with their validators and all 7 indexes.
2. GIVEN `work_collection` and `node_collection` already exist with data WHEN `setup_collections` is called again THEN no existing documents are deleted, no error is raised, and both validators are refreshed via `collMod`.
3. GIVEN `setup_collections` fails (e.g. `OperationFailure`) WHEN the error is raised THEN it propagates through the lifespan startup, which causes the FastAPI app to fail to start. The error is logged via `logger.error(..., exc_info=True)`.
4. GIVEN the server starts successfully THEN `app.state.motor_client` is set before `setup_collections` is called (correct lifespan order as in api.py:150–156).
5. GIVEN a test run calls `setup_collections` on a database that already has the indexes THEN `create_index` calls return without error (MongoDB handles duplicate index creation idempotently).

**Definition of Done:**
- New collection path uses `create_collection` with `validator`
- Existing collection path uses `collMod` to update validator
- All indexes use `create_index` (no-op if already present)
- Errors are caught, logged, and re-raised
- The function is called exactly once in the lifespan before `yield`

---

## Non-Functional Requirements

### Requirement 4: Setup Runs at Startup, Not Per-Request

**User Story:** As a system administrator, I want collection setup to occur once at server startup, not on every request, so that there is no per-request overhead.

**Maps to:** Lifespan context manager (api.py:148–158). (CONSTITUTION I.3, IX.4)

#### Acceptance Criteria

1. GIVEN the FastAPI lifespan context manager WHEN the server starts THEN `setup_collections` is called exactly once before the first request is served.
2. GIVEN a request comes in after startup THEN `setup_collections` is NOT called as part of request handling (it is not in any `Depends()` chain).

---

### Requirement 5: Error Logging and Propagation

**User Story:** As an operator, I want setup failures to be logged with full context and then re-raised, so that I can diagnose startup problems from logs.

**Maps to:** Exception handling in `setup_collections` (database.py:688–697). (CONSTITUTION V.2, V.6)

#### Acceptance Criteria

1. GIVEN `db.create_collection` raises `OperationFailure` WHEN `setup_collections` handles it THEN `logger.error(f"Failed to create collection {name}", exc_info=True)` is called and the error is re-raised.
2. GIVEN `db.command("collMod", ...)` raises `OperationFailure` WHEN handled THEN `logger.error(f"Failed to update validator for {name}", exc_info=True)` is called and the error is re-raised.
3. GIVEN `setup_collections` raises any exception THEN the FastAPI lifespan startup fails and the server does not serve requests.

---

## Correctness Properties

### Property 1: work_id is Globally Unique in work_collection

- **Description:** The unique index on `{work_id: 1}` MUST prevent two Work documents from sharing the same `work_id`. This is enforced at the database level, not just the application level. (CONSTITUTION IV.4)
- **Testable:** Attempt to insert two documents with the same `work_id` directly via Motor. Assert the second insert raises `DuplicateKeyError`.

### Property 2: node_id is Globally Unique in node_collection

- **Description:** The unique index on `{node_id: 1}` MUST prevent two node documents from sharing the same `node_id`. (CONSTITUTION IV.4)
- **Testable:** Attempt to insert two documents with the same `node_id` directly via Motor. Assert the second insert raises `DuplicateKeyError`.

### Property 3: node_type Enum Enforced at DB Level

- **Description:** The `_NODE_VALIDATOR` enforces `node_type` as one of `["part", "chapter", "scene", "beat"]`. No other value may be stored. (CONSTITUTION IV.3)
- **Testable:** Directly insert a document with `node_type: "act"` into `node_collection`. Assert the insert fails with a MongoDB write error. Try all four valid values and assert they succeed.

### Property 4: Position Must Be Non-Negative at DB Level

- **Description:** The `_NODE_VALIDATOR` enforces `position >= 0`. This prevents negative position values from entering the collection even if application code contains a bug. (CONSTITUTION IV.5)
- **Testable:** Directly insert a document with `position: -1` into `node_collection`. Assert the insert fails with a MongoDB write error.

### Property 5: Required Fields Enforced at DB Level

- **Description:** Documents missing any of `["node_id", "work_id", "account_id", "tag", "node_type", "position", "tags"]` for nodes or `["work_id", "account_id", "title", "tags"]` for works MUST be rejected by the validator. (CONSTITUTION IV.1, IV.2)
- **Testable:** For each required field, insert an otherwise valid document without that field. Assert each attempt raises a MongoDB write error with `WriteError`.

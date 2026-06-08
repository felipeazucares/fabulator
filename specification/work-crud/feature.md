# Feature Specification: Work CRUD

**Implementation status:** COMPLETE — all 5 endpoints and all `WorkStorage` methods are committed on branch `refactor/normalised-node-model`. This document is authoritative for verification, test authoring, and any corrective changes.

**Files in scope:**
- `server/app/database.py` — `WorkStorage` class (lines 717–837)
- `server/app/api.py` — 5 Work route handlers (lines 215–352)
- `server/app/models.py` — `CreateWorkRequest`, `UpdateWorkRequest`, `WorkResponse`

---

## Introduction

Works are the top-level container documents for a narrative project. Each Work belongs to exactly one user account (partitioned by `account_id`), holds project metadata (title, description, author, tags), and acts as the foreign-key parent for all Node documents. The `author` field is denormalized onto every child Node at creation time; a `PUT /works/{work_id}` request that changes `author` must cascade that value to all nodes via a single `update_many` in `node_collection`. Work CRUD is the first Tier-1 requirement that must be satisfied before any node operations are possible. (CONSTITUTION Part X, Tier 1)

---

## Glossary

| Term | Definition |
|------|-----------|
| **Work** | A MongoDB document in `work_collection` representing one narrative project |
| **work_id** | UUID4 string. Primary key for a Work. Never MongoDB's `_id`. |
| **account_id** | bcrypt hash of the user's username. Universal tenant partition key. Never returned in API responses. (CONSTITUTION I.4) |
| **author** | Free-text author name on a Work. Denormalized to all child Nodes. (CONSTITUTION I.7) |
| **author cascade** | Bulk `update_many` on `node_collection` setting `author` for all nodes where `{work_id, account_id}` match. Triggered when `PUT /works/{work_id}` updates the `author` field. |
| **TitleStr** | `Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]`. Whitespace-only is rejected by `min_length=1` after stripping. |
| **tag** (on Work) | A label string. Max length 100 chars. Max 50 tags per Work. Empty/whitespace strings rejected. |
| **WorkResponse** | Pydantic response model. Contains: `work_id`, `title`, `description`, `author`, `tags`, `created_at`, `updated_at`. **Does not contain `account_id`.** |

---

## Functional Requirements

### Requirement 1: Create Work

**User Story:** As an authenticated writer, I want to create a new narrative Work, so that I can organise a set of story nodes under a named project.

**Maps to:** `WorkStorage.create_work(account_id: str, data: dict) -> dict` (database.py:724) and `POST /works` handler `create_work` (api.py:227). (CONSTITUTION Part X Tier 1)

**Exact endpoint:**
```
Method:         POST
Path:           /works
Request body:   application/json — CreateWorkRequest
Response body:  WorkResponse
Status on success: 201
Required scope: tree:writer
OpenAPI tags:   ["Works"]
```

**Request shape (`CreateWorkRequest`):**
```json
{
  "title":       "string, required, 1–200 chars, whitespace stripped",
  "description": "string, optional, max 2000 chars",
  "author":      "string, optional, max 200 chars",
  "tags":        ["string array, optional, max 50 items, each max 100 chars"]
}
```

**Response shape (`WorkResponse`):**
```json
{
  "work_id":     "UUID4 string",
  "title":       "string",
  "description": "string or null",
  "author":      "string or null",
  "tags":        ["string array"],
  "created_at":  "ISO8601 UTC datetime",
  "updated_at":  "ISO8601 UTC datetime"
}
```

**What `create_work` in database.py does (do not modify):**
1. Generates `work_id = str(uuid.uuid4())`
2. Sets `created_at = updated_at = datetime.now(timezone.utc)`
3. Inserts document into `work_collection`
4. Returns the document dict with `_id` stripped via `_strip_id(doc)`

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:writer` scope WHEN `POST /works` is called with `{"title": "My Novel", "author": "Jane Doe", "tags": ["fiction"]}` THEN the server returns HTTP 201 with a JSON body containing `work_id` (a valid UUID4 string), `title: "My Novel"`, `author: "Jane Doe"`, `tags: ["fiction"]`, and ISO8601 `created_at`/`updated_at` fields. The response body MUST NOT contain `account_id`.
2. GIVEN a valid JWT with `tree:writer` scope WHEN `POST /works` is called with `{"title": "   "}` (whitespace-only title) THEN the server returns HTTP 422 with a JSON body containing a `detail` field describing the validation error.
3. GIVEN a valid JWT with `tree:writer` scope WHEN `POST /works` is called with `{"title": ""}` (empty title) THEN the server returns HTTP 422.
4. GIVEN a valid JWT with `tree:writer` scope WHEN `POST /works` is called with a `tags` list of 51 items THEN the server returns HTTP 422 with `detail` mentioning the tags limit.
5. GIVEN a valid JWT with `tree:writer` scope WHEN `POST /works` is called with a `tags` list containing an empty string `""` THEN the server returns HTTP 422.
6. GIVEN no Authorization header WHEN `POST /works` is called THEN the server returns HTTP 401.
7. GIVEN a valid JWT containing only `tree:reader` scope (not `tree:writer`) WHEN `POST /works` is called THEN the server returns HTTP 403 with `detail: "Insufficient permissions to complete action"`.
8. GIVEN a valid JWT with `tree:writer` scope WHEN `POST /works` is called with a valid body but the database raises `ConnectionFailure` or `OperationFailure` THEN the server returns HTTP 503 with `detail: "Database error"`. The raw exception MUST NOT appear in the response body.

**Definition of Done:**
- `POST /works` returns 201 on valid input
- `WorkResponse` is declared as `response_model` on the decorator
- `summary`, `description`, `tags=["Works"]` are present on the decorator
- Whitespace-only title returns 422
- Tags list > 50 returns 422
- `account_id` is absent from the response body
- A new document appears in `work_collection` with correct `work_id`, `account_id`, and timestamps

---

### Requirement 2: List Works

**User Story:** As an authenticated reader, I want to list all my Works ordered by creation date, so that I can see my projects at a glance.

**Maps to:** `WorkStorage.list_works(account_id: str) -> list[dict]` (database.py:757) and `GET /works` handler `list_works` (api.py:254). (CONSTITUTION Part X Tier 1)

**Exact endpoint:**
```
Method:         GET
Path:           /works
Query params:   none
Response body:  list[WorkResponse]
Status on success: 200
Required scope: tree:reader
OpenAPI tags:   ["Works"]
```

**What `list_works` in database.py does (do not modify):**
1. Queries `work_collection` with `{"account_id": account_id}`, sorted `created_at` descending
2. Returns list of dicts with `_id` stripped

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:reader` scope and at least two Works for the account WHEN `GET /works` is called THEN the server returns HTTP 200 with a JSON array of `WorkResponse` objects ordered by `created_at` descending (most recent first).
2. GIVEN a valid JWT with `tree:reader` scope and no Works for the account WHEN `GET /works` is called THEN the server returns HTTP 200 with an empty JSON array `[]`.
3. GIVEN User A has Works and User B is authenticated WHEN User B calls `GET /works` THEN User B receives only their own Works (account isolation enforced by `account_id` filter in `list_works`).
4. GIVEN no Authorization header WHEN `GET /works` is called THEN the server returns HTTP 401.
5. GIVEN a valid JWT without `tree:reader` scope WHEN `GET /works` is called THEN the server returns HTTP 403.

**Definition of Done:**
- `GET /works` returns 200 with correct array
- Result is ordered by `created_at` descending
- `account_id` absent from every item in the response array
- Empty array returned (not 404) when no Works exist

---

### Requirement 3: Get Single Work

**User Story:** As an authenticated reader, I want to fetch a single Work by its ID, so that I can display its details.

**Maps to:** `WorkStorage.get_work(work_id: str, account_id: str) -> dict | None` (database.py:745) and `GET /works/{work_id}` handler `get_work` (api.py:277). (CONSTITUTION I.4, Part X Tier 1)

**Exact endpoint:**
```
Method:         GET
Path:           /works/{work_id}
Path params:    work_id — must match UUID4 pattern via Path(pattern=UUID_PATTERN)
Response body:  WorkResponse
Status on success: 200
Required scope: tree:reader
OpenAPI tags:   ["Works"]
```

**UUID4 pattern (from models.py):**
```
r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
```

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:reader` scope and a `work_id` belonging to the authenticated account WHEN `GET /works/{work_id}` is called THEN the server returns HTTP 200 with the `WorkResponse` for that Work.
2. GIVEN a valid JWT with `tree:reader` scope WHEN `GET /works/{work_id}` is called with a `work_id` that does not exist in `work_collection` THEN the server returns HTTP 404 with `detail: "Work not found"`.
3. GIVEN User A owns Work W and User B is authenticated WHEN User B calls `GET /works/{W.work_id}` THEN the server returns HTTP 404 (not 403, not 200). (CONSTITUTION I.4)
4. GIVEN a valid JWT WHEN `GET /works/{work_id}` is called with a `work_id` that is not a valid UUID4 string (e.g. `"not-a-uuid"`) THEN the server returns HTTP 422.
5. GIVEN no Authorization header WHEN `GET /works/{work_id}` is called THEN the server returns HTTP 401.

**Definition of Done:**
- 200 with WorkResponse for owned work
- 404 with exact detail `"Work not found"` for missing or cross-account work
- 422 for invalid UUID4 path param

---

### Requirement 4: Update Work

**User Story:** As an authenticated writer, I want to update Work metadata and have `author` changes automatically propagated to all child nodes, so that my attribution stays consistent.

**Maps to:** `WorkStorage.update_work(work_id, account_id, updates) -> dict | None` and `WorkStorage.cascade_author_to_nodes(work_id, account_id, author)` (database.py:771, 797) and `PUT /works/{work_id}` handler `update_work` (api.py:304). (CONSTITUTION I.7, Part X Tier 1)

**Exact endpoint:**
```
Method:         PUT
Path:           /works/{work_id}
Path params:    work_id — UUID4 pattern
Request body:   UpdateWorkRequest (all fields optional)
Response body:  WorkResponse (updated state)
Status on success: 200
Required scope: tree:writer
OpenAPI tags:   ["Works"]
```

**Request shape (`UpdateWorkRequest` — all optional, omitted fields unchanged):**
```json
{
  "title":       "string, optional, 1–200 chars",
  "description": "string, optional, max 2000 chars",
  "author":      "string, optional, max 200 chars",
  "tags":        ["string array, optional"]
}
```

**Author cascade trigger (in `update_work`, database.py:789):**
```python
if "author" in updates:
    await self.cascade_author_to_nodes(work_id=work_id, account_id=account_id, author=updates["author"])
```
This is a bulk `update_many` on `node_collection` setting `{"author": <new_value>}` for all nodes where `{work_id, account_id}` match.

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:writer` scope and an owned Work WHEN `PUT /works/{work_id}` is called with `{"title": "Updated Title"}` THEN the server returns HTTP 200 with a `WorkResponse` where `title` is `"Updated Title"` and `updated_at` is later than the original `created_at`.
2. GIVEN a valid JWT with `tree:writer` scope and an owned Work with child nodes WHEN `PUT /works/{work_id}` is called with `{"author": "New Author"}` THEN the server returns HTTP 200 and all nodes in `node_collection` with that `work_id` have `author` set to `"New Author"`.
3. GIVEN a valid JWT with `tree:writer` scope WHEN `PUT /works/{work_id}` is called on a non-existent or cross-account `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.
4. GIVEN a valid JWT with `tree:writer` scope WHEN `PUT /works/{work_id}` is called with `{"title": ""}` THEN the server returns HTTP 422 (empty title not allowed).
5. GIVEN a valid JWT with `tree:reader` scope only WHEN `PUT /works/{work_id}` is called THEN the server returns HTTP 403.

**Definition of Done:**
- 200 with updated WorkResponse
- `updated_at` is refreshed on every update
- When `author` is in the update payload, `cascade_author_to_nodes` is called
- 404 for missing or cross-account work
- Omitted fields are not changed

---

### Requirement 5: Delete Work with Node Cascade

**User Story:** As an authenticated writer, I want to delete a Work and all its associated nodes in one operation, so that I leave no orphaned data.

**Maps to:** `WorkStorage.delete_work(work_id, account_id) -> tuple[bool, int]` (database.py:814) and `DELETE /works/{work_id}` handler `delete_work` (api.py:336). (CONSTITUTION I.1, Part X Tier 1)

**Exact endpoint:**
```
Method:         DELETE
Path:           /works/{work_id}
Path params:    work_id — UUID4 pattern
Response body:  {"detail": "Work deleted. {N} node(s) removed."}
Status on success: 200
Required scope: tree:writer
OpenAPI tags:   ["Works"]
```

**What `delete_work` does (do not modify):**
1. `delete_one` on `work_collection` with `{work_id, account_id}`
2. If `deleted_count == 0`, returns `(False, 0)` → API raises 404
3. `delete_many` on `node_collection` with `{work_id, account_id}`
4. Returns `(True, node_result.deleted_count)`

**Note:** `DELETE /works/{work_id}` currently has no `response_model` declared (pre-existing violation of CONSTITUTION III.2). A downstream agent writing new delete-style endpoints MUST declare `response_model`.

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:writer` scope and a Work with 3 child nodes WHEN `DELETE /works/{work_id}` is called THEN the server returns HTTP 200 with body `{"detail": "Work deleted. 3 node(s) removed."}` and no documents remain in `work_collection` or `node_collection` for that `work_id`.
2. GIVEN a valid JWT with `tree:writer` scope and a Work with no child nodes WHEN `DELETE /works/{work_id}` is called THEN the server returns HTTP 200 with body `{"detail": "Work deleted. 0 node(s) removed."}`.
3. GIVEN a valid JWT with `tree:writer` scope WHEN `DELETE /works/{work_id}` is called with a non-existent or cross-account `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.
4. GIVEN a valid JWT with `tree:reader` scope only WHEN `DELETE /works/{work_id}` is called THEN the server returns HTTP 403.

**Definition of Done:**
- Work document removed from `work_collection`
- All node documents for that work removed from `node_collection`
- Response body matches exact format `"Work deleted. {N} node(s) removed."`
- 404 returned for missing or cross-account work

---

## Non-Functional Requirements

### Requirement 6: Authentication and Scope Enforcement

**User Story:** As a system administrator, I want every Work endpoint to enforce JWT authentication and scope checks, so that unauthenticated or under-scoped clients cannot access or modify Works.

**Maps to:** `Security(get_current_active_user_account, scopes=[...])` on every handler (CONSTITUTION II.2, II.4)

#### Acceptance Criteria

1. GIVEN no `Authorization` header WHEN any Work endpoint is called THEN the server returns HTTP 401 with `detail: "Could not validate credentials"`.
2. GIVEN a valid JWT but missing the required scope WHEN a write endpoint (`POST`, `PUT`, `DELETE /works`) is called THEN the server returns HTTP 403 with `detail: "Insufficient permissions to complete action"`.
3. GIVEN a valid JWT but missing `tree:reader` scope WHEN `GET /works` or `GET /works/{work_id}` is called THEN the server returns HTTP 403.
4. GIVEN a blacklisted token (after `GET /logout`) WHEN any Work endpoint is called with that token THEN the server returns HTTP 401.

---

### Requirement 7: Account Isolation

**User Story:** As a user, I want my Works to be invisible to other users, so that my narrative projects remain private.

**Maps to:** All `WorkStorage` queries include `{"account_id": account_id}` filter (CONSTITUTION I.4)

#### Acceptance Criteria

1. GIVEN User A has a Work and User B is authenticated WHEN User B calls `GET /works/{A's work_id}` THEN the server returns HTTP 404 (not HTTP 403).
2. GIVEN User A has a Work and User B is authenticated WHEN User B calls `PUT /works/{A's work_id}` with a valid body THEN the server returns HTTP 404.
3. GIVEN User A has a Work and User B is authenticated WHEN User B calls `DELETE /works/{A's work_id}` THEN the server returns HTTP 404.
4. GIVEN User A and User B each have Works WHEN User B calls `GET /works` THEN the response contains only User B's Works, never User A's.

---

### Requirement 8: Input Validation

**User Story:** As an API consumer, I want clear validation errors for malformed requests, so that I can correct my input without server-side crashes.

**Maps to:** Pydantic `CreateWorkRequest`, `UpdateWorkRequest`; `Path(pattern=UUID_PATTERN)` (CONSTITUTION II.4)

#### Acceptance Criteria

1. GIVEN a `POST /works` body with `title` longer than 200 characters THEN the server returns HTTP 422.
2. GIVEN a `POST /works` body with `author` longer than 200 characters THEN the server returns HTTP 422.
3. GIVEN a `POST /works` body with `description` longer than 2000 characters THEN the server returns HTTP 422.
4. GIVEN a `GET /works/{work_id}` call where `work_id` is not a valid UUID4 string THEN the server returns HTTP 422 (enforced by `Path(pattern=UUID_PATTERN)` in the handler signature).
5. GIVEN a `POST /works` body with a `tags` item that is an empty string `""` THEN the server returns HTTP 422.
6. GIVEN a `POST /works` body with a `tags` item longer than 100 characters THEN the server returns HTTP 422.

---

### Requirement 9: Error Message Format

**User Story:** As an API consumer, I want sanitised error messages that never expose internal server details, so that my clients are robust and the API is secure.

**Maps to:** CONSTITUTION II.5, III.6

#### Acceptance Criteria

1. GIVEN any Work endpoint error THEN the response body contains exactly `{"detail": "<human-readable message>"}` with no stack trace, no `account_id`, no MongoDB internal IDs.
2. GIVEN a database failure (`ConnectionFailure` or `OperationFailure`) WHEN any Work endpoint is called THEN the server returns HTTP 503 with `detail: "Database error"`. The raw exception is logged to `logger.error(..., exc_info=True)` only.
3. GIVEN a 404 error THEN `detail` is exactly `"Work not found"` (not `"Work not found for account XYZ"`).

---

## Correctness Properties

### Property 1: account_id Never Exposed

- **Description:** The `account_id` field MUST NOT appear in any Work endpoint response body. It is an internal partition key only. (CONSTITUTION I.4, II.5)
- **Testable:** Inspect every Work endpoint response body. Assert `"account_id"` key is absent. The `WorkResponse` model excludes it by design.

### Property 2: work_id is Always UUID4

- **Description:** Every Work document in `work_collection` MUST have a `work_id` value matching the UUID4 pattern. Generated by `str(uuid.uuid4())` in `create_work`. (CONSTITUTION IV.4)
- **Testable:** After `POST /works`, assert `re.match(UUID4_PATTERN, response["work_id"])` is truthy.

### Property 3: Timestamps are Always UTC

- **Description:** `created_at` and `updated_at` MUST be set using `datetime.now(timezone.utc)`. `datetime.utcnow()` and `pytz` are prohibited. (CONSTITUTION IV.6)
- **Testable:** After any Work write, assert the stored timestamp is timezone-aware UTC. In Python: `assert work["created_at"].tzinfo is not None`.

### Property 4: Author Cascade is Atomic and Complete

- **Description:** When `PUT /works/{work_id}` changes the `author` field, `cascade_author_to_nodes` MUST be called with the new value. All nodes in `node_collection` with `{work_id, account_id}` MUST have `author` updated to the new value before the response is returned. No partial update is acceptable. (CONSTITUTION I.7)
- **Testable:** Create a Work with author "A", add 3 nodes, then `PUT /works/{id}` with `{"author": "B"}`. After the response, query `node_collection` and assert all 3 nodes have `author: "B"`.

### Property 5: Work Delete Removes All Nodes

- **Description:** After `DELETE /works/{work_id}`, no documents in `node_collection` with that `work_id` MUST remain. This is enforced by `delete_many` on `node_collection` in `WorkStorage.delete_work`. (CONSTITUTION I.1)
- **Testable:** Create Work, add nodes, delete Work, query `node_collection` with `{"work_id": deleted_id}` and assert empty result.

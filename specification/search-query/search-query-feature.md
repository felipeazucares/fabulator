# Feature Specification: Search & Query (Tier 3)
 
**Implementation status:** NOT STARTED — Tier 3. Blocked until Tier 2 (navigation) is verified complete per the CONSTITUTION roadmap. This document is authoritative for implementation, test authoring, and review.
 
## Introduction
 
Tier 3 adds read-only discovery over the existing `node_collection`. Two endpoints are added: a full-text search over node `description` and `text` fields, and a tag-based query over the node `tags` array. Both are strictly account-isolated (every query carries `{account_id}`), require only `tree:reader` scope, mutate nothing, and return the existing `NodeResponse` shape so the frontend can reuse its node renderer. Search depends on a MongoDB `$text` index and a multikey index on `tags`, both created idempotently in `setup_collections`. (CONSTITUTION Part X Tier 3; `CLAUDE.md:294–301`, `CLAUDE.md:335–336`)
 
---
 
## Glossary
 
| Term | Definition |
|------|-----------|
| **node** | A MongoDB document in `node_collection`. Content fields: `description`, `text`, `tag` (singular title), `tags` (label array). (`CLAUDE.md:48`) |
| **searchable fields** | `description` and `text` only. The `$text` index covers exactly these two fields. (`CLAUDE.md:335`) `tag` and `tags` are **not** covered by the text index — tag discovery uses Requirement 2. |
| **account_id** | bcrypt hash of the username. Universal tenant partition key. Never returned. (CONSTITUTION I.4) Every search/tag query MUST filter on it. |
| **NodeResponse** | Existing Pydantic model: `node_id`, `work_id`, `author`, `node_type`, `parent_id`, `position`, `tag`, `description`, `text`, `previous`, `next`, `tags`, `created_at`, `updated_at`. **No `account_id`.** (REQUIREMENTS Glossary) |
| **NodeSearchResponse** | `{"results": [NodeResponse, ...], "count": int}`. For `/nodes/search`, results are ordered by descending `textScore`. For `/nodes/by-tag`, results are ordered by `created_at` descending (no relevance score applies). |
| **$text index** | A single MongoDB text index spanning `description` and `text`, named `node_text_idx`. Only one text index is permitted per collection. (`CLAUDE.md:335`) |
| **tags index** | A multikey index on `{account_id: 1, tags: 1}` named `node_tags_idx`, supporting account-scoped tag queries. (`CLAUDE.md:336`) |
| **TextQueryStr** | `Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]`. Whitespace-only `query` rejected by `min_length=1` after stripping. |
| **node_type** | Enum `"part" \| "chapter" \| "scene" \| "beat"`. (REQUIREMENTS:39) Optional filter on both endpoints. |
 
---
 
## Functional Requirements
 
### Requirement 1: Full-Text Search Across Nodes
 
**User Story:** As an authenticated reader, I want to search the description and text of my nodes for a phrase, so that I can find relevant story content in a large narrative without manually traversing the tree.
 
**Maps to:** `SearchStorage.search_nodes(account_id, query, work_id=None, node_type=None) -> list[dict]` (database.py, new) and `GET /nodes/search` handler `search_nodes` (api.py, new). (`CLAUDE.md:300`; CONSTITUTION Part X Tier 3)
 
**Exact endpoint:**
```
Method:            GET
Path:              /nodes/search
Query params:      query    — required, TextQueryStr (1–200 chars, stripped)
                   work_id  — optional, UUID4 pattern; narrows to one Work
                   node_type — optional, one of part|chapter|scene|beat
                   limit    — optional, int 1–200, default 50
Response body:     NodeSearchResponse
Status on success: 200
Required scope:    tree:reader
OpenAPI tags:      ["Search"]
```
 
**What `search_nodes` does:**
1. Builds a filter `{"account_id": account_id, "$text": {"$search": query}}`, plus `work_id` and `node_type` when supplied.
2. Projects `textScore` via `{"score": {"$meta": "textScore"}}`.
3. Sorts by `{"score": {"$meta": "textScore"}}` descending, applies `limit`.
4. Returns list of dicts with `_id` stripped (reuse existing `_strip_id`). The transient `score` field is NOT included in `NodeResponse`.
**Example request:**
```
GET /nodes/search?query=lighthouse&node_type=beat&limit=20
Authorization: Bearer <jwt with tree:reader>
```
 
**Example response (200):**
```json
{
  "results": [
    {
      "node_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "work_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "author": "Jane Doe",
      "node_type": "beat",
      "parent_id": "1c8e5f3a-2d4b-4e6f-8a9c-0b1d2e3f4a5b",
      "position": 2,
      "tag": "The keeper's vigil",
      "description": "Aila climbs the lighthouse stair.",
      "text": "The lighthouse beam swept the black water...",
      "previous": null,
      "next": null,
      "tags": ["setting:lighthouse"],
      "created_at": "2026-04-01T09:30:00Z",
      "updated_at": "2026-04-01T09:30:00Z"
    }
  ],
  "count": 1
}
```
 
#### Acceptance Criteria
 
1. GIVEN a valid JWT with `tree:reader` scope and a node whose `text` contains the word "lighthouse" WHEN `GET /nodes/search?query=lighthouse` is called THEN the server returns HTTP 200 with `NodeSearchResponse` where `results` contains that node and `count` equals the number of matches. No item contains `account_id`.
2. GIVEN nodes match in both `description` and `text` WHEN `GET /nodes/search?query=<term>` is called THEN matches from either field are returned (the index spans both fields).
3. GIVEN multiple matching nodes with differing relevance WHEN search is called THEN `results` are ordered by descending `textScore`.
4. GIVEN no nodes match WHEN search is called THEN the server returns HTTP 200 with `{"results": [], "count": 0}`.
5. GIVEN `?query=` is empty or whitespace-only WHEN search is called THEN the server returns HTTP 422 (enforced by `TextQueryStr` `min_length=1` after stripping).
6. GIVEN `?work_id=<W>` is supplied WHEN search is called THEN only nodes whose `work_id == W` are returned.
7. GIVEN `?node_type=scene` is supplied WHEN search is called THEN only `scene` nodes are returned; an invalid `node_type` returns HTTP 422.
8. GIVEN User A has a matching node and User B is authenticated WHEN User B searches the same term THEN User B receives only their own matches (account isolation via the `account_id` filter).
9. GIVEN no Authorization header WHEN search is called THEN HTTP 401. GIVEN a JWT without `tree:reader` scope THEN HTTP 403 with `detail: "Insufficient permissions to complete action"`.
10. GIVEN the database raises `ConnectionFailure` or `OperationFailure` WHEN search is called THEN HTTP 503 with `detail: "Database error"`; the raw exception is logged with `exc_info=True` only and MUST NOT appear in the response.
11. **(Known limitation, documented not bug)** GIVEN a node text contains "lighthouses" WHEN `query=lighthouse` is called THEN it MAY match via stemming, but a substring like `query=light` is NOT guaranteed to match "lighthouse" — `$text` matches whole stemmed tokens, not substrings.
**Definition of Done:**
- `GET /nodes/search` returns 200 with `NodeSearchResponse` and `response_model` declared on the decorator (CONSTITUTION III.2).
- `summary`, `description`, `tags=["Search"]` present on the decorator.
- Empty/whitespace `query` returns 422.
- Results ordered by `textScore` descending.
- `account_id` and the transient `score` field absent from every result item.
- Query plan uses `node_text_idx` (verifiable via `explain()`).
---
 
### Requirement 2: Query Nodes by Tag(s)
 
**User Story:** As an authenticated reader, I want to retrieve all nodes carrying one or more tags, so that I can gather every node related to a theme, character, or plot thread.
 
**Maps to:** `SearchStorage.find_nodes_by_tags(account_id, tags, match="any", work_id=None) -> list[dict]` (database.py, new) and `GET /nodes/by-tag` handler `nodes_by_tag` (api.py, new). (`CLAUDE.md:301`; CONSTITUTION Part X Tier 3)
 
**Exact endpoint:**
```
Method:            GET
Path:              /nodes/by-tag
Query params:      tags    — required, repeated query param (?tags=a&tags=b) or CSV; 1–50 items, each 1–100 chars
                   match   — optional, "any" (default) | "all"
                   work_id — optional, UUID4 pattern
                   node_type — optional, one of part|chapter|scene|beat
Response body:     NodeSearchResponse
Status on success: 200
Required scope:    tree:reader
OpenAPI tags:      ["Search"]
```
 
**What `find_nodes_by_tags` does:**
1. For `match="any"`: filter `{"account_id": account_id, "tags": {"$in": tags}}`.
2. For `match="all"`: filter `{"account_id": account_id, "tags": {"$all": tags}}`.
3. Adds `work_id` / `node_type` when supplied.
4. Sorts `created_at` descending. Returns dicts with `_id` stripped.
**Example request:**
```
GET /nodes/by-tag?tags=foreshadowing&tags=romance&match=all
Authorization: Bearer <jwt with tree:reader>
```
 
**Example response (200):**
```json
{
  "results": [
    {
      "node_id": "a3bb189e-8bf9-4055-a76c-2d4e3f5a6b7c",
      "work_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "author": "Jane Doe",
      "node_type": "scene",
      "parent_id": "1c8e5f3a-2d4b-4e6f-8a9c-0b1d2e3f4a5b",
      "position": 0,
      "tag": "First meeting",
      "description": "They meet on the quay.",
      "text": "The gulls wheeled overhead as she stepped ashore...",
      "previous": null,
      "next": null,
      "tags": ["foreshadowing", "romance"],
      "created_at": "2026-04-02T11:00:00Z",
      "updated_at": "2026-04-02T11:00:00Z"
    }
  ],
  "count": 1
}
```
 
#### Acceptance Criteria
 
1. GIVEN nodes tagged `["foreshadowing"]` and `["foreshadowing","romance"]` WHEN `GET /nodes/by-tag?tags=foreshadowing` is called THEN both nodes are returned (default `match=any`).
2. GIVEN the same data WHEN `GET /nodes/by-tag?tags=foreshadowing&tags=romance&match=all` is called THEN only the node carrying BOTH tags is returned.
3. GIVEN no `tags` param WHEN the endpoint is called THEN HTTP 422.
4. GIVEN a `tags` item that is an empty string or exceeds 100 chars, or more than 50 items, THEN HTTP 422 (mirrors Work/Node tag constraints).
5. GIVEN no node carries any supplied tag WHEN called THEN HTTP 200 with `{"results": [], "count": 0}`.
6. GIVEN `?work_id=<W>` / `?node_type=<t>` supplied THEN results are correspondingly narrowed.
7. GIVEN User A has tagged nodes and User B is authenticated WHEN User B queries the same tag THEN User B receives only their own nodes.
8. GIVEN no Authorization header THEN HTTP 401; GIVEN missing `tree:reader` scope THEN HTTP 403.
9. GIVEN a database failure THEN HTTP 503 with `detail: "Database error"`; raw exception logged only.
**Definition of Done:**
- `GET /nodes/by-tag` returns 200 with `NodeSearchResponse` and `response_model` declared.
- `match=any` and `match=all` behave per AC 1–2; invalid `match` value returns 422.
- Tag validation matches existing node-tag rules (≤50 items, each 1–100 chars, no empty strings).
- `account_id` absent from every result item.
- Query plan uses `node_tags_idx` (verifiable via `explain()`).
---
 
### Requirement 3: Search Indexes in `setup_collections`
 
**User Story:** As an operator, I want the text and tag indexes created idempotently at startup, so that search is fast and redeploys need no manual migration.
 
**Maps to:** Index creation appended to `setup_collections` (database.py). Extends the existing index set described in REQUIREMENTS Req 27–28. (`CLAUDE.md:335–336`; CONSTITUTION IV)
 
#### Acceptance Criteria
 
1. GIVEN the server starts on a fresh database WHEN `setup_collections` completes THEN `node_collection` has a text index `node_text_idx` spanning `description` and `text`, and a multikey index `node_tags_idx` on `{account_id: 1, tags: 1}`.
2. GIVEN `setup_collections` runs a second time WHEN re-invoked THEN no error is raised and no data is deleted (idempotent; index creation is safe to repeat). (mirrors REQUIREMENTS Req 28 AC 2)
3. GIVEN a `$text` search runs against 1000 nodes WHEN executed THEN `explain()` shows `node_text_idx` is used (no `COLLSCAN`).
4. GIVEN a tag query runs against 1000 nodes WHEN executed THEN `explain()` shows `node_tags_idx` is used.
5. GIVEN an attempt to add a second text index with a different field set WHEN `setup_collections` runs THEN it does not raise (only one text index per collection is permitted; the existing one is reused, not duplicated).
**Definition of Done:**
- Both indexes exist after startup with the stated names.
- Re-running `setup_collections` is non-destructive and non-erroring.
- The total index count in REQUIREMENTS Req 28 AC 1 ("all 7 indexes") is updated to reflect the two new indexes — **flag for the spec owner: that count becomes 9.**
---
 
## Non-Functional Requirements
 
### Requirement 4: Authentication and Scope Enforcement
 
**Maps to:** `Security(get_current_active_user_account, scopes=["tree:reader"])` on both handlers. (CONSTITUTION II.2, II.4)
 
#### Acceptance Criteria
1. GIVEN no `Authorization` header WHEN either search endpoint is called THEN HTTP 401 with `detail: "Could not validate credentials"`.
2. GIVEN a valid JWT missing `tree:reader` scope WHEN either endpoint is called THEN HTTP 403 with `detail: "Insufficient permissions to complete action"`.
3. GIVEN a blacklisted token (after `GET /logout`) WHEN either endpoint is called THEN HTTP 401.
### Requirement 5: Account Isolation
 
**Maps to:** Every `SearchStorage` query includes `{"account_id": account_id}`. (CONSTITUTION I.4)
 
#### Acceptance Criteria
1. GIVEN User A's node matches a term/tag and User B is authenticated WHEN User B searches THEN User A's node never appears in User B's results.
2. GIVEN `?work_id=<A's work_id>` belonging to another account WHEN User B searches THEN results are empty (the `account_id` filter excludes it); the endpoint returns HTTP 200 with `count: 0`, NOT 403.
### Requirement 6: Input Validation
 
**Maps to:** Pydantic query-param models; `Query(...)` constraints. (CONSTITUTION II.4)
 
#### Acceptance Criteria
1. `query` > 200 chars → HTTP 422.
2. `query` empty/whitespace → HTTP 422.
3. `tags` with > 50 items, an empty item, or an item > 100 chars → HTTP 422.
4. `work_id` not a valid UUID4 → HTTP 422 (`Query(pattern=UUID_PATTERN)`).
5. `node_type` not in the enum → HTTP 422.
6. `match` not in `{any, all}` → HTTP 422.
7. `limit` outside 1–200 → HTTP 422.
### Requirement 7: Error Message Format
 
**Maps to:** CONSTITUTION II.5, III.6
 
#### Acceptance Criteria
1. Any error body is exactly `{"detail": "<message>"}` — no stack trace, no `account_id`, no MongoDB internals.
2. `ConnectionFailure`/`OperationFailure` → HTTP 503, `detail: "Database error"`, raw exception via `logger.error(..., exc_info=True)` only.
---
 
## Correctness Properties
 
### Property 1: Search and Tag Queries Are Strictly Account-Scoped
- **Description:** No node belonging to another `account_id` may ever appear in any search or tag result. Enforced by the `{account_id}` filter on every `SearchStorage` query. (CONSTITUTION I.4)
- **Testable:** Seed nodes for User A and User B with an identical term/tag; assert each user's results contain only their own `node_id`s.
### Property 2: Endpoints Are Read-Only
- **Description:** Neither endpoint mutates `node_collection`, `work_collection`, or any other collection. (CONSTITUTION; Tier 3 is query-only)
- **Testable:** Capture document counts and a content hash before and after a batch of search/tag calls; assert unchanged.
### Property 3: account_id Never Exposed
- **Description:** No result item contains `account_id`; the transient `textScore` (`score`) field is also excluded. (CONSTITUTION I.4, II.5)
- **Testable:** Assert `"account_id"` and `"score"` keys are absent from every item in `results`.
### Property 4: Text Index Coverage Matches Spec
- **Description:** The `$text` index spans exactly `description` and `text` (`CLAUDE.md:335`) — not `tag`/`tags`. Tag discovery is Requirement 2 only.
- **Testable:** A node matching only via `tags` MUST NOT be returned by `/nodes/search`; it MUST be returned by `/nodes/by-tag`.
### Property 5: Index Usage (No Collection Scans)
- **Description:** Search uses `node_text_idx`; tag queries use `node_tags_idx`. (`CLAUDE.md:335–336`)
- **Testable:** Run `explain()` on each query against ≥1000 seeded nodes; assert the named index is the winning plan and `COLLSCAN` is absent.
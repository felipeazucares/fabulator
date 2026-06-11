# Feature Specification: Work Reading Order (Tier 3)
 
**Implementation status:** COMPLETED ✅ — Merged to `main` 2026-06-11. Endpoint live at `GET /works/{work_id}/nodes/ordered`, tagged `["Search"]`.
 
## Introduction
 
This feature adds one read-only endpoint that returns **every node of a single Work, flattened into narrative reading order**, with the full `NodeResponse` metadata for each node. It is an addition to the Tier 3 Search & Query feature: a query-only, strictly account-isolated (`{account_id}` on every query) read that mutates nothing and requires only `tree:reader` scope.
 
Ordering is produced by a **depth-first pre-order traversal of the adjacency-list hierarchy, with siblings ordered by `position` ascending** — i.e. Part → its Chapters in order → each Chapter's Scenes in order → each Scene's Beats in order. This is the only ordering the data model enforces: `position` is guaranteed contiguous and gap-free (CONSTITUTION IV.5) and the `parent_id` chain is guaranteed acyclic (REQUIREMENTS CP 14), so the traversal is total, deterministic, and terminating by construction.
 
The node `previous` / `next` fields are **NOT** used to sequence the output. Per `node-crud-feature.md` (lines 67–68, 231–232) and DESIGN §I.1 ("Ordering authority") they are optional free-text narrative hints (max 200 chars, explicitly *not* UUIDs); they carry no uniqueness, cycle, or coverage guarantee and are not indexed. They ride along unchanged inside each `NodeResponse` as metadata, but are never trusted to order the sequence. (Resolved design decision; see Correctness Property 4.)
 
The endpoint reuses the existing `{account_id, work_id}` index on `node_collection` (REQUIREMENTS Req 27) — **no new index is required.**
 
---
 
## Glossary
 
| Term | Definition |
|------|-----------|
| **node** | A MongoDB document in `node_collection`. (`CLAUDE.md:48`) |
| **reading order** | The sequence produced by a depth-first **pre-order** traversal of the `parent_id` hierarchy for one Work, visiting each node before its children and ordering siblings by `position` ascending. The parent always precedes its descendants. |
| **account_id** | bcrypt hash of the username. Universal tenant partition key. Never returned. (CONSTITUTION I.4) Every query MUST filter on it. |
| **NodeResponse** | Existing Pydantic model: `node_id`, `work_id`, `author`, `node_type`, `parent_id`, `position`, `tag`, `description`, `text`, `previous`, `next`, `tags`, `created_at`, `updated_at`. **No `account_id`.** (REQUIREMENTS Glossary) |
| **OrderedNodesResponse** | New Pydantic model: `{"work_id": str, "nodes": [NodeResponse, ...], "count": int, "next_cursor": str \| null}`. `nodes` is the reading-order slice for the current page; `count` is the number of items in `nodes`; `next_cursor` is the opaque cursor for the next page, or `null` when the Work has been fully returned. |
| **cursor** | An opaque pagination token equal to the `node_id` of the last node on the previous page. The next page resumes at the node immediately **after** that node in the full reading-order sequence. Absent on the first request. |
| **previous / next** | Optional free-text narrative hint strings (max 200 chars, not UUIDs). Returned as metadata; **never** used to order the output. (`node-crud-feature.md:67–68`; DESIGN §I.1) |
 
---
 
## Functional Requirements
 
### Requirement 1: Return a Work's Nodes in Reading Order
 
**User Story:** As an authenticated reader, I want to retrieve all nodes of one Work flattened into narrative reading order with full metadata, so that I can render, export, or read the whole story linearly without traversing the tree client-side.
 
**Maps to:** `NodeStorage.get_reading_order(work_id, account_id) -> list[dict]` (database.py, new) and `GET /works/{work_id}/nodes/ordered` handler `get_work_reading_order` (api.py, new). (CONSTITUTION Part X Tier 3)
 
**Exact endpoint:**
```
Method:            GET
Path:              /works/{work_id}/nodes/ordered
Path params:       work_id — required, UUID4 pattern via Path(pattern=UUID_PATTERN)
Query params:      limit   — optional, int 1–200, default 50
                   cursor  — optional, UUID4 pattern; node_id to resume after
Response body:     OrderedNodesResponse
Status on success: 200
Required scope:    tree:reader
OpenAPI tags:      ["Search"]
```
 
**What `get_reading_order` does:**
1. Fetches all nodes for the Work with the filter `{"account_id": account_id, "work_id": work_id}` (uses the existing `{account_id, work_id}` index).
2. Builds an in-memory `parent_id → children` map and the set of root nodes (`parent_id is None`).
3. Sorts roots by `position` ascending, then performs a depth-first **pre-order** walk, sorting each node's children by `position` ascending before recursing. A `visited` set guards against cycles defensively (the chain is guaranteed acyclic by CP 14; a detected repeat is logged at error level and the node is skipped, never re-entered).
4. Returns the ordered list of node dicts with `_id` stripped (reuse existing `_strip_id`).
**Pagination (CONSTITUTION IX.4 — mandatory on list endpoints):** The handler materialises the full ordered list from `get_reading_order`, then applies cursor + `limit` over that sequence:
- No `cursor`: slice `[0 : limit]`.
- With `cursor`: locate the index of the node whose `node_id == cursor`; slice `[index+1 : index+1+limit]`. A `cursor` that is not present in the Work's node set returns HTTP 422 `detail: "Invalid cursor"`.
- `next_cursor` is the `node_id` of the last node in the returned slice when more nodes remain after it, else `null`.
> **Flag for the spec owner:** pagination uses an **opaque `node_id` cursor over a server-materialised pre-order sequence**, not a MongoDB range cursor, because pre-order is not expressible as a single indexed sort. Materialisation is O(n) per page within one Work (bounded; one Work ≈ one manuscript). If per-Work node counts are ever expected to exceed low tens of thousands, revisit with a persisted `order_index` column.
 
**Example request:**
```
GET /works/9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d/nodes/ordered?limit=2
Authorization: Bearer <jwt with tree:reader>
```
 
**Example response (200):**
```json
{
  "work_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "nodes": [
    {
      "node_id": "1c8e5f3a-2d4b-4e6f-8a9c-0b1d2e3f4a5b",
      "work_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "author": "Jane Doe",
      "node_type": "part",
      "parent_id": null,
      "position": 0,
      "tag": "Part One",
      "description": "The arrival.",
      "text": null,
      "previous": null,
      "next": null,
      "tags": [],
      "created_at": "2026-04-01T09:00:00Z",
      "updated_at": "2026-04-01T09:00:00Z"
    },
    {
      "node_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "work_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "author": "Jane Doe",
      "node_type": "chapter",
      "parent_id": "1c8e5f3a-2d4b-4e6f-8a9c-0b1d2e3f4a5b",
      "position": 0,
      "tag": "Chapter 1",
      "description": "Aila reaches the lighthouse.",
      "text": null,
      "previous": null,
      "next": null,
      "tags": ["setting:lighthouse"],
      "created_at": "2026-04-01T09:05:00Z",
      "updated_at": "2026-04-01T09:05:00Z"
    }
  ],
  "count": 2,
  "next_cursor": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```
 
#### Acceptance Criteria
 
1. GIVEN a valid JWT with `tree:reader` scope and a Work whose hierarchy is Part(0) → Chapter(0), Chapter(1), with Chapter(0) → Scene(0), Scene(1) WHEN `GET /works/{work_id}/nodes/ordered` is called THEN the server returns HTTP 200 with `OrderedNodesResponse` whose `nodes` are ordered `[Part0, Chapter0, Scene0, Scene1, Chapter1]` (pre-order, siblings by `position`). No item contains `account_id`.
2. GIVEN a Work with no nodes WHEN the endpoint is called THEN the server returns HTTP 200 with `{"work_id": "...", "nodes": [], "count": 0, "next_cursor": null}`.
3. GIVEN a Work with more than `limit` nodes WHEN `?limit=2` is called THEN `nodes` contains exactly 2 items and `next_cursor` equals the `node_id` of the 2nd item.
4. GIVEN the `next_cursor` from the previous page WHEN `?cursor=<next_cursor>&limit=2` is called THEN `nodes` contains the next 2 nodes in reading order, contiguous with the previous page and with no overlap or gap.
5. GIVEN the final page WHEN it is returned THEN `next_cursor` is `null`.
6. GIVEN a `cursor` value that is a valid UUID4 but is not the `node_id` of any node in this Work WHEN the endpoint is called THEN the server returns HTTP 422 with `detail: "Invalid cursor"`.
7. GIVEN `work_id` is not UUID4 format, or `cursor` is not UUID4 format, or `limit` is outside 1–200 WHEN the endpoint is called THEN the server returns HTTP 422.
8. GIVEN `work_id` does not exist or belongs to a different account WHEN the endpoint is called THEN the server returns HTTP 404 with `detail: "Work not found"` (the Work ownership check runs first).
9. GIVEN a node carries non-empty `previous` / `next` hint strings WHEN the endpoint is called THEN those values appear verbatim in that node's `NodeResponse`, AND the ordering of `nodes` is unchanged by them (ordering derives solely from hierarchy + `position`).
10. GIVEN User A owns a Work and User B is authenticated WHEN User B calls the endpoint for A's `work_id` THEN the server returns HTTP 404.
11. GIVEN no Authorization header THEN HTTP 401. GIVEN a JWT without `tree:reader` scope THEN HTTP 403 with `detail: "Insufficient permissions to complete action"`.
12. GIVEN the database raises `ConnectionFailure` or `OperationFailure` WHEN the endpoint is called THEN HTTP 503 with `detail: "Database error"`; the raw exception is logged with `exc_info=True` only and MUST NOT appear in the response.
**Definition of Done:**
- `GET /works/{work_id}/nodes/ordered` returns 200 with `OrderedNodesResponse` and `response_model` declared on the decorator (CONSTITUTION III.2).
- `summary`, `description`, `tags=["Search"]` present on the decorator.
- Work ownership check performed before traversal; cross-account or missing Work returns 404.
- Output is pre-order, siblings by `position`; parent always precedes its descendants.
- `limit` enforced (default 50, max 200); `cursor` pagination behaves per AC 3–6.
- `account_id` absent from every item in `nodes`.
- `previous` / `next` returned as metadata but never used for ordering.
---
 
## Non-Functional Requirements
 
### Requirement 2: Authentication and Scope Enforcement
 
**Maps to:** `Security(get_current_active_user_account, scopes=["tree:reader"])` on the handler. (CONSTITUTION II.2, II.4)
 
#### Acceptance Criteria
1. GIVEN no `Authorization` header WHEN the endpoint is called THEN HTTP 401 with `detail: "Could not validate credentials"`.
2. GIVEN a valid JWT missing `tree:reader` scope WHEN the endpoint is called THEN HTTP 403 with `detail: "Insufficient permissions to complete action"`.
3. GIVEN a blacklisted token (after `GET /logout`) WHEN the endpoint is called THEN HTTP 401.
### Requirement 3: Account Isolation (404 not 403)
 
**Maps to:** The Work ownership check and the `{account_id}` filter on the node query. (CONSTITUTION I.4)
 
#### Acceptance Criteria
1. GIVEN User A owns Work W and User B is authenticated WHEN User B calls `GET /works/{W.work_id}/nodes/ordered` THEN HTTP 404 (the Work ownership check fails first).
2. GIVEN the node query for any Work WHEN executed THEN it includes `{"account_id": account_id}`; no node belonging to another account can appear in `nodes`.
### Requirement 4: Input Validation
 
**Maps to:** `Path(pattern=UUID_PATTERN)` and `Query(...)` constraints. (CONSTITUTION II.4)
 
#### Acceptance Criteria
1. `work_id` not a valid UUID4 → HTTP 422.
2. `cursor` present but not a valid UUID4 → HTTP 422.
3. `limit` outside 1–200 → HTTP 422.
4. `cursor` valid UUID4 but not a node in this Work → HTTP 422 with `detail: "Invalid cursor"`.
### Requirement 5: Error Message Format
 
**Maps to:** CONSTITUTION II.5, III.6
 
#### Acceptance Criteria
1. Any error body is exactly `{"detail": "<message>"}` — no stack trace, no `account_id`, no MongoDB internals.
2. A missing/cross-account Work → HTTP 404, `detail: "Work not found"`.
3. `ConnectionFailure`/`OperationFailure` → HTTP 503, `detail: "Database error"`, raw exception via `logger.error(..., exc_info=True)` only.
---
 
## Correctness Properties
 
### Property 1: Output Is a Valid Pre-Order Traversal
- **Description:** In `nodes`, every parent appears before all of its descendants, and a node's children appear in `position` ascending order. (CONSTITUTION I.5, IV.5)
- **Testable:** For each item, assert its `parent_id` (if non-null) appears at an earlier index; assert children of any node appear in non-decreasing `position` order.
### Property 2: Complete and Non-Duplicating Coverage
- **Description:** Across all pages, every node of the Work appears exactly once. (CONSTITUTION I.6)
- **Testable:** Page through to exhaustion; assert the multiset of returned `node_id`s equals the set of all `node_id`s with `{account_id, work_id}`, with no repeats.
### Property 3: Endpoint Is Read-Only
- **Description:** The endpoint mutates no collection. (Tier 3 is query-only)
- **Testable:** Capture document counts and a content hash before and after a batch of calls; assert unchanged.
### Property 4: Ordering Is Independent of `previous` / `next`
- **Description:** The output sequence derives solely from the `parent_id` hierarchy and `position`. The free-text `previous` / `next` hints (`node-crud-feature.md:67–68`) never influence ordering and are returned only as metadata. (DESIGN §I.1; future typing of these fields is tracked as DESIGN OD-06.)
- **Testable:** Take a Work, record its reading order, then set arbitrary `previous` / `next` strings on its nodes and re-query; assert the order of `node_id`s is identical.
### Property 5: account_id Never Exposed
- **Description:** No item in `nodes` contains `account_id`. (CONSTITUTION I.4, II.5)
- **Testable:** Assert the `"account_id"` key is absent from every item in `nodes`.
### Property 6: Index Usage (No Collection Scans)
- **Description:** The node fetch uses the existing `{account_id, work_id}` index. (REQUIREMENTS Req 27)
- **Testable:** Run `explain()` on the fetch against ≥1000 seeded nodes; assert the `{account_id, work_id}` index is the winning plan and `COLLSCAN` is absent.
# Feature Specification: Demo Tree Seeding

**Implementation status:** NOT STARTED. Depends on Work CRUD and Node creation storage methods being complete (Tier 1). This document is authoritative for implementation, test authoring, and review.

## Introduction

This feature loads a small, representative demo Work and its node tree into `node_collection` for the authenticated account, so a new user (or a QA/demo session) can immediately explore navigation, search, and tag queries against realistic data. It is exposed as a single mutating endpoint, `POST /demo/seed`, rather than an offline script, because the tenant partition key `account_id` is a bcrypt hash of the username that is only resolvable from an authenticated request; a script cannot reproduce it without replicating auth internals. The endpoint delegates all writes to the existing `WorkStorage`/`NodeStorage` create methods, so seeded data passes the same schema validators and adjacency invariants as user-created data. The demo content itself is produced by a pure builder, `build_demo_tree(account_id, author)`, which a future CLI can reuse without duplicating the tree definition. (CONSTITUTION I.4, I.7)

## Glossary

| Term | Definition |
|------|-----------|
| **demo Work** | A single Work created by the seed endpoint, carrying the reserved tag `demo` so it can be identified and optionally reset. |
| **build_demo_tree** | Pure function `build_demo_tree(account_id, author) -> tuple[WorkCreate, list[NodeCreate]]`. Holds the canonical demo content; performs no I/O. The single source of truth for what the demo contains. |
| **adjacency fields** | `parent_id` + `position` define hierarchy; `previous`/`next` form the sibling linked list. The builder MUST populate all four so the tree is navigable on creation. (CONSTITUTION I.6) |
| **account_id** | bcrypt hash of the username. Universal tenant partition key. Never returned. Resolved from the JWT via `get_current_active_user_account`. (CONSTITUTION I.4) |
| **author** | Free-text attribution. Denormalised onto every demo Node from the demo Work at creation. (CONSTITUTION I.7) |
| **node_type** | Enum `"part" \| "chapter" \| "scene" \| "beat"`. The demo uses all four levels. (REQUIREMENTS:56) |
| **DemoSeedResponse** | `{"work_id": str, "title": str, "total_nodes": int, "by_type": dict}`. Reuses the shape of `WorkStatsResponse` plus `title`. No `account_id`. |
| **reset** | Optional boolean query param. When `true`, the endpoint deletes the account's existing `demo`-tagged Works (and their nodes) before seeding. Default `false` (additive). |

## Functional Requirements

### Requirement 1: Seed a Demo Tree

**User Story:** As an authenticated user, I want to load a ready-made demo Work and node tree into my account, so that I can explore the application's navigation, search, and tag features without building content by hand.

**Maps to:** `build_demo_tree` (new module, e.g. `server/app/demo.py`), `DemoStorage.seed_demo(account_id, author, reset)` reusing existing `create_work`/`create_node` (database.py), and `POST /demo/seed` handler (api.py).

**Endpoint:** `POST /demo/seed` — query param `reset` (optional bool, default `false`) — scope: `tree:writer` — returns `201 DemoSeedResponse`

**What `seed_demo` does:**
**What `seed_demo` does (explicit, transactional):**

The entire seed MUST be atomic — either the demo Work and all its nodes are committed together, or nothing is. Implement this with a MongoDB multi-document transaction (Atlas M0 is a 3-node replica set and supports transactions). The exact procedure:

1. Generate the demo `work_id` (UUID4) and call `build_demo_tree(account_id, author)` to obtain one `WorkCreate` and an ordered list of `NodeCreate` (no I/O yet).
2. Open a client session and start a transaction:
   ```python
   async with await client.start_session() as session:
       async with session.start_transaction():
           if reset:
               await delete_demo_works(account_id, session=session)   # nodes then works, demo-tagged, account-scoped
           await create_work(work, account_id, session=session)
           for node in nodes:
               await create_node(node, account_id, session=session)
       # leaving the context with no exception commits; any exception aborts and rolls back
   ```
3. **Required signature change:** `create_work`, `create_node`, and the demo-delete helper MUST accept an optional `session=None` keyword and thread it into their underlying `motor` calls (e.g. `collection.insert_one(doc, session=session)`). This is the only modification to the existing Tier 1 storage methods; it is backward-compatible (default `None` = current behaviour). Every write inside the seed MUST be passed the session — a single un-threaded write silently breaks atomicity.
4. On commit, return `DemoSeedResponse` summarising the created Work.

**Mandated fallback (if transactions are unavailable on the deployment):** if `session.start_transaction()` or `commit_transaction()` raises a server error indicating transactions are not supported, the implementation MUST instead use ordered creation with compensating cleanup: insert all nodes first, insert the Work document **last** (the Work is the only thing that makes the tree discoverable via `GET /works`), and wrap the whole sequence in `try/except` that, on any failure, calls `delete_many({account_id, work_id})` on `node_collection` and `delete_one({account_id, work_id})` on `work_collection` before returning 503. Do not implement both paths speculatively — use the transaction; fall back only on an explicit transaction-unsupported error.

**Example request:**
```
POST /demo/seed?reset=false
Authorization: Bearer <jwt with tree:writer>
```

**Example response (201):**
```json
{
  "work_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "title": "Demo: The Lighthouse at the End of the World",
  "total_nodes": 11,
  "by_type": { "part": 1, "chapter": 2, "scene": 4, "beat": 4 }
}
```

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:writer` scope WHEN `POST /demo/seed` is called THEN the server returns HTTP 201 with `DemoSeedResponse` whose `work_id` is a UUID4, `total_nodes` matches the number of nodes created, and `by_type` sums to `total_nodes`. No field contains `account_id`.
2. GIVEN the seed succeeds WHEN the created Work is fetched via `GET /works/{work_id}` THEN it exists, carries the `demo` tag, and its `author` is denormalised onto every seeded node.
3. GIVEN the seed succeeds WHEN the tree is traversed THEN every non-root node has a `parent_id` pointing to an existing seeded node, sibling sets are contiguously ordered by `position` from 0, and `previous`/`next` form a valid linked list within each sibling set (first `previous` is null, last `next` is null).
4. GIVEN the demo Work contains tagged nodes WHEN `GET /nodes/by-tag` and `GET /nodes/search` are called THEN they return seeded nodes (the demo populates `tags` and searchable `text`/`description` so Tier 3 features have data).
5. GIVEN `POST /demo/seed` is called twice with `reset=false` WHEN the second call completes THEN a second, independent demo Work exists; the first is unchanged (additive; never clobbers existing data).
6. GIVEN the account already has demo Works WHEN `POST /demo/seed?reset=true` is called THEN prior `demo`-tagged Works and their nodes are removed first and exactly one new demo Work remains.
7. GIVEN User A seeds a demo WHEN User B is authenticated THEN User B cannot see or reset User A's demo Work (account isolation).
8. GIVEN no Authorization header WHEN the endpoint is called THEN HTTP 401. GIVEN a JWT with only `tree:reader` scope THEN HTTP 403 with `detail: "Insufficient permissions to complete action"`.
9. GIVEN node creation fails partway through the transaction WHEN the error occurs THEN the transaction aborts, the response is HTTP 503 with `detail: "Database error"`, and neither the demo Work nor any of its nodes exist afterwards (verified via `GET /works` and a direct `node_collection` query on the `work_id`).
10. GIVEN the database raises `ConnectionFailure`/`OperationFailure` WHEN the endpoint is called THEN HTTP 503 with `detail: "Database error"`; the raw exception is logged with `exc_info=True` only.

**Definition of Done:**
- `POST /demo/seed` returns 201 with `DemoSeedResponse` and `response_model` declared on the decorator.
- `summary`, `description`, `tags=["Demo"]` present on the decorator.
- Writes go through `create_work`/`create_node` (no direct collection writes that bypass validators).
- `build_demo_tree` is pure (no I/O) and is the only definition of the demo content.
- `reset=true` removes only the calling account's `demo`-tagged Works.
- The seed runs in a single multi-document transaction; `create_work`/`create_node`/the demo-delete helper accept and thread an optional `session` kwarg, and every write in the seed receives the session.
- The compensating-cleanup fallback is implemented and triggers only on an explicit transaction-unsupported error.
- `account_id` absent from every response field.

## Non-Functional Requirements

### Requirement 2: Authentication and Scope Enforcement

**Maps to:** `Security(get_current_active_user_account, scopes=["tree:writer"])` on the handler. (CONSTITUTION II.2, II.4)

#### Acceptance Criteria
1. GIVEN no `Authorization` header WHEN the endpoint is called THEN HTTP 401 with `detail: "Could not validate credentials"`.
2. GIVEN a valid JWT missing `tree:writer` scope WHEN the endpoint is called THEN HTTP 403 with `detail: "Insufficient permissions to complete action"`.
3. GIVEN a blacklisted token (after `GET /logout`) WHEN the endpoint is called THEN HTTP 401.

### Requirement 3: Account Isolation

**Maps to:** Every `DemoStorage` query includes `{"account_id": account_id}`. (CONSTITUTION I.4)

#### Acceptance Criteria
1. GIVEN User A has a demo Work WHEN User B calls `POST /demo/seed?reset=true` THEN only User B's `demo`-tagged Works are affected; User A's remain.
2. GIVEN the seed completes WHEN any response body is inspected THEN it contains no `account_id`.

### Requirement 4: Input Validation

**Maps to:** `Query(...)` constraint on `reset`. (CONSTITUTION II.4)

#### Acceptance Criteria
1. GIVEN `?reset=notabool` WHEN the endpoint is called THEN HTTP 422.
2. GIVEN any request body is supplied WHEN the endpoint is called THEN it is ignored (the endpoint takes no body); malformed bodies do not cause a 500.

### Requirement 5: Error Message Format

**Maps to:** CONSTITUTION II.5, III.6

#### Acceptance Criteria
1. Any error body is exactly `{"detail": "<message>"}` — no stack trace, no `account_id`, no MongoDB internals.
2. `ConnectionFailure`/`OperationFailure` → HTTP 503, `detail: "Database error"`, raw exception via `logger.error(..., exc_info=True)` only.

## Correctness Properties

### Property 1: Seeded Data Is Indistinguishable From User Data
- **Description:** Demo Work and nodes are written through the same `create_work`/`create_node` paths as user content, so they satisfy every schema validator, denormalisation rule, and adjacency invariant. The only marker is the `demo` tag. (CONSTITUTION I.6, I.7)
- **Testable:** Seed a demo, then assert each node passes the same validation a user-created node would, and that `GET /works/{id}/nodes` returns a well-formed tree.

### Property 2: Adjacency Integrity
- **Description:** Hierarchy (`parent_id`/`position`) and sibling ordering (`previous`/`next`) are internally consistent across the whole seeded tree.
- **Testable:** Traverse from the root; assert positions are contiguous from 0 within each sibling set, `previous`/`next` chains are unbroken with null endpoints, and no `parent_id` references a missing node.

### Property 3: Strict Account Scoping
- **Description:** Seeding and reset only ever touch the calling account's data. (CONSTITUTION I.4)
- **Testable:** With two accounts each holding a demo Work, call reset+seed as one account; assert the other account's demo Work is untouched.

### Property 4: Seed Is Atomic (All-Or-Nothing)
- **Description:** The seed runs inside a multi-document transaction: the demo Work and every node commit together or not at all. A failure at any point leaves the account exactly as it was before the call — no demo Work, no orphan nodes. If transactions are unavailable, the mandated compensating-cleanup fallback (create Work last, delete-by-`work_id` on failure) provides the same guarantee. (See Requirement 1, "What `seed_demo` does".)
- **Testable:** Inject a failure on the Nth `create_node`. Assert that afterwards `GET /works` shows no new demo Work AND a direct query of `node_collection` for that `work_id` returns zero documents, and the endpoint returned 503.

### Property 5: Single Source Of Demo Content
- **Description:** `build_demo_tree` is the only place the demo tree is defined; the endpoint and any future CLI both call it. (DRY; prevents divergence between entry points)
- **Testable:** Assert the endpoint path constructs no node content of its own beyond what `build_demo_tree` returns.

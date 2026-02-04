# Dependency Update Tasks

Generated: 2026-02-04

## Summary

The `server/requirements.txt` is already updated to modern versions (2024/2025), and the codebase has been migrated to **Pydantic v2** (using `ConfigDict` and `model_config` patterns).

## Tasks

### 1. Remove or consolidate root requirements.txt
**Priority:** High
**Status:** [x] Complete

The root `/requirements.txt` has outdated 2021 pinned versions:
- fastapi==0.65.1
- pydantic==1.8.2
- motor==2.4.0
- pymongo==3.11.4
- etc.

The `/server/requirements.txt` has modern 2024+ versions and is the active file. Either delete the root file or consolidate to avoid confusion.

---

### 2. Replace deprecated datetime.utcnow()
**Priority:** Medium
**Status:** [x] Complete

**File:** `server/app/models.py:218`

`datetime.utcnow()` is deprecated in Python 3.12+. Replace with:
```python
from datetime import datetime, timezone
datetime.now(timezone.utc)
```

---

### 3. Consider replacing pytz with zoneinfo
**Priority:** Low
**Status:** [x] Complete

**File:** `server/app/authentication.py`

Since Python 3.9+, the built-in `zoneinfo` module is preferred over `pytz`.

Change:
```python
from pytz import timezone
timezone("gmt")
```

To:
```python
from zoneinfo import ZoneInfo
ZoneInfo("GMT")
```

---

### 4. Verify Python version compatibility
**Priority:** Medium
**Status:** [x] Complete

**Findings:**
- System Python: 3.9.6 (compatible with all dependencies)
- FastAPI supports Python 3.9+ (3.8 dropped)
- Updated `List[str]` to `list[str]` in models.py (3.9+ feature)
- `Optional[X]` kept as-is (can use `X | None` if upgrading to 3.10+)

**Optional future upgrade:** Python 3.11+ offers ~25% performance improvement

---

### 5. Update test dependencies and run tests
**Priority:** High
**Status:** [~] Dependencies updated, tests pending

**Completed:**
- Removed duplicate `import asyncio` from test file
- Removed redundant `@pytest.mark.asyncio` decorators (pytest.ini has `asyncio_mode = auto`)
- pytest.ini already configured for modern pytest-asyncio 0.24+

**Pending:**
1. Recreate the virtual environment with updated `server/requirements.txt`
2. Run `pytest` to verify everything works (waiting for MongoDB Atlas)

---

## Files Reference

| File | Status |
|------|--------|
| `/requirements.txt` | Outdated - remove or consolidate |
| `/server/requirements.txt` | Current - already updated |
| `/server/app/models.py` | Needs datetime fix |
| `/server/app/authentication.py` | Optional pytz modernization |

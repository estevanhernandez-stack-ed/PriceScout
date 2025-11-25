# PriceScout Improvement Plan

**Based on:** Code Review (November 24, 2025)
**Current Score:** 85/100 (B+)
**Target Score:** 92/100 (A)

---

## Phase 1: Critical - Fix Failing Tests

**Priority:** HIGH
**Impact:** Test reliability, CI/CD pipeline

### 1.1 Scraper Test Fixes (20+ failures)

| Task | Files | Issue |
|------|-------|-------|
| Update `check_url_status` mocks | `test_scraper.py`, `test_scraper_critical.py` | Method signature changed |
| Fix `parse_ticket_description` tests | `test_scraper_critical.py` | Return value format changed |
| Update `process_movie_block` tests | `test_scraper_critical.py` | Interface changes |
| Fix async scraper tests | `test_scraper_async.py` | Mock setup issues |

**Action Items:**
```bash
# Run specific failing tests to diagnose
pytest tests/test_scraper*.py -v --tb=short

# Files to update:
# - tests/test_scraper.py
# - tests/test_scraper_async.py
# - tests/test_scraper_critical.py
# - tests/test_scraper_unit.py
# - tests/test_scraper_concurrent.py
```

### 1.2 Analysis Mode Test Fixes (12 failures)

| Task | Files | Issue |
|------|-------|-------|
| Fix `generate_operating_hours_report` mocks | `test_analysis_mode.py` | Database query changes |
| Update theater analysis tests | `test_analysis_mode.py` | UI component changes |
| Fix film analysis workflow | `test_analysis_mode.py` | SQLAlchemy interface |

**Action Items:**
```bash
pytest tests/test_analysis_mode.py -v --tb=short
pytest tests/test_modes_analysis.py -v --tb=short
```

### 1.3 Data Management Test Fixes (7 failures)

| Task | Files | Issue |
|------|-------|-------|
| Fix `strip_common_terms` test | `test_data_management.py` | Function moved/renamed |
| Update `process_market` mocks | `test_data_management.py` | Interface changes |
| Fix schema migration tests | `test_data_management.py` | Schema updates |

**Action Items:**
```bash
pytest tests/test_data_management.py -v --tb=short
```

### 1.4 Theming Test Fixes (3 failures)

| Task | Files | Issue |
|------|-------|-------|
| Fix session state initialization | `test_theming.py` | Streamlit mock changes |

---

## Phase 2: Code Quality Improvements

**Priority:** MEDIUM
**Impact:** Maintainability, developer experience

### 2.1 Fix SQLAlchemy Deprecation Warning

**File:** `app/db_models.py:28`

**Current:**
```python
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()
```

**Fix:**
```python
from sqlalchemy.orm import declarative_base
Base = declarative_base()
```

### 2.2 Add Type Hints to Core Modules

**Priority order for type hints:**

| Module | Complexity | Priority |
|--------|------------|----------|
| `security_config.py` | Low | 1 |
| `users.py` | Medium | 2 |
| `config.py` | Low | 3 |
| `cookie_manager.py` | Low | 4 |
| `database.py` | High | 5 |
| `scraper.py` | High | 6 |

**Example transformation:**
```python
# Before
def validate_password_strength(password):
    ...

# After
def validate_password_strength(password: str) -> tuple[bool, str]:
    ...
```

### 2.3 Refactor Large Files

#### 2.3.1 Split `database.py`

**Current:** Single 2000+ line file

**Proposed structure:**
```
app/db/
├── __init__.py          # Re-exports for backwards compatibility
├── connection.py        # Connection management
├── prices.py            # Price-related queries
├── films.py             # Film metadata queries
├── theaters.py          # Theater queries
├── operating_hours.py   # Operating hours queries
├── scrape_runs.py       # Scrape run management
└── migrations.py        # Schema migrations
```

#### 2.3.2 Split `scraper.py`

**Proposed structure:**
```
app/scraping/
├── __init__.py
├── base.py              # Base scraper class
├── fandango.py          # Fandango-specific logic
├── parsers.py           # HTML parsing utilities
├── ticket_types.py      # Ticket type classification
└── utils.py             # URL checking, helpers
```

---

## Phase 3: Testing Improvements

**Priority:** MEDIUM
**Impact:** Code confidence, regression prevention

### 3.1 Increase Test Coverage

**Current ratio:** 0.55:1 (test:app)
**Target ratio:** 0.70:1

| Module | Current Tests | Needed |
|--------|---------------|--------|
| `data_management_v2.py` | Partial | +15 tests |
| `theater_matching_tool.py` | Minimal | +10 tests |
| `ui_components.py` | None | +8 tests |
| `theming.py` | 3 (failing) | Fix + 5 |
| `state.py` | Minimal | +5 tests |

### 3.2 Add Integration Tests

**New test file:** `tests/test_integration_e2e.py`

| Test Scenario | Description |
|---------------|-------------|
| Full scrape workflow | Theater selection → Scrape → Save |
| User lifecycle | Create → Login → Change password → Delete |
| Report generation | Select data → Generate → Export |
| Mode switching | Navigate between all modes |

### 3.3 Add Pre-commit Hooks

**Create:** `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json

  - repo: https://github.com/psf/black
    rev: 24.3.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=120']
```

---

## Phase 4: Documentation Improvements

**Priority:** LOW
**Impact:** Developer onboarding, maintenance

### 4.1 Standardize Docstrings

**Adopt Google style docstrings:**

```python
def create_user(username: str, password: str, role: str = "user") -> tuple[bool, str]:
    """Create a new user with password validation.

    Args:
        username: Username for the new user (will be lowercased).
        password: Plain text password (will be hashed with bcrypt).
        role: User role - 'admin', 'manager', or 'user'.

    Returns:
        A tuple of (success, message) where success is True if user
        was created, and message contains success/error details.

    Raises:
        ValueError: If role is not a valid role type.

    Example:
        >>> success, msg = create_user("john", "SecurePass123!", "user")
        >>> print(msg)
        "User created successfully."
    """
```

### 4.2 Add Architecture Documentation

**Create:** `docs/ARCHITECTURE.md`

Contents:
- System overview diagram
- Module dependency graph
- Data flow diagrams
- Database schema ERD

---

## Implementation Schedule

### Week 1: Test Fixes (Phase 1)

| Day | Task | Hours |
|-----|------|-------|
| 1 | Fix scraper tests (1.1) | 4 |
| 2 | Fix scraper tests continued | 4 |
| 3 | Fix analysis mode tests (1.2) | 3 |
| 4 | Fix data management tests (1.3) | 2 |
| 4 | Fix theming tests (1.4) | 1 |
| 5 | Verify all tests pass | 2 |

**Deliverable:** 100% test pass rate

### Week 2: Quick Wins (Phase 2.1-2.2)

| Day | Task | Hours |
|-----|------|-------|
| 1 | Fix SQLAlchemy deprecation | 0.5 |
| 1-3 | Add type hints to priority modules | 6 |
| 4-5 | Test type hints with mypy | 2 |

**Deliverable:** Type hints on 6 core modules

### Week 3-4: Refactoring (Phase 2.3)

| Day | Task | Hours |
|-----|------|-------|
| 1-3 | Plan and create db/ module structure | 4 |
| 4-7 | Migrate database.py functions | 8 |
| 8-10 | Update imports across codebase | 4 |
| 11-12 | Verify tests still pass | 2 |

**Deliverable:** Refactored database module

### Week 5: Testing Improvements (Phase 3)

| Day | Task | Hours |
|-----|------|-------|
| 1-2 | Add missing unit tests | 6 |
| 3 | Add integration tests | 4 |
| 4 | Setup pre-commit hooks | 2 |
| 5 | Document testing strategy | 2 |

**Deliverable:** 0.70:1 test ratio, pre-commit hooks

---

## Success Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Test Pass Rate | 89% | 100% | Pending |
| Test:Code Ratio | 0.55:1 | 0.70:1 | Pending |
| Type Hint Coverage | ~30% | 80% | Pending |
| Overall Score | 85/100 | 92/100 | Pending |
| Deprecation Warnings | 1 | 0 | Pending |

---

## Quick Reference Commands

```bash
# Run all tests
pytest tests/ -v

# Run specific test category
pytest tests/test_scraper*.py -v --tb=short

# Check type hints
pip install mypy
mypy app/ --ignore-missing-imports

# Run linting
pip install flake8
flake8 app/ --max-line-length=120

# Format code
pip install black isort
black app/
isort app/

# Security audit
pip install bandit pip-audit
bandit -r app/
pip-audit
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Refactoring breaks imports | High | Maintain backwards-compatible re-exports |
| Test fixes introduce regressions | Medium | Run full test suite after each fix |
| Type hints cause runtime errors | Low | Use `from __future__ import annotations` |

---

**Document Created:** November 24, 2025
**Next Review:** After Phase 1 completion

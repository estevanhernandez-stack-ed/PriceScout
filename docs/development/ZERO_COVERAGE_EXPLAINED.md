# Zero-Coverage Files Explanation

**Generated:** October 25, 2025  
**Status:** Documentation for deployment review

---

## 📊 Files Showing 0% Coverage

The following files show 0% test coverage in the coverage report. Here's why and what to do about them:

### 1. **`test_bom_scraper.py`** (Root)

**Type:** Manual test script  
**Lines:** ~25  
**Status:** ✅ Not a problem

**What it is:**
- Manual testing script for Box Office Mojo scraper
- Runs async scraping tests with real API calls
- Not part of automated test suite

**Why 0% coverage:**
- Not imported by any production code
- Not executed during pytest runs
- Intended for manual testing only

**Action:**
```powershell
# Moved by cleanup.ps1 to tests/manual_tests/
.\cleanup.ps1
```

---

### 2. **`fix_test_users.py`** (Root)

**Type:** Temporary utility script  
**Lines:** 61  
**Status:** ⚠️ Should be deleted

**What it is:**
- One-time script we created to fix test_users.py
- Removed `with patch` blocks from test file
- Made test usernames unique

**Why 0% coverage:**
- Not part of production code
- Not imported anywhere
- Was a temporary fix tool

**Action:**
```powershell
# Deleted by cleanup.ps1
.\cleanup.ps1
# Or delete manually:
Remove-Item fix_test_users.py
```

---

### 3. **`fix_json.py`** (Root)

**Type:** Utility script  
**Lines:** 166  
**Status:** ✅ Should be moved

**What it is:**
- Theme generation utility
- Creates `themes_final.json` from Python dict
- Used during development to create theme files

**Why 0% coverage:**
- Not imported by production code
- Standalone utility for theme creation
- Run manually when updating themes

**Action:**
```powershell
# Moved by cleanup.ps1 to scripts/
.\cleanup.ps1
```

**Usage:**
```powershell
# If you need to regenerate themes:
python scripts/fix_json.py
```

---

### 4. **`create_themes_file.py`** (Root)

**Type:** Utility script  
**Lines:** 156  
**Status:** ✅ Should be moved

**What it is:**
- Theme generation utility (similar to fix_json.py)
- Creates `themes_minimal.json`
- Development tool for theme management

**Why 0% coverage:**
- Not imported by production code
- Standalone utility
- Manual execution only

**Action:**
```powershell
# Moved by cleanup.ps1 to scripts/
.\cleanup.ps1
```

---

### 5. **`app/theater_matching_tool.py`** (App Folder)

**Type:** Production feature module  
**Lines:** 899  
**Status:** ⚠️ **NEEDS TESTING**

**What it is:**
- **Actual feature mode** in the Price Scout app
- Interactive tool for matching theaters across databases
- Uses fuzzy matching with `thefuzz` library
- Heavy Streamlit UI components

**Why 0% coverage:**
- Only loaded when "Theater Matching" mode is selected (lazy import)
- Current tests don't exercise UI mode selection
- UI-heavy code is harder to test with unit tests
- Would require dedicated UI/integration tests

**How it's used:**
```python
# app/price_scout_app.py:280
elif mode == "Theater Matching":
    from app.theater_matching_tool import main as theater_matching_main
    theater_matching_main()
```

**Testing challenges:**
- Heavy Streamlit UI interaction (file uploads, dataframes, buttons)
- Async operations
- Complex user workflows
- Session state dependencies

**Recommended approach:**
1. **Integration tests** - Test the matching algorithm separately
2. **Manual testing** - Use the UI to verify functionality
3. **Future:** Add Streamlit UI tests when feasible

**Example test stub:**
```python
# tests/test_theater_matching_tool.py (future)
def test_strip_common_terms():
    """Test theater name normalization."""
    from app.theater_matching_tool import _strip_common_terms
    
    assert _strip_common_terms("AMC Dine-In Theater") == " "
    assert _strip_common_terms("Marcus Cinema") == " "

def test_fuzzy_match_theaters():
    """Test fuzzy matching logic."""
    from app.theater_matching_tool import fuzzy_match_theaters
    # ... test matching algorithm
```

**Action for deployment:**
- ✅ Keep in app/ (it's a feature, not a utility)
- ⚠️ Document in user manual
- ⚠️ Add to manual testing checklist
- 🔜 Plan integration tests post-deployment

---

## 📋 Summary Table

| File | Type | Lines | Coverage | Action | Priority |
|------|------|-------|----------|--------|----------|
| `test_bom_scraper.py` | Manual test | 25 | 0% | Move to `tests/manual_tests/` | Low |
| `fix_test_users.py` | Temp utility | 61 | 0% | Delete | High |
| `fix_json.py` | Theme utility | 166 | 0% | Move to `scripts/` | Medium |
| `create_themes_file.py` | Theme utility | 156 | 0% | Move to `scripts/` | Medium |
| `app/theater_matching_tool.py` | **Feature** | **899** | **0%** | **Add tests** | **High** |

---

## ✅ Quick Fix Commands

### Run Cleanup Script (Recommended)
```powershell
# Moves utilities and deletes temp files
.\cleanup.ps1
```

### Manual Cleanup
```powershell
# Create directories
New-Item -ItemType Directory -Force -Path "scripts"
New-Item -ItemType Directory -Force -Path "tests\manual_tests"

# Move files
Move-Item test_bom_scraper.py tests\manual_tests\
Move-Item fix_json.py scripts\
Move-Item create_themes_file.py scripts\

# Delete temp file
Remove-Item fix_test_users.py
```

---

## 🎯 Impact on Coverage

**Before cleanup:**
- Total files showing 0%: 5
- Production code at 0%: 1 (`theater_matching_tool.py`)
- Utility/test files: 4

**After cleanup:**
- Utilities moved out of coverage scope
- Only real issue: `theater_matching_tool.py` needs tests
- Coverage metric becomes more accurate

**Coverage improvement:**
```
Current overall: 40%
After removing utilities from coverage: ~40% (same, but cleaner)
After testing theater_matching_tool: Could reach 45-50%
```

---

## 📝 Recommendations

### Immediate (Before Deployment)
1. ✅ Run `cleanup.ps1` to organize files
2. ✅ Manually test Theater Matching mode
3. ✅ Document Theater Matching in user guide

### Short Term (Post-Deployment)
4. 🔜 Add unit tests for `theater_matching_tool.py` helper functions
5. 🔜 Add integration tests for matching algorithm
6. 🔜 Consider extracting business logic from UI code

### Long Term
7. 🔮 Investigate Streamlit UI testing frameworks
8. 🔮 Refactor UI-heavy code for better testability
9. 🔮 Aim for 50%+ overall coverage

---

## 🎬 Conclusion

**4 of the 5 files at 0% are utilities/scripts** - not actual production code concerns.

**1 file (`theater_matching_tool.py`) is a legitimate feature** that needs testing but is challenging due to UI-heavy architecture.

**Action:** Run cleanup script and add Theater Matching to manual testing checklist.

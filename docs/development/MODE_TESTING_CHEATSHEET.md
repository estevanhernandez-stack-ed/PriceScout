# 🚀 Streamlit Mode Testing - Quick Reference

**Copy-paste this to test any Streamlit mode in < 1 hour!**

---

## Step 1: Copy the Fixture Template

```python
import pytest
from unittest.mock import patch, MagicMock, Mock
import pandas as pd
import datetime
from tests.ui_test_helpers import MockSessionState

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock all dependencies for YOUR_MODE tests."""
    with patch('app.config.DB_FILE', '/fake/db.sqlite'), \
         patch('app.modes.YOUR_MODE.database.FUNCTION_1', return_value=pd.DataFrame()), \
         patch('app.modes.YOUR_MODE.database.FUNCTION_2', return_value=[]), \
         patch('app.modes.YOUR_MODE.st') as mock_st:  # ← CRITICAL: Patch at module level!
        
        # Create session state
        session = MockSessionState()
        
        # TODO: Initialize session state keys (see Step 2)
        session.key1 = None
        session.key2 = []
        session.key3 = {}
        
        mock_st.session_state = session
        
        # Setup sensible defaults
        mock_st.button.return_value = False
        mock_st.form_submit_button.return_value = False
        
        # Dynamic columns mock (REQUIRED!)
        def columns_side_effect(spec):
            if isinstance(spec, int):
                return [MagicMock() for _ in range(spec)]
            elif isinstance(spec, list):
                return [MagicMock() for _ in range(len(spec))]
            return [MagicMock(), MagicMock()]
        
        mock_st.columns.side_effect = columns_side_effect
        
        # Other common mocks
        mock_st.tabs.return_value = [MagicMock(), MagicMock()]
        mock_st.multiselect.return_value = []
        mock_st.date_input.return_value = (
            datetime.date.today() - datetime.timedelta(days=7),
            datetime.date.today()
        )
        
        # Spinner context manager
        spinner_mock = MagicMock()
        spinner_mock.__enter__ = Mock(return_value=MagicMock())
        spinner_mock.__exit__ = Mock(return_value=False)
        mock_st.spinner.return_value = spinner_mock
        
        mock_st.rerun = MagicMock()
        
        yield mock_st
```

---

## Step 2: Find Required Session State Keys

**Method 1 - Search the code:**
```bash
# In PowerShell:
Select-String "st.session_state\[|st.session_state\." app/modes/YOUR_MODE.py
```

**Method 2 - Run test and let it fail:**
```bash
pytest tests/test_modes_YOUR_MODE.py -v
# Look for: AttributeError: 'MockSessionState' object has no attribute 'X'
# Add: session.X = default_value
# Repeat until all pass
```

**Example Session State Init:**
```python
session.data_type = None
session.selected_item = None
session.filters = []
session.date_range = ()
session.results_df = pd.DataFrame()
session.is_loading = False
# ... add all keys your mode uses
```

---

## Step 3: Write 3 Essential Tests

### Test 1: Smoke Test (Does it render?)
```python
def test_renders_without_error(mock_dependencies):
    """Basic smoke test - mode renders without crashing."""
    from app.modes.YOUR_MODE import render_YOUR_MODE
    
    # Should not raise any exceptions
    render_YOUR_MODE()
```

### Test 2: UI Elements (Are key components shown?)
```python
def test_renders_ui_elements(mock_dependencies):
    """Verify key UI elements are rendered."""
    from app.modes.YOUR_MODE import render_YOUR_MODE
    
    render_YOUR_MODE()
    
    mock_dependencies.header.assert_called()
    mock_dependencies.button.assert_called()
    # Add more assertions for key UI elements
```

### Test 3: Error Handling (Does it handle bad data?)
```python
def test_handles_empty_data(mock_dependencies):
    """Test handling of empty/missing data."""
    from app.modes.YOUR_MODE import render_YOUR_MODE
    
    with patch('app.modes.YOUR_MODE.database.get_data', return_value=pd.DataFrame()):
        render_YOUR_MODE()
        
        # Should show warning/error
        mock_dependencies.warning.assert_called()
```

---

## Step 4: Add Value Tests (Optional but Recommended)

### Test Database Interaction
```python
def test_queries_database_on_button_click(mock_dependencies):
    """Test that button click triggers database query."""
    with patch('app.modes.YOUR_MODE.database.get_data') as mock_query:
        mock_dependencies.button.return_value = True
        
        render_YOUR_MODE()
        
        mock_query.assert_called_once()
```

### Test State Changes
```python
def test_updates_session_state(mock_dependencies):
    """Test that user action updates session state."""
    session = mock_dependencies.session_state
    
    # Simulate user interaction
    session.selected_option = 'Option A'
    
    render_YOUR_MODE()
    
    # Verify state was updated
    assert session.results is not None
```

---

## 🎯 Quick Checklist

- [ ] Created `tests/test_modes_YOUR_MODE.py`
- [ ] Copied fixture template
- [ ] Patched `app.modes.YOUR_MODE.st` (NOT global `st`)
- [ ] Found all session state keys (search or trial-and-error)
- [ ] Initialized all session state keys in fixture
- [ ] Added dynamic columns mock
- [ ] Patched database functions
- [ ] Wrote 3 essential tests (smoke, UI, error)
- [ ] Added 2-5 value tests (database, state, workflow)
- [ ] All tests passing ✅
- [ ] Coverage 30-40% ✅

---

## 🚫 Common Mistakes

| ❌ DON'T | ✅ DO |
|---------|------|
| `with mock_streamlit() as st:` | `with patch('app.modes.X.st') as mock_st:` |
| Try to control button clicks | Set session state beforehand |
| Initialize 2-3 session keys | Initialize ALL session keys |
| Aim for 100% coverage | Aim for 30-40% (realistic) |
| Test every UI detail | Test error paths & logic |
| `mock_st.columns = MagicMock()` | `mock_st.columns.side_effect = ...` |

---

## 📊 Expected Results

**Good Coverage:** 30-40% isolated, 50-60% in full suite  
**Test Count:** 10-15 focused tests  
**Time Investment:** 1-2 hours  
**Maintenance:** Low (stable patterns)

---

## 🆘 Troubleshooting

**Problem:** `AttributeError: 'MockSessionState' object has no attribute 'X'`  
**Fix:** Add `session.X = default_value` to fixture

**Problem:** `ValueError: not enough values to unpack`  
**Fix:** Check `columns.side_effect` is set up correctly

**Problem:** Tests pass individually but fail together  
**Fix:** Use `autouse=True` on fixture

**Problem:** Database errors  
**Fix:** Patch `DB_FILE` and all database functions

**Problem:** Coverage seems low  
**Fix:** That's normal! 30-40% is great for UI-heavy modes

---

## 💡 Pro Tips

1. **Start with the smoke test** - Get basic rendering working first
2. **Run after each change** - `pytest tests/test_modes_X.py -v`
3. **Check coverage** - `pytest tests/test_modes_X.py --cov=app.modes.X`
4. **Copy from analysis_mode** - `tests/test_modes_analysis.py` is your template
5. **Don't overthink it** - Simple tests are fine!

---

**🎉 You're ready! Copy this template and start testing!**

For more details, see `UI_TESTING_GUIDE.md` and `TESTING_PROGRESS.md`

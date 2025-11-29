# UI Testing Quick Reference Guide

This guide shows you how to quickly add tests to any Streamlit mode using our reusable helpers.

## ⚡ **NEW: Testing Streamlit Modes - Best Practices**

After testing `analysis_mode.py`, we learned the optimal approach:

### ✅ **Critical Pattern: Patch at Module Level**

**DO THIS:**
```python
@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('app.modes.analysis_mode.st') as mock_st:
        # Patch where the module imports 'st', not globally!
        session = MockSessionState()
        mock_st.session_state = session
        yield mock_st
```

**NOT THIS:**
```python
# ❌ Don't use mock_streamlit() context manager for modes
with mock_streamlit() as st_mock:  # This doesn't work for mode testing
    render_mode()
```

### � **Key Requirements for Mode Testing**

1. **Patch streamlit at the import point**: `patch('app.modes.your_mode.st')`
2. **Initialize session state extensively**: Modes expect many keys to exist
3. **Use dynamic column mocking**: `columns.side_effect = lambda spec: [MagicMock()] * (spec if isinstance(spec, int) else len(spec))`
4. **Simplify assertions**: Verify rendering succeeds rather than exact UI state

### 📝 **Complete Mode Testing Template**

```python
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from tests.ui_test_helpers import MockSessionState

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock all Streamlit and external dependencies."""
    with patch('app.config.DB_FILE', '/fake/db.sqlite'), \
         patch('app.modes.your_mode.database.get_data', return_value=pd.DataFrame()), \
         patch('app.modes.your_mode.st') as mock_st:
        
        # Create session state
        session = MockSessionState()
        
        # Initialize ALL session state keys your mode uses
        session['key1'] = 'value1'
        session['key2'] = []
        session['key3'] = None
        # ... add all keys the mode expects
        
        # Setup mocks
        mock_st.session_state = session
        mock_st.columns.side_effect = lambda spec: [MagicMock()] * (
            spec if isinstance(spec, int) else len(spec)
        )
        mock_st.button.return_value = False
        mock_st.form_submit_button.return_value = False
        
        yield mock_st

def test_renders_without_error(mock_dependencies):
    """Basic smoke test - mode renders without crashing."""
    from app.modes.your_mode import render_your_mode
    
    # Should not raise
    render_your_mode()
    
def test_renders_ui_elements(mock_dependencies):
    """Verify key UI elements are rendered."""
    from app.modes.your_mode import render_your_mode
    
    render_your_mode()
    
    mock_dependencies.header.assert_called()
    mock_dependencies.button.assert_called()
```

## �📚 Import the Helpers

```python
from tests.ui_test_helpers import (
    MockSessionState,  # NEW: Use this for mode testing
    mock_streamlit,    # For simple component tests
    create_session_state,
    assert_error_displayed,
    assert_success_displayed,
    simulate_button_click,
    simulate_text_input,
    simulate_selectbox
)
```

## 🎯 Common Test Patterns

### Pattern 1: Test Basic UI Rendering
```python
def test_mode_renders_title():
    """Test that the mode displays its title."""
    with mock_streamlit() as st_mock:
        my_mode_function()
        
        st_mock.title.assert_called_once()
        # OR check for specific title
        st_mock.title.assert_called_with("My Mode Title")
```

### Pattern 2: Test Error Messages
```python
def test_mode_shows_error_for_invalid_input():
    """Test that error is shown for invalid input."""
    with mock_streamlit() as st_mock:
        my_mode_function(invalid_data=True)
        
        assert_error_displayed(st_mock)
        # OR check for specific message
        assert_error_displayed(st_mock, "Invalid input")
```

### Pattern 3: Test Button Clicks
```python
def test_mode_processes_on_button_click():
    """Test that clicking button triggers processing."""
    with mock_streamlit() as st_mock:
        # Make button return True (clicked)
        simulate_button_click(st_mock)
        
        my_mode_function()
        
        assert_success_displayed(st_mock)
```

### Pattern 4: Test Session State
```python
def test_mode_stores_result_in_session():
    """Test that results are stored in session state."""
    session = create_session_state(logged_in=True, user_name='test')
    
    with mock_streamlit(session) as st_mock:
        my_mode_function()
        
        # Check that new key was added
        assert 'result' in session.set_keys
        assert session['result'] == expected_value
```

### Pattern 5: Test Form Input
```python
def test_mode_processes_form_input():
    """Test form input handling."""
    with mock_streamlit() as st_mock:
        # Simulate user input
        simulate_text_input(st_mock, "Test Theater")
        simulate_selectbox(st_mock, "2025-10-25")
        st_mock.form_submit_button.return_value = True
        
        my_mode_function()
        
        assert_success_displayed(st_mock)
```

### Pattern 6: Test Data Display
```python
def test_mode_displays_dataframe():
    """Test that dataframe is displayed."""
    with mock_streamlit() as st_mock:
        my_mode_function(data=sample_data)
        
        # Check dataframe was displayed
        st_mock.dataframe.assert_called_once()
        
        # Get the dataframe that was displayed
        args, kwargs = st_mock.dataframe.call_args
        df = args[0]
        assert len(df) > 0
```

### Pattern 7: Test Permission Checks
```python
def test_mode_requires_login():
    """Test that mode requires user to be logged in."""
    session = create_session_state(logged_in=False)
    
    with mock_streamlit(session) as st_mock:
        my_mode_function()
        
        assert_error_displayed(st_mock, "must be logged in")
        st_mock.stop.assert_called_once()
```

### Pattern 8: Test Database Integration
```python
def test_mode_loads_data_from_database(mock_database):
    """Test that mode loads data from database."""
    with mock_streamlit() as st_mock:
        with patch('app.database.get_connection', return_value=mock_database.connection):
            # Setup mock data
            mock_database.cursor.fetchall.return_value = [('Theater 1',), ('Theater 2',)]
            
            my_mode_function()
            
            # Verify database was queried
            assert mock_database.cursor.execute.called
```

### Pattern 9: Test Multiple Conditions
```python
def test_mode_handles_different_user_types():
    """Test behavior for admin vs regular user."""
    # Test admin
    admin_session = create_session_state(is_admin=True)
    with mock_streamlit(admin_session) as st_mock:
        my_mode_function()
        st_mock.button.assert_any_call("Admin Action")
    
    # Test regular user
    user_session = create_session_state(is_admin=False)
    with mock_streamlit(user_session) as st_mock:
        my_mode_function()
        # Admin button should not appear
        calls = [call[0][0] for call in st_mock.button.call_args_list]
        assert "Admin Action" not in calls
```

### Pattern 10: Test Download Functionality
```python
def test_mode_generates_excel_download():
    """Test that Excel download is offered."""
    with mock_streamlit() as st_mock:
        my_mode_function(data=sample_data)
        
        # Check download button was created
        st_mock.download_button.assert_called_once()
        
        # Verify it's for Excel
        args, kwargs = st_mock.download_button.call_args
        assert 'label' in kwargs
        assert 'xlsx' in kwargs.get('file_name', '') or 'Excel' in kwargs.get('label', '')
```

## 🔧 Helper Functions Reference

### Assertion Helpers
- `assert_error_displayed(st_mock, message=None)` - Check error was shown
- `assert_success_displayed(st_mock, message=None)` - Check success was shown
- `assert_warning_displayed(st_mock, message=None)` - Check warning was shown
- `assert_info_displayed(st_mock, message=None)` - Check info was shown
- `assert_no_errors(st_mock)` - Check NO errors were shown
- `assert_rerun_called(st_mock)` - Check st.rerun() was called
- `assert_dataframe_displayed(st_mock)` - Check dataframe was shown

### Simulation Helpers
- `simulate_button_click(st_mock)` - Make button return True
- `simulate_text_input(st_mock, "value")` - Set text input value
- `simulate_selectbox(st_mock, "option")` - Set selectbox selection
- `simulate_multiselect(st_mock, ["opt1", "opt2"])` - Set multiselect
- `simulate_checkbox(st_mock, True/False)` - Set checkbox state

### Session State
- `create_session_state(key=value, ...)` - Create session with initial values
- Access session like dict: `session['key']`
- Check what was set: `'key' in session.set_keys`
- Check what was deleted: `'key' in session.deleted_keys`

### Call Inspection
- `get_call_count(st_mock.function)` - How many times called
- `get_last_call_args(st_mock.function)` - Get args from last call

## 📋 Quick Test Template

Copy this template to get started quickly:

```python
import pytest
from unittest.mock import patch, MagicMock
from tests.ui_test_helpers import (
    mock_streamlit,
    create_session_state,
    assert_error_displayed,
    assert_success_displayed,
)
from app.modes.my_mode import my_mode_function


def test_basic_rendering():
    """Test that mode renders without errors."""
    with mock_streamlit() as st_mock:
        my_mode_function()
        
        # Add your assertions here
        st_mock.title.assert_called()


def test_error_handling():
    """Test error handling."""
    with mock_streamlit() as st_mock:
        my_mode_function(invalid_input=True)
        
        assert_error_displayed(st_mock)


def test_with_session_state():
    """Test with session state."""
    session = create_session_state(logged_in=True)
    
    with mock_streamlit(session) as st_mock:
        my_mode_function()
        
        # Check session was updated
        assert 'some_key' in session


# Add more tests here...
```

## 🎓 Tips

1. **Start simple**: Test basic rendering first, then add complexity
2. **One assertion per test**: Makes failures easier to diagnose
3. **Use descriptive names**: `test_shows_error_when_theater_not_found` is better than `test_error`
4. **Mock external dependencies**: Database, API calls, file I/O
5. **Test edge cases**: Empty data, None values, errors
6. **Copy-paste patterns**: Use this guide to quickly create new tests

### **Session State Initialization Checklist**

When testing a mode, you MUST initialize session state with all keys it expects:

**Example from analysis_mode.py (14 keys required):**
```python
session['analysis_data_type'] = None
session['selected_company'] = None
session['analysis_director_select'] = None
session['analysis_market_select'] = None
session['analysis_theaters'] = []
session['film_analysis_genres'] = []
session['analysis_date_range'] = ()
session['analysis_report_df'] = None
session['analysis_date_range_start'] = None
session['analysis_date_range_end'] = None
session['film_summary_df'] = None
session['film_detail_data'] = None
session['analysis_genres'] = []
session['analysis_ratings'] = []
```

**How to find all required keys:**
1. Search the mode file for `st.session_state[` and `st.session_state.`
2. Look for `if 'key' not in st.session_state:` patterns
3. Run test and let AttributeError tell you what's missing
4. Iterate until test passes

### **Handling Complex UI Interactions**

**Button Loops:**
If mode has button loops (e.g., data type selection), set state beforehand:
```python
# Don't try to control which button returns True
# Instead, set the state as if user already clicked
session['analysis_data_type'] = 'Film'
render_mode()
```

**Columns Unpacking:**
```python
# Dynamic columns mock handles any number of columns
mock_st.columns.side_effect = lambda spec: [MagicMock()] * (
    spec if isinstance(spec, int) else len(spec)
)

# Now all these work:
# col1, col2 = st.columns(2)
# col1, col2, col3 = st.columns([1, 2, 1])
```

**Date Range Tuples:**
```python
# Modes often expect date ranges as tuples
from datetime import datetime, timedelta
session['analysis_date_range'] = (
    datetime.now() - timedelta(days=30),
    datetime.now()
)
```

## 📊 Coverage Goals by Module Type

- **Pure business logic** (scrapers, parsers): 80-90%
- **Modes with business logic**: **50-70%** ⭐ (when run with full suite)
- **Pure UI rendering**: 20-40% (just test error paths)
- **Database operations**: 60-80%

### **Real-World Coverage Examples**

| Module | Coverage (Isolated) | Coverage (Full Suite) | Tests | Notes |
|--------|---------------------|----------------------|-------|-------|
| `analysis_mode.py` | **34%** | **57%** | 10 tests | Film/theater analysis with complex UI |
| `market_mode.py` | N/A | **80%** | Multiple | Theater selection, simpler logic |
| `omdb_client.py` | **100%** | **100%** | 14 tests | Pure API client, no UI |
| `theming.py` | **93%** | **93%** | 7 tests | Theme management |
| `users.py` | **100%** | **100%** | 22 tests | User management, CRUD ops |

**Note:** "Isolated" = running just that module's tests. "Full Suite" = running all tests (other tests may also execute the module's code).

**Key Insight:** For complex Streamlit modes (500+ lines), **30-40% isolated coverage** with **10-15 focused tests** is excellent and realistic. When other integration tests run, total coverage may reach 50-70%. Don't aim for 100% on UI-heavy code.

### **Coverage Strategy for Modes**

**HIGH PRIORITY (Easy wins, big impact):**
- ✅ Error handling paths (empty data, None values, exceptions)
- ✅ Data type selection logic
- ✅ Database query execution
- ✅ Session state updates
- ✅ Basic rendering (smoke tests)

**MEDIUM PRIORITY:**
- ⚠️ Complex filtering logic
- ⚠️ Data transformations
- ⚠️ Conditional UI rendering

**LOW PRIORITY (Diminishing returns):**
- ⏸️ Exact column layouts
- ⏸️ CSS/styling choices
- ⏸️ All button click combinations
- ⏸️ Every st.write() call



## ⚡ Quick Wins

To quickly improve coverage, focus on:
1. Error handling paths (always easy to test)
2. Permission checks
3. Data validation
4. Session state updates
5. Database query functions

## 🐛 Common Issues & Solutions

### Issue 1: `AttributeError: 'MockSessionState' object has no attribute 'key'`

**Problem:** Mode tries to access session state attribute-style (`st.session_state.key`) but MockSessionState only supports dict-style.

**Solution:** MockSessionState now supports both:
```python
# Both work:
session['key'] = 'value'  # Dict-style
session.key = 'value'     # Attribute-style
```

### Issue 2: `ValueError: not enough values to unpack`

**Problem:** `st.columns()` mock returns wrong number of columns.

**Solution:** Use dynamic side_effect:
```python
mock_st.columns.side_effect = lambda spec: [MagicMock()] * (
    spec if isinstance(spec, int) else len(spec)
)
```

### Issue 3: `AttributeError: 'MagicMock' object has no attribute 'button'`

**Problem:** Columns have their own buttons: `col1.button()`.

**Solution:** Don't control button state; set session state beforehand:
```python
# Instead of trying to mock col1.button()
# Just set the expected state:
session['data_type_selected'] = 'Film'
```

### Issue 4: Tests pass individually but fail together

**Problem:** Session state persists between tests.

**Solution:** Use `autouse=True` fixture to reset mocks:
```python
@pytest.fixture(autouse=True)
def mock_dependencies():
    with patch('app.modes.your_mode.st') as mock_st:
        session = MockSessionState()  # Fresh instance each test
        # ... setup
        yield mock_st
```

### Issue 5: `KeyError: 'some_key'` in session state

**Problem:** Missing initialization.

**Solution:** Initialize ALL keys the mode uses:
```python
# Search mode file for all session state access
# Initialize each one:
session['key1'] = default_value
session['key2'] = []
session['key3'] = None
```

### Issue 6: Database connection errors

**Problem:** Mode tries to connect to real database.

**Solution:** Patch `DB_FILE` and database functions:
```python
with patch('app.config.DB_FILE', '/fake/db.sqlite'), \
     patch('app.modes.your_mode.database.get_data', return_value=pd.DataFrame()):
    # Tests run isolated from real DB
```

---

## 🎯 Real-World Example: `test_modes_analysis.py`

This is the complete, working pattern that achieved **57% coverage** on a 662-statement mode:

```python
"""Tests for app/modes/analysis_mode.py - simplified tests focusing on coverage."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import datetime

from app.modes.analysis_mode import render_film_analysis, render_theater_analysis, render_analysis_mode
from tests.ui_test_helpers import MockSessionState


@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock all dependencies for analysis mode tests."""
    with patch('app.config.DB_FILE', '/fake/db.sqlite'), \
         patch('app.modes.analysis_mode.database.get_all_unique_genres', return_value=['Action', 'Drama', 'Comedy']), \
         patch('app.modes.analysis_mode.database.get_film_details', return_value={'title': 'Test Film', 'year': 2025}), \
         patch('app.modes.analysis_mode.st') as mock_st:
        
        # Initialize session state with ALL required keys
        session = MockSessionState()
        session.analysis_data_type = None
        session.selected_company = None
        session.analysis_director_select = None
        session.analysis_market_select = None
        session.analysis_theaters = []
        session.film_analysis_genres = []
        session.analysis_date_range = ()
        session.analysis_report_df = pd.DataFrame()
        session.analysis_date_range_start = None
        session.analysis_date_range_end = None
        session.film_summary_df = pd.DataFrame()
        session.film_detail_data = pd.DataFrame()
        session.analysis_genres = []
        session.analysis_ratings = []
        
        mock_st.session_state = session
        
        # Mock streamlit functions with sensible defaults
        mock_st.button.return_value = False
        mock_st.date_input.return_value = (datetime.date.today() - datetime.timedelta(days=7), datetime.date.today())
        
        # Dynamic columns mock - handles any number of columns
        def columns_side_effect(spec):
            if isinstance(spec, int):
                return [MagicMock() for _ in range(spec)]
            elif isinstance(spec, list):
                return [MagicMock() for _ in range(len(spec))]
            return [MagicMock(), MagicMock()]
        
        mock_st.columns.side_effect = columns_side_effect
        mock_st.tabs.return_value = [MagicMock(), MagicMock()]
        mock_st.multiselect.return_value = []
        
        # Mock spinner context manager
        spinner_mock = MagicMock()
        spinner_mock.__enter__ = Mock(return_value=MagicMock())
        spinner_mock.__exit__ = Mock(return_value=False)
        mock_st.spinner.return_value = spinner_mock
        
        mock_st.rerun = MagicMock()
        
        yield mock_st


@pytest.fixture
def sample_film_data():
    """Sample film data for testing."""
    return pd.DataFrame({
        'film_title': ['Movie A', 'Movie B', 'Movie C'],
        'theater_name': ['Theater 1', 'Theater 2', 'Theater 3'],
        'play_date': ['2025-10-20', '2025-10-21', '2025-10-22'],
        'price': [12.50, 13.00, 11.00],
    })


class TestRenderFilmAnalysis:
    """Test render_film_analysis function."""
    
    def test_renders_without_error(self, mock_dependencies, sample_film_data):
        """Test that film analysis renders without crashing."""
        with patch('app.modes.analysis_mode.database.execute_query', return_value=sample_film_data):
            # Should not raise any exceptions
            render_film_analysis(cache_data={})
    
    def test_renders_ui_elements(self, mock_dependencies):
        """Test that expected UI elements are rendered."""
        with patch('app.modes.analysis_mode.database.execute_query', return_value=pd.DataFrame()):
            render_film_analysis(cache_data={})
            
            mock_dependencies.subheader.assert_called()
            mock_dependencies.date_input.assert_called()
            mock_dependencies.button.assert_called()
    
    def test_handles_empty_data(self, mock_dependencies):
        """Test handling of empty dataframe."""
        with patch('app.modes.analysis_mode.database.execute_query', return_value=pd.DataFrame()):
            mock_dependencies.button.return_value = True
            
            render_film_analysis(cache_data={})
            
            # Should show warning for empty data
            mock_dependencies.warning.assert_called()


# Result: 10 tests, 34% isolated coverage (57% in full suite), all passing!
```

**Key Takeaways:**
- ✅ **Patch at module level** (`app.modes.analysis_mode.st`)
- ✅ **Initialize 14 session state keys** (found by trial & error)
- ✅ **Dynamic columns mocking** (handles 2, 3, 4+ columns)
- ✅ **Simple assertions** (render succeeds, UI called, errors shown)
- ✅ **34% isolated coverage with 10 focused tests** (57% when run with full suite)
- ✅ **All tests passing**, clean and maintainable

This pattern is now proven and reusable for all other modes!




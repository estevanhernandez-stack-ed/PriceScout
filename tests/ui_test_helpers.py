"""
Reusable UI Test Helpers for Streamlit Components

This module provides helper functions and fixtures for testing Streamlit UI components
across different modes. By centralizing these patterns, we can:
1. Ensure consistent testing approaches
2. Reduce code duplication
3. Make it easy to add tests to new modes

Usage:
    from tests.ui_test_helpers import mock_streamlit, mock_session_state, assert_error_displayed
    
    def test_my_mode():
        with mock_streamlit() as st_mock:
            # Your test code
            assert_error_displayed(st_mock, "Expected error message")
"""

import pytest
from unittest.mock import MagicMock, patch
from contextlib import contextmanager


# ============================================================================
# SESSION STATE HELPERS
# ============================================================================

class MockSessionState(dict):
    """
    A dictionary-based mock for st.session_state that tracks all operations.
    Supports both dict-style and attribute-style access.
    
    Tracks:
    - All key accesses
    - All key assignments
    - All key deletions
    
    Usage:
        session = MockSessionState({'logged_in': True, 'user_name': 'test'})
        session['new_key'] = 'value'
        session.other_key = 'value'  # Also works
        assert 'new_key' in session.set_keys
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Use object's __setattr__ to avoid our custom logic
        object.__setattr__(self, 'accessed_keys', [])
        object.__setattr__(self, 'set_keys', {})
        object.__setattr__(self, 'deleted_keys', [])
    
    def __getitem__(self, key):
        self.accessed_keys.append(key)
        return super().__getitem__(key)
    
    def __setitem__(self, key, value):
        self.set_keys[key] = value
        super().__setitem__(key, value)
    
    def __delitem__(self, key):
        self.deleted_keys.append(key)
        super().__delitem__(key)
    
    def __getattr__(self, key):
        """Support attribute-style access like st.session_state.key"""
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'MockSessionState' object has no attribute '{key}'")
    
    def __setattr__(self, key, value):
        """Support attribute-style assignment like st.session_state.key = value"""
        # Special handling for our tracking attributes
        if key in ('accessed_keys', 'set_keys', 'deleted_keys'):
            object.__setattr__(self, key, value)
        else:
            self[key] = value
    
    def get(self, key, default=None):
        self.accessed_keys.append(key)
        return super().get(key, default)


@pytest.fixture
def mock_session_state():
    """
    Fixture providing a fresh MockSessionState instance.
    
    Usage:
        def test_something(mock_session_state):
            mock_session_state['key'] = 'value'
            assert 'key' in mock_session_state
    """
    return MockSessionState()


def create_session_state(**kwargs):
    """
    Create a MockSessionState with initial values.
    
    Args:
        **kwargs: Initial key-value pairs for session state
    
    Returns:
        MockSessionState instance
    
    Usage:
        session = create_session_state(logged_in=True, user_name='Alice')
    """
    return MockSessionState(kwargs)


# ============================================================================
# STREAMLIT COMPONENT MOCKS
# ============================================================================

@contextmanager
def mock_streamlit(session_state=None):
    """
    Context manager that mocks all common Streamlit functions.
    
    Args:
        session_state: Optional MockSessionState or dict to use. If None, creates empty one.
    
    Yields:
        MagicMock: The mocked streamlit module with tracked method calls
    
    Usage:
        with mock_streamlit() as st_mock:
            my_function_that_uses_streamlit()
            assert st_mock.error.called
            st_mock.error.assert_called_with("Expected error")
    """
    if session_state is None:
        session_state = MockSessionState()
    
    st_mock = MagicMock()
    st_mock.session_state = session_state
    
    # Mock common Streamlit functions
    st_mock.title = MagicMock()
    st_mock.header = MagicMock()
    st_mock.subheader = MagicMock()
    st_mock.text = MagicMock()
    st_mock.markdown = MagicMock()
    st_mock.write = MagicMock()
    
    # Status/feedback
    st_mock.success = MagicMock()
    st_mock.error = MagicMock()
    st_mock.warning = MagicMock()
    st_mock.info = MagicMock()
    
    # Input widgets
    st_mock.button = MagicMock(return_value=False)
    st_mock.text_input = MagicMock(return_value="")
    st_mock.number_input = MagicMock(return_value=0)
    st_mock.selectbox = MagicMock(return_value=None)
    st_mock.multiselect = MagicMock(return_value=[])
    st_mock.checkbox = MagicMock(return_value=False)
    st_mock.radio = MagicMock(return_value=None)
    st_mock.slider = MagicMock(return_value=0)
    st_mock.date_input = MagicMock()
    st_mock.file_uploader = MagicMock(return_value=None)
    
    # Layout
    st_mock.columns = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock()])
    st_mock.container = MagicMock()
    st_mock.expander = MagicMock()
    st_mock.tabs = MagicMock(return_value=[MagicMock(), MagicMock()])
    st_mock.sidebar = MagicMock()
    
    # Data display
    st_mock.dataframe = MagicMock()
    st_mock.table = MagicMock()
    st_mock.metric = MagicMock()
    st_mock.json = MagicMock()
    
    # Control flow
    st_mock.rerun = MagicMock()
    st_mock.stop = MagicMock()
    st_mock.form = MagicMock()
    st_mock.form_submit_button = MagicMock(return_value=False)
    
    # Downloads
    st_mock.download_button = MagicMock()
    
    # Spinner/progress
    st_mock.spinner = MagicMock()
    st_mock.progress = MagicMock()
    
    # Other
    st_mock.divider = MagicMock()
    st_mock.empty = MagicMock()
    
    yield st_mock


# ============================================================================
# ASSERTION HELPERS
# ============================================================================

def assert_error_displayed(st_mock, expected_message=None):
    """
    Assert that st.error was called, optionally with a specific message.
    
    Args:
        st_mock: The mocked streamlit module
        expected_message: Optional substring to check for in error message
    
    Usage:
        assert_error_displayed(st_mock)
        assert_error_displayed(st_mock, "Invalid input")
    """
    assert st_mock.error.called, "Expected st.error to be called but it wasn't"
    
    if expected_message:
        call_args = str(st_mock.error.call_args)
        assert expected_message in call_args, \
            f"Expected error message to contain '{expected_message}', but got: {call_args}"


def assert_success_displayed(st_mock, expected_message=None):
    """Assert that st.success was called."""
    assert st_mock.success.called, "Expected st.success to be called but it wasn't"
    
    if expected_message:
        call_args = str(st_mock.success.call_args)
        assert expected_message in call_args, \
            f"Expected success message to contain '{expected_message}', but got: {call_args}"


def assert_warning_displayed(st_mock, expected_message=None):
    """Assert that st.warning was called."""
    assert st_mock.warning.called, "Expected st.warning to be called but it wasn't"
    
    if expected_message:
        call_args = str(st_mock.warning.call_args)
        assert expected_message in call_args, \
            f"Expected warning message to contain '{expected_message}', but got: {call_args}"


def assert_info_displayed(st_mock, expected_message=None):
    """Assert that st.info was called."""
    assert st_mock.info.called, "Expected st.info to be called but it wasn't"
    
    if expected_message:
        call_args = str(st_mock.info.call_args)
        assert expected_message in call_args, \
            f"Expected info message to contain '{expected_message}', but got: {call_args}"


def assert_no_errors(st_mock):
    """Assert that st.error was NOT called."""
    assert not st_mock.error.called, \
        f"Expected no errors but st.error was called with: {st_mock.error.call_args}"


def assert_rerun_called(st_mock):
    """Assert that st.rerun was called."""
    assert st_mock.rerun.called, "Expected st.rerun to be called but it wasn't"


def assert_dataframe_displayed(st_mock):
    """Assert that st.dataframe was called."""
    assert st_mock.dataframe.called, "Expected st.dataframe to be called but it wasn't"


def get_call_count(mock_func):
    """
    Get the number of times a mock function was called.
    
    Usage:
        count = get_call_count(st_mock.error)
    """
    return mock_func.call_count


def get_last_call_args(mock_func):
    """
    Get the arguments from the last call to a mock function.
    
    Returns:
        tuple: (args, kwargs) from the last call
    
    Usage:
        args, kwargs = get_last_call_args(st_mock.error)
        error_message = args[0]
    """
    if not mock_func.called:
        return None, None
    
    call = mock_func.call_args
    return call.args if call else (), call.kwargs if call else {}


# ============================================================================
# WIDGET INTERACTION HELPERS
# ============================================================================

def simulate_button_click(st_mock, button_label=None):
    """
    Configure a button mock to return True (clicked).
    
    Args:
        st_mock: The mocked streamlit module
        button_label: Optional specific button label to target
    
    Usage:
        simulate_button_click(st_mock)
        # Now any st.button() call will return True
    """
    st_mock.button.return_value = True


def simulate_text_input(st_mock, value):
    """Set text_input to return a specific value."""
    st_mock.text_input.return_value = value


def simulate_selectbox(st_mock, value):
    """Set selectbox to return a specific value."""
    st_mock.selectbox.return_value = value


def simulate_multiselect(st_mock, values):
    """Set multiselect to return specific values."""
    st_mock.multiselect.return_value = values


def simulate_checkbox(st_mock, checked=True):
    """Set checkbox to return True or False."""
    st_mock.checkbox.return_value = checked


# ============================================================================
# DATABASE MOCK HELPERS
# ============================================================================

@pytest.fixture
def mock_database():
    """
    Fixture providing mocked database functions.
    
    Usage:
        def test_something(mock_database):
            with patch('app.database.get_connection', return_value=mock_database.connection):
                # Your test
    """
    db_mock = MagicMock()
    db_mock.connection = MagicMock()
    db_mock.cursor = MagicMock()
    db_mock.connection.cursor.return_value = db_mock.cursor
    return db_mock


# ============================================================================
# EXAMPLE USAGE PATTERNS
# ============================================================================

"""
PATTERN 1: Basic UI Test
========================
def test_mode_displays_title():
    with mock_streamlit() as st_mock:
        my_mode_function()
        st_mock.title.assert_called_once()


PATTERN 2: Test Error Handling
===============================
def test_mode_shows_error_when_no_data():
    with mock_streamlit() as st_mock:
        my_mode_function(data=None)
        assert_error_displayed(st_mock, "No data")


PATTERN 3: Test Button Click
=============================
def test_mode_processes_data_on_button_click():
    with mock_streamlit() as st_mock:
        simulate_button_click(st_mock)
        my_mode_function()
        assert_success_displayed(st_mock)


PATTERN 4: Test Session State
==============================
def test_mode_updates_session_state():
    session = create_session_state(logged_in=True)
    with mock_streamlit(session) as st_mock:
        my_mode_function()
        assert 'result' in session.set_keys


PATTERN 5: Test Form Submission
================================
def test_mode_handles_form_submission():
    with mock_streamlit() as st_mock:
        st_mock.form_submit_button.return_value = True
        simulate_text_input(st_mock, "test_value")
        my_mode_function()
        assert_success_displayed(st_mock)
"""

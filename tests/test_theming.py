import pytest
from unittest.mock import MagicMock, patch
import json
import os
import sys

# Add the app directory to the system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.theming import (
    load_themes,
    apply_css,
    theme_selector_component,
    THEMES
)

# Test load_themes function
def test_load_themes_success(tmp_path):
    """Test that themes are loaded correctly from a valid JSON file."""
    themes_file = tmp_path / "themes.json"
    themes_data = {"MyTheme": {"css": "body { color: red; }"}}
    themes_file.write_text(json.dumps(themes_data))
    
    with patch('app.theming.THEMES_FILE', str(themes_file)):
        loaded_themes = load_themes()
        assert "MyTheme" in loaded_themes
        assert loaded_themes["MyTheme"]["css"] == "body { color: red; }"

def test_load_themes_file_not_found():
    """Test that load_themes returns a default theme if the file is not found."""
    with patch('app.theming.THEMES_FILE', "nonexistent.json"):
        themes = load_themes()
        assert "Default" in themes
        assert "css" in themes["Default"]

def test_load_themes_invalid_json(tmp_path):
    """Test that load_themes returns a default theme for an invalid JSON file."""
    themes_file = tmp_path / "invalid.json"
    themes_file.write_text("this is not json")
    
    with patch('app.theming.THEMES_FILE', str(themes_file)):
        themes = load_themes()
        assert "Default" in themes

# Test apply_css function
@patch('app.theming.st')
def test_apply_css_with_css(mock_st):
    """Test that apply_css calls st.markdown with the correct style tag."""
    apply_css("test-css")
    mock_st.markdown.assert_called_once_with("<style>test-css</style>", unsafe_allow_html=True)

@patch('app.theming.st')
def test_apply_css_with_empty_css(mock_st):
    """Test that apply_css does not call st.markdown with empty CSS."""
    apply_css("")
    mock_st.markdown.assert_not_called()

@patch('app.theming.st')
def test_apply_css_with_none(mock_st):
    """Test that apply_css does not call st.markdown with None."""
    apply_css(None)
    mock_st.markdown.assert_not_called()

# Test theme_selector_component function
def test_theme_selector_component_initializes_session_state():
    """Test that theme selector initializes session state."""
    mock_st = MagicMock()
    mock_st.session_state = MagicMock()
    del mock_st.session_state.dark_mode

    with patch('app.theming.st', mock_st):
        theme_selector_component()

        # Should set dark_mode in session state
        assert hasattr(mock_st.session_state, 'dark_mode')

def test_theme_selector_component_renders_sidebar():
    """Test that theme selector renders in sidebar."""
    mock_st = MagicMock()
    mock_session = MagicMock()
    mock_session.dark_mode = True
    mock_st.session_state = mock_session
    mock_st.sidebar.toggle.return_value = True

    with patch('app.theming.st', mock_st):
        theme_selector_component()

        # Verify sidebar components were called
        mock_st.sidebar.divider.assert_called_once()
        mock_st.sidebar.toggle.assert_called_once_with(
            "🌙 Dark Mode",
            value=True,
            key="dark_mode_toggle"
        )

def test_theme_selector_component_theme_change_triggers_rerun(mocker):
    """Test that changing the theme triggers st.rerun."""
    mock_st = mocker.patch('app.theming.st')
    # Set initial state (dark mode off)
    mock_st.session_state.dark_mode = False
    
    # Simulate user turning the toggle ON
    mock_st.sidebar.toggle.return_value = True

    theme_selector_component()

    # Should call rerun because the state changed
    mock_st.rerun.assert_called_once()

@patch('app.theming.st')
def test_theme_selector_component_applies_css(mock_st):
    """Test that CSS is applied correctly based on theme."""
    # Test with dark mode ON
    mock_st.session_state.dark_mode = True
    mock_st.sidebar.toggle.return_value = True # No change
    
    theme_selector_component()
    
    # Get the css from the call_args
    css_call = mock_st.markdown.call_args[0][0]
    assert ".stApp" in css_call # A known dark mode style
    assert "background-color: #0E1117" in css_call

    # Reset and test with dark mode OFF
    mock_st.reset_mock()
    mock_st.session_state.dark_mode = False
    mock_st.sidebar.toggle.return_value = False # No change
    
    theme_selector_component()
    
    css_call_light = mock_st.markdown.call_args[0][0]
    assert ".stApp" not in css_call_light
    assert "background-color: #0E1117" not in css_call_light
    assert "button[kind=\"primary\"]" in css_call_light # Should still have primary button override

def test_theme_selector_component_no_theme_change():
    """Test that selecting same theme doesn't trigger rerun."""
    mock_st = MagicMock()
    current_theme = list(THEMES.keys())[0]

    mock_session = MagicMock()
    mock_session.dark_mode = True
    mock_st.session_state = mock_session
    mock_st.sidebar.toggle.return_value = True

    with patch('app.theming.st', mock_st):
        theme_selector_component()

        # Should NOT call rerun if theme didn't change
        mock_st.rerun.assert_not_called()

def test_themes_loaded_on_import():
    """Test that themes are loaded into the module-level variable on import."""
    assert isinstance(THEMES, dict)
    assert len(THEMES) > 0
    assert "Default" in THEMES

import pytest
from unittest.mock import patch, mock_open, MagicMock
import json
from app.theming import load_themes, apply_css, theme_selector_component, THEMES


def test_load_themes_success():
    """Test loading themes from valid JSON file."""
    mock_themes = {
        "Dark": {"css": "body { background: black; }"},
        "Light": {"css": "body { background: white; }"}
    }
    
    with patch('builtins.open', mock_open(read_data=json.dumps(mock_themes))):
        themes = load_themes()
        
        assert "Dark" in themes
        assert "Light" in themes
        assert themes["Dark"]["css"] == "body { background: black; }"


def test_load_themes_file_not_found():
    """Test fallback when themes.json is missing."""
    with patch('builtins.open', side_effect=FileNotFoundError):
        themes = load_themes()
        
        # Should return default theme
        assert "Default" in themes
        assert "css" in themes["Default"]


def test_load_themes_invalid_json():
    """Test fallback when themes.json has invalid JSON."""
    with patch('builtins.open', mock_open(read_data="invalid json {")):
        themes = load_themes()
        
        # Should return default theme
        assert "Default" in themes
        assert "css" in themes["Default"]


def test_apply_css_with_css():
    """Test that apply_css injects CSS into Streamlit."""
    mock_st = MagicMock()
    
    with patch('app.theming.st', mock_st):
        apply_css("body { color: red; }")
        
        # Verify st.markdown was called with the CSS
        mock_st.markdown.assert_called_once()
        call_args = mock_st.markdown.call_args
        assert "body { color: red; }" in call_args[0][0]
        assert call_args[1]['unsafe_allow_html'] is True


def test_apply_css_with_empty_css():
    """Test that apply_css handles empty CSS gracefully."""
    mock_st = MagicMock()
    
    with patch('app.theming.st', mock_st):
        apply_css("")
        
        # Should not call st.markdown with empty CSS
        mock_st.markdown.assert_not_called()


def test_apply_css_with_none():
    """Test that apply_css handles None gracefully."""
    mock_st = MagicMock()
    
    with patch('app.theming.st', mock_st):
        apply_css(None)
        
        # Should not call st.markdown with None
        mock_st.markdown.assert_not_called()


def test_theme_selector_component_initializes_session_state():
    """Test that theme selector initializes session state."""
    mock_st = MagicMock()
    # Create a mock that supports 'in' operator for session state checks
    class MockSessionState:
        def __init__(self):
            # Initialize _dict first using object.__setattr__ to avoid recursion
            object.__setattr__(self, '_dict', {})
            # Don't initialize current_theme - let the function do it
        
        def __contains__(self, key):
            return key in self._dict
        
        def __setattr__(self, name, value):
            if name == '_dict':
                object.__setattr__(self, name, value)
            else:
                self._dict[name] = value
                object.__setattr__(self, name, value)
    
    mock_session = MockSessionState()
    mock_st.session_state = mock_session
    mock_st.sidebar.selectbox.return_value = list(THEMES.keys())[0]
    
    with patch('app.theming.st', mock_st):
        theme_selector_component()
        
        # Should set current_theme in session state
        assert mock_session.current_theme is not None


def test_theme_selector_component_renders_sidebar():
    """Test that theme selector renders in sidebar."""
    mock_st = MagicMock()
    mock_session = MagicMock()
    mock_session.current_theme = list(THEMES.keys())[0]
    mock_st.session_state = mock_session
    mock_st.sidebar.selectbox.return_value = list(THEMES.keys())[0]
    
    with patch('app.theming.st', mock_st):
        theme_selector_component()
        
        # Verify sidebar components were called
        mock_st.sidebar.divider.assert_called_once()
        mock_st.sidebar.subheader.assert_called_once_with("Appearance")
        mock_st.sidebar.selectbox.assert_called_once()


def test_theme_selector_component_theme_change_triggers_rerun():
    """Test that changing theme triggers st.rerun()."""
    mock_st = MagicMock()
    current_theme = list(THEMES.keys())[0]
    new_theme = list(THEMES.keys())[1] if len(THEMES.keys()) > 1 else current_theme
    
    mock_session = MagicMock()
    mock_session.current_theme = current_theme
    mock_st.session_state = mock_session
    mock_st.sidebar.selectbox.return_value = new_theme
    
    with patch('app.theming.st', mock_st):
        theme_selector_component()
        
        # If theme changed, should call rerun
        if new_theme != current_theme:
            mock_st.rerun.assert_called_once()
        
        # Session state should be updated
        assert mock_session.current_theme == new_theme


def test_theme_selector_component_applies_css():
    """Test that theme selector applies CSS."""
    mock_st = MagicMock()
    mock_session = MagicMock()
    mock_session.current_theme = list(THEMES.keys())[0]
    mock_st.session_state = mock_session
    mock_st.sidebar.selectbox.return_value = list(THEMES.keys())[0]
    
    with patch('app.theming.st', mock_st):
        theme_selector_component()
        
        # Should call st.markdown to apply CSS
        assert mock_st.markdown.called


def test_theme_selector_component_no_theme_change():
    """Test that selecting same theme doesn't trigger rerun."""
    mock_st = MagicMock()
    current_theme = list(THEMES.keys())[0]
    
    mock_session = MagicMock()
    mock_session.current_theme = current_theme
    mock_st.session_state = mock_session
    mock_st.sidebar.selectbox.return_value = current_theme
    
    with patch('app.theming.st', mock_st):
        theme_selector_component()
        
        # Should NOT call rerun if theme didn't change
        mock_st.rerun.assert_not_called()


def test_themes_loaded_on_import():
    """Test that THEMES is populated on module import."""
    # THEMES should be loaded when module is imported
    assert THEMES is not None
    assert isinstance(THEMES, dict)
    assert len(THEMES) > 0

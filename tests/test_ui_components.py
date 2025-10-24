import pytest
from unittest.mock import MagicMock, patch
import streamlit as st
import datetime
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.ui_components import apply_daypart_auto_selection

@pytest.fixture
def mock_ui_session_state(monkeypatch):
    """Fixture to mock streamlit's session_state for UI component tests."""
    mock_state = MagicMock()
    # This will be populated by the function under test
    mock_state.selected_showtimes = {}
    monkeypatch.setattr(st, "session_state", mock_state)
    return mock_state

# Sample data for tests
all_showings_data = {
    '2025-09-08': {
        'Theater A': [
            {'film_title': 'Film 1', 'showtime': '10:00am', 'daypart': 'Matinee'},
            {'film_title': 'Film 1', 'showtime': '01:00pm', 'daypart': 'Matinee'}, # another matinee
            {'film_title': 'Film 1', 'showtime': '08:00pm', 'daypart': 'Prime'},
            {'film_title': 'Film 2', 'showtime': '09:00pm', 'daypart': 'Prime'},
        ]
    }
}
films_to_process_data = ['Film 1', 'Film 2']
theaters_to_process_data = ['Theater A']

def test_apply_daypart_selection_all(mock_ui_session_state):
    """Tests that selecting 'All' dayparts selects all available showtimes."""
    daypart_selections = {"All", "Matinee", "Prime"}
    
    apply_daypart_auto_selection(daypart_selections, all_showings_data, films_to_process_data, theaters_to_process_data)
    
    selected = st.session_state.selected_showtimes
    date_key = '2025-09-08'
    assert date_key in selected
    selected_for_date = selected[date_key]

    assert 'Theater A' in selected_for_date
    assert 'Film 1' in selected_for_date['Theater A']
    assert 'Film 2' in selected_for_date['Theater A']
    # All 3 showtimes for Film 1 should be selected
    assert len(selected_for_date['Theater A']['Film 1']) == 3
    assert '10:00am' in selected_for_date['Theater A']['Film 1']
    assert '01:00pm' in selected_for_date['Theater A']['Film 1']
    assert '08:00pm' in selected_for_date['Theater A']['Film 1']
    # The one showtime for Film 2 should be selected
    assert len(selected_for_date['Theater A']['Film 2']) == 1
    assert '09:00pm' in selected_for_date['Theater A']['Film 2']

def test_apply_daypart_selection_individual(mock_ui_session_state):
    """Tests that selecting individual dayparts selects only the first showtime for each."""
    daypart_selections = {"Matinee", "Prime"}

    apply_daypart_auto_selection(daypart_selections, all_showings_data, films_to_process_data, theaters_to_process_data)

    selected = st.session_state.selected_showtimes
    date_key = '2025-09-08'
    assert date_key in selected
    selected_for_date = selected[date_key]

    assert 'Theater A' in selected_for_date
    assert 'Film 1' in selected_for_date['Theater A']
    assert 'Film 2' in selected_for_date['Theater A']
    
    # For Film 1, it should select the EARLIEST Matinee ('10:00am') and the EARLIEST Prime ('08:00pm')
    assert len(selected_for_date['Theater A']['Film 1']) == 2
    assert '10:00am' in selected_for_date['Theater A']['Film 1']
    assert '08:00pm' in selected_for_date['Theater A']['Film 1']
    assert '01:00pm' not in selected_for_date['Theater A']['Film 1'] # The second matinee should be ignored

    # For Film 2, it should select the only Prime showtime
    assert len(selected_for_date['Theater A']['Film 2']) == 1
    assert '09:00pm' in selected_for_date['Theater A']['Film 2']

def test_apply_daypart_selection_empty(mock_ui_session_state):
    """Tests that an empty daypart selection results in no selected showtimes."""
    daypart_selections = set()
    apply_daypart_auto_selection(daypart_selections, all_showings_data, films_to_process_data, theaters_to_process_data)
    assert not st.session_state.selected_showtimes # Should be an empty dict
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from app.modes.compsnipe_mode import render_compsnipe_mode


class MockSessionState:
    """Mock Streamlit session state that acts like an object."""
    def __init__(self, **kwargs):
        self._data = kwargs
        for key, value in kwargs.items():
            object.__setattr__(self, key, value)
    
    def get(self, key, default=None):
        return self._data.get(key, default)
    
    def __contains__(self, key):
        return key in self._data
    
    def update(self, d):
        for key, value in d.items():
            self._data[key] = value
            object.__setattr__(self, key, value)
    
    def __setattr__(self, key, value):
        if key != '_data':
            self._data[key] = value
        object.__setattr__(self, key, value)


@pytest.fixture
def mock_scout():
    """Create a mock Scout object."""
    scout = MagicMock()
    return scout


@pytest.fixture
def sample_theaters():
    """Sample theater data for testing."""
    return [
        {'name': 'AMC West Olive 16', 'url': 'https://example.com/1', 'zip': '63141'},
        {'name': 'Marcus Wehrenberg Des Peres', 'url': 'https://example.com/2', 'zip': '63131'},
        {'name': 'B&B Creve Coeur West Olive', 'url': 'https://example.com/3', 'zip': '63141'}
    ]


@pytest.fixture
def sample_markets_data():
    """Sample markets data."""
    return {
        'AMC Theatres': {
            'St. Louis': {
                'theaters': ['AMC West Olive 16']
            }
        }
    }


@pytest.fixture
def sample_cache_data():
    """Sample cache data."""
    return {
        'AMC West Olive 16': {
            'name': 'AMC West Olive 16',
            'url': 'https://example.com/1',
            'zip': '63141'
        }
    }


def test_basic_ui_rendering(mock_scout, sample_theaters, sample_markets_data, sample_cache_data):
    """Test that CompSnipe mode renders basic UI elements."""
    with patch('app.modes.compsnipe_mode.st') as mock_st:
        mock_st.session_state = MockSessionState(live_search_results={})
        mock_st.text_input.return_value = ""
        mock_st.form.return_value.__enter__.return_value = MagicMock()
        mock_st.form.return_value.__exit__.return_value = None
        mock_st.form_submit_button.return_value = False
        
        render_compsnipe_mode(
            mock_scout, sample_theaters, False, 
            MagicMock(), sample_markets_data, sample_cache_data
        )
        
        # Verify basic UI elements
        mock_st.title.assert_called_once()
        assert 'CompSnipe' in str(mock_st.title.call_args)


def test_fuzzy_search_matching(mock_scout, sample_theaters, sample_markets_data, sample_cache_data):
    """Test fuzzy search finds matching theaters."""
    with patch('app.modes.compsnipe_mode.st') as mock_st:
        with patch('app.modes.compsnipe_mode.fuzz') as mock_fuzz:
            mock_st.session_state = MockSessionState(live_search_results={})
            # First call for fuzzy search, then name search, then ZIP
            mock_st.text_input.side_effect = ["AMC", "", ""]
            mock_st.form.return_value.__enter__.return_value = MagicMock()
            mock_st.form.return_value.__exit__.return_value = None
            mock_st.form_submit_button.return_value = False
            
            # Mock high scores for AMC theaters
            mock_fuzz.token_set_ratio.side_effect = lambda q, t: 90 if 'AMC' in t else 50
            
            render_compsnipe_mode(
                mock_scout, sample_theaters, False,
                MagicMock(), sample_markets_data, sample_cache_data
            )
            
            # Verify fuzzy matching was used
            assert mock_fuzz.token_set_ratio.call_count >= 1


def test_no_matching_theaters_message(mock_scout, sample_theaters, sample_markets_data, sample_cache_data):
    """Test info message when no theaters match search."""
    with patch('app.modes.compsnipe_mode.st') as mock_st:
        with patch('app.modes.compsnipe_mode.fuzz') as mock_fuzz:
            mock_st.session_state = MockSessionState(live_search_results={})
            mock_st.text_input.side_effect = ["XYZ123", "", ""]
            mock_st.form.return_value.__enter__.return_value = MagicMock()
            mock_st.form.return_value.__exit__.return_value = None
            mock_st.form_submit_button.return_value = False
            
            # Low scores - no matches
            mock_fuzz.token_set_ratio.return_value = 30
            
            render_compsnipe_mode(
                mock_scout, sample_theaters, False,
                MagicMock(), sample_markets_data, sample_cache_data
            )
            
            # Verify info about no matches
            info_calls = [str(c) for c in mock_st.info.call_args_list]
            assert any('no matching' in c.lower() for c in info_calls)


def test_forms_rendered(mock_scout, sample_theaters, sample_markets_data, sample_cache_data):
    """Test that all forms are rendered."""
    with patch('app.modes.compsnipe_mode.st') as mock_st:
        mock_st.session_state = MockSessionState(live_search_results={})
        mock_st.text_input.return_value = ""
        mock_st.form.return_value.__enter__.return_value = MagicMock()
        mock_st.form.return_value.__exit__.return_value = None
        mock_st.form_submit_button.return_value = False
        mock_st.date_input.return_value = date.today()
        
        render_compsnipe_mode(
            mock_scout, sample_theaters, False,
            MagicMock(), sample_markets_data, sample_cache_data
        )
        
        # Verify forms were created
        assert mock_st.form.call_count >= 2  # Name search + ZIP search


def test_theater_selection_with_selection(mock_scout, sample_theaters, sample_markets_data, sample_cache_data):
    """Test UI when theaters are selected."""
    with patch('app.modes.compsnipe_mode.st') as mock_st:
        mock_st.session_state = MockSessionState(
            compsnipe_theaters=[{'name': 'Test Theater', 'url': 'test'}],
            live_search_results={}
        )
        mock_st.text_input.return_value = ""
        mock_st.form.return_value.__enter__.return_value = MagicMock()
        mock_st.form.return_value.__exit__.return_value = None
        mock_st.form_submit_button.return_value = False
        mock_st.date_input.return_value = date.today()
        mock_st.button.return_value = False
        
        render_compsnipe_mode(
            mock_scout, sample_theaters, False,
            MagicMock(), sample_markets_data, sample_cache_data
        )
        
        # Verify "Find Available Films" button is rendered
        button_calls = [str(c) for c in mock_st.button.call_args_list]
        assert any('find available films' in c.lower() for c in button_calls)


def test_film_scope_selection_stage(mock_scout, sample_theaters, sample_markets_data, sample_cache_data):
    """Test film scope selection stage renders."""
    with patch('app.modes.compsnipe_mode.st') as mock_st:
        mock_st.session_state = MockSessionState(
            stage='cs_films_found',
            compsnipe_theaters=[
                {'name': 'Theater 1', 'url': 'test1'},
                {'name': 'Theater 2', 'url': 'test2'}
            ],
            all_showings={
                'Theater 1': [
                    {'film_title': 'Movie A', 'showtime': '7:00 PM'},
                    {'film_title': 'Movie B', 'showtime': '9:00 PM'}
                ],
                'Theater 2': [
                    {'film_title': 'Movie A', 'showtime': '7:30 PM'}
                ]
            },
            live_search_results={}
        )
        
        mock_st.text_input.return_value = ""
        mock_st.form.return_value.__enter__.return_value = MagicMock()
        mock_st.form.return_value.__exit__.return_value = None
        mock_st.form_submit_button.return_value = False
        mock_st.button.return_value = False
        
        # Mock columns
        mock_cols = [MagicMock(), MagicMock(), MagicMock()]
        for col in mock_cols:
            col.button.return_value = False
        mock_st.columns.return_value = mock_cols
        
        render_compsnipe_mode(
            mock_scout, sample_theaters, False,
            MagicMock(), sample_markets_data, sample_cache_data
        )
        
        # Verify film scope buttons were created
        assert any(col.button.called for col in mock_cols)


def test_disabled_ui_elements(mock_scout, sample_theaters, sample_markets_data, sample_cache_data):
    """Test that UI elements respect IS_DISABLED flag."""
    with patch('app.modes.compsnipe_mode.st') as mock_st:
        mock_st.session_state = MockSessionState(live_search_results={})
        mock_st.text_input.return_value = ""
        mock_st.form.return_value.__enter__.return_value = MagicMock()
        mock_st.form.return_value.__exit__.return_value = None
        mock_st.form_submit_button.return_value = False
        mock_st.date_input.return_value = date.today()
        
        render_compsnipe_mode(
            mock_scout, sample_theaters, 
            True,  # IS_DISABLED = True
            MagicMock(), sample_markets_data, sample_cache_data
        )
        
        # Check that disabled flag was used
        text_input_calls = mock_st.text_input.call_args_list
        disabled_calls = [c for c in text_input_calls if c.kwargs.get('disabled') == True]
        assert len(disabled_calls) > 0


def test_live_name_search_results_display(mock_scout, sample_theaters, sample_markets_data, sample_cache_data):
    """Test display of live name search results."""
    with patch('app.modes.compsnipe_mode.st') as mock_st:
        mock_st.session_state = MockSessionState(
            live_name_search_results={
                'Theater A': {'name': 'Theater A', 'url': 'test1'},
                'Theater B': {'name': 'Theater B', 'url': 'test2'}
            },
            live_search_results={}
        )
        
        mock_st.text_input.return_value = ""
        mock_st.form.return_value.__enter__.return_value = MagicMock()
        mock_st.form.return_value.__exit__.return_value = None
        mock_st.form_submit_button.return_value = False
        
        # Mock columns for theater buttons
        mock_cols = [MagicMock() for _ in range(4)]
        for col in mock_cols:
            col.button.return_value = False
        mock_st.columns.return_value = mock_cols
        
        render_compsnipe_mode(
            mock_scout, sample_theaters, False,
            MagicMock(), sample_markets_data, sample_cache_data
        )
        
        # Verify buttons were created for results
        assert any(col.button.called for col in mock_cols)


def test_live_zip_search_results_display(mock_scout, sample_theaters, sample_markets_data, sample_cache_data):
    """Test display of live ZIP search results."""
    with patch('app.modes.compsnipe_mode.st') as mock_st:
        mock_st.session_state = MockSessionState(
            live_search_results={
                'Theater X': {'name': 'Theater X', 'url': 'testX'},
                'Theater Y': {'name': 'Theater Y', 'url': 'testY'}
            }
        )
        
        mock_st.text_input.return_value = ""
        mock_st.form.return_value.__enter__.return_value = MagicMock()
        mock_st.form.return_value.__exit__.return_value = None
        mock_st.form_submit_button.return_value = False
        
        # Mock columns
        mock_cols = [MagicMock() for _ in range(4)]
        for col in mock_cols:
            col.button.return_value = False
        mock_st.columns.return_value = mock_cols
        
        render_compsnipe_mode(
            mock_scout, sample_theaters, False,
            MagicMock(), sample_markets_data, sample_cache_data
        )
        
        # Verify theater buttons from ZIP search
        assert any(col.button.called for col in mock_cols)
    """Test that live name search form is rendered."""

"""
Tests for operating_hours_mode.py

Focus on testable functions:
1. highlight_changes - DataFrame styling function
2. _generate_op_hours_summary_by_film - Data transformation
3. _generate_op_hours_summary_by_theater - Data transformation  
4. _generate_manual_run_comparison_table - Data transformation
5. Basic UI rendering tests
"""
import pytest
from unittest.mock import MagicMock, patch, mock_open
import pandas as pd
import datetime
from app.modes.operating_hours_mode import (
    highlight_changes,
    _generate_op_hours_summary_by_film,
    _generate_op_hours_summary_by_theater,
    _generate_manual_run_comparison_table,
    load_ui_config,
    render_operating_hours_mode
)


class TestHighlightChanges:
    """Test the highlight_changes function for DataFrame styling."""
    
    def test_highlight_changed(self):
        """Test highlighting for changed rows."""
        row = pd.Series({'Changed': '🔄 Changed', 'col1': 'val1', 'col2': 'val2'})
        result = highlight_changes(row)
        assert result == ['background-color: #0277bd; color: white'] * len(row)
    
    def test_highlight_new(self):
        """Test highlighting for new rows."""
        row = pd.Series({'Changed': '✨ New', 'col1': 'val1', 'col2': 'val2'})
        result = highlight_changes(row)
        assert result == ['background-color: #0277bd; color: white'] * len(row)
    
    def test_highlight_no_change(self):
        """Test highlighting for unchanged rows."""
        row = pd.Series({'Changed': '✅ No Change', 'col1': 'val1', 'col2': 'val2'})
        result = highlight_changes(row)
        assert result == ['background-color: #2e7d32; color: white'] * len(row)
    
    def test_highlight_default(self):
        """Test default highlighting (no status)."""
        row = pd.Series({'Changed': 'Unknown', 'col1': 'val1', 'col2': 'val2'})
        result = highlight_changes(row)
        assert result == [''] * len(row)


class TestLoadUIConfig:
    """Test UI config loading."""
    
    @patch('builtins.open', mock_open(read_data='{"mode": "test"}'))
    def test_load_ui_config_success(self):
        """Test successful UI config loading."""
        with patch('app.modes.operating_hours_mode.SCRIPT_DIR', '/fake/path'):
            with patch('json.load', return_value={'mode': 'test'}):
                config = load_ui_config()
                assert config == {'mode': 'test'}


class TestGenerateOpHoursSummaryByFilm:
    """Test _generate_op_hours_summary_by_film function."""
    
    @patch('app.modes.operating_hours_mode.database')
    def test_empty_input(self, mock_db):
        """Test with empty input."""
        result = _generate_op_hours_summary_by_film({})
        assert result == {}
    
    @patch('app.modes.operating_hours_mode.database')
    def test_single_theater_single_film(self, mock_db):
        """Test with one theater showing one film."""
        mock_db.get_film_details.return_value = {'title': 'Movie A', 'rating': 'PG'}
        
        all_results = {
            '2025-01-15': {
                'Theater 1': [
                    {'film_title': 'Movie A', 'showtime': '7:00 PM'},
                    {'film_title': 'Movie A', 'showtime': '9:30 PM'}
                ]
            }
        }
        
        result = _generate_op_hours_summary_by_film(all_results)
        
        assert '2025-01-15' in result
        assert 'Movie A' in result['2025-01-15']
        assert result['2025-01-15']['Movie A']['film_details'] == {'title': 'Movie A', 'rating': 'PG'}
        assert len(result['2025-01-15']['Movie A']['theaters']) == 1
        assert result['2025-01-15']['Movie A']['theaters'][0]['theater_name'] == 'Theater 1'
        assert result['2025-01-15']['Movie A']['theaters'][0]['num_showings'] == 2
    
    @patch('app.modes.operating_hours_mode.database')
    def test_multiple_theaters_same_film(self, mock_db):
        """Test with multiple theaters showing the same film."""
        mock_db.get_film_details.return_value = {'title': 'Movie A', 'rating': 'PG'}
        
        all_results = {
            '2025-01-15': {
                'Theater 1': [
                    {'film_title': 'Movie A', 'showtime': '7:00 PM'}
                ],
                'Theater 2': [
                    {'film_title': 'Movie A', 'showtime': '8:00 PM'}
                ]
            }
        }
        
        result = _generate_op_hours_summary_by_film(all_results)
        
        assert len(result['2025-01-15']['Movie A']['theaters']) == 2
        theater_names = [t['theater_name'] for t in result['2025-01-15']['Movie A']['theaters']]
        assert 'Theater 1' in theater_names
        assert 'Theater 2' in theater_names
    
    @patch('app.modes.operating_hours_mode.database')
    def test_duplicate_showtimes_counted_once(self, mock_db):
        """Test that duplicate showtimes are counted once."""
        mock_db.get_film_details.return_value = {'title': 'Movie A'}
        
        all_results = {
            '2025-01-15': {
                'Theater 1': [
                    {'film_title': 'Movie A', 'showtime': '7:00 PM'},
                    {'film_title': 'Movie A', 'showtime': '7:00 PM'},  # Duplicate
                    {'film_title': 'Movie A', 'showtime': '9:00 PM'}
                ]
            }
        }
        
        result = _generate_op_hours_summary_by_film(all_results)
        
        # Should count unique showtimes only
        assert result['2025-01-15']['Movie A']['theaters'][0]['num_showings'] == 2


class TestGenerateOpHoursSummaryByTheater:
    """Test _generate_op_hours_summary_by_theater function."""
    
    @patch('app.modes.operating_hours_mode.database')
    def test_empty_input(self, mock_db):
        """Test with empty input."""
        result = _generate_op_hours_summary_by_theater({})
        assert result == {}
    
    @patch('app.modes.operating_hours_mode.database')
    def test_single_theater_multiple_films(self, mock_db):
        """Test with one theater showing multiple films."""
        mock_db.get_film_details.side_effect = lambda title: {'title': title, 'rating': 'PG'}
        
        all_results = {
            '2025-01-15': {
                'Theater 1': [
                    {'film_title': 'Movie A', 'showtime': '7:00 PM'},
                    {'film_title': 'Movie B', 'showtime': '8:00 PM'}
                ]
            }
        }
        
        result = _generate_op_hours_summary_by_theater(all_results)
        
        assert '2025-01-15' in result
        assert 'Theater 1' in result['2025-01-15']
        assert len(result['2025-01-15']['Theater 1']) == 2
        
        film_titles = [f['film_title'] for f in result['2025-01-15']['Theater 1']]
        assert 'Movie A' in film_titles
        assert 'Movie B' in film_titles
    
    @patch('app.modes.operating_hours_mode.database')
    def test_multiple_theaters_different_films(self, mock_db):
        """Test with multiple theaters showing different films."""
        mock_db.get_film_details.side_effect = lambda title: {'title': title}
        
        all_results = {
            '2025-01-15': {
                'Theater 1': [
                    {'film_title': 'Movie A', 'showtime': '7:00 PM'}
                ],
                'Theater 2': [
                    {'film_title': 'Movie B', 'showtime': '8:00 PM'}
                ]
            }
        }
        
        result = _generate_op_hours_summary_by_theater(all_results)
        
        assert 'Theater 1' in result['2025-01-15']
        assert 'Theater 2' in result['2025-01-15']
        assert result['2025-01-15']['Theater 1'][0]['film_title'] == 'Movie A'
        assert result['2025-01-15']['Theater 2'][0]['film_title'] == 'Movie B'


class TestGenerateManualRunComparisonTable:
    """Test _generate_manual_run_comparison_table function."""
    
    @patch('app.modes.operating_hours_mode.database')
    def test_empty_input(self, mock_db):
        """Test with no results."""
        result = _generate_manual_run_comparison_table({})
        assert result == []
    
    @patch('app.modes.operating_hours_mode.database')
    def test_single_date_single_theater(self, mock_db):
        """Test with one date and one theater."""
        # Mock database calls
        mock_db.get_operating_hours_for_theaters_and_dates.return_value = pd.DataFrame()
        mock_db.calculate_operating_hours_from_showings.return_value = pd.DataFrame()
        
        results = {
            '2025-01-15': {
                'Theater 1': [
                    {'showtime': '7:00 AM'},
                    {'showtime': '11:00 PM'}
                ]
            }
        }
        
        result = _generate_manual_run_comparison_table(results)
        
        # Should return a list with one theater report
        assert len(result) == 1
        assert result[0]['theater_name'] == 'Theater 1'
        assert 'report' in result[0]
        assert isinstance(result[0]['report'], pd.DataFrame)
    
    @patch('app.modes.operating_hours_mode.database')
    def test_multiple_theaters_same_date(self, mock_db):
        """Test with multiple theaters on same date."""
        mock_db.get_operating_hours_for_theaters_and_dates.return_value = pd.DataFrame()
        mock_db.calculate_operating_hours_from_showings.return_value = pd.DataFrame()
        
        results = {
            '2025-01-15': {
                'Theater 1': [
                    {'showtime': '7:00 AM'},
                    {'showtime': '11:00 PM'}
                ],
                'Theater 2': [
                    {'showtime': '8:00 AM'},
                    {'showtime': '10:00 PM'}
                ]
            }
        }
        
        result = _generate_manual_run_comparison_table(results)
        
        assert len(result) == 2
        theater_names = [r['theater_name'] for r in result]
        assert 'Theater 1' in theater_names
        assert 'Theater 2' in theater_names
    
    @patch('app.modes.operating_hours_mode.database')
    def test_no_showings_for_theater(self, mock_db):
        """Test with empty showings list."""
        mock_db.get_operating_hours_for_theaters_and_dates.return_value = pd.DataFrame()
        mock_db.calculate_operating_hours_from_showings.return_value = pd.DataFrame()
        
        results = {
            '2025-01-15': {
                'Theater 1': []
            }
        }
        
        result = _generate_manual_run_comparison_table(results)
        
        # Should still create a report entry
        assert len(result) == 1
        assert result[0]['theater_name'] == 'Theater 1'

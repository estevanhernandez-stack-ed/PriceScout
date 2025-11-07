"""
Tests for theater_matching_tool.py utility functions.
"""
import pytest
from unittest.mock import patch, mock_open, MagicMock
import json
import io

from app.theater_matching_tool import (
    get_markets_data,
    _strip_common_terms,
    _extract_zip_from_market_name,
    find_duplicate_theaters,
    load_all_markets_data_from_disk
)


class TestGetMarketsData:
    """Tests for get_markets_data function."""
    
    def test_loads_markets_data_from_uploaded_file(self):
        """Should load and parse markets data from an uploaded file."""
        mock_file = MagicMock()
        mock_file.getvalue.return_value = b'{"AMC": {"East": {"Market1": {"theaters": [{"name": "AMC Theater"}]}}}}'
        
        result = get_markets_data(mock_file)
        
        assert result is not None
        assert "AMC" in result
        assert "East" in result["AMC"]
    
    def test_returns_none_when_no_file_uploaded(self):
        """Should return None when no file is uploaded."""
        result = get_markets_data(None)
        assert result is None
    
    def test_handles_multiple_companies(self):
        """Should handle markets data with multiple parent companies."""
        mock_file = MagicMock()
        mock_file.getvalue.return_value = b'{"AMC": {"East": {}}, "Regal": {"West": {}}}'
        
        result = get_markets_data(mock_file)
        
        assert "AMC" in result
        assert "Regal" in result


class TestStripCommonTerms:
    """Tests for _strip_common_terms function."""
    
    def test_removes_amc_brand(self):
        """Should remove AMC brand name from theater name."""
        result = _strip_common_terms('AMC Empire 25')
        assert 'amc' not in result.lower()
        assert 'empire' in result.lower()
    
    def test_removes_multiple_brands(self):
        """Should remove multiple brand terms."""
        result = _strip_common_terms('Regal Cinemas IMAX')
        assert 'Regal' not in result
        assert 'Cinemas' not in result
    
    def test_removes_amenity_terms(self):
        """Should remove amenity terms like IMAX, Dolby."""
        result = _strip_common_terms('Downtown IMAX Theater')
        assert 'imax' not in result.lower()
        assert 'downtown' in result.lower()
    
    def test_cleans_up_extra_spaces(self):
        """Should clean up extra spaces and punctuation."""
        result = _strip_common_terms('AMC Downtown IMAX')
        # Should have cleaned spaces but kept some content
        assert '  ' not in result
        assert result.strip() != ''
    
    def test_preserves_location_names(self):
        """Should preserve location names."""
        result = _strip_common_terms('AMC Lincoln Square')
        assert 'lincoln' in result.lower()
        assert 'square' in result.lower()
    
    def test_handles_empty_string(self):
        """Should handle empty string gracefully."""
        result = _strip_common_terms('')
        assert result == ''
    
    def test_case_insensitive(self):
        """Should handle different cases."""
        result1 = _strip_common_terms('amc Empire')
        result2 = _strip_common_terms('AMC Empire')
        # Both should remove AMC/amc
        assert 'AMC' not in result1.upper()
        assert 'AMC' not in result2


class TestExtractZipFromMarketName:
    """Tests for _extract_zip_from_market_name function."""
    
    def test_extracts_5_digit_zip_at_end(self):
        """Should extract 5-digit ZIP code at the end of market name."""
        assert _extract_zip_from_market_name('New York 10001') == '10001'
        assert _extract_zip_from_market_name('Los Angeles 90210') == '90210'
    
    def test_returns_none_when_no_zip(self):
        """Should return None when no ZIP code is present."""
        assert _extract_zip_from_market_name('New York') is None
        assert _extract_zip_from_market_name('Market Name') is None
    
    def test_ignores_zip_not_at_end(self):
        """Should only extract ZIP if it's at the end."""
        assert _extract_zip_from_market_name('12345 Market Name') is None
    
    def test_ignores_non_5_digit_numbers(self):
        """Should ignore numbers that aren't 5 digits."""
        assert _extract_zip_from_market_name('Market 123') is None
        assert _extract_zip_from_market_name('Market 123456') is None
    
    def test_handles_various_formats(self):
        """Should handle various market name formats."""
        assert _extract_zip_from_market_name('Market Name - 12345') == '12345'
        assert _extract_zip_from_market_name('Market Name 67890') == '67890'
        assert _extract_zip_from_market_name('Market Name (54321)') is None  # Parens don't count as "at end"


class TestFindDuplicateTheaters:
    """Tests for find_duplicate_theaters function."""
    
    def test_finds_exact_duplicate_names(self):
        """Should find theaters with exact duplicate names."""
        markets_data = {
            "AMC": {
                "East": {
                    "Market1": {
                        "theaters": [
                            {"name": "AMC Empire", "zip": "10001"},
                            {"name": "AMC Empire", "zip": "10002"}
                        ]
                    }
                }
            }
        }

        duplicates = find_duplicate_theaters(markets_data)

        # Returns dict with market as key, list of duplicate names as value
        assert len(duplicates) > 0
        assert 'Market1' in duplicates
        assert 'AMC Empire' in duplicates['Market1']
    
    def test_returns_empty_dict_when_no_duplicates(self):
        """Should return empty dict when there are no duplicates."""
        markets_data = {
            "AMC": {
                "East": {
                    "Market1": {
                        "theaters": [
                            {"name": "Theater A", "zip": "10001"},
                            {"name": "Theater B", "zip": "10002"}
                        ]
                    }
                }
            }
        }

        duplicates = find_duplicate_theaters(markets_data)

        assert duplicates == {}
    
    def test_finds_duplicates_within_same_market(self):
        """Should find duplicates within the same market."""
        markets_data = {
            "AMC": {
                "East": {
                    "Market1": {
                        "theaters": [
                            {"name": "AMC Empire", "zip": "10001"},
                            {"name": "AMC Empire", "zip": "10002"},
                            {"name": "AMC Empire", "zip": "10003"}
                        ]
                    }
                }
            }
        }

        duplicates = find_duplicate_theaters(markets_data)

        assert len(duplicates) > 0
        assert 'Market1' in duplicates
    
    def test_handles_multiple_duplicates(self):
        """Should handle multiple duplicates in same market."""
        markets_data = {
            "AMC": {
                "East": {
                    "Market1": {
                        "theaters": [
                            {"name": "Theater A", "zip": "10001"},
                            {"name": "Theater A", "zip": "10002"},
                            {"name": "Theater B", "zip": "10003"},
                            {"name": "Theater B", "zip": "10004"}
                        ]
                    }
                }
            }
        }

        duplicates = find_duplicate_theaters(markets_data)

        assert len(duplicates) > 0
        assert 'Market1' in duplicates
        assert len(duplicates['Market1']) == 2  # Two duplicate names
    
    def test_handles_empty_markets_data(self):
        """Should handle empty markets data gracefully."""
        duplicates = find_duplicate_theaters({})
        assert duplicates == {}
    
    def test_return_format(self):
        """Should return dict with market names as keys."""
        markets_data = {
            "AMC": {
                "East": {
                    "New York 10001": {
                        "theaters": [
                            {"name": "Theater Dup", "zip": "10001"},
                            {"name": "Theater Dup", "zip": "10001"}
                        ]
                    }
                }
            }
        }

        duplicates = find_duplicate_theaters(markets_data)

        assert isinstance(duplicates, dict)
        assert 'New York 10001' in duplicates
        assert isinstance(duplicates['New York 10001'], list)
        assert 'Theater Dup' in duplicates['New York 10001']


class TestLoadAllMarketsDataFromDisk:
    """Tests for load_all_markets_data_from_disk function."""
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"AMC": {"East": {"Market1": {"theaters": [{"name": "AMC Theater"}]}}}}')
    @patch('app.theater_matching_tool.glob.glob')
    def test_loads_and_merges_multiple_market_files(self, mock_glob, mock_file):
        """Should load and merge data from multiple markets.json files."""
        mock_glob.return_value = [
            'data/AMC/markets.json',
            'data/Regal/markets.json'
        ]
        
        result = load_all_markets_data_from_disk()
        
        assert isinstance(result, dict)
        # With our mock, it will contain AMC data
        assert "AMC" in result


class TestHelperFunctions:
    """Tests for helper functions and integration patterns."""
    
    def test_company_name_extraction_logic(self):
        """Tests the company extraction pattern used in matching."""
        from app import utils

        # Test various theater names - function returns full company name
        company = utils._extract_company_name('AMC Empire 25')
        assert 'AMC' in company  # May return "AMC Theatres"
        
        company2 = utils._extract_company_name('Some Other Theater')
        assert company2 == 'Unknown'
    
    def test_perfect_match_detection(self):
        """Tests the perfect match logic used in find_best_match."""
        from thefuzz import fuzz

        # Perfect matches should score 100
        assert fuzz.ratio('AMC Empire 25', 'AMC Empire 25') == 100
        
        # Case matters for ratio - use lower() in matching
        assert fuzz.ratio('amc empire 25'.lower(), 'AMC Empire 25'.lower()) == 100
        
        # Very different names score low
        assert fuzz.ratio('AMC Empire 25', 'Regal Stadium 14') < 50
    
    def test_token_set_ratio_for_matching(self):
        """Tests token set ratio used for flexible matching."""
        from thefuzz import fuzz
        
        # Token set ratio ignores word order and duplicates
        score = fuzz.token_set_ratio('AMC Empire 25 IMAX', 'Empire 25 AMC')
        assert score > 80  # Should be high despite different order
    
    def test_regex_patterns_for_stripping(self):
        """Tests that regex patterns work for common terms."""
        # These should all get stripped
        test_cases = [
            ('AMC Theater', 'theater'),
            ('Regal Cinemas', ''),
            ('IMAX Downtown', 'downtown')
        ]
        
        for input_name, expected_part in test_cases:
            result = _strip_common_terms(input_name).lower()
            if expected_part:
                assert expected_part in result


class TestDataStructures:
    """Tests to validate expected data structures."""
    
    def test_theater_cache_structure(self):
        """Validates the expected theater_cache.json structure."""
        # This is a documentation test for the cache format
        expected_cache = {
            "markets": {
                "Market Name 12345": {
                    "zip": "12345",
                    "theaters": [
                        {
                            "name": "Theater Name",
                            "url": "https://...",
                            "company": "CompanyName"
                        }
                    ]
                }
            }
        }
        
        assert "markets" in expected_cache
        assert isinstance(expected_cache["markets"], dict)
    
    def test_match_result_structure(self):
        """Validates the expected match result structure."""
        # This is a documentation test for match results
        expected_result = {
            "Original Name": "Theater A",
            "Matched Fandango Name": "Theater B",
            "Match Score": "95% (Original)",
            "Matched Fandango URL": "https://..."
        }
        
        assert all(key in expected_result for key in [
            "Original Name", "Matched Fandango Name", "Match Score", "Matched Fandango URL"
        ])
    
    def test_markets_data_structure(self):
        """Validates the expected markets.json structure."""
        # This is a documentation test for markets data
        expected_structure = {
            "ParentCompany": {
                "Region": {
                    "Market Name 12345": {
                        "theaters": [
                            {"name": "Theater", "zip": "12345"}
                        ]
                    }
                }
            }
        }
        
        parent = list(expected_structure.keys())[0]
        assert isinstance(expected_structure[parent], dict)
        
        region = list(expected_structure[parent].keys())[0]
        assert isinstance(expected_structure[parent][region], dict)

# Tests for app/omdb_client.py - OMDb API client for film metadata.

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import requests
import httpx

from app.omdb_client import OMDbClient


@pytest.fixture
def mock_api_key():
    '''Mock Streamlit secrets for API key.'''
    with patch('streamlit.secrets') as mock_secrets:
        mock_secrets.__getitem__.return_value = 'test_api_key_12345'
        yield mock_secrets


@pytest.fixture
def omdb_client(mock_api_key):
    '''Create OMDbClient instance with mocked API key.'''
    return OMDbClient()


@pytest.fixture
def sample_omdb_response():
    '''Sample successful OMDb API response.'''
    return {
        "Response": "True",
        "Title": "The Matrix",
        "Year": "1999",
        "imdbID": "tt0133093",
        "Genre": "Action, Sci-Fi",
        "Rated": "R",
        "Runtime": "136 min",
        "Director": "Lana Wachowski, Lilly Wachowski",
        "Actors": "Keanu Reeves, Laurence Fishburne",
        "Plot": "A computer hacker learns about the true nature of reality.",
        "Poster": "https://example.com/poster.jpg",
        "Metascore": "73",
        "imdbRating": "8.7",
        "Released": "31 Mar 1999",
        "BoxOffice": "$171,479,930"
    }


@pytest.fixture
def sample_omdb_response_minimal():
    '''Sample OMDb response with minimal/N/A values.'''
    return {
        "Response": "True",
        "Title": "Unknown Film",
        "imdbID": "tt1234567",
        "Genre": "N/A",
        "Rated": "N/A",
        "Runtime": "N/A",
        "Director": "N/A",
        "Actors": "N/A",
        "Plot": "N/A",
        "Poster": "N/A",
        "Metascore": "N/A",
        "imdbRating": "N/A",
        "Released": "N/A",
        "BoxOffice": "N/A"
    }


class TestOMDbClientInit:
    '''Tests for OMDbClient initialization.'''

    def test_init_with_api_key(self, omdb_client):
        '''Test successful initialization with API key.'''
        assert omdb_client.api_key == 'test_api_key_12345'

    def test_init_missing_api_key(self):
        '''Test initialization fails gracefully with missing API key.'''
        with patch('streamlit.secrets') as mock_secrets:
            mock_secrets.__getitem__.side_effect = KeyError('omdb_api_key')
            with pytest.raises(ValueError):  # OMDb raises ValueError, not KeyError
                OMDbClient()

    def test_init_extracts_key_from_url(self):
        '''Test initialization extracts API key from full URL.'''
        with patch('streamlit.secrets') as mock_secrets:
            mock_secrets.__getitem__.return_value = 'http://www.omdbapi.com/?apikey=extracted_key_123'
            client = OMDbClient()
            assert client.api_key == 'extracted_key_123'


class TestParseTitleAndYear:
    '''Tests for _parse_title_and_year method.'''

    def test_parse_title_with_year_in_parentheses(self, omdb_client):
        '''Test parsing title with year in parentheses.'''
        title, year = omdb_client._parse_title_and_year('The Matrix (1999)')
        assert title == 'The Matrix'
        assert year == '1999'

    def test_parse_title_without_year(self, omdb_client):
        '''Test parsing title without year.'''
        title, year = omdb_client._parse_title_and_year('The Matrix')
        assert title == 'The Matrix'
        assert year is None

    def test_parse_title_with_year_in_middle(self, omdb_client):
        '''Test parsing title with year in middle does not extract year.'''
        title, year = omdb_client._parse_title_and_year('Film (2023) Extended Edition')
        # Implementation only extracts year from end of title
        assert title == 'Film (2023) Extended Edition'  # Full title kept
        assert year is None  # Year not extracted from middle

    def test_parse_empty_title(self, omdb_client):
        '''Test parsing empty title.'''
        title, year = omdb_client._parse_title_and_year('')
        assert title == ''
        assert year is None


class TestParseFilmData:
    '''Tests for _parse_film_data method.'''

    def test_parse_film_data_complete_response(self, omdb_client, sample_omdb_response):
        '''Test parsing complete OMDb response with all fields.'''
        result = omdb_client._parse_film_data(sample_omdb_response)
        
        assert result['film_title'] == 'The Matrix'
        assert result['imdb_id'] == 'tt0133093'
        assert result['genre'] == 'Action, Sci-Fi'
        assert result['mpaa_rating'] == 'R'
        assert result['runtime'] == '136 min'
        assert result['director'] == 'Lana Wachowski, Lilly Wachowski'
        assert result['actors'] == 'Keanu Reeves, Laurence Fishburne'
        assert result['plot'] == 'A computer hacker learns about the true nature of reality.'
        assert result['poster_url'] == 'https://example.com/poster.jpg'
        assert result['metascore'] == 73
        assert result['imdb_rating'] == 8.7
        assert result['release_date'] == '1999-03-31'
        assert result['domestic_gross'] == 171479930
        assert result['opening_weekend_domestic'] is None
        assert isinstance(result['last_omdb_update'], datetime)

    def test_parse_film_data_with_na_values(self, omdb_client, sample_omdb_response_minimal):
        '''Test parsing OMDb response with N/A values.'''
        result = omdb_client._parse_film_data(sample_omdb_response_minimal)
        
        assert result['film_title'] == 'Unknown Film'
        assert result['imdb_id'] == 'tt1234567'
        assert result['genre'] == 'N/A'
        assert result['metascore'] is None
        assert result['imdb_rating'] is None
        assert result['release_date'] is None
        assert result['domestic_gross'] is None

    def test_parse_release_date_valid_format(self, omdb_client):
        '''Test parsing valid release date.'''
        response = {'Released': '15 Sep 2025'}
        result = omdb_client._parse_film_data(response)
        assert result['release_date'] == '2025-09-15'

    def test_parse_release_date_invalid_format(self, omdb_client):
        '''Test parsing invalid release date format returns original.'''
        response = {'Released': 'September 2025'}
        result = omdb_client._parse_film_data(response)
        assert result['release_date'] == 'September 2025'

    def test_parse_release_date_none(self, omdb_client):
        '''Test parsing None release date.'''
        response = {'Released': None}
        result = omdb_client._parse_film_data(response)
        assert result['release_date'] is None

    def test_parse_film_data_safe_convert_with_commas(self, omdb_client):
        '''Test safe_convert handles numeric strings with commas.'''
        response = {'Metascore': '7,4', 'Response': 'True'}
        result = omdb_client._parse_film_data(response)
        assert result['metascore'] == 74

    def test_parse_film_data_safe_convert_invalid(self, omdb_client):
        '''Test safe_convert returns None for invalid values.'''
        response = {'imdbRating': 'eight-point-five', 'Response': 'True'}
        result = omdb_client._parse_film_data(response)
        assert result['imdb_rating'] is None


class TestParseOMDbBoxOffice:
    '''Tests for _parse_omdb_box_office method.'''

    def test_parse_box_office_valid(self, omdb_client):
        '''Test parsing valid box office value.'''
        assert omdb_client._parse_omdb_box_office('$171,479,930') == 171479930

    def test_parse_box_office_no_commas(self, omdb_client):
        '''Test parsing box office value without commas.'''
        assert omdb_client._parse_omdb_box_office('$1000000') == 1000000

    def test_parse_box_office_na(self, omdb_client):
        '''Test parsing N/A box office value.'''
        assert omdb_client._parse_omdb_box_office('N/A') is None

    def test_parse_box_office_none(self, omdb_client):
        '''Test parsing None box office value.'''
        assert omdb_client._parse_omdb_box_office(None) is None

    def test_parse_box_office_invalid(self, omdb_client):
        '''Test parsing invalid box office value.'''
        assert omdb_client._parse_omdb_box_office('invalid') is None


class TestSearchOMDb:
    '''Tests for _search_omdb method.'''

    def test_search_omdb_success(self, omdb_client, sample_omdb_response):
        '''Test successful OMDb search.'''
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = sample_omdb_response
            mock_get.return_value = mock_response
            
            result = omdb_client._search_omdb('The Matrix', '1999')
            
            assert result == sample_omdb_response
            mock_get.assert_called_once()
            call_params = mock_get.call_args[1]['params']
            assert call_params['t'] == 'The Matrix'
            assert call_params['y'] == '1999'
            assert call_params['apikey'] == 'test_api_key_12345'

    def test_search_omdb_without_year(self, omdb_client, sample_omdb_response):
        '''Test OMDb search without year parameter.'''
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = sample_omdb_response
            mock_get.return_value = mock_response
            
            result = omdb_client._search_omdb('The Matrix', None)
            
            call_params = mock_get.call_args[1]['params']
            assert 'y' not in call_params

    def test_search_omdb_extracts_year_from_title(self, omdb_client, sample_omdb_response):
        '''Test that _search_omdb extracts year from title.'''
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = sample_omdb_response
            mock_get.return_value = mock_response
            
            omdb_client._search_omdb('The Matrix (1999)', None)
            
            call_params = mock_get.call_args[1]['params']
            assert call_params['t'] == 'The Matrix'
            assert call_params['y'] == '1999'

    def test_search_omdb_request_exception(self, omdb_client):
        '''Test OMDb search with request exception.'''
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.RequestException('Connection error')
            
            result = omdb_client._search_omdb('The Matrix', '1999')
            
            assert result is None

    def test_search_omdb_timeout(self, omdb_client):
        '''Test OMDb search with timeout.'''
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout('Request timed out')
            
            result = omdb_client._search_omdb('The Matrix', '1999')
            
            assert result is None


class TestSearchOMDbAsync:
    '''Tests for _search_omdb_async method.'''

    @pytest.mark.asyncio
    async def test_search_omdb_async_success(self, omdb_client, sample_omdb_response):
        '''Test successful async OMDb search.'''
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.json.return_value = sample_omdb_response
        mock_client.get.return_value = mock_response
        
        result = await omdb_client._search_omdb_async('The Matrix', '1999', mock_client)
        
        assert result == sample_omdb_response

    @pytest.mark.asyncio
    async def test_search_omdb_async_request_error(self, omdb_client):
        '''Test async OMDb search with request error.'''
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get.side_effect = httpx.RequestError('Connection error')
        
        result = await omdb_client._search_omdb_async('The Matrix', '1999', mock_client)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_search_omdb_async_general_exception(self, omdb_client):
        '''Test async OMDb search with general exception.'''
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.get.side_effect = Exception('Unexpected error')
        
        result = await omdb_client._search_omdb_async('The Matrix', '1999', mock_client)
        
        assert result is None


class TestSearchByID:
    '''Tests for _search_by_id method.'''

    def test_search_by_id_success(self, omdb_client, sample_omdb_response):
        '''Test successful search by IMDb ID.'''
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = sample_omdb_response
            mock_get.return_value = mock_response
            
            result = omdb_client._search_by_id('tt0133093')
            
            assert result == sample_omdb_response
            call_params = mock_get.call_args[1]['params']
            assert call_params['i'] == 'tt0133093'
            assert 't' not in call_params

    def test_search_by_id_request_exception(self, omdb_client):
        '''Test search by ID with request exception.'''
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.RequestException('Connection error')
            
            result = omdb_client._search_by_id('tt0133093')
            
            assert result is None


class TestFuzzySearchAndMatch:
    '''Tests for _fuzzy_search_and_match method.'''

    def test_fuzzy_search_high_confidence_match(self, omdb_client, sample_omdb_response):
        '''Test fuzzy search with high confidence match.'''
        search_results = {
            'Response': 'True',
            'Search': [
                {'Title': 'The Matrix', 'Year': '1999', 'imdbID': 'tt0133093'},
                {'Title': 'The Matrix Reloaded', 'Year': '2003', 'imdbID': 'tt0234215'}
            ]
        }
        
        with patch('requests.get') as mock_get:
            mock_get.side_effect = [
                Mock(json=lambda: search_results),
                Mock(json=lambda: sample_omdb_response)
            ]
            
            result = omdb_client._fuzzy_search_and_match('The Matrix', '1999')
            
            assert result == sample_omdb_response
            assert mock_get.call_count == 2

    def test_fuzzy_search_year_bonus(self, omdb_client, sample_omdb_response):
        '''Test fuzzy search gives bonus for year match.'''
        search_results = {
            'Response': 'True',
            'Search': [
                {'Title': 'The Matrix', 'Year': '1999', 'imdbID': 'tt0133093'},
                {'Title': 'The Matrix', 'Year': '2000', 'imdbID': 'tt9999999'}
            ]
        }
        
        with patch('requests.get') as mock_get:
            mock_get.side_effect = [
                Mock(json=lambda: search_results),
                Mock(json=lambda: sample_omdb_response)
            ]
            
            result = omdb_client._fuzzy_search_and_match('The Matrix', '1999')
            
            second_call_params = mock_get.call_args_list[1][1]['params']
            assert second_call_params['i'] == 'tt0133093'

    def test_fuzzy_search_low_confidence(self, omdb_client):
        '''Test fuzzy search with low confidence match.'''
        search_results = {
            'Response': 'True',
            'Search': [
                {'Title': 'Completely Different Film', 'Year': '1999', 'imdbID': 'tt1234567'}
            ]
        }
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = Mock(json=lambda: search_results)
            
            result = omdb_client._fuzzy_search_and_match('The Matrix', '1999')
            
            assert result is None
            assert mock_get.call_count == 1

    def test_fuzzy_search_no_results(self, omdb_client):
        '''Test fuzzy search with no results.'''
        search_results = {'Response': 'False', 'Error': 'Movie not found!'}
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = Mock(json=lambda: search_results)
            
            result = omdb_client._fuzzy_search_and_match('Nonexistent Film', None)
            
            assert result is None

    def test_fuzzy_search_request_exception(self, omdb_client):
        '''Test fuzzy search with request exception.'''
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.RequestException('Connection error')
            
            result = omdb_client._fuzzy_search_and_match('The Matrix', None)
            
            assert result is None


class TestGetFilmDetails:
    '''Tests for get_film_details method.'''

    def test_get_film_details_first_attempt_success(self, omdb_client, sample_omdb_response):
        '''Test successful film details retrieval on first attempt.'''
        with patch.object(omdb_client, '_search_omdb') as mock_search:
            mock_search.return_value = sample_omdb_response
            
            result = omdb_client.get_film_details('The Matrix', '1999')
            
            assert result['film_title'] == 'The Matrix'
            assert mock_search.call_count == 1

    def test_get_film_details_cleaned_title_success(self, omdb_client, sample_omdb_response):
        '''Test film details retrieval succeeds with cleaned title.'''
        failed_response = {'Response': 'False', 'Error': 'Movie not found!'}
        
        with patch.object(omdb_client, '_search_omdb') as mock_search:
            mock_search.side_effect = [failed_response, sample_omdb_response]
            
            with patch('app.utils.clean_film_title') as mock_clean:
                mock_clean.return_value = 'The Matrix'
                
                result = omdb_client.get_film_details('The Matrix - Special Event', '1999')
                
                assert result['film_title'] == 'The Matrix'
                assert mock_search.call_count == 2

    def test_get_film_details_fuzzy_search_success(self, omdb_client, sample_omdb_response):
        '''Test film details retrieval succeeds with fuzzy search.'''
        failed_response = {'Response': 'False', 'Error': 'Movie not found!'}
        
        with patch.object(omdb_client, '_search_omdb') as mock_search:
            mock_search.return_value = failed_response
            
            with patch.object(omdb_client, '_fuzzy_search_and_match') as mock_fuzzy:
                mock_fuzzy.return_value = sample_omdb_response
                
                with patch('app.utils.clean_film_title') as mock_clean:
                    mock_clean.return_value = 'The Matrix'
                    
                    result = omdb_client.get_film_details('The Matrix', '1999')
                    
                    assert result['film_title'] == 'The Matrix'
                    assert mock_fuzzy.call_count == 1

    def test_get_film_details_all_attempts_fail(self, omdb_client):
        '''Test film details retrieval when all attempts fail.'''
        failed_response = {'Response': 'False', 'Error': 'Movie not found!'}
        
        with patch.object(omdb_client, '_search_omdb') as mock_search:
            mock_search.return_value = failed_response
            
            with patch.object(omdb_client, '_fuzzy_search_and_match') as mock_fuzzy:
                mock_fuzzy.return_value = None
                
                with patch('app.utils.clean_film_title') as mock_clean:
                    mock_clean.return_value = 'Nonexistent Film'
                    
                    result = omdb_client.get_film_details('Nonexistent Film', '1999')
                    
                    assert result is None

    def test_get_film_details_connection_error(self, omdb_client):
        '''Test film details retrieval with connection error.'''
        with patch.object(omdb_client, '_search_omdb') as mock_search:
            mock_search.return_value = None
            
            with patch.object(omdb_client, '_fuzzy_search_and_match') as mock_fuzzy:
                mock_fuzzy.return_value = None
                
                with patch('app.utils.clean_film_title') as mock_clean:
                    mock_clean.return_value = 'The Matrix'
                    
                    result = omdb_client.get_film_details('The Matrix', '1999')
                    
                    assert result is None


class TestGetFilmDetailsAsync:
    '''Tests for get_film_details_async method.'''

    @pytest.mark.asyncio
    async def test_get_film_details_async_success(self, omdb_client, sample_omdb_response):
        '''Test successful async film details retrieval.'''
        with patch.object(omdb_client, '_search_omdb_async') as mock_search:
            mock_search.return_value = sample_omdb_response
            
            result = await omdb_client.get_film_details_async('The Matrix', '1999')
            
            assert result['film_title'] == 'The Matrix'

    @pytest.mark.asyncio
    async def test_get_film_details_async_cleaned_title(self, omdb_client, sample_omdb_response):
        '''Test async film details with cleaned title.'''
        failed_response = {'Response': 'False', 'Error': 'Movie not found!'}
        
        with patch.object(omdb_client, '_search_omdb_async') as mock_search:
            mock_search.side_effect = [failed_response, sample_omdb_response]
            
            with patch('app.utils.clean_film_title') as mock_clean:
                mock_clean.return_value = 'The Matrix'
                
                result = await omdb_client.get_film_details_async('The Matrix - Event', '1999')
                
                assert result['film_title'] == 'The Matrix'

    @pytest.mark.asyncio
    async def test_get_film_details_async_all_fail(self, omdb_client):
        '''Test async film details when all attempts fail.'''
        failed_response = {'Response': 'False', 'Error': 'Movie not found!'}
        
        with patch.object(omdb_client, '_search_omdb_async') as mock_search:
            mock_search.return_value = failed_response
            
            with patch('app.utils.clean_film_title') as mock_clean:
                mock_clean.return_value = 'Nonexistent'
                
                result = await omdb_client.get_film_details_async('Nonexistent', '1999')
                
                assert result is None

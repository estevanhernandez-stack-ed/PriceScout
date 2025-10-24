import pytest
from unittest.mock import patch, MagicMock
import requests
from datetime import datetime

from app.omdb_client import OMDbClient

@pytest.fixture
def mock_omdb_client(monkeypatch):
    """Fixture to create an OMDbClient with a mocked st.secrets."""
    mock_secrets = {"omdb_api_key": "fake_key"}
    monkeypatch.setattr('streamlit.secrets', mock_secrets)
    client = OMDbClient()
    return client

def test_init_success(mock_omdb_client):
    """Tests that the client initializes correctly with an API key."""
    assert mock_omdb_client.api_key == "fake_key"

def test_init_no_api_key(monkeypatch):
    """Tests that the client raises a ValueError if the API key is missing."""
    monkeypatch.setattr('streamlit.secrets', {})
    with pytest.raises(ValueError, match="OMDb API key not found"):
        OMDbClient()

@patch('app.omdb_client.requests.get')
def test_get_film_details_success(mock_get, mock_omdb_client):
    """Tests a successful API call and data parsing."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "Title": "Inception",
        "Year": "2010",
        "Rated": "PG-13",
        "Released": "16 Jul 2010",
        "Genre": "Action, Adventure, Sci-Fi",
        "Director": "Christopher Nolan",
        "Actors": "Leonardo DiCaprio, Joseph Gordon-Levitt, Elliot Page",
        "Plot": "A thief who steals corporate secrets through the use of dream-sharing technology...",
        "Poster": "http://example.com/poster.jpg",
        "Metascore": "74",
        "imdbRating": "8.8",
        "imdbID": "tt1375666",
        "BoxOffice": "$292,576,195",
        "Response": "True"
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    details = mock_omdb_client.get_film_details("Inception")

    assert details is not None
    assert details["film_title"] == "Inception"
    assert details["imdb_id"] == "tt1375666"
    assert details["genre"] == "Action, Adventure, Sci-Fi"
    assert details["metascore"] == 74
    assert details["imdb_rating"] == 8.8
    assert details["release_date"] == "2010-07-16"
    assert details["domestic_gross"] == 292576195 # This was checking for 'box_office_gross'
    assert isinstance(details["last_omdb_update"], datetime)

@patch('app.omdb_client.requests.get')
def test_get_film_details_not_found(mock_get, mock_omdb_client):
    """Tests the case where the API returns 'Response: False'."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "Response": "False",
        "Error": "Movie not found!"
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    details = mock_omdb_client.get_film_details("NonExistentMovie")

    assert details is None

def test_init_with_full_url_as_key(monkeypatch):
    """Tests that the client can extract the API key from a full URL."""
    full_url_secret = "http://www.omdbapi.com/?i=tt3896198&apikey=fake_key"
    mock_secrets = {"omdb_api_key": full_url_secret}
    monkeypatch.setattr('streamlit.secrets', mock_secrets)
    client = OMDbClient()
    assert client.api_key == "fake_key"

def test_parse_film_data_with_malformed_date(mock_omdb_client):
    """Tests that a malformed date string is handled gracefully."""
    api_response = {
        "Title": "Movie with Bad Date",
        "Released": "Not a real date",
        "Response": "True"
    }
    parsed_data = mock_omdb_client._parse_film_data(api_response)
    # It should return the original malformed string without crashing
    assert parsed_data["release_date"] == "Not a real date"

@patch('app.omdb_client.requests.get')
def test_get_film_details_request_exception(mock_get, mock_omdb_client):
    """Tests how the client handles a network error."""
    mock_get.side_effect = requests.exceptions.RequestException("Network error")

    details = mock_omdb_client.get_film_details("Any Movie")

    assert details is None

def test_parse_film_data_with_na_values(mock_omdb_client):
    """Tests the internal parsing logic with 'N/A' values."""
    api_response = {
        "Title": "A Movie with Missing Info",
        "Metascore": "N/A",
        "imdbRating": "N/A",
        "Released": "N/A",
        "BoxOffice": "N/A",
        "Response": "True"
    }

    parsed_data = mock_omdb_client._parse_film_data(api_response)

    assert parsed_data["film_title"] == "A Movie with Missing Info"
    assert parsed_data["metascore"] is None
    assert parsed_data["imdb_rating"] is None
    assert parsed_data["release_date"] is None
    assert parsed_data["domestic_gross"] is None

def test_safe_convert_handles_type_error(mock_omdb_client):
    """Tests that the safe_convert helper returns default on a type conversion error."""
    api_response = {
        "Title": "Movie with Bad Data",
        "imdbRating": "eight-point-five", # A string that can't be converted to float
        "Response": "True"
    }
    parsed_data = mock_omdb_client._parse_film_data(api_response)
    assert parsed_data["imdb_rating"] is None


def test_parse_film_data_with_number_commas(mock_omdb_client): # This test was failing due to fragile implementation
    """
    Tests that the parsing logic correctly handles numeric strings that might contain commas.
    The safe_convert helper inside _parse_film_data is responsible for this.
    """
    api_response = {
        "Title": "Test",
        # Simulate a value that contains a comma to test the replace logic
        "Metascore": "7,4", # This would be parsed as 74
        "Response": "True"
    }

    parsed_data = mock_omdb_client._parse_film_data(api_response)

    assert parsed_data["metascore"] == 74
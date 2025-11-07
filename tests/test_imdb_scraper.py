import pytest
from unittest.mock import patch, MagicMock
import httpx
from bs4 import BeautifulSoup
from app.imdb_scraper import IMDbScraper


@pytest.fixture
def scraper():
    """Create an IMDbScraper instance for testing."""
    return IMDbScraper()


@pytest.fixture
def sample_imdb_html():
    """Sample IMDb calendar HTML for testing."""
    return """
    <html>
        <body>
            <h4>25 October 2025</h4>
            <ul>
                <li>The Dark Knight Returns (I) (2025)</li>
                <li>Space Odyssey: Part 2</li>
                <li>Mystery Thriller</li>
            </ul>
            <h4>01 November 2025</h4>
            <ul>
                <li>Avatar: The Next Chapter (II) (2025)</li>
                <li>Holiday Special</li>
            </ul>
            <h4>15 November 2025</h4>
            <ul>
                <li>Epic Fantasy Adventure</li>
            </ul>
        </body>
    </html>
    """


def test_imdb_scraper_initialization(scraper):
    """Test that IMDbScraper can be initialized."""
    assert scraper is not None
    assert scraper.BASE_URL == "https://www.imdb.com"


def test_discover_upcoming_releases_success(scraper, sample_imdb_html):
    """Test successful discovery of upcoming releases."""
    mock_response = MagicMock()
    mock_response.content = sample_imdb_html.encode('utf-8')
    mock_response.raise_for_status = MagicMock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        films = scraper.discover_upcoming_releases()
        
        # Should discover 6 films total
        assert len(films) == 6
        
        # Check first film
        assert films[0]['title'] == 'The Dark Knight Returns'
        assert films[0]['release_date'] == '2025-10-25'
        
        # Check that (I) (2025) suffix was removed
        assert '(I)' not in films[0]['title']
        assert '(2025)' not in films[0]['title']
        
        # Check second film (no suffix to remove)
        assert films[1]['title'] == 'Space Odyssey: Part 2'
        assert films[1]['release_date'] == '2025-10-25'
        
        # Check film from different date
        assert films[3]['title'] == 'Avatar: The Next Chapter'
        assert films[3]['release_date'] == '2025-11-01'
        
        # Verify correct URL was called
        mock_client.return_value.__enter__.return_value.get.assert_called_once_with(
            'https://www.imdb.com/calendar/'
        )


def test_discover_upcoming_releases_http_error(scraper):
    """Test handling of HTTP errors."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 Not Found", request=MagicMock(), response=MagicMock()
    )
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        films = scraper.discover_upcoming_releases()
        
        # Should return empty list on error
        assert films == []


def test_discover_upcoming_releases_network_error(scraper):
    """Test handling of network errors."""
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError(
            "Connection failed"
        )
        
        films = scraper.discover_upcoming_releases()
        
        # Should return empty list on error
        assert films == []


def test_discover_upcoming_releases_parsing_error(scraper):
    """Test handling of malformed HTML."""
    malformed_html = "<html><body><h4>Invalid Date Format</h4><ul><li>Film</li></ul></body></html>"
    
    mock_response = MagicMock()
    mock_response.content = malformed_html.encode('utf-8')
    mock_response.raise_for_status = MagicMock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        films = scraper.discover_upcoming_releases()
        
        # Should return empty list when date parsing fails
        assert films == []


def test_discover_upcoming_releases_no_date_headers(scraper):
    """Test handling of HTML with no date headers."""
    html = "<html><body><ul><li>Film without date</li></ul></body></html>"
    
    mock_response = MagicMock()
    mock_response.content = html.encode('utf-8')
    mock_response.raise_for_status = MagicMock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        films = scraper.discover_upcoming_releases()
        
        # Should return empty list
        assert films == []


def test_discover_upcoming_releases_date_header_no_films(scraper):
    """Test handling of date headers with no film list."""
    html = "<html><body><h4>25 October 2025</h4><p>No films</p></body></html>"
    
    mock_response = MagicMock()
    mock_response.content = html.encode('utf-8')
    mock_response.raise_for_status = MagicMock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        films = scraper.discover_upcoming_releases()
        
        # Should return empty list when no ul follows h4
        assert films == []


def test_discover_upcoming_releases_empty_film_list(scraper):
    """Test handling of empty film lists."""
    html = "<html><body><h4>25 October 2025</h4><ul></ul></body></html>"
    
    mock_response = MagicMock()
    mock_response.content = html.encode('utf-8')
    mock_response.raise_for_status = MagicMock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        films = scraper.discover_upcoming_releases()
        
        # Should return empty list
        assert films == []


def test_discover_upcoming_releases_mixed_valid_invalid_dates(scraper):
    """Test handling of mix of valid and invalid date headers."""
    html = """
    <html>
        <body>
            <h4>25 October 2025</h4>
            <ul><li>Valid Film</li></ul>
            <h4>Invalid Date</h4>
            <ul><li>Should be skipped</li></ul>
            <h4>01 November 2025</h4>
            <ul><li>Another Valid Film</li></ul>
        </body>
    </html>
    """
    
    mock_response = MagicMock()
    mock_response.content = html.encode('utf-8')
    mock_response.raise_for_status = MagicMock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        films = scraper.discover_upcoming_releases()
        
        # Should only return films from valid dates
        assert len(films) == 2
        assert films[0]['title'] == 'Valid Film'
        assert films[0]['release_date'] == '2025-10-25'
        assert films[1]['title'] == 'Another Valid Film'
        assert films[1]['release_date'] == '2025-11-01'


def test_discover_upcoming_releases_title_cleaning(scraper):
    """Test that film titles are properly cleaned."""
    html = """
    <html>
        <body>
            <h4>25 October 2025</h4>
            <ul>
                <li>Clean Title</li>
                <li>Title with (I) (2025)</li>
                <li>Title with (II) (2026)</li>
                <li>Title with (III) (2024)</li>
                <li>Title (No Year)</li>
            </ul>
        </body>
    </html>
    """
    
    mock_response = MagicMock()
    mock_response.content = html.encode('utf-8')
    mock_response.raise_for_status = MagicMock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        films = scraper.discover_upcoming_releases()
        
        assert len(films) == 5
        assert films[0]['title'] == 'Clean Title'
        assert films[1]['title'] == 'Title with'  # (I) (2025) removed
        assert films[2]['title'] == 'Title with'  # (II) (2026) removed
        assert films[3]['title'] == 'Title with'  # (III) (2024) removed
        assert films[4]['title'] == 'Title (No Year)'  # No change - doesn't match pattern


def test_discover_upcoming_releases_uses_correct_headers(scraper):
    """Test that the scraper sends appropriate headers."""
    mock_response = MagicMock()
    mock_response.content = b"<html></html>"
    mock_response.raise_for_status = MagicMock()
    
    with patch('httpx.Client') as mock_client:
        mock_client.return_value.__enter__.return_value.get.return_value = mock_response
        
        scraper.discover_upcoming_releases()
        
        # Verify Client was created with headers
        call_kwargs = mock_client.call_args[1]
        assert 'headers' in call_kwargs
        assert 'User-Agent' in call_kwargs['headers']
        assert 'Mozilla' in call_kwargs['headers']['User-Agent']
        assert call_kwargs['follow_redirects'] is True

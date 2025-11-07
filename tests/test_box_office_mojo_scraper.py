import pytest
from unittest.mock import patch, MagicMock
import httpx
from app.box_office_mojo_scraper import BoxOfficeMojoScraper

@pytest.fixture
def scraper():
    """Returns an instance of the BoxOfficeMojoScraper."""
    return BoxOfficeMojoScraper()

@patch('app.box_office_mojo_scraper.httpx.Client')
def test_discover_films_by_year_success(mock_client, scraper):
    """Tests successful discovery of films from a yearly release page."""
    mock_html = """
    <html><body>
        <a href="/release/rl123/"><h3>Test Film 1</h3></a>
        <a href="/release/rl456/"><h3>Test Film 2</h3></a>
    </body></html>
    """
    mock_response = MagicMock()
    mock_response.content = mock_html.encode('utf-8')
    mock_response.raise_for_status.return_value = None
    mock_client.return_value.__enter__.return_value.get.return_value = mock_response

    films = scraper.discover_films_by_year(2025)

    assert len(films) == 2
    assert films[0]['title'] == 'Test Film 1'
    assert films[0]['bom_url'] == 'https://www.boxofficemojo.com/release/rl123/'
    assert films[1]['title'] == 'Test Film 2'
    assert films[1]['bom_url'] == 'https://www.boxofficemojo.com/release/rl456/'

@patch('app.box_office_mojo_scraper.httpx.Client')
def test_discover_films_by_year_request_exception(mock_client, scraper):
    """Tests that an empty list is returned on a network error."""
    mock_client.return_value.__enter__.return_value.get.side_effect = httpx.RequestError("Network Error")
    films = scraper.discover_films_by_year(2025)
    assert films == []

@patch('app.box_office_mojo_scraper.httpx.Client')
def test_discover_films_by_year_no_table(mock_client, scraper):
    """Tests that an empty list is returned if the main table is not found."""
    mock_html = "<html><body><p>No table here.</p></body></html>"
    mock_response = MagicMock()
    mock_response.content = mock_html.encode('utf-8')
    mock_response.raise_for_status.return_value = None
    mock_client.return_value.__enter__.return_value.get.return_value = mock_response

    films = scraper.discover_films_by_year(2025)
    assert films == []

@patch('app.box_office_mojo_scraper.httpx.get')
def test_get_film_financials_success(mock_get, scraper):
    """Tests successful scraping of financial data from a film's page."""
    mock_html = """
    <html><body>
        <span>Domestic Gross</span><span>$100,000,000</span>
        <span>Opening Weekend</span><span>$25,000,000</span>
    </body></html>
    """
    mock_response = MagicMock()
    mock_response.content = mock_html.encode('utf-8')
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    financials = scraper.get_film_financials("http://example.com/film")

    assert financials['domestic_gross'] == 100000000
    assert financials['opening_weekend_domestic'] == 25000000

@patch('app.box_office_mojo_scraper.httpx.get')
def test_get_film_financials_missing_data(mock_get, scraper):
    """Tests scraping a page where some financial data is missing."""
    mock_html = """
    <html><body>
        <span>Domestic Gross</span><span>$100,000,000</span>
    </body></html>
    """
    mock_response = MagicMock()
    mock_response.content = mock_html.encode('utf-8')
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    financials = scraper.get_film_financials("http://example.com/film")

    assert financials['domestic_gross'] == 100000000
    assert financials['opening_weekend_domestic'] is None

@patch('app.box_office_mojo_scraper.httpx.get')
def test_get_film_financials_request_exception(mock_get, scraper):
    mock_get.side_effect = httpx.RequestError("Network Error")
    financials = scraper.get_film_financials("http://example.com/film")
    assert financials['opening_weekend_domestic'] is None
    assert financials['domestic_gross'] is None

def test_parse_money_valid_formats(scraper):
    """Test _parse_money with various valid money formats."""
    # Standard format with dollar sign and commas
    assert scraper._parse_money('$1,234,567') == 1234567
    
    # Without dollar sign
    assert scraper._parse_money('1,234,567') == 1234567
    
    # Small amount
    assert scraper._parse_money('$100') == 100
    
    # Large amount
    assert scraper._parse_money('$100,000,000') == 100000000
    
    # No commas
    assert scraper._parse_money('$1234567') == 1234567
    
    # Just a number
    assert scraper._parse_money('42') == 42
    
    # Zero
    assert scraper._parse_money('$0') == 0

def test_parse_money_invalid_formats(scraper):
    """Test _parse_money with invalid or edge case inputs."""
    # N/A value
    assert scraper._parse_money('N/A') is None
    
    # Empty string
    assert scraper._parse_money('') is None
    
    # None input
    assert scraper._parse_money(None) is None
    
    # Text that's not a number
    assert scraper._parse_money('Unknown') is None
    
    # Mixed invalid characters (decimal point not removed by regex)
    assert scraper._parse_money('$1,234.56') is None

@patch('app.box_office_mojo_scraper.httpx.Client')
def test_discover_film_url_success(mock_client, scraper):
    """Test successful discovery of a film URL through search."""
    mock_html = """
    <html><body>
        <a href="/title/tt1234567/">Test Film</a>
    </body></html>
    """
    mock_response = MagicMock()
    mock_response.content = mock_html.encode('utf-8')
    mock_response.raise_for_status.return_value = None
    mock_client.return_value.__enter__.return_value.get.return_value = mock_response
    
    url = scraper.discover_film_url("Test Film")
    
    assert url == "https://www.boxofficemojo.com/title/tt1234567/"

@patch('app.box_office_mojo_scraper.httpx.Client')
def test_discover_film_url_not_found(mock_client, scraper):
    """Test when film URL is not found in search results."""
    mock_html = """
    <html><body>
        <p>No results found</p>
    </body></html>
    """
    mock_response = MagicMock()
    mock_response.content = mock_html.encode('utf-8')
    mock_response.raise_for_status.return_value = None
    mock_client.return_value.__enter__.return_value.get.return_value = mock_response
    
    url = scraper.discover_film_url("Nonexistent Film")
    
    assert url is None

@patch('app.box_office_mojo_scraper.httpx.Client')
def test_discover_film_url_request_error(mock_client, scraper):
    """Test discover_film_url handling network errors."""
    mock_client.return_value.__enter__.return_value.get.side_effect = httpx.RequestError("Network Error")
    
    url = scraper.discover_film_url("Test Film")
    
    assert url is None

@patch('app.box_office_mojo_scraper.httpx.Client')
def test_discover_films_by_month_success(mock_client, scraper):
    """Test successful discovery of films for a specific month."""
    mock_html = """
    <html><body>
        <a href="/release/rl123/"><h3>January Film 1</h3></a>
        <a href="/release/rl456/"><h3>January Film 2</h3></a>
    </body></html>
    """
    mock_response = MagicMock()
    mock_response.content = mock_html.encode('utf-8')
    mock_response.raise_for_status.return_value = None
    mock_client.return_value.__enter__.return_value.get.return_value = mock_response
    
    films = scraper.discover_films_by_month(2025, 1)
    
    assert len(films) == 2
    assert films[0]['title'] == 'January Film 1'
    assert films[1]['title'] == 'January Film 2'

@patch('app.box_office_mojo_scraper.httpx.Client')
def test_discover_films_by_month_404_error(mock_client, scraper):
    """Test discover_films_by_month handling 404 errors gracefully."""
    mock_error = httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=MagicMock())
    mock_error.response.status_code = 404
    mock_client.return_value.__enter__.return_value.get.side_effect = mock_error
    
    films = scraper.discover_films_by_month(2099, 12)
    
    assert films == []

@patch('app.box_office_mojo_scraper.httpx.Client')
def test_discover_films_by_month_parse_error(mock_client, scraper):
    """Test discover_films_by_month handling parse errors."""
    mock_response = MagicMock()
    # Invalid UTF-8 to trigger parse error
    mock_response.content = b'\x80\x81'
    mock_response.raise_for_status.return_value = None
    mock_client.return_value.__enter__.return_value.get.return_value = mock_response
    
    films = scraper.discover_films_by_month(2025, 1)
    
    assert films == []

def test_discover_films_by_year_deduplication(scraper):
    """Test that discover_films_by_year removes duplicate films."""
    # Mock discover_films_by_month to return duplicates across months
    original_method = scraper.discover_films_by_month
    
    def mock_discover_month(year, month):
        if month == 1:
            return [
                {"title": "Film A", "bom_url": "http://example.com/a"},
                {"title": "Film B", "bom_url": "http://example.com/b"}
            ]
        elif month == 2:
            return [
                {"title": "Film A", "bom_url": "http://example.com/a"},  # Duplicate
                {"title": "Film C", "bom_url": "http://example.com/c"}
            ]
        else:
            return []
    
    scraper.discover_films_by_month = mock_discover_month
    
    try:
        films = scraper.discover_films_by_year(2025)
        
        # Should have 3 unique films (A, B, C) not 4
        assert len(films) == 3
        titles = [f['title'] for f in films]
        assert 'Film A' in titles
        assert 'Film B' in titles
        assert 'Film C' in titles
        assert titles.count('Film A') == 1
    finally:
        scraper.discover_films_by_month = original_method

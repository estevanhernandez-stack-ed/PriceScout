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

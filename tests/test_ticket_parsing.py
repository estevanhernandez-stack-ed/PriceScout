import pytest
import json
from app.scraper import Scraper
from unittest.mock import patch

@pytest.fixture
def scraper_instance():
    """Provides a Scraper instance with real ticket_types.json data for comprehensive testing."""
    return Scraper(headless=True)

@pytest.mark.parametrize("description, expected_base_type, expected_amenities", [
    # --- Standard Cases ---
    ("Adult", "Adult", []),
    ("Child", "Child", []),
    ("Senior", "Senior", []),
    ("Student", "Student", []),
    ("Military", "Military", []),
    ("General Admission", "General Admission", []),

    # --- Amenity Cases ---
    ("Adult IMAX", "Adult", ["IMAX"]),
    ("Child 3D", "Child", ["3D"]),
    ("Senior Dolby Cinema", "Senior", ["Dolby Cinema"]),
    ("Adult with D-BOX", "Adult", ["D-BOX"]),
    ("Adult with Recliner", "Adult", ["Recliner"]),
    ("IMAX with Laser for Adults", "Adult", ["IMAX with Laser"]),
    ("IMAX with Laser", "Unknown", ["IMAX with Laser"]), # No base type, so 'Unknown' is expected

    # --- Combination Cases ---
    ("Adult IMAX 3D", "Adult", ["3D", "IMAX"]), # Amenities should be sorted alphabetically
    ("Child Dolby Cinema with D-BOX", "Child", ["D-BOX", "Dolby Cinema"]),

    # --- Complex/Messy Descriptions ---
    ("General Admission Ticket", "General Admission", []),
    ("Adult Ticket", "Adult", []),
    ("Senior Citizen", "Senior", []),
    ("Child (Age 3-11)", "Child", []),
    ("Adult (12-60)", "Adult", []),
    ("Child (with 3D)", "Child", ["3D"]),

    # --- Case Insensitivity ---
    ("adult", "Adult", []),
    ("CHILD", "Child", []),
    ("senior with IMAX", "Senior", ["IMAX"]),

    # --- Unmatched/Special Event Cases ---
    ("Special Event Screening", "Special Event Screening", []),
    ("Private Event", "Private Event", []),
    ("Fathom Event", "Fathom Event", []),
    ("Anime Movie", "Anime Movie", []),
    ("Concert Film", "Concert Film", []),

    # --- Edge Cases ---
    ("", "Unknown", []),
    ("Ticket", "Unknown", []), # "Ticket" is an ignored word
    ("IMAX Ticket", "Unknown", ["IMAX"]),
    ("Adult Child", "Adult", []), # Should find 'Adult' and ignore the rest.
])
@patch('app.database.log_unmatched_ticket_type')
def test_parse_ticket_description(mock_log_unmatched, scraper_instance, description, expected_base_type, expected_amenities):
    """
    Tests the _parse_ticket_description function with a wide variety of inputs
    to ensure it correctly identifies base types and amenities.
    """
    result = scraper_instance._parse_ticket_description(description)

    # Assert the base type and amenities are correct
    assert result["base_type"] == expected_base_type
    assert sorted(result["amenities"]) == sorted(expected_amenities)

    # --- Verify that logging is called for new, unknown base types ---
    # Get all known base type keywords from the scraper's loaded data
    known_base_type_keywords = [kw for kws in scraper_instance.ticket_types_data['base_type_map'].values() for kw in kws]
    
    # If the expected base type is not one of the canonical types AND it's not a generic/ignored term,
    # it should have been logged as an unmatched type.
    if expected_base_type not in scraper_instance.ticket_types_data['base_type_map'] and \
       expected_base_type not in ["Unknown", "General Admission"] and \
       expected_base_type.lower() not in known_base_type_keywords:
        mock_log_unmatched.assert_called_with(description, expected_base_type)
    else:
        mock_log_unmatched.assert_not_called()

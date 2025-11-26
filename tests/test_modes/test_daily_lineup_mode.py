"""
Tests for daily_lineup_mode.py

Focus on testable pure functions:
1. compact_film_title - Title compacting with year removal, article removal, word limit
2. format_showtime - Time format conversion to 12-hour AM/PM
3. get_format_indicators - Format code to readable indicator mapping
"""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import date, datetime

from app.modes.daily_lineup_mode import (
    compact_film_title,
    format_showtime,
    get_format_indicators,
    parse_showtime_for_sort,
    parse_runtime_minutes,
    calculate_outtime,
)


class TestCompactFilmTitle:
    """Test the compact_film_title function for title shortening."""

    def test_remove_year_basic(self):
        """Test basic year removal from title."""
        result = compact_film_title("Wicked (2024)")
        assert result == "Wicked"

    def test_remove_year_with_subtitle(self):
        """Test year removal from title with subtitle."""
        result = compact_film_title("Wicked: For Good (2025)")
        assert result == "Wicked: For Good"

    def test_remove_year_multiple_words(self):
        """Test year removal from multi-word title."""
        result = compact_film_title("Now You See Me: Now You Don't (2025)")
        assert result == "Now You See Me: Now You Don't"

    def test_keep_year_when_disabled(self):
        """Test that year is kept when remove_year=False."""
        result = compact_film_title("Wicked (2024)", remove_year=False)
        assert result == "Wicked (2024)"

    def test_remove_article_the(self):
        """Test removal of leading 'The'."""
        result = compact_film_title("The Wild Robot", remove_articles=True)
        assert result == "Wild Robot"

    def test_remove_article_a(self):
        """Test removal of leading 'A'."""
        result = compact_film_title("A Complete Unknown", remove_articles=True)
        assert result == "Complete Unknown"

    def test_remove_article_an(self):
        """Test removal of leading 'An'."""
        result = compact_film_title("An American Werewolf", remove_articles=True)
        assert result == "American Werewolf"

    def test_remove_article_case_insensitive(self):
        """Test article removal is case-insensitive."""
        result = compact_film_title("THE MATRIX", remove_articles=True)
        assert result == "MATRIX"

    def test_keep_article_when_disabled(self):
        """Test that articles are kept when remove_articles=False."""
        result = compact_film_title("The Wild Robot", remove_articles=False)
        assert result == "The Wild Robot"

    def test_max_words_limit_3(self):
        """Test limiting title to 3 words."""
        result = compact_film_title("Now You See Me: Now You Don't", max_words=3)
        assert result == "Now You See"

    def test_max_words_limit_2(self):
        """Test limiting title to 2 words."""
        result = compact_film_title("The Lord of the Rings", max_words=2)
        assert result == "The Lord"

    def test_max_words_no_truncation_needed(self):
        """Test max_words when title is already short enough."""
        result = compact_film_title("Wicked", max_words=3)
        assert result == "Wicked"

    def test_max_words_none_means_no_limit(self):
        """Test that max_words=None means no limit."""
        result = compact_film_title("Now You See Me: Now You Don't", max_words=None)
        assert result == "Now You See Me: Now You Don't"

    def test_max_words_zero_means_no_limit(self):
        """Test that max_words=0 means no limit."""
        result = compact_film_title("Now You See Me: Now You Don't", max_words=0)
        assert result == "Now You See Me: Now You Don't"

    def test_combined_year_and_articles(self):
        """Test combining year removal and article removal."""
        result = compact_film_title("The Wild Robot (2024)", remove_year=True, remove_articles=True)
        assert result == "Wild Robot"

    def test_combined_all_options(self):
        """Test combining all options: year, articles, and word limit."""
        result = compact_film_title(
            "The Lord of the Rings: The Fellowship (2001)",
            remove_year=True,
            remove_articles=True,
            max_words=3
        )
        assert result == "Lord of the"

    def test_empty_title(self):
        """Test with empty string."""
        result = compact_film_title("")
        assert result == ""

    def test_none_title(self):
        """Test with None input."""
        result = compact_film_title(None)
        assert result is None

    def test_whitespace_handling(self):
        """Test that extra whitespace is trimmed."""
        result = compact_film_title("  Wicked (2024)  ")
        assert result == "Wicked"

    def test_year_not_at_end_preserved(self):
        """Test that year not at end of title is preserved."""
        result = compact_film_title("2001: A Space Odyssey (1968)")
        assert result == "2001: A Space Odyssey"

    def test_parentheses_not_year(self):
        """Test that non-year parentheses are preserved."""
        result = compact_film_title("Movie (Director's Cut)")
        assert result == "Movie (Director's Cut)"


class TestFormatShowtime:
    """Test the format_showtime function for time conversion."""

    def test_format_hhmm_morning(self):
        """Test formatting HH:MM morning time."""
        result = format_showtime("09:30")
        assert result == "9:30 AM"

    def test_format_hhmm_afternoon(self):
        """Test formatting HH:MM afternoon time."""
        result = format_showtime("14:00")
        assert result == "2:00 PM"

    def test_format_hhmm_noon(self):
        """Test formatting noon."""
        result = format_showtime("12:00")
        assert result == "12:00 PM"

    def test_format_hhmm_midnight(self):
        """Test formatting midnight."""
        result = format_showtime("00:00")
        assert result == "12:00 AM"

    def test_format_hhmmss_morning(self):
        """Test formatting HH:MM:SS morning time."""
        result = format_showtime("09:30:00")
        assert result == "9:30 AM"

    def test_format_hhmmss_evening(self):
        """Test formatting HH:MM:SS evening time."""
        result = format_showtime("19:45:00")
        assert result == "7:45 PM"

    def test_format_leading_zero_stripped(self):
        """Test that leading zero is stripped from hour."""
        result = format_showtime("01:00")
        assert result == "1:00 AM"

    def test_format_double_digit_hour_preserved(self):
        """Test that double-digit hours are preserved."""
        result = format_showtime("11:30")
        assert result == "11:30 AM"

    def test_format_invalid_returns_original(self):
        """Test that invalid format returns original string."""
        result = format_showtime("invalid")
        assert result == "invalid"

    def test_format_empty_string(self):
        """Test with empty string."""
        result = format_showtime("")
        assert result == ""


class TestGetFormatIndicators:
    """Test the get_format_indicators function for format code mapping."""

    def test_3d_format(self):
        """Test 3D format detection."""
        result = get_format_indicators(["3D"])
        assert result == "3D"

    def test_imax_format(self):
        """Test IMAX format detection."""
        result = get_format_indicators(["IMAX"])
        assert result == "IMAX"

    def test_ultrascreen_format(self):
        """Test UltraScreen format detection."""
        result = get_format_indicators(["ULTRASCREEN"])
        assert result == "UltraScreen"

    def test_plf_format(self):
        """Test PLF format detection."""
        result = get_format_indicators(["PLF"])
        assert result == "PLF"

    def test_superscreen_maps_to_plf(self):
        """Test SuperScreen maps to PLF."""
        result = get_format_indicators(["SUPERSCREEN"])
        assert result == "PLF"

    def test_premium_maps_to_plf(self):
        """Test Premium maps to PLF."""
        result = get_format_indicators(["PREMIUM"])
        assert result == "PLF"

    def test_dolby_format(self):
        """Test Dolby format detection."""
        result = get_format_indicators(["DOLBY"])
        assert result == "Dolby"

    def test_xd_format(self):
        """Test XD format detection."""
        result = get_format_indicators(["XD"])
        assert result == "XD"

    def test_rpx_format(self):
        """Test RPX format detection."""
        result = get_format_indicators(["RPX"])
        assert result == "RPX"

    def test_dbox_format(self):
        """Test D-BOX format detection."""
        result = get_format_indicators(["D-BOX"])
        assert result == "D-BOX"

    def test_dfx_format(self):
        """Test DFX format detection."""
        result = get_format_indicators(["DFX"])
        assert result == "DFX"

    def test_standard_returns_standard(self):
        """Test standard format returns 'Standard'."""
        result = get_format_indicators(["STANDARD"])
        assert result == "Standard"

    def test_2d_returns_standard(self):
        """Test 2D format returns 'Standard'."""
        result = get_format_indicators(["2D"])
        assert result == "Standard"

    def test_empty_list_returns_standard(self):
        """Test empty list returns 'Standard'."""
        result = get_format_indicators([])
        assert result == "Standard"

    def test_none_in_list_returns_standard(self):
        """Test None value in list returns 'Standard'."""
        result = get_format_indicators([None])
        assert result == "Standard"

    def test_empty_string_returns_standard(self):
        """Test empty string in list returns 'Standard'."""
        result = get_format_indicators([""])
        assert result == "Standard"

    def test_multiple_formats_combined(self):
        """Test multiple formats are combined."""
        result = get_format_indicators(["IMAX", "3D"])
        # Should contain both, sorted alphabetically
        assert "3D" in result
        assert "IMAX" in result

    def test_case_insensitive(self):
        """Test format detection is case-insensitive."""
        result = get_format_indicators(["imax"])
        assert result == "IMAX"

    def test_duplicate_formats_deduplicated(self):
        """Test duplicate formats are removed."""
        result = get_format_indicators(["IMAX", "IMAX", "IMAX"])
        assert result == "IMAX"

    def test_unknown_format_preserved(self):
        """Test unknown format is preserved as-is."""
        result = get_format_indicators(["SPECIAL_FORMAT"])
        assert result == "SPECIAL_FORMAT"


class TestCompactFilmTitleEdgeCases:
    """Additional edge case tests for compact_film_title."""

    def test_sequel_number_preserved(self):
        """Test that sequel numbers are preserved."""
        result = compact_film_title("Moana 2 (2024)")
        assert result == "Moana 2"

    def test_roman_numeral_preserved(self):
        """Test that Roman numerals are preserved."""
        result = compact_film_title("Rocky IV (1985)")
        assert result == "Rocky IV"

    def test_colon_in_title_preserved(self):
        """Test that colons in titles are preserved."""
        result = compact_film_title("Star Wars: A New Hope (1977)")
        assert result == "Star Wars: A New Hope"

    def test_hyphen_in_title_preserved(self):
        """Test that hyphens in titles are preserved."""
        result = compact_film_title("Spider-Man: No Way Home (2021)")
        assert result == "Spider-Man: No Way Home"

    def test_article_in_middle_not_removed(self):
        """Test that articles in the middle of title are not removed."""
        result = compact_film_title("Lord of the Rings", remove_articles=True)
        assert result == "Lord of the Rings"

    def test_single_word_title(self):
        """Test single word title."""
        result = compact_film_title("Wicked (2024)", max_words=1)
        assert result == "Wicked"


class TestParseShowtimeForSort:
    """Test the parse_showtime_for_sort function for proper chronological ordering."""

    def test_24hour_format_hhmm(self):
        """Test parsing 24-hour HH:MM format."""
        from datetime import time as dt_time
        result = parse_showtime_for_sort("14:30")
        assert result == dt_time(14, 30)

    def test_24hour_format_hhmmss(self):
        """Test parsing 24-hour HH:MM:SS format."""
        from datetime import time as dt_time
        result = parse_showtime_for_sort("14:30:00")
        assert result == dt_time(14, 30, 0)

    def test_single_digit_hour(self):
        """Test parsing single-digit hour (9:00 vs 09:00)."""
        from datetime import time as dt_time
        result = parse_showtime_for_sort("9:30")
        assert result == dt_time(9, 30)

    def test_morning_time(self):
        """Test parsing morning time."""
        from datetime import time as dt_time
        result = parse_showtime_for_sort("09:00")
        assert result == dt_time(9, 0)

    def test_evening_time(self):
        """Test parsing evening time."""
        from datetime import time as dt_time
        result = parse_showtime_for_sort("22:00")
        assert result == dt_time(22, 0)

    def test_10pm_sorts_after_9pm(self):
        """Test that 10:00 PM (22:00) sorts AFTER 9:00 PM (21:00) - the main bug fix."""
        time_22 = parse_showtime_for_sort("22:00")  # 10:00 PM
        time_21 = parse_showtime_for_sort("21:00")  # 9:00 PM
        time_9 = parse_showtime_for_sort("09:00")   # 9:00 AM

        # 9:00 AM should come before 9:00 PM
        assert time_9 < time_21
        # 9:00 PM should come before 10:00 PM
        assert time_21 < time_22
        # Full ordering: 9:00 AM < 9:00 PM < 10:00 PM
        assert time_9 < time_21 < time_22

    def test_sorting_multiple_times(self):
        """Test that a list of times sorts correctly."""
        times = ["22:00", "09:00", "14:30", "21:00", "10:00"]
        sorted_times = sorted(times, key=parse_showtime_for_sort)
        assert sorted_times == ["09:00", "10:00", "14:30", "21:00", "22:00"]

    def test_empty_string(self):
        """Test empty string returns end-of-day time."""
        from datetime import time as dt_time
        result = parse_showtime_for_sort("")
        assert result == dt_time(23, 59, 59)

    def test_none_value(self):
        """Test None returns end-of-day time."""
        from datetime import time as dt_time
        result = parse_showtime_for_sort(None)
        assert result == dt_time(23, 59, 59)

    def test_12hour_format_am(self):
        """Test parsing 12-hour AM format."""
        from datetime import time as dt_time
        result = parse_showtime_for_sort("9:30 AM")
        assert result == dt_time(9, 30)

    def test_12hour_format_pm(self):
        """Test parsing 12-hour PM format."""
        from datetime import time as dt_time
        result = parse_showtime_for_sort("2:30 PM")
        assert result == dt_time(14, 30)


class TestParseRuntimeMinutes:
    """Test the parse_runtime_minutes function for runtime string parsing."""

    def test_simple_minutes(self):
        """Test parsing simple minute format '120 min'."""
        assert parse_runtime_minutes("120 min") == 120

    def test_minutes_no_space(self):
        """Test parsing '120min' without space."""
        assert parse_runtime_minutes("120min") == 120

    def test_hours_and_minutes(self):
        """Test parsing '2h 30m' format."""
        assert parse_runtime_minutes("2h 30m") == 150

    def test_hours_and_minutes_no_space(self):
        """Test parsing '2h30m' without space."""
        assert parse_runtime_minutes("2h30m") == 150

    def test_colon_format(self):
        """Test parsing '2:30' (hours:minutes) format."""
        assert parse_runtime_minutes("2:30") == 150

    def test_just_hours(self):
        """Test parsing '2h' format."""
        assert parse_runtime_minutes("2h") == 120

    def test_hours_spelled_out(self):
        """Test parsing '2 hours' format."""
        assert parse_runtime_minutes("2 hours") == 120

    def test_plain_number(self):
        """Test parsing plain number '120'."""
        assert parse_runtime_minutes("120") == 120

    def test_none_value(self):
        """Test None returns None."""
        assert parse_runtime_minutes(None) is None

    def test_empty_string(self):
        """Test empty string returns None."""
        assert parse_runtime_minutes("") is None

    def test_invalid_string(self):
        """Test invalid string returns None."""
        assert parse_runtime_minutes("not a runtime") is None

    def test_case_insensitive(self):
        """Test parsing is case-insensitive."""
        assert parse_runtime_minutes("120 MIN") == 120
        assert parse_runtime_minutes("2H 30M") == 150


class TestCalculateOuttime:
    """Test the calculate_outtime function for end time calculation."""

    def test_basic_calculation(self):
        """Test basic outtime calculation."""
        result = calculate_outtime("14:00", 120)  # 2:00 PM + 2 hours = 4:00 PM
        assert result == "4:00 PM"

    def test_morning_showing(self):
        """Test morning showing outtime."""
        result = calculate_outtime("09:30", 90)  # 9:30 AM + 1.5 hours = 11:00 AM
        assert result == "11:00 AM"

    def test_evening_showing(self):
        """Test evening showing outtime."""
        result = calculate_outtime("21:00", 150)  # 9:00 PM + 2.5 hours = 11:30 PM
        assert result == "11:30 PM"

    def test_crosses_midnight(self):
        """Test showing that crosses midnight."""
        result = calculate_outtime("23:00", 120)  # 11:00 PM + 2 hours = 1:00 AM
        assert result == "1:00 AM"

    def test_none_showtime(self):
        """Test None showtime returns None."""
        assert calculate_outtime(None, 120) is None

    def test_none_runtime(self):
        """Test None runtime returns None."""
        assert calculate_outtime("14:00", None) is None

    def test_zero_runtime(self):
        """Test zero runtime returns None."""
        assert calculate_outtime("14:00", 0) is None

    def test_with_seconds_format(self):
        """Test with HH:MM:SS format."""
        result = calculate_outtime("14:00:00", 120)
        assert result == "4:00 PM"

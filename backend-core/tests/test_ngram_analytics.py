"""Tests for N-Gram analytics, particularly special character handling."""

import pytest
from app.services.ngram.analytics import clean_query_str


class TestCleanQueryStr:
    """Test the clean_query_str function preserves important characters."""

    def test_preserves_inch_marks(self):
        """Inch marks (") should be preserved for measurements."""
        assert clean_query_str('10" gold shelf brackets') == '10" gold shelf brackets'
        assert clean_query_str('24" monitor stand') == '24" monitor stand'

    def test_preserves_foot_marks(self):
        """Foot marks (') should be preserved for measurements."""
        assert clean_query_str("5' tall ladder") == "5' tall ladder"
        assert clean_query_str("6' cable") == "6' cable"

    def test_preserves_brand_symbols(self):
        """Brand symbols (™, ®, ©) should be preserved."""
        assert clean_query_str("Nike™ running shoes") == "nike™ running shoes"
        assert clean_query_str("Microsoft® software") == "microsoft® software"
        assert clean_query_str("©2024 product") == "©2024 product"

    def test_preserves_degree_symbol(self):
        """Degree symbol (°) should be preserved for measurements."""
        assert clean_query_str("90° angle bracket") == "90° angle bracket"
        assert clean_query_str("180° hinge") == "180° hinge"

    def test_preserves_ampersand(self):
        """Ampersands (&) should be preserved in company/product names."""
        assert clean_query_str("L&T connector") == "l&t connector"
        assert clean_query_str("Black & Decker drill") == "black & decker drill"

    def test_preserves_plus_sign(self):
        """Plus signs (+) should be preserved in product names."""
        assert clean_query_str("5+1 pack") == "5+1 pack"
        assert clean_query_str("C++ programming book") == "c++ programming book"

    def test_preserves_hashtag(self):
        """Hashtags (#) should be preserved."""
        assert clean_query_str("#1 seller") == "#1 seller"
        assert clean_query_str("Product #123") == "product #123"

    def test_preserves_hyphens(self):
        """Hyphens should be preserved in compound words."""
        assert clean_query_str("USB-C cable") == "usb-c cable"
        assert clean_query_str("T-shirt") == "t-shirt"

    def test_collapses_multiple_hyphens(self):
        """Multiple consecutive hyphens should be collapsed to single hyphen."""
        assert clean_query_str("multi---dash") == "multi-dash"
        assert clean_query_str("test----word") == "test-word"

    def test_converts_underscores_to_spaces(self):
        """Underscores should be converted to spaces."""
        assert clean_query_str("hello_world") == "hello world"
        assert clean_query_str("test___word") == "test   word"  # Multiple underscores → multiple spaces
        # Note: multiple spaces are collapsed later

    def test_collapses_whitespace(self):
        """Multiple spaces should be collapsed to single space."""
        assert clean_query_str("too   many    spaces") == "too many spaces"
        assert clean_query_str("  trim  spaces  ") == "trim spaces"

    def test_strips_unwanted_chars(self):
        """Unwanted characters should be stripped."""
        assert clean_query_str("test!!!urgent") == "test urgent"
        assert clean_query_str("price$19.99") == "price 19 99"
        assert clean_query_str("email@test.com") == "email test com"

    def test_preserves_unicode_letters(self):
        """Unicode letters from any language should be preserved."""
        # Spanish
        assert clean_query_str("niño toys") == "niño toys"
        # French
        assert clean_query_str("café tables") == "café tables"
        # German
        assert clean_query_str("Müller brand") == "müller brand"
        # Japanese
        assert clean_query_str("日本 product") == "日本 product"

    def test_mixed_unicode_and_special_chars(self):
        """Unicode letters combined with special characters."""
        assert clean_query_str('niño\'s 10" toy') == 'niño\'s 10" toy'
        assert clean_query_str("café™ 90° mug") == "café™ 90° mug"

    def test_lowercases_input(self):
        """All input should be lowercased."""
        assert clean_query_str("UPPER CASE") == "upper case"
        assert clean_query_str("MiXeD CaSe") == "mixed case"

    def test_empty_and_whitespace(self):
        """Empty strings and pure whitespace should be handled."""
        assert clean_query_str("") == ""
        assert clean_query_str("   ") == ""
        assert clean_query_str("\t\n") == ""

    def test_real_world_examples(self):
        """Test with realistic product search terms."""
        assert clean_query_str('10" gold shelf brackets heavy duty') == '10" gold shelf brackets heavy duty'
        assert clean_query_str("Nike™ Air Max 90° Comfort") == "nike™ air max 90° comfort"
        assert clean_query_str("5' x 10\" wood plank") == "5' x 10\" wood plank"
        assert clean_query_str("USB-C to USB-A adapter #1 seller") == "usb-c to usb-a adapter #1 seller"

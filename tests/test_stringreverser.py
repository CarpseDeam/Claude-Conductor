import pytest

from src.utils.string_reverser import reverse_string


class TestReverseString:
    """Tests for the reverse_string function."""

    # Must Do: Return the input string reversed
    def test_reverses_string(self):
        assert reverse_string("hello") == "olleh"

    def test_reverses_longer_string(self):
        assert reverse_string("abcdefg") == "gfedcba"

    # Must Do: Handle empty strings
    def test_handles_empty_string(self):
        assert reverse_string("") == ""

    # Edge Case: Single character returns same character
    def test_single_character(self):
        assert reverse_string("a") == "a"

    # Edge Case: Unicode characters preserved correctly
    def test_unicode_characters(self):
        assert reverse_string("héllo") == "olléh"

    def test_unicode_emoji(self):
        assert reverse_string("ab🎉cd") == "dc🎉ba"

    def test_unicode_multibyte(self):
        assert reverse_string("日本語") == "語本日"

    # Postcondition: Output length equals input length
    def test_output_length_equals_input_length(self):
        test_input = "testing"
        result = reverse_string(test_input)
        assert len(result) == len(test_input)

    # Postcondition: Output is reversed input
    def test_double_reverse_returns_original(self):
        test_input = "reversible"
        result = reverse_string(reverse_string(test_input))
        assert result == test_input

    # Must Not Do: Modify the original string
    def test_does_not_modify_original_string(self):
        original = "immutable"
        original_copy = original
        reverse_string(original)
        assert original == original_copy

    # Must Not Do: Raise exceptions on valid input
    def test_no_exception_on_valid_input(self):
        reverse_string("valid")

    def test_no_exception_on_empty_string(self):
        reverse_string("")

    def test_no_exception_on_whitespace(self):
        reverse_string("   ")

    # Additional edge cases for robustness
    def test_palindrome(self):
        assert reverse_string("racecar") == "racecar"

    def test_whitespace_preserved(self):
        assert reverse_string("a b c") == "c b a"

    def test_special_characters(self):
        assert reverse_string("!@#$%") == "%$#@!"

#!/usr/bin/python
# ----------------------------------------------------------------------------------
# Project: Crystalsweep
# File: tests/utils/test_validators.py
# ----------------------------------------------------------------------------------
# Purpose:
# Tests for MotorPositionValidator input parsing and formatted string output.
# ----------------------------------------------------------------------------------
# Author: Christofanis Skordas
#
# Copyright (c) 2026 GSECARS, The University of Chicago, USA
# Copyright (c) 2026 NSF SEES, USA
# ----------------------------------------------------------------------------------
import pytest
from pydantic import ValidationError

from crystalsweep.utils.validators import MotorPositionValidator


class TestMotorPositionValidatorInit:
    """Verify MotorPositionValidator accepts valid inputs and rejects invalid ones."""

    def test_valid_float_string(self):
        v = MotorPositionValidator("3.14")
        assert abs(v._value - 3.14) < 1e-9

    def test_valid_integer_string(self):
        v = MotorPositionValidator("42")
        assert v._value == 42.0

    def test_negative_value(self):
        v = MotorPositionValidator("-5.5")
        assert v._value == -5.5

    def test_leading_and_trailing_whitespace_stripped(self):
        v = MotorPositionValidator("  2.718  ")
        assert abs(v._value - 2.718) < 1e-9

    def test_zero_is_valid(self):
        v = MotorPositionValidator("0")
        assert v._value == 0.0

    def test_scientific_notation(self):
        v = MotorPositionValidator("1e-3")
        assert abs(v._value - 0.001) < 1e-12

    def test_invalid_string_raises(self):
        with pytest.raises((ValidationError, ValueError)):
            MotorPositionValidator("not_a_number")

    def test_empty_string_raises(self):
        with pytest.raises((ValidationError, ValueError)):
            MotorPositionValidator("")

    def test_negative_precision_clamped_to_zero(self):
        v = MotorPositionValidator("1.23456", precision=-3)
        assert v._precision == 0

    def test_zero_precision_accepted(self):
        v = MotorPositionValidator("1.23", precision=0)
        assert v._precision == 0

    def test_default_precision_is_four(self):
        v = MotorPositionValidator("1.0")
        assert v._precision == 4


class TestMotorPositionValidatorFormatted:
    """Verify formatted property rounds to the configured precision."""

    def test_default_precision_four(self):
        v = MotorPositionValidator("3.14159")
        assert v.formatted == "3.1416"

    def test_precision_two(self):
        v = MotorPositionValidator("1.5678", precision=2)
        assert v.formatted == "1.57"

    def test_precision_zero(self):
        v = MotorPositionValidator("3.9", precision=0)
        assert v.formatted == "4"

    def test_negative_value_formatted(self):
        v = MotorPositionValidator("-7.12345", precision=3)
        assert v.formatted == "-7.123"

    def test_integer_string_formatted_with_decimals(self):
        v = MotorPositionValidator("42", precision=4)
        assert v.formatted == "42.0000"

    def test_zero_formatted(self):
        v = MotorPositionValidator("0", precision=4)
        assert v.formatted == "0.0000"

    def test_precision_six(self):
        v = MotorPositionValidator("1.123456789", precision=6)
        assert v.formatted == "1.123457"

    def test_small_value_rounds_correctly(self):
        v = MotorPositionValidator("0.00005", precision=4)
        assert v.formatted == "0.0001"

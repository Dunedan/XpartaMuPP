# Copyright (C) 2017 Wildfire Games.
# This file is part of 0 A.D.
#
# 0 A.D. is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# 0 A.D. is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 0 A.D.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for the ELO-implementation."""

from unittest import TestCase

from parameterized import parameterized

from xpartamupp.elo import get_rating_adjustment, ELO_K_FACTOR_CONSTANT_RATING


class TestELO(TestCase):
    """Test behavior of ELO calculation."""

    @parameterized.expand([
        ([1000, 1000, 0, 0, 1], 82),
        ([1000, 1000, 0, 0, -1], -83),
        ([1000, 1000, 0, 0, 0], 0),
        ([1200, 1200, 0, 0, 1], 78),
        ([1200, 1200, 0, 0, -1], -78),
        ([1200, 1200, 0, 0, 0], 0),
        ([1200, 1200, 1, 0, 1], 65),
        ([1200, 1200, 1, 0, 0], 0),
        ([1200, 1200, 1, 0, -1], -65),
        ([1200, 1200, 100, 0, 1], 16),
        ([1200, 1200, 100, 0, 0], 0),
        ([1200, 1200, 100, 0, -1], -16),
        ([1200, 1200, 1000, 0, 1], 16),
        ([1200, 1200, 1000, 0, 0], 0),
        ([1200, 1200, 1000, 0, -1], -16),
        ([1200, 1200, 0, 1, 1], 78),
        ([1200, 1200, 0, 1, 0], 0),
        ([1200, 1200, 0, 1, -1], -78),
        ([1200, 1200, 0, 100, 1], 78),
        ([1200, 1200, 0, 100, 0], 0),
        ([1200, 1200, 0, 100, -1], -78),
        ([1200, 1200, 0, 1000, 1], 78),
        ([1200, 1200, 0, 1000, 0], 0),
        ([1200, 1200, 0, 1000, -1], -78),
        ([1400, 1000, 0, 0, 1], 24),
        ([1400, 1000, 0, 0, 0], -49),
        ([1400, 1000, 0, 0, -1], -122),
        ([1000, 1400, 0, 0, 1], 137),
        ([1000, 1400, 0, 0, 0], 55),
        ([1000, 1400, 0, 0, -1], -28),
    ])
    def test_valid_adjustments(self, args, expected_adjustment):
        """Test correctness of valid rating adjustments."""
        self.assertEqual(get_rating_adjustment(*args), expected_adjustment)

    @parameterized.expand([
        ([ELO_K_FACTOR_CONSTANT_RATING, ELO_K_FACTOR_CONSTANT_RATING, 0, 0, 1], 60),
        ([ELO_K_FACTOR_CONSTANT_RATING, ELO_K_FACTOR_CONSTANT_RATING, 0, 0, -1], -60),
        ([ELO_K_FACTOR_CONSTANT_RATING, ELO_K_FACTOR_CONSTANT_RATING, 0, 0, 0], 0),
        ([ELO_K_FACTOR_CONSTANT_RATING + 300, ELO_K_FACTOR_CONSTANT_RATING + 300, 0, 0, 1], 60),
        ([ELO_K_FACTOR_CONSTANT_RATING + 300, ELO_K_FACTOR_CONSTANT_RATING + 300, 0, 0, -1], -60),
        ([ELO_K_FACTOR_CONSTANT_RATING + 300, ELO_K_FACTOR_CONSTANT_RATING + 300, 0, 0, 0], 0),
        ([ELO_K_FACTOR_CONSTANT_RATING + 200, ELO_K_FACTOR_CONSTANT_RATING, 0, 0, 1], 40),
        ([ELO_K_FACTOR_CONSTANT_RATING + 200, ELO_K_FACTOR_CONSTANT_RATING, 0, 0, -1], -80),
        ([ELO_K_FACTOR_CONSTANT_RATING + 200, ELO_K_FACTOR_CONSTANT_RATING, 0, 0, 0], -20),
        ([ELO_K_FACTOR_CONSTANT_RATING + 500, ELO_K_FACTOR_CONSTANT_RATING + 300, 0, 0, 1], 40),
        ([ELO_K_FACTOR_CONSTANT_RATING + 500, ELO_K_FACTOR_CONSTANT_RATING + 300, 0, 0, -1], -80),
        ([ELO_K_FACTOR_CONSTANT_RATING + 500, ELO_K_FACTOR_CONSTANT_RATING + 300, 0, 0, 0], -20),
        ([ELO_K_FACTOR_CONSTANT_RATING, ELO_K_FACTOR_CONSTANT_RATING + 200, 0, 0, 1], 80),
        ([ELO_K_FACTOR_CONSTANT_RATING, ELO_K_FACTOR_CONSTANT_RATING + 200, 0, 0, -1], -40),
        ([ELO_K_FACTOR_CONSTANT_RATING, ELO_K_FACTOR_CONSTANT_RATING + 200, 0, 0, 0], 20),
        ([ELO_K_FACTOR_CONSTANT_RATING + 300, ELO_K_FACTOR_CONSTANT_RATING + 500, 0, 0, 1], 80),
        ([ELO_K_FACTOR_CONSTANT_RATING + 300, ELO_K_FACTOR_CONSTANT_RATING + 500, 0, 0, -1], -40),
        ([ELO_K_FACTOR_CONSTANT_RATING + 300, ELO_K_FACTOR_CONSTANT_RATING + 500, 0, 0, 0], 20),
    ])
    def test_constant_rating(self, args, expected_adjustment):
        """Test that points gained are constant above a threshold."""
        self.assertEqual(get_rating_adjustment(*args), expected_adjustment)

    @parameterized.expand([
        ([1600, 1000, 0, 0, 1], 0),
        ([1000, 1600, 0, 0, -1], 0),
    ])
    def test_sure_wins(self, args, expected_adjustment):
        """Test that sure wins don't grant points."""
        self.assertEqual(get_rating_adjustment(*args), expected_adjustment)

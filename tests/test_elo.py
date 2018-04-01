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

from hypothesis import example, given
from hypothesis.strategies import integers, just, one_of
from parameterized import parameterized

from xpartamupp.elo import (get_rating_adjustment, ANTI_INFLATION, ELO_K_FACTOR_CONSTANT_RATING,
                            ELO_SURE_WIN_DIFFERENCE, VOLATILITY_CONSTANT)


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
        ([2200, 2300, 0, 0, 1], 70),
        ([2200, 2300, 0, 0, 0], 10),
        ([2200, 2300, 0, 0, -1], -50),
    ])
    def test_valid_adjustments(self, args, expected_adjustment):
        """Test correctness of valid rating adjustments."""
        self.assertEqual(get_rating_adjustment(*args), expected_adjustment)

    @given(integers(min_value=ELO_K_FACTOR_CONSTANT_RATING),
           integers(max_value=ELO_SURE_WIN_DIFFERENCE - 1), integers(), integers(),
           integers(min_value=-1, max_value=1))
    @example(ELO_K_FACTOR_CONSTANT_RATING + 300, 0, 0, 0, 1)
    def test_constant_rating(self, rating_player1, difference_player2, played_games_player1,
                             played_games_player2, result):
        """Test that points gained are constant above a threshold."""
        volatility = 50.0 * (min(max(0, played_games_player1), VOLATILITY_CONSTANT) /
                             VOLATILITY_CONSTANT + 0.25) / 1.25
        rating_adjustment = (difference_player2 + result * ELO_SURE_WIN_DIFFERENCE) / volatility \
            - ANTI_INFLATION
        if result == 1:
            expected_adjustment = max(0.0, rating_adjustment)
        elif result == -1:
            expected_adjustment = min(0.0, rating_adjustment)
        else:
            expected_adjustment = rating_adjustment

        self.assertEqual(get_rating_adjustment(rating_player1, rating_player1 + difference_player2,
                                               played_games_player1, played_games_player2, result),
                         round(expected_adjustment))

    @given(integers(), integers(min_value=ELO_SURE_WIN_DIFFERENCE), integers(),
           integers(), one_of(just(-1), just(1)))
    @example(1000, ELO_SURE_WIN_DIFFERENCE, 0, 0, 1)
    def test_sure_win(self, rating_player1, difference_player2, played_games_player1,
                      played_games_player2, result):
        """Test behavior if winning player has >600 points more.

        In this case the winning player shouldn't gain points, as it
        was a "sure win" and the loosing player shouldn't loose
        points.
        """
        self.assertEqual(get_rating_adjustment(rating_player1,
                                               rating_player1 - difference_player2 * result,
                                               played_games_player1, played_games_player2, result),
                         0)
        self.assertEqual(get_rating_adjustment(rating_player1 - difference_player2 * result,
                                               rating_player1, played_games_player2,
                                               played_games_player1, result * -1), 0)

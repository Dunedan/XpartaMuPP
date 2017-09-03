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

from argparse import Namespace
from unittest import TestCase

from parameterized import parameterized

from xpartamupp.lobby_ranking import parse_args


class TestArgumentParsing(TestCase):
    """Test handling of parsing command line parameters."""

    @parameterized.expand([
        (['create'], Namespace(action='create', database_url='sqlite:///lobby_rankings.sqlite3')),
        (['--database-url', 'sqlite:////tmp/db.sqlite3', 'create'],
         Namespace(action='create', database_url='sqlite:////tmp/db.sqlite3')),
    ])
    def test_valid(self, cmd_args, expected_args):
        """Test valid parameter combinations."""
        self.assertEqual(parse_args(cmd_args), expected_args)

    @parameterized.expand([
        ([],),
        (['--database-url=sqlite:////tmp/db.sqlite3'],),
    ])
    def test_missing_action(self, cmd_args):
        """Test invalid parameter combinations."""
        with self.assertRaises(SystemExit):
            parse_args(cmd_args)

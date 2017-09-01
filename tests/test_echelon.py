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

from xpartamupp.echelon import parse_args


class TestArgumentParsing(TestCase):
    """Test handling of parsing command line parameters."""

    @parameterized.expand([
        ([], Namespace(domain='lobby.wildfiregames.com', login='EcheLOn', log_level=30,
                       nickname='Ratings', password='XXXXXX', room='arena')),
        (['--debug'],
         Namespace(domain='lobby.wildfiregames.com', login='EcheLOn', log_level=10,
                   nickname='Ratings', password='XXXXXX', room='arena')),
        (['--quiet'],
         Namespace(domain='lobby.wildfiregames.com', login='EcheLOn', log_level=40,
                   nickname='Ratings', password='XXXXXX', room='arena')),
        (['--verbose'],
         Namespace(domain='lobby.wildfiregames.com', login='EcheLOn', log_level=20,
                   nickname='Ratings', password='XXXXXX', room='arena')),
        (['-m', 'lobby.domain.tld'],
         Namespace(domain='lobby.domain.tld', login='EcheLOn', log_level=30, nickname='Ratings',
                   password='XXXXXX', room='arena')),
        (['--domain=lobby.domain.tld'],
         Namespace(domain='lobby.domain.tld', login='EcheLOn', log_level=30, nickname='Ratings',
                   password='XXXXXX', room='arena')),
        (['-m' 'lobby.domain.tld', '-l', 'bot', '-p', '123456', '-n', 'Bot', '-r', 'arena123',
          '-v'],
         Namespace(domain='lobby.domain.tld', login='bot', log_level=20, nickname='Bot',
                   password='123456', room='arena123')),
        (['--domain=lobby.domain.tld', '--login=bot', '--password=123456', '--nickname=Bot',
          '--room=arena123', '--verbose'],
         Namespace(domain='lobby.domain.tld', login='bot', log_level=20, nickname='Bot',
                   password='123456', room='arena123')),
    ])
    def test_valid(self, cmd_args, expected_args):
        """Test valid parameter combinations."""
        self.assertEqual(parse_args(cmd_args), expected_args)

    @parameterized.expand([
        (['-f'],),
        (['--foo'],),
        (['--debug', '--quiet'],),
        (['--quiet', '--verbose'],),
        (['--debug', '--verbose'],),
        (['--debug', '--quiet', '--verbose'],),
    ])
    def test_invalid(self, cmd_args):
        """Test invalid parameter combinations."""
        with self.assertRaises(SystemExit):
            parse_args(cmd_args)

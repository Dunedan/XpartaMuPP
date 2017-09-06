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

# pylint: disable=no-self-use

import sys

from argparse import Namespace
from unittest import TestCase
from unittest.mock import Mock, call, patch

from parameterized import parameterized

from xpartamupp.echelon import main, parse_args


class TestArgumentParsing(TestCase):
    """Test handling of parsing command line parameters."""

    @parameterized.expand([
        ([], Namespace(domain='lobby.wildfiregames.com', login='EcheLOn', log_level=30,
                       nickname='Ratings', password='XXXXXX', room='arena',
                       database_url='sqlite:///lobby_rankings.sqlite3')),
        (['--debug'],
         Namespace(domain='lobby.wildfiregames.com', login='EcheLOn', log_level=10,
                   nickname='Ratings', password='XXXXXX', room='arena',
                   database_url='sqlite:///lobby_rankings.sqlite3')),
        (['--quiet'],
         Namespace(domain='lobby.wildfiregames.com', login='EcheLOn', log_level=40,
                   nickname='Ratings', password='XXXXXX', room='arena',
                   database_url='sqlite:///lobby_rankings.sqlite3')),
        (['--verbose'],
         Namespace(domain='lobby.wildfiregames.com', login='EcheLOn', log_level=20,
                   nickname='Ratings', password='XXXXXX', room='arena',
                   database_url='sqlite:///lobby_rankings.sqlite3')),
        (['-m', 'lobby.domain.tld'],
         Namespace(domain='lobby.domain.tld', login='EcheLOn', log_level=30, nickname='Ratings',
                   password='XXXXXX', room='arena',
                   database_url='sqlite:///lobby_rankings.sqlite3')),
        (['--domain=lobby.domain.tld'],
         Namespace(domain='lobby.domain.tld', login='EcheLOn', log_level=30, nickname='Ratings',
                   password='XXXXXX', room='arena',
                   database_url='sqlite:///lobby_rankings.sqlite3')),
        (['-m' 'lobby.domain.tld', '-l', 'bot', '-p', '123456', '-n', 'Bot', '-r', 'arena123',
          '-v'],
         Namespace(domain='lobby.domain.tld', login='bot', log_level=20, nickname='Bot',
                   password='123456', room='arena123',
                   database_url='sqlite:///lobby_rankings.sqlite3')),
        (['--domain=lobby.domain.tld', '--login=bot', '--password=123456', '--nickname=Bot',
          '--room=arena123', '--database-url=sqlite:////tmp/db.sqlite3', '--verbose'],
         Namespace(domain='lobby.domain.tld', login='bot', log_level=20, nickname='Bot',
                   password='123456', room='arena123',
                   database_url='sqlite:////tmp/db.sqlite3')),
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


class TestMain(TestCase):
    """Test main method."""

    def test_success(self):
        """Test successful execution."""
        with patch('xpartamupp.echelon.parse_args') as args_mock, \
                patch('xpartamupp.echelon.Leaderboard') as leaderboard_mock, \
                patch('xpartamupp.echelon.EcheLOn') as xmpp_mock:
            args_mock.return_value = Mock(log_level=30, login='EcheLOn',
                                          domain='lobby.wildfiregames.com', password='XXXXXX',
                                          room='arena', nickname='Ratings',
                                          database_url='sqlite:///lobby_rankings.sqlite3')
            main()
            args_mock.assert_called_once_with(sys.argv[1:])
            leaderboard_mock.assert_called_once_with('sqlite:///lobby_rankings.sqlite3')
            xmpp_mock().register_plugin.assert_has_calls([call('xep_0004'), call('xep_0030'),
                                                          call('xep_0045'), call('xep_0060'),
                                                          call('xep_0199')], any_order=True)
            xmpp_mock().connect.assert_called_once_with()
            xmpp_mock().process.assert_called_once_with(threaded=False)

    def test_failing_connect(self):
        """Test failing connect to XMPP server."""
        with patch('xpartamupp.echelon.parse_args') as args_mock, \
                patch('xpartamupp.echelon.Leaderboard') as leaderboard_mock, \
                patch('xpartamupp.echelon.EcheLOn') as xmpp_mock:
            args_mock.return_value = Mock(log_level=30, login='EcheLOn',
                                          domain='lobby.wildfiregames.com', password='XXXXXX',
                                          room='arena', nickname='Ratings',
                                          database_url='sqlite:///lobby_rankings.sqlite3')
            xmpp_mock().connect.return_value = False
            main()
            args_mock.assert_called_once_with(sys.argv[1:])
            leaderboard_mock.assert_called_once_with('sqlite:///lobby_rankings.sqlite3')
            xmpp_mock().register_plugin.assert_has_calls([call('xep_0004'), call('xep_0030'),
                                                          call('xep_0045'), call('xep_0060'),
                                                          call('xep_0199')], any_order=True)
            xmpp_mock().connect.assert_called_once_with()
            xmpp_mock().process.assert_not_called()

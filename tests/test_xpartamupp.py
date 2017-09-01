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

from xpartamupp.xpartamupp import Games, parse_args


class TestGames(TestCase):
    """Test Games class responsible for holding active games."""

    def test_add(self):
        """Test successfully adding a game."""
        games = Games()
        jid = 'player1@domain.tld'
        # TODO: Check how the real format of data looks like
        game_data = {'players': ['player1', 'player2'], 'nbp': 'foo', 'state': 'init'}
        games.add_game(jid, game_data)
        all_games = games.get_all_games()
        game_data.update({'players-init': game_data['players'], 'nbp-init': game_data['nbp'],
                          'state': game_data['state']})
        self.assertDictEqual(all_games, {jid: game_data})

    @parameterized.expand([
        ('', {}, KeyError),
        ('player1@domain.tld', {}, KeyError),
        ('player1@domain.tld', None, TypeError),
        ('player1@domain.tld', '', TypeError),
    ])
    def test_add_invalid(self, jid, game_data, exception):
        """Test trying to add games with invalid data."""
        games = Games()
        with self.assertRaises(exception):
            games.add_game(jid, game_data)

    def test_remove(self):
        """Test removal of games."""
        games = Games()
        jid1 = 'player1@domain.tld'
        jid2 = 'player3@domain.tld'
        # TODO: Check how the real format of data looks like
        game_data1 = {'players': ['player1', 'player2'], 'nbp': 'foo', 'state': 'init'}
        games.add_game(jid1, game_data1)
        game_data2 = {'players': ['player3', 'player4'], 'nbp': 'bar', 'state': 'init'}
        games.add_game(jid2, game_data2)
        game_data1.update({'players-init': game_data1['players'], 'nbp-init': game_data1['nbp'],
                           'state': game_data1['state']})
        game_data2.update({'players-init': game_data2['players'], 'nbp-init': game_data2['nbp'],
                           'state': game_data2['state']})
        self.assertDictEqual(games.get_all_games(), {jid1: game_data1, jid2: game_data2})
        games.remove_game(jid1)
        self.assertDictEqual(games.get_all_games(), {jid2: game_data2})
        games.remove_game(jid2)
        self.assertDictEqual(games.get_all_games(), dict())

    def test_remove_unknown(self):
        """Test removal of a game, which doesn't exist."""
        games = Games()
        jid = 'player1@domain.tld'
        # TODO: Check how the real format of data looks like
        game_data = {'players': ['player1', 'player2'], 'nbp': 'foo', 'state': 'init'}
        games.add_game(jid, game_data)
        with self.assertRaises(KeyError):
            games.remove_game('foo')

    def test_change_state(self):
        """Test state changes of a games."""
        pass
        # slightly unknown how to do that properly, as some data structures aren't known


class TestArgumentParsing(TestCase):
    """Test handling of parsing command line parameters."""

    @parameterized.expand([
        ([], Namespace(domain='lobby.wildfiregames.com', elo='disabled', login='xpartamupp',
                       log_level=30, nickname='WFGbot', password='XXXXXX', room='arena')),
        (['--debug'],
         Namespace(domain='lobby.wildfiregames.com', elo='disabled', login='xpartamupp',
                   log_level=10, nickname='WFGbot', password='XXXXXX', room='arena')),
        (['--quiet'],
         Namespace(domain='lobby.wildfiregames.com', elo='disabled', login='xpartamupp',
                   log_level=40, nickname='WFGbot', password='XXXXXX', room='arena')),
        (['--verbose'],
         Namespace(domain='lobby.wildfiregames.com', elo='disabled', login='xpartamupp',
                   log_level=20, nickname='WFGbot', password='XXXXXX', room='arena')),
        (['-m', 'lobby.domain.tld'],
         Namespace(domain='lobby.domain.tld', elo='disabled', login='xpartamupp', log_level=30,
                   nickname='WFGbot', password='XXXXXX', room='arena')),
        (['--domain=lobby.domain.tld'],
         Namespace(domain='lobby.domain.tld', elo='disabled', login='xpartamupp', log_level=30,
                   nickname='WFGbot', password='XXXXXX', room='arena')),
        (['-m' 'lobby.domain.tld', '-l', 'bot', '-p', '123456', '-n', 'Bot', '-r', 'arena123',
          '-e', 'RatingsBot', '-v'],
         Namespace(domain='lobby.domain.tld', elo='RatingsBot', login='bot', log_level=20,
                   nickname='Bot', password='123456', room='arena123')),
        (['--domain=lobby.domain.tld', '--login=bot', '--password=123456', '--nickname=Bot',
          '--room=arena123', '--elo=RatingsBot', '--verbose'],
         Namespace(domain='lobby.domain.tld', elo='RatingsBot', login='bot', log_level=20,
                   nickname='Bot', password='123456', room='arena123')),
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

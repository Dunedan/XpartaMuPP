#!/usr/bin/env python3

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

import argparse
import logging
import time
import sys

import sleekxmpp
from sleekxmpp.stanza import Iq
from sleekxmpp.xmlstream import register_stanza_plugin
from sleekxmpp.xmlstream.handler import Callback
from sleekxmpp.xmlstream.matcher import StanzaPath

from xpartamupp.stanzas import (BoardListXmppPlugin, GameListXmppPlugin, GameReportXmppPlugin,
                                ProfileXmppPlugin)


class Games(object):
    """Class to tracks all games in the lobby."""

    def __init__(self):
        """Initialize with empty games."""
        self.games = {}

    def add_game(self, jid, data):
        """Add a game.

        Arguments:
            jid (sleekxmpp.xmlstream.jid.JID): JID of the player who
                started the game
            data (dict): information about the game

        Returns:
            True if adding the game succeeded, False if not

        """
        try:
            data['players-init'] = data['players']
            data['nbp-init'] = data['nbp']
            data['state'] = 'init'
        except (KeyError, ValueError):
            logging.warning("Received invalid data for add game from 0ad: %s", data)
            return False
        else:
            self.games[jid] = data
            return True

    def remove_game(self, jid):
        """Remove a game attached to a JID.

        Arguments:
            jid (sleekxmpp.xmlstream.jid.JID): JID of the player whose
                game to remove.

        Returns:
            True if removing the game succeeded, False if not

        """
        try:
            del self.games[jid]
        except KeyError:
            logging.warning("Game for jid %s didn't exist", jid)
            return False
        else:
            return True

    def get_all_games(self):
        """Return all games.

        Returns:
            dict containing all games with the JID of the player who
            started the game as key.

        """
        return self.games

    def change_game_state(self, jid, data):
        """Switch game state between running and waiting.

        Arguments:
            jid (sleekxmpp.xmlstream.jid.JID): JID of the player whose
                game to change
            data (dict): information about the game

        Returns:
            True if changing the game state succeeded, False if not

        """
        if jid not in self.games:
            logging.warning("Tried to change state for non-existent game %s", jid)
            return False

        try:
            if self.games[jid]['nbp-init'] > data['nbp']:
                logging.debug("change game (%s) state from %s to %s", jid,
                              self.games[jid]['state'], 'waiting')
                self.games[jid]['state'] = 'waiting'
            else:
                logging.debug("change game (%s) state from %s to %s", jid,
                              self.games[jid]['state'], 'running')
                self.games[jid]['state'] = 'running'
            self.games[jid]['nbp'] = data['nbp']
            self.games[jid]['players'] = data['players']
        except (KeyError, ValueError):
            logging.warning("Received invalid data for change game state from 0ad: %s", data)
            return False
        else:
            if 'startTime' not in self.games[jid]:
                self.games[jid]['startTime'] = str(round(time.time()))
            return True


class XpartaMuPP(sleekxmpp.ClientXMPP):
    """Main class which handles IQ data and sends new data."""

    def __init__(self, sjid, password, room, nick, ratings_bot):
        """Initialize XpartaMuPP.

        Arguments:
             sjid (str): JID to use for authentication
             password (str): password to use for authentication
             room (str): XMPP MUC room to join
             nick (str): Nick to use
             ratings_bot (str): JID of the ratings bot

        """
        sleekxmpp.ClientXMPP.__init__(self, sjid, password)
        self.sjid = sjid
        self.room = room
        self.nick = nick
        self.ratings_bot_warned = False

        self.ratings_bot = sleekxmpp.jid.JID(jid=ratings_bot)
        self.games = Games()

        # Store mapping of nicks and XmppIDs, attached via presence
        # stanza
        self.nicks = {}

        register_stanza_plugin(Iq, GameListXmppPlugin)
        register_stanza_plugin(Iq, BoardListXmppPlugin)
        register_stanza_plugin(Iq, GameReportXmppPlugin)
        register_stanza_plugin(Iq, ProfileXmppPlugin)

        self.register_handler(Callback('Iq Gamelist', StanzaPath('iq@type=set/gamelist'),
                                       self._iq_game_list_handler))
        self.register_handler(Callback('Iq Boardlist', StanzaPath('iq@type=get/boardlist'),
                                       self._iq_board_list_request_handler))
        self.register_handler(Callback('Iq GameReport', StanzaPath('iq@type=set/gamereport'),
                                       self._iq_game_report_handler))
        self.register_handler(Callback('Iq Profile', StanzaPath('iq@type=get/profile'),
                                       self._iq_profile_request_handler))

        self.add_event_handler("session_start", self._session_start)
        self.add_event_handler("muc::%s::got_online" % self.room, self._muc_online)
        self.add_event_handler("muc::%s::got_offline" % self.room, self._muc_offline)
        self.add_event_handler("groupchat_message", self._muc_message)

    def _session_start(self, event):  # pylint: disable=unused-argument
        """Join MUC channel and announce presence.

        Arguments:
            event (?): ?

        """
        self.plugin['xep_0045'].joinMUC(self.room, self.nick)
        self.send_presence()
        self.get_roster()
        logging.info("XpartaMuPP started")

    def _muc_online(self, presence):
        """Add joining players to the list of players.

        Arguments:
            presence (sleekxmpp.stanza.presence.Presence): Received
                presence stanza.

        """
        nick = str(presence['muc']['nick'])
        jid = sleekxmpp.jid.JID(jid=presence['muc']['jid'])

        if nick == self.nick:
            return

        if jid.resource not in ['0ad', 'CC']:
            return

        if jid not in self.nicks:
            self.nicks[jid] = nick

        # Send game list to new player.
        self._send_game_list(jid)
        logging.debug("Client '%s' connected with a nick '%s'.", jid, nick)

        if self.ratings_bot not in self.nicks:
            self._warn_ratings_bot_offline()
            return

        iq = self.make_iq_get(ito=self.ratings_bot)
        stanza = BoardListXmppPlugin()
        stanza.add_command('getratinglist')
        iq.set_payload(stanza)

        try:
            iq.send(block=False, callback=self._iq_board_list_result_handler)
        except Exception:
            logging.exception("Failed to send rating list request to %s",
                              self.ratings_bot)

    def _muc_offline(self, presence):
        """Remove leaving players from the list of players.

        Arguments:
            presence (sleekxmpp.stanza.presence.Presence): Received
                presence stanza.

        """
        nick = str(presence['muc']['nick'])
        jid = sleekxmpp.jid.JID(jid=presence['muc']['jid'])

        if nick == self.nick:
            return
        elif nick == self.ratings_bot:
            self.ratings_bot_warned = False

        # Delete any game the player was hosting.
        if self.games.remove_game(jid):
            self._send_game_list()

        try:
            del self.nicks[jid]
        except KeyError:
            logging.debug("Client \"%s\" didn't exist in nick list", jid)

        logging.debug("Client '%s' with nick '%s' disconnected", jid, nick)

    def _muc_message(self, msg):
        """Process messages in the MUC room.

        Respond to messages highlighting the bots name with an
        informative message.

        Arguments:
            msg (?): ?
        """
        if msg['mucnick'] != self.nick and self.nick.lower() in msg['body'].lower():
            self.send_message(mto=msg['from'].bare,
                              mbody="I am the administrative bot in this lobby and cannot "
                                    "participate in any games.",
                              mtype='groupchat')

    def _iq_game_list_handler(self, iq):
        """Handle game state change requests.

        Arguments:
            iq (sleekxmpp.stanza.iq.IQ): Received IQ stanza

        """
        if iq['from'].resource != '0ad':
            return

        command = iq['gamelist']['command']
        if command == 'register':
            success = self.games.add_game(iq['from'], iq['gamelist']['game'])
        elif command == 'unregister':
            success = self.games.remove_game(iq['from'])
        elif command == 'changestate':
            success = self.games.change_game_state(iq['from'], iq['gamelist']['game'])
        else:
            logging.info('Received unknown game command: "%s"', command)
            return

        if success:
            try:
                self._send_game_list()
            except Exception:
                logging.exception('Failed to send game list after "%s" command', command)

    def _iq_board_list_request_handler(self, iq):
        """Handle board list requests and responses.

        Deprecated once muc_online can send lists/register
        automatically on joining the room.

        Arguments:
            iq (sleekxmpp.stanza.iq.IQ): Received IQ stanza

        """
        if iq['from'].resource != '0ad':
            return

        try:
            if self.ratings_bot not in self.nicks:
                self._warn_ratings_bot_offline()
                return

            new_iq = self.make_iq_get(ito=self.ratings_bot)
            stanza = BoardListXmppPlugin()
            stanza.add_command('getleaderboard')
            stanza.add_recipient(iq['from'])
            new_iq.set_payload(stanza)

            try:
                new_iq.send(block=False, callback=self._iq_board_list_result_handler)
            except Exception:
                logging.exception("Failed to send get leaderboard request from %s",
                                  self.ratings_bot)
        except Exception:
            logging.exception("Failed to relay the get leaderboard request from %s to the "
                              "ratings bot", iq['from'].bare)

    def _iq_board_list_result_handler(self, iq):
        """Send the whole leaderboard.

        If no target is passed the leaderboard is broadcasted to all
        clients.

        Arguments:
            iq (sleekxmpp.stanza.iq.IQ): Received IQ stanza

        """
        if iq['from'].resource != 'CC':
            return

        to = iq['boardlist']['recipient']
        new_iq = self.make_iq_result(ito=to)
        new_iq.set_payload(iq['boardlist'])

        if not to:
            # Rating List
            for jid in list(self.nicks):
                new_iq['to'] = jid
                try:
                    new_iq.send(block=False)
                except Exception:
                    logging.exception("Failed to send rating list to %s", jid)
        else:
            try:
                new_iq.send(block=False)
            except Exception:
                logging.exception("Failed to send leaderboard to %s", to)

    def _iq_game_report_handler(self, iq):
        """Handle end of game reports from clients.

        Arguments:
            iq (sleekxmpp.stanza.iq.IQ): Received IQ stanza

        """
        if iq['from'].resource != '0ad':
            return

        try:
            if self.ratings_bot not in self.nicks:
                self._warn_ratings_bot_offline()
                return

            new_iq = self.make_iq_set(ito=self.ratings_bot)
            stanza = GameReportXmppPlugin()
            stanza.add_game(iq['gamereport'])
            stanza.add_sender(iq['from'])
            new_iq.set_payload(stanza)

            try:
                new_iq.send(block=False)
            except Exception:
                logging.exception("Failed to send game report request to %s",
                                  self.ratings_bot)
        except Exception:
            logging.exception("Failed to relay game report from %s to the ratings bot",
                              iq['from'].bare)

    def _iq_profile_request_handler(self, iq):
        """Handle profile requests and responses.

        Forwards profile requests to the ratings bot and register a
        callback for its response.

        Arguments:
            iq (sleekxmpp.stanza.iq.IQ): Received IQ stanza

        """
        if iq['from'].resource != '0ad':
            return

        try:
            if self.ratings_bot not in self.nicks:
                self._warn_ratings_bot_offline()
                return

            new_iq = self.make_iq_get(ito=self.ratings_bot)
            stanza = ProfileXmppPlugin()
            stanza.add_command(iq['profile']['command'])
            stanza.add_recipient(iq['from'])
            new_iq.set_payload(stanza)

            try:
                new_iq.send(block=False, callback=self._iq_profile_result_handler)
            except Exception:
                logging.exception("Failed to send profile request to %s", self.ratings_bot)
        except Exception:
            logging.exception("Failed to relay profile request from %s to the ratings bot",
                              iq['from'].bare)

    def _iq_profile_result_handler(self, iq):
        """Send the player profile to a specified target.

        Relay a profile result returned by the ratings bot to the
        player who requested it.

        Arguments:
            iq (sleekxmpp.stanza.iq.IQ): Received IQ stanza

        """
        if iq['from'].resource != 'CC':
            return

        new_iq = self.make_iq_result(ito=iq['profile']['recipient'])
        new_iq.set_payload(iq['profile'])

        try:
            new_iq.send(block=False)
        except Exception:
            logging.exception("Failed to send profile to %s", iq['profile']['recipient'])

    def _warn_ratings_bot_offline(self):
        """Warn if the ratings bot is offline."""
        if not self.ratings_bot_warned:
            logging.warning("Ratings bot '%s' is offline", self.ratings_bot)
            self.ratings_bot_warned = True

    def _send_game_list(self, to=None):
        """Send a massive stanza with the whole game list.

        If no target is passed the gamelist is broadcasted to all
        clients.

        Arguments:
            to (sleekxmpp.xmlstream.jid.JID): Player to send the game
                list to. If None, the game list will be broadcasted
        """
        games = self.games.get_all_games()

        # Create a stanza with all games
        stanza = GameListXmppPlugin()
        for jids in games:
            stanza.add_game(games[jids])

        iq = self.make_iq_result()
        iq.set_payload(stanza)

        if not to:
            for jid in list(self.nicks):
                iq['to'] = jid
                try:
                    iq.send(block=False)
                except Exception:
                    logging.exception("Failed to send game list to %s", jid)
        else:
            iq['to'] = to
            try:
                iq.send(block=False)
            except Exception:
                logging.exception("Failed to send game list to %s", to)


def parse_args(args):
    """Parse command line arguments.

    Arguments:
        args (dict): Raw command line arguments given to the script

    Returns:
         Parsed command line arguments

    """
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description="XpartaMuPP - XMPP Multiplayer Game Manager")

    log_settings = parser.add_mutually_exclusive_group()
    log_settings.add_argument('-q', '--quiet', help='only log errors', action='store_const',
                              dest='log_level', const=logging.ERROR)
    log_settings.add_argument('-d', '--debug', help='log debug messages', action='store_const',
                              dest='log_level', const=logging.DEBUG)
    log_settings.add_argument('-v', '--verbose', help='log more informative messages',
                              action='store_const', dest='log_level', const=logging.INFO)
    log_settings.set_defaults(log_level=logging.WARNING)

    parser.add_argument('-m', '--domain', help='XMPP server to connect to',
                        default="lobby.wildfiregames.com")
    parser.add_argument('-l', '--login', help='username for login', default="xpartamupp")
    parser.add_argument('-p', '--password', help='password for login', default="XXXXXX")
    parser.add_argument('-n', '--nickname', help='nickname shown to players', default="WFGbot")
    parser.add_argument('-r', '--room', help='XMPP MUC room to join', default="arena")
    parser.add_argument('-e', '--elo', help='username of the rating bot', default="disabled")

    return parser.parse_args(args)


def main():
    """Entry point a console script."""
    args = parse_args(sys.argv[1:])

    logging.basicConfig(level=args.log_level,
                        format='%(asctime)s        %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    xmpp = XpartaMuPP(args.login + '@' + args.domain + '/CC', args.password,
                      args.room + '@conference.' + args.domain, args.nickname,
                      args.elo + '@' + args.domain + '/CC')
    xmpp.register_plugin('xep_0030')  # Service Discovery
    xmpp.register_plugin('xep_0004')  # Data Forms
    xmpp.register_plugin('xep_0045')  # Multi-User Chat
    xmpp.register_plugin('xep_0060')  # PubSub
    xmpp.register_plugin('xep_0199')  # XMPP Ping

    if xmpp.connect():
        xmpp.process()
    else:
        logging.error("Unable to connect")


if __name__ == '__main__':
    main()

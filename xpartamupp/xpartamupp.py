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
import traceback

import sleekxmpp
from sleekxmpp.stanza import Iq
from sleekxmpp.xmlstream import ElementBase, register_stanza_plugin, ET
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
            jid (str): JID of the player who started the game
            data (?): information about the game

        """
        data['players-init'] = data['players']
        data['nbp-init'] = data['nbp']
        data['state'] = 'init'
        self.games[jid] = data

    def remove_game(self, jid):
        """Remove a game attached to a JID.

        Arguments:
            jid (str): JID of the player whoms game to remove.

        """
        del self.games[jid]

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
            jid (str): JID of the player whose game to change
            data (?): ?

        """
        if jid in self.games:
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
            if 'startTime' not in self.games[jid]:
                self.games[jid]['startTime'] = str(round(time.time()))


class PlayerXmppPlugin(ElementBase):
    """Class for custom player stanza extension."""

    name = 'query'
    namespace = 'jabber:iq:player'
    interfaces = {'online'}
    sub_interfaces = interfaces
    plugin_attrib = 'player'

    def add_player_online(self, player):
        """Add a player to the extension.

        Arguments:
            player (str): JID of the player to add

        """
        self.xml.append(ET.fromstring("<online>%s</online>" % player))


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

        self.ratings_bot = ratings_bot
        self.games = Games()

        # Store mapping of nicks and XmppIDs, attached via presence
        # stanza
        self.nicks = {}

        register_stanza_plugin(Iq, PlayerXmppPlugin)
        register_stanza_plugin(Iq, GameListXmppPlugin)
        register_stanza_plugin(Iq, BoardListXmppPlugin)
        register_stanza_plugin(Iq, GameReportXmppPlugin)
        register_stanza_plugin(Iq, ProfileXmppPlugin)

        self.register_handler(Callback('Iq Player', StanzaPath('iq/player'), self.iq_handler,
                                       instream=True))
        self.register_handler(Callback('Iq Gamelist', StanzaPath('iq/gamelist'), self.iq_handler,
                                       instream=True))
        self.register_handler(Callback('Iq Boardlist', StanzaPath('iq/boardlist'), self.iq_handler,
                                       instream=True))
        self.register_handler(Callback('Iq GameReport', StanzaPath('iq/gamereport'),
                                       self.iq_handler, instream=True))
        self.register_handler(Callback('Iq Profile', StanzaPath('iq/profile'), self.iq_handler,
                                       instream=True))

        self.add_event_handler("session_start", self.start)
        self.add_event_handler("muc::%s::got_online" % self.room, self.muc_online)
        self.add_event_handler("muc::%s::got_offline" % self.room, self.muc_offline)
        self.add_event_handler("groupchat_message", self.muc_message)

    def start(self, event):  # pylint: disable=unused-argument
        """Join MUC channel and announce presence.

        Arguments:
            event (?): ?

        """
        self.plugin['xep_0045'].joinMUC(self.room, self.nick)
        self.send_presence()
        self.get_roster()
        logging.info("XpartaMuPP started")

    def muc_online(self, presence):
        """Add joining players to the list of players.

        Arguments:
            presence (?): ?

        """
        nick = str(presence['muc']['nick'])
        jid = str(presence['muc']['jid'])

        if self.ratings_bot in self.nicks:
            self.relay_rating_list_request(self.ratings_bot)

        self.relay_player_online(jid)
        if nick != self.nick:
            if jid not in self.nicks:
                self.nicks[jid] = nick

            # Send game list to new player.
            self.send_game_list(presence['muc']['jid'])
            logging.debug("Client '%s' connected with a nick '%s'.", jid, nick)

    def muc_offline(self, presence):
        """Remove leaving players from the list of players.

        Arguments:
            presence (?): ?

        """
        nick = str(presence['muc']['nick'])
        jid = str(presence['muc']['jid'])

        if nick != self.nick:
            # Delete any games they were hosting.
            for game_jid in self.games.get_all_games():
                if game_jid == jid:
                    self.games.remove_game(game_jid)
                    self.send_game_list()
                    break

            if jid in self.nicks:
                del self.nicks[jid]

            logging.debug("Client '%s' with nick '%s' disconnected", jid, nick)

        if nick == self.ratings_bot:
            self.ratings_bot_warned = False

    def muc_message(self, msg):
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

    def iq_handler(self, iq):
        """Handle the custom stanzas.

        This method should be very robust because we could receive
        anything.

        Arguments:
            iq (?): ?
        """
        if iq['type'] == 'error':
            logging.error('iqhandler error %s', iq['error']['condition'])
            # self.disconnect()
        elif iq['type'] == 'get':
            # Request lists.
            # Send lists/register on leaderboard; depreciated once
            # muc_online can send lists/register automatically on
            # joining the room.
            if 'boardlist' in iq.plugins:
                try:
                    self.relay_board_list_request(self.ratings_bot, iq['from'])
                except:
                    traceback.print_exc()
                    logging.error("Failed to process leaderboardlist request from %s",
                                  iq['from'].bare)
            elif 'profile' in iq.plugins:
                command = iq['profile']['command']
                try:
                    self.relay_profile_request(self.ratings_bot, iq['from'], command)
                except:
                    pass
            else:
                logging.error("Unknown 'get' type stanza request from %s", iq['from'].bare)
        elif iq['type'] == 'result':
            # Iq successfully received
            if 'boardlist' in iq.plugins:
                recipient = iq['boardlist']['recipient']
                self.relay_board_list(iq['boardlist'], recipient)
            elif 'profile' in iq.plugins:
                recipient = iq['profile']['recipient']
                player = iq['profile']['command']
                self.relay_profile(iq['profile'], player, recipient)
            else:
                pass  # TODO error/warn?
        elif iq['type'] == 'set':
            if 'gamelist' in iq.plugins:
                # Register-update / unregister a game
                command = iq['gamelist']['command']
                if command == 'register':
                    # Add game
                    try:
                        self.games.add_game(str(iq['from']), iq['gamelist']['game'])
                        self.send_game_list()
                    except:
                        traceback.print_exc()
                        logging.error("Failed to process game registration data")
                elif command == 'unregister':
                    # Remove game
                    try:
                        self.games.remove_game(str(iq['from']))
                        self.send_game_list()
                    except:
                        traceback.print_exc()
                        logging.error("Failed to process game unregistration data")

                elif command == 'changestate':
                    # Change game status (waiting/running)
                    try:
                        self.games.change_game_state(str(iq['from']), iq['gamelist']['game'])
                        self.send_game_list()
                    except:
                        traceback.print_exc()
                        logging.error("Failed to process changestate data")
                else:
                    logging.error("Failed to process command '%s' received from %s", command,
                                  iq['from'].bare)
            elif 'gamereport' in iq.plugins:
                # Client is reporting end of game statistics
                try:
                    self.relay_game_report(iq['gamereport'], iq['from'])
                except:
                    traceback.print_exc()
                    logging.error("Failed to update game statistics for %s", iq['from'].bare)
        else:
            logging.error("Failed to process stanza type '%s' received from %s", iq['type'],
                          iq['from'].bare)

    def send_game_list(self, to=None):
        """Send a massive stanza with the whole game list.

        If no target is passed the gamelist is broadcasted to all
        clients.

        Arguments:
            to (sleekxmpp.xmlstream.jid.JID): Player to send the game
                                              list to. If None, the
                                              game list will be
                                              broadcasted
        """
        games = self.games.get_all_games()
        if not to:
            for jid in list(self.nicks):
                iq = self.make_iq_result(ito=jid)
                stanza = GameListXmppPlugin()
                # Pull games and add each to the stanza
                for jids in games:
                    stanza.add_game(games[jids])
                iq.set_payload(stanza)

                try:
                    iq.send(block=False, now=True)
                except:
                    logging.error("Failed to send game list")

                return

        if str(to) not in self.nicks:
            logging.error("No player with the XmPP ID '%s' known to send gamelist to.",
                          str(to))
            return

        iq = self.make_iq_result(ito=to)
        stanza = GameListXmppPlugin()
        # Pull games and add each to the stanza
        for jids in games:
            stanza.add_game(games[jids])
        iq.set_payload(stanza)

        try:
            iq.send(block=False, now=True)
        except:
            logging.error("Failed to send game list")

    def relay_board_list_request(self, recipient, player):
        """Send a boardListRequest to EcheLOn.

        Arguments:
            recipient (str): JID of the ratings bot
            player (sleekxmpp.xmlstream.jid.JID): Player who requested
                                                  the board list

        """
        if recipient not in self.nicks:
            self.warn_ratings_bot_offline()
            return

        iq = self.make_iq_get(ito=recipient)
        stanza = BoardListXmppPlugin()
        stanza.add_command('getleaderboard')
        stanza.add_recipient(player)
        iq.set_payload(stanza)

        try:
            iq.send(block=False, now=True)
        except:
            logging.error("Failed to send leaderboard list request")

    def relay_rating_list_request(self, recipient):
        """Send a ratingListRequest to EcheLOn.

        Arguments:
            recipient (?):  JID of the ratings bot

        """
        if recipient not in self.nicks:
            self.warn_ratings_bot_offline()
            return

        iq = self.make_iq_get(ito=recipient)
        stanza = BoardListXmppPlugin()
        stanza.add_command('getratinglist')
        iq.set_payload(stanza)

        try:
            iq.send(block=False, now=True)
        except:
            logging.error("Failed to send rating list request")

    def relay_profile_request(self, recipient, player, command):
        """Send a profileRequest to EcheLOn.

        Arguments:
            recipient (?):  JID of the ratings bot
            player (sleekxmpp.xmlstream.jid.JID): ?
            command (?): ?

        """
        if recipient not in self.nicks:
            self.warn_ratings_bot_offline()
            return

        iq = self.make_iq_get(ito=recipient)
        stanza = ProfileXmppPlugin()
        stanza.add_command(command)
        stanza.add_recipient(player)
        iq.set_payload(stanza)

        try:
            iq.send(block=False, now=True)
        except:
            logging.error("Failed to send profile request")

    def relay_player_online(self, jid):
        """Tells EcheLOn that someone comes online.

        Arguments:
            jid (?): ?

        """
        to = self.ratings_bot
        if to not in self.nicks:
            return

        iq = self.make_iq_set(ito=to)
        stanza = PlayerXmppPlugin()
        stanza.add_player_online(jid)
        iq.set_payload(stanza)

        try:
            iq.send(block=False, now=True)
        except:
            logging.error("Failed to send player muc online")

    def relay_game_report(self, data, sender):
        """Relay a game report to EcheLOn."""
        to = self.ratings_bot
        if to not in self.nicks:
            self.warn_ratings_bot_offline()
            return

        iq = self.make_iq_set(ito=to)
        stanza = GameReportXmppPlugin()
        stanza.add_game(data)
        stanza.add_sender(sender)
        iq.set_payload(stanza)

        try:
            iq.send(block=False, now=True)
        except:
            logging.error("Failed to send game report request")

    def relay_board_list(self, board_list, to=None):
        """Send the whole leaderboard list.

        If no target is passed the boardlist is broadcasted to all
        clients.
        """
        iq = self.make_iq_result(ito=to)
        # for i in board:
        #     stanza.addItem(board[i]['name'], board[i]['rating'])
        # stanza.addCommand('boardlist')
        iq.set_payload(board_list)

        if not to:
            # Rating List
            for jid in list(self.nicks):
                iq['to'] = jid
                try:
                    iq.send(block=False, now=True)
                except:
                    logging.error("Failed to send rating list")
        else:
            # Leaderboard
            if str(to) not in self.nicks:
                logging.error("No player with the XMPP ID '%s' known to send board list to",
                              str(to))
                return
            try:
                iq.send(block=False, now=True)
            except:
                logging.error("Failed to send leaderboard list")

    def relay_profile(self, data, player, to):  # pylint: disable=unused-argument
        """Send the player profile to a specified target."""
        if not to:
            logging.error("Failed to send profile, target unspecified")
            return

        iq = self.make_iq_result(ito=to)
        iq.set_payload(data)

        if str(to) not in self.nicks:
            logging.error("No player with the XmPP ID '%s' known to send profile to", str(to))
            return

        try:
            iq.send(block=False, now=True)
        except:
            traceback.print_exc()
            logging.error("Failed to send profile")

    def warn_ratings_bot_offline(self):
        """Warn if the ratings bot is offline."""
        if not self.ratings_bot_warned:
            logging.warning("Ratings bot '%s' is offline", str(self.ratings_bot))
            self.ratings_bot_warned = True


def main():
    """Entry point a console script."""
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description="XpartaMuPP - XMPP Multiplayer Game Manager")

    log_settings = parser.add_mutually_exclusive_group()
    log_settings.add_argument('-q', '--quiet', help='only log errors', action='store_const',
                              dest='loglevel', const=logging.ERROR)
    log_settings.add_argument('-d', '--debug', help='log debug messages', action='store_const',
                              dest='loglevel', const=logging.DEBUG)
    log_settings.add_argument('-v', '--verbose', help='log more informative messages',
                              action='store_const', dest='loglevel', const=logging.INFO)
    log_settings.set_defaults(loglevel=logging.WARNING)

    parser.add_argument('-m', '--domain', help='XMPP server to connect to',
                        default="lobby.wildfiregames.com")
    parser.add_argument('-l', '--login', help='username for login', default="xpartamupp")
    parser.add_argument('-p', '--password', help='password for login', default="XXXXXX")
    parser.add_argument('-n', '--nickname', help='nickname shown to players', default="WFGbot")
    parser.add_argument('-r', '--room', help='XMPP MUC room to join', default="arena")
    parser.add_argument('-e', '--elo', help='username of the rating bot', default="disabled")

    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel,
                        format='%(asctime)s        %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    xmpp = XpartaMuPP(args.login + '@' + args.domain + '/CC', args.password,
                      args.room + '@conference.' + args.domain, args.nickname,
                      args.elo + '@' + args.domain + '/CC')
    xmpp.register_plugin('xep_0030')  # Service Discovery
    xmpp.register_plugin('xep_0004')  # Data Forms
    xmpp.register_plugin('xep_0045')  # Multi-User Chat    # used
    xmpp.register_plugin('xep_0060')  # PubSub
    xmpp.register_plugin('xep_0199')  # XMPP Ping

    if xmpp.connect():
        xmpp.process(threaded=False)
    else:
        logging.error("Unable to connect")


if __name__ == '__main__':
    main()

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


class GameList():
    """Class to tracks all games in the lobby."""

    def __init__(self):
        self.game_list = {}

    def add_game(self, jid, data):
        """Add a game."""
        data['players-init'] = data['players']
        data['nbp-init'] = data['nbp']
        data['state'] = 'init'
        self.game_list[str(jid)] = data

    def remove_game(self, jid):
        """Remove a game attached to a JID."""
        del self.game_list[str(jid)]

    def get_all_games(self):
        """Return all games."""
        return self.game_list

    def change_game_state(self, jid, data):
        """Switch game state between running and waiting."""
        jid = str(jid)
        if jid in self.game_list:
            if self.game_list[jid]['nbp-init'] > data['nbp']:
                logging.debug("change game (%s) state from %s to %s", jid,
                              self.game_list[jid]['state'], 'waiting')
                self.game_list[jid]['state'] = 'waiting'
            else:
                logging.debug("change game (%s) state from %s to %s", jid,
                              self.game_list[jid]['state'], 'running')
                self.game_list[jid]['state'] = 'running'
            self.game_list[jid]['nbp'] = data['nbp']
            self.game_list[jid]['players'] = data['players']
            if 'startTime' not in self.game_list[jid]:
                self.game_list[jid]['startTime'] = str(round(time.time()))


class PlayerXmppPlugin(ElementBase):
    """Class for custom player stanza extension."""

    name = 'query'
    namespace = 'jabber:iq:player'
    interfaces = set(('online'))
    sub_interfaces = interfaces
    plugin_attrib = 'player'

    def add_player_online(self, player):
        self.xml.append(ET.fromstring("<online>%s</online>" % player))


class BoardListXmppPlugin(ElementBase):
    """Class for custom boardlist and ratinglist stanza extension."""

    name = 'query'
    namespace = 'jabber:iq:boardlist'
    interfaces = set(('board', 'command', 'recipient'))
    sub_interfaces = interfaces
    plugin_attrib = 'boardlist'

    def add_command(self, command):
        self.xml.append(ET.fromstring("<command>%s</command>" % command))

    def add_recipient(self, recipient):
        self.xml.append(ET.fromstring("<recipient>%s</recipient>" % recipient))

    def add_item(self, name, rating):
        self.xml.append(ET.Element("board", {"name": name, "rating": rating}))


class GameReportXmppPlugin(ElementBase):
    """Class for custom gamereport stanza extension."""

    name = 'report'
    namespace = 'jabber:iq:gamereport'
    plugin_attrib = 'gamereport'
    interfaces = ('game', 'sender')
    sub_interfaces = interfaces

    def add_sender(self, sender):
        self.xml.append(ET.fromstring("<sender>%s</sender>" % sender))

    def add_game(self, gr):
        self.xml.append(ET.fromstring(str(gr)).find('{%s}game' % self.namespace))

    def get_game(self):
        """Required to parse incoming stanzas with this extension."""
        game = self.xml.find('{%s}game' % self.namespace)
        data = {}
        for key, item in game.items():
            data[key] = item
        return data


class ProfileXmppPlugin(ElementBase):
    """Class for custom profile."""

    name = 'query'
    namespace = 'jabber:iq:profile'
    interfaces = set(('profile', 'command', 'recipient'))
    sub_interfaces = interfaces
    plugin_attrib = 'profile'

    def add_command(self, command):
        self.xml.append(ET.fromstring("<command>%s</command>" % command))

    def add_recipient(self, recipient):
        self.xml.append(ET.fromstring("<recipient>%s</recipient>" % recipient))

    def add_item(self, player, rating, highest_rating, rank, total_games_played, wins, losses):
        item_xml = ET.Element("profile", {"player": player, "rating": rating,
                                          "highestRating": highest_rating, "rank": rank,
                                          "totalGamesPlayed": total_games_played, "wins": wins,
                                          "losses": losses})
        self.xml.append(item_xml)


class GameListXmppPlugin(ElementBase):
    """Class for custom gamelist stanza extension."""

    name = 'query'
    namespace = 'jabber:iq:gamelist'
    interfaces = set(('game', 'command'))
    sub_interfaces = interfaces
    plugin_attrib = 'gamelist'

    def add_game(self, data):
        self.xml.append(ET.Element("game", data))

    def get_game(self):
        """Required to parse incoming stanzas with this extension."""
        game = self.xml.find('{%s}game' % self.namespace)
        data = {}
        for key, item in game.items():
            data[key] = item
        return data


class XpartaMuPP(sleekxmpp.ClientXMPP):
    """Main class which handles IQ data and sends new data."""

    def __init__(self, sjid, password, room, nick, ratingsbot):
        sleekxmpp.ClientXMPP.__init__(self, sjid, password)
        self.sjid = sjid
        self.room = room
        self.nick = nick
        self.ratings_bot_warned = False

        self.ratings_bot = ratingsbot
        # Game collection
        self.game_list = GameList()

        # Store mapping of nicks and XmppIDs, attached via presence stanza
        self.nicks = {}

        self.lastLeft = ""

        register_stanza_plugin(Iq, PlayerXmppPlugin)
        register_stanza_plugin(Iq, GameListXmppPlugin)
        register_stanza_plugin(Iq, BoardListXmppPlugin)
        register_stanza_plugin(Iq, GameReportXmppPlugin)
        register_stanza_plugin(Iq, ProfileXmppPlugin)

        self.register_handler(Callback('Iq Player', StanzaPath('iq/player'), self.iqhandler,
                                       instream=True))
        self.register_handler(Callback('Iq Gamelist', StanzaPath('iq/gamelist'), self.iqhandler,
                                       instream=True))
        self.register_handler(Callback('Iq Boardlist', StanzaPath('iq/boardlist'), self.iqhandler,
                                       instream=True))
        self.register_handler(Callback('Iq GameReport', StanzaPath('iq/gamereport'),
                                       self.iqhandler, instream=True))
        self.register_handler(Callback('Iq Profile', StanzaPath('iq/profile'), self.iqhandler,
                                       instream=True))

        self.add_event_handler("session_start", self.start)
        self.add_event_handler("muc::%s::got_online" % self.room, self.muc_online)
        self.add_event_handler("muc::%s::got_offline" % self.room, self.muc_offline)
        self.add_event_handler("groupchat_message", self.muc_message)

    def start(self, event):
        """Process the session_start event."""
        self.plugin['xep_0045'].joinMUC(self.room, self.nick)
        self.send_presence()
        self.get_roster()
        logging.info("XpartaMuPP started")

    def muc_online(self, presence):
        """Process presence stanza from a chat room."""
        if self.ratings_bot in self.nicks:
            self.relay_rating_list_request(self.ratings_bot)
        self.relay_player_online(presence['muc']['jid'])
        if presence['muc']['nick'] != self.nick:
            # If it doesn't already exist, store player JID mapped to their nick.
            if str(presence['muc']['jid']) not in self.nicks:
                self.nicks[str(presence['muc']['jid'])] = presence['muc']['nick']
            # Check the jid isn't already in the lobby.
            # Send Gamelist to new player.
            self.send_game_list(presence['muc']['jid'])
            logging.debug("Client '%s' connected with a nick of '%s'.", presence['muc']['jid'],
                          presence['muc']['nick'])

    def muc_offline(self, presence):
        """Process presence stanza from a chat room."""
        # Clean up after a player leaves
        if presence['muc']['nick'] != self.nick:
            # Delete any games they were hosting.
            for jid in self.game_list.get_all_games():
                if jid == str(presence['muc']['jid']):
                    self.game_list.remove_game(jid)
                    self.send_game_list()
                    break
            # Remove them from the local player list.
            self.lastLeft = str(presence['muc']['jid'])
            if str(presence['muc']['jid']) in self.nicks:
                del self.nicks[str(presence['muc']['jid'])]
        if presence['muc']['nick'] == self.ratings_bot:
            self.ratings_bot_warned = False

    def muc_message(self, msg):
        """Process new messages from the chatroom."""
        if msg['mucnick'] != self.nick and self.nick.lower() in msg['body'].lower():
            self.send_message(mto=msg['from'].bare,
                              mbody="I am the administrative bot in this lobby and cannot "
                                    "participate in any games.",
                              mtype='groupchat')

    def iqhandler(self, iq):
        """Handle the custom stanzas.

        This method should be very robust because we could receive anything
        """
        if iq['type'] == 'error':
            logging.error('iqhandler error' + iq['error']['condition'])
            #self.disconnect()
        elif iq['type'] == 'get':
            # Request lists.
            # Send lists/register on leaderboard; depreciated once muc_online
            #  can send lists/register automatically on joining the room.
            if 'boardlist' in iq.plugins:
                command = iq['boardlist']['command']
                try:
                    self.relay_board_list_request(iq['from'])
                except:
                    traceback.print_exc()
                    logging.error("Failed to process leaderboardlist request from %s",
                                  iq['from'].bare)
            elif 'profile' in iq.plugins:
                command = iq['profile']['command']
                try:
                    self.relay_profile_request(iq['from'], command)
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
                        self.game_list.add_game(iq['from'], iq['gamelist']['game'])
                        self.send_game_list()
                    except:
                        traceback.print_exc()
                        logging.error("Failed to process game registration data")
                elif command == 'unregister':
                    # Remove game
                    try:
                        self.game_list.remove_game(iq['from'])
                        self.send_game_list()
                    except:
                        traceback.print_exc()
                        logging.error("Failed to process game unregistration data")

                elif command == 'changestate':
                    # Change game status (waiting/running)
                    try:
                        self.game_list.change_game_state(iq['from'], iq['gamelist']['game'])
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

    def send_game_list(self, to=""):
        """Send a massive stanza with the whole game list.

        If no target is passed the gamelist is broadcasted to all
        clients.
        """
        games = self.game_list.get_all_games()
        if to == "":
            for jid in list(self.nicks):
                stz = GameListXmppPlugin()

                # Pull games and add each to the stanza
                for jids in games:
                    g = games[jids]
                    stz.add_game(g)

                # Set additional IQ attributes
                iq = self.Iq()
                iq['type'] = 'result'
                iq['to'] = jid
                iq.setPayload(stz)

                # Try sending the stanza
                try:
                    iq.send(block=False, now=True)
                except:
                    logging.error("Failed to send game list")
        else:
            # Check recipient exists
            if str(to) not in self.nicks:
                logging.error("No player with the XmPP ID '%s' known to send gamelist to.",
                              str(to))
                return
            stz = GameListXmppPlugin()

            # Pull games and add each to the stanza
            for jids in games:
                g = games[jids]
                stz.add_game(g)

            # Set additional IQ attributes
            iq = self.Iq()
            iq['type'] = 'result'
            iq['to'] = to
            iq.setPayload(stz)

            # Try sending the stanza
            try:
                iq.send(block=False, now=True)
            except:
                logging.error("Failed to send game list")

    def relay_board_list_request(self, recipient):
        """Send a boardListRequest to EcheLOn."""
        to = self.ratings_bot
        if to not in self.nicks:
            self.warn_ratings_bot_offline()
            return
        stz = BoardListXmppPlugin()
        iq = self.Iq()
        iq['type'] = 'get'
        stz.add_command('getleaderboard')
        stz.add_recipient(recipient)
        iq.setPayload(stz)
        # Set additional IQ attributes
        iq['to'] = to
        # Try sending the stanza
        try:
            iq.send(block=False, now=True)
        except:
            logging.error("Failed to send leaderboard list request")

    def relay_rating_list_request(self, recipient):
        """Send a ratingListRequest to EcheLOn."""
        to = self.ratings_bot
        if to not in self.nicks:
            self.warn_ratings_bot_offline()
            return
        stz = BoardListXmppPlugin()
        iq = self.Iq()
        iq['type'] = 'get'
        stz.add_command('getratinglist')
        iq.setPayload(stz)
        ## Set additional IQ attributes
        iq['to'] = to
        ## Try sending the stanza
        try:
            iq.send(block=False, now=True)
        except:
            logging.error("Failed to send rating list request")

    def relay_profile_request(self, recipient, player):
        """Send a profileRequest to EcheLOn."""
        to = self.ratings_bot
        if to not in self.nicks:
            self.warn_ratings_bot_offline()
            return
        stz = ProfileXmppPlugin()
        iq = self.Iq()
        iq['type'] = 'get'
        stz.add_command(player)
        stz.add_recipient(recipient)
        iq.setPayload(stz)
        # Set additional IQ attributes
        iq['to'] = to
        # Try sending the stanza
        try:
            iq.send(block=False, now=True)
        except:
            logging.error("Failed to send profile request")

    def relay_player_online(self, jid):
        """Tells EcheLOn that someone comes online."""
        # Check recipient exists
        to = self.ratings_bot
        if to not in self.nicks:
            return
        stz = PlayerXmppPlugin()
        iq = self.Iq()
        iq['type'] = 'set'
        stz.add_player_online(jid)
        iq.setPayload(stz)
        # Set additional IQ attributes
        iq['to'] = to
        # Try sending the stanza
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
        stz = GameReportXmppPlugin()
        stz.add_game(data)
        stz.add_sender(sender)
        iq = self.Iq()
        iq['type'] = 'set'
        iq.setPayload(stz)
        # Set additional IQ attributes
        iq['to'] = to
        # Try sending the stanza
        try:
            iq.send(block=False, now=True)
        except:
            logging.error("Failed to send game report request")

    def relay_board_list(self, board_list, to=""):
        """Send the whole leaderboard list.

        If no target is passed the boardlist is broadcasted to all
        clients.
        """
        iq = self.Iq()
        iq['type'] = 'result'
        #for i in board:
        #    stz.addItem(board[i]['name'], board[i]['rating'])
        #stz.addCommand('boardlist')
        iq.setPayload(board_list)
        # Check recipient exists
        if to == "":
            # Rating List
            for jid in list(self.nicks):
                # Set additional IQ attributes
                iq['to'] = jid
                # Try sending the stanza
                try:
                    iq.send(block=False, now=True)
                except:
                    logging.error("Failed to send rating list")
        else:
            # Leaderboard
            if str(to) not in self.nicks:
                logging.error("No player with the XmPP ID '%s' known to send boardlist to",
                              str(to))
                return
            # Set additional IQ attributes
            iq['to'] = to
            # Try sending the stanza
            try:
                iq.send(block=False, now=True)
            except:
                logging.error("Failed to send leaderboard list")

    def relay_profile(self, data, player, to):
        """Send the player profile to a specified target."""
        if to == "":
            logging.error("Failed to send profile, target unspecified")
            return

        iq = self.Iq()
        iq['type'] = 'result'
        iq.setPayload(data)
        # Check recipient exists
        if str(to) not in self.nicks:
            logging.error("No player with the XmPP ID '%s' known to send profile to", str(to))
            return

        # Set additional IQ attributes
        iq['to'] = to

        # Try sending the stanza
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


if __name__ == '__main__':
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
                      args.ratingsbot + '@' + args.domain + '/CC')
    xmpp.register_plugin('xep_0030')  # Service Discovery
    xmpp.register_plugin('xep_0004')  # Data Forms
    xmpp.register_plugin('xep_0045')  # Multi-User Chat    # used
    xmpp.register_plugin('xep_0060')  # PubSub
    xmpp.register_plugin('xep_0199')  # XMPP Ping

    if xmpp.connect():
        xmpp.process(threaded=False)
    else:
        logging.error("Unable to connect")

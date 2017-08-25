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
import traceback

import sleekxmpp
from sleekxmpp.stanza import Iq
from sleekxmpp.xmlstream import ElementBase, register_stanza_plugin, ET
from sleekxmpp.xmlstream.handler import Callback
from sleekxmpp.xmlstream.matcher import StanzaPath
from sqlalchemy import func

from ELO import get_rating_adjustment
from LobbyRanking import session as db, Game, Player, PlayerInfo

from stanzas import BoardListXmppPlugin, GameReportXmppPlugin, ProfileXmppPlugin

# Rating that new players should be inserted into the
# database with, before they've played any games.
leaderboard_default_rating = 1200


class LeaderboardList(object):
    """Class that contains and manages leaderboard data."""

    def __init__(self, room):
        self.room = room
        self.last_rated = ""

    def get_profile(self, jid):
        """Retrieve the profile for the specified JID."""
        stats = {}
        player = db.query(Player).filter(Player.jid.ilike(str(jid)))

        if not player.first():
            return

        queried_player = player.first()
        player_id = queried_player.id
        if queried_player.rating != -1:
            stats['rating'] = str(queried_player.rating)
            rank = db.query(Player).filter(Player.rating >= queried_player.rating).count()
            stats['rank'] = str(rank)

        if queried_player.highest_rating != -1:
            stats['highestRating'] = str(queried_player.highest_rating)

        games_played = db.query(PlayerInfo).filter_by(player_id=player_id).count()
        wins = db.query(Game).filter_by(winner_id=player_id).count()
        stats['totalGamesPlayed'] = str(games_played)
        stats['wins'] = str(wins)
        stats['losses'] = str(games_played - wins)
        return stats

    def get_or_create_player(self, jid):
        """Store a player(JID) in the database if they don't yet exist.

        Return either the newly created instance of the Player model,
        or the one that already exists in the database.
        """
        players = db.query(Player).filter_by(jid=str(jid))
        if not players.first():
            player = Player(jid=str(jid), rating=-1)
            db.add(player)
            db.commit()
            return player
        return players.first()

    def remove_player(self, jid):
        """Remove a player(JID) from database.

        Returns the player that was removed, or None if that player
        didn't exist.
        """
        players = db.query(Player).filter_by(jid=jid)
        player = players.first()
        if not player:
            return None
        players.delete()
        return player

    def add_game(self, gamereport):
        """Add a game to the database.

        Add a game to the database and updates the data on a
        player(JID) from game results.
        Return the created Game object, or None if the creation failed
        for any reason.

        Side effects:
        - Inserts a new Game instance into the database.
        """
        # Discard any games still in progress.
        if any(map(lambda state: state == 'active',
                   dict.values(gamereport['playerStates']))):
            return None

        players = map(lambda jid: db.query(Player).filter(Player.jid.ilike(str(jid))).first(),
                      dict.keys(gamereport['playerStates']))

        winning_jid = list(dict.keys({jid: state for jid, state in
                                      gamereport['playerStates'].items()
                                      if state == 'won'}))[0]

        def get(stat, jid):
            return gamereport[stat][jid]

        #single_stats = {'timeElapsed', 'mapName', 'teamsLocked', 'matchID'}
        total_score_stats = {'economyScore', 'militaryScore', 'totalScore'}
        resource_stats = {'foodGathered', 'foodUsed', 'woodGathered', 'woodUsed', 'stoneGathered',
                          'stoneUsed', 'metalGathered', 'metalUsed', 'vegetarianFoodGathered',
                          'treasuresCollected', 'lootCollected', 'tributesSent',
                          'tributesReceived'}
        units_stats = {'totalUnitsTrained', 'totalUnitsLost', 'enemytotalUnitsKilled',
                       'infantryUnitsTrained', 'infantryUnitsLost', 'enemyInfantryUnitsKilled',
                       'workerUnitsTrained', 'workerUnitsLost', 'enemyWorkerUnitsKilled',
                       'femaleCitizenUnitsTrained', 'femaleCitizenUnitsLost',
                       'enemyFemaleCitizenUnitsKilled', 'cavalryUnitsTrained', 'cavalryUnitsLost',
                       'enemyCavalryUnitsKilled', 'championUnitsTrained', 'championUnitsLost',
                       'enemyChampionUnitsKilled', 'heroUnitsTrained', 'heroUnitsLost',
                       'enemyHeroUnitsKilled', 'shipUnitsTrained', 'shipUnitsLost',
                       'enemyShipUnitsKilled', 'traderUnitsTrained', 'traderUnitsLost',
                       'enemyTraderUnitsKilled'}
        buildings_stats = {'totalBuildingsConstructed', 'totalBuildingsLost',
                           'enemytotalBuildingsDestroyed', 'civCentreBuildingsConstructed',
                           'civCentreBuildingsLost', 'enemyCivCentreBuildingsDestroyed',
                           'houseBuildingsConstructed', 'houseBuildingsLost',
                           'enemyHouseBuildingsDestroyed', 'economicBuildingsConstructed',
                           'economicBuildingsLost', 'enemyEconomicBuildingsDestroyed',
                           'outpostBuildingsConstructed', 'outpostBuildingsLost',
                           'enemyOutpostBuildingsDestroyed', 'militaryBuildingsConstructed',
                           'militaryBuildingsLost', 'enemyMilitaryBuildingsDestroyed',
                           'fortressBuildingsConstructed', 'fortressBuildingsLost',
                           'enemyFortressBuildingsDestroyed', 'wonderBuildingsConstructed',
                           'wonderBuildingsLost', 'enemyWonderBuildingsDestroyed'}
        market_stats = {'woodBought', 'foodBought', 'stoneBought', 'metalBought', 'tradeIncome'}
        misc_stats = {'civs', 'teams', 'percentMapExplored'}

        stats = total_score_stats | resource_stats | units_stats | buildings_stats | market_stats \
            | misc_stats
        player_infos = []
        for player in players:
            jid = player.jid
            playerinfo = PlayerInfo(player=player)
            for reportname in stats:
                setattr(playerinfo, reportname, get(reportname, jid.lower()))
            player_infos.append(playerinfo)

        game = Game(map=gamereport['mapName'], duration=int(gamereport['timeElapsed']),
                    teamsLocked=bool(gamereport['teamsLocked']), matchID=gamereport['matchID'])
        game.players.extend(players)
        game.player_info.extend(player_infos)
        game.winner = db.query(Player).filter(Player.jid.ilike(str(winning_jid))).first()
        db.add(game)
        db.commit()
        return game

    def verify_game(self, gamereport):
        """Check whether or not the game should be rated.

        Return a boolean based on whether the game should be rated.
        Here, we can specify the criteria for rated games.
        """
        winning_jids = list(dict.keys({jid: state for jid, state in
                                      gamereport['playerStates'].items()
                                      if state == 'won'}))
        # We only support 1v1s right now. TODO: Support team games.
        if len(winning_jids) * 2 > len(dict.keys(gamereport['playerStates'])):
            # More than half the people have won. This is not a balanced team game or duel.
            return False
        if len(dict.keys(gamereport['playerStates'])) != 2:
            return False
        return True

    def rate_game(self, game):
        """Update player ratings based on game outcome.

        Take a game with 2 players and alters their ratings based on
        the result of the game.

        Returns self.

        Side effects:
        - Changes the game's players' ratings in the database.
        """
        player1 = game.players[0]
        player2 = game.players[1]
        # TODO: Support draws. Since it's impossible to draw in the game currently,
        # the database model, and therefore this code, requires a winner.
        # The Elo implementation does not, however.
        result = 1 if player1 == game.winner else -1
        # Player's ratings are -1 unless they have played a rated game.
        if player1.rating == -1:
            player1.rating = leaderboard_default_rating
        if player2.rating == -1:
            player2.rating = leaderboard_default_rating

        rating_adjustment1 = int(get_rating_adjustment(player1.rating, player2.rating,
                                                       len(player1.games), len(player2.games),
                                                       result))
        rating_adjustment2 = int(get_rating_adjustment(player2.rating, player1.rating,
                                                       len(player2.games), len(player1.games),
                                                       result * -1))
        if result == 1:
            result_qualitative = "won"
        elif result == 0:
            result_qualitative = "drew"
        else:
            result_qualitative = "lost"
        name1 = '@'.join(player1.jid.split('@')[:-1])
        name2 = '@'.join(player2.jid.split('@')[:-1])
        self.last_rated = "A rated game has ended. %s %s against %s. Rating Adjustment: %s (%s " \
                          "-> %s) and %s (%s -> %s)." % (name1, result_qualitative, name2, name1,
                                                         player1.rating,
                                                         player1.rating + rating_adjustment1,
                                                         name2, player2.rating,
                                                         player2.rating + rating_adjustment2)
        player1.rating += rating_adjustment1
        player2.rating += rating_adjustment2
        if not player1.highest_rating:
            player1.highest_rating = -1
        if not player2.highest_rating:
            player2.highest_rating = -1
        if player1.rating > player1.highest_rating:
            player1.highest_rating = player1.rating
        if player2.rating > player2.highest_rating:
            player2.highest_rating = player2.rating
        db.commit()
        return self

    def get_last_rated_message(self):
        """Get the string of the last rated game.

        Triggers an update chat for the bot.
        """
        return self.last_rated

    def add_and_rate_game(self, gamereport):
        """Call addGame

        If the game has only two players, also calls rateGame.

        Returns the result of addGame.
        """
        game = self.add_game(gamereport)
        if game and self.verify_game(gamereport):
            self.rate_game(game)
        else:
            self.last_rated = ""
        return game

    def get_board(self):
        """Returns a dictionary of player rankings to JIDs for sending."""
        board = {}
        players = db.query(Player).filter(Player.rating != -1) \
            .order_by(Player.rating.desc()).limit(100).all()
        for rank, player in enumerate(players):  # pylint: disable=unused-variable
            board[player.jid] = {'name': '@'.join(player.jid.split('@')[:-1]),
                                 'rating': str(player.rating)}
        return board

    def get_rating_list(self, nicks):
        """Return a rating list of players currently in the lobby

        The returned list is by nick because the client can't link JID
        to nick conveniently.
        """
        ratinglist = {}
        player_filter = func.upper(Player.jid).in_([str(jid).upper() for jid in list(nicks)])
        players = db.query(Player.jid, Player.rating).filter(player_filter)
        for player in players:
            rating = str(player.rating) if player.rating != -1 else ''
            for jid in list(nicks):
                if jid.upper() == player.jid.upper():
                    ratinglist[nicks[jid]] = {'name': nicks[jid], 'rating': rating}
                    break
        return ratinglist


class ReportManager(object):
    """Class which manages different game reports from clients.

    Also calls leaderboard functions as appropriate.
    """

    def __init__(self, leaderboard):
        self.leaderboard = leaderboard
        self.interim_report_tracker = []
        self.interim_jid_tracker = []

    def add_report(self, jid, raw_game_report):
        """Add a game to the interface between a raw report and the leaderboard database."""
        # cleanRawGameReport is a copy of rawGameReport with all reporter specific information
        # removed.
        clean_raw_game_report = raw_game_report.copy()
        del clean_raw_game_report["playerID"]

        if clean_raw_game_report not in self.interim_report_tracker:
            # Store the game.
            self.interim_report_tracker.append(clean_raw_game_report)
            # Initilize the JIDs and store the initial JID.
            num_players = self.get_num_players(raw_game_report)
            jids = [None] * num_players
            if num_players - int(raw_game_report["playerID"]) > -1:
                jids[int(raw_game_report["playerID"]) - 1] = str(jid).lower()
            self.interim_jid_tracker.append(jids)
        else:
            # We get the index at which the JIDs coresponding to the game are stored.
            index = self.interim_report_tracker.index(clean_raw_game_report)
            # We insert the new report JID into the ascending list of JIDs for the game.
            jids = self.interim_jid_tracker[index]
            if len(jids) - int(raw_game_report["playerID"]) > -1:
                jids[int(raw_game_report["playerID"]) - 1] = str(jid).lower()
            self.interim_jid_tracker[index] = jids

        self.check_full()

    def expand_report(self, raw_game_report, jids):
        """Re-formats a raw game into Python data structures.

        JIDs are left empty.

        Returns a processed gameReport of type dict.
        """
        processed_game_report = {}
        for key in raw_game_report:
            if raw_game_report[key].find(",") == -1:
                processed_game_report[key] = raw_game_report[key]
            else:
                split = raw_game_report[key].split(",")
                # Remove the false split positive.
                split.pop()
                stat_to_jid = {}
                for i, part in enumerate(split):
                    stat_to_jid[jids[i]] = part
                processed_game_report[key] = stat_to_jid
        return processed_game_report

    def check_full(self):
        """Check if enough reports are present to add game to the leaderboard.

        Searches internal database to check if enough reports have
        been submitted to add a game to the leaderboard. If so, the
        report will be interpolated and addAndRateGame will be called
        with the result.
        """
        i = 0
        length = len(self.interim_report_tracker)
        while i < length:
            num_players = self.get_num_players(self.interim_report_tracker[i])
            num_reports = 0
            for jid in self.interim_jid_tracker[i]:
                if jid is not None:
                    num_reports += 1
            if num_reports == num_players:
                try:
                    self.leaderboard.add_and_rate_game(
                        self.expand_report(self.interim_report_tracker[i],
                                           self.interim_jid_tracker[i]))
                except:
                    traceback.print_exc()
                del self.interim_jid_tracker[i]
                del self.interim_report_tracker[i]
                length -= 1
            else:
                i += 1
                self.leaderboard.last_rated = ""

    def get_num_players(self, raw_game_report):
        """Compute the number of players in a raw gameReport.

        Returns int, the number of players.
        """
        # Find a key in the report which holds values for multiple players.
        for key in raw_game_report:
            if raw_game_report[key].find(",") != -1:
                # Count the number of values, minus one for the false split positive.
                return len(raw_game_report[key].split(",")) - 1
        # Return -1 in case of failure.
        return -1


class PlayerXmppPlugin(ElementBase):
    """Class for custom player stanza extension."""

    name = 'query'
    namespace = 'jabber:iq:player'
    interfaces = {'game', 'online'}
    sub_interfaces = interfaces
    plugin_attrib = 'player'

    def add_player_online(self, player):
        self.xml.append(ET.fromstring("<player>%s</player>" % player))


class EcheLOn(sleekxmpp.ClientXMPP):
    """Main class which handles IQ data and sends new data."""

    def __init__(self, sjid, password, room, nick):
        sleekxmpp.ClientXMPP.__init__(self, sjid, password)
        self.sjid = sjid
        self.room = room
        self.nick = nick

        # Init leaderboard object
        self.leaderboard = LeaderboardList(room)

        # gameReport to leaderboard abstraction
        self.report_manager = ReportManager(self.leaderboard)

        # Store mapping of nicks and XmppIDs, attached via presence stanza
        self.nicks = {}

        register_stanza_plugin(Iq, PlayerXmppPlugin)
        register_stanza_plugin(Iq, BoardListXmppPlugin)
        register_stanza_plugin(Iq, GameReportXmppPlugin)
        register_stanza_plugin(Iq, ProfileXmppPlugin)

        self.register_handler(Callback('Iq Player', StanzaPath('iq/player'), self.iqhandler,
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

    def start(self, event):
        """Join MUC channel and announce presence."""
        self.plugin['xep_0045'].joinMUC(self.room, self.nick)
        self.send_presence()
        self.get_roster()
        logging.info("EcheLOn started")

    def muc_online(self, presence):
        """Add joining players to the list of players."""
        nick = str(presence['muc']['nick'])
        jid = str(presence['muc']['jid'])

        if nick != self.nick:
            if jid not in self.nicks:
                self.nicks[jid] = nick
            logging.debug("Client '%s' connected with a nick of '%s'.", jid, nick)

    def muc_offline(self, presence):
        """Remove leaving players from the list of players."""
        nick = str(presence['muc']['nick'])
        jid = str(presence['muc']['jid'])

        if nick != self.nick:
            if jid in self.nicks:
                del self.nicks[jid]

    def iqhandler(self, iq):
        """Handle the custom stanzas.

        This method should be very robust because we could receive anything
        """
        if iq['type'] == 'error':
            logging.error('iqhandler error' + iq['error']['condition'])
            #self.disconnect()
        elif iq['type'] == 'get':
            # Request lists.
            if 'boardlist' in iq.plugins:
                command = iq['boardlist']['command']
                recipient = iq['boardlist']['recipient']
                if command == 'getleaderboard':
                    try:
                        self.leaderboard.get_or_create_player(iq['from'])
                        self.send_board_list(iq['from'], recipient)
                    except:
                        traceback.print_exc()
                        logging.error("Failed to process leaderboardlist request from %s",
                                      iq['from'].bare)
                elif command == 'getratinglist':
                    try:
                        self.send_rating_list(iq['from'])
                    except:
                        traceback.print_exc()
                else:
                    logging.error("Failed to process boardlist request from %s", iq['from'].bare)
            elif 'profile' in iq.plugins:
                command = iq['profile']['command']
                recipient = iq['profile']['recipient']
                try:
                    self.send_profile(iq['from'], command, recipient)
                except:
                    try:
                        self.send_profile_not_found(iq['from'], command, recipient)
                    except:
                        logging.debug("No record found for %s", command)
            else:
                logging.error("Unknown 'get' type stanza request from %s", iq['from'].bare)
        elif iq['type'] == 'result':
            # Iq successfully received
            pass
        elif iq['type'] == 'set':
            if 'gamereport' in iq.plugins:
                # Client is reporting end of game statistics
                try:
                    self.report_manager.add_report(iq['gamereport']['sender'],
                                                   iq['gamereport']['game'])
                    if self.leaderboard.get_last_rated_message() != "":
                        self.send_message(mto=self.room,
                                          mbody=self.leaderboard.get_last_rated_message(),
                                          mtype="groupchat", mnick=self.nick)
                        self.send_rating_list(iq['from'])
                except:
                    traceback.print_exc()
                    logging.error("Failed to update game statistics for %s", iq['from'].bare)
            elif 'player' in iq.plugins:
                player = iq['player']['online']
                #try:
                self.leaderboard.get_or_create_player(player)
                #except:
                #    logging.debug("Could not create new user %s", player)
        else:
            logging.error("Failed to process stanza type '%s' received from %s",
                          iq['type'], iq['from'].bare)

    def send_board_list(self, to, recipient):
        """Send the whole leaderboard list.

        If no target is passed the boardlist is broadcasted
        to all clients.
        """
        # Pull leaderboard data and add it to the stanza
        board = self.leaderboard.get_board()

        iq = self.make_iq_result(ito=to)
        stanza = BoardListXmppPlugin()
        for i in board:
            stanza.add_item(board[i]['name'], board[i]['rating'])
        stanza.add_command('boardlist')
        stanza.add_recipient(recipient)
        iq.set_payload(stanza)

        if str(to) not in self.nicks:
            logging.error("No player with the XmPP ID '%s' known to send boardlist to", str(to))
            return

        try:
            iq.send(block=False, now=True)
        except:
            logging.error("Failed to send leaderboard list")

    def send_rating_list(self, to):
        """Send the rating list."""
        # Pull rating list data and add it to the stanza
        ratinglist = self.leaderboard.get_rating_list(self.nicks)

        iq = self.make_iq_result(ito=to)
        stanza = BoardListXmppPlugin()
        for i in ratinglist:
            stanza.add_item(ratinglist[i]['name'], ratinglist[i]['rating'])
        stanza.add_command('ratinglist')
        iq.set_payload(stanza)

        if str(to) not in self.nicks:
            logging.error("No player with the XmPP ID '%s' known to send ratinglist to", str(to))
            return

        try:
            iq.send(block=False, now=True)
        except:
            logging.error("Failed to send rating list")

    def send_profile(self, to, player, recipient):
        """Send the player profile to a specified target."""
        if not to:
            logging.error("Failed to send profile")
            return

        online = False
        # Pull stats and add it to the stanza
        for jid in list(self.nicks):
            if self.nicks[jid] == player:
                stats = self.leaderboard.get_profile(jid)
                online = True
                break

        if not online:
            stats = self.leaderboard.get_profile(player + "@" + str(recipient).split('@')[1])

        iq = self.make_iq_result(ito=to)
        stanza = ProfileXmppPlugin()
        stanza.add_item(player, stats['rating'], stats['highestRating'], stats['rank'],
                        stats['totalGamesPlayed'], stats['wins'], stats['losses'])
        stanza.add_command(player)
        stanza.add_recipient(recipient)
        iq.set_payload(stanza)

        if str(to) not in self.nicks:
            logging.error("No player with the XmPP ID '%s' known to send profile to", str(to))
            return

        try:
            iq.send(block=False, now=True)
        except:
            traceback.print_exc()
            logging.error("Failed to send profile")

    def send_profile_not_found(self, to, player, recipient):
        """Send a profile not-found error to a specified target."""
        iq = self.make_iq_result(ito=to)
        stanza = ProfileXmppPlugin()
        stanza.add_item(player, str(-2))
        stanza.add_command(player)
        stanza.add_recipient(recipient)
        iq.set_payload(stanza)

        if str(to) not in self.nicks:
            logging.error("No player with the XmPP ID '%s' known to send profile to", str(to))
            return

        try:
            iq.send(block=False, now=True)
        except:
            traceback.print_exc()
            logging.error("Failed to send profile")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description="EcheLOn - XMPP Rating Bot")

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
    parser.add_argument('-l', '--login', help='username for login', default="EcheLOn")
    parser.add_argument('-p', '--password', help='password for login', default="XXXXXX")
    parser.add_argument('-n', '--nickname', help='nickname shown to players', default="Ratings")
    parser.add_argument('-r', '--room', help='XMPP MUC room to join', default="arena")

    args = parser.parse_args()

    logging.basicConfig(level=args.log_level,
                        format='%(asctime)s        %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    xmpp = EcheLOn(args.login + '@' + args.domain + '/CC', args.password,
                   args.room + '@conference.' + args.domain, args.nickname)
    xmpp.register_plugin('xep_0030')  # Service Discovery
    xmpp.register_plugin('xep_0004')  # Data Forms
    xmpp.register_plugin('xep_0045')  # Multi-User Chat    # used
    xmpp.register_plugin('xep_0060')  # PubSub
    xmpp.register_plugin('xep_0199')  # XMPP Ping

    if xmpp.connect():
        xmpp.process(threaded=False)
    else:
        logging.error("Unable to connect")

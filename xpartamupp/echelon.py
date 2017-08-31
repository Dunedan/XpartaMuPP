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

import sleekxmpp
from sleekxmpp.stanza import Iq
from sleekxmpp.xmlstream import register_stanza_plugin
from sleekxmpp.xmlstream.handler import Callback
from sleekxmpp.xmlstream.matcher import StanzaPath
import sqlalchemy
from sqlalchemy.orm import sessionmaker

from xpartamupp.elo import get_rating_adjustment
from xpartamupp.lobby_ranking import Game, Player, PlayerInfo

from xpartamupp.stanzas import BoardListXmppPlugin, GameReportXmppPlugin, ProfileXmppPlugin

# Rating that new players should be inserted into the
# database with, before they've played any games.
LEADERBOARD_DEFAULT_RATING = 1200


class Leaderboard(object):
    """Class that provides and manages leaderboard data."""

    def __init__(self):
        """Initialize the leaderboard."""
        self.last_rated = ""

        engine = sqlalchemy.create_engine('sqlite:///lobby_rankings.sqlite3')
        self.db = sessionmaker(bind=engine)()

    def get_profile(self, jid):
        """Get the leaderboard profile for the specified player.

        Arguments:
            jid (str): JID of the player to retrieve the profile for

        Returns:
            dict with statistics about the requested player or None if
            the player isn't known

        """
        stats = {}
        player = self.db.query(Player).filter(Player.jid.ilike(jid)).first()

        if not player:
            logging.debug("Couldn't find profile for player %s", jid)
            return {}

        if player.rating != -1:
            stats['rating'] = player.rating
            rank = self.db.query(Player).filter(Player.rating >= player.rating).count()
            stats['rank'] = rank

        if player.highest_rating != -1:
            stats['highestRating'] = player.highest_rating

        games_played = self.db.query(PlayerInfo).filter_by(player_id=player.id).count()
        wins = self.db.query(Game).filter_by(winner_id=player.id).count()
        stats['totalGamesPlayed'] = games_played
        stats['wins'] = wins
        stats['losses'] = games_played - wins
        return stats

    def get_or_create_player(self, jid):
        """Get a player from the leaderboard database.

        Get player information from the leaderboard database and
        create him first, if he doesn't exist yet.

        Arguments:
            jid (str): JID of the player to get

        Returns:
            Player instance representing the player specified by the
            supplied JID

        """
        player = self.db.query(Player).filter_by(jid=jid).first()
        if player:
            return player

        player = Player(jid=jid, rating=-1)
        self.db.add(player)
        self.db.commit()
        logging.debug("Created player %s", jid)
        return player

    def remove_player(self, jid):
        """Remove a player from leaderboard database.

        Arguments:
            jid (str): JID of the player to remove

        Returns:
            Player that was removed or None if that player didn't
            exist

        """
        player = self.db.query(Player).filter_by(jid=jid).first()
        if player:
            player.delete()
            logging.debug("Deleted player %s", jid)
            return player

        return None

    def _add_game(self, game_report):
        """Add a game to the database.

        Add a game to the database and update the data on a
        player from game results.

        Arguments:
            game_report (dict): a report about a game

        Returns:
            Game object for the created game or None if the creation
            failed for any reason.

        """
        # Discard any games still in progress.
        if any(map(lambda state: state == 'active', dict.values(game_report['playerStates']))):
            return None

        players = map(lambda jid: self.db.query(Player).filter(Player.jid.ilike(str(jid))).first(),
                      dict.keys(game_report['playerStates']))

        winning_jid = [jid for jid, state in game_report['playerStates'].items()
                       if state == 'won'][0]

        # single_stats = {'timeElapsed', 'mapName', 'teamsLocked', 'matchID'}
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
            player_info = PlayerInfo(player=player)
            for report_name in stats:
                setattr(player_info, report_name, game_report[report_name][jid.lower()])
            player_infos.append(player_info)

        game = Game(map=game_report['mapName'], duration=int(game_report['timeElapsed']),
                    teamsLocked=bool(game_report['teamsLocked']), matchID=game_report['matchID'])
        game.players.extend(players)
        game.player_info.extend(player_infos)
        game.winner = self.db.query(Player).filter(Player.jid.ilike(str(winning_jid))).first()
        self.db.add(game)
        self.db.commit()
        return game

    @staticmethod
    def _verify_game(game_report):
        """Check whether or not the game should be rated.

        The criteria for rated games can be specified here.

        Arguments:
            game_report (dict): a report about a game

        Returns:
            True if the game should be rated, false otherwise.

        """
        winning_jids = [jid for jid, state in game_report['playerStates'].items()
                        if state == 'won']
        # We only support 1v1s right now.
        if len(winning_jids) > 1 or len(dict.keys(game_report['playerStates'])) != 2:
            return False
        return True

    def _rate_game(self, game):
        """Update player ratings based on game outcome.

        Take a game with 2 players and alters their ratings based on
        the result of the game.

        Adjusts the players ratings in the database.

        Arguments:
            game (Game): game to rate
        """
        player1 = game.players[0]
        player2 = game.players[1]
        # Since it's impossible to draw in the game currently, the
        # database model, and therefore this code, requires a winner.
        # The Elo implementation does not, however.
        result = 1 if player1 == game.winner else -1
        # Player's ratings are -1 unless they have played a rated game.
        if player1.rating == -1:
            player1.rating = LEADERBOARD_DEFAULT_RATING
        if player2.rating == -1:
            player2.rating = LEADERBOARD_DEFAULT_RATING

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
        self.db.commit()

    def get_last_rated_message(self):
        """Get the string of the last rated game.

        Triggers an update chat for the bot.

        Returns:
            str with the a message about a rated game

        """
        return self.last_rated

    def add_and_rate_game(self, game_report):
        """Add and rate a game.

        If the game has only two players, rate the game.

        Arguments:
            game_report (dict): a report about a game

        Returns:
             Game object

        """
        game = self._add_game(game_report)
        if game and self._verify_game(game_report):
            self._rate_game(game)
        else:
            self.last_rated = ""
        return game

    def get_board(self):
        """Return a mapping between player ratings and JIDs.

        Returns:
            dict with player JIDs and ratings

        """
        board = {}
        players = self.db.query(Player).filter(Player.rating != -1) \
            .order_by(Player.rating.desc()).limit(100).all()
        for rank, player in enumerate(players):  # pylint: disable=unused-variable
            board[player.jid] = {'name': '@'.join(player.jid.split('@')[:-1]),
                                 'rating': str(player.rating)}
        return board

    def get_rating_list(self, nicks):
        """Return a mapping between online player ratings and JIDs.

        The returned dictionary is by nick because the client can't
        link JID to nick conveniently.

        Arguments:
            nicks (dict): Players currently online

        Returns:
            dict with player nicks and ratings

        """
        ratings = {}
        player_filter = sqlalchemy.func.upper(Player.jid).in_(
            [str(jid).upper() for jid in list(nicks)])
        players = self.db.query(Player.jid, Player.rating).filter(player_filter)
        for player in players:
            rating = str(player.rating) if player.rating != -1 else ''
            for jid in list(nicks):
                if jid.upper() == player.jid.upper():
                    ratings[nicks[jid]] = {'name': nicks[jid], 'rating': rating}
                    break
        return ratings


class ReportManager(object):
    """Class which manages different game reports from clients.

    Calls leaderboard functions as appropriate.
    """

    def __init__(self, leaderboard):
        """Initialize the report manager.

        Arguments:
            leaderboard (Leaderboard): Leaderboard the manager is for

        """
        self.leaderboard = leaderboard
        self.interim_report_tracker = []
        self.interim_jid_tracker = []

    def add_report(self, jid, raw_game_report):
        """Add a game to the interface between a raw report and the leaderboard database.

        Arguments:
            jid (?): ?
            raw_game_report (?): ?

        """
        # clean_raw_game_report is a copy of raw_game_report with all
        # reporter specific information removed, so multiple reports
        # from different reporters should be identical.
        clean_raw_game_report = raw_game_report.copy()
        del clean_raw_game_report["playerID"]

        if clean_raw_game_report not in self.interim_report_tracker:
            # Store the game.
            self.interim_report_tracker.append(clean_raw_game_report)
            # Initialize the JIDs and store the initial JID.
            num_players = self._get_num_players(raw_game_report)
            jids = [None] * num_players
            if num_players - int(raw_game_report["playerID"]) > -1:
                jids[int(raw_game_report["playerID"]) - 1] = str(jid).lower()
            self.interim_jid_tracker.append(jids)
        else:
            # We get the index at which the JIDs corresponding to the
            # game are stored.
            index = self.interim_report_tracker.index(clean_raw_game_report)
            # We insert the new report JID into the ascending list of
            # JIDs for the game.
            jids = self.interim_jid_tracker[index]
            if len(jids) - int(raw_game_report["playerID"]) > -1:
                jids[int(raw_game_report["playerID"]) - 1] = str(jid).lower()
            self.interim_jid_tracker[index] = jids

        self._check_full()

    @staticmethod
    def _expand_report(raw_game_report, jids):
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

    def _check_full(self):
        """Check if enough reports are present to add game to the leaderboard.

        Searches internal database to check if all players who attended
        a game, have provided reports about it. If so, the report will
        be interpolated and rating of the game will be triggered with
        the result.
        """
        i = 0
        length = len(self.interim_report_tracker)
        while i < length:
            num_players = self._get_num_players(self.interim_report_tracker[i])
            num_reports = 0
            for jid in self.interim_jid_tracker[i]:
                if jid is not None:
                    num_reports += 1
            if num_reports == num_players:
                try:
                    self.leaderboard.add_and_rate_game(
                        self._expand_report(self.interim_report_tracker[i],
                                            self.interim_jid_tracker[i]))
                except Exception:
                    logging.exception("Failed to add and rate a game.")
                del self.interim_jid_tracker[i]
                del self.interim_report_tracker[i]
                length -= 1
            else:
                i += 1
                self.leaderboard.last_rated = ""

    @staticmethod
    def _get_num_players(raw_game_report):
        """Compute the number of players in a raw gameReport.

        Arguments:
            raw_game_report (?): ?

        Returns:
             int with the number of players in the game

        """
        # Find a key in the report which holds values for multiple
        # players.
        for key in raw_game_report:
            if raw_game_report[key].find(",") != -1:
                # Count the number of values, minus one for the false
                # split positive.
                return len(raw_game_report[key].split(",")) - 1
        # Return -1 in case of failure.
        return -1


class EcheLOn(sleekxmpp.ClientXMPP):
    """Main class which handles IQ data and sends new data."""

    def __init__(self, sjid, password, room, nick):
        """Initialize EcheLOn."""
        sleekxmpp.ClientXMPP.__init__(self, sjid, password)
        self.sjid = sjid
        self.room = room
        self.nick = nick

        self.leaderboard = Leaderboard()
        self.report_manager = ReportManager(self.leaderboard)
        # Store mapping of nicks and JIDs, attached via presence
        # stanza
        self.nicks = {}

        register_stanza_plugin(Iq, BoardListXmppPlugin)
        register_stanza_plugin(Iq, GameReportXmppPlugin)
        register_stanza_plugin(Iq, ProfileXmppPlugin)

        self.register_handler(Callback('Iq Player', StanzaPath('iq/player'),
                                       self._iq_player_handler, instream=True))
        self.register_handler(Callback('Iq Boardlist', StanzaPath('iq/boardlist'),
                                       self._iq_board_list_handler, instream=True))
        self.register_handler(Callback('Iq GameReport', StanzaPath('iq/gamereport'),
                                       self._iq_game_report_handler, instream=True))
        self.register_handler(Callback('Iq Profile', StanzaPath('iq/profile'),
                                       self._iq_profile_handler, instream=True))

        self.add_event_handler("session_start", self._session_start)
        self.add_event_handler("muc::%s::got_online" % self.room, self._muc_online)
        self.add_event_handler("muc::%s::got_offline" % self.room, self._muc_offline)

    def _session_start(self, event):  # pylint: disable=unused-argument
        """Join MUC channel and announce presence.

        Arguments:
            event (?): ?

        """
        self.plugin['xep_0045'].joinMUC(self.room, self.nick)
        self.send_presence()
        self.get_roster()
        logging.info("EcheLOn started")

    def _muc_online(self, presence):
        """Add joining players to the list of players.

        Arguments:
            presence (?): ?

        """
        nick = str(presence['muc']['nick'])
        jid = str(presence['muc']['jid'])

        if nick != self.nick:
            if jid not in self.nicks:
                self.nicks[jid] = nick
            logging.debug("Client '%s' connected with a nick of '%s'.", jid, nick)

    def _muc_offline(self, presence):
        """Remove leaving players from the list of players.

        Arguments:
            presence (?): ?

        """
        nick = str(presence['muc']['nick'])
        jid = str(presence['muc']['jid'])

        if nick != self.nick:
            if jid in self.nicks:
                del self.nicks[jid]

    def _iq_player_handler(self, iq):
        """Handle new clients announcing themselves as online."""
        if iq['type'] == 'set' and 'player' in iq.plugins:
            player = iq['player']['online']
            self.leaderboard.get_or_create_player(player)
            return

        logging.warning("Failed to process stanza type '%s' received from %s",
                        iq['type'], iq['from'].bare)

    def _iq_board_list_handler(self, iq):
        """Handle incoming leaderboard list requests."""
        if iq['type'] == 'get' and 'boardlist' in iq.plugins:
            command = iq['boardlist']['command']
            recipient = iq['boardlist']['recipient']
            if command == 'getleaderboard':
                try:
                    self.leaderboard.get_or_create_player(iq['from'])
                    self._send_leaderboard(iq['from'], recipient)
                except Exception:
                    logging.exception("Failed to process get leaderboard request from %s",
                                      iq['from'].bare)
                return
            elif command == 'getratinglist':
                try:
                    self._send_rating_list(iq['from'])
                except Exception:
                    logging.exception("Failed to send the rating list to %s", iq['from'])
                return

        logging.warning("Failed to process stanza type '%s' received from %s", iq['type'],
                        iq['from'].bare)

    def _iq_game_report_handler(self, iq):
        """Handle end of game reports from clients."""
        if iq['type'] == 'set' and 'gamereport' in iq.plugins:
            try:
                self.report_manager.add_report(iq['gamereport']['sender'],
                                               iq['gamereport']['game'])
                if self.leaderboard.get_last_rated_message() != "":
                    self.send_message(mto=self.room,
                                      mbody=self.leaderboard.get_last_rated_message(),
                                      mtype="groupchat", mnick=self.nick)
                    self._send_rating_list(iq['from'])
            except Exception:
                logging.exception("Failed to update game statistics for %s", iq['from'].bare)
            return

        logging.warning("Failed to process stanza type '%s' received from %s", iq['type'],
                        iq['from'].bare)

    def _iq_profile_handler(self, iq):
        """Handle profile requests from clients."""
        if iq['type'] == 'get' and 'profile' in iq.plugins:
            command = iq['profile']['command']
            recipient = iq['profile']['recipient']
            try:
                self._send_profile(iq['from'], command, recipient)
            except Exception:
                logging.exception("Failed to send profile about %s to %s", command, recipient)
            return

        logging.warning("Failed to process stanza type '%s' received from %s", iq['type'],
                        iq['from'].bare)

    def _send_leaderboard(self, to, recipient):
        """Send the whole leaderboard.

        If no target is passed the leaderboard is broadcasted to all
        clients.

        Arguments:
            to (sleekxmpp.xmlstream.jid.JID): sender of the get
                                              leaderboard request (can
                                              be player or XpartaMuPP)
            recipient (str): Player who requested the leaderboard
        """
        board = self.leaderboard.get_board()

        iq = self.make_iq_result(ito=to)
        stanza = BoardListXmppPlugin()
        for value in board.values():
            stanza.add_item(value['name'], value['rating'])
        stanza.add_command('boardlist')
        stanza.add_recipient(recipient)
        iq.set_payload(stanza)

        if str(to) not in self.nicks:
            logging.error("No player with the XMPP ID '%s' known to send leaderboard to", str(to))
            return

        try:
            iq.send(block=False, now=True)
        except Exception:
            logging.exception("Failed to send leaderboard")

    def _send_rating_list(self, to):
        """Send the rating list.

        Arguments:
            to (sleekxmpp.xmlstream.jid.JID): player who should receive
                                              the rating list

        """
        rating_list = self.leaderboard.get_rating_list(self.nicks)

        iq = self.make_iq_result(ito=to)
        stanza = BoardListXmppPlugin()
        for values in rating_list.values():
            stanza.add_item(values['name'], values['rating'])
        stanza.add_command('ratinglist')
        iq.set_payload(stanza)

        if str(to) not in self.nicks:
            logging.error("No player with the XMPP ID '%s' known to send rating list to", str(to))
            return

        try:
            iq.send(block=False, now=True)
        except Exception:
            logging.exception("Failed to send rating list")

    def _send_profile(self, to, player_nick, recipient):
        """Send the player profile to a specified target.

        Arguments:
            to (sleekxmpp.xmlstream.jid.JID): player who requested the
                                              profile
            player_nick (?): ?
            recipient (?): ?

        """
        player_jid = None
        for jid, nick in self.nicks.items():
            if nick == player_nick:
                player_jid = jid
                break
        if not player_jid:
            player_jid = player_nick + "@" + str(recipient).split('@')[1]

        try:
            stats = self.leaderboard.get_profile(player_jid)
        except Exception:
            logging.exception("Failed to get leaderboard profile for player %s", player_jid)
            stats = {}

        iq = self.make_iq_result(ito=to)
        stanza = ProfileXmppPlugin()
        if stats:
            stanza.add_item(player_nick, str(stats['rating']), str(stats['highestRating']),
                            str(stats['rank']), str(stats['totalGamesPlayed']), str(stats['wins']),
                            str(stats['losses']))
        else:
            stanza.add_item(player_nick, str(-2))
        stanza.add_command(player_nick)
        stanza.add_recipient(recipient)
        iq.set_payload(stanza)

        if str(to) not in self.nicks:
            logging.error("No player_nick with the XMPP ID '%s' known to send profile to", str(to))
            return

        try:
            iq.send(block=False, now=True)
        except Exception:
            logging.exception("Failed to send profile")


def main():
    """Entry point a console script."""
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


if __name__ == '__main__':
    main()

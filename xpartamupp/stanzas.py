from sleekxmpp.xmlstream import ElementBase, ET


class BoardListXmppPlugin(ElementBase):
    """Class for custom boardlist and ratinglist stanza extension."""

    name = 'query'
    namespace = 'jabber:iq:boardlist'
    interfaces = {'board', 'command', 'recipient'}
    sub_interfaces = interfaces
    plugin_attrib = 'boardlist'

    def add_command(self, command):
        """Add a command to the extension.

        Arguments:
            command (str): Command to add
        """
        self.xml.append(ET.fromstring("<command>%s</command>" % command))

    def add_recipient(self, recipient):
        """Add a recipient to the extension.

        Arguments:
            recipient (sleekxmpp.xmlstream.jid.JID): Recipient to add
        """
        self.xml.append(ET.fromstring("<recipient>%s</recipient>" % recipient))

    def add_item(self, name, rating):
        """Add an item to the extension.

        Argumnets:
            name (str): Name of the player to add
            rating (str): Rating of the player to add
        """
        self.xml.append(ET.Element("board", {"name": name, "rating": rating}))


class GameListXmppPlugin(ElementBase):
    """Class for custom gamelist stanza extension."""

    name = 'query'
    namespace = 'jabber:iq:gamelist'
    interfaces = {'game', 'command'}
    sub_interfaces = interfaces
    plugin_attrib = 'gamelist'

    def add_game(self, data):
        """Add a game to the extension.

        Arguments:
            data (?): ?
        """
        self.xml.append(ET.Element("game", data))

    def get_game(self):
        """Get game from stanza.

        Required to parse incoming stanzas with this extension.

        Returns:
            dict with game data

        """
        game = self.xml.find('{%s}game' % self.namespace)
        data = {}
        for key, item in game.items():
            data[key] = item
        return data


class GameReportXmppPlugin(ElementBase):
    """Class for custom gamereport stanza extension."""

    name = 'report'
    namespace = 'jabber:iq:gamereport'
    plugin_attrib = 'gamereport'
    interfaces = ('game', 'sender')
    sub_interfaces = interfaces

    def add_sender(self, sender):
        """Add a sender to the extension.

        Only necessary for requests forwarded by XpartaMupp to
        EcheLOn, as the actual sender will be taken for all
        others.

        Arguments:
            sender (sleekxmpp.xmlstream.jid.JID): original sending
                player of the game report

        """
        self.xml.append(ET.fromstring("<sender>%s</sender>" % sender))

    def add_game(self, game_report):
        """Add a game to the extension.

        Arguments:
            game_report (dict): a report about a game

        """
        self.xml.append(ET.fromstring(str(game_report)).find('{%s}game' % self.namespace))

    def get_game(self):
        """Get game from stanza.

        Required to parse incoming stanzas with this extension.

        Returns:
            dict with game information

        """
        game = self.xml.find('{%s}game' % self.namespace)
        data = {}
        for key, item in game.items():
            data[key] = item
        return data


class ProfileXmppPlugin(ElementBase):
    """Class for custom profile."""

    name = 'query'
    namespace = 'jabber:iq:profile'
    interfaces = {'profile', 'command', 'recipient'}
    sub_interfaces = interfaces
    plugin_attrib = 'profile'

    def add_command(self, command):
        """Add a command to the extension.

        Arguments:
            command (str): ?

        """
        self.xml.append(ET.fromstring("<command>%s</command>" % command))

    def add_recipient(self, recipient):
        """Add a recipient to the extension.

        Arguments:
            recipient (sleekxmpp.xmlstream.jid.JID): Recipient to add

        """
        self.xml.append(ET.fromstring("<recipient>%s</recipient>" % recipient))

    def add_item(self, player, rating, highest_rating="0",  # pylint: disable=too-many-arguments
                 rank="0", total_games_played="0", wins="0", losses="0"):
        """Add an item to the extension.

        Arguments:
            player (str): Name of the player
            rating (str): Current rating of the player
            highest_rating (str): Highest rating the player had
            rank (str): Rank of the player
            total_games_played (str): Total number of games the player
                                      played
            wins (str): Number of won games the player had
            losses (str): Number of lost games the player had
        """
        item_xml = ET.Element("profile", {"player": player, "rating": rating,
                                          "highestRating": highest_rating, "rank": rank,
                                          "totalGamesPlayed": total_games_played, "wins": wins,
                                          "losses": losses})
        self.xml.append(item_xml)

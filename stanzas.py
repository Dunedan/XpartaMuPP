from sleekxmpp.xmlstream import ElementBase, ET


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

    def add_item(self, player, rating, highest_rating="0", rank="0", total_games_played="0",
                 wins="0", losses="0"):
        item_xml = ET.Element("profile", {"player": player, "rating": rating,
                                          "highestRating": highest_rating, "rank": rank,
                                          "totalGamesPlayed": total_games_played, "wins": wins,
                                          "losses": losses})
        self.xml.append(item_xml)
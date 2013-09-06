import ibid
from ibid.plugins import Processor, match, authorise, periodic
from ibid.utils import human_join, json_webservice, plural
from ibid.config import Option
import json
import urllib
import copy
from pprint import pprint
from ibid.db import IbidUnicodeText, Boolean, Integer, DateTime, \
                    Table, Column, ForeignKey, relation, Base, VersionedSchema

features = {'twitchannouncer': {
    'description': u'Announces twitch broadcasters, can get information about a select list of streamers.',
    'categories': ('lookup',),
}}

class TwitchBroadcasterDB(Base):
    __table__ = Table('twitch_broadcasters', Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('name', IbidUnicodeText, nullable=False, index=True),
    useexisting=True)
    __table__.versioned_schema = VersionedSchema(__table__, 1)

    def __init__(self, name):
        self.name = name


class TwitchBroadcaster(object):
    def __init__(self, name):
        self.name = name
        self.previous = self
        self.live = False
        self.game = ''
        self.title = ''
        self.viewers = 0
        self.liveurl = 'http://twitch.tv/' + name

    def justLive(self):
        return not self.previous.live and self.live

    def switchedGames(self):
        return self.previous.game != self.game and not self.justLive()

    def isLive (self):
        return self.live


class TwitchAnnouncer(Processor):
    features = ('twitch',)
    source = Option('output_source', 'Source for Twitch Broadcaster Updates', u'')
    target = Option('output_target', 'Target for Twitch Broadcaster Updates', u'')
    usage = u'!twitch <name>'
    addressed = False
    priority = 200

    def setup(self):
        Processor.setup(self)
        self.loadBroadcastersFromDB()
        self.updateBroadcasters()

    @periodic(interval=60, initial_delay=5)
    def tick(self, event):
        self.updateBroadcasters()

        for broadcaster in self.twitchlist.justLive():
            message = u'%s just went live and is playing %s. "%s" - %s' % \
                      (broadcaster.name, broadcaster.game, broadcaster.title, broadcaster.liveurl)
            event.addresponse(message, source=self.source, target=self.target, address=False)

        for broadcaster in self.twitchlist.switchedGames():
            message = u'%s just switched games and is playing %s. "%s" - %s' % \
                      (broadcaster.name, broadcaster.game, broadcaster.title, broadcaster.liveurl)
            event.addresponse(message, source=self.source, target=self.target, address=False)

    @match(r'!twitchlist')
    def twitchList(self, event):
        twitch_names = []

        for broadcaster in self.twitchlist.iterate():
            twitch_names.append(broadcaster.name)

        message = u'The following people are being watched: %s' % \
                  (human_join(twitch_names))
        event.addresponse(message, address=False, processed=True)

    @match(r'!twitchadd(?:\s+{broadcaster_name:chunk})')
    def twitchAdd(self, event, broadcaster_name):
        broadcasterCheck = event.session.query(TwitchBroadcasterDB).filter_by(name=broadcaster_name).first()

        if not broadcasterCheck:
            event.session.add(TwitchBroadcasterDB(broadcaster_name))
            event.session.commit()
            self.twitchlist.add(TwitchBroadcaster(broadcaster_name))
            event.addresponse(u"Added Broadcaster: %s", broadcaster_name)
        else:
            event.addresponse(u"Broadcaster already is being watched: %s", broadcaster_name)

    @match(r'!twitchremove(?:\s+{broadcaster_name:chunk})')
    def twitchRemove(self, event, broadcaster_name):
        broadcasterCheck = event.session.query(TwitchBroadcasterDB).filter_by(name=broadcaster_name).first()

        if broadcasterCheck:
            event.session.delete(broadcasterCheck)
            event.session.commit()
            self.twitchlist.remove(broadcaster_name)
            event.addresponse(u"Removed Broadcaster: %s", broadcaster_name)
        else:
            event.addresponse(u"Broadcaster is not currently being watched: %s", broadcaster_name)

    @match(r'!(?:twitch)?{broadcaster_name:chunk}?')
    def broadcasterInfoProcess(self, event, broadcaster_name):
        live_streamers = []
        for tempBroadcaster in self.twitchlist.isLive():
            live_streamers.append(tempBroadcaster.name)

        if not live_streamers:
            message = u'No one is currently streaming'
            event.addresponse(message, address=False, processed=True)
        else:
            if broadcaster_name:
                self.twitchlist.update()
                if broadcaster_name == "*":
                    for live_streamer in live_streamers:
                        self.broadcasterInfo(event, live_streamer)
                else:
                    self.broadcasterInfo(event, broadcaster_name)
            else:
                message = u'The following people are streaming: %s' % \
                          (human_join(live_streamers))
                event.addresponse(message, address=False, processed=True)

    def broadcasterInfo(self, event, broadcaster_name):
        broadcasterListSearch = self.twitchlist.searchBroadcasterByName(broadcaster_name)

        if len(broadcasterListSearch) > 0:
            for broadcaster in broadcasterListSearch.iterate():
                if broadcaster.isLive():
                    message = u'%s is live and is playing %s. "%s" - %s' % \
                              (broadcaster.name, broadcaster.game, broadcaster.title, broadcaster.liveurl)
                    event.addresponse(message, address=False, processed=True)
                else:
                    message = u'%s is not live. - %s' % \
                              (broadcaster.name, broadcaster.liveurl)
                    event.addresponse(message, address=False, processed=True)
        else:
            message = u'%s is an invalid user. Add user with !twitchadd <user>' % \
                      (broadcaster_name)
            event.addresponse(message, address=False, processed=True)

    def loadBroadcastersFromDB(self):
        session = ibid.databases.ibid()
        dbList = session.query(TwitchBroadcasterDB).all()
        newList = []

        for dbBroadcaster in dbList:
            newList.append(TwitchBroadcaster(dbBroadcaster.name))

        self.twitchlist = TwitchList(newList)


    def updateBroadcasters(self):
        self.twitchlist.update()

class TwitchList(object):
    broadcasters = {} 
    def __init__(self, broadcaster_list=[]):
        self.broadcasters = {}
        for broadcaster in broadcaster_list:
            self.broadcasters[broadcaster.name] = broadcaster

    def update(self):
        try:
            new_data = json_webservice('http://api.justin.tv/api/stream/list.json?channel=' + ','.join(self.broadcasters.keys()))

            for broadcaster_name in self.broadcasters:
                broadcaster = self.getBroadcasterByName(broadcaster_name)
                del broadcaster.previous
                broadcaster.previous = copy.copy(broadcaster)
                broadcaster.live = False

            for broadcaster_data in new_data:
                channel = broadcaster_data['channel']
                login = channel['login']

                broadcaster = self.getBroadcasterByName(login) 
                broadcaster.live = True
                broadcaster.game = channel['meta_game']
                broadcaster.title = broadcaster_data['title']
                broadcaster.viewers = broadcaster_data['channel_count']
        except:
            pass

    def add(self, broadcaster):
        self.broadcasters[broadcaster.name] = broadcaster

    def remove(self, broadcaster_name):
        del self.broadcasters[broadcaster_name]

    def getBroadcasterByName(self, name):
        if name in self.broadcasters:
            return self.broadcasters[name]
        return TwitchBroadcaster(name)

    def searchBroadcasterByName(self, search):
        returnList = TwitchList()

        for broadcaster in self.iterate():
            if broadcaster.name.find(search) >= 0:
                returnList.add(broadcaster)

        return returnList

    def iterate(self):
        for broadcaster in self.broadcasters:
            yield self.getBroadcasterByName(broadcaster)

    def justLive(self):
        for broadcaster in self.iterate():
            if broadcaster.justLive():
                yield broadcaster

    def switchedGames(self):
        for broadcaster in self.iterate():
            if broadcaster.switchedGames():
                yield broadcaster

    def isLive(self):
        for broadcaster in self.iterate():
            if broadcaster.isLive():
                yield broadcaster

    def __len__(self):
        return len(self.broadcasters)

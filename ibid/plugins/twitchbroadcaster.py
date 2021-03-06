import ibid
from datetime import datetime, timedelta
import logging

from ibid.plugins import Processor, match, periodic
from ibid.utils import human_join, json_webservice, format_date
from ibid.config import Option
import copy
from pprint import pprint
from ibid.db import IbidUnicodeText, Integer, DateTime, \
                    Table, Column, Base, VersionedSchema
from random import randint

log = logging.getLogger('plugins.twitchbroadcaster')

features = {'twitchannouncer': {
    'description': u'Announces twitch broadcasters, can get information about a select list of streamers.',
    'categories': ('lookup',),
}}

class TwitchBroadcasterDB(Base):
    __table__ = Table('twitch_broadcasters', Base.metadata,
    Column('id', Integer, primary_key=True),
    Column('name', IbidUnicodeText, nullable=False, index=True),
    Column('lastlive', DateTime, nullable=True),
    useexisting=True)

    def __init__(self, name):
        self.name = name

    class TwitchBroadcasterSchema(VersionedSchema):
        def upgrade_1_to_2(self):
            self.add_column(Column('lastlive', DateTime, nullable=True))

    __table__.versioned_schema = TwitchBroadcasterSchema(__table__, 2)


class TwitchBroadcaster(object):
    def __init__(self, name):
        self.name = name
        self.previous = self
        self.live = False
        self.game = ''
        self.title = ''
        self.viewers = 0
        self.liveurl = ''
        self.lastlive = None

    @classmethod
    def from_db(cls, broadcaster_db):
        broadcaster = cls(broadcaster_db.name)
        broadcaster.lastlive = broadcaster_db.lastlive
        return broadcaster

    def justOffline(self):
        return self.previous.live and not self.live

    def justLive(self):
        lastlivecheck = self.lastlive and (self.lastlive < datetime.now() - timedelta(minutes=5))
        return not self.previous.live and self.live and lastlivecheck

    def switchedGames(self):
        return self.previous.game != self.game and not self.justLive()

    def isLive(self):
        return self.live

    def format_lastlive(self):
        return format_date(self.lastlive) if self.lastlive else 'Never'

    def updateTwitch(self):
        try:
            new_data = json_webservice('https://api.twitch.tv/kraken/streams?channel=' + self.name)
            if new_data['streams']:
                broadcaster_data = new_data['streams'].pop()
                channel = broadcaster_data['channel']
                self.live = True
                self.game = broadcaster_data['game']
                self.title = channel['status']
                self.viewers = broadcaster_data['viewers']
                self.liveurl = channel['url']
        except Exception, e:
            return False

    def updateHitbox(self):
        try:
            new_data = json_webservice('http://api.hitbox.tv/media/live/' + self.name)
            if new_data['livestream']:
                media = new_data['livestream'].pop()
                if media['media_is_live'] == u'1':
                    self.live = True
                    self.game = media['category_name']
                    self.title = media['media_status']
                    self.viewers = media['media_views']
                    self.liveurl = media['channel']['channel_link']
        except Exception, e:
            return False


    def update(self):
        del self.previous
        self.previous = copy.copy(self)
        self.live = False

        try:
            self.updateHitbox()
            self.updateTwitch()
        except Exception, e:
            log.debug(u'Error while updating broadcasters %s' % (e.message))

    def updateDB(self):
        session = ibid.databases.ibid()
        broadcasterCheck = session.query(TwitchBroadcasterDB).filter_by(name=self.name).first()
        broadcasterCheck.lastlive = self.lastlive
        session.add(broadcasterCheck)
        session.commit()

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
            message = u'%s just went live and is playing %s. "%s" - %s viewers - %s' % \
                      (broadcaster.name, broadcaster.game, broadcaster.title, broadcaster.viewers, broadcaster.liveurl)
            event.addresponse(message, source=self.source, target=self.target, address=False)

        for broadcaster in self.twitchlist.switchedGames():
            message = u'%s just switched games and is playing %s. "%s" - %s viewers - %s' % \
                      (broadcaster.name, broadcaster.game, broadcaster.title, broadcaster.viewers, broadcaster.liveurl)
            event.addresponse(message, source=self.source, target=self.target, address=False)

    @match(r'!twitchlist')
    def twitchList(self, event):
        twitch_names = []

        for broadcaster in self.twitchlist.iterate():
            twitch_names.append(broadcaster.name)

        message = u'The following people are being watched: %s' % \
                  (human_join(twitch_names))
        event.addresponse(message, address=False, processed=True)

    @match(r'!twitchrandom')
    def twitchRandom(self, event):
        summary = json_webservice('https://api.twitch.tv/kraken/streams/summary')
        maxchannel = summary['channels']
        randomnum = randint(1, maxchannel)

        query = json_webservice('https://api.twitch.tv/kraken/streams?limit=1&offset=%d' % randomnum)

        stream = query['streams'].pop()

        message = u'Random Stream found. Number:  %s/%s' % \
                  (randomnum, maxchannel)
        event.addresponse(message, address=False, processed=True)

        self.broadcasterInfo(event, stream['channel']['name'])

    @match(r'!twitchadd {broadcaster_name:chunk}')
    def twitchAdd(self, event, broadcaster_name):
        broadcasterCheck = event.session.query(TwitchBroadcasterDB).filter_by(name=broadcaster_name).first()

        if not broadcasterCheck:
            event.session.add(TwitchBroadcasterDB(broadcaster_name))
            event.session.commit()
            self.twitchlist.add(TwitchBroadcaster(broadcaster_name))
            event.addresponse(u"Added Broadcaster: %s", broadcaster_name)
        else:
            event.addresponse(u"Broadcaster already is being watched: %s", broadcaster_name)

    @match(r'!twitchremove {broadcaster_name:chunk}')
    def twitchRemove(self, event, broadcaster_name):
        broadcasterCheck = event.session.query(TwitchBroadcasterDB).filter_by(name=broadcaster_name).first()

        if broadcasterCheck:
            event.session.delete(broadcasterCheck)
            event.session.commit()
            self.twitchlist.remove(broadcaster_name)
            event.addresponse(u"Removed Broadcaster: %s", broadcaster_name)
        else:
            event.addresponse(u"Broadcaster is not currently being watched: %s", broadcaster_name)

    @match(r'!(?:twitch )?{broadcaster_name:chunk}?')
    def broadcasterInfoProcess(self, event, broadcaster_name):
        if event.processed:
            return
        self.twitchlist.update()

        live_streamers = []
        for tempBroadcaster in self.twitchlist.isLive():
            live_streamers.append(tempBroadcaster.name)

        if broadcaster_name:
            if broadcaster_name == "*":
                for live_streamer in live_streamers:
                    self.broadcasterInfo(event, live_streamer)
            else:
                self.broadcasterInfo(event, broadcaster_name)
        else:
            if live_streamers:
                message = u'The following people are streaming: %s' % \
                          (human_join(live_streamers))
                event.addresponse(message, address=False, processed=True)

        if not event.processed:
            message = u'No one is currently streaming'
            event.addresponse(message, address=False, processed=True)

    def broadcasterInfo(self, event, broadcaster_name):
        broadcasterListSearch = self.twitchlist.searchBroadcasterByName(broadcaster_name)

        if len(broadcasterListSearch) == 0:
            broadcaster = TwitchBroadcaster(broadcaster_name)
            broadcaster.update()

            if broadcaster.isLive():
                broadcasterListSearch = TwitchList()
                broadcasterListSearch.add(broadcaster)

        if len(broadcasterListSearch) > 0:
            for broadcaster in broadcasterListSearch.iterate():
                if broadcaster.isLive():
                    message = u'%s is live and is playing %s. "%s" - %s viewers - %s' % \
                              (broadcaster.name, broadcaster.game, broadcaster.title, broadcaster.viewers, broadcaster.liveurl)
                    event.addresponse(message, address=False, processed=True)
                else:
                    message = u'%s is not live. Last live: %s - %s' % \
                              (broadcaster.name, broadcaster.format_lastlive(), broadcaster.liveurl)
                    event.addresponse(message, address=False, processed=True)
        else:
            message = u'%s is an invalid user or is not live. Add user with !twitchadd <user>' % \
                      (broadcaster_name)
            event.addresponse(message, address=False, processed=True)

    def loadBroadcastersFromDB(self):
        session = ibid.databases.ibid()
        dbList = session.query(TwitchBroadcasterDB).all()
        newList = []

        for dbBroadcaster in dbList:
            newList.append(TwitchBroadcaster.from_db(dbBroadcaster))

        self.twitchlist = TwitchList(newList)


    def updateBroadcasters(self):
        self.twitchlist.update()

class TwitchList(object):
    broadcasters = {}
    def __init__(self, broadcaster_list=[]):
        self.broadcasters = {}
        for broadcaster in broadcaster_list:
            self.broadcasters[broadcaster.name] = broadcaster

    def updateHitbox(self):
        try:
            new_data = json_webservice('http://api.hitbox.tv/media/live/' + ','.join(self.broadcasters.keys()))
            for media in new_data['livestream']:
                if media['media_is_live'] == u'1':
                    login = media['media_name']
                    broadcaster = self.getBroadcasterByName(login)
                    broadcaster.live = True
                    broadcaster.game = media['category_name']
                    broadcaster.title = media['media_status']
                    broadcaster.viewers = media['media_views']
                    broadcaster.liveurl = media['channel']['channel_link']
        except Exception, e:
            return False

    def updateTwitch(self):
        try:
            new_data = json_webservice('https://api.twitch.tv/kraken/streams?channel=' + ','.join(self.broadcasters.keys()))
            for broadcaster_data in new_data['streams']:
                channel = broadcaster_data['channel']
                login = channel['name']
                broadcaster = self.getBroadcasterByName(login)
                broadcaster.live = True
                broadcaster.game = broadcaster_data['game']
                broadcaster.title = channel['status']
                broadcaster.viewers = broadcaster_data['viewers']
                broadcaster.liveurl = channel['url']
        except Exception, e:
            return False


    def update(self):
        try:
            for broadcaster_name in self.broadcasters:
                broadcaster = self.getBroadcasterByName(broadcaster_name)
                del broadcaster.previous
                broadcaster.previous = copy.copy(broadcaster)
                broadcaster.live = False

            self.updateHitbox()
            self.updateTwitch()

            for broadcaster_name in self.broadcasters:
                broadcaster = self.getBroadcasterByName(broadcaster_name)
                if broadcaster.justLive():
                    broadcaster.lastlive = datetime.utcnow()
                    broadcaster.updateDB()

        except Exception, e:
            log.debug(u'Error while updating broadcasters %s' % (e.message))

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

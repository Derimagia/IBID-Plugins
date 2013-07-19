from ibid.plugins import Processor, match, authorise, periodic
from ibid.utils import human_join, json_webservice, plural
from ibid.config import Option
import json
import urllib
import copy
from pprint import pprint


features = {'twitchannouncer': {
    'description': u'Announces twitch broadcasters, can get information about a select list of streamers.',
    'categories': ('lookup',),
}}

class twitchannouncer(Processor):
    features = ('twitch',)
    source = Option('twitch_output_source', 'Source for Twitch Broadcaster Updates', 'esper')
    target = Option('twitch_output_target', 'Target for Twitch Broadcaster Updates', '#channel')
    usage = u'!twitch <name>'
    addressed = False

    twitch_broadcasters = ['array', 'of', 'broadcasters']

    def setup(self):
        Processor.setup(self)
        self.twitchlist = TwitchList(self.twitch_broadcasters)
        self.twitchlist.update()

    @periodic(interval=60, initial_delay=5)
    def tick(self, event):
        self.twitchlist.update()
        for broadcaster in self.twitchlist.justLive():
            message = u'%s just went live and is playing %s. "%s" - %s' % \
                      (broadcaster.name, broadcaster.game, broadcaster.title, broadcaster.liveurl)
            event.addresponse(message, source=self.source, target=self.target, address=False)

        for broadcaster in self.twitchlist.switchedGames():
            message = u'%s just switched games and is playing %s. "%s" - %s' % \
                      (broadcaster.name, broadcaster.game, broadcaster.title, broadcaster.liveurl)
            event.addresponse(message, source=self.source, target=self.target, address=False)

    @match(r'^(!twitch)(?:(\s+(.+?))?)$')
    def list(self, event, var1, var2, broadcaster):
        self.twitchlist.update()
        broadcaster = self.twitchlist.getBroadcasterByName(broadcaster)
        if broadcaster:
            if broadcaster.isLive():
                message = u'%s is live and is playing %s. "%s" - %s' % \
                          (broadcaster.name, broadcaster.game, broadcaster.title, broadcaster.liveurl)
                event.addresponse(message, {}, address=False, processed=True)
            else:
                message = u'%s is not live. - %s' % \
                          (broadcaster.name, broadcaster.liveurl)
                event.addresponse(message, {}, address=False, processed=True)
            return

        live_streamers = []
        for broadcaster in self.twitchlist.isLive():
            live_streamers.append(broadcaster.name)

        if not live_streamers:
            message = u'Noone is currently streaming'
            event.addresponse(message, {}, address=False, processed=True)
        else:
            message = u'The following people are streaming: %s' % \
                      (human_join(live_streamers))
            event.addresponse(message, {}, address=False, processed=True)



class TwitchList(object):
    broadcasters = {} 
    broadcasters_names = ''

    def __init__(self, raw_names):
        self.broadcasters_names = raw_names
        for raw_name in raw_names:
            self.broadcasters[raw_name] = TwitchBroadcaster(raw_name)


    def update(self):
        try:
            new_data = json_webservice('http://api.justin.tv/api/stream/list.json?channel=' + ','.join(self.broadcasters_names))

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

    def getBroadcasterByName(self, name):
        if name in self.broadcasters:
            return self.broadcasters[name]
        return False

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


class TwitchBroadcaster(object):
    name = ''
    live = False
    game = ''
    title = ''
    viewers = 0
    liveurl = ''

    def __init__(self, name):
        self.name = name
        self.previous = self
        self.liveurl = 'http://twitch.tv/' + name
        pass

    def justLive(self):
        return not self.previous.live and self.live

    def switchedGames(self):
        return self.previous.game != self.game and not self.justLive()

    def isLive (self):
        return self.live

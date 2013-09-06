from ibid.plugins import Processor, match
from ibid.config import Option
import steam

features = {'steam': {
    'description': u'Steam',
    'categories': ('lookup',),
}}

class Steam(Processor):
    features = ('steam',)
    source = Option('output_source', 'Source for Steam Updates', u'')
    target = Option('output_target', 'Target for Steam Updates', u'')
    steam_api_key = Option('steam_api_key', 'Steam API Key', u'')

    usage = u'!steam <name>'
    addressed = False
    priority = 0

    def setup(self):
        Processor.setup(self)
        steam.api.key.set(self.steam_api_key)

    @match(r'!steam\s+{steam_name:chunk}')
    def steamList(self, event, steam_name):
        try:
            id64 = steam.user.vanity_url(steam_name).id64
        except steam.user.VanityError:
            id64 = steam_name

        try:
            profile = steam.user.profile(id64)

            lookup = {0 : u'Offline',
                      1 : u'Online',
                      2 : u'Busy',
                      3 : u'Away',
                      4 : u'Snooze',
                      5 : u'Looking to Trade',
                      6 : u'Looking to Play'}

            status = lookup.get(profile.status)

            if not status:
                status = u'Unknown (ID: %s)' % profile.status

            event.addresponse(u"Steam User %s is currently %s. %s" % (steam_name, status, profile.profile_url), address=False)
            print profile.status
        except steam.user.ProfileNotFoundError:
            event.addresponse(u"Steam User with Vanity not found: %s" % steam_name, address=False)





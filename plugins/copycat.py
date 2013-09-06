import pprint
import urllib2
import base64
import cleverbot
from ibid.plugins import Processor, match, authorise
from ibid.config import Option, IntOption
from ibid.utils import human_join, json_webservice, plural

class copycat(Processor):
    usage = u'copycat'
    features = ('copycat')
    addressed = False
    priority = 500
    permission = u'copycat'
    currentCopycats = dict()

    @match(r'!copycat')
    @authorise()
    def disableAllCopycat(self, event, *args):
        self.currentCopycats = dict()
        event.addresponse(u'Copycat Removed for everyone', address=True, processed=True)
        return

    @match(r'^(!copycat\s(.*))')
    @authorise()
    def enableCopycat(self, event, inval, name, *args):
        if event["processed"]:
            return
        sender = event["sender"]["id"]

        if name not in self.currentCopycats:
            self.currentCopycats[name] = True
            event.addresponse(u'Copycat Activated for %s' % (name), address=True, processed=True)
        else:
            del self.currentCopycats[name]
            event.addresponse(u'Copycat Removed for %s' % (name), address=True, processed=True)
        return

    @match(r'(.*)')
    def copycat(self, event, message, *args):
        if event["processed"]:
            return
        sender = event["sender"]["id"]

        if sender in self.currentCopycats:
            event.addresponse(message, address=False, processed=False)

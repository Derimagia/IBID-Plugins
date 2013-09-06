import pprint
import urllib2
import base64
import random
import cleverbot
from ibid.plugins import Processor, match
from ibid.config import Option, IntOption
from ibid.utils import human_join, json_webservice, plural


class cleverbotprocessor(Processor):
    usage = u'clevertbot'
    features = ('cleverbot',)
    addressed = False
    priority = 949
    processed = False

    currentCleverbots = dict()
    mainCleverbot = cleverbot.Session()

    @match(r'^(talk to me)|(cleverbot)')
    def enableCleverbot(self, event, *args):
        if event["processed"]:
            return

        sender = event["sender"]["id"]

        if sender not in self.currentCleverbots:
            self.currentCleverbots[sender] = cleverbot.Session()
            event.addresponse(u'Cleverbot Activated', address=True, processed=True)
        return

    @match(r'^(stop talking)|^(shut up)$')
    def disableCleverbot(self, event, *args):
        if event["processed"]:
            return
        sender = event["sender"]["id"]

        if self.currentCleverbots[sender]:
            del self.currentCleverbots[sender]

        event.addresponse(u'Cleverbot Disabled', address=True, processed=True)
        return

    @match(r'^(cleverbot)$')
    def toggleCleverbot(self, event, *args):
        if event["processed"]:
            return
        sender = event["sender"]["id"]
        if self.currentCleverbots[sender]:
            self.disableCleverbot(event)
        else:
            self.enableCleverbot(event)
        return

    @match(r'^(cleverbot who)$')
    def whoCleverbot(self, event, *args):
        if event["processed"]:
            return
        if event["addressed"]:
            people = self.currentCleverbots.keys()
            if len(people) > 0:
                event.addresponse(u'IRC: I am currently talking to %s' % (human_join(people)), address=True, processed=True)
            else:
                event.addresponse(u'IRC: I am not talking to anyone', address=True, processed=True)
        return

    @match(r'!clevertalk(?:\s+{salt:chunk})')
    def cleverTalk(self, event, salt):
        cleverbotOne = cleverbot.Session()
        cleverbotTwo = cleverbot.Session()

        messageone = ""
        messagetwo = salt

        for i in range(10):
            messageone = unicode(cleverbotOne.Ask(messagetwo))
            event.addresponse(u'C1: %s' % messageone, address=False, processed=True)
            messagetwo = unicode(cleverbotTwo.Ask(messageone))
            event.addresponse(u'C2: %s' % messagetwo, address=False, processed=True)


    @match(r'.*')
    def processMessage(self, event):
        if event["processed"]:
            return
            
        message = event['message']['clean']
        sender = event["sender"]["id"]
        addressed = event["addressed"]
        sendMessage = False
        currentCleverbot = self.mainCleverbot

        if addressed:
            sendMessage = True

        if not sendMessage:
            if sender in self.currentCleverbots:
                sendMessage = True
                currentCleverbot = self.currentCleverbots[sender]

        #Randomly respond
        # if not sendMessage:
        #     if random.randint(1, 25) == 1:
        #         sendMessage = True

        if sendMessage:
            response = unicode(currentCleverbot.Ask(message))
            event.addresponse(response, address=True, processed=True)            

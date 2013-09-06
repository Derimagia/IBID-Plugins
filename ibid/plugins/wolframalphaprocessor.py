import pprint
import urllib
import urllib2
import base64
import wolframalpha
from ibid.plugins import Processor, match
from ibid.config import Option, IntOption
from ibid.utils import human_join, generic_webservice, plural, unicode_output
from ibid.compat import defaultdict, json
      
class wolframalphaprocessor(Processor):
    wa_api_key = Option('wa_api_key', 'Wolfram Alpha API Key', u'')
    usage = u'?<query>'
    features = ('wolframalpha',)
    addressed = False
    priority = 900

    @match(r'(?:calc\s|\?)(.*)')
    def processMessage(self, event, message):
        if event["processed"]:
            return
  
        client = wolframalpha.Client(self.wa_api_key)
        results = list(client.query(message.strip()).pods)
        
        lines = []

        for pod in results:
            if pod.text:
                lines.append(unicode_output(pod.text.encode('ascii', 'ignore')))

        if not lines:
            event.addresponse(u'No results.', {}, address=False, processed=True)
        else:
            for line in lines:
                event.addresponse(line, {}, address=False, processed=True)
        return

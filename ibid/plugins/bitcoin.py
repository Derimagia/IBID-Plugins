from ibid.plugins import Processor, match
from ibid.utils import json_webservice


features = {'bitcoin': {
    'description': u'Bitcoin',
    'categories': ('lookup',),
}}

class Bitcoin(Processor):
    features = ('bitcoin',)

    usage = u'!btc'
    addressed = False
    priority = 0

    @match(r'!btc')
    def steamList(self, event):
        mtgoxData = self.getMTGoxData()
        buy_price = mtgoxData['data']['buy']['display']
        sell_price = mtgoxData['data']['sell']['display']
        event.addresponse(u"Current Bitcoin Price (MtGox): S: %s  -  B: %s" % (buy_price, sell_price), address=False)


    def getMTGoxData(self):
        return json_webservice('https://data.mtgox.com/api/2/BTCUSD/money/ticker')


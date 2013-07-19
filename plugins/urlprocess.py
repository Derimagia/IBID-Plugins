from ibid.plugins import Processor, match
import urllib
from urllib2 import HTTPError
import urlparse
import re
from pprint import pprint
import datetime
from ibid.utils import json_webservice
import pytz

features = {'urlprocess': {
    'description': u'Processes URLs and outputs information about them',
    'categories': ('lookup',),
}}


class urlprocess(Processor):
    usage = u'<URL>'
    features = ('urlprocess',)
    addressed = False
    priority = 900

    event = {}
    option = {}

    def makedict(**kwargs):
        return kwargs

    no_colors = makedict(white="", black="", blue="", red="", dred="", purple="", dyellow="", yellow="", bgreen="", dgreen="", green="", bpurple="", dgrey="", lgrey="", nocolor="")
    all_colors = makedict(white="\0030", black="\0031", blue="\0032", red="\0034", dred="\0035", purple="\0036", dyellow="\0037", yellow="\0038", bgreen="\0039", dgreen="\00310", green="\00311", bpurple="\00313", dgrey="\00314", lgrey="\00315", nocolor="\003")
    color = all_colors

    checkTwitch = re.compile(r'(?:(?:http|https):\/\/)?(?:www\.)?twitch.tv\/(.*)(?:\/)?')
    checkYoutube = re.compile(r'(?:(?:http|https):\/\/)?(?:www\.)?youtube.com\/(?:\/)?')
    checkReddit = re.compile(r'(?:(?:http|https):\/\/)?(?:www\.)?reddit.com\/(r|t)\/(.*)(?:\/)?')
    checkUrlRegex = r'(.*?)((?:[a-z][\w-]+:(?:\/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}\/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:\'\".,<>?]))(.*)'

    checkUrl = re.compile(checkUrlRegex)


    twitchTimezone = pytz.timezone('US/Pacific')
    botTimezone = pytz.timezone("US/Eastern")

    @match(checkUrlRegex)
    def urlprocess(self, event, nothing, url, *args):
        self.event = event

        if event["source"] == "xmpp":
            self.color = self.no_colors
        else:
            self.color = self.all_colors

        self.parseUrl(url, action="default")
        return

    @match("!twitch (.*)")
    def processSimpleTwitchRequest(self, event, broadcaster, *args):
        self.event = event

        if event["source"] == "xmpp":
            self.color = self.no_colors
        else:
            self.color = self.all_colors

        returnObj = self.processTwitch(broadcaster)

        if "type" in returnObj:
            if returnObj["type"] == "twitch":
                streamURL = u"http://twitch.tv/" + broadcaster
                self.event.addresponse(streamURL, {}, address=False, processed=True)
            else:
                returnObj["errorMessage"] = u"Invalid Twitch Broadcaster"

        self.parseReturnObject(returnObj)

        return
    def processYoutube(self, youtubeID):
        returnObj = {}
        returnObj["type"] = "none"
        try:
            dataYoutube = self.getJsonFromUrl("http://gdata.youtube.com/feeds/api/videos/" + youtubeID + "?alt=json")
            if "entry" in dataYoutube:
                dataYoutube = dataYoutube["entry"]
                returnObj["youtubeID"] = youtubeID
                returnObj["type"] = "youtube"
                returnObj["title"] = dataYoutube["title"]["$t"]
                returnObj["description"] = dataYoutube["media$group"]["media$description"]["$t"]
                returnObj["author"] = dataYoutube["author"].pop()["name"]["$t"]
                returnObj["views"] = dataYoutube["yt$statistics"]["viewCount"]
                returnObj["rating"] = dataYoutube["gd$rating"]["average"]
                returnObj["durationSeconds"] = int(dataYoutube["media$group"]["yt$duration"]["seconds"])
                returnObj["duration"] = self.sec2hms(returnObj["durationSeconds"])
                returnObj["url"] = dataYoutube["link"].pop()["href"]
        except HTTPError:
            returnObj["errorMessage"] = u"That was an invalid video. Please try again later"
            return returnObj
        return returnObj

    def processYoutubeURL(self, query):
        returnObj = {}
        returnObj["type"] = "none"
        queryElements = self.parseUrlQuery(query)
        if "v" in queryElements:
            youtubeID = queryElements["v"]
            returnObj = self.processYoutube(youtubeID)
        return returnObj

    def processUrlThroughReddit(self, query):
        returnObj = {}
        try:
            dataReddit = self.getJsonFromUrl("http://www.reddit.com/api/info.json?url=" + urllib.quote_plus(query.rstrip('\/')) + "&sort=top&count=1&restrict_sr=off")

            if not dataReddit:
                return returnObj

            if "data" in dataReddit:
                dataPostList = dataReddit["data"]["children"]

                if (len(dataPostList) > 0):
                    returnObj = dataPostList[0]["data"]
                    for item in dataPostList:
                        if item["data"]["score"] > returnObj["score"]:
                            returnObj = item["data"]
                    returnObj["type"] = "reddit"
        except HTTPError:
            returnObj["errorMessage"] = u"I had an issue accessing Reddit's API. Please try again later"
            return returnObj
        return returnObj

    def processTwitchURL(self, query):
        twitchMatchObj = self.checkTwitch.search(query, re.IGNORECASE)
        broadcaster = twitchMatchObj.group(1)
        returnObj = self.processTwitch(broadcaster)
        return returnObj

    def processTwitch(self, broadcaster):
        urlArray = broadcaster.split("/")

        broadcaster = urlArray[0]
        returnObj = {}
        try:
            dataUser = self.getJsonFromUrl("http://api.justin.tv/api/channel/show/" + broadcaster + ".json")

            if not dataUser:
                return returnObj

            if dataUser:
                returnObj["type"] = "twitch"
                returnObj["category"] = dataUser["category_title"]
                returnObj["url"] = dataUser["channel_url"]
                returnObj["timezone"] = dataUser["timezone"]
                returnObj["user"] = dataUser["login"]
                returnObj["title"] = dataUser["title"]
                returnObj["status"] = dataUser["status"]
                returnObj["description"] = dataUser["description"]
                returnObj["live"] = False

                dataStreamList = self.getJsonFromUrl("http://api.justin.tv/api/stream/list.json?channel=" + broadcaster)

                if (dataStreamList):
                    dataStream = dataStreamList.pop()
                    returnObj["live"] = True
                    returnObj["viewers"] = dataStream["channel_count"]

                    naive = datetime.datetime.strptime(dataStream["up_time"] + "", "%a %b %d %H:%M:%S %Y")
                    twitch_time = self.twitchTimezone.localize(naive, is_dst=None)

                    twitch_time = twitch_time.astimezone(self.botTimezone)

                    returnObj["up_time_string"] = self.pretty_date(twitch_time)

                    if ("meta_game" in dataStream):
                        returnObj["game"] = dataStream["meta_game"]
                    else:
                        returnObj["game"] = "None"

                returnObj["live_status"] = "Online" if returnObj["live"] else "Offline"
        except HTTPError as e:
            returnObj["errorMessage"] = u"I had an issue accessing Twitch's API. Please try again later"
            return returnObj
        return returnObj

    def processReddit(self, query):
        returnObj = {}
        redditPathElements = self.parseUrlPath(query)
        try:
            if len(redditPathElements) > 3:
                entryID = redditPathElements[3]

                if len(redditPathElements) > 5:
                    commentID = redditPathElements[5]
                    dataComment = self.getJsonFromUrl("http://www.reddit.com/comments/" + entryID + "/_/" + commentID + ".json?limit=1")

                    if dataComment:
                        returnObj = dataComment.pop(1)["data"]["children"].pop()["data"]
                        returnObj["type"] = "redditComment"
                else:
                    dataPost = self.getJsonFromUrl("http://www.reddit.com/by_id/t3_" + entryID + ".json")

                    if dataPost:
                        returnObj = dataPost["data"]["children"].pop()["data"]
                        returnObj["type"] = "redditPost"

        except HTTPError:
            returnObj["errorMessage"] = u"I had an issue accessing Reddit's API. Please try again later"
            return returnObj
        return returnObj

    def parseReturnObject(self, data, action="default"):
        nocolor = self.color['nocolor']
        color = self.color

        msg1 = u""
        msg2 = u""
        msg3 = u""
        ret = False

        if "errorMessage" in data:
            self.event.addresponse(data["errorMessage"], {}, address=False, processed=True)
            return
        if "type" not in data:
            data["type"] = "none"
        if data:
            if "youtube" in data:
                youtubeTitle = data["youtube"]["title"]
                youtubeDescription = self.truncate(data["youtube"]["description"], 120)
                youtubeRating = data["youtube"]["author"]
                youtubeViews = data["youtube"]["views"]
                youtubeRating = data["youtube"]["rating"]
                # youtubeDuration = data["youtube"]["duration"]
                # youtubeDurationSeconds = data["youtube"]["durationSeconds"]
                # youtubeURL = data["youtube"]["url"]
            if data["type"] == "reddit":

                redditTitle = data['title']
                redditUpvotes = data['ups']
                redditDownvotes = data['downs']
                redditScore = data['score']
                redditAuthor = data['author']
                redditLink = "http://www.reddit.com" + data['permalink']

                if "youtube" in data:
                    msg1 = '%s[YT TITLE]: %s %s' % (color['blue'], nocolor, youtubeTitle)
                    msg1 += ' %s[REDDIT SCORE]: %s %s (%s %s %s|%s %s %s)' % (color['lgrey'], nocolor, redditScore, color['bgreen'], redditUpvotes, nocolor, color['red'], redditDownvotes, nocolor)
                    msg2 = '%s[YT DESCRIPTION]: %s %s' % (color['red'], nocolor, youtubeDescription)
                    msg3 = '%s[REDDIT LINK]: %s %s' % (color['dgreen'], nocolor, redditLink)
                else:
                    msg1 = '%s[TITLE]: %s %s' % (color['blue'], nocolor, redditTitle)
                    msg2 = '%s[SCORE]: %s %s (%s %s %s|%s %s %s)' % (color['lgrey'], nocolor, redditScore, color['bgreen'], redditUpvotes, nocolor, color['red'], redditDownvotes, nocolor)
                    msg2 += '  %s[OP]: %s %s' % (color['bpurple'], nocolor, redditAuthor)
                    msg3 = '%s[PERMALINK]: %s %s' % (color['dgreen'], nocolor, redditLink)
                    ret = True
            elif data["type"] == "redditPost":
                redditTitle = data['title']
                redditUpvotes = data['ups']
                redditDownvotes = data['downs']
                redditScore = data['score']
                redditAuthor = data['author']

                msg1 = '%s[TITLE]: %s %s' % (color['blue'], nocolor, redditTitle)
                msg2 = '%s[SCORE]: %s %s (%s %s %s|%s %s %s)' % (color['dgrey'], nocolor, redditScore, color['bgreen'], redditUpvotes, nocolor, color['red'], redditDownvotes, nocolor)
                msg2 += '  %s[OP]: %s %s' % (color['bpurple'], nocolor, redditAuthor)
                ret = True
            elif data["type"] == "redditComment":
                entryBody = self.truncate(data['body'], 200)

                if entryBody != data['body']:
                    entryBody += "..."
                redditUpvotes = data['ups']
                redditDownvotes = data['downs']
                redditScore = redditUpvotes - redditDownvotes
                redditAuthor = data['author']
                msg1 = '%s[COMMENT]: %s %s' % (color['blue'], nocolor, entryBody)
                msg2 = '%s[SCORE]: %s %s (%s %s %s|%s %s %s)' % (color['lgrey'], nocolor, redditScore, color['bgreen'], redditUpvotes, nocolor, color['red'], redditDownvotes, nocolor)
                msg2 += '  %s[AUTHOR]: %s %s' % (color['bpurple'], nocolor, redditAuthor)
                ret = True
            elif "youtube" in data:
                msg1 = '%s[TITLE]:%s %s  %s[RATING]: %s %s  %s[VIEWS]: %s %s' % (color['blue'], nocolor, youtubeTitle, color['lgrey'], nocolor, youtubeRating, color['bgreen'], nocolor, youtubeViews)
                msg2 = '%s[DESCRIPTION]%s %s' % (color['red'], nocolor, youtubeDescription)
            elif data["type"] == "twitch":
                twitchUser = data["user"]
                colorStatus = color['bgreen'] if data["live"] else color['red']
                onlineStatus = data["live_status"]
                # twitchTitle = data["title"]
                # twitchTimezone = data["timezone"]
                twitchStatus = data["status"]
                twitchDescription = data["description"]
                if ("up_time_string" in data):
                    twitchUptimeString = data["up_time_string"]

                if (data["live"]):
                    twitchViewers = data["viewers"]
                    twitchGame = data["game"]

                if (action == "default"):
                    if (data["live"]):
                        msg1 = '%s[STATUS]:%s %s  %s[STARTED]:%s %s %s[TITLE]:%s %s' % (color['blue'], colorStatus, onlineStatus, color['green'], nocolor, twitchUptimeString, color['lgrey'], nocolor, twitchStatus)
                        msg2 = '%s[USER]%s %s %s[VIEWERS]%s %s %s[GAME]:%s %s' % (color['green'], nocolor, twitchUser, color['bgreen'], nocolor, twitchViewers, color["blue"], nocolor, twitchGame)
                    else:
                        msg1 = '%s[STATUS]:%s %s  %s[TITLE]:%s %s' % (color['blue'], colorStatus, onlineStatus, color['lgrey'], nocolor, twitchStatus)
                        msg2 = '%s[USER]%s %s %s[DESCRIPTION]:%s %s' % (color['green'], nocolor, twitchUser, color['bgreen'], nocolor, twitchDescription)

                elif action == "uptime":
                    if data["live"]:
                        msg1 = "User '%s' started streaming about %s" % (twitchUser, twitchUptimeString)
                    elif (action == "game"):
                        if (data["live"]):
                            msg1 = "User '%s' is playing the game '%s'" % (twitchUser, twitchGame)

        if msg1:
            self.event.addresponse(msg1, {}, address=False, processed=True)
        if msg2:
            self.event.addresponse(msg2, {}, address=False, processed=True)
        if msg3:
            self.event.addresponse(msg3, {}, address=False, processed=True)
        return ret

    def parseUrl(self, query, action="default"):
        data = {}

        if (self.checkTwitch.search(query, re.IGNORECASE)):
            data = self.processTwitchURL(query)
        elif (self.checkReddit.search(query, re.IGNORECASE)):
            data = self.processReddit(query)
        else:
            data = self.processUrlThroughReddit(query)


        if (self.checkYoutube.search(query, re.IGNORECASE)):
            data["youtube"] = self.processYoutubeURL(query)

        if "youtube" in data:
            if "errorMessage" in data["youtube"]:
                data["errorMessage"] = data["youtube"]["errorMessage"]


        return self.parseReturnObject(data, action)

    def getRedditLink(self, id):
        return "http://www.reddit.com/by_id/t3_" + id + ".json"

    def getJsonFromUrl(self, url):
        return json_webservice(url)

    def truncate(self, s, width):
        s.lstrip()
        try:
            return s[0:width]
        except:
            return s

    def parseUrlPath(self, query):
        pathList = urlparse.urlsplit(query).path.split("/")
        if pathList[0] == "":
            pathList.pop(0)
        if len(pathList) > 0 and pathList[len(pathList) - 1] == "":
            pathList.pop(len(pathList) - 1)
        return pathList

    def parseUrlQuery(self, query):
      return dict((k, v if len(v)>1 else v[0]) for k, v in urlparse.parse_qs(urlparse.urlsplit(query).query).iteritems())

    def sec2hms(self, seconds):
        hours = seconds / 3600
        seconds -= 3600 * hours
        minutes = seconds / 60
        seconds -= 60 * minutes
        if hours == 0:
            return "%02d:%02d" % (minutes, seconds)
        return "%02d:%02d:%02d" % (hours, minutes, seconds)

    def pretty_date(self, time=False):
        from datetime import datetime
        now = datetime.now(self.botTimezone)
        if type(time) is int:
            diff = now - datetime.fromtimestamp(time)
        elif isinstance(time, datetime):
            diff = now - time
        elif not time:
            diff = now - now
        second_diff = diff.seconds
        day_diff = diff.days
 
        if day_diff < 0:
            return ''

        if day_diff == 0:
            if second_diff < 10:
                return "just now"
            if second_diff < 60:
                return str(second_diff) + " seconds ago"
            if second_diff < 120:
                return "a minute ago"
            if second_diff < 3600:
                return str(second_diff / 60) + " minutes ago"
            if second_diff < 7200:
                return "an hour ago"
            if second_diff < 86400:
                return str(second_diff / 3600) + " hours ago"
        if day_diff == 1:
            return "Yesterday"
        if day_diff < 7:
            return str(day_diff) + " days ago"
        if day_diff < 31:
            return str(day_diff / 7) + " weeks ago"
        if day_diff < 365:
            return str(day_diff / 30) + " months ago"
        return str(day_diff / 365) + " years ago"

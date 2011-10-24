from twisted.internet import reactor
from pprint import pformat

from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.web.http_headers import Headers
from twisted.internet.defer import succeed

#from twisted.python import log

from twisted.internet import task

from twisted.web.client import getPage

from zope.interface import implements

import sys

import urllib
import logging

debug_mode = False

logger = logging.getLogger('Sunshine.GaduAPI')

try:
    proper_twisted = True
    from twisted.web.iweb import IBodyProducer
    from twisted.web.client import Agent
except ImportError:
    logger.info("Twisted version is too old.")
    proper_twisted = False

try:
    import oauth.oauth as oauth
    test_oauth = oauth.OAuthSignatureMethod_HMAC_SHA1()
    oauth_loaded = True
except:
    logger.info("oAuth module can't be loaded")
    oauth_loaded = False

import xml.etree.ElementTree as ET
import json
import mimetools
import mimetypes
import time

REQUEST_TOKEN_URL = 'http://api.gadu-gadu.pl/request_token'
ACCESS_TOKEN_URL = 'http://api.gadu-gadu.pl/access_token'
AUTHORIZE_TOKEN_URL = 'http://login.gadu-gadu.pl/authorize'
PUT_AVATAR_URL = 'http://api.gadu-gadu.pl/avatars/%s/0.xml'
GET_INFO_URL = 'http://api.gadu-gadu.pl/users/%s.json'

def check_requirements():
    if proper_twisted == True and oauth_loaded == True:
        return True
    else:
        return False
        logger.info("Requirements related with Gadu-Gadu oAuth API support not fullfilled. You need twisted-core, twisted-web in version 9.0.0 or greater and python-oauth.")


class StringProducer(object):
    if check_requirements() == True:
        implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass

class BeginningPrinter(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.remaining = 1024 * 10
        self.body = ''

    def dataReceived(self, bytes):
        if self.remaining:
            display = bytes[:self.remaining]
            self.body = self.body+display
            self.remaining -= len(display)

    def connectionLost(self, reason):
        #print 'Finished receiving body:', reason.getErrorMessage()
        self.finished.callback(self.body)

class GG_Oauth(object):
    def __init__(self, uin, password):
        self.uin = uin
        self.password = password
        
        self.timestamp = 0
        self.expire_token = 0
        self.access_token = None
        
        self.__loopingcall = None
        
        self.agent = Agent(reactor)
        
        self.consumer = oauth.OAuthConsumer(self.uin, self.password)
        
        self._signature_method = oauth.OAuthSignatureMethod_HMAC_SHA1()

    #
    # REQUESTING TOKEN
    #

    def requestToken(self):
        if debug_mode:
            logger.info("requestToken")
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(self.consumer, http_method='POST', http_url=REQUEST_TOKEN_URL) # create an oauth request
        oauth_request.sign_request(self._signature_method, self.consumer, None) # the request knows how to generate a signature
        auth_header = oauth_request.to_header()
	headers = {}
        headers['Authorization'] = [auth_header['Authorization']]
        headers['Accept'] = ['application/json']
        headers['User-Agent'] = ['Gadu-Gadu Client, build 10,1,1,11119']
        headers['Host'] = ['api.gadu-gadu.pl']
	headers['Content-Length'] = [0]
        headers = Headers(headers)
        
        url = REQUEST_TOKEN_URL
        
        d = self.agent.request(
            'POST',
            REQUEST_TOKEN_URL,
            headers,
            None)
        
        d.addCallback(self.cbRequestToken)
        d.addErrback(self.cbShutdown)

    def cbRequestToken(self, response):
        if debug_mode:
            logger.info("cbRequestToken")
        mimetype = response.headers.getRawHeaders('Content-Type', 'text/xml')
        finished = Deferred()
        response.deliverBody(BeginningPrinter(finished))
        finished.addCallback(self.cbRequestTokenSuccess, mimetype[0])
        finished.addErrback(self.cbShutdown)
        return finished

    def cbRequestTokenSuccess(self, result, mimetype):
        if debug_mode:
            logger.info("cbRequestTokenSuccess result: %s, mime: %s" % (result, mimetype))
        content = {}
        if mimetype == 'application/json':
            content = json.loads(result)['result']
        elif mimetype == 'text/xml':
            xml = ET.fromstring(result)
            content['oauth_token'] = xml.find("oauth_token").text
            content['oauth_token_secret'] = xml.find("oauth_token_secret").text
        else:
            logger.info("cbRequestTokenSuccess failed: unknown mimetype.")
            return

        oauth_token = oauth.OAuthToken(content['oauth_token'], content['oauth_token_secret'])

        postvars = 'callback_url=http://www.mojageneracja.pl&request_token=%s&uin=%s&password=%s' % (oauth_token.key, self.uin, self.password)

        headers = {}
        headers['User-Agent'] = ['Gadu-Gadu Client, build 10,1,1,11119']
        headers['Accept'] = ['*/*']
        headers['Content-Type'] = ['application/x-www-form-urlencoded']

        headers = Headers(headers)

        body = StringProducer(str(postvars))

        d = self.agent.request(
            'POST',
            AUTHORIZE_TOKEN_URL,
            headers,
            body)

        d.addCallback(self.cbTokenAuthorised, oauth_token)
        d.addErrback(self.cbShutdown)

    def cbTokenAuthorised(self, result, oauth_token):
        if debug_mode:
            logger.info("cbTokenAuthorised")
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(self.consumer, token=oauth_token, http_method='POST', http_url=ACCESS_TOKEN_URL) # create an oauth request
        oauth_request.sign_request(self._signature_method, self.consumer, oauth_token) # the request knows how to generate a signature
        auth_header = oauth_request.to_header()

        headers = {}
        headers['Authorization'] = [auth_header['Authorization']]
        headers['User-Agent'] = ['Gadu-Gadu Client, build 10,1,1,11119']
        headers['Accept'] = ['application/json']
	headers['Content-Length'] = [0]
        headers = Headers(headers)

        d = self.agent.request(
            'POST',
            ACCESS_TOKEN_URL,
            headers,
            None)

        d.addCallback(self.requestAccessToken, oauth_token)
        d.addErrback(self.cbShutdown)

    def requestAccessToken(self, response, oauth_token):
        if debug_mode:
            logger.info("requestAccessToken")
        mimetype = response.headers.getRawHeaders('Content-Type', 'text/xml')
        finished = Deferred()
        response.deliverBody(BeginningPrinter(finished))
        finished.addCallback(self.accessTokenReceived, oauth_token, mimetype[0])
        finished.addErrback(self.cbShutdown)
        return finished

    def accessTokenReceived(self, result, oauth_token, mimetype):
        if debug_mode:
            logger.info("accessTokenReceived result: %s, mimetype: %s" % (result, mimetype))
        content = {}
        if mimetype == 'application/json':
            content = json.loads(result)['result']
        elif mimetype == 'text/xml':
            xml = ET.fromstring(result)
            content['oauth_token'] = xml.find("oauth_token").text
            content['oauth_token_secret'] = xml.find("oauth_token_secret").text
        else:
            logger.info("accessTokenReceived failed: unknown mimetype.")
            return

        self.access_token = oauth.OAuthToken(content['oauth_token'], content['oauth_token_secret'])
        self.expire_token = time.time()+36000

    def getContentType(self, filename):
        return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    def getExtByType(self, mime):
        return mimetypes.guess_extension(mime)
        
    def encodeMultipart(self, fields, files):
        """
        fields is a sequence of (name, value) elements for regular form fields.
        files is a sequence of (name, filename, value) elements for data to be uploaded as files
        Return (content_type, body) ready for httplib.HTTP instance
        """
        boundary = mimetools.choose_boundary()
        crlf = '\r\n'
        
        l = []
        for (k, v) in fields:
            l.append('--' + boundary)
            l.append('Content-Disposition: form-data; name="%s"' % k)
            l.append('')
            l.append(v)
        for (k, f, v) in files:
            l.append('--' + boundary)
            l.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (k, f))
            l.append('Content-Type: %s' % self.getContentType(f))
            l.append('')
            l.append(v)
        l.append('--' + boundary + '--')
        l.append('')
        body = crlf.join(l)
        
        return boundary, body
        
    def putAvatar(self, data, ext):
        if debug_mode:
            logger.info("accessTokenReceived")
        url = str(PUT_AVATAR_URL % self.uin)

        oauth_request = oauth.OAuthRequest.from_consumer_and_token(self.consumer, token=self.access_token, http_method='PUT', http_url=url) # create an oauth request
        oauth_request.sign_request(self._signature_method, self.consumer, self.access_token) # the request knows how to generate a signature
        auth_header = oauth_request.to_header()
        
        filename = str(self.uin)+ext
        
        (boundary, body) = self.encodeMultipart(fields=(('_method', 'PUT'),), files=(('avatar', filename, data),))
        body = StringProducer(str(body))
        
        headers = {}
        #headers['Connection'] = ['keep-alive']
        headers['Authorization'] = [auth_header['Authorization']]
        headers['User-Agent'] = ['Gadu-Gadu Client, build 10,1,1,11119']
        headers['Accept'] = ['*/*']
        headers['Content-Type'] = ['multipart/form-data; boundary=%s' % boundary]
        headers = Headers(headers)
        
        d = self.agent.request(
            'POST',
            url,
            headers,
            body)
        
        d.addCallback(self.putAvatarSuccess)
        d.addErrback(self.cbShutdown)
        
    def putAvatarSuccess(self, response):
        logger.info("New avatar should be uploaded now.")
    
    def fetchUserInfo(self, uin):
        if debug_mode:
            logger.info("fetchUserInfo")
        url = str(GET_INFO_URL % uin)
        
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(self.consumer, token=self.access_token, http_method='GET', http_url=url) # create an oauth request
        oauth_request.sign_request(self._signature_method, self.consumer, self.access_token) # the request knows how to generate a signature
        auth_header = oauth_request.to_header()
        
        headers = {}
        #headers['Connection'] = ['keep-alive']
        headers['Authorization'] = [auth_header['Authorization']]
        headers['User-Agent'] = ['Gadu-Gadu Client, build 10,1,1,11119']
        headers['Accept'] = ['*/*']
        headers = Headers(headers)
        
        d = self.agent.request(
            'GET',
            url,
            headers,
            None)
        
        d.addCallback(self.fetchUserInfoSuccess)
        d.addErrback(self.cbShutdown)
        
    def fetchUserInfoSuccess(self, response):
        if debug_mode:
            logger.info("fetchUserInfoSuccess")
        finished = Deferred()
        response.deliverBody(BeginningPrinter(finished))
        finished.addCallback(self.onUserInfoRecv)
        finished.addErrback(self.cbShutdown)
        return finished

    def onUserInfoRecv(self, result):
        if debug_mode:
            logger.info("onUserInfoRecv")
        content = json.loads(result)['result']
        self.onUserInfo(content)
        
    def onUserInfo(self, result):
        pass
    
    def cbShutdown(self, reason):
        logger.info("Something went wrong: %s" % (reason))
    
    def checkTokenForAvatar(self, data, ext):
        if debug_mode:
            logger.info("checkTokenForAvatar")
        #print 'checkTokenForAvatar'
        if int(time.time()) <= self.expire_token and self.access_token != None:
            self.putAvatar(data, ext)
            self.__loopingcall.stop()
    
    def checkTokenForUserInfo(self, uin):
        if debug_mode:
            logger.info("checkTokenForUserInfo")
        if int(time.time()) <= self.expire_token and self.access_token != None:
            self.fetchUserInfo(uin)
            self.__loopingcall.stop()

    def getToken(self):
        self.requestToken()
            
    def uploadAvatar(self, data, ext):
        if debug_mode:
            logger.info("uploadAvatar")
        if int(time.time()) <= self.expire_token and self.access_token != None:
            self.putAvatar(data, ext)
        else:
            self.requestToken()
            self.__loopingcall = task.LoopingCall(self.checkTokenForAvatar, data, ext)
            self.__loopingcall.start(1.0)

    def getUserInfo(self, uin):
        if debug_mode:
            logger.info("getUserInfo")
        if int(time.time()) <= self.expire_token and self.access_token != None:
            self.fetchUserInfo(uin)
        else:
            self.requestToken()
            self.__loopingcall = task.LoopingCall(self.checkTokenForUserInfo, uin)
            self.__loopingcall.start(1.0)
            
    def getUserInfoDeffered(self, uin):
        if debug_mode:
            logger.info("getUserInfoDeffered")
        d = Deferred()
        if int(time.time()) <= self.expire_token and self.access_token != None:
            d.addCallback(self.onUserInfoRecv)
            d.addErrback(self.cbShutdown)
        else:
            self.requestToken()
            self.__loopingcall = task.LoopingCall(self.checkTokenForUserInfo, uin)
            self.__loopingcall.start(1.0)
        return d

#if check_requirements() == True:
#    gg = GG_Oauth(4634020, 'xxxxxx')
    #data = open('avatar.png', 'r').read()
    #ext = mimetypes.guess_extension(mimetypes.guess_type('avatar.png')[0])
    #gg.uploadAvatar(data, ext)
#    gg.getUserInfo('5120225')
#else:
#    print 'GG_oAuth_API: Requirements related with Gadu-Gadu oAuth API support not fullfilled. You need twisted-core, twisted-web in version 9.0.0 or greater and python-oauth.'

#log.startLogging(sys.stdout)
#reactor.run()

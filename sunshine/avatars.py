# telepathy-sunshine is the GaduGadu connection manager for Telepathy
#
# Copyright (C) 2006-2007 Ali Sabil <ali.sabil@gmail.com>
# Copyright (C) 2010 Krzysztof Klinikowski <kkszysiu@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import logging
import imghdr
import hashlib
import dbus
import StringIO
from sunshine.lqsoft.gaduapi import *

import telepathy

from twisted.web.client import getPage
from twisted.internet.task import coiterate

from xml.dom import minidom

from sunshine.handle import SunshineHandleFactory
from sunshine.util.decorator import async

__all__ = ['SunshineAvatars']

logger = logging.getLogger('Sunshine.Avatars')

SUPPORTED_AVATAR_MIME_TYPES = dbus.Array(["image/png", "image/jpeg", "image/gif"], signature='s')
MINIMUM_AVATAR_PIXELS = dbus.UInt32(96)
RECOMMENDED_AVATAR_PIXELS = dbus.UInt32(96)
MAXIMUM_AVATAR_PIXELS = dbus.UInt32(256)
MAXIMUM_AVATAR_BYTES = dbus.UInt32(500 * 1024)

class SunshineAvatars(telepathy.server.ConnectionInterfaceAvatars):

    def __init__(self):
        self.avatars_urls = {}
        telepathy.server.ConnectionInterfaceAvatars.__init__(self)
        
        dbus_interface = telepathy.CONNECTION_INTERFACE_AVATARS
        self._implement_property_get(dbus_interface, {
            'SupportedAvatarMIMETypes':
            lambda: SUPPORTED_AVATAR_MIME_TYPES,
            'MinimumAvatarHeight': lambda: MINIMUM_AVATAR_PIXELS,
            'MinimumAvatarWidth': lambda: MINIMUM_AVATAR_PIXELS,
            'RecommendedAvatarHeight': lambda: RECOMMENDED_AVATAR_PIXELS,
            'RecommendedAvatarWidth': lambda: RECOMMENDED_AVATAR_PIXELS,
            'MaximumAvatarHeight': lambda: MAXIMUM_AVATAR_PIXELS,
            'MaximumAvatarWidth': lambda: MAXIMUM_AVATAR_PIXELS,
            'MaximumAvatarBytes': lambda: MAXIMUM_AVATAR_BYTES,
        })

    def GetAvatarRequirements(self):
        return (SUPPORTED_AVATAR_MIME_TYPES,
                MINIMUM_AVATAR_PIXELS, MINIMUM_AVATAR_PIXELS,
                MAXIMUM_AVATAR_PIXELS, MAXIMUM_AVATAR_PIXELS,
                MAXIMUM_AVATAR_BYTES)

    def GetKnownAvatarTokens(self, contacts):
        result = {}
        for handle_id in contacts:
            handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
            if handle == self.GetSelfHandle():
                logger.info("Avatar for self handle...")
                #tutaj kiedys trzeba napisac kod odp za naszego avatara
                result[handle] = "1"
            url = 'http://api.gadu-gadu.pl/avatars/%s/0.xml' % (str(handle.name))
            d = getPage(url, timeout=10)
            d.addCallback(self.on_fetch_avatars_file_ok, url, handle)
            d.addErrback(self.on_fetch_avatars_file_failed, url, handle)
        return result

    def RequestAvatars(self, contacts):
        def simpleIterate(contacts):
            if len(contacts) > 0:
                for handle_id in contacts:
                    handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)

                    d = getPage(str(self.avatars_urls[handle.name]['avatar']), timeout=20)
                    d.addCallback(self.on_fetch_avatars_ok, handle)
                    d.addErrback(self.on_fetch_avatars_failed, handle)

                    yield d
        coiterate(simpleIterate(contacts))

    def SetAvatar(self, avatar, mime_type):
        if check_requirements() == True:
            if not isinstance(avatar, str):
                avatar = "".join([chr(b) for b in avatar])
                data = StringIO.StringIO(avatar).getvalue()
                ext = self.ggapi.getExtByType(mime_type)
                self.ggapi.uploadAvatar(data, ext)
        return str(self.profile.uin).encode("hex")

    def ClearAvatar(self):
        pass

    def getAvatar(self, sender, url):
        handle_id = self.get_handle_id_by_name(telepathy.constants.HANDLE_TYPE_CONTACT, str(sender))

        if handle_id != 0:
            handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
            
            h = hashlib.new('md5')
            h.update(handle.name)
            h.update(url)
            token = h.hexdigest()
            
            self.avatars_urls[handle.name] = {}
            self.avatars_urls[handle.name]['token'] = token
            self.avatars_urls[handle.name]['avatar'] = url
            
            d = getPage(str(url), timeout=20)
            d.addCallback(self.on_fetch_avatars_ok, handle)
            d.addErrback(self.on_fetch_avatars_failed, handle)

    def on_fetch_avatars_file_ok(self, result, url, handle):
        try:
            if result:
                logger.info("Avatar file retrieved from %s" % (url))
                e = minidom.parseString(result)
                if e.getElementsByTagName('avatar')[0].attributes["blank"].value != '1':
                    timestamp = e.getElementsByTagName('timestamp')[0].firstChild.data
                    avatar = e.getElementsByTagName('bigAvatar')[0].firstChild.data
                    
                    h = hashlib.new('md5')
                    h.update(handle.name)
                    h.update(timestamp)
                    token = h.hexdigest()
                    
                    self.avatars_urls[handle.name] = {}
                    self.avatars_urls[handle.name]['token'] = token
                    self.avatars_urls[handle.name]['avatar'] = avatar
                    
                    self.AvatarUpdated(handle, token)
        except:
            logger.info("Avatar file can't be retrieved from %s" % (url))

    def on_fetch_avatars_file_failed(self, error, url, handle_id):
        logger.info("Avatar file can't be retrieved from %s, error: %s" % (url, error.getErrorMessage()))

    def on_fetch_avatars_ok(self, result, handle):
        try:
            logger.info("Avatar retrieved for %s" % (handle.name))
            type = imghdr.what('', result)
            if type is None: type = 'jpeg'
            avatar = dbus.ByteArray(result)
            
            token = self.avatars_urls[handle.name]['token']
            
            self.AvatarRetrieved(handle, token, avatar, 'image/' + type)
        except:
            logger.debug("Avatar retrieved but something went wrong.")

    def on_fetch_avatars_failed(self, error, handle):
        logger.debug("Avatar not retrieved, error: %s" % (error.getErrorMessage()))

# telepathy-sunshine is the GaduGadu connection manager for Telepathy
#
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
import dbus
import dbus.service

from sunshine.Connection_Interface_Contact_Info import ConnectionInterfaceContactInfo

import telepathy
import telepathy.constants
import telepathy.errors

from twisted.internet import defer

from sunshine.handle import SunshineHandleFactory
from sunshine.util.decorator import async

__all__ = ['SunshineContactInfo']

logger = logging.getLogger('Sunshine.ContactInfo')

CONNECTION_INTERFACE_CONTACT_INFO = 'org.freedesktop.Telepathy.Connection.Interface.ContactInfo'

# Contact_Info_Flag
CONTACT_INFO_FLAG_CAN_SET = 1
CONTACT_INFO_FLAG_PUSH = 2
LAST_CONTACT_INFO_FLAG = 2
# Contact_Info_Field_Flags (bitfield/set of flags, 0 for none)
CONTACT_INFO_FIELD_FLAG_PARAMETERS_MANDATORY = 1

class SunshineContactInfo(ConnectionInterfaceContactInfo):
    def __init__(self):
        logger.info('SunshineContactInfo called.')
        ConnectionInterfaceContactInfo.__init__(self)
        
        self.ggapi.onUserInfo = self.onUserInfo
        
        dbus_interface = CONNECTION_INTERFACE_CONTACT_INFO
        
        self._implement_property_get(dbus_interface, {
            'ContactInfoFlags': lambda: self.contact_info_flags,
            'SupportedFields': lambda: self.contact_info_supported_fields,
        })

    @property
    def contact_info_flags(self):
        return (CONTACT_INFO_FLAG_CAN_SET | CONTACT_INFO_FLAG_PUSH)

    @property
    def contact_info_supported_fields(self):
        return dbus.Array([
                  ('nickname', ['type=home'], 0, 1),
                  ('fn', ['type=home'], 0, 1),
                  ('label', ['type=home'], 0, 1),
                  ('bday', ['type=home'], 0, 1),
                  ('url', ['type=home', 'type=mg'], 0, 2)
                ])

    def GetContactInfo(self, contacts):
        logger.info("GetContactInfo")
        tmp = {}
        for contact in contacts:
            tmp[contact] = []
        return tmp

    def RefreshContactInfo(self, contacts):
        logger.info('RefreshContactInfo')
        for handle_id in contacts:
            handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
            self.ggapi.getUserInfo(str(handle.name))
        pass
    
    @dbus.service.method(CONNECTION_INTERFACE_CONTACT_INFO, in_signature='u', out_signature='a(sasas)',
                         async_callbacks=('reply_handler', 'error_handler'))
    def RequestContactInfo(self, contact, reply_handler, error_handler):
        logger.info('RequestContactInfo')
        handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, contact)
        self.ggapi.getUserInfo(str(handle.name))
        #TODO: This need to be fixed as soon as possible.
        #d = Deferred()
        #d = self.ggapi.getUserInfoDeffered(str(handle.name))
        #d.addCallbacks(reply_handler, error_handler)
        #d.callback(result)
        #print 'result:', result
        #return d
        reply_handler([])
        return []
        
    def SetContactInfo(self, contactinfo):
        logger.info('SetContactInfo')
        pass
        
    def onUserInfo(self, result):
        if 'users' in result:
            for user in result['users']:
                if '_uin' in user:
                    info = []
                    if 'nick' in user:
                        if '_content' in user['nick']:
                            info.append(('nickname', ['type=home'], [user['nick']['_content']]))
                    if 'name' in user:
                        if '_content' in user['name']:
                            fn = user['name']['_content']
                            if 'surname' in user:
                                if '_content' in user['surname']:
                                    fn += ' '+user['surname']['_content']
                            info.append(('fn', ['type=home'], [fn]))
                    if 'city' in user:
                        if '_content' in user['city']:
                            info.append(('label', ['type=home'], [user['city']['_content']]))
                    if 'birth' in user:
                        if '_content' in user['birth']:
                            info.append(('bday', ['type=home'], [user['birth']['_content'][:-15]]))
                    if 'hasActiveMGProfile' in user:
                        if user['hasActiveMGProfile'] == True:
                            mg = 'https://www.mojageneracja.pl/%s' % (user['_uin'])
                            info.append(('url', ['type=mg'], [mg]))
                    if 'wwwUrl' in user:
                        if '_content' in user['wwwUrl']:
                            info.append(('url', ['type=home'], [user['wwwUrl']['_content']]))

                    handle_id = self.get_handle_id_by_name(telepathy.constants.HANDLE_TYPE_CONTACT, str(user['_uin']))
                    handle = self.handle(telepathy.constants.HANDLE_TYPE_CONTACT, handle_id)
                    self.ContactInfoChanged(handle, info)
                        
        


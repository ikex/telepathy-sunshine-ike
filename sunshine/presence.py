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

# Implementation of the SimplePresence specification at :
# http://telepathy.freedesktop.org/spec.html#org.freedesktop.Telepathy.Connection.Interface.SimplePresence

import logging
import time

import dbus
import telepathy
import telepathy.constants
import telepathy.errors

from sunshine.handle import SunshineHandleFactory
from sunshine.util.decorator import async

__all__ = ['SunshinePresence']

logger = logging.getLogger('Sunshine.Presence')


class SunshinePresenceMapping(object):
    #from busy to away
    #from idle to dnd
    ONLINE = 'available'
    FFC  = 'free_for_chat'
    AWAY = 'away'
    DND = 'dnd'
    INVISIBLE = 'hidden'
    OFFLINE = 'offline'

    to_gg = {
            ONLINE:     'AVAILABLE',
            AWAY:       'BUSY',
            DND:        'DND',
            INVISIBLE:  'HIDDEN',
            OFFLINE:    'NOT_AVAILABLE'
            }

    to_telepathy = {
            'AVAILABLE':                ONLINE,
            'FFC':                      FFC,
            'BUSY':                     AWAY,
            'DND':                      DND,
            'HIDDEN':                   INVISIBLE,
            'NOT_AVAILABLE':            OFFLINE
            }

    from_gg_to_tp = {
            0:                          OFFLINE,
            0x0001:                     OFFLINE,
            0x4015:                     OFFLINE,
            0x0017:                     ONLINE,
            0x4018:                     ONLINE,
            0x0002:                     ONLINE,
            0x4004:                     ONLINE,
            0x0003:                     AWAY,
            0x4005:                     AWAY,
            0x0021:                     DND,
            0x4022:                     DND,
            0x0014:                     INVISIBLE,
            0x4016:                     INVISIBLE,
            #Opisy graficzne
            #Z tego co mi sie wydaje one zawsze maja maske "z opisem"
            0x4115:                     OFFLINE,
            0x4118:                     ONLINE,
            0x4104:                     ONLINE,
            0x4105:                     AWAY,
            0x4122:                     DND,
            0x4116:                     INVISIBLE,
            # Jakis dziwny status, nie wiem skad sie wzial
            0x4020:			OFFLINE,
            0x4120:			OFFLINE
    }

    to_presence_type = {
            ONLINE:     dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_AVAILABLE),
            FFC:        dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_AVAILABLE),
            AWAY:       dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_AWAY),
            DND:        dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_BUSY),
            INVISIBLE:  dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_HIDDEN),
            OFFLINE:    dbus.UInt32(telepathy.constants.CONNECTION_PRESENCE_TYPE_OFFLINE)
            }

class SunshinePresence(telepathy.server.ConnectionInterfaceSimplePresence):

    def __init__(self):
        telepathy.server.ConnectionInterfaceSimplePresence.__init__(self)

        self.presence = None
        self.personal_message = None

        self._implement_property_get(
            telepathy.CONNECTION_INTERFACE_SIMPLE_PRESENCE, {
                'Statuses' : lambda: self._protocol.statuses
            })

    # SimplePresence

    def GetPresences(self, contacts):
        return self.get_simple_presences(contacts)

    def SetPresence(self, status, message):
        if status == SunshinePresenceMapping.OFFLINE:
            self.Disconnect()

        try:
            presence = SunshinePresenceMapping.to_gg[status]
        except KeyError:
            raise telepathy.errors.InvalidArgument

        logger.info("Setting Presence to '%s'" % presence)
        logger.info("Setting Personal message to '%s'" % message)

        message = message.encode('UTF-8')

        self.presence = presence
        self.personal_message = message

        if self._status == telepathy.CONNECTION_STATUS_CONNECTED:
            self._self_presence_changed(SunshineHandleFactory(self, 'self'), presence, message)
            self.profile.setMyState(presence, message)
        else:
            self._self_presence_changed(SunshineHandleFactory(self, 'self'), presence, message)
            
    def get_simple_presences(self, contacts):
        presences = dbus.Dictionary(signature='u(uss)')
        for handle_id in contacts:
            handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
            if handle == SunshineHandleFactory(self, 'self'):
                presence = SunshinePresenceMapping.to_telepathy[self.presence]
                personal_message = self.personal_message
            else:
                #I dont know what to do here. Do I really need this? :P
                contact = handle.contact
                if contact is not None:
		    if contact.status in SunshinePresenceMapping.from_gg_to_tp:
			presence = SunshinePresenceMapping.from_gg_to_tp[contact.status]
                    else:
			presence = SunshinePresenceMapping.from_gg_to_tp[0]
                    personal_message = str('')
                else:
                    presence = SunshinePresenceMapping.OFFLINE
                    personal_message = u""

            presence_type = SunshinePresenceMapping.to_presence_type[presence]

            presences[handle] = dbus.Struct((presence_type, presence, personal_message), signature='uss')
        return presences

    #@async
    def _presence_changed(self, handle, presence, personal_message):
        try:
            presence = SunshinePresenceMapping.from_gg_to_tp[presence]
        except KeyError:
            presence = SunshinePresenceMapping.from_gg_to_tp[0]
        presence_type = SunshinePresenceMapping.to_presence_type[presence]
        personal_message = unicode(str(personal_message), "utf-8").replace('\x00', '')

        self.PresencesChanged({handle: (presence_type, presence, personal_message)})


    #@async
    def _self_presence_changed(self, handle, presence, personal_message):
        presence = SunshinePresenceMapping.to_telepathy[presence]
        presence_type = SunshinePresenceMapping.to_presence_type[presence]
        personal_message = unicode(str(personal_message), "utf-8")

        self.PresencesChanged({handle: (presence_type, presence, personal_message)})


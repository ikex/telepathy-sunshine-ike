# telepathy-sunshine is the GaduGadu connection manager for Telepathy
#
# Copyright (C) 2011 Krzysztof Klinikowski <kkszysiu@gmail.com>
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

import telepathy

from sunshine.connection import SunshineConnection
from sunshine.presence import SunshinePresenceMapping

from sunshine.Protocol_Interface_Avatars import ProtocolInterfaceAvatars

__all__ = ['SunshineProtocol']

logger = logging.getLogger('Sunshine.Protocol')

class SunshineProtocol(telepathy.server.Protocol,
                        telepathy.server.ProtocolInterfacePresence,
                        ProtocolInterfaceAvatars):

    _proto = "gadugadu"
    _vcard_field = ""
    _english_name = "Gadu-Gadu"
    _icon = "im-gadugadu"

    _secret_parameters = set([
            'password'
            ])
    _mandatory_parameters = {
            'account' : 's',
            'password' : 's'
            }
    _optional_parameters = {
            'server' : 's',
            'port' : 'q',
            'export-contacts' : 'b',
            'use-ssl' : 'b',
            'use-specified-server' : 'b'
            }
    _parameter_defaults = {
            'server' : '91.197.13.67',
            'port' : 8074,
            'export-contacts' : False,
            'use-ssl' : True,
            'use-specified-server' : False
            }

    _requestable_channel_classes = [
        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_TEXT),
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID']),

        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': telepathy.CHANNEL_TYPE_TEXT,
            telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_ROOM)},
            [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
            telepathy.CHANNEL_INTERFACE + '.TargetID']),

        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_CONTACT_LIST),
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_GROUP)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID']),

        ({telepathy.CHANNEL_INTERFACE + '.ChannelType': dbus.String(telepathy.CHANNEL_TYPE_CONTACT_LIST),
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_LIST)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID']),
        ]

    _supported_interfaces = [
            telepathy.CONNECTION_INTERFACE_ALIASING,
            telepathy.CONNECTION_INTERFACE_AVATARS,
            telepathy.CONNECTION_INTERFACE_CAPABILITIES,
            telepathy.CONNECTION_INTERFACE_CONTACT_CAPABILITIES,
            telepathy.CONNECTION_INTERFACE_PRESENCE,
            telepathy.CONNECTION_INTERFACE_SIMPLE_PRESENCE,
            telepathy.CONNECTION_INTERFACE_CONTACTS,
            telepathy.CONNECTION_INTERFACE_REQUESTS,
            telepathy.CONNECTION_INTERFACE_CONTACT_INFO
        ]

    _statuses = {
            SunshinePresenceMapping.ONLINE:(
                telepathy.CONNECTION_PRESENCE_TYPE_AVAILABLE,
                True, True),
            SunshinePresenceMapping.AWAY:(
                telepathy.CONNECTION_PRESENCE_TYPE_AWAY,
                True, True),
            SunshinePresenceMapping.DND:(
                telepathy.CONNECTION_PRESENCE_TYPE_BUSY,
                True, True),
            SunshinePresenceMapping.INVISIBLE:(
                telepathy.CONNECTION_PRESENCE_TYPE_HIDDEN,
                True, True),
            SunshinePresenceMapping.OFFLINE:(
                telepathy.CONNECTION_PRESENCE_TYPE_OFFLINE,
                True, True)
            }


    def __init__(self, connection_manager):
        telepathy.server.Protocol.__init__(self, connection_manager, 'gadugadu')
        telepathy.server.ProtocolInterfacePresence.__init__(self)
        ProtocolInterfaceAvatars.__init__(self)

    def create_connection(self, connection_manager, parameters):
        return SunshineConnection(self, connection_manager, parameters)

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
import weakref

import dbus
import telepathy

from sunshine.channel.contact_list import SunshineContactListChannelFactory
from sunshine.channel.group import SunshineGroupChannel
from sunshine.channel.text import SunshineTextChannel, SunshineRoomTextChannel
#from sunshine.channel.media import SunshineMediaChannel
from sunshine.handle import SunshineHandleFactory

__all__ = ['SunshineChannelManager']

logger = logging.getLogger('Sunshine.ChannelManager')

class SunshineChannelManager(telepathy.server.ChannelManager):
    def __init__(self, connection):
        telepathy.server.ChannelManager.__init__(self, connection)

        fixed = {telepathy.CHANNEL_INTERFACE + '.ChannelType': telepathy.CHANNEL_TYPE_TEXT,
            telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)}
        self._implement_channel_class(telepathy.CHANNEL_TYPE_TEXT,
            self._get_text_channel, fixed, [])

        fixed = {telepathy.CHANNEL_INTERFACE + '.ChannelType': telepathy.CHANNEL_TYPE_TEXT,
            telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_ROOM)}
        self._implement_channel_class(telepathy.CHANNEL_TYPE_TEXT,
            self._get_text_channel, fixed, [])

        fixed = {telepathy.CHANNEL_INTERFACE + '.ChannelType': telepathy.CHANNEL_TYPE_CONTACT_LIST}
        self._implement_channel_class(telepathy.CHANNEL_TYPE_CONTACT_LIST,
            self._get_list_channel, fixed, [])

#        fixed = {telepathy.CHANNEL_INTERFACE + '.ChannelType': telepathy.CHANNEL_TYPE_STREAMED_MEDIA,
#            telepathy.CHANNEL_INTERFACE + '.TargetHandleType': dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)}
#        self._implement_channel_class(telepathy.CHANNEL_TYPE_STREAMED_MEDIA,
#            self._get_media_channel, fixed, [telepathy.CHANNEL_INTERFACE + '.TargetHandle'])

    def _get_list_channel(self, props):
        _, surpress_handler, handle = self._get_type_requested_handle(props)

        if handle.get_type() == telepathy.HANDLE_TYPE_GROUP:
            channel = SunshineGroupChannel(self._conn, self, props)
            logger.debug('New group channel')
        else:
            channel = SunshineContactListChannelFactory(self._conn,
                self, handle, props)
            logger.debug('New contact list channel: %s' % (handle.name))
        return channel

    def _get_text_channel(self, props, conversation=None):
        _, surpress_handler, handle = self._get_type_requested_handle(props)

        if handle.get_type() == telepathy.HANDLE_TYPE_CONTACT:
            logger.debug('New text channel for contact handle, name: %s, id: %s, type: %s' % (handle.name, handle.id, handle.type))

            channel = SunshineTextChannel(self._conn, self, conversation, props)
            return channel
        elif handle.get_type() == telepathy.HANDLE_TYPE_ROOM:
            logger.debug('New text channel for room handle, name: %s, id: %s, type: %s' % (handle.name, handle.id, handle.type))

            channel = SunshineRoomTextChannel(self._conn, self, conversation, props)
            return channel
        else:
            raise telepathy.NotImplemented('Unknown handle for text channel.')


#    def _get_media_channel(self, props, call=None):
#        _, surpress_handler, handle = self._get_type_requested_handle(props)
#
#        if handle.get_type() != telepathy.HANDLE_TYPE_CONTACT:
#            raise telepathy.NotImplemented('Only contacts are allowed')
#
#        contact = handle.contact
#
##        if contact.presence == papyon.Presence.OFFLINE:
##            raise telepathy.NotAvailable('Contact not available')
#
#        logger.debug('New media channel')
#
#        if call is None:
#            client = self._conn.msn_client
#            call = client.call_manager.create_call(contact)
#
#        return GaduMediaChannel(self._conn, self, call, handle, props)

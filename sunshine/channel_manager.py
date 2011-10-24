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
from string import ascii_letters, digits

import dbus
import telepathy

from sunshine.channel.contact_list import SunshineContactListChannelFactory
from sunshine.channel.group import SunshineGroupChannel
from sunshine.channel.text import SunshineTextChannel, SunshineRoomTextChannel
#from sunshine.channel.media import SunshineMediaChannel
from sunshine.handle import SunshineHandleFactory

#from butterfly.Channel_Interface_Conference import CHANNEL_INTERFACE_CONFERENCE

__all__ = ['SunshineChannelManager']

logger = logging.getLogger('Sunshine.ChannelManager')

_ASCII_ALNUM = ascii_letters + digits

# copy/pasted from tp-glib's libtpcodegen
def escape_as_identifier(identifier):
    """Escape the given string to be a valid D-Bus object path or service
    name component, using a reversible encoding to ensure uniqueness.

    The reversible encoding is as follows:

    * The empty string becomes '_'
    * Otherwise, each non-alphanumeric character is replaced by '_' plus
      two lower-case hex digits; the same replacement is carried out on
      the first character, if it's a digit
    """
    # '' -> '_'
    if not identifier:
        return '_'

    # A bit of a fast path for strings which are already OK.
    # We deliberately omit '_' because, for reversibility, that must also
    # be escaped.
    if (identifier.strip(_ASCII_ALNUM) == '' and
        identifier[0] in ascii_letters):
        return identifier

    # The first character may not be a digit
    if identifier[0] not in ascii_letters:
        ret = ['_%02x' % ord(identifier[0])]
    else:
        ret = [identifier[0]]

    # Subsequent characters may be digits or ASCII letters
    for c in identifier[1:]:
        if c in _ASCII_ALNUM:
            ret.append(c)
        else:
            ret.append('_%02x' % ord(c))

    return ''.join(ret)

class SunshineChannelManager(telepathy.server.ChannelManager):
    __text_channel_id = 1
    __media_channel_id = 1

    def __init__(self, connection, protocol):
        telepathy.server.ChannelManager.__init__(self, connection)

        self.set_requestable_channel_classes(protocol.requestable_channels)

        self.implement_channel_classes(telepathy.CHANNEL_TYPE_TEXT, self._get_text_channel)
        self.implement_channel_classes(telepathy.CHANNEL_TYPE_CONTACT_LIST, self._get_list_channel)
        #self.implement_channel_classes(telepathy.CHANNEL_TYPE_STREAMED_MEDIA, self._get_media_channel)
        #self.implement_channel_classes(telepathy.CHANNEL_TYPE_FILE_TRANSFER, self._get_ft_channel)

    def _get_list_channel(self, props):
        _, surpress_handler, handle = self._get_type_requested_handle(props)

        logger.debug('New contact list channel')

        if handle.get_type() == telepathy.HANDLE_TYPE_GROUP:
            path = "RosterChannel/Group/%s" % escape_as_identifier(handle.get_name())
            channel = SunshineGroupChannel(self._conn, self, props, object_path=path)
        else:
            channel = SunshineContactListChannelFactory(self._conn,
                self, handle, props)
        return channel

    def _get_text_channel(self, props, conversation=None):
        _, surpress_handler, handle = self._get_type_requested_handle(props)

        path = "TextChannel%d" % self.__text_channel_id
        self.__text_channel_id += 1

        if handle.get_type() == telepathy.HANDLE_TYPE_CONTACT:
            logger.debug('New text channel for contact handle, name: %s, id: %s, type: %s' % (handle.name, handle.id, handle.type))

            channel = SunshineTextChannel(self._conn, self, conversation, props, object_path=path)
            return channel
        elif handle.get_type() == telepathy.HANDLE_TYPE_ROOM:
            logger.debug('New text channel for room handle, name: %s, id: %s, type: %s' % (handle.name, handle.id, handle.type))

            channel = SunshineRoomTextChannel(self._conn, self, conversation, props, object_path=path)
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

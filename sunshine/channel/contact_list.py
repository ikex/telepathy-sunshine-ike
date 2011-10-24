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

import telepathy

import xml.etree.ElementTree as ET

from sunshine.util.decorator import async
from sunshine.handle import SunshineHandleFactory
from sunshine.channel import SunshineChannel

from twisted.internet import reactor, defer

from sunshine.lqsoft.pygadu.twisted_protocol import GaduClient
from sunshine.lqsoft.pygadu.models import GaduProfile, GaduContact

__all__ = ['SunshineContactListChannelFactory']

logger = logging.getLogger('Sunshine.ContactListChannel')

def SunshineContactListChannelFactory(connection, manager, handle, props):
    handle = connection.handle(
        props[telepathy.CHANNEL_INTERFACE + '.TargetHandleType'],
        props[telepathy.CHANNEL_INTERFACE + '.TargetHandle'])

    if handle.get_name() == 'stored':
        raise telepathy.errors.NotImplemented
    elif handle.get_name() == 'subscribe':
        channel_class = SunshineSubscribeListChannel
    elif handle.get_name() == 'publish':
        raise telepathy.errors.NotImplemented
    elif handle.get_name() == 'hide':
        raise telepathy.errors.NotImplemented
    elif handle.get_name() == 'allow':
        raise telepathy.errors.NotImplemented
    elif handle.get_name() == 'deny':
        raise telepathy.errors.NotImplemented
    else:
        logger.error("Unknown list type : " + handle.get_name())
        raise telepathy.errors.InvalidHandle
    return channel_class(connection, manager, props)


class SunshineListChannel(
        SunshineChannel,
        telepathy.server.ChannelTypeContactList,
        telepathy.server.ChannelInterfaceGroup):
    "Abstract Contact List channels"

    def __init__(self, connection, manager, props, object_path=None):
        self._conn_ref = weakref.ref(connection)
        telepathy.server.ChannelTypeContactList.__init__(self, connection, manager, props, object_path=object_path)
        SunshineChannel.__init__(self, connection, props)
        telepathy.server.ChannelInterfaceGroup.__init__(self)
        self._populate(connection)

    def GetLocalPendingMembersWithInfo(self):
        return []

    def _populate(self, connection):
        added = set()
        local_pending = set()
        remote_pending = set()

        for contact in connection.gadu_client.contacts:
            #logger.info("New contact %s, name: %s added." % (contact.uin, contact.ShowName))
            ad, lp, rp = self._filter_contact(contact)
            if ad or lp or rp:
                handle = SunshineHandleFactory(self._conn_ref(), 'contact',
                        contact.uin, None)
                #capabilities
                self._conn_ref().contactAdded(handle)
                if ad: added.add(handle)
                if lp: local_pending.add(handle)
                if rp: remote_pending.add(handle)
        #self._conn_ref()._populate_capabilities()
        #capabilities for self handle
        self._conn_ref().contactAdded(self._conn_ref().GetSelfHandle())
        self.MembersChanged('', added, (), local_pending, remote_pending, 0,
                telepathy.CHANNEL_GROUP_CHANGE_REASON_NONE)

    def _filter_contact(self, contact):
        return (False, False, False)

    def _contains_handle(self, handle):
        members, local_pending, remote_pending = self.GetAllMembers()
        return (handle in members) or (handle in local_pending) or \
                (handle in remote_pending)


class SunshineSubscribeListChannel(SunshineListChannel):
    """Subscribe List channel.

    This channel contains the list of contact to whom the current used is
    'subscribed', basically this list contains the contact for whom you are
    supposed to receive presence notification."""

    def __init__(self, connection, manager, props):
        SunshineListChannel.__init__(self, connection, manager, props,
                object_path='RosterChannel/List/subscribe')
        self.GroupFlagsChanged(telepathy.CHANNEL_GROUP_FLAG_CAN_ADD |
                telepathy.CHANNEL_GROUP_FLAG_CAN_REMOVE, 0)

    def AddMembers(self, contacts, message):
        logger.info("Subscribe - AddMembers called")
        for h in contacts:
            self._add(h, message)

    def RemoveMembers(self, contacts, message):
        for h in contacts:
            self._remove(h)
        self._conn_ref().exportContactsFile()

    def _filter_contact(self, contact):
        return (True, False, False)

    def _add(self, handle_id, message):
        handle = self._conn.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
        if handle.contact is not None:
            return True

        contact_xml = ET.Element("Contact")
        ET.SubElement(contact_xml, "Guid").text = str(handle.name)
        ET.SubElement(contact_xml, "GGNumber").text = str(handle.name)
        ET.SubElement(contact_xml, "ShowName").text = str(handle.name)
        ET.SubElement(contact_xml, "Groups")
        c = GaduContact.from_xml(contact_xml)
        self._conn_ref().gadu_client.addContact( c )
        self._conn_ref().gadu_client.notifyAboutContact( c )
        logger.info("Adding contact: %s" % (handle.name))
        self.MembersChanged('', [handle], (), (), (), 0,
                    telepathy.CHANNEL_GROUP_CHANGE_REASON_INVITED)

        #alias and group settings for new contacts are bit tricky
        #try to set alias
        handle.contact.ShowName = self._conn_ref().get_contact_alias(handle.id)
        #and group
        if self._conn_ref().pending_contacts_to_group.has_key(handle.name):
            logger.info("Trying to add temporary group.")
            handle.contact.updateGroups(self._conn_ref().pending_contacts_to_group[handle.name])
        self._conn_ref().contactAdded(handle)
        logger.info("Contact added.")
        self._conn_ref().exportContactsFile()

    def _remove(self, handle_id):
        handle = self._conn.handle(telepathy.HANDLE_TYPE_CONTACT, h)
        contact = handle.contact
        if contact is None:
            return True
        logger.info("Removing contact: %s" % (handle.name))
        self._conn_ref().gadu_client.removeContact(contact, notify=True)
        self.MembersChanged('', (), [handle], (), (), 0,
                    telepathy.CHANNEL_GROUP_CHANGE_REASON_NONE)
        #self._conn_ref().exportContactsFile()

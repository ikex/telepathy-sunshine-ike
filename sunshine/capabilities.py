# telepathy-sunshine is the GaduGadu connection manager for Telepathy
#
# Copyright (C) 2009 Collabora Ltd.
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

import telepathy

try:
    from telepathy.server import ConnectionInterfaceContactCapabilities
except:
    from telepathy._generated.Connection_Interface_Contact_Capabilities \
        import ConnectionInterfaceContactCapabilities

from sunshine.util.decorator import async
from sunshine.handle import SunshineHandleFactory

__all__ = ['SunshineCapabilities']

logger = logging.getLogger('Sunshine.Capabilities')

class SunshineCapabilities(telepathy.server.ConnectionInterfaceCapabilities,
        ConnectionInterfaceContactCapabilities):

    text_chat_class = \
        ({telepathy.CHANNEL_INTERFACE + '.ChannelType':
              telepathy.CHANNEL_TYPE_TEXT,
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType':
              dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID'])

    audio_chat_class = \
        ({telepathy.CHANNEL_INTERFACE + '.ChannelType':
              telepathy.CHANNEL_TYPE_STREAMED_MEDIA,
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType':
              dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID',
          telepathy.CHANNEL_TYPE_STREAMED_MEDIA + '.InitialAudio'])

    av_chat_class = \
        ({telepathy.CHANNEL_INTERFACE + '.ChannelType':
              telepathy.CHANNEL_TYPE_STREAMED_MEDIA,
          telepathy.CHANNEL_INTERFACE + '.TargetHandleType':
              dbus.UInt32(telepathy.HANDLE_TYPE_CONTACT)},
         [telepathy.CHANNEL_INTERFACE + '.TargetHandle',
          telepathy.CHANNEL_INTERFACE + '.TargetID',
          telepathy.CHANNEL_TYPE_STREAMED_MEDIA + '.InitialAudio',
          telepathy.CHANNEL_TYPE_STREAMED_MEDIA + '.InitialVideo'])

    def __init__(self):
        telepathy.server.ConnectionInterfaceCapabilities.__init__(self)
        ConnectionInterfaceContactCapabilities.__init__(self)

        # handle -> list(RCC)
        self._contact_caps = {}
        self._video_clients = []
        self._update_capabilities_calls = []

    def AdvertiseCapabilities(self, add, remove):
#        for caps, specs in add:
#            if caps == telepathy.CHANNEL_TYPE_STREAMED_MEDIA:
#                if specs & telepathy.CHANNEL_MEDIA_CAPABILITY_VIDEO:
#                    self._self_handle.profile.client_id.has_webcam = True
#                    self._self_handle.profile.client_id.supports_rtc_video = True
#        for caps in remove:
#            if caps == telepathy.CHANNEL_TYPE_STREAMED_MEDIA:
#                self._self_handle.profile.client_id.has_webcam = False

        return telepathy.server.ConnectionInterfaceCapabilities.\
            AdvertiseCapabilities(self, add, remove)

    def GetContactCapabilities(self, handles):
        if 0 in handles:
            raise telepathy.InvalidHandle('Contact handle list contains zero')

        ret = dbus.Dictionary({}, signature='ua(a{sv}as)')
        for i in handles:
            handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, i)
            # If the handle has no contact capabilities yet then it
            # won't be in the dict. It's fair to return an empty list
            # here for its contact caps.
            if handle in self._contact_caps:
		ret[handle] = dbus.Array(self._contact_caps[handle], signature='(a{sv}as)')
            else:
                ret[handle] = dbus.Array([], signature='(a{sv}as)')

        return ret

    def UpdateCapabilities(self, caps):
        if self._status != telepathy.CONNECTION_STATUS_CONNECTED:
            self._update_capabilities_calls.append(caps)
            return

        # voip is disabled, so
        return

        # We only care about voip.
        for client, classes, capabilities in caps:
            video = False
            for channel_class in classes:
                # Does this client support video?
                if channel_class[telepathy.CHANNEL_INTERFACE + '.ChannelType'] == \
                        telepathy.CHANNEL_TYPE_STREAMED_MEDIA:
                    video = True
                    self._video_clients.append(client)
                else:
                    # *Did* it used to support video?
                    if client in self._video_clients:
                        self._video_clients.remove(client)

        changed = False

        # We've got no more clients that support video; remove the cap.
        if not video and not self._video_clients:
            self._self_handle.profile.client_id.has_webcam = False
            changed = True

        # We want video.
        if video and not self._self_handle.profile.client_id.has_webcam:
            self._self_handle.profile.client_id.has_webcam = True
            self._self_handle.profile.client_id.supports_rtc_video = True
            changed = True

        # Signal.
        if changed:
            updated = dbus.Dictionary({self._self_handle: self._contact_caps[self._self_handle]},
                signature='ua(a{sv}as)')
            self.ContactCapabilitiesChanged(updated)

    def on_contact_client_capabilities_changed(self, contact):
        self._update_capabilities(contact)


    def contactAdded(self, handle):
        """When we add a contact in our contact list, add the
        capabilities to create text channel to the contact"""
        self.add_text_capabilities([handle])

    def add_text_capabilities(self, contacts_handles):
        """Add the create capability for text channel to these contacts."""
        ret = []
        cc_ret = dbus.Dictionary({}, signature='ua(a{sv}as)')
        for handle in contacts_handles:
            ctype = telepathy.CHANNEL_TYPE_TEXT
            if handle in self._caps and ctype in self._caps[handle]:
                old_gen, old_spec = self._caps[handle][ctype]
            else:
                old_gen = 0
                old_spec = 0
            new_gen = old_gen
            new_gen |= telepathy.CONNECTION_CAPABILITY_FLAG_CREATE

            diff = (int(handle), ctype, old_gen, new_gen, old_spec, old_spec)
            ret.append(diff)

            # ContactCapabilities
            self._contact_caps.setdefault(handle, []).append(self.text_chat_class)
            cc_ret[handle] = self._contact_caps[handle]

        self.CapabilitiesChanged(ret)
        self.ContactCapabilitiesChanged(cc_ret)

#    def add_create_capability(self, contact_handle):
#        """Add the create capability for self handle."""
#        ret = []
#        cc_ret = dbus.Dictionary({}, signature='ua(a{sv}as)')
#
#        ctype = telepathy.CHANNEL_TYPE_TEXT
#        if handle in self._caps:
#            old_gen, old_spec = self._caps[handle][ctype]
#        else:
#            old_gen = 0
#            old_spec = 0
#        new_gen = old_gen
#        new_gen |= telepathy.CONNECTION_CAPABILITY_FLAG_CREATE
#
#        diff = (int(handle), ctype, old_gen, new_gen, old_spec, old_spec)
#        ret.append(diff)
#
#        # ContactCapabilities
#        self._contact_caps.setdefault(handle, []).append(self.text_chat_class)
#        cc_ret[handle] = self._contact_caps[handle]
#
#        self.CapabilitiesChanged(ret)
#        self.ContactCapabilitiesChanged(cc_ret)

    def _update_capabilities(self, contact):
        handle = SunshineHandleFactory(self, 'contact',
                contact.account, contact.network_id)
        ctype = telepathy.CHANNEL_TYPE_STREAMED_MEDIA

        new_gen, new_spec, rcc = self._get_capabilities(contact)
        if handle in self._caps:
            old_gen, old_spec = self._caps[handle][ctype]
        else:
            old_gen = 0
            old_spec = 0

        if old_gen != new_gen or old_spec != new_spec:
            diff = (int(handle), ctype, old_gen, new_gen, old_spec, new_spec)
            self.CapabilitiesChanged([diff])

        if rcc is None:
            return

        self._contact_caps.setdefault(handle, [])

        if rcc in self._contact_caps[handle]:
            return

        if self.audio_chat_class in self._contact_caps[handle]:
            self._contact_caps[handle].remove(self.audio_chat_class)

        if self.audio_chat_class in self._contact_caps[handle]:
            self._contact_caps[handle].remove(self.audio_chat_class)

        self._contact_caps[handle].append(rcc)

        ret = dbus.Dictionary({handle: self._contact_caps[handle]},
            signature='ua(a{sv}as)')
        self.ContactCapabilitiesChanged(ret)

    def _get_capabilities(self, contact):
        gen_caps = 0
        spec_caps = 0

        rcc = None

        caps = contact.client_capabilities
        #if caps.supports_sip_invite:
            #gen_caps |= telepathy.CONNECTION_CAPABILITY_FLAG_CREATE
            #gen_caps |= telepathy.CONNECTION_CAPABILITY_FLAG_INVITE
            #spec_caps |= telepathy.CHANNEL_MEDIA_CAPABILITY_AUDIO
            #spec_caps |= telepathy.CHANNEL_MEDIA_CAPABILITY_NAT_TRAVERSAL_STUN

            #if caps.has_webcam:
                #spec_caps |= telepathy.CHANNEL_MEDIA_CAPABILITY_VIDEO
                #rcc = self.av_chat_class
            #else:
                #rcc = self.audio_chat_class

        return gen_caps, spec_caps, rcc

    @async
    def _populate_capabilities(self):
        """ Add the capability to create text channels to all contacts in our
        contacts list."""
        handles = set([self._self_handle])
        for contact in self.profile.contacts:
            handle = SunshineHandleFactory(self, 'contact',
                    str(contact.uin), None)
            handles.add(handle)
        self.add_text_capabilities(handles)

        # These caps were updated before we were online.
        for caps in self._update_capabilities_calls:
            self.UpdateCapabilities(caps)
        self._update_capabilities_calls = []

    def updateCapabilitiesCalls(self):
        # These caps were updated before we were online.
        for caps in self._update_capabilities_calls:
            self.UpdateCapabilities(caps)

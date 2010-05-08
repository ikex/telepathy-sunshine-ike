# telepathy-sunshine is the GaduGadu connection manager for Telepathy
#
# Copyright (C) 2007 Ali Sabil <ali.sabil@gmail.com>
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
import telepathy.constants

from sunshine.handle import SunshineHandleFactory
from sunshine.util.decorator import async

__all__ = ['SunshineAliasing']

logger = logging.getLogger('Sunshine.Aliasing')

class SunshineAliasing(telepathy.server.ConnectionInterfaceAliasing):

    def __init__(self):
        telepathy.server.ConnectionInterfaceAliasing.__init__(self)
        self.aliases = {}

    def GetAliasFlags(self):
        return telepathy.constants.CONNECTION_ALIAS_FLAG_USER_SET

    def RequestAliases(self, contacts):
        logger.debug("Called RequestAliases")
        return [self._get_alias(handle_id) for handle_id in contacts]

    def GetAliases(self, contacts):
        logger.debug("Called GetAliases")

        result = dbus.Dictionary(signature='us')
        for contact in contacts:
            result[contact] = self._get_alias(contact)
        return result

    def SetAliases(self, aliases):
        for handle_id, alias in aliases.iteritems():
            handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
            if handle == SunshineHandleFactory(self, 'self'):
                logger.info("Self alias changed to '%s'" % alias)
                self.configfile.save_self_alias(alias)
                self.AliasesChanged(((SunshineHandleFactory(self, 'self'), alias), ))
            else:
                logger.debug("Called SetAliases for handle: %s, alias: %s" % (handle.name, alias))
                
                if alias == handle.name:
                    alias = ''
                
                new_alias = alias
                
                try:
                    handle.contact.updateName(new_alias)
                except:
                    pass
                
                #alias = unicode(alias, 'utf-8')
                logger.info("Contact %s alias changed to '%s'" % (unicode(handle.name), alias))
                self.aliases[handle.name] = alias
                self.AliasesChanged([(handle, alias)])

#    # papyon.event.ContactEventInterface
#    def on_contact_display_name_changed(self, contact):
#        self._contact_alias_changed(contact)
#
#    # papyon.event.ContactEventInterface
#    def on_contact_infos_changed(self, contact, updated_infos):
#        alias = updated_infos.get(ContactGeneral.ANNOTATIONS, {}).\
#            get(ContactAnnotations.NICKNAME, None)
#
#        if alias is not None or alias != "":
#            self._contact_alias_changed(contact)
#
#    # papyon.event.ContactEventInterface
#    def on_contact_memberships_changed(self, contact):
#        handle = ButterflyHandleFactory(self, 'contact',
#                contact.account, contact.network_id)
#        if contact.is_member(papyon.Membership.FORWARD):
#            alias = handle.pending_alias
#            if alias is not None:
#                infos = {ContactGeneral.ANNOTATIONS : \
#                            {ContactAnnotations.NICKNAME : alias.encode('utf-8')}
#                        }
#                self.msn_client.address_book.\
#                    update_contact_infos(contact, infos)
#                handle.pending_alias = None

    def _get_alias(self, handle_id):
        """Get the alias from one handle id"""
        handle = self.handle(telepathy.HANDLE_TYPE_CONTACT, handle_id)
        if handle == SunshineHandleFactory(self, 'self'):
            logger.info("SunshineHandleFactory for self handle '%s', id: %s" % (handle.name, handle.id))
            alias = self.configfile.get_self_alias()
            self.configfile.save_self_alias(alias)
            if alias == None or len(alias) == 0:
                alias = handle.name
        else:
            logger.info("SunshineHandleFactory handle '%s', id: %s" % (handle.name, handle.id))
            contact = handle.contact
            #print str(self.aliases)
            if self.aliases.has_key(handle.name):
                alias = self.aliases[handle.name]
                #del self.aliases[handle.name]
            elif contact is None:
                alias = handle.name
            else:
                alias = contact.ShowName
                if alias == '' or alias is None:
                     alias = str(handle.name)
        return alias

#    @async
#    def _contact_alias_changed(self, contact):
#        handle = GaduHandleFactory(self, 'contact',
#                contact.account, None)
#
#        alias = contact.infos.get(ContactGeneral.ANNOTATIONS, {}).\
#            get(ContactAnnotations.NICKNAME, None)
#
#        if alias == "" or alias is None:
#            alias = contact.display_name
#
#        alias = unicode(alias, 'utf-8')
#        logger.info("Contact %s alias changed to '%s'" % (unicode(handle), alias))
#        self.AliasesChanged([(handle, alias)])
#

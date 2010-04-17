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

import sys
import os
import time
import weakref
import logging

import xml.etree.ElementTree as ET

from sunshine.lqsoft.pygadu.twisted_protocol import GaduClient
from sunshine.lqsoft.pygadu.models import GaduProfile, GaduContact, GaduContactGroup

from twisted.internet import reactor, protocol
from twisted.web.client import getPage
from twisted.internet import task
from twisted.python import log

import dbus
import telepathy

from sunshine.presence import SunshinePresence
from sunshine.aliasing import SunshineAliasing
from sunshine.avatars import SunshineAvatars
from sunshine.handle import SunshineHandleFactory
from sunshine.capabilities import SunshineCapabilities
from sunshine.contacts import SunshineContacts
from sunshine.channel_manager import SunshineChannelManager
from sunshine.util.decorator import async, stripHTML

__all__ = ['SunshineConfig', 'GaduClientFactory', 'SunshineConnection']

logger = logging.getLogger('Sunshine.Connection')

ssl_support = False

#SSL
try:
    from OpenSSL import crypto, SSL
    from twisted.internet import ssl
    ssl_support = True
except ImportError:
    ssl_support = False
try:
    if ssl and ssl.supported:
        ssl_support = True
except NameError:
    ssl_support = False


if ssl_support == False:
    logger.info('SSL unavailable. Falling back to normal non-SSL connection.')
else:
    logger.info('Using SSL-like connection.')

class SunshineConfig(object):
    def __init__(self, uin):
        self.uin = uin
        self.path = None
        self.contacts_count = 0

    def check_dirs(self):
        path = os.path.join(os.path.join(os.environ['HOME'], '.telepathy-sunshine'), str(self.uin))
        try:
            os.makedirs(path)
        except:
            pass
        if os.path.isfile(os.path.join(path, 'profile.xml')):
            pass
        else:
            contactbook_xml = ET.Element("ContactBook")

            ET.SubElement(contactbook_xml, "Groups")
            ET.SubElement(contactbook_xml, "Contacts")

            main_xml = ET.ElementTree(contactbook_xml)
            main_xml.write(os.path.join(path, 'profile.xml'), encoding="UTF-8")
            
        self.path = os.path.join(path, 'profile.xml')
        self.path2 = os.path.join(path, 'alias')
        return os.path.join(path, 'profile.xml')

    def get_contacts(self):
        file = open(self.path, "r")
        config_xml = ET.parse(file).getroot()

        self.roster = {'groups':[], 'contacts':[]}

        for elem in config_xml.find('Groups').getchildren():
            self.roster['groups'].append(elem)

        for elem in config_xml.find('Contacts').getchildren():
            self.roster['contacts'].append(elem)

        self.contacts_count = len(config_xml.find('Contacts').getchildren())

        return self.roster

    def make_contacts_file(self, groups, contacts):
        contactbook_xml = ET.Element("ContactBook")

        groups_xml = ET.SubElement(contactbook_xml, "Groups")
        contacts_xml = ET.SubElement(contactbook_xml, "Contacts")

        for group in groups:
            #Id, Name, IsExpanded, IsRemovable
            group_xml = ET.SubElement(groups_xml, "Group")
            ET.SubElement(group_xml, "Id").text = group.Id
            ET.SubElement(group_xml, "Name").text = group.Name
            ET.SubElement(group_xml, "IsExpanded").text = str(group.IsExpanded).lower()
            ET.SubElement(group_xml, "IsRemovable").text = str(group.IsRemovable).lower()

        for contact in contacts:
            #Guid, GGNumber, ShowName. MobilePhone. HomePhone, Email, WWWAddress, FirstName, LastName, Gender, Birth, City, Province, Groups, CurrentAvatar, Avatars
            contact_xml = ET.SubElement(contacts_xml, "Contact")
            ET.SubElement(contact_xml, "Guid").text = contact.Guid
            ET.SubElement(contact_xml, "GGNumber").text = contact.GGNumber
            ET.SubElement(contact_xml, "ShowName").text = contact.ShowName
            contact_groups_xml = ET.SubElement(contact_xml, "Groups")
            contact_groups = ET.fromstring(contact.Groups)
            if contact.Groups:
                for group in contact_groups.getchildren():
                    ET.SubElement(contact_groups_xml, "GroupId").text = group.text
            contact_avatars_xml = ET.SubElement(contact_xml, "Avatars")
            ET.SubElement(contact_avatars_xml, "URL").text = ""
            ET.SubElement(contact_xml, "FlagNormal").text = "true"

        main_xml = ET.ElementTree(contactbook_xml)
        main_xml.write(self.path, encoding="UTF-8")

    def get_contacts_count(self):
        return self.contacts_count

    # alias config
    def get_self_alias(self):
        if os.path.exists(self.path2):
            file = open(self.path2, "r")
            alias = file.read()
            file.close()
            return alias
        
    def save_self_alias(self, alias):
        file = open(self.path2, "w")
        file.write(alias)
        file.close()
        
#class GaduClientFactory(protocol.ClientFactory, protocol.ReconnectingClientFactory):
class GaduClientFactory(protocol.ClientFactory):
    def __init__(self, config):
        self.config = config

    def buildProtocol(self, addr):
        # connect using current selected profile
        #self.resetDelay()
        return GaduClient(self.config)

    def startedConnecting(self, connector):
        logger.info('Started to connect.')

    def clientConnectionLost(self, connector, reason):
        logger.info('Lost connection.  Reason: %s' % (reason))
        #protocol.ReconnectingClientFactory.clientConnectionLost(self, connector, reason)
        #connector.connect()
        if self.config.contactsLoop != None:
            self.config.contactsLoop.stop()
            self.config.contactsLoop = None
        if self.config.exportLoop != None:
            self.config.exportLoop.stop()
            self.config.exportLoop = None
        if reactor.running:
            reactor.stop()

    def clientConnectionFailed(self, connector, reason):
        logger.info('Connection failed. Reason: %s' % (reason))
        #protocol.ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)
        if self.config.contactsLoop != None:
            self.config.contactsLoop.stop()
            self.config.contactsLoop = None
        if self.config.exportLoop != None:
            self.config.exportLoop.stop()
            self.config.exportLoop = None
        if reactor.running:
            reactor.stop()

class SunshineConnection(telepathy.server.Connection,
        telepathy.server.ConnectionInterfaceRequests,
        SunshinePresence,
        SunshineAliasing,
        SunshineAvatars,
        SunshineCapabilities,
        SunshineContacts
        ):

    _mandatory_parameters = {
            'account' : 's',
            'password' : 's'
            }
    _optional_parameters = {
            'server' : 's',
            'port' : 'q',
            'use-ssl' : 'b',
            'export-contacts' : 'b'
            }
    _parameter_defaults = {
            'server' : '91.197.13.67',
            'port' : dbus.UInt16(8074),
            'use-ssl' : dbus.Boolean(False),
            'export-contacts' : dbus.Boolean(False)
            }

    def __init__(self, manager, parameters):
        try:
            parameters['export-contacts'] = bool(parameters['export-contacts'])
        except KeyError:
            parameters['export-contacts'] = False
        try:
            parameters['use-ssl'] = bool(parameters['use-ssl'])
        except KeyError:
            parameters['use-ssl'] = False
        self.check_parameters(parameters)

        try:
            account = unicode(parameters['account'])
            server = (parameters['server'], parameters['port'])

            self._manager = weakref.proxy(manager)
            self._account = (parameters['account'], parameters['password'])
            self._server = (parameters['server'], parameters['port'])
            self._export_contacts = bool(parameters['export-contacts'])

            self.profile = GaduProfile(uin= int(parameters['account']) )
            self.profile.uin = int(parameters['account'])
            self.profile.password = str(parameters['password'])
            self.profile.status = 0x014
            self.profile.onLoginSuccess = self.on_loginSuccess
            self.profile.onLoginFailure = self.on_loginFailed
            self.profile.onContactStatusChange = self.on_updateContact
            self.profile.onMessageReceived = self.on_messageReceived
            self.profile.onXmlAction = self.onXmlAction
            self.profile.onXmlEvent = self.onXmlEvent
            self.profile.onUserData = self.onUserData
            #self.profile.onStatusNoticiesRecv = self.on_StatusNoticiesRecv

            self.password = str(parameters['password'])

            #lets try to make file with contacts etc ^^
            self.configfile = SunshineConfig(int(parameters['account']))
            self.configfile.check_dirs()
            #lets get contacts from contacts config file
            contacts_list = self.configfile.get_contacts()

            for contact_from_list in contacts_list['contacts']:
                c = GaduContact.from_xml(contact_from_list)
                try:
                    c.uin
                    self.profile.addContact( c )
                except:
                    pass
                
            for group_from_list in contacts_list['groups']:
                g = GaduContactGroup.from_xml(group_from_list)
                if g.Name:
                    self.profile.addGroup(g)
            
            logger.info("We have %s contacts in file." % (self.configfile.get_contacts_count()))
            
            self.factory = GaduClientFactory(self.profile)
            self._channel_manager = SunshineChannelManager(self)

            self._recv_id = 0
            self._conf_id = 0
            self.pending_contacts_to_group = {}
            self._status = None
            self.profile.contactsLoop = None
            
            # Call parent initializers
            telepathy.server.Connection.__init__(self, 'gadugadu', account, 'sunshine')
            telepathy.server.ConnectionInterfaceRequests.__init__(self)
            SunshinePresence.__init__(self)
            SunshineAvatars.__init__(self)
            SunshineCapabilities.__init__(self)
            SunshineContacts.__init__(self)

            self.set_self_handle(SunshineHandleFactory(self, 'self'))

            self.__disconnect_reason = telepathy.CONNECTION_STATUS_REASON_NONE_SPECIFIED
            #small hack. We started to connnect with status invisible and just later we change status to client-like
            self._initial_presence = 0x014
            self._initial_personal_message = None
            self._personal_message = ''

            logger.info("Connection to the account %s created" % account)
        except Exception, e:
            import traceback
            logger.exception("Failed to create Connection")
            raise

    @property
    def manager(self):
        return self._manager

    @property
    def gadu_client(self):
        return self.profile

    def handle(self, handle_type, handle_id):
        self.check_handle(handle_type, handle_id)
        return self._handles[handle_type, handle_id]

    def get_contact_alias(self, handle_id):
        return self._get_alias(handle_id)

    def get_handle_id_by_name(self, handle_type, name):
        """Returns a handle ID for the given type and name

        Arguments:
        handle_type -- Telepathy Handle_Type for all the handles
        name -- username for the contact

        Returns:
        handle_id -- ID for the given username
        """
        handle_id = 0
        for handle in self._handles.values():
            if handle.get_name() == name and handle.type == handle_type:
                handle_id = handle.get_id()
                break

        return handle_id

    def Connect(self):
        if self._status == telepathy.CONNECTION_STATUS_DISCONNECTED:
            logger.info("Connecting")
            self.StatusChanged(telepathy.CONNECTION_STATUS_CONNECTING,
                    telepathy.CONNECTION_STATUS_REASON_REQUESTED)
            self.__disconnect_reason = telepathy.CONNECTION_STATUS_REASON_NONE_SPECIFIED
            self.getServerAdress(self._account[0])

    def Disconnect(self):
        if self.profile.contactsLoop:
            self.profile.contactsLoop.stop()
            self.profile.contactsLoop = None
        if self._export_contacts == True:
            if self.profile.exportLoop:
                self.profile.exportLoop.stop()
                self.profile.exportLoop = None
                
        logger.info("Disconnecting")
        #self.profile.setMyState('NOT_AVAILABLE', self._personal_message)
        self.StatusChanged(telepathy.CONNECTION_STATUS_DISCONNECTED,
                telepathy.CONNECTION_STATUS_REASON_REQUESTED)
        self.profile.disconnect()
        #if reactor.running:
        #    reactor.stop()

    def RequestHandles(self, handle_type, names, sender):
        logger.info("Method RequestHandles called, handle type: %s, names: %s" % (str(handle_type), str(names)))
        self.check_connected()
        self.check_handle_type(handle_type)
        
        handles = []
        for name in names:
            if handle_type == telepathy.HANDLE_TYPE_CONTACT:
                contact_name = name
                    
                try:
                    int(str(contact_name))
                except:
                    raise InvalidHandle
                
                handle_id = self.get_handle_id_by_name(telepathy.constants.HANDLE_TYPE_CONTACT, str(contact_name))

                if handle_id != 0:
                    handle = self.handle(telepathy.constants.HANDLE_TYPE_CONTACT, handle_id)
                else:
                    handle = SunshineHandleFactory(self, 'contact',
                            str(contact_name), None)
            elif handle_type == telepathy.HANDLE_TYPE_ROOM:
                handle = SunshineHandleFactory(self, 'room', name)
            elif handle_type == telepathy.HANDLE_TYPE_LIST:
                handle = SunshineHandleFactory(self, 'list', name)
            elif handle_type == telepathy.HANDLE_TYPE_GROUP:
                handle = SunshineHandleFactory(self, 'group', name)
            else:
                raise telepathy.NotAvailable('Handle type unsupported %d' % handle_type)
            handles.append(handle.id)
            self.add_client_handle(handle, sender)
        return handles

    def _generate_props(self, channel_type, handle, suppress_handler, initiator_handle=None):
        props = {
            telepathy.CHANNEL_INTERFACE + '.ChannelType': channel_type,
            telepathy.CHANNEL_INTERFACE + '.TargetHandle': 0 if handle is None else handle.get_id(),
            telepathy.CHANNEL_INTERFACE + '.TargetHandleType': telepathy.HANDLE_TYPE_NONE if handle is None else handle.get_type(),
            telepathy.CHANNEL_INTERFACE + '.Requested': suppress_handler
            }

        if initiator_handle is not None:
            props[telepathy.CHANNEL_INTERFACE + '.InitiatorHandle'] = initiator_handle.id

        return props

    @dbus.service.method(telepathy.CONNECTION, in_signature='suub',
        out_signature='o', async_callbacks=('_success', '_error'))
    def RequestChannel(self, type, handle_type, handle_id, suppress_handler,
            _success, _error):
        self.check_connected()
        channel_manager = self._channel_manager

        if handle_id == 0:
            handle = None
        else:
            handle = self.handle(handle_type, handle_id)
        props = self._generate_props(type, handle, suppress_handler)
        self._validate_handle(props)

        channel = channel_manager.channel_for_props(props, signal=False)

        _success(channel._object_path)
        self.signal_new_channels([channel])

    @async
    def updateContactsFile(self):
        """Method that updates contact file when it changes and in loop every 5 seconds."""
        self.configfile.make_contacts_file(self.profile.groups, self.profile.contacts)

    @async
    def exportContactsFile(self):
        logger.info("Exporting contacts.")
        file = open(self.configfile.path, "r")
        contacts_xml = file.read()
        file.close()
        if len(contacts_xml) != 0:
            self.profile.exportContacts(contacts_xml)

    @async
    def makeTelepathyContactsChannel(self):
        logger.debug("Method makeTelepathyContactsChannel called.")
        handle = SunshineHandleFactory(self, 'list', 'subscribe')
        props = self._generate_props(telepathy.CHANNEL_TYPE_CONTACT_LIST,
            handle, False)
        self._channel_manager.channel_for_props(props, signal=True)

    @async
    def makeTelepathyGroupChannels(self):
        logger.debug("Method makeTelepathyGroupChannels called.")
        for group in self.profile.groups:
            handle = SunshineHandleFactory(self, 'group',
                    group.Name)
            props = self._generate_props(
                telepathy.CHANNEL_TYPE_CONTACT_LIST, handle, False)
            self._channel_manager.channel_for_props(props, signal=True)

    def getServerAdress(self, uin):
        logger.info("Fetching GG server adress.")
        url = 'http://appmsg.gadu-gadu.pl/appsvc/appmsg_ver10.asp?fmnumber=%s&lastmsg=0&version=10.0.0.10784' % (str(uin))
        d = getPage(url, timeout=10)
        d.addCallback(self.on_server_adress_fetched, uin)
        d.addErrback(self.on_server_adress_fetched_failed, uin)

    def on_server_adress_fetched(self, result, uin):
        try:
            result = result.replace('\n', '')
            a = result.split(' ')
            if a[0] == '0' and a[-1:][0] != 'notoperating':
                addr = a[-1:][0]
                logger.info("GG server adress fetched, IP: %s" % (addr))
                if ssl_support:
                    self.ssl = ssl.CertificateOptions(method=SSL.SSLv3_METHOD)
                    reactor.connectSSL(addr, 443, self.factory, self.ssl)
                else:
                    reactor.connectTCP(addr, 8074, self.factory)
            else:
                raise Exception()
        except:
            logger.debug("Cannot get GG server IP adress. Trying again...")
            self.getServerAdress(uin)

    def on_server_adress_fetched_failed(self, error, uin):
        logger.info("Failed to get page with server IP adress.")
        self.getServerAdress(uin)

    def on_contactsImported(self):
        logger.info("No contacts in the XML contacts file yet. Contacts imported.")

        self.configfile.make_contacts_file(self.profile.groups, self.profile.contacts)
        self.profile.contactsLoop = task.LoopingCall(self.updateContactsFile)
        self.profile.contactsLoop.start(5.0)

        if self._export_contacts == True:
            self.profile.exportLoop = task.LoopingCall(self.exportContactsFile)
            self.profile.exportLoop.start(30.0)

        self.makeTelepathyContactsChannel()
        self.makeTelepathyGroupChannels()
        
        SunshineAliasing.__init__(self)
            
        self._status = telepathy.CONNECTION_STATUS_CONNECTED
        self.StatusChanged(telepathy.CONNECTION_STATUS_CONNECTED,
                telepathy.CONNECTION_STATUS_REASON_REQUESTED)

    def on_loginSuccess(self):
        logger.info("Connected")

        #if its a first run or we dont have any contacts in contacts file yet then try to import contacts from server
        if self.configfile.get_contacts_count() == 0:
            self.profile.importContacts(self.on_contactsImported)
        else:
            self.configfile.make_contacts_file(self.profile.groups, self.profile.contacts)
            self.profile.contactsLoop = task.LoopingCall(self.updateContactsFile)
            self.profile.contactsLoop.start(5.0)
            
            if self._export_contacts == True:
                self.profile.exportLoop = task.LoopingCall(self.exportContactsFile)
                self.profile.exportLoop.start(30.0)

            self.makeTelepathyContactsChannel()
            self.makeTelepathyGroupChannels()

            SunshineAliasing.__init__(self)
    
            self._status = telepathy.CONNECTION_STATUS_CONNECTED
            self.StatusChanged(telepathy.CONNECTION_STATUS_CONNECTED,
                    telepathy.CONNECTION_STATUS_REASON_REQUESTED)

    def on_loginFailed(self, response):
        logger.info("Login failed: ", response)
        self._status = telepathy.CONNECTION_STATUS_DISCONNECTED
        self.StatusChanged(telepathy.CONNECTION_STATUS_DISCONNECTED,
                telepathy.CONNECTION_STATUS_REASON_AUTHENTICATION_FAILED)
        reactor.stop()

    @async
    def on_updateContact(self, contact):
        handle_id = self.get_handle_id_by_name(telepathy.constants.HANDLE_TYPE_CONTACT, str(contact.uin))
        handle = self.handle(telepathy.constants.HANDLE_TYPE_CONTACT, handle_id)
        logger.info("Method on_updateContact called, status changed for UIN: %s, id: %s, status: %s, description: %s" % (contact.uin, handle.id, contact.status, contact.get_desc()))
        self._presence_changed(handle, contact.status, contact.get_desc())

    #@async
    def on_messageReceived(self, msg):
        if hasattr(msg.content.attrs, 'conference') and msg.content.attrs.conference != None:
            recipients = msg.content.attrs.conference.recipients
            #recipients.append(self.profile.uin)
            print msg.sender
            print 'recipients:', recipients
            recipients = map(str, recipients)
            recipients.append(str(msg.sender))
            print 'recipients:', recipients
            recipients = sorted(recipients)
            conf_name = ', '.join(map(str, recipients))
            print 'conf_name:', conf_name

            #active handle for current writting contact
            ahandle_id = self.get_handle_id_by_name(telepathy.constants.HANDLE_TYPE_CONTACT,
                                              str(msg.sender))

            if ahandle_id != 0:
                ahandle = self.handle(telepathy.constants.HANDLE_TYPE_CONTACT, ahandle_id)
            else:
                ahandle = SunshineHandleFactory(self, 'contact',
                        str(msg.sender), None)

            #now we need to preapare a new room and make initial users in it
            room_handle_id = self.get_handle_id_by_name(telepathy.constants.HANDLE_TYPE_ROOM, str(conf_name))
            print 'room_handle_id:', room_handle_id

            handles = []
            
            if room_handle_id == 0:
                room_handle =  SunshineHandleFactory(self, 'room', str(conf_name))

                for number in recipients:
                    handle_id = self.get_handle_id_by_name(telepathy.constants.HANDLE_TYPE_CONTACT,
                                              number)
                    if handle_id != 0:
                        handle = self.handle(telepathy.constants.HANDLE_TYPE_CONTACT, handle_id)
                    else:
                        handle = SunshineHandleFactory(self, 'contact',
                                number, None)

                    handles.append(handle)
            else:
                room_handle = self.handle(telepathy.constants.HANDLE_TYPE_ROOM, room_handle_id)

            props = self._generate_props(telepathy.CHANNEL_TYPE_TEXT,
                    room_handle, False)

            if handles:
                #print handles
                channel = self._channel_manager.channel_for_props(props,
                        signal=True, conversation=handles)
                channel.MembersChanged('', handles, [], [], [],
                        0, telepathy.CHANNEL_GROUP_CHANGE_REASON_NONE)
            else:
                channel = self._channel_manager.channel_for_props(props,
                        signal=True, conversation=None)

            if int(msg.content.klass) == 9:
                timestamp = int(msg.time)
            else:
                timestamp = int(time.time())
            type = telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL
            logger.info("User %s sent a message" % ahandle.name)

            logger.info("Msg from %r %d %d [%r] [%r]" % (msg.sender, msg.content.offset_plain, msg.content.offset_attrs, msg.content.plain_message, msg.content.html_message))

            if msg.content.html_message:
                #we need to strip all html tags
                text = stripHTML(msg.content.html_message).replace('&lt;', '<').replace('&gt;', '>')
            else:
                text = (msg.content.plain_message).decode('windows-1250')

            message = "%s" % unicode(str(text).replace('\x00', '').replace('\r', '').decode('UTF-8'))
            #print 'message: ', message
            channel.Received(self._recv_id, timestamp, ahandle, type, 0, message)
            self._recv_id += 1

        else:
            handle_id = self.get_handle_id_by_name(telepathy.constants.HANDLE_TYPE_CONTACT,
                                      str(msg.sender))
            if handle_id != 0:
                handle = self.handle(telepathy.constants.HANDLE_TYPE_CONTACT, handle_id)
            else:
                handle = SunshineHandleFactory(self, 'contact',
                        str(msg.sender), None)

            if int(msg.content.klass) == 9:
                timestamp = int(msg.time)
            else:
                timestamp = int(time.time())
            type = telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL
            logger.info("User %s sent a message" % handle.name)

            logger.info("Msg from %r %d %d [%r] [%r]" % (msg.sender, msg.content.offset_plain, msg.content.offset_attrs, msg.content.plain_message, msg.content.html_message))

            props = self._generate_props(telepathy.CHANNEL_TYPE_TEXT,
                    handle, False)
            channel = self._channel_manager.channel_for_props(props,
                    signal=True, conversation=None)

            if msg.content.html_message:
                #we need to strip all html tags
                text = stripHTML(msg.content.html_message).replace('&lt;', '<').replace('&gt;', '>')
            else:
                text = (msg.content.plain_message).decode('windows-1250')


            message = "%s" % unicode(str(text).replace('\x00', '').replace('\r', ''))
            #message = "%s" % unicode(str(msg.content.plain_message).replace('\x00', '').replace('\r', '').decode('windows-1250').encode('utf-8'))
            #print 'message: ', message
            channel.Received(self._recv_id, timestamp, handle, type, 0, message)
            self._recv_id += 1
            
    def onXmlAction(self, xml):
        logger.info("XmlAction: %s" % xml.data)

    def onXmlEvent(self, xml):
        logger.info("XmlEvent: %s" % xml,data)

    def onUserData(self, data):
        logger.info("UserData: %s" % str(data))
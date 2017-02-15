#!/usr/bin/env python

# Copyright (c) 2015, Palo Alto Networks
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# Author: John Anderson <lampwins@gmail.com>

"""Retrieving and parsing predefined objects from the firewall"""

from pandevice import getlogger
import pandevice.errors as err
from pan.xapi import PanXapiError
from pandevice.updater import PanOSVersion
import objects

logger = getlogger(__name__)


class Predefined(object):
    """Predefined Objects Subsystem of Firewall

    A member of a base.PanDevice object that has special methods for
    interacting with the predefned objects of the firewall

    This class is typically not instantiated by anything but the
    base.PanDevice class itself. There is an instance of this Predefined class
    inside every instantiated base.PanDevice class.

    Args:
        device (base.PanDevice): The firewall or Panorama this Predefined subsystem leverages

    """

    # xpath
    PREDEFINED_ROOT_XPATH = "/config/predefined"
    ENTRY = "/entry[@name='%s']"
    SERVICE = "/service"
    # apps and containers share a namespace so we need to search both
    APPLICATION_CONTAINS_XPATH = '//*[contains(local-name(), "application")]'
    ALL_APPLICATION_XPATH = PREDEFINED_ROOT_XPATH + APPLICATION_CONTAINS_XPATH
    SINGLE_APPLICATION_XPATH = ALL_APPLICATION_XPATH + ENTRY
    ALL_SERVICE_XPATH = PREDEFINED_ROOT_XPATH + SERVICE
    SINGLE_SERVICE_XPATH = ALL_SERVICE_XPATH + ENTRY

    def __init__(self, device=None, *args, **kwargs):
        # Create a class logger
        self._logger = getlogger(__name__ + "." + self.__class__.__name__)

        self.parent = device

        self.service_objects = {}
        self.application_objects = {}
        self.application_container_objects = {}

    def _get_xml(self, xpath):
        """use the parent to get the xml given the xpath"""

        err_msg = "Predefined object(s) does not exist with xpath: {0}".format(xpath)

        root = self.parent.xapi.get(xpath, retry_on_peer=False)

        elm = root.find("result")
        return elm

    def _parse_application_xml(self, xml):
        """parse the xml into actual objects and store them in the dicts"""

        for elm in xml:
            if elm.find("functions") is not None:
                # this is an ApplicationContainerObject
                obj = objects.ApplicationContainer()
                obj.refresh(xml=elm)
                self.application_container_objects[obj.name] = obj
            else:
                # this is an ApplicationObject
                obj = objects.ApplicationObject()
                obj.refresh(xml=elm)
                self.application_objects[obj.name] = obj

    def _parse_service_xml(self, xml):
        """parse the xml into actual objects and store them in the dicts"""

        for elm in xml:
            obj = objects.ServiceObject()
            obj.refresh(xml=elm)
            self.service_objects[obj.name] = obj

    def refresh_application(self, name):
        """Refresh a Single Predefined Application

        This method refreshes single predefined application or application container
        (predefined only object).

        Args:
            name (str): Name of the application to refresh

        """

        xpath = self.SINGLE_APPLICATION_XPATH % name
        xml = self._get_xml(xpath)
        self._parse_application_xml(xml)

    def refresh_service(self, name):
        """Refresh a Single Predefined Service

        This method refreshes single predefined service (predefined only object).

        Args:
            name (str): Name of the service to refresh

        """

        xpath = self.SINGLE_SERVICE_XPATH % name
        xml = self._get_xml(xpath)
        self._parse_service_xml(xml)

    def refreshall_applications(self):
        """Refresh all Predefined Applications

        This method refreshes all predefined applications and application containers.

        CAUTION: This method requires a lot of overhead on the device api to respond.
        Response time will vary by platform, but know that it will generally take
        longer than a normal api request.

        """

        xpath = self.ALL_APPLICATION_XPATH + "/entry"
        xml = self._get_xml(xpath)
        self._parse_application_xml(xml)

    def refreshall_services(self):
        """Refresh all Predefined Services

        This method refreshes all predefined services.

        """

        xpath = self.ALL_SERVICE_XPATH + "/entry"
        xml = self._get_xml(xpath)
        self._parse_service_xml(xml)

    def refreshall(self):
        """Refresh all Predefined Objects

        This method refreshes all predefined objects. This includes applications,
        application containers, and services.

        CAUTION: This method requires a lot of overhead on the device api to respond.
        Response time will vary by platform, but know that it will generally take
        longer than a normal api request.

        """

        # first we clear all existing objects
        self.application_objects = {}
        self.application_container_objects = {}
        self.service_objects = {}

        # now we call the refresh methods
        self.refreshall_services()
        self.refreshall_applications()

    def application(self, name, refresh_if_none=True, include_containers=True):
        """Get a Predefined Application

        Return the instance of the application from the given name.

        Args:
            name (str): Name of the application
            refresh_if_none (bool): Refresh the application if it is not found
            include_containers (bool): also search application containers if no match found

        Returns:
            Either an ApplicationObject, ApplicationContainerObject, or None

        """

        obj = self.application_objects.get(name, None)
        if obj is None and include_containers:
            obj = self.application_container_objects.get(name, None)

        if obj is None and refresh_if_none:
            self.refresh_application(name)
            # recursive call but with no refresh
            obj = self.application(name, refresh_if_none=False, include_containers=include_containers)

        return obj

    def service(self, name, refresh_if_none=True):
        """Get a Predefined Service

        Return the instance of the service from the given name.

        Args:
            name (str): Name of the service
            refresh_if_none (bool): Refresh the service if it is not found

        Returns:
            Either a ServiceObject or None

        """

        obj = self.service_objects.get(name, None)

        if obj is None and refresh_if_none:
            self.refresh_service(name)
            # recursive call but with no refresh
            obj = self.service(name, refresh_if_none=False)

        return obj

    def applications(self, names, refresh_if_none=True, include_containers=True):
        """Get a list of Predefined Applications

        Return a list of the instances of the applications from the given names.

        Args:
            names (list): Names of the applications
            refresh_if_none (bool): Refresh the application(s) if it is not found
            include_containers (bool): also search application containers if no match found

        Returns:
            A list of all found ApplicationObjects or ApplicationContainerObjects

        """

        objs = []

        for name in set(names):
            obj = self.application(name, refresh_if_none=refresh_if_none, include_containers=include_containers)
            if obj:
                objs.append(obj)

        return objs

    def services(self, names, refresh_if_none=True):
        """Get a list of Predefined Services

        Return a list of the instances of the services from the given names.

        Args:
            names (list): Names of the services
            refresh_if_none (bool): Refresh the service(s) if it is not found

        Returns:
            A list of all found ServiceObjects

        """

        objs = []

        for name in set(names):
            obj = self.service(name, refresh_if_none=refresh_if_none)
            if obj:
                objs.append(obj)

        return objs

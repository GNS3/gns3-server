# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

""" Interacts with Rackspace API to create and manage cloud instances. """

from .base_cloud_ctrl import BaseCloudCtrl
import json
import requests
from libcloud.compute.drivers.rackspace import ENDPOINT_ARGS_MAP
from libcloud.compute.providers import get_driver
from libcloud.compute.types import Provider

from .exceptions import ItemNotFound, ApiError
from ..version import __version__

import logging
log = logging.getLogger(__name__)

RACKSPACE_REGIONS = [{ENDPOINT_ARGS_MAP[k]['region']: k} for k in
                     ENDPOINT_ARGS_MAP]

GNS3IAS_URL = 'http://localhost:8888'  # TODO find a place for this value


class RackspaceCtrl(BaseCloudCtrl):

    """ Controller class for interacting with Rackspace API. """

    def __init__(self, username, api_key):
        super(RackspaceCtrl, self).__init__(username, api_key)

        # set this up so it can be swapped out with a mock for testing
        self.post_fn = requests.post
        self.driver_cls = get_driver(Provider.RACKSPACE)

        self.driver = None
        self.region = None
        self.instances = {}

        self.authenticated = False
        self.identity_ep = \
            "https://identity.api.rackspacecloud.com/v2.0/tokens"

        self.regions = []
        self.token = None

    def authenticate(self):
        """
        Submit username and api key to API service.

        If authentication is successful, set self.regions and self.token.
        Return boolean.

        """

        self.authenticated = False

        if len(self.username) < 1:
            return False

        if len(self.api_key) < 1:
            return False

        data = json.dumps({
            "auth": {
                "RAX-KSKEY:apiKeyCredentials": {
                    "username": self.username,
                    "apiKey": self.api_key
                }
            }
        })

        headers = {
            'Content-type': 'application/json',
            'Accept': 'application/json'
        }

        response = self.post_fn(self.identity_ep, data=data, headers=headers)

        if response.status_code == 200:

            api_data = response.json()
            self.token = self._parse_token(api_data)

            if self.token:
                self.authenticated = True
                user_regions = self._parse_endpoints(api_data)
                self.regions = self._make_region_list(user_regions)

        else:
            self.regions = []
            self.token = None

        response.connection.close()

        return self.authenticated

    def list_regions(self):
        """ Return a list the regions available to the user. """

        return self.regions

    def _parse_endpoints(self, api_data):
        """
        Parse the JSON-encoded data returned by the Identity Service API.

        Return a list of regions available for Compute v2.

        """

        region_codes = []

        for ep_type in api_data['access']['serviceCatalog']:
            if ep_type['name'] == "cloudServersOpenStack" \
                    and ep_type['type'] == "compute":

                for ep in ep_type['endpoints']:
                    if ep['versionId'] == "2":
                        region_codes.append(ep['region'])

        return region_codes

    def _parse_token(self, api_data):
        """ Parse the token from the JSON-encoded data returned by the API. """

        try:
            token = api_data['access']['token']['id']
        except KeyError:
            return None

        return token

    def _make_region_list(self, region_codes):
        """
        Make a list of regions for use in the GUI.

        Returns a list of key-value pairs in the form:
            <API's Region Name>: <libcloud's Region Name>
            eg,
            [
                {'DFW': 'dfw'}
                {'ORD': 'ord'},
                ...
            ]

        """

        region_list = []

        for ep in ENDPOINT_ARGS_MAP:
            if ENDPOINT_ARGS_MAP[ep]['region'] in region_codes:
                region_list.append({ENDPOINT_ARGS_MAP[ep]['region']: ep})

        return region_list

    def set_region(self, region):
        """ Set self.region and self.driver. Returns True or False. """

        try:
            self.driver = self.driver_cls(self.username, self.api_key,
                                          region=region)

        except ValueError:
            return False

        self.region = region
        return True

    def _get_shared_images(self, username, region, gns3_version):
        """
        Given a GNS3 version, ask gns3-ias to share compatible images

        Response:
            [{"created_at": "", "schema": "", "status": "", "member_id": "", "image_id": "", "updated_at": ""},]
            or, if access was already asked
            [{"image_id": "", "member_id": "", "status": "ALREADYREQUESTED"},]
        """
        endpoint = GNS3IAS_URL+"/images/grant_access"
        params = {
            "user_id": username,
            "user_region": region,
            "gns3_version": gns3_version,
        }
        response = requests.get(endpoint, params=params)
        status = response.status_code
        if status == 200:
            return response.json()
        elif status == 404:
            raise ItemNotFound()
        else:
            raise ApiError("IAS status code: %d" % status)

    def list_images(self):
        """
        Return a dictionary containing RackSpace server images
        retrieved from gns3-ias server
        """
        if not (self.username and self.region):
            return []

        try:
            response = self._get_shared_images(self.username, self.region, __version__)
            shared_images = json.loads(response)
            images = {}
            for i in shared_images:
                images[i['image_id']] = i['image_name']
            return images
        except ItemNotFound:
            return []
        except ApiError as e:
            log.error('Error while retrieving image list: %s' % e)

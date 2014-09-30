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

"""
Simple file upload & listing handler.
"""


import os
import tornado.web
import tornado.websocket

import logging
log = logging.getLogger(__name__)

class GNS3BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        if 'required_user' not in self.settings:
            return "FakeUser"

        user = self.get_secure_cookie("user")
        if not user:
          return None

        if self.settings['required_user'] == user.decode("utf-8"):
          return user

class GNS3WebSocketBaseHandler(tornado.websocket.WebSocketHandler):
    def get_current_user(self):
        if 'required_user' not in self.settings:
            return "FakeUser"

        user = self.get_secure_cookie("user")
        if not user:
          return None

        if self.settings['required_user'] == user.decode("utf-8"):
          return user


class LoginHandler(tornado.web.RequestHandler):
    def get(self):
        self.write('<html><body><form action="/login" method="post">'
                   'Name: <input type="text" name="name">'
                   'Password: <input type="text" name="password">'
                   '<input type="submit" value="Sign in">'
                   '</form></body></html>')

        try:
          redirect_to = self.get_argument("next")
          self.set_secure_cookie("login_success_redirect_to", redirect_to)
        except tornado.web.MissingArgumentError:
          pass

    def post(self):

        user = self.get_argument("name")
        password = self.get_argument("password")

        if self.settings['required_user'] == user and self.settings['required_pass'] == password:
          self.set_secure_cookie("user", user)
          auth_status = "successful"
        else:
          self.set_secure_cookie("user", "None")
          auth_status = "failure"

        log.info("Authentication attempt %s: %s" %(auth_status, user))

        try:
          redirect_to = self.get_secure_cookie("login_success_redirect_to")
        except tornado.web.MissingArgumentError:
          redirect_to = "/"

        self.redirect(redirect_to)
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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

import multiprocessing
import zmq

import logging
log = logging.getLogger(__name__)


class IModule(multiprocessing.Process):
    """
    Module interface
    """

    destination = {}

    def __init__(self, name=None, args=(), kwargs={}):

        multiprocessing.Process.__init__(self,
                                         name=name,
                                         args=args,
                                         kwargs=kwargs)

        self._context = None
        self._ioloop = None
        self._stream = None
        self._host = args[0]
        self._port = args[1]
        self._current_session = None
        self._current_destination = None

    def setup(self):
        """
        Sets up PyZMQ and creates the stream to handle requests
        """

        self._context = zmq.Context()
        self._ioloop = zmq.eventloop.ioloop.IOLoop.instance()
        self._stream = self.create_stream(self._host, self._port, self.decode_request)

    def create_stream(self, host=None, port=0, callback=None):
        """
        Creates a new ZMQ stream
        """

        socket = self._context.socket(zmq.DEALER)
        socket.setsockopt(zmq.IDENTITY, self.name.encode("utf-8"))
        if host and port:
            log.info("ZeroMQ client ({}) connecting to {}:{}".format(self.name, host, port))
            try:
                socket.connect("tcp://{}:{}".format(host, port))
            except zmq.error.ZMQError as e:
                log.critical("Could not connect to ZeroMQ server on {}:{}, reason: {}".format(host, port, e))
                raise SystemExit
        else:
            log.info("ZeroMQ client ({}) connecting to ipc:///tmp/gns3.ipc".format(self.name))
            try:
                socket.connect("ipc:///tmp/gns3.ipc")
            except zmq.error.ZMQError as e:
                log.critical("Could not connect to ZeroMQ server on ipc:///tmp/gns3.ipc, reason: {}".format(e))
                raise SystemExit

        stream = zmq.eventloop.zmqstream.ZMQStream(socket, self._ioloop)
        if callback:
            stream.on_recv(callback)
        return stream

    def run(self):
        """
        Sets up everything and starts the event loop
        """

        self.setup()
        try:
            self._ioloop.start()
        except KeyboardInterrupt:
            return

    def stop(self):
        """
        Stops the event loop
        """

        #zmq.eventloop.ioloop.IOLoop.instance().stop()
        self._ioloop.stop()

    def send_response(self, response):
        """
        Sends a response back to the requester
        """

        # add session and destination to the response
        response = [self._current_session, self._current_destination, response]
        log.debug("ZeroMQ client ({}) sending: {}".format(self.name, response))
        self._stream.send_json(response)

    def decode_request(self, request):
        """
        Decodes the request to JSON
        """

        try:
            request = zmq.utils.jsonapi.loads(request[0])
        except ValueError:
            self.send_response("ValueError")  # FIXME: explicit json error
            return

        log.debug("ZeroMQ client ({}) received: {}".format(self.name, request))
        self._current_session = request[0]
        self._current_destination = request[1]

        if self._current_destination not in self.destination:
            # FIXME: return error if destination not found!
            return
        log.debug("Routing request to {}: {}".format(self._current_destination, request[2]))
        self.destination[self._current_destination](self, request[2])

    def destinations(self):
        """
        Channels handled by this modules.
        """

        return self.destination.keys()

    @classmethod
    def route(cls, destination):
        """
        Decorator to register a destination routed to a method
        """

        def wrapper(method):
            cls.destination[destination] = method
            return method
        return wrapper

#!/usr/bin/env python
#
# Copyright (C) 2017 GNS3 Technologies Inc.
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

import asyncio

#from gns3server.utils.asyncio.embed_shell import EmbedShell

#FIXME: this is broken with recent Python >= 3.6
# def test_embed_shell_help(async_run):
#     class Application(EmbedShell):
#
#         async def hello(self):
#             """
#             The hello world function
#
#             The hello usage
#             """
#             await asyncio.sleep(1)
#
#     reader = asyncio.StreamReader()
#     writer = asyncio.StreamReader()
#     app = Application(reader, writer)
#     assert async_run(app._parse_command('help')) == 'Help:\nhello: The hello world function\n\nhelp command for details about a command\n'
#     assert async_run(app._parse_command('?')) == 'Help:\nhello: The hello world function\n\nhelp command for details about a command\n'
#     assert async_run(app._parse_command('? hello')) == 'hello: The hello world function\n\nThe hello usage\n'


# def test_embed_shell_execute(async_run):
#     class Application(EmbedShell):
#
#         async def hello(self):
#             """
#             The hello world function
#
#             The hello usage
#             """
#             return 'world'
#     reader = asyncio.StreamReader()
#     writer = asyncio.StreamReader()
#     app = Application(reader, writer)
#     assert async_run(app._parse_command('hello')) == 'world'
#
#
# def test_embed_shell_welcome(async_run, loop):
#     reader = asyncio.StreamReader()
#     writer = asyncio.StreamReader()
#     app = EmbedShell(reader, writer, welcome_message="Hello")
#     task = loop.create_task(app.run())
#     assert async_run(writer.read(5)) == b"Hello"
#     task.cancel()
#     try:
#         loop.run_until_complete(task)
#     except asyncio.CancelledError:
#         pass
#
#
# def test_embed_shell_prompt(async_run, loop):
#     reader = asyncio.StreamReader()
#     writer = asyncio.StreamReader()
#     app = EmbedShell(reader, writer)
#     app.prompt = "gbash# "
#     task = loop.create_task(app.run())
#     assert async_run(writer.read(7)) == b"gbash# "
#     task.cancel()
#     try:
#         loop.run_until_complete(task)
#     except asyncio.CancelledError:
#         pass

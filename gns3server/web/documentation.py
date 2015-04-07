# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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

import re
import os.path
import os

from gns3server.handlers import *
from gns3server.web.route import Route


class Documentation(object):

    """Extract API documentation as Sphinx compatible files"""

    def __init__(self, route, directory):
        """
        :param route: Route instance
        :param directory: Output directory
        """
        self._documentation = route.get_documentation()
        self._directory = directory

    def write(self):
        for handler_name in sorted(self._documentation):
            print("Build {}".format(handler_name))

            for path in sorted(self._documentation[handler_name]):

                api_version = self._documentation[handler_name][path]["api_version"]
                if api_version is None:
                    continue

                self._create_handler_directory(handler_name, api_version)

                filename = self._file_path(path)
                handler_doc = self._documentation[handler_name][path]
                with open("{}/api/v{}/{}/{}.rst".format(self._directory, api_version, handler_name, filename), 'w+') as f:
                    f.write('{}\n----------------------------------------------------------------------------------------------------------------------\n\n'.format(path))
                    f.write('.. contents::\n')
                    for method in handler_doc["methods"]:
                        f.write('\n{} {}\n'.format(method["method"], path.replace("{", '**{').replace("}", "}**")))
                        f.write('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n')
                        f.write('{}\n\n'.format(method["description"]))

                        if len(method["parameters"]) > 0:
                            f.write("Parameters\n**********\n")
                            for parameter in method["parameters"]:
                                desc = method["parameters"][parameter]
                                f.write("- **{}**: {}\n".format(parameter, desc))
                            f.write("\n")

                        f.write("Response status codes\n**********************\n")
                        for code in method["status_codes"]:
                            desc = method["status_codes"][code]
                            f.write("- **{}**: {}\n".format(code, desc))
                        f.write("\n")

                        if "properties" in method["input_schema"]:
                            f.write("Input\n*******\n")
                            self._write_definitions(f, method["input_schema"])
                            self._write_json_schema(f, method["input_schema"])

                        if "properties" in method["output_schema"]:
                            f.write("Output\n*******\n")
                            self._write_json_schema(f, method["output_schema"])

                        self._include_query_example(f, method, path, api_version)

    def _create_handler_directory(self, handler_name, api_version):
        """Create a directory for the handler and add an index inside"""

        directory = "{}/api/v{}/{}".format(self._directory, api_version, handler_name)
        os.makedirs(directory, exist_ok=True)

        with open("{}/api/v{}/{}.rst".format(self._directory, api_version, handler_name), "w+") as f:
            f.write(handler_name.replace("api.", "").replace("_", " ", ).capitalize())
            f.write("\n---------------------\n\n")
            f.write(".. toctree::\n   :glob:\n   :maxdepth: 2\n\n   {}/*\n".format(handler_name))

    def _include_query_example(self, f, method, path, api_version):
        """If a sample session is available we include it in documentation"""
        m = method["method"].lower()
        query_path = "{}_{}.txt".format(m, self._file_path(path))
        if os.path.isfile(os.path.join(self._directory, "api", "examples", query_path)):
            f.write("Sample session\n***************\n")
            f.write("\n\n.. literalinclude:: ../../examples/{}\n\n".format(query_path))

    def _file_path(self, path):
        return re.sub("^v1", "", re.sub("[^a-z0-9]", "", path))

    def _write_definitions(self, f, schema):
        if "definitions" in schema:
            f.write("Types\n+++++++++\n")
            for definition in sorted(schema['definitions']):
                desc = schema['definitions'][definition].get("description")
                f.write("{}\n^^^^^^^^^^^^^^^^^^^^^^\n{}\n\n".format(definition, desc))
                self._write_json_schema(f, schema['definitions'][definition])
            f.write("Body\n+++++++++\n")

    def _write_json_schema_object(self, f, obj):
        """
            obj is current object in JSON schema
            schema is the whole schema including definitions
        """
        for name in sorted(obj.get("properties", {})):
            prop = obj["properties"][name]
            mandatory = " "
            if name in obj.get("required", []):
                mandatory = "&#10004;"

            if "enum" in prop:
                field_type = "enum"
                prop['description'] = "Possible values: {}".format(', '.join(prop['enum']))
            else:
                field_type = prop.get("type", "")

            # Resolve oneOf relation to their human type.
            if field_type == 'object' and 'oneOf' in prop:
                field_type = ', '.join(map(lambda p: p['$ref'].split('/').pop(), prop['oneOf']))

            f.write("    <tr><td>{}</td>\
                    <td>{}</td> \
                    <td>{}</td> \
                    <td>{}</td> \
                    </tr>\n".format(
                name,
                mandatory,
                field_type,
                prop.get("description", "")
            ))

    def _write_json_schema(self, f, schema):
        # TODO: rewrite this using RST for portability
        f.write(".. raw:: html\n\n    <table>\n")
        f.write("    <tr> \
                <th>Name</th> \
                <th>Mandatory</th> \
                <th>Type</th> \
                <th>Description</th> \
                </tr>\n")
        self._write_json_schema_object(f, schema)
        f.write("    </table>\n\n")


if __name__ == '__main__':
    print("Generate API documentation")
    Documentation(Route, "docs").write()

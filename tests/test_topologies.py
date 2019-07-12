#!/usr/bin/env python
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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


#
# This will test the conversion from old topology format to the new
#
# Read tests/topologies/README.rst for documentation

import os
import json
import pytest
import shutil


from gns3server.controller.topology import load_topology, GNS3_FILE_FORMAT_REVISION
from gns3server.version import __version__

topologies_directory = os.path.join(os.path.dirname(os.path.realpath(__file__)), "topologies")


def topologies():
    dirs = []
    for directory in os.listdir(topologies_directory):
        if os.path.isdir(os.path.join(topologies_directory, directory)):
            dirs.append(directory)
    return dirs


@pytest.mark.parametrize("directory", topologies())
def test_convert(directory, tmpdir):
    before_directory = os.path.join(topologies_directory, directory, "before")
    after_directory = os.path.join(topologies_directory, directory, "after")

    assert os.path.exists(before_directory), "No before directory found file for {}".format(directory)
    assert os.path.exists(after_directory), "No after directory found file for {}".format(directory)

    gns3_file = None
    for file in os.listdir(before_directory):
        if file.endswith(".gns3"):
            gns3_file = file

    assert gns3_file, "No .gns3 found file for {}".format(before_directory)

    with open(os.path.join(before_directory, gns3_file)) as f:
        before_topology = json.load(f)

    # We use a temporary directory for conversion operation to not corrupt our files
    work_directory = str(tmpdir / "work")
    shutil.copytree(before_directory, work_directory)

    work_topology = load_topology(os.path.join(work_directory, gns3_file))
    assert work_topology

    if "revision" not in before_topology or before_topology["revision"] < GNS3_FILE_FORMAT_REVISION:
        assert os.path.exists(os.path.join(work_directory, gns3_file + ".backup{}".format(before_topology.get("revision", 0))))

    # We should have the same file in after directory and the work directory
    for root, dirs, files in os.walk(after_directory):
        for file in files:
            directory = os.path.relpath(root, after_directory)
            file_path = os.path.join(work_directory, directory, file)
            assert os.path.exists(file_path), "{} is missing".format(os.path.join(directory, file))

            # For gns3project we check if size are not too much differents
            if file_path.endswith(".gns3project"):
                size = os.stat(file_path).st_size
                other_size = os.stat(os.path.join(os.path.join(root, file))).st_size
                assert size in range(other_size - 100, other_size + 100), "File {} is different".format(os.path.join(directory, file))
            # For non .gns3 file we check if the file are the same
            elif not file_path.endswith(".gns3"):
                assert os.stat(file_path).st_size == os.stat(os.path.join(os.path.join(root, file))).st_size, "File {} is different".format(os.path.join(directory, file))

    # Check if we don't have unexpected file in work directory
    for root, dirs, files in os.walk(work_directory):
        for file in files:
            directory = os.path.relpath(root, work_directory)
            file_path = os.path.join(after_directory, directory, file)
            # .backup are created by the conversion process
            if ".backup" not in file_path:
                assert os.path.exists(file_path), "{} should not be here".format(os.path.join(directory, file))

    with open(os.path.join(after_directory, gns3_file)) as f:
        after_topology = json.load(f)
    compare_dict("/", work_topology, after_topology)


def compare_dict(path, source, reference):
    """
    Compare two dictionary of a topology
    """
    assert isinstance(source, dict), "Source is not a dict in {}".format(path)
    for key in source:
        assert key in reference, "Unexpected {} in {} it should be {}".format(key, source, reference)
    for key in sorted(reference.keys()):
        val = reference[key]
        assert key in source, "{} is missing in {}".format(key, source)
        if isinstance(val, str) or isinstance(val, float) or isinstance(val, int) or isinstance(val, bool) or val is None:
            if val == "ANYSTR":
                pass
            elif val == "ANYUUID" and len(source[key]) == 36:
                pass
            # We test that the revision number has been bumped to last version. This avoid modifying all the tests
            # at each new revision bump.
            elif key == "revision":
                assert source[key] == GNS3_FILE_FORMAT_REVISION
            elif key == "version":
                assert source[key] == __version__
            else:
                assert val == source[key], "Wrong value for {}: \n{}\nit should be\n{}".format(key, source[key], val)
        elif isinstance(val, dict):
            compare_dict(path + key + "/", source[key], val)
        elif isinstance(val, list):
            assert len(val) == len(source[key]), "Not enough value in {} ({}/{}) it shoud be {} not {}".format(key, len(val), len(source[key]), val, source[key])
            for idx, element in enumerate(source[key]):
                if isinstance(element, dict):
                    compare_dict(path + key + "/", element, val[idx])
                else:
                    assert element == val[idx]
        else:
            assert False, "Value type for {} is not supported".format(key)

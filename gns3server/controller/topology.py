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

import os
import html
import json
import uuid
import glob
import shutil
import zipfile
import pydantic

from typing import Optional

from ..version import __version__
from ..utils.qt import qt_font_to_style
from ..compute.dynamips import PLATFORMS_DEFAULT_RAM
from .controller_error import ControllerError
from .compute import Compute
from .drawing import Drawing
from .node import Node
from .link import Link

from gns3server.schemas.controller.topology import Topology
from gns3server.schemas.compute.dynamips_nodes import DynamipsCreate

import logging

log = logging.getLogger(__name__)


GNS3_FILE_FORMAT_REVISION = 9


class DynamipsNodeValidation(DynamipsCreate):
    name: Optional[str] = None


def _check_topology_schema(topo, path):
    try:
        Topology.model_validate(topo)

        # Check the nodes property against compute schemas
        for node in topo["topology"].get("nodes", []):
            if node["node_type"] == "dynamips":
                DynamipsNodeValidation.model_validate(node.get("properties", {}))

    except pydantic.ValidationError as e:
        error = f"Invalid data in topology file {path}: {e}"
        log.critical(error)
        raise ControllerError(error)


def project_to_topology(project):
    """
    :return: A dictionary with the topology ready to dump to a .gns3
    """
    data = {
        "project_id": project.id,
        "name": project.name,
        "auto_start": project.auto_start,
        "auto_open": project.auto_open,
        "auto_close": project.auto_close,
        "scene_width": project.scene_width,
        "scene_height": project.scene_height,
        "zoom": project.zoom,
        "show_layers": project.show_layers,
        "snap_to_grid": project.snap_to_grid,
        "show_grid": project.show_grid,
        "grid_size": project.grid_size,
        "drawing_grid_size": project.drawing_grid_size,
        "show_interface_labels": project.show_interface_labels,
        "variables": project.variables,
        "supplier": project.supplier,
        "topology": {"nodes": [], "links": [], "computes": [], "drawings": []},
        "type": "topology",
        "revision": GNS3_FILE_FORMAT_REVISION,
        "version": __version__,
    }

    for node in project.nodes.values():
        if isinstance(node, Node):
            data["topology"]["nodes"].append(node.asdict(topology_dump=True))
        else:
            data["topology"]["nodes"].append(node)
    for link in project.links.values():
        if isinstance(link, Link):
            data["topology"]["links"].append(link.asdict(topology_dump=True))
        else:
            data["topology"]["links"].append(link)
    for drawing in project.drawings.values():
        if isinstance(drawing, Drawing):
            data["topology"]["drawings"].append(drawing.asdict(topology_dump=True))
        else:
            data["topology"]["drawings"].append(drawing)
    for compute in project.computes:
        if isinstance(compute, Compute):
            compute = compute.asdict(topology_dump=True)
            if compute["compute_id"] not in (
                "vm",
                "local",
            ):
                data["topology"]["computes"].append(compute)
        elif isinstance(compute, dict):
            data["topology"]["computes"].append(compute)
    _check_topology_schema(data, project.path)
    return data


def load_topology(path):
    """
    Open a topology file, patch it for last GNS3 release and return it
    """

    log.debug(f"Read topology {path}")
    try:
        with open(path, encoding="utf-8") as f:
            topo = json.load(f)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise ControllerError(f"Could not load topology {path}: {str(e)}")

    if topo.get("revision", 0) > GNS3_FILE_FORMAT_REVISION:
        raise ControllerError(
            "This project was created with more recent version of GNS3 (file revision: {}). Please upgrade GNS3 to version {} or later".format(
                topo["revision"], topo["version"]
            )
        )

    changed = False
    if "revision" not in topo or topo["revision"] < GNS3_FILE_FORMAT_REVISION:
        # Convert the topology if this is an old one but backup the file first
        try:
            shutil.copy(path, path + ".backup{}".format(topo.get("revision", 0)))
        except OSError as e:
            raise ControllerError(f"Can't write backup of the topology {path}: {str(e)}")
        changed = True
        # update the version because we converted the topology
        topo["version"] = __version__

    if "revision" not in topo or topo["revision"] < 5:
        topo = _convert_1_3_later(topo, path)

    # Version before GNS3 2.0 alpha 4
    if topo["revision"] < 6:
        topo = _convert_2_0_0_alpha(topo, path)

    # Version before GNS3 2.0 beta 3
    if topo["revision"] < 7:
        topo = _convert_2_0_0_beta_2(topo, path)

    # Version before GNS3 2.1
    if topo["revision"] < 8:
        topo = _convert_2_0_0(topo, path)

    # Version before GNS3 2.1
    if topo["revision"] < 9:
        topo = _convert_2_1_0(topo, path)

    # Version GNS3 2.2 dev (for project created with 2.2dev).
    # Appliance ID has been replaced by Template ID
    if topo["revision"] == 9:
        for node in topo.get("topology", {}).get("nodes", []):
            if "appliance_id" in node:
                node["template_id"] = node["appliance_id"]
                del node["appliance_id"]
            # make sure console_type is not None but "none" string
            if "console_type" in node and node["console_type"] is None:
                node["console_type"] = "none"

        # make sure we can open a project with empty variable name
        variables = topo.get("variables")
        if variables:
            topo["variables"] = [var for var in variables if var.get("name")]

    try:
        _check_topology_schema(topo, path)
    except ControllerError as e:
        log.error("Can't load the topology %s", path)
        raise e

    if changed:
        try:
            with open(path, "w+", encoding="utf-8") as f:
                json.dump(topo, f, indent=4, sort_keys=True)
        except OSError as e:
            raise ControllerError(f"Can't write the topology {path}: {str(e)}")
    return topo


def _convert_2_1_0(topo, topo_path):
    """
    Convert topologies from GNS3 2.1.x to 2.2

    Changes:
     * Removed acpi_shutdown option from Qemu, VMware and VirtualBox

    """
    topo["revision"] = 9

    if "grid_size" in topo:
        # drawing_grid_size should be the same size as grid_size
        # to avoid overlapping grids
        topo["drawing_grid_size"] = topo["grid_size"]

    for node in topo.get("topology", {}).get("nodes", []):
        # make sure console_type is not None but "none" string
        if "console_type" in node and node["console_type"] is None:
            node["console_type"] = "none"
        if "properties" in node:
            if node["node_type"] in ("qemu", "vmware", "virtualbox"):
                if "acpi_shutdown" in node["properties"]:
                    if node["properties"]["acpi_shutdown"] is True:
                        node["properties"]["on_close"] = "save_vm_state"
                    else:
                        node["properties"]["on_close"] = "power_off"
                    del node["properties"]["acpi_shutdown"]
                if "save_vm_state" in node["properties"]:
                    del node["properties"]["save_vm_state"]
    return topo


def _convert_2_0_0(topo, topo_path):
    """
    Convert topologies from GNS3 2.0.0 to 2.1

    Changes:
     * Remove startup_script_path from VPCS and base config file for IOU and Dynamips
    """
    topo["revision"] = 8

    for node in topo.get("topology", {}).get("nodes", []):
        if "properties" in node:
            if node["node_type"] == "vpcs":
                if "startup_script_path" in node["properties"]:
                    del node["properties"]["startup_script_path"]
                if "startup_script" in node["properties"]:
                    del node["properties"]["startup_script"]
            elif node["node_type"] == "dynamips" or node["node_type"] == "iou":
                if "startup_config" in node["properties"]:
                    del node["properties"]["startup_config"]
                if "private_config" in node["properties"]:
                    del node["properties"]["private_config"]
                if "startup_config_content" in node["properties"]:
                    del node["properties"]["startup_config_content"]
                if "private_config_content" in node["properties"]:
                    del node["properties"]["private_config_content"]
    return topo


def _convert_2_0_0_beta_2(topo, topo_path):
    """
    Convert topologies from GNS3 2.0.0 beta 2 to beta 3.

    Changes:
     * Node id folders for dynamips
    """
    topo_dir = os.path.dirname(topo_path)
    topo["revision"] = 7

    for node in topo.get("topology", {}).get("nodes", []):
        if node["node_type"] == "dynamips":
            node_id = node["node_id"]
            dynamips_id = node["properties"]["dynamips_id"]

            dynamips_dir = os.path.join(topo_dir, "project-files", "dynamips")
            node_dir = os.path.join(dynamips_dir, node_id)
            try:
                os.makedirs(os.path.join(node_dir, "configs"), exist_ok=True)
                for path in glob.glob(os.path.join(glob.escape(dynamips_dir), f"*_i{dynamips_id}_*")):
                    shutil.move(path, os.path.join(node_dir, os.path.basename(path)))
                for path in glob.glob(os.path.join(glob.escape(dynamips_dir), "configs", f"i{dynamips_id}_*")):
                    shutil.move(path, os.path.join(node_dir, "configs", os.path.basename(path)))
            except OSError as e:
                raise ControllerError(f"Can't convert project {topo_path}: {str(e)}")
    return topo


def _convert_2_0_0_alpha(topo, topo_path):
    """
    Convert topologies from GNS3 2.0.0 alpha to 2.0.0 final.

    Changes:
     * No more serial console
     * No more option for VMware / VirtualBox remote console (always use telnet)
    """
    topo["revision"] = 6
    for node in topo.get("topology", {}).get("nodes", []):
        if node.get("console_type") == "serial":
            node["console_type"] = "telnet"
        if node["node_type"] in ("vmware", "virtualbox"):
            prop = node.get("properties")
            if "enable_remote_console" in prop:
                del prop["enable_remote_console"]
    return topo


def _convert_1_3_later(topo, topo_path):
    """
    Convert topologies from 1_3 to the new file format

    Look in tests/topologies/README.rst for instructions to test changes here
    """
    topo_dir = os.path.dirname(topo_path)

    _convert_snapshots(topo_dir)

    new_topo = {
        "type": "topology",
        "revision": 5,
        "version": __version__,
        "auto_start": topo.get("auto_start", False),
        "name": topo["name"],
        "project_id": topo.get("project_id"),
        "topology": {"links": [], "drawings": [], "computes": [], "nodes": []},
    }
    if new_topo["project_id"] is None:
        new_topo["project_id"] = str(uuid.uuid4())  # Could arrive for topologues with drawing only
    if "topology" not in topo:
        return new_topo
    topo = topo["topology"]

    # Create computes
    server_id_to_compute_id = {}
    for server in topo.get("servers", []):
        compute = {
            "host": server.get("host", "localhost"),
            "port": server.get("port", 3080),
            "protocol": server.get("protocol", "http"),
        }
        if server["local"]:
            compute["compute_id"] = "local"
            compute["name"] = "Local"
        elif server.get("vm", False):
            compute["compute_id"] = "vm"
            compute["name"] = "GNS3 VM"
        else:
            compute["name"] = "Remote {}".format(server["id"])
            compute["compute_id"] = str(uuid.uuid4())
        server_id_to_compute_id[server["id"]] = compute["compute_id"]
        new_topo["topology"]["computes"].append(compute)

    # Create nodes
    ports = {}
    node_id_to_node_uuid = {}
    for old_node in topo.get("nodes", []):
        node = {}
        node["console"] = old_node["properties"].get("console", None)
        try:
            node["compute_id"] = server_id_to_compute_id[old_node["server_id"]]
        except KeyError:
            node["compute_id"] = "local"
        node["console_type"] = old_node["properties"].get("console_type", "telnet")
        if "label" in old_node:
            node["name"] = old_node["label"]["text"]
            node["label"] = _convert_label(old_node["label"])
        else:
            node["name"] = old_node["properties"]["name"]
        node["node_id"] = old_node.get("vm_id", str(uuid.uuid4()))

        node["symbol"] = old_node.get("symbol", None)
        # Compatibility with <= 1.3
        if node["symbol"] is None and "default_symbol" in old_node:
            if old_node["default_symbol"].endswith("normal.svg"):
                node["symbol"] = old_node["default_symbol"][:-11] + ".svg"
            else:
                node["symbol"] = old_node["default_symbol"]

        node["x"] = int(old_node["x"])
        node["y"] = int(old_node["y"])
        node["z"] = int(old_node.get("z", 1))
        node["port_name_format"] = old_node.get("port_name_format", "Ethernet{0}")
        node["port_segment_size"] = int(old_node.get("port_segment_size", "0"))
        node["first_port_name"] = old_node.get("first_port_name")

        node["properties"] = {}

        # Some old dynamips node don't have type
        if "type" not in old_node:
            old_node["type"] = old_node["properties"]["platform"].upper()

        if old_node["type"] == "VPCSDevice":
            node["node_type"] = "vpcs"
        elif old_node["type"] == "QemuVM":
            node = _convert_qemu_node(node, old_node)
        elif old_node["type"] == "DockerVM":
            node["node_type"] = "docker"
            if node["symbol"] is None:
                node["symbol"] = ":/symbols/docker_guest.svg"
        elif old_node["type"] == "ATMSwitch":
            node["node_type"] = "atm_switch"
            node["symbol"] = ":/symbols/atm_switch.svg"
            node["console_type"] = None
        elif old_node["type"] == "EthernetHub":
            node["node_type"] = "ethernet_hub"
            node["console_type"] = None
            node["symbol"] = ":/symbols/hub.svg"
            node["properties"]["ports_mapping"] = []
            for port in old_node.get("ports", []):
                node["properties"]["ports_mapping"].append(
                    {"name": "Ethernet{}".format(port["port_number"] - 1), "port_number": port["port_number"] - 1}
                )
        elif old_node["type"] == "EthernetSwitch":
            node["node_type"] = "ethernet_switch"
            node["symbol"] = ":/symbols/ethernet_switch.svg"
            node["console_type"] = None
            node["properties"]["ports_mapping"] = []
            for port in old_node.get("ports", []):
                node["properties"]["ports_mapping"].append(
                    {
                        "name": "Ethernet{}".format(port["port_number"] - 1),
                        "port_number": port["port_number"] - 1,
                        "type": port["type"],
                        "vlan": port["vlan"],
                    }
                )
        elif old_node["type"] == "FrameRelaySwitch":
            node["node_type"] = "frame_relay_switch"
            node["symbol"] = ":/symbols/frame_relay_switch.svg"
            node["console_type"] = None
        elif old_node["type"].upper() in [
            "C1700",
            "C2600",
            "C2691",
            "C3600",
            "C3620",
            "C3640",
            "C3660",
            "C3725",
            "C3745",
            "C7200",
            "EtherSwitchRouter",
        ]:
            if node["symbol"] is None:
                node["symbol"] = ":/symbols/router.svg"
            node["node_type"] = "dynamips"
            node["properties"]["dynamips_id"] = old_node.get("dynamips_id")
            if "platform" not in node["properties"] and old_node["type"].upper().startswith("C"):
                node["properties"]["platform"] = old_node["type"].lower()
                if node["properties"]["platform"].startswith("c36"):
                    node["properties"]["platform"] = "c3600"
            if "ram" not in node["properties"] and old_node["type"].startswith("C"):
                node["properties"]["ram"] = PLATFORMS_DEFAULT_RAM[old_node["type"].lower()]
        elif old_node["type"] == "VMwareVM":
            node["node_type"] = "vmware"
            node["properties"]["linked_clone"] = old_node.get("linked_clone", False)
            if node["symbol"] is None:
                node["symbol"] = ":/symbols/vmware_guest.svg"
        elif old_node["type"] == "VirtualBoxVM":
            node["node_type"] = "virtualbox"
            node["properties"]["linked_clone"] = old_node.get("linked_clone", False)
            if node["symbol"] is None:
                node["symbol"] = ":/symbols/vbox_guest.svg"
        elif old_node["type"] == "IOUDevice":
            node["node_type"] = "iou"
            node["port_name_format"] = old_node.get("port_name_format", "Ethernet{segment0}/{port0}")
            node["port_segment_size"] = int(old_node.get("port_segment_size", "4"))
            if node["symbol"] is None:
                if "l2" in node["properties"].get("path", ""):
                    node["symbol"] = ":/symbols/multilayer_switch.svg"
                else:
                    node["symbol"] = ":/symbols/router.svg"

        elif old_node["type"] == "Cloud":
            symbol = old_node.get("symbol", ":/symbols/cloud.svg")
            old_node["ports"] = _create_cloud(node, old_node, symbol)
        elif old_node["type"] == "Host":
            symbol = old_node.get("symbol", ":/symbols/computer.svg")
            old_node["ports"] = _create_cloud(node, old_node, symbol)
        else:
            raise ControllerError("Conversion of {} is not supported".format(old_node["type"]))

        for prop in old_node.get("properties", {}):
            if prop not in ["console", "name", "console_type", "console_host", "use_ubridge"]:
                node["properties"][prop] = old_node["properties"][prop]

        node_id_to_node_uuid[old_node["id"]] = node["node_id"]
        for port in old_node.get("ports", []):
            if node["node_type"] in ("ethernet_hub", "ethernet_switch"):
                port["port_number"] -= 1
            ports[port["id"]] = port
        new_topo["topology"]["nodes"].append(node)

    # Create links
    for old_link in topo.get("links", []):
        try:
            nodes = []
            source_node = {
                "adapter_number": ports[old_link["source_port_id"]].get("adapter_number", 0),
                "port_number": ports[old_link["source_port_id"]].get("port_number", 0),
                "node_id": node_id_to_node_uuid[old_link["source_node_id"]],
            }
            nodes.append(source_node)

            destination_node = {
                "adapter_number": ports[old_link["destination_port_id"]].get("adapter_number", 0),
                "port_number": ports[old_link["destination_port_id"]].get("port_number", 0),
                "node_id": node_id_to_node_uuid[old_link["destination_node_id"]],
            }
            nodes.append(destination_node)
        except KeyError:
            continue

        link = {"link_id": str(uuid.uuid4()), "nodes": nodes}
        new_topo["topology"]["links"].append(link)

    # Ellipse
    for ellipse in topo.get("ellipses", []):
        svg = '<svg height="{height}" width="{width}"><ellipse cx="{cx}" cy="{cy}" fill="{fill}" fill-opacity="1.0" rx="{rx}" ry="{ry}" {border_style} /></svg>'.format(
            height=int(ellipse["height"]),
            width=int(ellipse["width"]),
            cx=int(ellipse["width"] / 2),
            cy=int(ellipse["height"] / 2),
            rx=int(ellipse["width"] / 2),
            ry=int(ellipse["height"] / 2),
            fill=ellipse.get("color", "#ffffff"),
            border_style=_convert_border_style(ellipse),
        )
        new_ellipse = {
            "drawing_id": str(uuid.uuid4()),
            "x": int(ellipse["x"]),
            "y": int(ellipse["y"]),
            "z": int(ellipse.get("z", 0)),
            "rotation": int(ellipse.get("rotation", 0)),
            "svg": svg,
        }
        new_topo["topology"]["drawings"].append(new_ellipse)

    # Notes
    for note in topo.get("notes", []):
        font_info = note.get("font", "TypeWriter,10,-1,5,75,0,0,0,0,0").split(",")

        if font_info[4] == "75":
            weight = "bold"
        else:
            weight = "normal"
        if font_info[5] == "1":
            style = "italic"
        else:
            style = "normal"

        svg = '<svg height="{height}" width="{width}"><text fill="{fill}" fill-opacity="{opacity}" font-family="{family}" font-size="{size}" font-weight="{weight}" font-style="{style}">{text}</text></svg>'.format(
            height=int(font_info[1]) * 2,
            width=int(font_info[1]) * len(note["text"]),
            fill="#" + note.get("color", "#00000000")[-6:],
            opacity=round(
                1.0 / 255 * int(note.get("color", "#ffffffff")[:3][-2:], base=16), 2
            ),  # Extract the alpha channel from the hexa version
            family=font_info[0],
            size=int(font_info[1]),
            weight=weight,
            style=style,
            text=html.escape(note["text"]),
        )
        new_note = {
            "drawing_id": str(uuid.uuid4()),
            "x": int(note["x"]),
            "y": int(note["y"]),
            "z": int(note.get("z", 0)),
            "rotation": int(note.get("rotation", 0)),
            "svg": svg,
        }
        new_topo["topology"]["drawings"].append(new_note)

    # Images
    for image in topo.get("images", []):
        img_path = image["path"]
        # Absolute image path are rewrite to project specific image
        if os.path.abspath(img_path):
            try:
                os.makedirs(os.path.join(topo_dir, "images"), exist_ok=True)
                shutil.copy(img_path, os.path.join(topo_dir, "images", os.path.basename(img_path)))
            except OSError:
                pass
        new_image = {
            "drawing_id": str(uuid.uuid4()),
            "x": int(image["x"]),
            "y": int(image["y"]),
            "z": int(image.get("z", 0)),
            "rotation": int(image.get("rotation", 0)),
            "svg": os.path.basename(img_path),
        }
        new_topo["topology"]["drawings"].append(new_image)

    # Rectangles
    for rectangle in topo.get("rectangles", []):
        svg = '<svg height="{height}" width="{width}"><rect fill="{fill}" fill-opacity="1.0" height="{height}" width="{width}" {border_style} /></svg>'.format(
            height=int(rectangle["height"]),
            width=int(rectangle["width"]),
            fill=rectangle.get("color", "#ffffff"),
            border_style=_convert_border_style(rectangle),
        )
        new_rectangle = {
            "drawing_id": str(uuid.uuid4()),
            "x": int(rectangle["x"]),
            "y": int(rectangle["y"]),
            "z": int(rectangle.get("z", 0)),
            "rotation": int(rectangle.get("rotation", 0)),
            "svg": svg,
        }
        new_topo["topology"]["drawings"].append(new_rectangle)

    # Convert instructions.txt to README.txt
    instructions_path = os.path.join(topo_dir, "instructions.txt")
    readme_path = os.path.join(topo_dir, "README.txt")
    if os.path.exists(instructions_path) and not os.path.exists(readme_path):
        shutil.move(instructions_path, readme_path)

    return new_topo


def _convert_border_style(element):
    QT_DASH_TO_SVG = {2: "25, 25", 3: "5, 25", 4: "5, 25, 25", 5: "25, 25, 5, 25, 5"}
    border_style = int(element.get("border_style", 0))
    style = ""
    if border_style == 1:  # No border
        return ""
    elif border_style == 0:
        pass  # Solid line
    else:
        style += f'stroke-dasharray="{QT_DASH_TO_SVG[border_style]}" '
    style += 'stroke="{stroke}" stroke-width="{stroke_width}"'.format(
        stroke=element.get("border_color", "#000000"), stroke_width=element.get("border_width", 2)
    )
    return style


def _convert_label(label):
    """
    Convert a label from 1.X to the new format
    """
    style = qt_font_to_style(label.get("font"), label.get("color"))
    return {
        "text": html.escape(label["text"]),
        "rotation": 0,
        "style": style,
        "x": int(label["x"]),
        "y": int(label["y"]),
    }


def _create_cloud(node, old_node, icon):
    node["node_type"] = "cloud"
    node["symbol"] = icon
    node["console_type"] = None
    node["console"] = None
    del old_node["properties"]["nios"]

    ports = []
    keep_ports = []
    for old_port in old_node.get("ports", []):
        if old_port["name"].startswith("nio_gen_eth"):
            port_type = "ethernet"
        elif old_port["name"].startswith("nio_gen_linux"):
            port_type = "ethernet"
        elif old_port["name"].startswith("nio_tap"):
            port_type = "tap"
        elif old_port["name"].startswith("nio_udp"):
            port_type = "udp"
        elif old_port["name"].startswith("nio_nat"):
            continue
        else:
            raise ControllerError("The conversion of cloud with {} is not supported".format(old_port["name"]))

        if port_type == "udp":
            try:
                _, lport, rhost, rport = old_port["name"].split(":")
            except ValueError:
                raise ControllerError("UDP tunnel using IPV6 is not supported in cloud")
            port = {
                "name": f"UDP tunnel {len(ports) + 1}",
                "port_number": len(ports) + 1,
                "type": port_type,
                "lport": int(lport),
                "rhost": rhost,
                "rport": int(rport),
            }
        else:
            port = {
                "interface": old_port["name"].split(":")[1],
                "name": old_port["name"].split(":")[1],
                "port_number": len(ports) + 1,
                "type": port_type,
            }
        keep_ports.append(old_port)
        ports.append(port)

    node["properties"]["ports_mapping"] = ports
    node["properties"]["interfaces"] = []
    return keep_ports


def _convert_snapshots(topo_dir):
    """
    Convert 1.x snapshot to the new format
    """
    old_snapshots_dir = os.path.join(topo_dir, "project-files", "snapshots")
    if os.path.exists(old_snapshots_dir):
        new_snapshots_dir = os.path.join(topo_dir, "snapshots")
        os.makedirs(new_snapshots_dir, exist_ok=True)

        for snapshot in os.listdir(old_snapshots_dir):
            snapshot_dir = os.path.join(old_snapshots_dir, snapshot)
            if os.path.isdir(snapshot_dir):
                is_gns3_topo = False

                # In .gns3project fileformat the .gns3 should be name project.gns3
                for file in os.listdir(snapshot_dir):
                    if file.endswith(".gns3"):
                        shutil.move(os.path.join(snapshot_dir, file), os.path.join(snapshot_dir, "project.gns3"))
                        is_gns3_topo = True

                if is_gns3_topo:
                    snapshot_arc = os.path.join(new_snapshots_dir, snapshot + ".gns3project")
                    with zipfile.ZipFile(snapshot_arc, "w", allowZip64=True) as myzip:
                        for root, dirs, files in os.walk(snapshot_dir):
                            for file in files:
                                myzip.write(
                                    os.path.join(root, file),
                                    os.path.relpath(os.path.join(root, file), snapshot_dir),
                                    compress_type=zipfile.ZIP_DEFLATED,
                                )

        shutil.rmtree(old_snapshots_dir)


def _convert_qemu_node(node, old_node):
    """
    Convert qemu node from 1.X to 2.0
    """

    # In 2.0 the internet VM is replaced by the NAT node
    if old_node.get("properties", {}).get("hda_disk_image_md5sum") == "8ebc5a6ec53a1c05b7aa101b5ceefe31":
        node["console"] = None
        node["console_type"] = None
        node["node_type"] = "nat"
        del old_node["properties"]
        node["properties"] = {"ports": [{"interface": "eth1", "name": "nat0", "port_number": 0, "type": "ethernet"}]}
        if node["symbol"] is None:
            node["symbol"] = ":/symbols/cloud.svg"
        return node

    node["node_type"] = "qemu"
    if node["symbol"] is None:
        node["symbol"] = ":/symbols/qemu_guest.svg"
    return node

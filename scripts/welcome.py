#!/usr/bin/env python3
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

import locale
import re
import os
import sys
import time
import subprocess
import configparser
from json import loads as convert
import urllib.request
from dialog import Dialog, PythonDialogBug


class Welcome_dialog:
    def __init__(self):
        try:
            locale.setlocale(locale.LC_ALL, '')
        except locale.Error:
            # Not supported via SSH
            pass
        self.display = Dialog(dialog="dialog", autowidgetsize=True)
        if self.gns3_version() is None:
            self.display.set_background_title("GNS3")
        else:
            self.display.set_background_title("GNS3 {}".format(self.gns3_version()))

    def get_ip(self):
        """
        Return the active IP
        """
        #request 'ip addr' data in JSON format from shell
        ip_addr_response = subprocess.run(['ip', '--json', 'addr'],capture_output=True)
        
        #process response, decode and use json.loads to convert the string to a dict
        ip_addr_data = convert(ip_addr_response.stdout.decode("utf-8"))
        
        #search ip_addr_data for the first ip adress that is not under a virtual bridge or loopback interface
        for i in ip_addr_data:
            if ('virbr' in i['ifname']) or ('lo' in i['ifname']):
                continue
            try:
                if 'UP' in i['flags']:
                    ip_addr = i['addr_info'][0]['local']
                    break
            except:
                continue
            ip_addr = None
            
        return ip_addr

    def repair_remote_install(self):
        """
        This method is only called by remote-install.sh during setup to ensure it is setting the same IP as shown by Dialog
        """        
        ip_addr = self.get_ip()
        subprocess.run(["sed", "-i", f"s/host = 0.0.0.0/host = {ip_addr}/", "/etc/gns3/gns3_server.conf"],capture_output=False)
        subprocess.run(["service", "gns3", "stop"],capture_output=False)
        subprocess.run(["service", "gns3", "start"],capture_output=False)


    def get_config(self):
        """
        Read the config
        """
        config = configparser.RawConfigParser()
        path = os.path.expanduser("~/.config/GNS3/gns3_server.conf")
        config.read([path], encoding="utf-8")
        return config


    def write_config(self, config):
        """
        Write the config file
        """

        with open(os.path.expanduser("~/.config/GNS3/gns3_server.conf"), 'w') as f:
            config.write(f)


    def gns3_major_version(self):
        """
        Returns the GNS3 major server version
        """

        version = self.gns3_version()
        if version:
            match = re.search(r"\d+.\d+", version)
            return match.group(0)
        return ""


    def gns3_version(self):
        """
        Return the GNS3 server version
        """
        try:
            return subprocess.check_output(["gns3server", "--version"]).strip().decode()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None


    def gns3vm_version(self):
        """
        Return the GNS3 VM version
        """
        try:
            with open('/home/gns3/.config/GNS3/gns3vm_version') as f:
                return f.read().strip()
        except FileNotFoundError:
            return "Remote Install"


    def mode(self):
        if self.display.yesno("This feature is for testers only. You may break your GNS3 installation. Are you REALLY sure you want to continue?", yes_label="Exit (Safe option)", no_label="Continue") == self.display.OK:
            return
        code, tag = self.display.menu("Select the GNS3 version",
                        choices=[("2.1", "Stable release for this GNS3 VM (RECOMMENDED)"),
                                    ("2.1dev", "Development version for stable release"),
                                    ("2.2", "Latest stable release")])
        self.display.clear()
        if code == Dialog.OK:
            os.makedirs(os.path.expanduser("~/.config/GNS3"), exist_ok=True)
            with open(os.path.expanduser("~/.config/GNS3/gns3_release"), "w+") as f:
                f.write(tag)

            self.update(force=True)


    def get_release(self):
        try:
            with open(os.path.expanduser("~/.config/GNS3/gns3_release")) as f:
                content = f.read()

                # Support old VM versions
                if content == "stable":
                    content = "1.5"
                elif content == "testing":
                    content = "1.5"
                elif content == "unstable":
                    content = "1.5dev"

                return content
        except OSError:
            return "1.5"


    def update(self, force=False):
        if not force:
            if self.display.yesno("It is recommended to ensure all Nodes are shutdown before upgrading. Continue?") != self.display.OK:
                return
        code, option = self.display.menu("Select an option",
                            choices=[("Upgrade GNS3", "Upgrades only the GNS3 pakage and dependences."),
                                    ("Upgrade All", "Upgrades all avaiable packages"),
                                    ("Dist Upgrade", "Upgrades all avaiable packages and the Linux Kernel. Requires a reboot.")])
        if code == Dialog.OK:
            if option == "Upgrade GNS3":
                ret = os.system(
                    "sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys A2E3EF7B \
                    && sudo apt-get update \
                    && sudo apt-get install -y --only-upgrade gns3-server"
                )
            elif option == "Upgrade All":
                ret = os.system(
                    'sudo apt-key adv --refresh-keys --keyserver keyserver.ubuntu.com \
                    && sudo apt-get update \
                    && sudo apt-get upgrade --yes --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"'
                )
            elif option == "Dist Upgrade":
                ret = os.system(
                    'sudo apt-key adv --refresh-keys --keyserver keyserver.ubuntu.com \
                    && sudo apt-get update \
                    && sudo apt-get dist-upgrade --yes --force-yes -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"'
                )
            if ret != 0:
                print("ERROR DURING UPGRADE PROCESS PLEASE TAKE A SCREENSHOT IF YOU NEED SUPPORT")
                time.sleep(15)
                return
            if option == "Dist Upgrade":
                if self.display.yesno("Reboot now?") == self.display.OK:
                    os.system("sudo reboot now")


    def migrate(self):
        """
        Migrate GNS3 VM data.
        """

        code, option = self.display.menu("Select an option",
                            choices=[("Setup", "Configure this VM to send data to another GNS3 VM"),
                                    ("Send", "Send images and projects to another GNS3 VM")])
        self.display.clear()
        if code == Dialog.OK:
            (answer, destination) = self.display.inputbox("What is IP address or hostname of the other GNS3 VM?", init="172.16.1.128")
            if answer != self.display.OK:
                return
            if destination == self.get_ip():
                self.display.msgbox("The destination cannot be the same as this VM IP address ({})".format(destination))
                return
            if option == "Send":
                # first make sure they are no files belonging to root
                os.system("sudo chown -R gns3:gns3 /opt/gns3")
                # then rsync the data
                command = r"rsync -az --progress -e 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i /home/gns3/.ssh/gns3-vm-key' /opt/gns3 gns3@{}:/opt".format(destination)
                ret = os.system('bash -c "{}"'.format(command))
                time.sleep(10)
                if ret != 0:
                    self.display.msgbox("Could not send data to the other GNS3 VM located at {}".format(destination))
                else:
                    self.display.msgbox("Images and projects have been successfully sent to the other GNS3 VM located at {}".format(destination))
            elif option == "Setup":
                script = """
    if [ ! -f ~/.ssh/gns3-vm-key ]
    then
        ssh-keygen -f ~/.ssh/gns3-vm-key -N '' -C gns3@{}
    fi
    ssh-copy-id -i ~/.ssh/gns3-vm-key gns3@{}
    """.format(self.get_ip(), destination)
                ret = os.system('bash -c "{}"'.format(script))
                time.sleep(10)
                if ret != 0:
                    self.display.msgbox("Error while setting up the migrate feature")
                else:
                    self.display.msgbox("Configuration successful, you can now send data to the GNS3 VM located at {} without password".format(destination))


    def shrink_disk(self):

        ret = os.system("lspci | grep -i vmware")
        if ret != 0:
            self.display.msgbox("Shrinking the disk is only supported when running inside VMware")
            return

        if self.display.yesno("Would you like to shrink the VM disk? The VM will reboot at the end of the process. Continue?") != self.display.OK:
            return

        os.system("sudo service gns3 stop")
        os.system("sudo service docker stop")
        os.system("sudo vmware-toolbox-cmd disk shrink /opt")
        os.system("sudo vmware-toolbox-cmd disk shrink /")

        self.display.msgbox("The GNS3 VM will reboot")
        os.execvp("sudo", ['/usr/bin/sudo', "reboot"])

    def vm_information(self):
        """
        Show IP, SSH settings....
        """

        content = "Welcome to GNS3 appliance\n\n"

        version = self.gns3_version()
        if version is None:
            content += "GNS3 is not installed please install it with sudo pip3 install gns3-server. Or download a preinstalled VM.\n\n"
        else:
            content = "GNS3 version: {gns3_version}\nVM version: {gns3vm_version}\nKVM support available: {kvm}\n\n".format(
                gns3vm_version=self.gns3vm_version(),
                gns3_version=version,
                kvm=self.kvm_support())

        ip = self.get_ip()

        if ip:
            content += f"""
IP:     {ip}
Web UI: http://{ip}:3080

To log in using SSH:
ssh gns3@{ip}
Password: gns3

Images and projects are located in /opt/gns3
""".strip()

        else:
            content += "eth0 is not configured. Please manually configure it via the Networking menu."

        content += "\n\nRelease channel: " + self.get_release()

        try:
            self.display.msgbox(content)
        # If it's an scp command or any bugs
        except:
            os.execvp("bash", ['/bin/bash'])


    def check_internet_connectivity(self):
        self.display.pause("Please wait...\n\n")
        try:
            response = urllib.request.urlopen('http://pypi.python.org/', timeout=5)
        except urllib.request.URLError as err:
            self.display.infobox("Can't connect to Internet (pypi.python.org): {}".format(str(err)))
            time.sleep(15)
            return
        self.display.infobox("Connection to Internet: OK")
        time.sleep(2)


    def keyboard_configuration():
        """
        Allow user to change the keyboard layout
        """
        os.system("/usr/bin/sudo dpkg-reconfigure keyboard-configuration")


    def set_security(self):
        config = self.get_config()
        if self.display.yesno("Enable server authentication?") == self.display.OK:
            if not config.has_section("Server"):
                config.add_section("Server")
            config.set("Server", "auth", True)
            (answer, text) = self.display.inputbox("Login?")
            if answer != self.display.OK:
                return
            config.set("Server", "user", text)
            (answer, text) = self.display.passwordbox("Password?")
            if answer != self.display.OK:
                return
            config.set("Server", "password", text)
        else:
            config.set("Server", "auth", False)

        self.write_config(config)


    def log(self):
        os.system("/usr/bin/sudo chmod 755 /var/log/upstart/gns3.log")
        with open("/var/log/upstart/gns3.log") as f:
            try:
                while True:
                    line = f.readline()
                    sys.stdout.write(line)
            except (KeyboardInterrupt, MemoryError):
                return


    def edit_config(self):
        """
        Edit GNS3 configuration file
        """

        major_version = self.gns3_major_version()
        if major_version == "2.2":
            os.system("nano ~/.config/GNS3/{}/gns3_server.conf".format(major_version))
        else:
            os.system("nano ~/.config/GNS3/gns3_server.conf")


    def edit_network(self):
        """
        Edit network configuration file
        """
        if self.display.yesno("The server will reboot at the end of the process. Continue?") != self.display.OK:
            return
        os.system("sudo nano /etc/network/interfaces")
        os.execvp("sudo", ['/usr/bin/sudo', "reboot"])


    def edit_proxy(self):
        """
        Configure proxy settings
        """
        res, http_proxy = self.display.inputbox(text="HTTP proxy string, for example http://<user>:<password>@<proxy>:<port>. Leave empty for no proxy.")
        if res != self.display.OK:
            return
        res, https_proxy = self.display.inputbox(text="HTTPS proxy string, for example http://<user>:<password>@<proxy>:<port>. Leave empty for no proxy.")
        if res != self.display.OK:
            return

        with open('/tmp/00proxy', 'w+') as f:
            f.write('Acquire::http::Proxy "' + http_proxy + '";')
        os.system("sudo mv /tmp/00proxy /etc/apt/apt.conf.d/00proxy")
        os.system("sudo chown root /etc/apt/apt.conf.d/00proxy")
        os.system("sudo chmod 744 /etc/apt/apt.conf.d/00proxy")

        with open('/tmp/proxy.sh', 'w+') as f:
            f.write('export http_proxy="' + http_proxy + '"\n')
            f.write('export https_proxy="' + https_proxy + '"\n')
            f.write('export HTTP_PROXY="' + http_proxy + '"\n')
            f.write('export HTTPS_PROXY="' + https_proxy + '"\n')
        os.system("sudo mv /tmp/proxy.sh /etc/profile.d/proxy.sh")
        os.system("sudo chown root /etc/profile.d/proxy.sh")
        os.system("sudo chmod 744 /etc/profile.d/proxy.sh")
        os.system("sudo cp /etc/profile.d/proxy.sh /etc/default/docker")

        self.display.msgbox("The GNS3 VM will reboot")
        os.execvp("sudo", ['/usr/bin/sudo', "reboot"])


    def kvm_support(self):
        """
        Returns true if KVM is available
        """
        return subprocess.call("kvm-ok") == 0


    def kvm_control(self):
        """
        Check if KVM is correctly configured
        """

        kvm_ok = self.kvm_support()
        config = self.get_config()
        try:
            if config.getboolean("Qemu", "enable_kvm") is True:
                if kvm_ok is False:
                    if self.display.yesno("KVM is not available!\n\nQemu VM will crash!!\n\nThe reason could be unsupported hardware or another virtualization solution is already running.\n\nDisable KVM and get lower performances?") == self.display.OK:
                        config.set("Qemu", "enable_kvm", False)
                        self.write_config(config)
                        os.execvp("sudo", ['/usr/bin/sudo', "reboot"])
            else:
                if kvm_ok is True:
                    if self.display.yesno("KVM is available on your computer.\n\nEnable KVM and get better performances?") == self.display.OK:
                        config.set("Qemu", "enable_kvm", True)
                        self.write_config(config)
                        os.execvp("sudo", ['/usr/bin/sudo', "reboot"])
        except configparser.NoSectionError:
            return


    def display_loop(self):
        try:
            while True:
                code, tag = self.display.menu("GNS3 {}".format(self.gns3_version()),
                                choices=[("Information", "Display VM information"),
                                    ("Upgrade", "Upgrade GNS3"),
                                    ("Migrate", "Migrate data to another GNS3 VM"),
                                    ("Shell", "Open a console"),
                                    ("Security", "Configure authentication"),
                                    ("Keyboard", "Change keyboard layout"),
                                    ("Configure", "Edit server configuration (advanced users ONLY)"),
                                    ("Proxy", "Configure proxy settings"),
                                    ("Networking", "Configure networking settings"),
                                    ("Log", "Show server log"),
                                    ("Test", "Check internet connection"),
                                    ("Shrink", "Shrink the VM disk"),
                                    ("Version", "Select the GNS3 version"),
                                    ("Restore", "Restore the VM (if you have trouble for upgrade)"),
                                    ("Reboot", "Reboot the VM"),
                                    ("Shutdown", "Shutdown the VM")])
                self.display.clear()
                if code == Dialog.OK:
                    if tag == "Shell":
                        print("Type: 'welcome.py' to get back to the dialog menu.")
                        sys.exit(0)
                    elif tag == "Version":
                        self.mode()
                    elif tag == "Restore":
                        os.execvp("sudo", ['/usr/bin/sudo', "/usr/local/bin/gns3restore"])
                    elif tag == "Reboot":
                        os.execvp("sudo", ['/usr/bin/sudo', "reboot"])
                    elif tag == "Shutdown":
                        os.execvp("sudo", ['/usr/bin/sudo', "poweroff"])
                    elif tag == "Upgrade":
                        self.update()
                    elif tag == "Information":
                        self.vm_information()
                    elif tag == "Log":
                        self.log()
                    elif tag == "Migrate":
                        self.migrate()
                    elif tag == "Configure":
                        self.edit_config()
                    elif tag == "Networking":
                        self.edit_network()
                    elif tag == "Security":
                        self.set_security()
                    elif tag == "Keyboard":
                        self.keyboard_configuration()
                    elif tag == "Test":
                        self.check_internet_connectivity()
                    elif tag == "Proxy":
                        self.edit_proxy()
                    elif tag == "Shrink":
                        self.shrink_disk()
        except KeyboardInterrupt:
            sys.exit(0)

if __name__ == "__main__":
    ws = Welcome_dialog()
    ws.vm_information()
    ws.kvm_control()
    ws.display_loop()

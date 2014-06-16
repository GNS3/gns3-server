""" Create a new GNS3 Server Rackspace image with the provided options. """

import argparse
import getpass
import os
import sys
import uuid
from fabric.api import env
from fabric.contrib.files import exists
from github import Github
from novaclient.v1_1 import client
from time import sleep

POLL_SEC = 30
GNS3_REPO = 'gns3/gns3-server'
PLANC_REPO = 'planctechnologies/gns3-server'
OS_AUTH_URL = 'https://identity.api.rackspacecloud.com/v2.0/'
UBUNTU_BASE_ID = '5cc098a5-7286-4b96-b3a2-49f4c4f82537'


def main():
    """
    Get the user options and perform the image creation.

    Creates a new instance, installs the required software, creates an image
    from the instance, and then deletes the instance.

    """

    args = get_cli_args()

    g = Github()

    if args.username:
        username = args.username

    else:
        if 'OS_USERNAME' in os.environ:
            username = os.environ.get('OS_USERNAME')
        else:
            username = raw_input('Enter Rackspace username: ')

    if args.password:
        password = args.password

    else:
        if 'OS_PASSWORD' in os.environ:
            password = os.environ.get('OS_PASSWORD')
        else:
            password = getpass.getpass('Enter Rackspace password: ')

    if args.tenant:
        tenant = args.tenant

    else:
        if 'OS_TENANT_NAME' in os.environ:
            tenant = os.environ.get('OS_TENANT_NAME')
        else:
            tenant = raw_input('Enter Rackspace Tenant ID: ')

    if args.region:
        region = args.region

    else:
        if 'OS_REGION_NAME' in os.environ:
            region = os.environ.get('OS_REGION_NAME')
        else:
            region = raw_input('Enter Rackspace Region Name: ')

    if args.source == 'release':
        # get the list of releases, present them to the user, save the url
        repo = g.get_repo('gns3/gns3-server')
        keyword = "tag"
        i = 1
        branch_opts = {}
        for tag in repo.get_tags():
            branch_opts[i] = tag.name
            i += 1

    elif args.source == 'dev':
        # get the list of dev branches, present them to the user, save the url
        repo = g.get_repo('planctechnologies/gns3-server')
        keyword = "branch"
        i = 1
        branch_opts = {}
        for branch in repo.get_branches():
            branch_opts[i] = branch.name
            i += 1

    prompt_text = "Select a %s" % keyword
    selected_branch = prompt_user_select(branch_opts, prompt_text)

    if args.image_name:
        image_name = args.image_name
    else:
        image_name = "gns3-%s" % (uuid.uuid4().hex[0:4])

    if args.on_boot:
        on_boot = True
    else:
        on_boot = False

    startup_script = create_script(repo.svn_url, selected_branch, on_boot)

    server_name = uuid.uuid4().hex
    instance = create_instance(username, password, tenant, region, server_name,
                               startup_script)

    passwd = uuid.uuid4().hex
    instance.change_password(passwd)
    # wait for the password change to be processed
    sleep(10)

    env.host_string = str(instance.accessIPv4)
    env.user = "root"
    env.password = passwd

    sys.stdout.write("Installing software...")
    sys.stdout.flush()

    while 1:
        if exists('/tmp/gns-install-complete'):
            break

        sleep(20)
        sys.stdout.write(".")
        sys.stdout.flush()

    print("Done.")

    create_image(username, password, tenant, region, instance, image_name)


def prompt_user_select(opts, text="Please select"):
    """ Ask the user to select an option from the provided list. """

    print("%s" % text)
    print("=" * len(text))
    for o in opts:
        print("(%s)\t%s" % (o, opts[o]))

    while 1:
        selected = raw_input("Select: ")
        try:
            return opts[int(selected)]
        except (KeyError, ValueError):
            print("Invalid selection.  Try again")


def create_instance(username, password, tenant, region, server_name, script,
                    auth_url=OS_AUTH_URL):
    """ Create a new instance. """

    sys.stdout.write("Creating instance...")
    sys.stdout.flush()

    nc = client.Client(username, password, tenant, auth_url,
                       region_name=region)
    server = nc.servers.create(server_name, UBUNTU_BASE_ID, 2,
                               config_drive=True, userdata=script)
    server_id = server.id

    while 1:
        server = nc.servers.get(server_id)
        if server.status == 'ACTIVE':
            break

        sleep(20)
        sys.stdout.write(".")
        sys.stdout.flush()

    print "Done."

    return server


def create_script(git_url, git_branch, on_boot):
    """ Create the start-up script. """

    # Consider using jinja or similar if this becomes unwieldly
    script = "#!/bin/bash\n\n"
    script += "export DEBIAN_FRONTEND=noninteractive\n\n"
    script += "apt-get -y update\n"
    script += "apt-get -o Dpkg::Options::=\"--force-confnew\" --force-yes -fuy dist-upgrade\n\n"

    reqs = ["git", "python3-setuptools", "python3-netifaces", "python3-pip"]

    for r in reqs:
        script += "apt-get -y install %s\n" % r

    script += "\n"

    script += "mkdir -p /opt/gns3\n"
    script += "pushd /opt/gns3\n"
    script += "git clone --branch %s %s\n" % (git_branch, git_url)
    script += "cd gns3-server\n"
    script += "pip3 install tornado\n"
    script += "pip3 install pyzmq\n"
    script += "pip3 install jsonschema\n"
    script += "python3 ./setup.py install\n\n"

    if on_boot:
        script += "echo '/usr/local/bin/gns3-server' >> /etc/rc.local\n\n"

    script += "touch /tmp/gns-install-complete\n\n"

    return script


def create_image(username, password, tenant, region, server,
                 image_name, auth_url=OS_AUTH_URL):
    """ Create a Rackspace image based on the server instance. """

    nc = client.Client(username, password, tenant, auth_url,
                       region_name=region)

    sys.stdout.write("Creating image %s..." % image_name)
    sys.stdout.flush()

    server.create_image(image_name)

    while 1:
        server = nc.servers.get(server.id)
        if getattr(server, 'OS-EXT-STS:task_state') is None:
            break

        sleep(20)
        sys.stdout.write(".")
        sys.stdout.flush()

    print("Done.")


def get_cli_args():
    """ Parse the CLI input. """

    parser = argparse.ArgumentParser(
        description='Create a new GNS3 image',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--rackspace_username', dest='username', action='store'
    )
    parser.add_argument(
        '--rackspace_password', dest='password', action='store'
    )
    parser.add_argument(
        '--rackspace_tenant', dest='tenant', action='store'
    )
    parser.add_argument(
        '--rackspace_region', dest='region', action='store'
    )
    parser.add_argument('--source', dest='source', action='store',
                        choices=['release', 'dev'], default='release',
                        help='specify the gns3-server source location')
    parser.add_argument('--branch', dest='branch', action='store',
                        help='specify the branch/tag')
    parser.add_argument('--start-on-boot', dest='on_boot', action='store_true',
                        help='start the GNS3-server when the image boots',
                        default=False)
    parser.add_argument('--image-name', dest='image_name', action='store',
                        help='the name of the image to be created')

    return parser.parse_args()


if __name__ == "__main__":
    main()

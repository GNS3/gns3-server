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
from string import Template
from time import sleep

POLL_SEC = 20
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

    github = Github()

    args = get_cli_args()
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
        repo = github.get_repo(GNS3_REPO)
        keyword = "tag"
        i = 1
        branch_opts = {}
        for tag in repo.get_tags():
            branch_opts[i] = tag.name
            i += 1
    elif args.source == 'dev':
        # get the list of dev branches, present them to the user, save the url
        repo = github.get_repo(PLANC_REPO)
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
        image_name = "gns3-%s-%s-%s" % (args.source, selected_branch,
                                        uuid.uuid4().hex[0:4])

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
    sleep(POLL_SEC)

    env.host_string = str(instance.accessIPv4)
    env.user = "root"
    env.password = passwd

    sys.stdout.write("Installing software...")
    sys.stdout.flush()

    while True:
        if exists('/tmp/gns-install-complete'):
            break

        sleep(POLL_SEC)
        sys.stdout.write(".")
        sys.stdout.flush()

    print("Done.")

    image_id = create_image(username, password, tenant, region, instance,
                            image_name)
    instance.delete()


def prompt_user_select(opts, text="Please select"):
    """ Ask the user to select an option from the provided list. """

    print("%s" % text)
    print("=" * len(text))
    for o in opts:
        print("(%s)\t%s" % (o, opts[o]))

    while True:
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

    while True:
        server = nc.servers.get(server.id)
        if server.status == 'ACTIVE':
            break

        sleep(POLL_SEC)
        sys.stdout.write(".")
        sys.stdout.flush()

    print("Done.")

    return server


def create_script(git_url, git_branch, on_boot):
    """ Create the start-up script. """

    script_template = Template(open('script_template', 'r').read())

    params = {'git_url': git_url, 'git_branch': git_branch, 'rc_local': ''}

    if on_boot:
        params['rc_local'] = "echo '/usr/local/bin/gns3-server' >> /etc/rc.local"

    return script_template.substitute(params)


def create_image(username, password, tenant, region, server,
                 image_name, auth_url=OS_AUTH_URL):
    """ Create a Rackspace image based on the server instance. """

    nc = client.Client(username, password, tenant, auth_url,
                       region_name=region)

    sys.stdout.write("Creating image %s..." % image_name)
    sys.stdout.flush()

    image_id = server.create_image(image_name)

    while True:
        server = nc.servers.get(server.id)
        if getattr(server, 'OS-EXT-STS:task_state') is None:
            break

        sleep(POLL_SEC)
        sys.stdout.write(".")
        sys.stdout.flush()

    print("Done.")

    return image_id


def get_cli_args():
    """ Parse the CLI input. """

    parser = argparse.ArgumentParser(
        description='Create a new GNS3 image',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        '--rackspace_username', dest='username', action='store')
    parser.add_argument(
        '--rackspace_password', dest='password', action='store')
    parser.add_argument(
        '--rackspace_tenant', dest='tenant', action='store')
    parser.add_argument(
        '--rackspace_region', dest='region', action='store')
    parser.add_argument(
        '--source', dest='source', action='store', choices=['release', 'dev'],
        default='release', help='specify the gns3-server source location')
    parser.add_argument(
        '--branch', dest='branch', action='store',
        help='specify the branch/tag')
    parser.add_argument(
        '--start-on-boot', dest='on_boot', action='store_true',
        default=False, help='start the GNS3-server when the image boots')
    parser.add_argument(
        '--image-name', dest='image_name', action='store',
        help='the name of the image to be created')

    return parser.parse_args()


if __name__ == "__main__":
    main()

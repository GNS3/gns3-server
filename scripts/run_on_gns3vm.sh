#!/bin/bash

# This script will push current dev to a GNS3 VM and
# will also start the server in console

SERVER_ADDRESS=$1

if [ "$SERVER_ADDRESS" == "" ]
then
    echo "usage: run_on_gns3vm.sh VM_IP"
    exit 1
fi

ssh gns3@$SERVER_ADDRESS "sudo service gns3 stop"
rsync -avz --exclude==".git/*" --exclude=='docs/*' --exclude="__pycache__" --exclude=='tests/*'  . "gns3@$SERVER_ADDRESS:gns3server"

ssh gns3@$SERVER_ADDRESS "killall python3;cd gns3server;python3 -m gns3server"

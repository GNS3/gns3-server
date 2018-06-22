#!/usr/bin/env bash

rm gns3server/appliances/*
rmdir gns3server/appliances
rm -Rf /tmp/gns3-registry

git clone https://github.com/GNS3/gns3-registry.git /tmp/gns3-registry
mv /tmp/gns3-registry/appliances gns3server/appliances

git add .
git commit -m "Sync appliances"
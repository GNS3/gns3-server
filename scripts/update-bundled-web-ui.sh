#!/bin/bash

#
# Copyright (C) 2018 GNS3 Technologies Inc.
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
# Syncs WebUI with gns3server
#
# For updating with fresh latest repo just type (latest, development version):
# $ ./scripts/update-bundled-web-ui.sh
#
# It's also possible to update with custom repo:
# $ ./scripts/update-bundled-web-ui.sh --repository ../my-custom-web-ui-repo/
# 
# And for proper tag:
# $ ./scripts/update-bundled-web-ui.sh --tag=v2019.1.0-alpha.1
#
set -e

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
GNS3SERVER_DIR=$(realpath "$CURRENT_DIR/..")
REPO_DIR="/tmp/gns3-web-ui"
CUSTOM_REPO=false


for i in "$@"
do
  case $i in
      -r=*|--repository=*)
      REPOSITORY="${i#*=}"
      CUSTOM_REPO=true
      REPO_DIR=$(realpath "$PWD/${REPOSITORY%/}")
      echo "Custom repo dir: $REPO_DIR"
      shift 
      ;;
      -t=*|--tag=*)
      TAG="${i#*=}"
      echo "Using tag: $TAG"
      shift 
      ;;
      *)
            # unknown option
      ;;
  esac
done


echo "Removing: $GNS3SERVER_DIR/gns3server/static/web-ui/*"

rm -rf $GNS3SERVER_DIR/gns3server/static/web-ui/*

echo "Re-create: $GNS3SERVER_DIR/gns3server/static/web-ui"

mkdir -p "$GNS3SERVER_DIR/gns3server/static/web-ui/"

if [ "$CUSTOM_REPO" = false ] ; then
    if [ ! -d /tmp/gns3-web-ui ]; then
        git clone https://github.com/GNS3/gns3-web-ui.git "$REPO_DIR"
    else
      cd "$REPO_DIR"

      git checkout master
      git fetch --tags
      git pull

      if [[ ! -z "$TAG" ]] 
      then
        echo "Switching to tag: ${TAG}"
        git checkout "tags/${TAG}"
      fi

      cd "$CURRENT_DIR"
    fi
fi

echo "Current working dir $REPO_DIR"

cd "$REPO_DIR"

yarn install
yarn ng build --source-map=false --configuration=production --base-href /static/web-ui/

cp -R $REPO_DIR/dist/* "$GNS3SERVER_DIR/gns3server/static/web-ui/"

cd "$GNS3SERVER_DIR"

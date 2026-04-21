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
# With custom GitHub repo and branch:
# $ ./scripts/update-bundled-web-ui.sh --url=https://github.com/USER/repo --branch=develop
#
set -e

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
GNS3SERVER_DIR=$(realpath "$CURRENT_DIR/..")
REPO_DIR="/tmp/gns3-web-ui"
CUSTOM_REPO=false
GITHUB_URL=""
BRANCH=""


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
      -u=*|--url=*)
      GITHUB_URL="${i#*=}"
      echo "GitHub URL: $GITHUB_URL"
      shift
      ;;
      -b=*|--branch=*)
      BRANCH="${i#*=}"
      echo "Branch: $BRANCH"
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

# Determine if we need to clone/fetch from a URL (vs using local repository)
USE_GITHUB_URL=false
if [[ -n "$GITHUB_URL" ]]; then
    USE_GITHUB_URL=true
fi


echo "Removing: $GNS3SERVER_DIR/gns3server/static/web-ui/*"

rm -rf $GNS3SERVER_DIR/gns3server/static/web-ui/*

echo "Re-create: $GNS3SERVER_DIR/gns3server/static/web-ui"

mkdir -p "$GNS3SERVER_DIR/gns3server/static/web-ui/"

if [ "$CUSTOM_REPO" = false ] ; then
    if [ ! -d "$REPO_DIR" ]; then
        if [[ -n "$GITHUB_URL" ]]; then
            git clone "$GITHUB_URL" "$REPO_DIR"
        else
            git clone https://github.com/GNS3/gns3-web-ui.git "$REPO_DIR"
        fi
    fi

    cd "$REPO_DIR"

    if [[ "$USE_GITHUB_URL" = true ]]; then
        git fetch origin
        if [[ -n "$BRANCH" ]]; then
            git checkout "$BRANCH"
            git pull
        else
            git checkout master-3.0
            git pull
        fi
    else
        git checkout master-3.0
        git fetch --tags
        git pull
    fi

    if [[ -n "$TAG" ]]
    then
      echo "Switching to tag: ${TAG}"
      git checkout "tags/${TAG}"
    fi

    cd "$CURRENT_DIR"
fi

echo "Current working dir $REPO_DIR"

cd "$REPO_DIR"

yarn install

yarn ng build --source-map=false --configuration=production --base-href /static/web-ui/

cp -R $REPO_DIR/dist/browser/* "$GNS3SERVER_DIR/gns3server/static/web-ui/"

cd "$GNS3SERVER_DIR"
git add gns3server/static/web-ui/*
if [[ -n "$TAG" ]]
then
  git commit -m "Bundle web-ui ${TAG}"
fi

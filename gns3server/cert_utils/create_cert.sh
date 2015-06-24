#!/bin/bash

# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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

# Bash shell script for generating self-signed certs.
# The certicate is automaticaly put in your GNS3 config

DST_DIR="$HOME/.config/GNS3/ssl"
OLD_DIR=`pwd`

fail_if_error() {
  [ $1 != 0 ] && {
    unset PASSPHRASE
    cd $OLD_DIR
    exit 10
  }
}


mkdir -p $DST_DIR
fail_if_error $?
cd $DST_DIR

SUBJ="/C=CA/ST=Alberta/O=GNS3SELF/localityName=Calgary/commonName=localhost/organizationalUnitName=GNS3Server/emailAddress=gns3cert@gns3.com"

openssl req -nodes -new -x509 -keyout server.key -out server.cert -subj "$SUBJ"

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

# Bash shell script for generating self-signed certs. Run this in a folder, as it
# generates a few files. Large portions of this script were taken from the
# following artcile:
#
# http://usrportage.de/archives/919-Batch-generating-SSL-certificates.html
#
# Additional alterations by: Brad Landers
# Date: 2012-01-27
# https://gist.github.com/bradland/1690807

# Script accepts a single argument, the fqdn for the cert

DST_DIR="$HOME/.config/GNS3Certs/"
OLD_DIR=`pwd`

#GNS3 Server expects to find certs with the default FQDN below. If you create
#different certs you will need to update server.py
DOMAIN="$1"
if [ -z "$DOMAIN" ]; then
  DOMAIN="gns3server.localdomain.com"
fi

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


# Generate a passphrase
export PASSPHRASE=$(head -c 500 /dev/urandom | tr -dc a-z0-9A-Z | head -c 128; echo)

# Certificate details; replace items in angle brackets with your own info
subj="
C=CA
ST=Alberta
O=GNS3
localityName=Calgary
commonName=$DOMAIN
organizationalUnitName=GNS3Server
emailAddress=gns3cert@gns3.com
"

# Generate the server private key
openssl genrsa -aes256 -out $DOMAIN.key -passout env:PASSPHRASE 2048
fail_if_error $?

#openssl rsa -outform der -in $DOMAIN.pem -out $DOMAIN.key -passin env:PASSPHRASE

# Generate the CSR
openssl req \
    -new \
    -batch \
    -subj "$(echo -n "$subj" | tr "\n" "/")" \
    -key $DOMAIN.key \
    -out $DOMAIN.csr \
    -passin env:PASSPHRASE
fail_if_error $?
cp $DOMAIN.key $DOMAIN.key.org
fail_if_error $?

# Strip the password so we don't have to type it every time we restart Apache
openssl rsa -in $DOMAIN.key.org -out $DOMAIN.key -passin env:PASSPHRASE
fail_if_error $?

# Generate the cert (good for 10 years)
openssl x509 -req -days 3650 -in $DOMAIN.csr -signkey $DOMAIN.key -out $DOMAIN.crt
fail_if_error $?

echo "${DST_DIR}${DOMAIN}.key"
echo "${DST_DIR}${DOMAIN}.crt"

cd $OLD_DIR
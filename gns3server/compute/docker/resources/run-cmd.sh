#!/bin/sh
# run docker startup, first arg is new PATH, remainder is command

PATH="$1"
shift
exec "$@"

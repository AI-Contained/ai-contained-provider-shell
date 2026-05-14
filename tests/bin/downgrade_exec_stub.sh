#!/bin/sh
# A mock of the downgrade_exec binary
while [ $# -gt 0 ]; do
    [ "$1" = "--" ] && shift && break
    shift
done
exec "$@"

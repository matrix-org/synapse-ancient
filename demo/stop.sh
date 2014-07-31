#!/bin/bash

set -e

DIR="$( cd "$( dirname "$0" )" && pwd )"

PID_FILE="$DIR/servers.pid"

if [ ! -f $PID_FILE ]; then
    echo "servers.pid does not exist!"
    exit 1
fi

kill `cat "$PID_FILE"`

rm "$PID_FILE"


#!/bin/bash

set -e

DIR="$( cd "$( dirname "$0" )" && pwd )"

PID_FILE="$DIR/servers.pid"

if [ ! -f $PID_FILE ]; then
    echo "servers.pid does not exist!"
    exit 1
fi

pids=`cat "$PID_FILE" | tr "\n" " "`

echo "Killing: $pids"

kill $pids

rm "$PID_FILE"


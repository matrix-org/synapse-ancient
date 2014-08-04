#!/bin/bash

set -e

DIR="$( cd "$( dirname "$0" )" && pwd )"

PID_FILE="$DIR/servers.pid"

if [ -f $PID_FILE ]; then
    echo "servers.pid already exists!"
    exit 1
fi

for port in "8080" "8081" "8082"; do
    echo -n "Starting server on port $port... "

    synapse-homeserver \
        -p "$port" \
        -H "localhost:$port" \
        -f "$DIR/$port.log" \
        -d "$DIR/$port.db" \
        -vv \
        > /dev/null 2>&1 & disown

    echo "$!" >> "$PID_FILE"

    echo "Started."
done

echo -n "Starting webclient on port 8000..."
(cd "$DIR" && cd "../webclient/" && python -m SimpleHTTPServer > /dev/null 2>&1 & disown)
echo "$!" >> "$PID_FILE"
echo "Started."

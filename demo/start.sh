#!/bin/bash

set -e

DIR="$( cd "$( dirname "$0" )" && pwd )"

PID_FILE="$DIR/servers.pid"

if [ -f $PID_FILE ]; then
    echo "servers.pid already exists!"
    exit 1
fi

declare -A colours


colours[red]=8080
colours[blue]=8081
colours[green]=8082

for colour in "${!colours[@]}"; do
    port="${colours[$colour]}"

    echo -n "Starting $colour on port $port... "

    synapse-homeserver \
        -p "$port" \
        -H "$colour" \
        -f "$DIR/$colour.log" \
        -d "$DIR/$colour.db" \
        -vv \
        & disown > /dev/null

    echo "$!" >> "$PID_FILE"

    echo "Started."
done
#!/bin/bash
# MongoDB initialisation script.
# This script is automatically executed by the official MongoDB Docker image
# when it is placed inside /docker-entrypoint-initdb.d/.
#
# It reads imports.txt (same directory) and runs mongoimport for each entry.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

while IFS= read -r line; do
    # Skip comments and blank lines
    if echo "$line" | grep -qE '^\s*#|^\s*$'; then
        continue
    fi

    db=$(echo "$line" | cut -d ";" -f 1)
    collection=$(echo "$line" | cut -d ";" -f 2)
    file=$(echo "$line" | cut -d ";" -f 3)
    json_array=$(echo "$line" | cut -d ";" -f 4)

    options=""
    if [ "$json_array" = "true" ]; then
        options="$options --jsonArray"
    fi

    echo "Importing $file into $db.$collection ..."
    mongoimport --db "$db" --collection "$collection" --file "$file" $options
done < "$SCRIPT_DIR/imports.txt"

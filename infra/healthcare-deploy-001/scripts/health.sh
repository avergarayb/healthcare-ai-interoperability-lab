#!/bin/sh
set -eu
. "$(CDPATH= cd -- "$(dirname "$0")" && pwd)/lib.sh"
compose ps --format json | while IFS= read -r line; do
  name=$(printf '%s' "$line" | sed -n 's/.*"Name":"\([^"]*\)".*/\1/p')
  health=$(printf '%s' "$line" | sed -n 's/.*"Health":"\([^"]*\)".*/\1/p')
  state=$(printf '%s' "$line" | sed -n 's/.*"State":"\([^"]*\)".*/\1/p')
  if [ -n "$name" ]; then
    echo "service=$name state=${state:-unknown} health=${health:-none}"
  fi
done

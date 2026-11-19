#!/bin/sh
set -eu
. "$(CDPATH= cd -- "$(dirname "$0")" && pwd)/lib.sh"
compose stop
echo "stop=containers_stopped volumes=kept"

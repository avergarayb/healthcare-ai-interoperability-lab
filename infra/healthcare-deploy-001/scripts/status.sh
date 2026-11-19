#!/bin/sh
set -eu
. "$(CDPATH= cd -- "$(dirname "$0")" && pwd)/lib.sh"
echo "profile=$DEPLOY_PROFILE"
compose ps

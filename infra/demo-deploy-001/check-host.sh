#!/bin/sh
set -eu
docker version >/dev/null
docker compose version
echo "docker=present"
if [ -r /proc/meminfo ]; then
  mem=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
  echo "mem_kib=$mem"
  df -Pk / | awk 'NR==2 {print "disk_kb="$2" used_kb="$3}'
else
  echo "host_gate=skipped_not_linux"
fi
echo "firewall=not_changed"
echo "ssh=not_changed"

#!/bin/sh
set -eu
. "$(CDPATH= cd -- "$(dirname "$0")" && pwd)/lib.sh"
"$here/prepare.sh" >/dev/null

echo "verify=compose_config profile=$DEPLOY_PROFILE"
compose config >/dev/null

published=$(compose config | awk '
  /published:/ {pub=$2}
  /host_ip:/ {print pub, $2}
')
if [ -z "$published" ]; then
  echo "verify=FAIL reason=no_published_ports" >&2
  exit 1
fi
printf '%s\n' "$published" | while IFS= read -r row; do
  [ -n "$row" ] || continue
  case "$row" in
    *"127.0.0.1") ;;
    *) echo "verify=FAIL reason=published_port_not_loopback row=$row" >&2; exit 1 ;;
  esac
done
if compose config | grep -E 'published: "(5432|2575|2576|8081|8090|8095|8096)"' >/dev/null; then
  echo "verify=FAIL reason=internal_port_published" >&2
  exit 1
fi

echo "verify=egress_internal_network"
net="hc-deploy-egress-$$"
docker network create --internal "$net" >/dev/null
docker run -d --name "$net-ok" --network "$net" python:3.13-slim python -c "import socket; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(('0.0.0.0', 8080)); s.listen(8); s.accept()" >/dev/null
cleanup_net() {
  docker rm -f "$net-ok" >/dev/null 2>&1 || true
  docker network rm "$net" >/dev/null 2>&1 || true
}
trap cleanup_net EXIT
i=0
internal=FAIL
while [ "$i" -lt 20 ]; do
  if docker run --rm --network "$net" python:3.13-slim python -c "import socket; socket.create_connection(('$net-ok', 8080), 2).close()" >/dev/null 2>&1; then
    internal=PASS
    break
  fi
  i=$((i + 1))
  sleep 1
done
external=FAIL
if docker run --rm --network "$net" python:3.13-slim python -c "import socket; socket.create_connection(('1.1.1.1', 443), 3).close()" >/dev/null 2>&1; then
  external=PASS
fi
cleanup_net
trap - EXIT
if [ "$internal" != "PASS" ] || [ "$external" != "FAIL" ]; then
  echo "verify=FAIL internal=$internal external_reached=$external" >&2
  exit 1
fi
echo "verify=PASS ports=loopback egress_external=blocked egress_internal=allowed"
echo "verify=BLOCKED linux_vm=absent wsl_ubuntu=absent browser_e2e=not_run"

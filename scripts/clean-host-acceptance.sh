#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/alica-d2
INSTALL_ROOT="$ROOT/install"
TOOLS="$GITHUB_WORKSPACE/.acceptance-tools"
EVIDENCE="$GITHUB_WORKSPACE/acceptance-evidence"
NETWORK=alica-d2-clean-host
DIND=alica-d2-dind
CONTROL=alica-d2-debian13
HTTP_PORT=80
HTTPS_PORT=443

cleanup() {
  docker rm -f "$CONTROL" >/dev/null 2>&1 || true
  docker rm -f "$DIND" >/dev/null 2>&1 || true
  docker network rm "$NETWORK" >/dev/null 2>&1 || true
  sudo umount "$ROOT" >/dev/null 2>&1 || true
  sudo rm -f /tmp/alica-d2-clean-host.img
  rm -rf "$TOOLS"
}
trap cleanup EXIT

rm -rf "$TOOLS" "$EVIDENCE"
mkdir -p "$TOOLS/root/.docker/cli-plugins" "$EVIDENCE"

curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-28.4.0.tgz \
  | tar -xz -C "$TOOLS"
cp "$TOOLS/docker/docker" "$TOOLS/docker-cli"
chmod 0755 "$TOOLS/docker-cli"
curl -fsSL \
  https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-x86_64 \
  -o "$TOOLS/root/.docker/cli-plugins/docker-compose"
chmod 0755 "$TOOLS/root/.docker/cli-plugins/docker-compose"

sudo truncate -s 120G /tmp/alica-d2-clean-host.img
sudo mkfs.ext4 -q -F /tmp/alica-d2-clean-host.img
sudo mkdir -p "$ROOT"
sudo mount -o loop /tmp/alica-d2-clean-host.img "$ROOT"
sudo chmod 0777 "$ROOT"

docker network create "$NETWORK" >/dev/null
docker run -d --privileged \
  --name "$DIND" \
  --network "$NETWORK" \
  -e DOCKER_TLS_CERTDIR= \
  -v "$ROOT:$ROOT" \
  docker:28.4-dind \
  --host=tcp://0.0.0.0:2375 >/dev/null

for _ in $(seq 1 60); do
  if docker exec "$DIND" docker info >/dev/null 2>&1; then break; fi
  sleep 2
done
docker exec "$DIND" docker info >/dev/null

cat > "$TOOLS/Dockerfile.debian13" <<'EOF'
FROM debian:13-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends ca-certificates systemd python3 >/dev/null \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
STOPSIGNAL SIGRTMIN+3
CMD ["/lib/systemd/systemd"]
EOF
docker build -q -t alica-d2-debian13-systemd -f "$TOOLS/Dockerfile.debian13" "$TOOLS" >/dev/null
docker run -d --privileged --cgroupns=private \
  --name "$CONTROL" \
  --network "$NETWORK" \
  --tmpfs /run --tmpfs /run/lock \
  -e DOCKER_HOST=tcp://alica-d2-dind:2375 \
  -v "$GITHUB_WORKSPACE/release/d2-candidate:/bundle:ro" \
  -v "$TOOLS/docker-cli:/usr/local/bin/docker:ro" \
  -v "$TOOLS/root/.docker/cli-plugins/docker-compose:/usr/local/lib/docker/cli-plugins/docker-compose:ro" \
  -v "$ROOT:$ROOT" \
  alica-d2-debian13-systemd >/dev/null
for _ in $(seq 1 60); do
  if docker exec "$CONTROL" systemctl is-system-running >/dev/null 2>&1; then break; fi
  state=$(docker exec "$CONTROL" systemctl is-system-running 2>/dev/null || true)
  if [ "$state" = degraded ]; then break; fi
  sleep 2
done
docker exec "$CONTROL" sh -c 'test "$(cat /proc/1/comm)" = systemd'

run_debian() {
  docker exec "$CONTROL" bash -lc "$1"
}

INSTALL='/bundle/alicactl install --manifest /bundle/manifest.json --signature /bundle/manifest.signature.json --public-key /bundle/public-key.json --request /bundle/install-request.json --json'

run_debian "printf 'OS='; . /etc/os-release; printf '%s-%s\\n' \"\$ID\" \"\$VERSION_ID\"; uname -m; nproc; python3 -c 'import os; print(os.sysconf(\"SC_PAGE_SIZE\")*os.sysconf(\"SC_PHYS_PAGES\"))'; df -B1 '$ROOT'; docker version --format '{{.Server.Version}}'; docker compose version --short; cat /proc/1/comm" \
  > "$EVIDENCE/clean-host-facts.txt"

run_debian "$INSTALL" | tee "$EVIDENCE/install-result.json"
run_debian "$INSTALL" | tee "$EVIDENCE/noop-result.json"
run_debian "python3 -c 'import pathlib; print(next(pathlib.Path(\"$INSTALL_ROOT\").rglob(\"compose.yaml\")).read_text(), end=\"\")'" | tee "$EVIDENCE/compose.yaml"

DIND_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$DIND")
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 ps --format '{{.Names}}|{{.Ports}}' | tee "$EVIDENCE/published-ports.txt"
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 run --rm --network host curlimages/curl:8.16.0 \
  -ksS -o /dev/null -w '%{http_code}\n' "https://localhost:$HTTPS_PORT/" \
  > "$EVIDENCE/https-status.txt"
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 run --rm --network host curlimages/curl:8.16.0 \
  -sS -H 'Host: localhost' -o /dev/null -w '%{http_code} %{redirect_url}\n' \
  "http://localhost:$HTTP_PORT/" > "$EVIDENCE/http-redirect.txt"

"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 ps \
  --filter label=com.docker.compose.project=alica-d2-public-clean-host \
  --format '{{.Names}}|{{.Status}}|{{.Image}}' | sort > "$EVIDENCE/containers.txt"
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 inspect \
  $("$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 ps -q --filter label=com.docker.compose.project=alica-d2-public-clean-host) \
  --format '{{.Name}}{{range .Mounts}}{{if eq .Type "bind"}}|{{.Source}}{{end}}{{end}}' | sort > "$EVIDENCE/mounts.txt"

run_debian "python3 -c 'import pathlib; print(next(pathlib.Path(\"$INSTALL_ROOT\").rglob(\"operation-journal.json\")).read_text(), end=\"\")'" > "$EVIDENCE/operation-journal.json"
run_debian "python3 -c 'import pathlib; print(next(pathlib.Path(\"$INSTALL_ROOT\").rglob(\"cell-declaration.json\")).read_text(), end=\"\")'" > "$EVIDENCE/cell-declaration.json"

python3 - "$EVIDENCE" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1])
install=json.loads((p/'install-result.json').read_text())
noop=json.loads((p/'noop-result.json').read_text())
containers=(p/'containers.txt').read_text().splitlines()
mounts=(p/'mounts.txt').read_text().splitlines()
assert install['status']=='PASS' and install['changed'] is True
assert noop['status']=='PASS' and noop['changed'] is False and noop['mutationPerformed'] is False
assert len(containers)==8 and all('(healthy)' in x for x in containers)
assert (p/'https-status.txt').read_text().strip()=='200'
assert (p/'http-redirect.txt').read_text().split()[0]=='301'
assert mounts and all('.release-staging-' not in x for x in mounts)
assert all(('/mnt/alica-d2/install/release/' in x) or ('|' not in x) for x in mounts)
j=json.loads((p/'operation-journal.json').read_text())
assert j['entries'][-1]['phase']=='accepted' and j['entries'][-1]['result']=='succeeded'
summary={
 'status':'PASS', 'anonymousRegistryAuthentication':False,
 'runtimeServices':len(containers), 'allHealthy':True,
 'httpsStatus':200, 'httpStatus':301,
 'noopChanged':False, 'stableReleaseMounts':True,
 'journalTerminal':'accepted/succeeded'
}
(p/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
PY

# The daemon began with no registry credential configuration. Every GHCR image was
# therefore resolved and pulled anonymously by this fresh isolated daemon.
docker exec "$DIND" test ! -e /root/.docker/config.json
printf 'anonymous GHCR pulls: PASS\n' > "$EVIDENCE/anonymous-pull.txt"

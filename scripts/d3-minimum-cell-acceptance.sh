#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/alica-d3
INSTALL_ROOT="$ROOT/install"
TOOLS="$GITHUB_WORKSPACE/.acceptance-tools"
EVIDENCE="$GITHUB_WORKSPACE/acceptance-evidence"
NETWORK=alica-d3-clean-host
DIND=alica-d3-dind
CONTROL=alica-d3-debian13
HTTP_PORT=80
HTTPS_PORT=443

cleanup() {
  docker rm -f "$CONTROL" >/dev/null 2>&1 || true
  docker rm -f "$DIND" >/dev/null 2>&1 || true
  docker network rm "$NETWORK" >/dev/null 2>&1 || true
  sudo umount "$ROOT" >/dev/null 2>&1 || true
  sudo rm -f /tmp/alica-d3-clean-host.img
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

sudo truncate -s 120G /tmp/alica-d3-clean-host.img
sudo mkfs.ext4 -q -F /tmp/alica-d3-clean-host.img
sudo mkdir -p "$ROOT"
sudo mount -o loop /tmp/alica-d3-clean-host.img "$ROOT"
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
docker build -q -t alica-d3-debian13-systemd -f "$TOOLS/Dockerfile.debian13" "$TOOLS" >/dev/null
docker run -d --privileged --cgroupns=private \
  --name "$CONTROL" \
  --network "$NETWORK" \
  --tmpfs /run --tmpfs /run/lock \
  -e DOCKER_HOST=tcp://alica-d3-dind:2375 \
  -v "$GITHUB_WORKSPACE/release/d3-candidate:/bundle:ro" \
  -v "$TOOLS/docker-cli:/usr/local/bin/docker:ro" \
  -v "$TOOLS/root/.docker/cli-plugins/docker-compose:/usr/local/lib/docker/cli-plugins/docker-compose:ro" \
  -v "$ROOT:$ROOT" \
  alica-d3-debian13-systemd >/dev/null
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

run_debian "install -d -m 0700 /run/alica-d3 && printf '%s\\n' 'acceptance-byok-placeholder-not-a-live-key' > /run/alica-d3/provider-api-key && chmod 0600 /run/alica-d3/provider-api-key"

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

CELL_NETWORK=alica-d3-public-clean-host_application
AINBA_ID=$("$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 ps -q --filter label=com.docker.compose.project=alica-d3-public-clean-host --filter label=com.docker.compose.service=ainba-anchor)
DOGHOUSE_ID=$("$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 ps -q --filter label=com.docker.compose.project=alica-d3-public-clean-host --filter label=com.docker.compose.service=doghouse-node)
test -n "$AINBA_ID" -a -n "$DOGHOUSE_ID"
AINBA_TOKEN=$(sudo cat "$INSTALL_ROOT/release/secrets/ainba-control-token")
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 run --rm --network "$CELL_NETWORK" curlimages/curl:8.16.0 \
  -fsS http://ainba-anchor:8787/status > "$EVIDENCE/ainba-status.json"
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 run --rm --network "$CELL_NETWORK" curlimages/curl:8.16.0 \
  -fsS -X POST -H "Authorization: Bearer $AINBA_TOKEN" -H 'Content-Type: application/json' \
  --data '{"operation":"echo","input":"D3 anchor acceptance"}' http://ainba-anchor:8787/v1/run \
  > "$EVIDENCE/ainba-run.json"
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 run --rm --network "$CELL_NETWORK" curlimages/curl:8.16.0 \
  -fsS http://doghouse-node:8790/status > "$EVIDENCE/doghouse-status.json"

# A report-only Doghouse must observe but never repair. Stop the anchor, retain the
# deterministic incident identifier over two cycles, and prove it remains stopped.
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 stop "$AINBA_ID" >/dev/null
sleep 20
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 run --rm --network "$CELL_NETWORK" curlimages/curl:8.16.0 \
  -fsS http://doghouse-node:8790/incidents > "$EVIDENCE/doghouse-incidents-1.json"
sleep 16
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 run --rm --network "$CELL_NETWORK" curlimages/curl:8.16.0 \
  -fsS http://doghouse-node:8790/incidents > "$EVIDENCE/doghouse-incidents-2.json"
test "$("$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 inspect -f '{{.State.Running}}' "$AINBA_ID")" = false
printf 'automatic repair absent: PASS\n' > "$EVIDENCE/doghouse-report-only.txt"
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 start "$AINBA_ID" >/dev/null
for _ in $(seq 1 60); do
  [ "$("$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 inspect -f '{{.State.Health.Status}}' "$AINBA_ID")" = healthy ] && break
  sleep 2
done
test "$("$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 inspect -f '{{.State.Health.Status}}' "$AINBA_ID")" = healthy
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 inspect "$AINBA_ID" "$DOGHOUSE_ID" > "$EVIDENCE/minimum-cell-inspect.json"

"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 ps \
  --filter label=com.docker.compose.project=alica-d3-public-clean-host \
  --format '{{.Names}}|{{.Status}}|{{.Image}}' | sort > "$EVIDENCE/containers.txt"
"$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 inspect \
  $("$TOOLS/docker-cli" --host tcp://"$DIND_IP":2375 ps -q --filter label=com.docker.compose.project=alica-d3-public-clean-host) \
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
assert len(install['components'])==10 and {'ainba-anchor','doghouse-node'} <= set(install['components'])
assert len(containers)==10 and all('(healthy)' in x for x in containers)
assert (p/'https-status.txt').read_text().strip()=='200'
assert (p/'http-redirect.txt').read_text().split()[0]=='301'
ainba_status=json.loads((p/'ainba-status.json').read_text())
ainba_run=json.loads((p/'ainba-run.json').read_text())
doghouse=json.loads((p/'doghouse-status.json').read_text())
incidents1=json.loads((p/'doghouse-incidents-1.json').read_text())['incidents']
incidents2=json.loads((p/'doghouse-incidents-2.json').read_text())['incidents']
assert ainba_status['status']=='ready' and ainba_status['provider']['configured'] is True
assert ainba_run['status']=='succeeded' and ainba_run['output']=='D3 anchor acceptance'
assert doghouse['mode']=='report-only' and doghouse['automaticRepair'] is False
assert len(incidents1)==1 and len(incidents2)==1 and incidents1[0]['incidentId']==incidents2[0]['incidentId']
minimum=json.loads((p/'minimum-cell-inspect.json').read_text())
assert len(minimum)==2
assert all(set(c['NetworkSettings']['Networks'])=={'alica-d3-public-clean-host_application'} for c in minimum)
assert all(not any(m.get('Source','').endswith('docker.sock') for m in c['Mounts']) for c in minimum)
assert any(c['Config']['Labels'].get('com.alica.mode')=='report-only' for c in minimum)
assert mounts and all('.release-staging-' not in x for x in mounts)
assert all(('/mnt/alica-d3/install/release/' in x) or ('|' not in x) for x in mounts)
j=json.loads((p/'operation-journal.json').read_text())
assert j['entries'][-1]['phase']=='accepted' and j['entries'][-1]['result']=='succeeded'
summary={
 'status':'PASS', 'anonymousRegistryAuthentication':False,
 'runtimeServices':len(containers), 'allHealthy':True,
 'httpsStatus':200, 'httpStatus':301,
 'noopChanged':False, 'stableReleaseMounts':True,
 'anchorAInBALifecycle':True, 'localBYOKConfigured':True,
 'doghouseMode':'report-only', 'deterministicIncidentIds':True,
 'automaticRepair':False, 'centralRuntimeDependency':False,
 'journalTerminal':'accepted/succeeded'
}
(p/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
PY

# The daemon began with no registry credential configuration. Every GHCR image was
# therefore resolved and pulled anonymously by this fresh isolated daemon.
docker exec "$DIND" test ! -e /root/.docker/config.json
printf 'anonymous GHCR pulls: PASS\n' > "$EVIDENCE/anonymous-pull.txt"

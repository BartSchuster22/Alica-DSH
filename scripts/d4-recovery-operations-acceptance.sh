#!/usr/bin/env bash
set -euo pipefail

ROOT=/mnt/alica-d4
INSTALL_ROOT="$ROOT/install"
REPOSITORY="$ROOT/repository"
OBJECTS="$ROOT/off-host-object-store"
SECRETS="$ROOT/secrets"
TOOLS="$GITHUB_WORKSPACE/.acceptance-tools-d4"
EVIDENCE="$GITHUB_WORKSPACE/acceptance-evidence-d4"
NETWORK=alica-d4-clean-host
DIND=alica-d4-dind
CONTROL=alica-d4-debian13
PROJECT=alica-d4-public-clean-host

cleanup() {
  docker rm -f "$CONTROL" >/dev/null 2>&1 || true
  docker rm -f "$DIND" >/dev/null 2>&1 || true
  docker network rm "$NETWORK" >/dev/null 2>&1 || true
  sudo umount "$ROOT" >/dev/null 2>&1 || true
  sudo rm -f /tmp/alica-d4-clean-host.img
  rm -rf "$TOOLS"
}
on_error() {
  status=$?; set +e; mkdir -p "$EVIDENCE"
  printf 'exit=%s line=%s command=%s\n' "$status" "${BASH_LINENO[0]:-unknown}" "${BASH_COMMAND:-unknown}" > "$EVIDENCE/failure.txt"
  docker exec "$DIND" docker ps -a --format '{{.Names}}|{{.Status}}|{{.Image}}' > "$EVIDENCE/failure-containers.txt" 2>&1
  docker exec "$CONTROL" journalctl --no-pager -n 300 > "$EVIDENCE/failure-systemd.log" 2>&1
  exit "$status"
}
trap on_error ERR
trap cleanup EXIT
rm -rf "$TOOLS" "$EVIDENCE"; mkdir -p "$TOOLS/root/.docker/cli-plugins" "$EVIDENCE"

curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-28.4.0.tgz | tar -xz -C "$TOOLS"
cp "$TOOLS/docker/docker" "$TOOLS/docker-cli"; chmod 0755 "$TOOLS/docker-cli"
curl -fsSL https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-x86_64 -o "$TOOLS/root/.docker/cli-plugins/docker-compose"
chmod 0755 "$TOOLS/root/.docker/cli-plugins/docker-compose"
sudo truncate -s 120G /tmp/alica-d4-clean-host.img; sudo mkfs.ext4 -q -F /tmp/alica-d4-clean-host.img
sudo mkdir -p "$ROOT"; sudo mount -o loop /tmp/alica-d4-clean-host.img "$ROOT"; sudo chmod 0777 "$ROOT"
mkdir -p "$ROOT/docker-data" "$OBJECTS" "$SECRETS"; chmod 0700 "$OBJECTS" "$SECRETS"
for pair in 'backup-key:d4-encryption-key-0123456789abcdef' 's3-access-key:ALICAD4ACCESSKEY1234' 's3-secret-key:d4-secret-access-key-0123456789abcdef' 'provider-api-key:acceptance-byok-placeholder-not-a-live-key'; do
  name=${pair%%:*}; value=${pair#*:}; printf '%s\n' "$value" > "$SECRETS/$name"; chmod 0600 "$SECRETS/$name"
done

docker network create "$NETWORK" >/dev/null
docker run -d --privileged --name "$DIND" --network "$NETWORK" --network-alias alica-d4.localhost -e DOCKER_TLS_CERTDIR= \
  -v "$ROOT:$ROOT" -v "$ROOT/docker-data:/var/lib/docker" docker:28.4-dind --host=tcp://0.0.0.0:2375 >/dev/null
for _ in $(seq 1 60); do docker exec "$DIND" docker info >/dev/null 2>&1 && break; sleep 2; done
docker exec "$DIND" docker info >/dev/null
# Pull every signed runtime artifact before entering alicactl's bounded install
# transaction, so registry latency cannot consume the transactional timeout.
while IFS= read -r image; do
  docker exec "$DIND" docker pull "$image" >/dev/null
done < <(python3 - <<'PY'
import json
manifest=json.load(open('release/d4-candidate/manifest.json'))
print('\n'.join(sorted({c['artifact'][6:].split('@sha256:')[0]+'@sha256:'+c['artifact'].split('@sha256:')[1] for c in manifest['components'] if c['artifact'].startswith('oci://')})))
PY
)
cat > "$TOOLS/Dockerfile.debian13" <<'EOF'
FROM debian:13-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends ca-certificates systemd python3 >/dev/null && apt-get clean && rm -rf /var/lib/apt/lists/*
STOPSIGNAL SIGRTMIN+3
CMD ["/lib/systemd/systemd"]
EOF
docker build -q -t alica-d4-debian13-systemd -f "$TOOLS/Dockerfile.debian13" "$TOOLS" >/dev/null
docker run -d --privileged --cgroupns=private --name "$CONTROL" --network "$NETWORK" --tmpfs /run --tmpfs /run/lock \
  -e DOCKER_HOST=tcp://alica-d4-dind:2375 -v "$GITHUB_WORKSPACE/release/d4-candidate:/bundle:ro" \
  -v "$GITHUB_WORKSPACE/scripts/d4-s3-alert-mock.py:/usr/local/lib/d4-s3-alert-mock.py:ro" \
  -v "$TOOLS/docker-cli:/usr/local/bin/docker:ro" -v "$TOOLS/root/.docker/cli-plugins/docker-compose:/usr/local/lib/docker/cli-plugins/docker-compose:ro" \
  -v "$ROOT:$ROOT" -v "$ROOT/docker-data:/var/lib/docker" alica-d4-debian13-systemd >/dev/null
for _ in $(seq 1 60); do state=$(docker exec "$CONTROL" systemctl is-system-running 2>/dev/null || true); [ "$state" = running ] || [ "$state" = degraded ] && break; sleep 2; done
docker exec "$CONTROL" sh -c 'test "$(cat /proc/1/comm)" = systemd'
run_debian(){ docker exec "$CONTROL" bash -lc "$1"; }
start_mock(){ run_debian "systemd-run --unit=alica-d4-mock --property=Restart=always /usr/bin/python3 /usr/local/lib/d4-s3-alert-mock.py '$OBJECTS'" >/dev/null; for _ in $(seq 1 30); do run_debian 'python3 -c "import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:9000/missing\")"' >/dev/null 2>&1 || true; run_debian 'systemctl is-active --quiet alica-d4-mock' && break; sleep 1; done; }
start_mock

INSTALL='ALICACTL_INSTALL_TEST_MODE=1 ALICACTL_DOCKER_BIN=/usr/local/bin/docker /bundle/alicactl install --manifest /bundle/manifest.json --signature /bundle/manifest.signature.json --public-key /bundle/public-key.json --request /bundle/install-request.json --json'
run_debian "$INSTALL" | tee "$EVIDENCE/install-result.json"
cat > "$ROOT/recovery-request.json" <<EOF
{
  "schemaVersion":"alica-recovery-operations/v1",
  "cellId":"$(python3 -c 'import json;print(json.load(open("release/d4-candidate/install-request.json"))["cellId"])')",
  "installationRoot":"$INSTALL_ROOT",
  "project":"$PROJECT",
  "encryptionKeyFile":"$SECRETS/backup-key",
  "localRepository":"$REPOSITORY",
  "s3":{"endpoint":"http://127.0.0.1:9000","region":"eu-west-1","bucket":"alica-d4-acceptance","prefix":"cells/public","accessKeyFile":"$SECRETS/s3-access-key","secretAccessKeyFile":"$SECRETS/s3-secret-key"},
  "operations":{"webhookUrl":"http://127.0.0.1:9000/webhook","canaryUrl":"https://alica-d4.localhost/","backupMaxAgeSeconds":90000,"minimumFreeDiskBytes":1,"certificateWarnSeconds":60}
}
EOF
chmod 0600 "$ROOT/recovery-request.json"
RECOVERY='ALICACTL_OPERATIONS_TEST_MODE=1 ALICACTL_OPERATIONS_ACTIVATE_TEST_UNITS=1 ALICACTL_DOCKER_BIN=/usr/local/bin/docker /bundle/alicactl'

# Seed a persistence marker, then create a coordinated encrypted backup and S3-compatible replica.
VOLUME=${PROJECT}_alica-data
run_debian "printf '%s\n' d4-preserved-state > /var/lib/docker/volumes/$VOLUME/_data/d4-marker.txt"
run_debian "$RECOVERY backup --request '$ROOT/recovery-request.json' --json" | tee "$EVIDENCE/backup-result.json"
BACKUP_ID=$(python3 -c 'import json;print(json.load(open("acceptance-evidence-d4/backup-result.json"))["backupId"])')
sudo cp "$REPOSITORY/$BACKUP_ID.manifest.json" "$EVIDENCE/backup-manifest.json"
sudo chown "$(id -u):$(id -g)" "$EVIDENCE/backup-manifest.json"
! sudo grep -a -q 'd4-preserved-state' "$REPOSITORY/$BACKUP_ID.abk"
sudo sha256sum "$REPOSITORY/$BACKUP_ID.abk" > "$EVIDENCE/encrypted-object.sha256"
run_debian "systemctl is-enabled alica-backup.timer alica-canary.timer" > "$EVIDENCE/systemd-enabled.txt"
run_debian "systemctl list-timers --all alica-backup.timer alica-canary.timer --no-pager" > "$EVIDENCE/systemd-timers.txt"
run_debian "$RECOVERY operations-check --request '$ROOT/recovery-request.json' --synthetic-alert --json" | tee "$EVIDENCE/operations-alert.json"
cp "$OBJECTS/webhook-deliveries.jsonl" "$EVIDENCE/webhook-deliveries.jsonl"
run_debian "$RECOVERY restart --request '$ROOT/recovery-request.json' --json" | tee "$EVIDENCE/restart-result.json"

# Reboot both isolated host planes. Docker restart policies and persistent systemd timers must recover.
docker restart "$DIND" >/dev/null; docker restart "$CONTROL" >/dev/null
for _ in $(seq 1 120); do docker exec "$DIND" docker info >/dev/null 2>&1 && [ "$(docker exec "$DIND" docker ps --filter label=com.alica.cell.id --format '{{.Status}}' | grep -c '(healthy)')" -eq 10 ] && break; sleep 2; done
start_mock
run_debian "systemctl is-enabled alica-backup.timer alica-canary.timer" > "$EVIDENCE/systemd-enabled-after-reboot.txt"
run_debian "$RECOVERY operations-check --request '$ROOT/recovery-request.json' --json" | tee "$EVIDENCE/post-reboot-operations.json"

# Destroy every Cell container, named volume and local backup cache, then restore only from off-host objects.
run_debian "systemctl disable --now alica-backup.timer alica-canary.timer >/dev/null"
run_debian "docker compose --env-file '$INSTALL_ROOT/release/compose.env' -f '$INSTALL_ROOT/release/compose.yaml' --project-name '$PROJECT' --profile minimum-cell down -v"
ORIGINAL_IDENTITY=$(sudo sha256sum "$INSTALL_ROOT/accepted/cell-declaration.json" | cut -d' ' -f1)
sudo rm -rf "$INSTALL_ROOT" "$REPOSITORY"
run_debian "$RECOVERY restore --request '$ROOT/recovery-request.json' --backup-id '$BACKUP_ID' --json" | tee "$EVIDENCE/restore-result.json"
test "$(sudo sha256sum "$INSTALL_ROOT/accepted/cell-declaration.json" | cut -d' ' -f1)" = "$ORIGINAL_IDENTITY"
test "$(sudo cat "$ROOT/docker-data/volumes/$VOLUME/_data/d4-marker.txt")" = d4-preserved-state
run_debian "docker compose --env-file '$INSTALL_ROOT/release/compose.env' -f '$INSTALL_ROOT/release/compose.yaml' --project-name '$PROJECT' --profile minimum-cell ps --format json" > "$EVIDENCE/restored-containers.jsonl"
run_debian "$RECOVERY operations-check --request '$ROOT/recovery-request.json' --json" | tee "$EVIDENCE/post-restore-operations.json"
run_debian "systemctl is-enabled alica-backup.timer alica-canary.timer" > "$EVIDENCE/systemd-enabled-after-restore.txt"

python3 - "$EVIDENCE" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); load=lambda n:json.loads((p/n).read_text())
backup=load('backup-result.json');manifest=load('backup-manifest.json');alert=load('operations-alert.json');restart=load('restart-result.json');post_reboot=load('post-reboot-operations.json');restore=load('restore-result.json');post_restore=load('post-restore-operations.json')
assert backup['status']=='PASS' and backup['offHostReplicated'] and backup['services']==10
assert manifest['consistency']=='coordinated-cold' and manifest['encryption']=='aes-256-gcm-chunked/v1' and len(manifest['dataUnits'])==10
assert alert['status']=='ALERT' and alert['alertDelivered'] and alert['syntheticAlert']
assert restart['status']=='PASS' and restart['services']==10
assert post_reboot['status']=='PASS' and all(x['Status']=='PASS' for x in post_reboot['checks'])
assert restore['status']=='PASS' and restore['services']==10 and restore['offHostReplicated']
assert restore['cellId']==backup['cellId'] and restore['releaseId']==backup['releaseId'] and restore['manifestDigest']==backup['manifestDigest']
assert post_restore['status']=='PASS' and all(x['Status']=='PASS' for x in post_restore['checks'])
for n in ['systemd-enabled.txt','systemd-enabled-after-reboot.txt','systemd-enabled-after-restore.txt']:
 assert (p/n).read_text().splitlines()==['enabled','enabled']
summary={'status':'PASS','acceptanceClass':'D4 isolated recovery and operations acceptance','hostResourceContractEvidence':{'phase':'D2','workflowRun':33494819700},'encryptedBackup':True,'s3CompatibleOffHostReplication':True,'isolatedRestoreFromOffHost':True,'cellIdentityPreserved':True,'stateMarkerPreserved':True,'runtimeServices':10,'hostRebootRecovery':True,'restartRecovery':True,'systemdTimersPersistent':True,'operationsChecks':['backup-age','canary','certificate','disk','drift','unhealthy-service'],'webhookAlertDelivered':True,'automaticRepair':False,'rpoSeconds':manifest['rpoSeconds'],'backupBytes':backup['bytes'],'restartRtoMilliseconds':restart['rtoMilliseconds'],'restoreRtoMilliseconds':restore['rtoMilliseconds']}
(p/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
PY

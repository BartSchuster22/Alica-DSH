#!/usr/bin/env bash
set -euo pipefail
ROOT=/mnt/alica-d5
INSTALL_ROOT="$ROOT/install"; REPOSITORY="$ROOT/repository"; OBJECTS="$ROOT/off-host-object-store"; SECRETS="$ROOT/secrets"
TOOLS="$GITHUB_WORKSPACE/.acceptance-tools-d5"; EVIDENCE="$GITHUB_WORKSPACE/acceptance-evidence-d5"
NETWORK=alica-d5-clean-host; DIND=alica-d5-dind; CONTROL=alica-d5-debian13; PROJECT=alica-d5-public-update
cleanup(){ docker rm -f "$CONTROL" >/dev/null 2>&1||true; docker rm -f "$DIND" >/dev/null 2>&1||true; docker network rm "$NETWORK" >/dev/null 2>&1||true; sudo umount "$ROOT" >/dev/null 2>&1||true; sudo rm -f /tmp/alica-d5-clean-host.img; rm -rf "$TOOLS"; }
on_error(){ status=$?;set +e;mkdir -p "$EVIDENCE";printf 'exit=%s line=%s command=%s\n' "$status" "${BASH_LINENO[0]:-unknown}" "${BASH_COMMAND:-unknown}" > "$EVIDENCE/failure.txt";docker exec "$DIND" docker ps -a --format '{{.Names}}|{{.Status}}|{{.Image}}' > "$EVIDENCE/failure-containers.txt" 2>&1;docker exec "$CONTROL" journalctl --no-pager -n 300 > "$EVIDENCE/failure-systemd.log" 2>&1;exit "$status"; }
trap on_error ERR;trap cleanup EXIT
rm -rf "$TOOLS" "$EVIDENCE";mkdir -p "$TOOLS/root/.docker/cli-plugins" "$EVIDENCE"
curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-28.4.0.tgz|tar -xz -C "$TOOLS";cp "$TOOLS/docker/docker" "$TOOLS/docker-cli";chmod 0755 "$TOOLS/docker-cli"
curl -fsSL https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-x86_64 -o "$TOOLS/root/.docker/cli-plugins/docker-compose";chmod 0755 "$TOOLS/root/.docker/cli-plugins/docker-compose"
sudo truncate -s 120G /tmp/alica-d5-clean-host.img;sudo mkfs.ext4 -q -F /tmp/alica-d5-clean-host.img;sudo mkdir -p "$ROOT";sudo mount -o loop /tmp/alica-d5-clean-host.img "$ROOT";sudo chmod 0777 "$ROOT"
mkdir -p "$ROOT/docker-data" "$OBJECTS" "$SECRETS" "$ROOT/requests";chmod 0700 "$OBJECTS" "$SECRETS"
for pair in 'backup-key:d5-encryption-key-0123456789abcdef' 's3-access-key:ALICAD5ACCESSKEY1234' 's3-secret-key:d5-secret-access-key-0123456789abcdef' 'provider-api-key:accept...ey';do name=${pair%%:*};value=${pair#*:};printf '%s\n' "$value">"$SECRETS/$name";chmod 0600 "$SECRETS/$name";done
docker network create "$NETWORK">/dev/null
docker run -d --privileged --name "$DIND" --network "$NETWORK" --network-alias alica-d5.localhost -e DOCKER_TLS_CERTDIR= -v "$ROOT:$ROOT" -v "$ROOT/docker-data:/var/lib/docker" docker:28.4-dind --host=tcp://0.0.0.0:2375 >/dev/null
for _ in $(seq 1 60);do docker exec "$DIND" docker info >/dev/null 2>&1&&break;sleep 2;done;docker exec "$DIND" docker info >/dev/null
while IFS= read -r image;do docker exec "$DIND" docker pull "$image">/dev/null;done < <(python3 -c 'import json; m=json.load(open("release/d4-candidate/manifest.json")); print("\n".join(sorted({c["artifact"][6:].split("@sha256:")[0]+"@sha256:"+c["artifact"].split("@sha256:")[1] for c in m["components"] if c["artifact"].startswith("oci://")})))')
printf '%s\n' 'FROM debian:13-slim' 'ENV DEBIAN_FRONTEND=noninteractive' 'RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends ca-certificates systemd python3 >/dev/null && apt-get clean && rm -rf /var/lib/apt/lists/*' 'STOPSIGNAL SIGRTMIN+3' 'CMD ["/lib/systemd/systemd"]' > "$TOOLS/Dockerfile.debian13"
docker build -q -t alica-d5-debian13-systemd -f "$TOOLS/Dockerfile.debian13" "$TOOLS">/dev/null
docker run -d --privileged --cgroupns=private --name "$CONTROL" --network "$NETWORK" --tmpfs /run --tmpfs /run/lock -e DOCKER_HOST=tcp://alica-d5-dind:2375 -v "$GITHUB_WORKSPACE/release/d4-candidate:/d4:ro" -v "$GITHUB_WORKSPACE/release/d5-candidate:/d5:ro" -v "$GITHUB_WORKSPACE/scripts/d4-s3-alert-mock.py:/usr/local/lib/d4-s3-alert-mock.py:ro" -v "$TOOLS/docker-cli:/usr/local/bin/docker:ro" -v "$TOOLS/root/.docker/cli-plugins/docker-compose:/usr/local/lib/docker/cli-plugins/docker-compose:ro" -v "$ROOT:$ROOT" -v "$ROOT/docker-data:/var/lib/docker" alica-d5-debian13-systemd >/dev/null
for _ in $(seq 1 60);do state=$(docker exec "$CONTROL" systemctl is-system-running 2>/dev/null||true);{ [ "$state" = running ]||[ "$state" = degraded ]; }&&break;sleep 2;done
docker exec "$CONTROL" sh -c 'test "$(cat /proc/1/comm)" = systemd';run_debian(){ docker exec "$CONTROL" bash -lc "$1"; }
run_debian "systemd-run --unit=alica-d5-mock --property=Restart=always /usr/bin/python3 /usr/local/lib/d4-s3-alert-mock.py '$OBJECTS'" >/dev/null
python3 - "$ROOT/requests/install.json" <<'PY'
import json,sys
x=json.load(open('release/d4-candidate/install-request.json'));x.update(installationRoot='/mnt/alica-d5/install',publicHost='alica-d5.localhost',publicOrigin='https://alica-d5.localhost',project='alica-d5-public-update');x['provider']['credentialFile']='/mnt/alica-d5/secrets/provider-api-key';open(sys.argv[1],'w').write(json.dumps(x)+'\n')
PY
run_debian "ALICACTL_INSTALL_TEST_MODE=1 ALICACTL_DOCKER_BIN=/usr/local/bin/docker /d4/alicactl install --manifest /d4/manifest.json --signature /d4/manifest.signature.json --public-key /d4/public-key.json --request '$ROOT/requests/install.json' --json" | tee "$EVIDENCE/d4-install.json"
cat > "$ROOT/requests/recovery.json" <<EOF
{"schemaVersion":"alica-recovery-operations/v1","cellId":"$(python3 -c 'import json;print(json.load(open("release/d4-candidate/install-request.json"))["cellId"])')","installationRoot":"$INSTALL_ROOT","project":"$PROJECT","encryptionKeyFile":"$SECRETS/backup-key","localRepository":"$REPOSITORY","s3":{"endpoint":"http://127.0.0.1:9000","region":"eu-west-1","bucket":"alica-d5-acceptance","prefix":"cells/public","accessKeyFile":"$SECRETS/s3-access-key","secretAccessKeyFile":"$SECRETS/s3-secret-key"},"operations":{"webhookUrl":"http://127.0.0.1:9000/webhook","canaryUrl":"https://alica-d5.localhost/","backupMaxAgeSeconds":90000,"minimumFreeDiskBytes":1,"certificateWarnSeconds":60}}
EOF
chmod 0600 "$ROOT/requests/recovery.json"
python3 - "$ROOT/requests/update.json" <<'PY'
import json,sys
x=json.load(open('release/d5-candidate/update-request.example.json'));x.update(installationRoot='/mnt/alica-d5/install',project='alica-d5-public-update',rootMetadata='/d5/root.json',timestampMetadata='/d5/timestamp.json',snapshotMetadata='/d5/snapshot.json',targetsMetadata='/d5/targets.json',recoveryRequest='/mnt/alica-d5/requests/recovery.json');open(sys.argv[1],'w').write(json.dumps(x)+'\n')
PY
UPDATE='ALICACTL_UPDATE_TEST_MODE=1 ALICACTL_OPERATIONS_TEST_MODE=1 ALICACTL_OPERATIONS_ACTIVATE_TEST_UNITS=1 ALICACTL_DOCKER_BIN=/usr/local/bin/docker /d5/alicactl'
run_debian "$UPDATE update-plan --manifest /d5/manifest.json --signature /d5/manifest.signature.json --public-key /d5/public-key.json --request '$ROOT/requests/update.json'" | tee "$EVIDENCE/update-plan.json"
VOLUME=${PROJECT}_alica-data;run_debian "printf '%s\n' d5-preserved-state > /var/lib/docker/volumes/$VOLUME/_data/d5-marker.txt"
if run_debian "ALICACTL_UPDATE_FAIL_PHASE=activate $UPDATE update --manifest /d5/manifest.json --signature /d5/manifest.signature.json --public-key /d5/public-key.json --request '$ROOT/requests/update.json'" > "$EVIDENCE/injected-failure.log" 2>&1; then
  FAULT_RC=0
else
  FAULT_RC=$?
fi
test "$FAULT_RC" -eq 3;grep -q 'target activation rolled back before acceptance' "$EVIDENCE/injected-failure.log"
sudo python3 -c 'import json; x=json.load(open("/mnt/alica-d5/install/accepted/lifecycle-state.json")); assert x["acceptedCurrent"]["releaseId"]=="rel_01a05d82-be23-7079-a700-13651201b7d2"'
test "$(run_debian "cat /var/lib/docker/volumes/$VOLUME/_data/d5-marker.txt")" = d5-preserved-state
run_debian "$UPDATE update --manifest /d5/manifest.json --signature /d5/manifest.signature.json --public-key /d5/public-key.json --request '$ROOT/requests/update.json'" | tee "$EVIDENCE/update-result.json"
run_debian "docker compose --env-file '$INSTALL_ROOT/release/compose.env' -f '$INSTALL_ROOT/release/compose.yaml' --project-name '$PROJECT' --profile minimum-cell ps --format json" > "$EVIDENCE/containers.jsonl"
sudo cp "$INSTALL_ROOT/accepted/lifecycle-state.json" "$INSTALL_ROOT/accepted/update-state.json" "$INSTALL_ROOT/accepted/operation-journal.json" "$EVIDENCE/";sudo chown "$(id -u):$(id -g)" "$EVIDENCE"/*.json
test "$(run_debian "cat /var/lib/docker/volumes/$VOLUME/_data/d5-marker.txt")" = d5-preserved-state
python3 - "$EVIDENCE" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]);load=lambda n:json.loads((p/n).read_text())
plan=load('update-plan.json');result=load('update-result.json');state=load('lifecycle-state.json');update=load('update-state.json');journal=load('operation-journal.json')
assert plan['status']=='PASS' and not plan['changed'] and not plan['mutationPerformed']
assert result['status']=='PASS' and result['changed'] and result['mutationPerformed'] and result['services']==10 and result['backupId'].startswith('bak_')
assert state['acceptedCurrent']['releaseId']==result['targetReleaseId'] and state['acceptedCurrent']['manifestDigest']==result['targetManifestDigest']
assert update['sourceReleaseId']==plan['sourceReleaseId'] and update['targetReleaseId']==result['targetReleaseId'] and update['backupId']==result['backupId']
assert update['trustVersions']=={'Root':1,'Timestamp':1,'Snapshot':1,'Targets':1}
assert journal['entries'][-1]['kind']=='update' and journal['entries'][-1]['phase']=='accepted' and journal['entries'][-1]['mutationAuthorized']
containers=[json.loads(x) for x in (p/'containers.jsonl').read_text().splitlines() if x.strip()];assert len(containers)==10 and all(x['State']=='running' for x in containers)
summary={'status':'PASS','acceptanceClass':'D5 trusted directional update acceptance','sourceReleaseId':result['sourceReleaseId'],'targetReleaseId':result['targetReleaseId'],'targetManifestDigest':result['targetManifestDigest'],'candidateChannelOnly':True,'manualApprovalRequired':True,'thresholdTrust':{'root':'2/3','targets':'2/3','snapshot':'1/1','timestamp':'1/1'},'exactDirectionalEdge':True,'mandatoryEncryptedOffHostBackup':True,'preAcceptanceAutomaticDefinitionRollback':True,'statePreserved':True,'runtimeServices':10,'atomicAcceptedCurrent':True,'unattendedOrStableUpdate':False,'postAcceptanceCrossReleaseRollback':False,'generalAvailability':False}
(p/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
PY

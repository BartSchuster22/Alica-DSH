#!/usr/bin/env bash
set -euo pipefail
MODE=${D6_MODE:?online or offline};case "$MODE" in online|offline);;*)exit 2;;esac
WORKSPACE=${GITHUB_WORKSPACE:-$PWD};CANDIDATE=${D6_CANDIDATE_DIR:-$WORKSPACE/release/d6-candidate};BUNDLE_ROOT=${D6_BUNDLE_ROOT:-}
ROOT=/mnt/alica-d6-$MODE;INSTALL_ROOT=$ROOT/install;TOOLS=$WORKSPACE/.d6-tools-$MODE;EVIDENCE=$WORKSPACE/acceptance-evidence-d6-$MODE
NETWORK=alica-d6-$MODE;DIND=alica-d6-$MODE-dind;CONTROL=alica-d6-$MODE-debian13;PROJECT=alica-d6-$MODE
cleanup(){ docker rm -f "$CONTROL" "$DIND" >/dev/null 2>&1||true;docker network rm "$NETWORK">/dev/null 2>&1||true;sudo umount "$ROOT">/dev/null 2>&1||true;sudo rm -f /tmp/alica-d6-$MODE.img;rm -rf "$TOOLS"; }
on_error(){ rc=$?;set +e;mkdir -p "$EVIDENCE";printf 'exit=%s line=%s command=%s\n' "$rc" "${BASH_LINENO[0]:-?}" "${BASH_COMMAND:-?}">$EVIDENCE/failure.txt;docker exec "$DIND" docker ps -a >$EVIDENCE/failure-containers.txt 2>&1;exit "$rc"; }
trap on_error ERR;trap cleanup EXIT;rm -rf "$TOOLS" "$EVIDENCE";mkdir -p "$TOOLS/root/.docker/cli-plugins" "$EVIDENCE"
test -x "$CANDIDATE/alicactl";sha256sum "$CANDIDATE"/* > "$EVIDENCE/candidate-sha256.txt"
curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-28.4.0.tgz|tar -xz -C "$TOOLS";cp "$TOOLS/docker/docker" "$TOOLS/docker-cli";chmod 0755 "$TOOLS/docker-cli"
curl -fsSL https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-x86_64 -o "$TOOLS/root/.docker/cli-plugins/docker-compose";chmod 0755 "$TOOLS/root/.docker/cli-plugins/docker-compose"
sudo truncate -s 120G /tmp/alica-d6-$MODE.img;sudo mkfs.ext4 -q -F /tmp/alica-d6-$MODE.img;sudo mkdir -p "$ROOT";sudo mount -o loop /tmp/alica-d6-$MODE.img "$ROOT";sudo chmod 0777 "$ROOT";mkdir -p "$ROOT/docker-data" "$ROOT/secrets" "$ROOT/repository" "$ROOT/off-host" "$ROOT/requests";chmod 0700 "$ROOT/secrets" "$ROOT/off-host"
for pair in 'backup-key:d6-encryption-key-0123456789abcdef' 's3-access-key:ALICAD6ACCESSKEY1234' 's3-secret-key:d6-secret-access-key-0123456789abcdef' 'provider-api-key:*** name=${pair%%:*};printf '%s\n' "${pair#*:}">$ROOT/secrets/$name;chmod 0600 "$ROOT/secrets/$name";done
if [ "$MODE" = offline ];then docker network create --internal "$NETWORK">/dev/null;else docker network create "$NETWORK">/dev/null;fi
docker run -d --privileged --name "$DIND" --network "$NETWORK" --network-alias alica-d6.localhost -e DOCKER_TLS_CERTDIR= -v "$ROOT:$ROOT" -v "$ROOT/docker-data:/var/lib/docker" docker:28.4-dind --host=tcp://0.0.0.0:2375 >/dev/null
for _ in $(seq 1 60);do docker exec "$DIND" docker info>/dev/null 2>&1&&break;sleep 2;done;docker exec "$DIND" docker info>/dev/null
if [ "$MODE" = offline ];then test -n "$BUNDLE_ROOT";test -f "$BUNDLE_ROOT/oci-images.docker-archive.tar";docker exec -i "$DIND" docker load < "$BUNDLE_ROOT/oci-images.docker-archive.tar" > "$EVIDENCE/offline-import.txt";docker exec "$DIND" test ! -e /root/.docker/config.json;else while IFS= read -r image;do docker exec "$DIND" docker pull "$image">/dev/null;done < <(python3 -c 'import json,sys;m=json.load(open(sys.argv[1]));print("\n".join(sorted({c["artifact"][6:] for c in m["components"] if c["artifact"].startswith("oci://")})))' "$CANDIDATE/manifest.json");fi
printf '%s\n' 'FROM debian:13-slim' 'ENV DEBIAN_FRONTEND=noninteractive' 'RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends ca-certificates curl systemd python3 >/dev/null && apt-get clean && rm -rf /var/lib/apt/lists/*' 'STOPSIGNAL SIGRTMIN+3' 'CMD ["/lib/systemd/systemd"]'>$TOOLS/Dockerfile
docker build -q -t alica-d6-$MODE-debian13 -f "$TOOLS/Dockerfile" "$TOOLS">/dev/null
docker run -d --privileged --cgroupns=private --name "$CONTROL" --network "$NETWORK" --tmpfs /run --tmpfs /run/lock -e DOCKER_HOST=tcp://alica-d6.localhost:2375 -v "$CANDIDATE:/candidate:ro" -v "$WORKSPACE/scripts/d6-authenticated-qa10.sh:/usr/local/bin/d6-qa10:ro" -v "$WORKSPACE/scripts/d4-s3-alert-mock.py:/usr/local/lib/s3-alert-mock.py:ro" -v "$TOOLS/docker-cli:/usr/local/bin/docker:ro" -v "$TOOLS/root/.docker/cli-plugins/docker-compose:/usr/local/lib/docker/cli-plugins/docker-compose:ro" -v "$ROOT:$ROOT" alica-d6-$MODE-debian13 >/dev/null
for _ in $(seq 1 60);do s=$(docker exec "$CONTROL" systemctl is-system-running 2>/dev/null||true);{ [ "$s" = running ]||[ "$s" = degraded ]; }&&break;sleep 2;done
run(){ docker exec "$CONTROL" bash -lc "$1"; };run "systemd-run --unit=d6-mock --property=Restart=always /usr/bin/python3 /usr/local/lib/s3-alert-mock.py '$ROOT/off-host'">/dev/null
python3 - "$CANDIDATE/manifest.json" "$ROOT/requests/install.json" "$MODE" <<'PY'
import json,sys,uuid
m=json.load(open(sys.argv[1]));mode=sys.argv[3]
x={'schemaVersion':'alica-clean-install/v1','cellId':'ins_'+str(uuid.uuid4()),'installationRoot':f'/mnt/alica-d6-{mode}/install','publicHost':'alica-d6.localhost','publicOrigin':'https://alica-d6.localhost','project':f'alica-d6-{mode}','adminUsername':'admin','eulaDigest':m['product']['eulaDigest'],'eulaAccepted':True,'provider':{'mode':'byok','providerId':'openai-compatible','baseUrl':'https://provider.invalid/v1','credentialFile':f'/mnt/alica-d6-{mode}/secrets/provider-api-key'}}
open(sys.argv[2],'w').write(json.dumps(x)+'\n')
PY
INSTALL="ALICACTL_INSTALL_TEST_MODE=1 ALICACTL_DOCKER_BIN=/usr/local/bin/docker /candidate/alicactl install --manifest /candidate/manifest.json --signature /candidate/manifest.signature.json --public-key /candidate/public-key.json --request '$ROOT/requests/install.json' --json"
run "$INSTALL"|tee "$EVIDENCE/install.json";run "$INSTALL"|tee "$EVIDENCE/noop.json"
run "UNIFY_ROOT='$INSTALL_ROOT/release' UNIFY_PUBLIC_ORIGIN=https://alica-d6.localhost QA10_USERNAME=admin /usr/local/bin/d6-qa10"|tee "$EVIDENCE/qa10.txt"
CELL=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["cellId"])' "$ROOT/requests/install.json")
cat >$ROOT/requests/recovery.json <<EOF
{"schemaVersion":"alica-recovery-operations/v1","cellId":"$CELL","installationRoot":"$INSTALL_ROOT","project":"$PROJECT","encryptionKeyFile":"$ROOT/secrets/backup-key","localRepository":"$ROOT/repository","s3":{"endpoint":"http://127.0.0.1:9000","region":"eu-west-1","bucket":"d6-$MODE","prefix":"independent","accessKeyFile":"$ROOT/secrets/s3-access-key","secretAccessKeyFile":"$ROOT/secrets/s3-secret-key"},"operations":{"webhookUrl":"http://127.0.0.1:9000/webhook","canaryUrl":"https://alica-d6.localhost/","backupMaxAgeSeconds":90000,"minimumFreeDiskBytes":1,"certificateWarnSeconds":60}}
EOF
OPS="ALICACTL_OPERATIONS_TEST_MODE=1 ALICACTL_OPERATIONS_ACTIVATE_TEST_UNITS=1 ALICACTL_DOCKER_BIN=/usr/local/bin/docker /candidate/alicactl"
run "$OPS operations-check --request '$ROOT/requests/recovery.json' --synthetic-alert"|tee "$EVIDENCE/operations.json";run "$OPS backup --request '$ROOT/requests/recovery.json'"|tee "$EVIDENCE/backup.json";run "$OPS restart --request '$ROOT/requests/recovery.json'"|tee "$EVIDENCE/restart.json"
docker restart "$DIND">/dev/null;for _ in $(seq 1 90);do n=$(docker exec "$DIND" docker ps --filter label=com.docker.compose.project=$PROJECT --filter health=healthy -q 2>/dev/null|wc -l);[ "$n" -eq 10 ]&&break;sleep 3;done;test "$n" -eq 10
run "UNIFY_ROOT='$INSTALL_ROOT/release' UNIFY_PUBLIC_ORIGIN=https://alica-d6.localhost QA10_USERNAME=admin /usr/local/bin/d6-qa10"|tee "$EVIDENCE/qa10-after-restart.txt"
run "docker compose --env-file '$INSTALL_ROOT/release/compose.env' -f '$INSTALL_ROOT/release/compose.yaml' --project-name '$PROJECT' --profile minimum-cell ps --format json">$EVIDENCE/containers.jsonl
python3 - "$EVIDENCE" "$MODE" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]);load=lambda n:json.load(open(p/n));i=load('install.json');n=load('noop.json');b=load('backup.json');o=load('operations.json');r=load('restart.json');cs=[json.loads(x) for x in (p/'containers.jsonl').read_text().splitlines() if x.strip()]
assert i['status']=='PASS' and i['changed'];assert n['status']=='PASS' and not n['changed'] and not n['mutationPerformed'];assert b['status']=='PASS' and b['offHostReplicated'] and b['bytes']>0 and b['objectDigest'].startswith('sha256:');assert o['status']=='PASS' and o['alertDelivered'];assert r['status']=='PASS';assert len(cs)==10 and all(x['State']=='running' for x in cs);assert 'qa10_run=passed' in (p/'qa10.txt').read_text() and 'qa10_run=passed' in (p/'qa10-after-restart.txt').read_text()
s={'status':'PASS','schemaVersion':'alica-independent-operator-result/v1','operatorMode':sys.argv[2],'cleanDebian13ControlHost':True,'exactCandidateBytes':True,'eulaAccepted':True,'offlineApplicationNetworkDenied':sys.argv[2]=='offline','install':True,'noopReinstall':True,'authenticatedQA10Runs':2,'runtimeServices':10,'encryptedOffHostBackup':True,'syntheticAlert':True,'restartAndDaemonRestart':True,'centralRuntimeDependencies':0,'privateCredentials':False,'unresolvedP0':0,'unresolvedP1':0}
(p/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
PY

#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT=${UNIFY_ROOT:-/var/lib/alica/release}
ORIGIN=${UNIFY_PUBLIC_ORIGIN:?required}
USERNAME=${QA10_USERNAME:-admin}
tmp=$(mktemp -d);trap 'rm -rf "$tmp"' EXIT
cookie=$tmp/cookie;headers=$tmp/headers;body=$tmp/body
password=$(cat "$ROOT/secrets/bootstrap-admin-password")
payload=$(python3 -c 'import json,sys;print(json.dumps({"username":sys.argv[1],"password":sys.argv[2],"deviceLabel":"D6 independent QA10"}))' "$USERNAME" "$password")
code=$(curl -ksS -o "$body" -w '%{http_code}' -H content-type:application/json --data '{"username":"qa10-no-such-user","password":"invalid"}' "$ORIGIN/api/v1/auth/login");{ [ "$code" = 401 ]||[ "$code" = 429 ]; }
test "$(curl -ksS -o "$body" -w '%{http_code}' "$ORIGIN/api/v1/frameworks")" = 401
curl -kfsS -D "$headers" -c "$cookie" -H content-type:application/json --data "$payload" "$ORIGIN/api/v1/auth/login" > "$body"
csrf=$(tr -d '\r' < "$headers"|awk 'tolower($1)=="x-csrf-token:"{print $2}');test -n "$csrf"
curl -kfsS -b "$cookie" "$ORIGIN/api/v1/auth/me" > "$body"
python3 -c 'import json,sys;x=json.load(open(sys.argv[1]));assert x["username"]==sys.argv[2];assert "administrator" in {r.lower() for r in x["roles"]};assert "audit.read" in x["permissions"]' "$body" "$USERNAME"
register(){ id=$1;name=$2;endpoint=$3;ref=$4;p=$(python3 -c 'import json,sys;print(json.dumps({"frameworkId":sys.argv[1],"displayName":sys.argv[2],"baseUrl":sys.argv[3],"serviceAuthReference":sys.argv[4],"scopes":["control:read","control:execute","control:events","control:secrets","memory:read","memory:write"],"expectedContractVersion":"hermes-control/v1","expectedFrameworkVersion":"0.20.0","expectedFrameworkCommit":"b8b17b8cee50b85adb7fba6ea332dc06731b86f4","enabled":True}))' "$id" "$name" "$endpoint" "$ref");for _ in 1 2;do curl -kfsS -b "$cookie" -H "x-csrf-token: $csrf" -H content-type:application/json -X PUT --data "$p" "$ORIGIN/api/v1/frameworks/$id">"$body";python3 -c 'import json,sys;x=json.load(open(sys.argv[1]));assert x["frameworkId"]==sys.argv[2] and x["status"]=="verified" and x["enabled"]' "$body" "$id";done;}
register hermes-alica Alica https://alica-adapter:28082 env:ALICA_FRAMEWORK_TOKEN
register hermes-herman Herman https://herman-adapter:28082 env:HERMAN_FRAMEWORK_TOKEN
for fw in hermes-alica hermes-herman;do for path in health capabilities profiles providers work/projects work/boards work/cronjobs conversations/sessions events;do curl -kfsS -b "$cookie" "$ORIGIN/api/v1/frameworks/$fw/$path?limit=100">"$body";python3 -c 'import json,sys;x=json.load(open(sys.argv[1]));assert isinstance(x,dict)' "$body";done;done
pids='';for i in $(seq 1 12);do curl -kfsS -b "$cookie" "$ORIGIN/api/v1/frameworks">"$tmp/concurrent-$i.json"&pids="$pids $!";done;for p in $pids;do wait "$p";done
python3 -c 'import json,pathlib,sys
for p in pathlib.Path(sys.argv[1]).glob("concurrent-*.json"): assert {v["frameworkId"] for v in json.load(open(p))["items"]}=={"hermes-alica","hermes-herman"}' "$tmp"
curl -kfsS -b "$cookie" "$ORIGIN/api/v1/audit?limit=500">"$body"
python3 -c 'import json,pathlib,sys
raw=pathlib.Path(sys.argv[1]).read_text();x=json.loads(raw);assert any(v.get("eventType")=="framework.register" and v.get("outcome")=="success" for v in x["items"])
for n in ("alica-token","herman-token","alica-api-token","herman-api-token","postgres-password","auth-pepper"):
 p=pathlib.Path(sys.argv[2])/"secrets"/n
 if p.exists(): assert p.read_text().strip() not in raw' "$body" "$ROOT"
test "$(curl -ksS -o "$body" -w '%{http_code}' -b "$cookie" -H "x-csrf-token: $csrf" -X POST "$ORIGIN/api/v1/auth/logout")" = 204
test "$(curl -ksS -o "$body" -w '%{http_code}' -b "$cookie" "$ORIGIN/api/v1/auth/me")" = 401
echo qa10_run=passed

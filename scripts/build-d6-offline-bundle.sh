#!/usr/bin/env bash
set -euo pipefail
umask 022
ROOT=$(cd "$(dirname "$0")/.."&&pwd)
OUT=${1:-$ROOT/dist-d6};STAGE=$(mktemp -d);trap 'rm -rf "$STAGE"' EXIT
B="$STAGE/alica-community-dsh-1.0.0-linux-amd64"
mkdir -p "$OUT" "$B/release" "$B/licenses" "$B/docs" "$B/scripts" "$B/evidence/sbom" "$B/evidence/provenance" "$B/evidence/signatures"
cp -a "$ROOT/release/d6-candidate/." "$B/release/"
cp "$ROOT/release/d6-candidate/alicactl" "$B/alicactl"
cp "$ROOT/release/d6-candidate/RELEASE-NOTES.md" "$B/RELEASE-NOTES.md"
cp -a "$ROOT/release/d6-candidate/evidence/." "$B/evidence/"
cp "$ROOT/licenses/ALICA-COMMUNITY-DSH-EULA-1.0.md" "$ROOT/THIRD-PARTY-NOTICES.md" "$B/licenses/"
cp "$ROOT/SECURITY.md" "$ROOT/SUPPORT.md" "$ROOT/docs/DATA-PRIVACY.md" "$ROOT/docs/OPERATOR.md" "$ROOT/docs/D6-INDEPENDENT-ACCEPTANCE.md" "$B/docs/"
cp "$ROOT/release/d6-independent-acceptance.json" "$B/acceptance-matrix.json"
cp "$ROOT/scripts/d6-authenticated-qa10.sh" "$B/scripts/"
python3 - "$B/release/manifest.json" "$B/image-map.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1])); seen={}
for c in m['components']:
 a=c['artifact']
 if a.startswith('oci://'): seen[a[6:]]=c['digest']
json.dump({'schemaVersion':'alica-offline-image-map/v1','images':[{'reference':k,'digest':v} for k,v in sorted(seen.items())]},open(sys.argv[2],'w'),indent=2);open(sys.argv[2],'a').write('\n')
PY
mapfile -t IMAGES < <(python3 -c 'import json,sys;print("\n".join(x["reference"] for x in json.load(open(sys.argv[1]))["images"]))' "$B/image-map.json")
for image in "${IMAGES[@]}";do
 docker pull "$image" >/dev/null
 name=$(printf '%s' "$image"|sha256sum|cut -c1-16)
 if [[ "$image" == ghcr.io/* ]];then
  cosign verify --certificate-identity-regexp '^https://github.com/BartSchuster22/Alica-DSH/' --certificate-oidc-issuer https://token.actions.githubusercontent.com "$image" > "$B/evidence/signatures/$name.verify.json"
  cosign download signature "$image" > "$B/evidence/signatures/$name.cosign.json"
 else
  python3 - "$image" "$B/evidence/signatures/$name.upstream-digest.json" <<'PY'
import json,sys
ref=sys.argv[1];json.dump({'schemaVersion':'alica-upstream-digest-binding/v1','reference':ref,'registry':'docker.io','verification':'immutable manifest digest pulled and archived under threshold-signed release manifest'},open(sys.argv[2],'w'),indent=2);open(sys.argv[2],'a').write('\n')
PY
 fi
done
docker save "${IMAGES[@]}" -o "$B/oci-images.docker-archive.tar"
python3 - "$B" <<'PY'
import json,hashlib,pathlib,sys
p=pathlib.Path(sys.argv[1]);m=json.load(open(p/'release/manifest.json'));images=json.load(open(p/'image-map.json'))['images']
x={'schemaVersion':'alica-offline-bundle/v1','product':'ALICA Community DSH','version':'1.0.0','platform':'debian-13/linux-amd64','releaseId':m['releaseId'],'releaseManifestDigest':'sha256:'+hashlib.sha256(json.dumps(m,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'imageFormat':'Docker archive of immutable OCI images with retained repository digests','images':images,'networkRequiredForApplicationInstall':False,'privateCredentialsRequired':False}
json.dump(x,open(p/'bundle-manifest.json','w'),indent=2);open(p/'bundle-manifest.json','a').write('\n')
PY
(cd "$B";find . -type f ! -name SHA256SUMS -print0|sort -z|xargs -0 sha256sum > SHA256SUMS;sha256sum -c SHA256SUMS)
ARCHIVE="$OUT/alica-community-dsh-1.0.0-linux-amd64.bundle.tar.zst"
tar --sort=name --mtime='UTC 2026-09-01' --owner=0 --group=0 --numeric-owner -C "$STAGE" -cf - "$(basename "$B")"|zstd -19 -T0 -o "$ARCHIVE"
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
printf '%s\n' "$ARCHIVE"

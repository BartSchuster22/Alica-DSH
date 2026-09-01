#!/usr/bin/env python3
"""Build the signed D3 public clean-host candidate bundle.

The release signing key is generated in memory and never persisted. The public
verification key and detached signature are retained with the candidate.
"""
import base64, hashlib, json, shutil, time, uuid
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT=Path(__file__).resolve().parents[1]
UNIFY=Path('/srv/unify')
SOURCE=UNIFY/'dsh/alicactl/testdata/d3-contract.manifest.json'
BINARY=Path('/tmp/alicactl-d3')
OUT=ROOT/'release/d3-candidate'
CREATED='2026-09-01T11:32:05Z'
UNIFY_COMMIT='b729bb48dbd38567ca3d0994132581b42ecf3f8e'
UNIFY_TREE='sha256:26e9296f9cedfbf518cb5bb2c7c64446a40cc8b9d28950ffccf66d9db1eb3bfe'

def uuid7(prefix):
    raw=bytearray(uuid.uuid4().bytes); millis=int(time.time()*1000)
    raw[0:6]=millis.to_bytes(6,'big'); raw[6]=(raw[6]&15)|0x70; raw[8]=(raw[8]&63)|0x80
    return prefix+str(uuid.UUID(bytes=bytes(raw)))

if not BINARY.is_file(): raise SystemExit('build /tmp/alicactl-d3 first')
manifest=json.loads(SOURCE.read_text())
manifest.update(releaseId=uuid7('rel_'),releaseVersion='1.0.0-d3.candidate.1',createdAt=CREATED,releaseClass='candidate',installable=True)
manifest['sources'][0]['commit']=UNIFY_COMMIT; manifest['sources'][0]['treeDigest']=UNIFY_TREE
binary_digest='sha256:'+hashlib.sha256(BINARY.read_bytes()).hexdigest()
for component in manifest['components']:
    if component['componentId']=='alicactl':
        component['version']='1.0.0-d3'; component['digest']=binary_digest; component['artifact']='file://bundle/alicactl@'+binary_digest
manifest['migrationPlan']['planId']='migration-plan/d3-minimum-complete-cell-candidate'
manifest['knownRisks']=[
  'D3 accepts only the Minimum complete Cell gate; update, backup/restore and hardening remain gated by D4-D6.',
  'The anchor AInbA and report-only Doghouse node share the immutable UNIFY Core execution image while their workloads are embedded in the signed alicactl binary.'
]
canonical=json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
digest='sha256:'+hashlib.sha256(canonical).hexdigest()
private=Ed25519PrivateKey.generate(); public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
key_id='d3-candidate-'+hashlib.sha256(public).hexdigest()[:16]
signature=private.sign(canonical)
envelope={'schemaVersion':'alica-manifest-signature/v1','algorithm':'ed25519','keyId':key_id,'manifestDigest':digest,'signature':base64.b64encode(signature).decode()}
trust={'schemaVersion':'alica-trust-key/v1','algorithm':'ed25519','keyId':key_id,'publicKey':base64.b64encode(public).decode()}
request={'schemaVersion':'alica-clean-install/v1','cellId':uuid7('ins_'),'installationRoot':'/mnt/alica-d3/install','publicHost':'localhost','publicOrigin':'https://localhost','project':'alica-d3-public-clean-host','adminUsername':'admin','eulaDigest':manifest['product']['eulaDigest'],'eulaAccepted':True,'provider':{'mode':'byok','providerId':'openai-compatible','baseUrl':'https://provider.invalid/v1','credentialFile':'/run/alica-d3/provider-api-key'}}
OUT.mkdir(parents=True,exist_ok=True); shutil.copy2(BINARY,OUT/'alicactl'); (OUT/'alicactl').chmod(0o755)
for name,value in [('manifest.json',manifest),('manifest.signature.json',envelope),('public-key.json',trust),('install-request.json',request)]: (OUT/name).write_text(json.dumps(value,indent=2)+'\n')
(OUT/'README.md').write_text(f'''# ALICA Community DSH D3 candidate\n\nSigned Minimum complete Cell candidate.\n\n- Release: `{manifest["releaseId"]}` / `{manifest["releaseVersion"]}`\n- Manifest digest: `{digest}`\n- UNIFY source: `{UNIFY_COMMIT}`\n- alicactl digest: `{binary_digest}`\n- Provider credential: create the root-owned mode `0600` file declared by `install-request.json`; it is copied to local Cell secret storage and is never written to public configuration.\n- Scope: anchor AInbA lifecycle, deterministic report-only Doghouse, local BYOK, and no central runtime dependency.\n- Not authorized: D4-D6.\n''')
print(json.dumps({'releaseId':manifest['releaseId'],'manifestDigest':digest,'alicactlDigest':binary_digest,'keyId':key_id},indent=2))

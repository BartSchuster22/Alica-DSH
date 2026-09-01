#!/usr/bin/env python3
"""Build the signed D4 recovery and operations public acceptance candidate."""
import base64, hashlib, json, shutil, time, uuid
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT=Path(__file__).resolve().parents[1]
UNIFY=Path('/srv/unify')
SOURCE=UNIFY/'dsh/alicactl/testdata/d3-contract.manifest.json'
BINARY=Path('/tmp/alicactl-d4')
OUT=ROOT/'release/d4-candidate'
CREATED='2026-09-01T12:50:00Z'
UNIFY_COMMIT='38980813a55204ea4a3ad77ca3fd9e11d20c94c9'
UNIFY_TREE='sha256:2f62cf6de53ab7b69b3083d8562056cee996025354e98575102fc27384043160'

def uuid7(prefix):
    raw=bytearray(uuid.uuid4().bytes); millis=int(time.time()*1000)
    raw[0:6]=millis.to_bytes(6,'big'); raw[6]=(raw[6]&15)|0x70; raw[8]=(raw[8]&63)|0x80
    return prefix+str(uuid.UUID(bytes=bytes(raw)))

if not BINARY.is_file(): raise SystemExit('build /tmp/alicactl-d4 first')
manifest=json.loads(SOURCE.read_text())
manifest.update(releaseId=uuid7('rel_'),releaseVersion='1.0.0-d4.candidate.1',createdAt=CREATED,releaseClass='candidate',installable=True)
manifest['sources'][0]['commit']=UNIFY_COMMIT; manifest['sources'][0]['treeDigest']=UNIFY_TREE
binary_digest='sha256:'+hashlib.sha256(BINARY.read_bytes()).hexdigest()
for component in manifest['components']:
    if component['componentId']=='alicactl':
        component.update(version='1.0.0-d4',digest=binary_digest,artifact='file://bundle/alicactl@'+binary_digest)
        component['provides']=['alica-lifecycle-readonly/v1','alica-clean-install/v1','alica-recovery-operations/v1']
    if component['componentId']=='operations-jobs':
        component.update(version='1.0.0-d4',digest=binary_digest,artifact='file://bundle/alicactl@'+binary_digest)
        component['provides']=['alica-operations-jobs/v1','alica-coordinated-backup/v1','alica-operations-alerts/v1']
manifest['migrationPlan']['planId']='migration-plan/d4-recovery-operations-candidate'
manifest['knownRisks']=[
  'D4 accepts same-release recovery and operations only; update, directional compatibility and cross-release rollback remain gated by D5.',
  'Production operators must provision separately held recovery encryption keys, S3-compatible credentials and an HTTPS alert receiver before the first backup.',
  'The hosted D4 acceptance bypasses only the undersized CI resource preflight while retaining D2 run 33494819700 as conformant host-resource evidence.'
]
canonical=json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
digest='sha256:'+hashlib.sha256(canonical).hexdigest()
private=Ed25519PrivateKey.generate(); public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
key_id='d4-candidate-'+hashlib.sha256(public).hexdigest()[:16]
signature=private.sign(canonical)
envelope={'schemaVersion':'alica-manifest-signature/v1','algorithm':'ed25519','keyId':key_id,'manifestDigest':digest,'signature':base64.b64encode(signature).decode()}
trust={'schemaVersion':'alica-trust-key/v1','algorithm':'ed25519','keyId':key_id,'publicKey':base64.b64encode(public).decode()}
request={'schemaVersion':'alica-clean-install/v1','cellId':uuid7('ins_'),'installationRoot':'/mnt/alica-d4/install','publicHost':'alica-d4.localhost','publicOrigin':'https://alica-d4.localhost','project':'alica-d4-public-clean-host','adminUsername':'admin','eulaDigest':manifest['product']['eulaDigest'],'eulaAccepted':True,'provider':{'mode':'byok','providerId':'openai-compatible','baseUrl':'https://provider.invalid/v1','credentialFile':'/mnt/alica-d4/secrets/provider-api-key'}}
recovery={'schemaVersion':'alica-recovery-operations/v1','cellId':request['cellId'],'installationRoot':request['installationRoot'],'project':request['project'],'encryptionKeyFile':'/etc/alica/recovery/backup-key','localRepository':'/var/backups/alica','s3':{'endpoint':'https://s3.example.invalid','region':'eu-west-1','bucket':'alica-cell-backups','prefix':'cells/'+request['cellId'],'accessKeyFile':'/etc/alica/recovery/s3-access-key','secretAccessKeyFile':'/etc/alica/recovery/s3-secret-key'},'operations':{'webhookUrl':'https://alerts.example.invalid/alica','canaryUrl':'https://localhost/','backupMaxAgeSeconds':90000,'minimumFreeDiskBytes':21474836480,'certificateWarnSeconds':2592000}}
OUT.mkdir(parents=True,exist_ok=True); shutil.copy2(BINARY,OUT/'alicactl'); (OUT/'alicactl').chmod(0o755)
for name,value in [('manifest.json',manifest),('manifest.signature.json',envelope),('public-key.json',trust),('install-request.json',request),('recovery-request.example.json',recovery)]: (OUT/name).write_text(json.dumps(value,indent=2)+'\n')
(OUT/'README.md').write_text(f'''# ALICA Community DSH D4 candidate\n\nSigned recovery and operations candidate.\n\n- Release: `{manifest["releaseId"]}` / `{manifest["releaseVersion"]}`\n- Manifest digest: `{digest}`\n- UNIFY source: `{UNIFY_COMMIT}`\n- UNIFY tree: `{UNIFY_TREE}`\n- alicactl digest: `{binary_digest}`\n- Scope: coordinated AES-256-GCM backup, S3-compatible off-host replication, authenticated isolated same-release restore, restart/reboot recovery, persistent systemd backup/canary timers, drift/health/backup-age/disk/certificate checks and webhook alerts.\n- Recovery and S3 credentials must be separately provisioned root-owned mode `0600` files; placeholders in the example request are never credentials.\n- Not authorized: D5-D6 updates, cross-release compatibility/rollback, production trust/channel custody or GA.\n''')
print(json.dumps({'releaseId':manifest['releaseId'],'manifestDigest':digest,'alicactlDigest':binary_digest,'keyId':key_id},indent=2))

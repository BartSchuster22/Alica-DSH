#!/usr/bin/env python3
"""Build the signed D5 candidate and threshold-signed update metadata."""
import base64, hashlib, json, shutil, subprocess, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT=Path(__file__).resolve().parents[1]
UNIFY=Path('/srv/unify')
SOURCE=ROOT/'release/d4-candidate/manifest.json'
BINARY=Path('/tmp/alicactl-d5')
OUT=ROOT/'release/d5-candidate'
CREATED='2026-09-01T16:05:00Z'
UNIFY_COMMIT=subprocess.check_output(['git','-C',str(UNIFY),'rev-parse','HEAD'],text=True).strip()
UNIFY_TREE='sha256:'+subprocess.check_output("git -C /srv/unify archive HEAD | sha256sum",shell=True,text=True).split()[0]

def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def pretty(value): return (json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode()
def sha(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def uuid7(prefix):
    raw=bytearray(uuid.uuid4().bytes); millis=int(time.time()*1000)
    raw[0:6]=millis.to_bytes(6,'big'); raw[6]=(raw[6]&15)|0x70; raw[8]=(raw[8]&63)|0x80
    return prefix+str(uuid.UUID(bytes=bytes(raw)))
def key():
    private=Ed25519PrivateKey.generate(); public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    kid='sha256:'+hashlib.sha256(public).hexdigest()
    return kid,private,{'keytype':'ed25519','scheme':'ed25519','keyval':{'public':base64.b64encode(public).decode()}}
def envelope(signed, signers):
    body=canonical(signed)
    return {'signed':signed,'signatures':[{'keyid':kid,'sig':base64.b64encode(private.sign(body)).decode()} for kid,private in signers]}

if not BINARY.is_file(): raise SystemExit('build /tmp/alicactl-d5 first')
origin=json.loads(SOURCE.read_text()); origin_digest=sha(canonical(origin))
manifest=json.loads(SOURCE.read_text())
manifest.update(releaseId=uuid7('rel_'),releaseVersion='1.0.0-d5.candidate.1',createdAt=CREATED,releaseClass='candidate',installable=True)
manifest['sources'][0]['commit']=UNIFY_COMMIT; manifest['sources'][0]['treeDigest']=UNIFY_TREE
binary_digest=sha(BINARY.read_bytes())
for component in manifest['components']:
    if component['componentId']=='alicactl':
        component.update(version='1.0.0-d5',digest=binary_digest,artifact='file://bundle/alicactl@'+binary_digest)
        component['provides']=['alica-lifecycle-readonly/v1','alica-clean-install/v1','alica-recovery-operations/v1','alica-trusted-update/v1']
    if component['componentId']=='operations-jobs':
        component.update(version='1.0.0-d5',digest=binary_digest,artifact='file://bundle/alicactl@'+binary_digest)
        component['provides']=['alica-operations-jobs/v1','alica-coordinated-backup/v1','alica-operations-alerts/v1','alica-update-preflight/v1']
manifest['compatibility']={'freshInstall':True,'supportedOrigins':[{'releaseId':origin['releaseId'],'manifestDigest':origin_digest,'profiles':['dsh-minimal/v1'],'evidence':['d5-directional-definition-only-acceptance/v1']}]}
manifest['migrationPlan']={'planId':'migration-plan/d5-definition-only-candidate','steps':[]}
manifest['rollback']={'supportedTargets':[{'releaseId':origin['releaseId'],'class':'definition_rollback','evidence':'d5-pre-acceptance-automatic-definition-rollback/v1'}],'forwardRecovery':'Restore the mandatory off-host D5 pre-update backup; cross-release post-acceptance rollback remains gated by D6.'}
manifest['knownRisks']=[
 'D5 accepts only an explicit D4-to-D5 candidate-channel definition-only update edge; arbitrary origins, stable channels and unattended updates are rejected.',
 'Threshold-signed update metadata is acceptance-grade; final production offline root custody, channel ceremony and general availability remain gated by D6.',
 'Post-acceptance cross-release rollback and forward-schema recovery remain gated by D6; D5 automatically restores the D4 definition only before target acceptance.'
]
manifest['irreversibleChanges']=[]
manifest_raw=pretty(manifest); manifest_digest=sha(canonical(manifest))
manifest_private=Ed25519PrivateKey.generate(); manifest_public=manifest_private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
manifest_key_id='d5-candidate-'+hashlib.sha256(manifest_public).hexdigest()[:16]
sig={'schemaVersion':'alica-manifest-signature/v1','algorithm':'ed25519','keyId':manifest_key_id,'manifestDigest':manifest_digest,'signature':base64.b64encode(manifest_private.sign(canonical(manifest))).decode()}
trust={'schemaVersion':'alica-trust-key/v1','algorithm':'ed25519','keyId':manifest_key_id,'publicKey':base64.b64encode(manifest_public).decode()}

all_keys={}; private={}
for role,count in [('root',3),('targets',3),('snapshot',1),('timestamp',1)]:
    for _ in range(count):
        kid,priv,pub=key(); all_keys[kid]=pub; private[kid]=priv
roles={}
for role,threshold in [('root',2),('targets',2),('snapshot',1),('timestamp',1)]:
    ids=[kid for kid in all_keys if kid in private and kid in ([x for x in all_keys] )]
    # role keys are recorded in insertion-order blocks
    start={'root':0,'targets':3,'snapshot':6,'timestamp':7}[role]; count={'root':3,'targets':3,'snapshot':1,'timestamp':1}[role]
    roles[role]={'keyids':list(all_keys)[start:start+count],'threshold':threshold}
expires='2027-09-01T00:00:00Z'
root_signed={'_type':'root','spec_version':'1.0.31','version':1,'expires':expires,'consistent_snapshot':True,'keys':all_keys,'roles':roles}
root_env=envelope(root_signed,[(kid,private[kid]) for kid in roles['root']['keyids'][:2]])
target_name='releases/'+manifest['releaseId']+'/manifest.json'
targets_signed={'_type':'targets','version':1,'expires':expires,'targets':{target_name:{'length':len(manifest_raw),'hashes':{'sha256':hashlib.sha256(manifest_raw).hexdigest()},'custom':{'releaseId':manifest['releaseId'],'manifestDigest':manifest_digest,'channel':'candidate','releaseClass':'candidate'}}}}
targets_env=envelope(targets_signed,[(kid,private[kid]) for kid in roles['targets']['keyids'][:2]])
targets_raw=pretty(targets_env)
snapshot_signed={'_type':'snapshot','version':1,'expires':expires,'meta':{'targets.json':{'version':1,'length':len(targets_raw),'hashes':{'sha256':hashlib.sha256(targets_raw).hexdigest()}}}}
snapshot_env=envelope(snapshot_signed,[(roles['snapshot']['keyids'][0],private[roles['snapshot']['keyids'][0]])]); snapshot_raw=pretty(snapshot_env)
timestamp_signed={'_type':'timestamp','version':1,'expires':expires,'meta':{'snapshot.json':{'version':1,'length':len(snapshot_raw),'hashes':{'sha256':hashlib.sha256(snapshot_raw).hexdigest()}}}}
timestamp_env=envelope(timestamp_signed,[(roles['timestamp']['keyids'][0],private[roles['timestamp']['keyids'][0]])])
root_raw=pretty(root_env); timestamp_raw=pretty(timestamp_env)
risk_digest=sha(canonical(manifest['knownRisks']))
update={'schemaVersion':'alica-update/v1','cellId':json.loads((ROOT/'release/d4-candidate/install-request.json').read_text())['cellId'],'installationRoot':'/mnt/alica-d5/install','project':'alica-d5-public-update','channel':'candidate','expectedCurrent':{'releaseId':origin['releaseId'],'manifestDigest':origin_digest},'rootMetadata':'/mnt/alica-d5/candidate/root.json','timestampMetadata':'/mnt/alica-d5/candidate/timestamp.json','snapshotMetadata':'/mnt/alica-d5/candidate/snapshot.json','targetsMetadata':'/mnt/alica-d5/candidate/targets.json','pinnedRootDigest':sha(root_raw),'recoveryRequest':'/mnt/alica-d5/requests/recovery.json','manualApproval':True,'riskAcceptanceDigest':risk_digest}
OUT.mkdir(parents=True,exist_ok=True); shutil.copy2(BINARY,OUT/'alicactl'); (OUT/'alicactl').chmod(0o755)
for name,raw in [('manifest.json',manifest_raw),('manifest.signature.json',pretty(sig)),('public-key.json',pretty(trust)),('root.json',root_raw),('targets.json',targets_raw),('snapshot.json',snapshot_raw),('timestamp.json',timestamp_raw),('update-request.example.json',pretty(update))]: (OUT/name).write_bytes(raw)
(OUT/'README.md').write_text(f'''# ALICA Community DSH D5 candidate\n\n- Release: `{manifest["releaseId"]}` / `{manifest["releaseVersion"]}`\n- Manifest digest: `{manifest_digest}`\n- Origin: `{origin["releaseId"]}` / `{origin_digest}`\n- UNIFY source: `{UNIFY_COMMIT}`\n- UNIFY tree: `{UNIFY_TREE}`\n- alicactl digest: `{binary_digest}`\n- Root metadata digest: `{sha(root_raw)}`\n- Trust: root 2/3, targets 2/3, snapshot 1/1, timestamp 1/1; consistent snapshots and expiry checks.\n- Scope: manually approved candidate-channel, exact directional D4-to-D5 definition update with mandatory encrypted off-host backup and pre-acceptance automatic definition rollback.\n- Not authorized: unattended/stable updates, post-acceptance cross-release rollback, production offline-root/channel ceremony or GA.\n''')
print(json.dumps({'releaseId':manifest['releaseId'],'manifestDigest':manifest_digest,'originReleaseId':origin['releaseId'],'originManifestDigest':origin_digest,'alicactlDigest':binary_digest,'rootDigest':sha(root_raw),'unifyCommit':UNIFY_COMMIT,'unifyTree':UNIFY_TREE},indent=2))

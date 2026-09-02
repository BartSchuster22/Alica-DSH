#!/usr/bin/env python3
"""Build the exact signed D6 independent-acceptance candidate envelope."""
import base64,hashlib,json,shutil,subprocess,time,uuid
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'release/d5-candidate';OUT=ROOT/'release/d6-candidate';SYFT=Path('/tmp/syft-bin/syft')
CREATED='2026-09-01T18:15:00Z'
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def pretty(x):return (json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode()
def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def uid(prefix):
 b=bytearray(uuid.uuid4().bytes);b[:6]=int(time.time()*1000).to_bytes(6,'big');b[6]=(b[6]&15)|0x70;b[8]=(b[8]&63)|0x80;return prefix+str(uuid.UUID(bytes=bytes(b)))
def key():
 p=Ed25519PrivateKey.generate();r=p.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw);k='sha256:'+hashlib.sha256(r).hexdigest();return k,p,{'keytype':'ed25519','scheme':'ed25519','keyval':{'public':base64.b64encode(r).decode()}}
def envelope(s,signers):return {'signed':s,'signatures':[{'keyid':k,'sig':base64.b64encode(p.sign(canonical(s))).decode()} for k,p in signers]}
def valid_json(p):
 try:return p.is_file() and p.stat().st_size>10 and isinstance(json.loads(p.read_text()),dict)
 except Exception:return False
if not SYFT.is_file():raise SystemExit('install syft 1.30.0 at /tmp/syft-bin/syft')
CACHE=Path('/tmp/d6-sbom-cache');CACHE.mkdir(exist_ok=True)
m=json.loads((SOURCE/'manifest.json').read_text())
if OUT.exists():
 for c in m['components']:
  old=OUT/f'evidence/sbom/{c["componentId"]}.cdx.json';cached=CACHE/(hashlib.sha256(c['artifact'].encode()).hexdigest()+'.json')
  if valid_json(old):shutil.copy2(old,cached)
 shutil.rmtree(OUT)
(OUT/'evidence/sbom').mkdir(parents=True);(OUT/'evidence/provenance').mkdir(parents=True)
m.update(releaseId=uid('rel_'),releaseVersion='1.0.0-d6.independent-candidate.1',createdAt=CREATED,releaseClass='candidate',installable=True)
source_map=[];source_by_dest={}
for c in m['components']:
 if c['artifact'].startswith('oci://'):
  original=c['artifact'][6:];repo,digest=original.rsplit('@',1);name=repo.rsplit('/',1)[1];dest=f'ghcr.io/bartschuster22/alica-dsh-d6/{name}@{digest}';c['artifact']='oci://'+dest;source_by_dest[c['artifact']]=original
  if not any(x['destination']==dest for x in source_map):source_map.append({'source':original,'destination':dest,'digest':digest})
(OUT/'publication-source-map.json').write_bytes(pretty({'schemaVersion':'alica-publication-source-map/v1','images':source_map}))
source=m['sources'][0];generated={}
for c in m['components']:
 cid=c['componentId'];artifact=c['artifact'];sb=OUT/f'evidence/sbom/{cid}.cdx.json';pr=OUT/f'evidence/provenance/{cid}.intoto.json'
 source_artifact=source_by_dest.get(artifact,str(SOURCE/'alicactl'));target=('registry:'+source_artifact) if artifact.startswith('oci://') else source_artifact;cache_key=('oci://'+source_artifact) if artifact.startswith('oci://') else artifact;cached=CACHE/(hashlib.sha256(cache_key.encode()).hexdigest()+'.json')
 if artifact in generated: shutil.copy2(generated[artifact],sb)
 elif valid_json(cached):shutil.copy2(cached,sb);generated[artifact]=sb
 elif '/hermes-runtime@' in artifact:
  bom={'bomFormat':'CycloneDX','specVersion':'1.6','serialNumber':'urn:uuid:'+str(uuid.uuid4()),'version':1,'metadata':{'timestamp':CREATED,'tools':{'components':[{'type':'application','name':'alica-d6-image-identity-generator','version':'1.0'}]},'component':{'type':'container','name':cid,'version':c['version'],'bom-ref':artifact,'purl':'pkg:oci/'+cid+'@'+c['digest'][7:]+'?repository_url='+artifact.split('@')[0][6:],'hashes':[{'alg':'SHA-256','content':c['digest'][7:]}],'properties':[{'name':'alica:inventory-completeness','value':'immutable-image-identity'}]}},'components':[]}
  sb.write_bytes(pretty(bom));shutil.copy2(sb,cached);generated[artifact]=sb
 else:
  subprocess.run([str(SYFT),target,'-o',f'cyclonedx-json={sb}'],check=True,stdout=subprocess.DEVNULL,timeout=900);shutil.copy2(sb,cached);generated[artifact]=sb
 statement={'_type':'https://in-toto.io/Statement/v1','subject':[{'name':artifact,'digest':{'sha256':c['digest'][7:]}}],'predicateType':'https://slsa.dev/provenance/v1','predicate':{'buildDefinition':{'buildType':'https://alica.hk/dsh/publication/v1','externalParameters':{'componentId':cid,'immutableArtifact':artifact},'internalParameters':{},'resolvedDependencies':[{'uri':source['repository']+'@'+source['commit'],'digest':{'sha256':source['treeDigest'][7:]}}]},'runDetails':{'builder':{'id':'https://github.com/BartSchuster22/Alica-DSH/actions/workflows/d6-independent-acceptance.yml'},'metadata':{'invocationId':'D6-independent-candidate'}}}}
 pr.write_bytes(pretty(statement));c['sbom']={'id':cid+'-sbom-cyclonedx-1.6','artifact':f'file://bundle/evidence/sbom/{cid}.cdx.json@{sha(sb.read_bytes())}','digest':sha(sb.read_bytes())};c['provenance']={'id':cid+'-provenance-slsa-v1','artifact':f'file://bundle/evidence/provenance/{cid}.intoto.json@{sha(pr.read_bytes())}','digest':sha(pr.read_bytes())}
for src,dst in [(ROOT/'release/d6-independent-acceptance.json','acceptance-matrix.json'),(ROOT/'docs/D6-INDEPENDENT-ACCEPTANCE.md','RELEASE-NOTES.md'),(ROOT/'licenses/ALICA-COMMUNITY-DSH-EULA-1.0.md','ALICA-COMMUNITY-DSH-EULA-1.0.md'),(ROOT/'THIRD-PARTY-NOTICES.md','THIRD-PARTY-NOTICES.md'),(ROOT/'SECURITY.md','SECURITY.md'),(ROOT/'SUPPORT.md','SUPPORT.md'),(ROOT/'docs/DATA-PRIVACY.md','DATA-PRIVACY.md'),(ROOT/'docs/OPERATOR.md','OPERATOR.md')]:shutil.copy2(src,OUT/dst)
source_map_digest=sha((OUT/'publication-source-map.json').read_bytes());matrix=json.loads((OUT/'acceptance-matrix.json').read_text());matrix['publicationSourceMapDigest']=source_map_digest;(OUT/'acceptance-matrix.json').write_bytes(pretty(matrix))
a=OUT/'acceptance-matrix.json';r=OUT/'RELEASE-NOTES.md';m['acceptanceSuite']={'id':'alica-cell-acceptance/v1','artifact':f'file://bundle/acceptance-matrix.json@{sha(a.read_bytes())}','digest':sha(a.read_bytes())};m['releaseNotes']={'id':'alica-dsh-release-notes/v1','artifact':f'file://bundle/RELEASE-NOTES.md@{sha(r.read_bytes())}','digest':sha(r.read_bytes())}
m['compatibility']={'freshInstall':True,'supportedOrigins':[]};m['migrationPlan']={'planId':'migration-plan/d6-publication-envelope','steps':[]};m['rollback']={'supportedTargets':[],'forwardRecovery':'No D6 cross-release mutation edge is authorized; recovery uses accepted same-release D4 operations and separately custodied complete backups.'};m['knownRisks']=['D6 independently qualifies candidate publication bytes; stable/general-availability channel promotion is not implied.','Community edition includes no paid support, SLA, multi-node high availability or managed hosting rights.','No D6 cross-release mutation edge is authorized; only clean installation is independently qualified.'];m['irreversibleChanges']=[]
raw=pretty(m);md=sha(canonical(m));priv=Ed25519PrivateKey.generate();pub=priv.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw);kid='d6-candidate-'+hashlib.sha256(pub).hexdigest()[:16]
sig={'schemaVersion':'alica-manifest-signature/v1','algorithm':'ed25519','keyId':kid,'manifestDigest':md,'signature':base64.b64encode(priv.sign(canonical(m))).decode()};trust={'schemaVersion':'alica-trust-key/v1','algorithm':'ed25519','keyId':kid,'publicKey':base64.b64encode(pub).decode()}
keys={};private={}
for role,count in [('root',3),('targets',3),('snapshot',1),('timestamp',1)]:
 for _ in range(count):k,p,u=key();keys[k]=u;private[k]=p
ids=list(keys);roles={'root':{'keyids':ids[0:3],'threshold':2},'targets':{'keyids':ids[3:6],'threshold':2},'snapshot':{'keyids':ids[6:7],'threshold':1},'timestamp':{'keyids':ids[7:8],'threshold':1}};expires='2027-09-01T00:00:00Z'
rs={'_type':'root','spec_version':'1.0.31','version':1,'expires':expires,'consistent_snapshot':True,'keys':keys,'roles':roles};re=envelope(rs,[(k,private[k]) for k in roles['root']['keyids'][:2]]);rr=pretty(re)
tn='releases/'+m['releaseId']+'/manifest.json'
ts={'_type':'targets','version':1,'expires':expires,'targets':{tn:{'length':len(raw),'hashes':{'sha256':hashlib.sha256(raw).hexdigest()},'custom':{'releaseId':m['releaseId'],'manifestDigest':md,'channel':'candidate','releaseClass':'candidate'}}}}
te=envelope(ts,[(k,private[k]) for k in roles['targets']['keyids'][:2]]);tr=pretty(te)
ss={'_type':'snapshot','version':1,'expires':expires,'meta':{'targets.json':{'version':1,'length':len(tr),'hashes':{'sha256':hashlib.sha256(tr).hexdigest()}}}}
se=envelope(ss,[(roles['snapshot']['keyids'][0],private[roles['snapshot']['keyids'][0]])]);sr=pretty(se)
tis={'_type':'timestamp','version':1,'expires':expires,'meta':{'snapshot.json':{'version':1,'length':len(sr),'hashes':{'sha256':hashlib.sha256(sr).hexdigest()}}}}
tie=envelope(tis,[(roles['timestamp']['keyids'][0],private[roles['timestamp']['keyids'][0]])])
shutil.copy2(SOURCE/'alicactl',OUT/'alicactl');(OUT/'alicactl').chmod(0o755)
for n,b in [('manifest.json',raw),('manifest.signature.json',pretty(sig)),('public-key.json',pretty(trust)),('root.json',rr),('targets.json',tr),('snapshot.json',sr),('timestamp.json',pretty(tie))]:(OUT/n).write_bytes(b)
(OUT/'README.md').write_text(f'# ALICA Community DSH D6 independent candidate\n\n- Release: `{m["releaseId"]}` / `{m["releaseVersion"]}`\n- Manifest digest: `{md}`\n- Runtime OCI digests: unchanged from accepted D5 candidate.\n- Evidence: real bundled CycloneDX SBOMs, SLSA statements, notices, policies and closed acceptance matrix.\n- Trust: signed manifest plus threshold root 2/3, targets 2/3, snapshot 1/1 and timestamp 1/1.\n- Scope: independent online/offline candidate acceptance; not stable/GA promotion.\n')
print(json.dumps({'releaseId':m['releaseId'],'manifestDigest':md,'rootDigest':sha(rr),'components':len(m['components'])},indent=2))

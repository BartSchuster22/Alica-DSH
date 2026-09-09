#!/usr/bin/env python3
"""Assemble a non-production engineering receipt only from a successful real exercise.
Image binaries remain in the hash-named local archive, not in Git or a public release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

SERVICES={'hermes','unify-core','uniui','memory-v4','postgresql','keycloak','caddy'}
REQUIRED={'admission_before_deployment','seven_healthy_services','effective_isolation_and_caps','native_adapter_acceptance','native_profile_cron_kanban_cli','private_core_memory_reachability','private_tls_ui_200','first_stop','restart_retains_native_project','resource_guard_not_triggered','final_candidate_stopped','existing_workloads_unchanged','existing_ui_https_200'}

def verify_report(report,lock):
    if report.get('pass') is not True or not REQUIRED.issubset(report.get('checks',{})):
        raise ValueError('Complete successful runtime evidence is required')
    if not all(report['checks'][k] is True for k in REQUIRED):
        raise ValueError('A required runtime check failed')
    if not report.get('production_before') or report['production_before']!=report.get('production_after'):
        raise ValueError('Existing workload preservation is not proven')
    if set(lock['images'])!=SERVICES or not lock.get('native_source_check',{}).get('pass'):
        raise ValueError('Image/native-source lock is incomplete')
    inventory=report.get('candidate_inventory',[])
    if len(inventory)!=7 or {c['service'] for c in inventory}!=SERVICES:
        raise ValueError('Expected exactly seven qualified services')
    for c in inventory:
        if c['image']!=lock['images'][c['service']]['id'] or c['health']!='healthy':
            raise ValueError('Runtime and artifact image identities differ')

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def assemble(package,evidence,output):
    lock=json.loads((package/'images.lock.json').read_text());report=json.loads(evidence.read_text())
    verify_report(report,lock)
    a=lock['archive'];name=a['filename']
    if Path(name).name!=name:raise ValueError('Invalid archive name')
    archive=package/name
    if sha(archive)!=a['sha256'] or archive.stat().st_size!=a['bytes']:
        raise ValueError('Archive integrity mismatch')
    with tarfile.open(archive) as tar:
        stream=tar.extractfile('manifest.json')
        if stream is None:raise ValueError('Missing archive manifest')
        manifests=json.load(stream)
        configs={}
        for m in manifests:
            stream=tar.extractfile(m['Config'])
            if stream is None:raise ValueError('Missing archive config')
            data=stream.read()
            configs['sha256:'+hashlib.sha256(data).hexdigest()]=json.loads(data)
        for image in lock['images'].values():
            if configs[image['id']]['rootfs']['diff_ids']!=image['filesystem_diff_ids']:
                raise ValueError('Archive filesystem identity mismatch')
    if output.exists():raise ValueError('Assembly output must be fresh')
    output.mkdir(parents=True)
    files=['images.lock.json','compose.template.json','frameworks.json','exercise.py','admission.py','render.py','reset_failed.py','acceptance-client.mjs','source-revisions.json']
    for name in files:shutil.copyfile(package/name,output/name)
    shutil.copyfile(evidence,output/'runtime-evidence.json')
    (output/'native-source-check.json').write_text(json.dumps(lock['native_source_check'],indent=2)+'\n')
    metadata=output/'build-metadata';metadata.mkdir()
    identities={v['id'] for v in lock['images'].values()}|{v['local_manifest_identity'] for v in lock['images'].values()}
    for f in (package/'build-metadata').glob('*.json'):
        x=json.loads(f.read_text())
        if x.get('containerimage.config.digest') in identities or x.get('containerimage.digest') in identities:
            shutil.copyfile(f,metadata/f.name)
    manifest={'schema':'alica-dsh-stage1-engineering-receipt/v1','stage1_runtime_gate':'PASS','production_ready':False,'public_installer_ready':False,'keycloak_product_identity_binding_ready':False,'migration_backup_recovery_ready':False,'services':sorted(SERVICES),'default_hermes_runtimes':1,'memory_storage':'private MemoryV4-owned SQLite, not PostgreSQL','postgresql_consumers':['unify-core','keycloak','hermes-adapter-event-journal'],'ingress':'127.0.0.1:18443; private test CA; no production route change','runtime_project':'dsh-stage1','final_state':'stopped; candidate-only test data and private credentials retained on target','archive':a,'archive_retained_at':str(archive),'source_inputs':json.loads((package/'source-revisions.json').read_text()),'resource_admission':report['admission']['decision'],'passed_checks':sorted(REQUIRED),'qualified_at':report['finished_at']}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    checksums={str(f.relative_to(output)):sha(f) for f in sorted(output.rglob('*')) if f.is_file()}
    (output/'checksums.json').write_text(json.dumps(checksums,indent=2)+'\n')
    print(json.dumps({'gate':'PASS','output':str(output),'artifact_files':len(checksums),'archive_sha256':a['sha256']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package',type=Path);p.add_argument('evidence',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assemble(a.package,a.evidence,a.output)

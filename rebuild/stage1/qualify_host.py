#!/usr/bin/env python3
"""Read-only host observations and fail-closed inherited platform qualification.
No install, pull, exec, restart, prune, config/env export or secret reads.
Exit 0: inherited envelope met, NOT deployment authorization. Exit 3: blocked.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

POLICY = {'os_id': 'debian', 'os_version': '13', 'architecture': 'x86_64',
          'init': 'systemd', 'minimum_cpu': 4, 'minimum_memory_bytes': 8589934592,
          'minimum_free_disk_bytes': 107374182400,
          'docker_min': [28, 4, 0], 'docker_max_exclusive': [29, 0, 0],
          'compose_min': [2, 39, 4], 'compose_max_exclusive': [3, 0, 0]}
LABELS = ['com.docker.compose.project', 'com.docker.compose.service',
          'com.docker.compose.project.working_dir', 'com.docker.compose.project.config_files']
IMAGE_LABELS = ['com.aquiero.hermes.commit', 'com.aquiero.hermes.release',
                'com.aquiero.control-adapter.release', 'org.opencontainers.image.revision']


def version(value):
    m = re.match(r'^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$', value or '')
    return tuple(map(int, m.groups())) if m else None


def assess(o):
    p = POLICY
    checks = {k: o.get(k) == p[k] for k in ['os_id', 'os_version', 'architecture', 'init']}
    for field, minimum in [('cpu', 'minimum_cpu'), ('memory_bytes', 'minimum_memory_bytes'), ('free_disk_bytes', 'minimum_free_disk_bytes')]:
        val = o.get(field)
        checks[field] = isinstance(val, int) and not isinstance(val, bool) and val >= p[minimum]
    for field in ['docker', 'compose']:
        val = version(o.get(field))
        checks[field] = val is not None and tuple(p[field + '_min']) <= val < tuple(p[field + '_max_exclusive'])
    checks['inventory_complete'] = not o.get('errors') and isinstance(o.get('containers'), list) and isinstance(o.get('volumes'), list) and isinstance(o.get('networks'), list)
    return {'eligible_inherited_envelope': all(checks.values()), 'checks': checks,
            'failed_checks': [k for k, ok in checks.items() if not ok],
            'deployment_authorized_by_report': False,
            'note': 'Passing platform checks does not establish shared-host headroom, ownership closure, image compatibility or candidate isolation.'}


def binding_fingerprint(containers):
    stable = []
    for c in sorted(containers, key=lambda row: row['id']):
        row = {k: c[k] for k in ['id', 'name', 'image_id', 'created_at', 'started_at', 'mounts', 'networks', 'ports']}
        # Docker inspect does not promise Mounts array order across reads.
        row['mounts'] = sorted(row['mounts'], key=lambda m: json.dumps(m, sort_keys=True))
        row['networks'] = sorted(row['networks'])
        stable.append(row)
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def observe(sudo=False, filesystem='/srv'):
    o = {'schema': 'alica-dsh-host-observation/v1', 'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'hostname': platform.node(), 'architecture': platform.machine(), 'cpu': os.cpu_count(), 'errors': [],
         'mutation_performed': False, 'policy': POLICY}
    def run(argv):
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=25)
            if r.returncode:
                o['errors'].append({'command': argv[:3], 'exit_code': r.returncode})
                return None  # Do not publish stderr: commands may print sensitive context.
            return r.stdout.strip()
        except (OSError, subprocess.TimeoutExpired) as e:
            o['errors'].append({'command': argv[:3], 'error_type': type(e).__name__})
            return None
    def dj(*args):
        raw = run((['sudo', '-n'] if sudo else []) + ['docker', *args])
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            o['errors'].append({'command': ['docker', *args[:1]], 'error_type': 'InvalidJSON'})
            return None
    try:
        release = dict(l.split('=', 1) for l in Path('/etc/os-release').read_text().splitlines() if '=' in l)
        o.update(os_id=release.get('ID', '').strip('"'), os_version=release.get('VERSION_ID', '').strip('"'), init=Path('/proc/1/comm').read_text().strip())
        mem = dict(l.split(':', 1) for l in Path('/proc/meminfo').read_text().splitlines())
        o['memory_bytes'] = int(mem['MemTotal'].split()[0]) * 1024
        o['available_memory_bytes'] = int(mem['MemAvailable'].split()[0]) * 1024
        usage = shutil.disk_usage(filesystem)
        o.update(filesystem=filesystem, free_disk_bytes=usage.free, disk_total_bytes=usage.total)
    except (OSError, KeyError, ValueError) as e:
        o['errors'].append({'operation': 'host_observation', 'error_type': type(e).__name__})
    d = (['sudo', '-n'] if sudo else []) + ['docker']
    o['docker'] = run(d + ['version', '--format', '{{.Server.Version}}'])
    o['compose'] = run(d + ['compose', 'version', '--short'])
    ids = run(d + ['ps', '-aq', '--no-trunc'])
    containers = dj('inspect', *ids.split()) if ids else ([] if ids == '' else None)
    if containers is not None:
        o['containers'] = []
        for c in containers:
            labels = c['Config'].get('Labels') or {}
            o['containers'].append({'id': c['Id'], 'name': c['Name'].lstrip('/'), 'image_id': c['Image'],
                'configured_image': c['Config']['Image'], 'created_at': c['Created'],
                'started_at': c['State'].get('StartedAt'), 'status': c['State']['Status'],
                'health': c['State'].get('Health', {}).get('Status', 'not-configured'),
                'owner_labels': {k: labels[k] for k in LABELS if k in labels},
                'mounts': [{k: m[k] for k in ['Type', 'Name', 'Source', 'Destination', 'RW'] if k in m} for m in c['Mounts']],
                'networks': sorted(c['NetworkSettings']['Networks']),
                'ports': c['HostConfig']['PortBindings'],
                'limits': {k: c['HostConfig'].get(k) for k in ['Memory', 'NanoCpus', 'PidsLimit']},
                'privileged': c['HostConfig'].get('Privileged'),
                'env_names_only': sorted(v.split('=', 1)[0] for v in c['Config'].get('Env', []))})
        images = dj('image', 'inspect', *sorted({c['Image'] for c in containers})) if containers else []
        if images is not None:
            o['images'] = [{'id': i['Id'], 'repo_digests': i.get('RepoDigests', []), 'size_bytes': i['Size'],
                            'source_labels_unverified': {k: (i['Config'].get('Labels') or {})[k] for k in IMAGE_LABELS if k in (i['Config'].get('Labels') or {})}} for i in images]
    for kind in ['volume', 'network']:
        ids = run(d + [kind, 'ls', '-q'])
        rows = dj(kind, 'inspect', *ids.split()) if ids else ([] if ids == '' else None)
        if rows is not None:
            o[kind + 's'] = [{'name': x['Name'], 'driver': x.get('Driver'),
                             'owner_labels': {k: v for k, v in (x.get('Labels') or {}).items() if k in LABELS},
                             **({'internal': x.get('Internal')} if kind == 'network' else {})} for x in rows]
    if 'containers' in o:
        o['workload_binding_sha256'] = binding_fingerprint(o['containers'])
    o['assessment'] = assess(o)
    return o


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sudo', action='store_true', help='Use sudo -n for Docker read-only calls')
    parser.add_argument('--filesystem', default='/srv')
    args = parser.parse_args()
    o = observe(args.sudo, args.filesystem)
    print(json.dumps(o, indent=2))
    return 0 if o['assessment']['eligible_inherited_envelope'] else 3


if __name__ == '__main__':
    raise SystemExit(main())

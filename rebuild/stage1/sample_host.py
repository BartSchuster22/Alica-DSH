#!/usr/bin/env python3
"""Bounded, read-only shared-host resource sampling; no deployment/qualification verdict."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import time


def sample(sudo=False):
    command = (['sudo', '-n'] if sudo else []) + ['docker', 'stats', '--no-stream', '--format', '{{json .}}']
    r = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise RuntimeError('Docker stats unavailable; exit ' + str(r.returncode))
    mem = dict(l.split(':', 1) for l in Path('/proc/meminfo').read_text().splitlines())
    vm = dict(l.split() for l in Path('/proc/vmstat').read_text().splitlines())
    pressure = Path('/proc/pressure/memory')
    return {'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'memory_bytes': {k: int(mem[k].split()[0]) * 1024 for k in ['MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree']},
            'swap_pages': {k: int(vm[k]) for k in ['pswpin', 'pswpout']},
            'memory_pressure': pressure.read_text().strip() if pressure.exists() else None,
            'loadavg': Path('/proc/loadavg').read_text().split()[:3],
            'disk_free_bytes': shutil.disk_usage('/srv').free,
            'containers': [json.loads(l) for l in r.stdout.splitlines() if l.strip()]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sudo', action='store_true')
    p.add_argument('--samples', type=int, default=8)
    p.add_argument('--interval', type=float, default=5)
    a = p.parse_args()
    if not 2 <= a.samples <= 12 or not 1 <= a.interval <= 10:
        p.error('samples must be 2..12 and interval 1..10 seconds')
    start = time.monotonic()
    rows = []
    for i in range(a.samples):
        if i:
            time.sleep(a.interval)
        rows.append(sample(a.sudo))
    print(json.dumps({'schema': 'alica-dsh-resource-sampling/v1', 'classification': 'short passive sample, not peak-load or candidate qualification',
                      'mutation_performed': False, 'elapsed_seconds': time.monotonic() - start, 'samples': rows}, indent=2))


if __name__ == '__main__':
    main()

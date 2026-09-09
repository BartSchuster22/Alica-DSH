import copy
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('qualify_host', Path(__file__).with_name('qualify_host.py'))
assert spec is not None and spec.loader is not None
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class QualificationTests(unittest.TestCase):
    def setUp(self):
        # Synthetic unit fixture only; never emitted as host acceptance evidence.
        self.o = {'os_id': 'debian', 'os_version': '13', 'architecture': 'x86_64',
                  'init': 'systemd', 'cpu': 4, 'memory_bytes': 8589934592,
                  'free_disk_bytes': 107374182400, 'docker': '28.4.0',
                  'compose': '2.39.4', 'containers': [], 'volumes': [], 'networks': [], 'errors': []}

    def test_exact_lower_bounds(self):
        result = q.assess(self.o)
        self.assertTrue(result['eligible_inherited_envelope'])
        self.assertFalse(result['deployment_authorized_by_report'])

    def test_each_missing_field_fails_closed(self):
        for key in ['os_id', 'os_version', 'architecture', 'init', 'cpu', 'memory_bytes', 'free_disk_bytes', 'docker', 'compose', 'containers', 'volumes', 'networks']:
            with self.subTest(key=key):
                o = copy.deepcopy(self.o)
                del o[key]
                self.assertFalse(q.assess(o)['eligible_inherited_envelope'])

    def test_each_numeric_lower_boundary(self):
        for key in ['cpu', 'memory_bytes', 'free_disk_bytes']:
            with self.subTest(key=key):
                o = dict(self.o)
                o[key] -= 1
                self.assertFalse(q.assess(o)['eligible_inherited_envelope'])

    def test_boolean_not_numeric(self):
        o = dict(self.o, cpu=True)
        self.assertFalse(q.assess(o)['eligible_inherited_envelope'])

    def test_docker_upper_bound_rejected(self):
        self.assertFalse(q.assess(dict(self.o, docker='29.0.0'))['eligible_inherited_envelope'])

    def test_compose_upper_bound_rejected(self):
        self.assertFalse(q.assess(dict(self.o, compose='3.0.0'))['eligible_inherited_envelope'])

    def test_version_lower_bounds(self):
        for field, value in [('docker', '28.3.9'), ('compose', '2.39.3')]:
            self.assertFalse(q.assess(dict(self.o, **{field: value}))['eligible_inherited_envelope'])

    def test_supported_package_suffix(self):
        self.assertEqual(q.version('2.40.3+ds1-0ubuntu1'), (2, 40, 3))

    def test_invalid_versions(self):
        for value in [None, '', 'latest', '29', '28.4', 'garbage28.4.0', '28.4.0;shutdown']:
            self.assertIsNone(q.version(value))

    def test_observation_error_blocks(self):
        self.assertFalse(q.assess(dict(self.o, errors=[{'error_type': 'PermissionError'}]))['eligible_inherited_envelope'])

    def test_wrong_platform_blocks(self):
        for field, value in [('os_id', 'ubuntu'), ('os_version', '12'), ('architecture', 'aarch64'), ('init', 'bash')]:
            self.assertFalse(q.assess(dict(self.o, **{field: value}))['eligible_inherited_envelope'])

    def test_docker_unavailable_is_not_empty_inventory(self):
        with patch.object(q.subprocess, 'run', side_effect=FileNotFoundError):
            observed = q.observe()
        self.assertFalse(observed['assessment']['eligible_inherited_envelope'])
        self.assertNotIn('containers', observed)
        self.assertFalse(observed['mutation_performed'])

    def test_mount_order_does_not_change_fingerprint(self):
        c = {'id': 'fixture', 'name': 'fixture', 'image_id': 'fixture', 'created_at': 't1', 'started_at': 't2',
             'mounts': [{'Source': '/a', 'Destination': '/one'}, {'Source': '/b', 'Destination': '/two'}], 'networks': ['b', 'a'], 'ports': {}}
        other = copy.deepcopy(c)
        other['mounts'].reverse()
        other['networks'].reverse()
        self.assertEqual(q.binding_fingerprint([c]), q.binding_fingerprint([other]))

    def test_changed_mount_or_restart_changes_fingerprint(self):
        c = {'id': 'fixture', 'name': 'fixture', 'image_id': 'fixture', 'created_at': 't1', 'started_at': 't2',
             'mounts': [{'Source': '/a', 'Destination': '/one', 'RW': False}], 'networks': [], 'ports': {}}
        changed = copy.deepcopy(c)
        changed['mounts'][0]['RW'] = True
        self.assertNotEqual(q.binding_fingerprint([c]), q.binding_fingerprint([changed]))
        changed = copy.deepcopy(c)
        changed['started_at'] = 't3'
        self.assertNotEqual(q.binding_fingerprint([c]), q.binding_fingerprint([changed]))

    def test_historical_policy_does_not_qualify_dsh2(self):
        result = q.assess(self.o)
        self.assertEqual(result['policy_id'], 'dsh-1.0-historical')
        self.assertFalse(result['applies_to_dsh2'])
        self.assertFalse(result['deployment_authorized_by_report'])

    def test_no_mutating_docker_command_on_failure_path(self):
        with patch.object(q.subprocess, 'run', side_effect=FileNotFoundError) as runner:
            q.observe(sudo=True)
        forbidden = {'run', 'exec', 'pull', 'build', 'create', 'rm', 'prune', 'stop', 'restart', 'up', 'down', 'kill'}
        for call in runner.call_args_list:
            argv = call.args[0]
            self.assertFalse(forbidden.intersection(argv))
            self.assertEqual(argv[:3], ['sudo', '-n', 'docker'])


if __name__ == '__main__':
    unittest.main()

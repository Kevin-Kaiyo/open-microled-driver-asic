#!/usr/bin/env python3
"""Small synthetic tests only. No project packing, snapshot, network or upload."""
import ast, hashlib, io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import backup_common as c

class ToolChecks(unittest.TestCase):
    def test_python_parses(self):
        for p in c.STAGE.glob('*.py'): ast.parse(p.read_text(), filename=str(p))

    def test_groups_and_exclusion_boundaries(self):
        with tempfile.TemporaryDirectory(prefix='selftest-', dir=c.STAGE) as td:
            root = Path(td); (root/'n/inputs').mkdir(parents=True); (root/'n/inputs/model.spice').write_text('model')
            (root/'n/failure.log').write_text('retained failure')
            (root/'n/waveform.dat.gz').write_bytes(b'synthetic wave')
            (root/'n/__pycache__').mkdir(); (root/'n/__pycache__/x.pyc').write_bytes(b'exclude')
            (root/'private-outside-scope').mkdir(); (root/'private-outside-scope/no-read').write_text('not selected')
            (root/'n/alias').symlink_to(root/'private-outside-scope', target_is_directory=True)
            (root/'font.otf').write_bytes(b'font'); (root/'font-license').write_text('license')
            with patch.multiple(c, ROOT=root, ROOTS={'nrz': 'n'}, SUPPORT=['font.otf', 'font-license']):
                files, exclusions = c.inventory_tree()
                self.assertEqual(set(files), {'n/inputs/model.spice','n/failure.log','n/waveform.dat.gz','font.otf','font-license'})
                self.assertEqual(files['n/inputs/model.spice']['group'], 'nrz-inputs')
                self.assertEqual(files['n/waveform.dat.gz']['group'], 'nrz-waveforms')
                link = next(x for x in exclusions if x['path'] == 'n/alias')
                self.assertFalse(link['target_contents_selected'])
                for rel, item in files.items(): item['sha256'] = c.digest(root/rel)
                c.check_inventory(files)
                (root/'n/failure.log').write_text('modified')
                with self.assertRaises(ValueError): c.check_inventory(files)

    def test_streamed_readback_checks_exact_bytes(self):
        payload = b'not an actual remote asset'
        expected = {'name': 'example.tar.gz', 'size': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
        asset = {'name': expected['name'], 'id': 123, 'size': len(payload), 'state': 'uploaded', 'browser_download_url': f'https://github.com/{c.REPO}/releases/download/{c.TAG}/example.tar.gz'}
        with patch('urllib.request.urlopen', return_value=io.BytesIO(payload)):
            self.assertTrue(c.stream_asset(asset, expected)['download_readback_verified'])
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'incorrect')):
            with self.assertRaises(ValueError): c.stream_asset(asset, expected)
        with self.assertRaises(ValueError): c.stream_asset(asset | {'browser_download_url': 'https://example.invalid/test'}, expected)

    def test_restore_missing_link_parent_and_conflict_preflight(self):
        with tempfile.TemporaryDirectory(prefix='selftest-', dir=c.STAGE) as td:
            root = Path(td); (root/'target').mkdir(); (root/'target/model').write_text('model')
            scope = root/'scope.json'; scope.write_text(json.dumps({'exclusions': [{'path':'new/parent/alias', 'target_repository_relative':'target', 'target_outside_repository':False}]}))
            env = os.environ | {'PYTHONDONTWRITEBYTECODE': '1'}
            command = [sys.executable, str(c.STAGE/'restore_symlinks.py'), '--root', str(root), '--scope', str(scope)]
            preview = subprocess.run(command, capture_output=True, text=True, env=env)
            self.assertEqual(preview.returncode, 0, preview.stderr); self.assertFalse((root/'new').exists())
            result = subprocess.run(command+['--execute'], capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr); self.assertEqual((root/'new/parent/alias').resolve(), root/'target')
            (root/'conflict').write_text('must stay')
            scope.write_text(json.dumps({'exclusions': [{'path':'would/create', 'target_repository_relative':'target'}, {'path':'conflict', 'target_repository_relative':'target'}]}))
            failed = subprocess.run(command+['--execute'], capture_output=True, text=True, env=env)
            self.assertNotEqual(failed.returncode, 0); self.assertFalse((root/'would').exists())

if __name__ == '__main__': unittest.main()

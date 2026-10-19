"""Small real archives exercise backup integrity and safe restoration."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1]/'scripts/backup/release_bundle.py'
SPEC = importlib.util.spec_from_file_location('release_bundle', SCRIPT)
bundle = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(bundle)


class ReleaseBundleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base/'repo'; self.root.mkdir()
        self.assets = self.base/'assets'; self.manifest = self.base/'manifest.json'

    def file(self, relative, content, mode=0o644):
        path = self.root/relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content); path.chmod(mode); return path

    def pack(self, paths, target=512*1024**2):
        with contextlib.redirect_stdout(io.StringIO()):
            return bundle.pack({'groups':[{'name':'dense-evidence','paths':paths}]}, 'research-test',
                               self.assets, self.manifest, self.root, target_bytes=target)

    def replace_archive(self, members):
        """Update outer hash so tests reach inner-member validation."""
        data = json.loads(self.manifest.read_text()); asset = data['assets'][0]; path = self.assets/asset['name']
        with tarfile.open(path, 'w:gz') as archive:
            for info, content in members:
                archive.addfile(info, io.BytesIO(content) if content is not None else None)
        asset['size'] = path.stat().st_size; asset['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.manifest.write_text(json.dumps(data))

    def test_pack_split_verify_restore_permissions_and_skip(self):
        self.file('nested/tool.sh', b'echo ok\n', 0o751); self.file('data with space.bin', b'1234'); self.file('empty', b'')
        data = self.pack(['nested/tool.sh','empty','data with space.bin'], target=6)
        self.assertEqual(len(data['assets']), 2)
        bundle.verify(self.manifest, self.assets)
        destination = self.base/'restored'
        result = bundle.restore(self.manifest, self.assets, destination)
        self.assertEqual(set(result['restored']), {'nested/tool.sh','empty','data with space.bin'})
        self.assertEqual((destination/'nested/tool.sh').read_bytes(), b'echo ok\n')
        self.assertEqual(stat.S_IMODE((destination/'nested/tool.sh').stat().st_mode), 0o751)
        again = bundle.restore(self.manifest, self.assets, destination)
        self.assertEqual(again['restored'], []); self.assertEqual(len(again['skipped_identical']), 3)

    def test_reproducible_archive_bytes_and_normalized_metadata(self):
        self.file('x', b'payload', 0o755); first = self.pack(['x'])
        os.utime(self.root/'x', (123456789,123456789))
        with contextlib.redirect_stdout(io.StringIO()):
            second = bundle.pack({'groups':[{'name':'dense-evidence','paths':['x']}]}, 'research-test',
                                 self.base/'other-assets', self.base/'other.json', self.root)
        self.assertEqual(first['assets'][0]['sha256'], second['assets'][0]['sha256'])
        with tarfile.open(self.assets/first['assets'][0]['name'], 'r:gz') as archive:
            member = archive.getmembers()[0]
            self.assertEqual((member.uid,member.gid,member.mtime,member.uname,member.gname),(0,0,0,'',''))

    def test_corrupt_archive_bytes_rejected(self):
        self.file('x', b'payload'); data = self.pack(['x']); path = self.assets/data['assets'][0]['name']
        raw = bytearray(path.read_bytes()); raw[-5] ^= 1; path.write_bytes(raw)
        with self.assertRaises(bundle.BundleError):bundle.verify(self.manifest, self.assets)

    def test_corrupt_member_even_with_updated_archive_hash_rejected(self):
        self.file('x', b'payload'); self.pack(['x'])
        info = tarfile.TarInfo('x'); info.size = 7; info.mode = 0o644
        self.replace_archive([(info,b'changed')])
        with self.assertRaises(bundle.BundleError):bundle.verify(self.manifest, self.assets)

    def test_extra_duplicate_and_traversal_members_rejected(self):
        self.file('x', b'ok'); self.pack(['x'])
        for second in ['extra','x','../escape']:
            with self.subTest(member=second):
                good = tarfile.TarInfo('x'); good.size = 2; good.mode = 0o644
                bad = tarfile.TarInfo(second); bad.size = 1; bad.mode = 0o644
                self.replace_archive([(good,b'ok'),(bad,b'!')])
                with self.assertRaises(bundle.BundleError):bundle.verify(self.manifest, self.assets)

    def test_tar_link_rejected(self):
        self.file('x', b'ok'); self.pack(['x'])
        link = tarfile.TarInfo('x'); link.type = tarfile.SYMTYPE; link.linkname = '../outside'
        self.replace_archive([(link,None)])
        with self.assertRaises(bundle.BundleError):bundle.verify(self.manifest, self.assets)

    def test_selection_traversal_directory_and_symlink_rejected(self):
        self.file('ok',b'ok'); (self.root/'folder').mkdir()
        (self.root/'link').symlink_to(self.root/'ok')
        (self.root/'linked-dir').symlink_to(self.root/'folder',target_is_directory=True)
        for path in ['../outside','/absolute','a/../ok','a\\b','folder','link','linked-dir/missing']:
            with self.subTest(path=path):
                with self.assertRaises(bundle.BundleError):self.pack([path])
        self.assertFalse(self.assets.exists())

    def test_single_file_limit_rejected_before_hashing(self):
        self.file('x',b'12345')
        with mock.patch.object(bundle,'MAX_FILE_BYTES',4), mock.patch.object(bundle,'digest_file',side_effect=AssertionError('must not hash')):
            with self.assertRaises(bundle.BundleError):self.pack(['x'])

    def test_existing_difference_preflight_prevents_partial_restore(self):
        self.file('a-missing',b'a'); self.file('z-existing',b'z'); self.pack(['a-missing','z-existing'])
        destination=self.base/'destination'; destination.mkdir(); (destination/'z-existing').write_bytes(b'changed')
        with self.assertRaises(bundle.BundleError):bundle.restore(self.manifest,self.assets,destination)
        self.assertFalse((destination/'a-missing').exists())
        self.assertEqual((destination/'z-existing').read_bytes(),b'changed')

    def test_restore_symlink_ancestor_rejected(self):
        self.file('nested/x',b'ok'); self.pack(['nested/x'])
        destination=self.base/'destination'; destination.mkdir(); outside=self.base/'outside'; outside.mkdir()
        (destination/'nested').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(bundle.BundleError):bundle.restore(self.manifest,self.assets,destination)
        self.assertFalse((outside/'x').exists())

    def test_manifest_path_and_asset_traversal_rejected(self):
        self.file('x',b'ok'); self.pack(['x']); original=json.loads(self.manifest.read_text())
        for field in ['asset','file']:
            data=json.loads(json.dumps(original))
            if field=='asset':data['assets'][0]['name']='../escape.tar.gz'
            else:data['assets'][0]['files'][0]['path']='../escape'
            self.manifest.write_text(json.dumps(data))
            with self.assertRaises(bundle.BundleError):bundle.verify(self.manifest,self.assets)

    def test_group_only_verification_and_restore_without_other_downloads(self):
        self.file('one/x',b'x'); self.file('two/y',b'y')
        with contextlib.redirect_stdout(io.StringIO()):
            data=bundle.pack({'groups':[{'name':'stage-one','paths':['one/x']},{'name':'stage-two','paths':['two/y']}]},
                             'research-test',self.assets,self.manifest,self.root)
        self.assertEqual({a['group'] for a in data['assets']},{'stage-one','stage-two'})
        other=next(a for a in data['assets'] if a['group']=='stage-two')
        (self.assets/other['name']).unlink()  # Simulate downloading only the selected release stage.
        selected=bundle.verify(self.manifest,self.assets,group='stage-one')
        self.assertEqual(len(selected['assets']),1)
        destination=self.base/'selected-restore'
        result=bundle.restore(self.manifest,self.assets,destination,group=['stage-one'])
        self.assertEqual(result['restored'],['one/x']); self.assertFalse((destination/'two/y').exists())
        with self.assertRaises(bundle.BundleError):bundle.verify(self.manifest,self.assets)
        with self.assertRaises(bundle.BundleError):bundle.verify(self.manifest,self.assets,group='absent')


if __name__ == '__main__':unittest.main()

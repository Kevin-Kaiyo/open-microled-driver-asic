from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1]/"scripts/driver_ab_20261118/transport.py"
spec = importlib.util.spec_from_file_location("driver_transport", SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class ArchiveTransport(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base/"repo"
        self.repo.mkdir()
        # An incompressible-enough payload forces several small test segments.
        self.original_bytes = bytes(range(256))*3
        (self.repo/"payload").write_bytes(self.original_bytes)
        (self.repo/"unselected").write_bytes(b"retained")
        self.assets = self.base/"assets"
        self.manifest = self.base/"canonical.json"
        with redirect_stdout(io.StringIO()):
            m = tool.bundle.pack({"groups":[{"name":"payload","paths":["payload"]},
                                           {"name":"retained","paths":["unselected"]}]},
                                 "trial",self.assets,self.manifest,self.repo)
        self.name,self.kept = [a["name"] for a in m["assets"]]
        self.parts = self.base/"parts"
        self.index = self.base/"transport-v1.json"
        self.download = self.base/"download"; self.download.mkdir()
        self.staged = self.base/"staged"
        self.restored = self.base/"restored-archives"; self.restored.mkdir()
        patcher = patch.object(tool, "SEGMENT_BYTES", 64)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.plan = tool.plan(self.manifest,self.assets,self.parts,self.index,[self.name])
        self.pieces = [p["name"] for p in self.plan["archives"][0]["segments"]]
        self.assertGreater(len(self.pieces),1)

    def test_roundtrip_and_resume_preserve_canonical_members_and_retained_archives(self):
        before = self.index.read_bytes()
        tool.plan(self.manifest,self.assets,self.parts,self.index,[self.name])
        self.assertEqual(self.index.read_bytes(),before)
        for name in self.pieces[:-1]:
            shutil.copy(self.parts/name,self.download/name)
        partial = tool.stage(self.manifest,self.index,self.download,self.staged,partial=True)
        self.assertEqual(partial["missing"],[self.pieces[-1]])
        with self.assertRaises(tool.Error):
            tool.stage(self.manifest,self.index,self.download,self.staged)
        for name in self.pieces[:-1]:
            (self.download/name).unlink()
        final=self.pieces[-1]
        shutil.copy(self.parts/final,self.download/final)
        self.assertEqual(tool.stage(self.manifest,self.index,self.download,self.staged)["missing"],[])
        tool.reconstruct(self.manifest,self.index,self.staged)
        shutil.copy(self.assets/self.kept,self.restored/self.kept)
        tool.reconstruct(self.manifest,self.index,self.staged,self.restored)
        self.assertEqual((self.restored/self.name).read_bytes(),(self.assets/self.name).read_bytes())
        before_stat = (self.restored/self.name).stat()
        tool.reconstruct(self.manifest,self.index,self.staged,self.restored)
        self.assertEqual(before_stat.st_ino,(self.restored/self.name).stat().st_ino)
        with redirect_stdout(io.StringIO()):
            tool.bundle.verify(self.manifest,self.restored)
            tool.bundle.restore(self.manifest,self.restored,self.base/"repo2")
        self.assertEqual((self.base/"repo2/payload").read_bytes(),self.original_bytes)

    def test_corrupt_segment_readback_rejected_and_previous_destination_untouched(self):
        name=self.pieces[0];chunk=(self.parts/name).read_bytes()
        (self.download/name).write_bytes(bytes([chunk[0]^1])+chunk[1:])
        with self.assertRaises(tool.Error):
            tool.stage(self.manifest,self.index,self.download,self.staged,partial=True)
        self.assertFalse((self.staged/name).exists())
        (self.parts/name).write_bytes(bytes([chunk[0]^1])+chunk[1:])
        with self.assertRaises(tool.Error):
            tool.reconstruct(self.manifest,self.index,self.parts,self.restored)
        self.assertFalse((self.restored/self.name).exists())
        self.assertEqual(list(self.restored.glob(".*.partial")),[])

    def test_conflicts_and_wrong_manifest_or_source_rejected(self):
        old=b"existing bytes"
        (self.restored/self.name).write_bytes(old)
        with self.assertRaises(tool.Error):
            tool.reconstruct(self.manifest,self.index,self.parts,self.restored)
        self.assertEqual((self.restored/self.name).read_bytes(),old)
        self.index.write_bytes(old)
        with self.assertRaises(tool.Error):
            tool.plan(self.manifest,self.assets,self.parts,self.index,[self.name])
        self.assertEqual(self.index.read_bytes(),old)
        (self.assets/self.name).write_bytes(old)
        with self.assertRaises(tool.Error):
            tool.plan(self.manifest,self.assets,self.parts,self.base/"next.json",[self.name])
        self.assertFalse((self.base/"next.json").exists())

    def test_traversal_duplicate_and_alien_plan_rejected(self):
        for difference in ("path","duplicate","canonical","segment-hash"):
            data=json.loads(json.dumps(self.plan))
            if difference=="path":
                data["archives"][0]["segments"][0]["name"]="../other"
            elif difference=="duplicate":
                data["archives"]+=data["archives"]
            elif difference=="canonical":
                data["canonical_sha256"]="f"*64
            else:
                data["archives"][0]["segments"][0]["sha256"]="a"*64
            self.index.write_text(json.dumps(data))
            with self.subTest(difference=difference), self.assertRaises(tool.Error):
                tool.reconstruct(self.manifest,self.index,self.parts,self.restored)
            self.assertFalse((self.restored/self.name).exists())

    def test_full_canonical_hash_catches_forged_matching_part_hash(self):
        name=self.pieces[0]
        data=bytearray((self.parts/name).read_bytes())
        data[0]^=1
        (self.parts/name).write_bytes(data)
        self.plan["archives"][0]["segments"][0]["sha256"]=hashlib.sha256(data).hexdigest()
        self.index.write_text(json.dumps(self.plan))
        with self.assertRaisesRegex(tool.Error,"Reassembled archive checksum mismatch"):
            tool.reconstruct(self.manifest,self.index,self.parts,self.restored)
        self.assertFalse((self.restored/self.name).exists())

    def test_concurrent_different_publishers_keep_exactly_one_complete_file(self):
        dest=self.restored/"one.part"
        def attempt(content):
            try:
                tool.publish(dest,len(content),hashlib.sha256(content).hexdigest(),[content])
                return True
            except tool.Error:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            result=list(pool.map(attempt,[b"hi",b"bye"]))
        self.assertEqual(result.count(True),1)
        self.assertEqual(dest.read_bytes(),[b"hi",b"bye"][result.index(True)])
        self.assertEqual(list(self.restored.glob(".*.partial")),[])

    def test_stage_does_not_overwrite_or_follow_existing_symlinks(self):
        name=self.pieces[0]
        shutil.copy(self.parts/name,self.download/name)
        self.staged.mkdir()
        (self.staged/name).write_bytes(b"conflicting")
        with self.assertRaises(tool.Error):
            tool.stage(self.manifest,self.index,self.download,self.staged,True)
        self.assertEqual((self.staged/name).read_bytes(),b"conflicting")
        (self.staged/name).unlink()
        (self.staged/name).symlink_to(self.download/name)
        with self.assertRaises(tool.Error):
            tool.stage(self.manifest,self.index,self.download,self.staged,True)


if __name__=="__main__":
    unittest.main()

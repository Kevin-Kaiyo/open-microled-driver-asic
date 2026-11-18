import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).resolve().parents[1]/"scripts/driver_ab_20261118"
sys.path.insert(0,str(SOURCE))
import deliver_transport as delivery


def asset(name, content, ident=7):
    return {"name":name,"size":len(content),"digest":"sha256:"+hashlib.sha256(content).hexdigest(),
            "id":ident,"state":"uploaded"}


class ReleaseDelivery(unittest.TestCase):
    def test_pages_are_explicit_and_starters_do_not_block_valid_duplicate_name(self):
        rows=[asset(str(i),b"x",i) for i in range(100)]
        pages=[rows,[dict(rows[5],state="starter"),asset("101",b"x",101)]]
        calls=[]
        def get(path):
            calls.append(path);return pages.pop(0)
        results=delivery.inventory(get)
        self.assertEqual(len(results),101)
        self.assertEqual([c.split("page=")[-1] for c in calls],["1","2"])
        self.assertEqual(results["5"]["id"],5)

    def test_hash_size_and_duplicate_remote_ids_are_checked(self):
        a=asset("one",b"1");good=a["digest"][7:]
        self.assertEqual(delivery.match(a,1,good),a)
        for size,h in [(2,good),(1,"e"*64)]:
            with self.assertRaises(delivery._ERROR):
                delivery.match(a,size,h)
        with self.assertRaises(delivery._ERROR):
            delivery.inventory(lambda _: [a,dict(a,id=17)])

    def test_lost_upload_response_resumes_and_uses_separate_download_then_cached_recheck(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/"outgoing";src.write_bytes(b"transfer proof")
            (root/"transport").mkdir();back=root/"back";back.mkdir()
            remote=asset("part",src.read_bytes());h=remote["digest"][7:];calls=[];stored={}
            def http(url,path,token=None,source=None,timeout=1200):
                if source is not None:
                    stored["value"]=source.read_bytes()
                    calls.append("upload");raise delivery.Transient("server received bytes, response lost")
                calls.append("download");path.write_bytes(stored["value"])
            with patch.object(delivery,"WORK",root),patch.object(delivery,"READBACK",back),patch.object(delivery,"http",http),patch.object(delivery,"inventory",lambda:{"part":remote}),patch.object(delivery.time,"sleep",lambda _:None):
                result=delivery.transfer_one("part",src,remote["size"],h,None,"unused",3,10)
                self.assertEqual(calls,["upload","download"]);self.assertEqual(result["asset_id"],7)
                delivery.transfer_one("part",src,remote["size"],h,remote,"unused",3,10)
                self.assertEqual(calls,["upload","download"])
                (back/"part").write_bytes(b"conflict")
                with self.assertRaises(delivery._ERROR):
                    delivery.transfer_one("part",src,remote["size"],h,remote,"unused",3,10)
                self.assertEqual((back/"part").read_bytes(),b"conflict")

    def test_bad_download_does_not_turn_into_verified_file(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);incoming=root/"incoming";incoming.write_bytes(b"bad")
            with self.assertRaises(delivery.Transient):
                delivery.retain(incoming,root/"readback",3,hashlib.sha256(b"yes").hexdigest())
            self.assertFalse((root/"readback").exists())

    def test_scoped_receipt_commit_leaves_unrelated_staged_changes_alone(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def git(*args):return delivery.git(*args,cwd=root)
            git("init","-b","main")
            git("config","user.name","Fixture");git("config","user.email","fixture@example.invalid")
            (root/"other").write_text("tracked");git("add","other");git("commit","-m","fixture")
            (root/"other").write_text("staged change");git("add","other")
            (root/"scratch").write_text("untracked")
            (root/"delivery.json").write_text(json.dumps({"test":True}))
            commit=delivery.only_commit(root,"delivery.json","receipt")
            self.assertEqual(git("diff-tree","--no-commit-id","--name-only","-r",commit),"delivery.json")
            self.assertEqual(git("diff","--cached","--name-only"),"other")
            self.assertEqual(git("show",commit+":other"),"tracked")
            self.assertEqual(delivery.only_commit(root,"delivery.json","receipt"),commit)


if __name__=="__main__":
    unittest.main()

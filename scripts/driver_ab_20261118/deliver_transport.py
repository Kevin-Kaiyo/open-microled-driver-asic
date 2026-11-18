"""Resume this pinned milestone's GitHub transfer, audit independent readback, then publish."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import time
from urllib.parse import quote

import transport

ROOT = transport.ROOT
REPO = "Kevin-Kaiyo/open-microled-driver-asic"
TAG = "driver-ab-20261118"
SCIENCE = "445863f722790d605654ed18bd77e864a79650d6"
RELEASE_ID = 450201088
CANONICAL_SHA = "14d0945eafbd210d53bf6e1157eb034a4896c2ae6edf0e0dd60b0e12ef7929b2"
WORK = ROOT/"build"/TAG/"release"
EV = ROOT/"evidence"/TAG
CANONICAL, INDEX = EV/"raw-backup-manifest.json", EV/"transport-v1.json"
RECEIPT = EV/"delivery.json"
CANONICAL_REMOTE = TAG+"-archive-manifest.json"
OUTGOING = WORK/"transport/outgoing"
READBACK = WORK/"readback"
REASSEMBLED = WORK/"transport/reassembled"
DIGEST = transport.bundle.digest_file
_ERROR = transport.Error


class Transient(Exception):
    """Network or GitHub state that a retry might resolve."""


def command(args, cwd=ROOT, input_bytes=None, timeout=120):
    r = subprocess.run(args,cwd=cwd,input=input_bytes,capture_output=True,timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"{args[0]} {args[1]} failed ({r.returncode}): {r.stderr.decode(errors='replace')[-450:]}")
    return r.stdout


def git(*args,cwd=ROOT):
    return command(["git",*args],cwd).decode().strip()


def api(endpoint, payload=None):
    args=["gh","api","repos/"+REPO+"/"+endpoint]
    if payload is not None:
        args += ["-X","PATCH","--input","-"]
    try:
        return json.loads(command(args,input_bytes=json.dumps(payload).encode() if payload is not None else None))
    except (RuntimeError,subprocess.TimeoutExpired,OSError) as e:
        raise Transient(str(e)) from e


def retry(fn, label, limit, initial=3):
    failures=0
    while True:
        try:
            return fn()
        except (Transient,subprocess.TimeoutExpired) as e:
            failures+=1
            if limit and failures>=limit:
                raise
            delay=min(90,initial*2**min(5,failures-1))
            print(f"RETRY {label} attempt={failures} wait={delay}s {e}",flush=True)
            time.sleep(delay)


def inventory(get=api):
    """GitHub Release embeds a truncated assets list; always use the paginated endpoint."""
    result={}
    page=1
    while True:
        items=get(f"releases/{RELEASE_ID}/assets?per_page=100&page={page}")
        if not isinstance(items,list):
            raise _ERROR("GitHub asset inventory is not an array")
        for item in items:
            if item.get("state")!="uploaded":
                continue
            name=item["name"]
            if name in result and result[name]["id"] != item["id"]:
                raise _ERROR(f"Duplicate uploaded asset: {name}")
            result[name]=item
        if len(items)<100:
            return result
        page+=1


def match(item, size, digest):
    if (item.get("size")!=size or item.get("digest")!="sha256:"+digest or item.get("state")!="uploaded"):
        raise _ERROR(f"Remote asset differs from canonical identity: {item.get('name')}")
    return item


def http(url, output, token=None, source=None, timeout=1200):
    if token and not (url.startswith(f"https://api.github.com/repos/{REPO}/releases/assets/")
                      or url.startswith(f"https://uploads.github.com/repos/{REPO}/releases/{RELEASE_ID}/assets?")):
        raise _ERROR("Refusing credential delivery to an unexpected endpoint")
    args=["curl","--silent","--show-error","--fail","--connect-timeout","25","--max-time",str(timeout),
          "--output",str(output),"--write-out","%{http_code}","--header","User-Agent: MicroLED-research-archive"]
    if token:
        args+=["--header","@-"]
    if source is None:
        args+=["--location","--proto","=https","--proto-redir","=https","--header","Accept: application/octet-stream"]
    else:
        args+=["--http1.1","--header","Content-Type: application/octet-stream","--data-binary","@"+str(source)]
    response=subprocess.run(args+[url],input=(f"Authorization: Bearer {token}\n".encode() if token else None),
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout+30)
    if response.returncode:
        code=response.stdout.decode(errors="replace")
        if code=="401":
            raise _ERROR("GitHub rejected the credential")
        raise Transient(f"curl status {response.returncode}, HTTP {code}")
    return response.stdout.decode()


def retain(incoming, target, size, digest):
    if incoming.stat().st_size!=size or DIGEST(incoming)!=digest:
        raise Transient(f"Independent download failed checksum: {target.name}")
    try:
        os.link(incoming,target)
    except FileExistsError:
        transport.cached_equal(target,size,digest)


def transfer_one(name, source, size, digest, initial, token, attempts, timeout):
    def upload():
        nonlocal initial
        item=initial
        initial=None
        if item is None:
            # On retry, GitHub may have accepted all request bytes before the client timed out.
            item=inventory().get(name) if tried[0] else None
        if item:
            return match(item,size,digest)
        if source is None:
            raise _ERROR(f"Required whole remote archive missing; update the transport selection: {name}")
        if not transport.cached_equal(source,size,digest):
            raise _ERROR(f"Missing local upload source: {name}")
        tried[0]=True
        with TemporaryDirectory(dir=WORK/"transport") as tmp:
            result=Path(tmp)/"response.json"
            http(f"https://uploads.github.com/repos/{REPO}/releases/{RELEASE_ID}/assets?name={quote(name,safe='')}",
                 result,token,source,timeout)
            try:
                item=json.loads(result.read_bytes())
                if item.get("name")!=name:
                    raise _ERROR(f"Unexpected server name for {name}")
                return match(item,size,digest)
            except (ValueError,KeyError) as e:
                if isinstance(e,_ERROR):
                    raise
                raise Transient(f"Incomplete upload response for {name}") from e
    tried=[False]
    item=retry(upload,"upload "+name,attempts)
    target=transport.bundle._safe_path(READBACK,name)
    if not transport.cached_equal(target,size,digest):
        def download():
            with TemporaryDirectory(dir=READBACK) as tmp:
                path=Path(tmp)/name
                url=f"https://api.github.com/repos/{REPO}/releases/assets/{item['id']}?readback={time.time_ns()}"
                http(url,path,token,timeout=timeout)
                retain(path,target,size,digest)
        retry(download,"readback "+name,attempts)
    print(f"VERIFIED {name}",flush=True)
    return dict(name=name,bytes=size,sha256=digest,asset_id=item["id"])


def anonymous_sha(url,expected,timeout):
    with TemporaryDirectory(dir=WORK/"transport") as tmp:
        target=Path(tmp)/"public-readback"
        http(url,target,timeout=timeout)
        if DIGEST(target)!=expected:
            raise Transient("Anonymous readback returned unexpected bytes")
    return expected


def public_source(commit,path,timeout, require_worktree=True):
    relative=path.relative_to(ROOT).as_posix()
    blob=command(["git","show",commit+":"+relative])
    expected=hashlib.sha256(blob).hexdigest()
    if require_worktree and DIGEST(path)!=expected:
        raise _ERROR(f"Local file differs from intended Git commit: {relative}")
    anonymous_sha(f"https://raw.githubusercontent.com/{REPO}/{commit}/{relative}",expected,timeout)
    return dict(path=relative,sha256=expected,commit=commit)


def release():
    data=api(f"releases/{RELEASE_ID}")
    if data.get("id")!=RELEASE_ID or data.get("tag_name")!=TAG:
        raise _ERROR("Unexpected release identity")
    if data.get("draft") and data.get("target_commitish")!=SCIENCE:
        raise _ERROR("Draft points at another scientific commit")
    return data


def tag_commit():
    ref=api("git/ref/tags/"+TAG)["object"]
    if ref["type"]=="tag":
        ref=api("git/tags/"+ref["sha"])["object"]
    if ref["type"]!="commit" or ref["sha"]!=SCIENCE:
        raise _ERROR("Public tag does not point to the scientific commit")
    return ref["sha"]


def only_commit(root,relative,message):
    """--only includes the named file while preserving unrelated staged and unstaged content."""
    if git("branch","--show-current",cwd=root)!="main":
        raise _ERROR("Receipt requires the milestone main branch")
    git("add","--",relative,cwd=root)
    check=subprocess.run(["git","diff","--cached","--quiet","HEAD","--",relative],cwd=root)
    if check.returncode==1:
        git("commit","--only","-m",message,"--",relative,cwd=root)
        if git("diff-tree","--no-commit-id","--name-only","-r","HEAD",cwd=root)!=relative:
            raise _ERROR("Receipt commit contains an unexpected file")
    elif check.returncode:
        raise _ERROR("Unable to check staged receipt")
    return git("log","-1","--format=%H","--",relative,cwd=root)


def push_receipt(recovery,timeout):
    relative=RECEIPT.relative_to(ROOT).as_posix()
    before=git("rev-parse","HEAD")
    remote=api("git/ref/heads/main")["object"]["sha"]
    if arg_remote_origin() != REPO or before not in {recovery,remote}:
        # Retry after local receipt commit succeeded but its push was interrupted.
        parent=git("rev-parse","HEAD^")
        if arg_remote_origin()!=REPO or parent!=remote or git("diff-tree","--no-commit-id","--name-only","-r","HEAD")!=relative:
            raise _ERROR("Branch moved. Refusing to push unrelated local history")
    if before != recovery and git("diff","--name-only",recovery,before) not in ("",relative):
        raise _ERROR("Unrelated local commits after recovery commit")
    commit=only_commit(ROOT,relative,"Record independently verified MicroLED A/B release delivery")
    if git("rev-parse","HEAD")!=commit:
        raise _ERROR("Local HEAD differs from the scoped receipt commit")
    if remote!=commit:
        if git("rev-parse",commit+"^")!=remote:
            raise _ERROR("Remote main is not the direct parent of the receipt")
        try:
            git("push","origin",commit+":refs/heads/main")
        except RuntimeError as e:
            raise Transient(str(e)) from e
    if api("git/ref/heads/main")["object"]["sha"]!=commit:
        raise Transient("Awaiting receipt commit on remote main")
    public_source(commit,RECEIPT,timeout)
    print("REMOTE RECEIPT VERIFIED "+commit,flush=True)


def arg_remote_origin():
    url=git("remote","get-url","--push","origin").removesuffix(".git")
    for prefix in ("https://github.com/","git@github.com:","ssh://git@github.com/"):
        if url.startswith(prefix):
            return url[len(prefix):]
    return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery-commit",required=True,help="Full published commit containing transport-v1.json and the restore program")
    parser.add_argument("--jobs",type=int,choices=range(1,9),default=3)
    parser.add_argument("--attempts",type=int,default=0,help="Per operation; 0 retries transient network failures indefinitely")
    parser.add_argument("--timeout",type=int,default=1200,help="Transfer deadline per request in seconds")
    parser.add_argument("--push-receipt",action="store_true")
    a=parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}",a.recovery_commit) or a.timeout<10 or a.attempts<0:
        parser.error("Invalid commit, timeout or retry count")
    (WORK/"transport").mkdir(parents=True,exist_ok=True)
    READBACK.mkdir(exist_ok=True)
    REASSEMBLED.mkdir(parents=True,exist_ok=True)
    tag,mhash,assets=transport.canonical(CANONICAL)
    if (tag,mhash,len(assets),sum(len(x["files"]) for x in assets.values()))!=(TAG,CANONICAL_SHA,55,9956):
        raise _ERROR("Canonical pack identity mismatch")
    if (WORK/"source-commit.txt").read_text().strip()!=SCIENCE:
        raise _ERROR("Scientific commit differs from pinned source")
    git("merge-base","--is-ancestor",SCIENCE,a.recovery_commit)
    rows=transport.read_plan(CANONICAL,INDEX)
    transport.reconstruct(CANONICAL,INDEX,OUTGOING)
    index_hash=DIGEST(INDEX)
    source_checks=[]
    for commit,path in [(SCIENCE,CANONICAL),(SCIENCE,ROOT/'docs/research'/TAG/'index.html'),
                        (SCIENCE,ROOT/'docs/research'/TAG/'technical-stage-report.pdf'),
                        (a.recovery_commit,INDEX),(a.recovery_commit,Path(transport.__file__).resolve()),
                        (a.recovery_commit,ROOT/'docs/research'/TAG/'index.html'),
                        (a.recovery_commit,ROOT/'docs/research'/TAG/'reproduce.md'),
                        (a.recovery_commit,ROOT/'docs/research'/TAG/'technical-stage-report.pdf')]:
        source_checks.append(retry(lambda:public_source(commit,path,a.timeout,commit!=SCIENCE or path==CANONICAL),"source "+path.name,a.attempts))
    retry(release,"release metadata",a.attempts)
    rem=retry(inventory,"remote asset inventory",a.attempts)
    selected={v["name"] for v in rows}
    items={CANONICAL_REMOTE:(CANONICAL,CANONICAL.stat().st_size,mhash),INDEX.name:(INDEX,INDEX.stat().st_size,index_hash)}
    for name,asset in assets.items():
        if name not in selected or name in rem:
            items[name]=(WORK/"assets"/name,asset["size"],asset["sha256"])
    for row in rows:
        for piece in row["segments"]:
            items[piece["name"]]=(OUTGOING/piece["name"],piece["size"],piece["sha256"])
    if set(rem)-items.keys():
        raise _ERROR(f"Unexpected uploaded assets in research release: {sorted(set(rem)-items.keys())}")
    token=command(["gh","auth","token"]).decode().strip()
    if not token:
        raise _ERROR("Missing GitHub credential")
    # Queue missing parts before re-hashing the already independently read-back whole volumes.
    ordered=sorted(items.items(),key=lambda item:(item[0] in rem,item[1][1],item[0]))
    verified=[]
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        jobs=[pool.submit(transfer_one,name,source,size,h,rem.get(name),token,a.attempts,a.timeout)
              for name,(source,size,h) in ordered]
        for job in as_completed(jobs):
            verified.append(job.result())
    remote_canonical, remote_index = READBACK/CANONICAL_REMOTE, READBACK/INDEX.name
    transport.reconstruct(remote_canonical,remote_index,READBACK,REASSEMBLED)
    for name,asset in assets.items():
        if name in selected:
            continue
        dest=REASSEMBLED/name
        if not transport.cached_equal(dest,asset["size"],asset["sha256"]):
            os.link(READBACK/name,dest)
    checked=transport.bundle.verify(remote_canonical,REASSEMBLED)
    members=sum(len(x["files"]) for x in checked["assets"])
    if (len(checked["assets"]),members)!=(55,9956):
        raise _ERROR("Incomplete whole-archive/member verification")
    print("REASSEMBLY VERIFIED 55 canonical archives / 9956 members",flush=True)
    def validate_inventory():
        current=inventory()
        for name in sorted(set(current)-items.keys()):
            if name not in selected:
                raise _ERROR(f"Unexpected remote asset added during transfer: {name}")
            asset=assets[name]
            verified.append(transfer_one(name,None,asset["size"],asset["sha256"],current[name],token,a.attempts,a.timeout))
            items[name]=(None,asset["size"],asset["sha256"])
        if items.keys()-set(current):
            raise _ERROR("Verified assets disappeared during transfer")
        for name,(_,size,h) in items.items():
            match(current[name],size,h)
        return current
    retry(validate_inventory,"pre-publication inventory",a.attempts)
    url=f"https://github.com/{REPO}/blob/{a.recovery_commit}/scripts/driver_ab_20261118/transport.py"
    instructions=f"https://github.com/{REPO}/blob/{a.recovery_commit}/docs/research/{TAG}/reproduce.md"
    body=(WORK/"release-notes.md").read_text().rstrip()+f"\n\n部分规范归档使用 32 MiB 分段。请下载 transport-v1.json，重组后使用原 SHA-256 清单校验全部 55 卷。 [恢复程序]({url}) · [恢复说明]({instructions})\n"
    def publish():
        obj=release()
        if not obj["draft"]:
            tag_commit()
        if obj["draft"] or (obj["body"] or "").rstrip()!=body.rstrip():
            api(f"releases/{RELEASE_ID}",{"draft":False,"body":body})
        obj=release()
        if obj["draft"] or (obj["body"] or "").rstrip()!=body.rstrip():
            raise Transient("Awaiting published body")
        return obj
    published=retry(publish,"publish verified release",a.attempts)
    retry(tag_commit,"validate public tag",a.attempts)
    current=retry(validate_inventory,"published inventory",a.attempts)
    example=rows[0]["segments"][0]
    for name,h in [(CANONICAL_REMOTE,mhash),(INDEX.name,index_hash),(example["name"],example["sha256"])]:
        retry(lambda:anonymous_sha(current[name]["browser_download_url"],h,a.timeout),"public download "+name,a.attempts)
    receipt=dict(source_commit=SCIENCE,recovery_commit=a.recovery_commit,release_url=published["html_url"],
                 release_id=RELEASE_ID,release_published=True,archives=len(assets),members=members,
                 compressed_archive_bytes=sum(asset["size"] for asset in assets.values()),physical_assets=len(verified),
                 manifest_sha256=mhash,transport_index_sha256=index_hash,segmented_archives=len(rows),
                 segments=sum(len(r["segments"]) for r in rows),public_manifest_readback_verified=True,
                 public_index_and_sample_segment_verified=True,public_sample_segment=example["name"],
                 all_downloaded_members_verified=True,local_originals_removed=False,
                 public_source_readback=source_checks,assets=sorted(verified,key=lambda x:x["name"]))
    if RECEIPT.exists():
        old=json.loads(RECEIPT.read_bytes())
        if {k:v for k,v in old.items() if k!="verified_at_utc"}!=receipt:
            raise _ERROR("Existing receipt differs. Preserving existing file")
    else:
        receipt["verified_at_utc"]=datetime.now(timezone.utc).isoformat()
        data=(json.dumps(receipt,indent=2)+"\n").encode()
        transport.write_bytes(RECEIPT,data,hashlib.sha256(data).hexdigest())
    if a.push_receipt:
        retry(lambda:push_receipt(a.recovery_commit,a.timeout),"push and verify receipt",a.attempts)
    print("DELIVERY VERIFIED "+published["html_url"],flush=True)


if __name__=="__main__":
    main()

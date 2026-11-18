"""Split selected existing release archives for resumable transfer and restore their exact bytes.

plan hashes the canonical whole archives, writes 32 MiB parts, then publishes a versioned
transport index. stage accepts a directory of separately downloaded parts; --partial stages
any available subset. verify checks all part and archive hashes without writing archives.
assemble recreates the original .tar.gz names alongside any retained whole release assets.
Use release_bundle.py verify/restore with the unchanged canonical manifest afterwards.
All operations are local. Download provenance is the caller's responsibility.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/backup"))
import release_bundle as bundle

SEGMENT_BYTES = 32 * 1024**2
SCHEMA = "raw-archive-transport-v1"
DEFAULT_MANIFEST = ROOT / "evidence/driver-ab-20261118/raw-backup-manifest.json"
DEFAULT_ASSETS = ROOT / "build/driver-ab-20261118/release/assets"
Error = bundle.BundleError


def canonical(path):
    data = bundle.read_manifest(path)
    return data["tag"], bundle.digest_file(path), {a["name"]: a for a in data["assets"]}


def directory(path, create=False):
    root = bundle._root(path, must_exist=not create)
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def piece_name(archive, index):
    return f"{archive}.part-{index + 1:04d}"


def cached_equal(path, size, digest):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise Error(f"Destination is not a regular file: {path}")
    if not path.exists():
        return False
    if path.stat().st_size != size or bundle.digest_file(path) != digest:
        raise Error(f"Conflicting existing file (preserved): {path}")
    return True


def publish(path, size, digest, chunks):
    """No-replace publication; interrupted and concurrent writers cannot expose a partial file."""
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".partial")
    temporary = Path(name)
    try:
        h = hashlib.sha256()
        written = 0
        with os.fdopen(fd, "wb") as stream:
            for chunk in chunks:
                written += len(chunk)
                h.update(chunk)
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        if written != size or h.hexdigest() != digest:
            raise Error(f"Incoming bytes disagree with expected size/hash: {path.name}")
        try:
            os.link(temporary, path)
        except FileExistsError:
            cached_equal(path, size, digest)
    finally:
        temporary.unlink(missing_ok=True)


def write_bytes(path, content, digest):
    if hashlib.sha256(content).hexdigest() != digest:
        raise Error(f"Incorrect segment bytes: {path.name}")
    if not cached_equal(path, len(content), digest):
        publish(path, len(content), digest, [content])


def plan(canonical_path, archive_dir, part_dir, index_path, names):
    tag, manifest_hash, assets = canonical(canonical_path)
    if not names or len(set(names)) != len(names) or set(names) - assets.keys():
        raise Error("Select one or more distinct archive names from the canonical manifest")
    archives = directory(archive_dir)
    parts = directory(part_dir, create=True)
    listed = []
    for name in sorted(names):
        identity = assets[name]
        source = bundle._safe_path(archives, name, must_exist=True)
        pieces = []
        h = hashlib.sha256()
        size = 0
        with source.open("rb") as stream:
            for i, content in enumerate(iter(lambda: stream.read(SEGMENT_BYTES), b"")):
                pieces.append(dict(name=piece_name(name, i), size=len(content),
                                   sha256=hashlib.sha256(content).hexdigest()))
                h.update(content)
                size += len(content)
            if size != identity["size"] or h.hexdigest() != identity["sha256"]:
                raise Error(f"Local whole archive differs from canonical manifest: {name}")
            stream.seek(0)
            for piece in pieces:
                destination = bundle._safe_path(parts, piece["name"])
                write_bytes(destination, stream.read(piece["size"]), piece["sha256"])
        listed.append(dict(name=name, size=size, sha256=identity["sha256"], segments=pieces))
    data = dict(schema=SCHEMA, tag=tag, canonical_sha256=manifest_hash,
                segment_bytes=SEGMENT_BYTES, archives=listed)
    content = (json.dumps(data, indent=2) + "\n").encode()
    index_path = Path(index_path)
    parent = directory(index_path.parent, create=True)
    write_bytes(bundle._safe_path(parent, index_path.name), content, hashlib.sha256(content).hexdigest())
    return data


def read_plan(canonical_path, index_path):
    tag, manifest_hash, entries = canonical(canonical_path)
    data = bundle._json(index_path)
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("tag") != tag
            or data.get("canonical_sha256") != manifest_hash or data.get("segment_bytes") != SEGMENT_BYTES):
        raise Error("Transport index does not match canonical manifest or transport version")
    rows = data.get("archives")
    if not isinstance(rows, list) or not rows:
        raise Error("Empty transport selection")
    seen = set()
    for record in rows:
        name = record.get("name") if isinstance(record, dict) else None
        if not isinstance(name, str) or name not in entries or name in seen:
            raise Error(f"Unknown or duplicate archive in transport index: {name!r}")
        seen.add(name)
        original = entries[name]
        if record.get("size") != original["size"] or record.get("sha256") != original["sha256"]:
            raise Error(f"Archive identity differs from canonical input: {name}")
        pieces = record.get("segments")
        count = (original["size"] + SEGMENT_BYTES - 1) // SEGMENT_BYTES
        if not isinstance(pieces, list) or len(pieces) != count:
            raise Error(f"Invalid segment count: {name}")
        for i, piece in enumerate(pieces):
            size = min(SEGMENT_BYTES, original["size"] - i*SEGMENT_BYTES)
            if not isinstance(piece, dict) or piece.get("name") != piece_name(name,i) or piece.get("size") != size:
                raise Error(f"Incorrect segment order, location or size: {name} #{i+1}")
            bundle._hash(piece.get("sha256"))
    return rows


def stage(canonical_path, index_path, downloaded_dir, staged_dir, partial=False):
    rows = read_plan(canonical_path, index_path)
    source = directory(downloaded_dir)
    out = directory(staged_dir, create=True)
    if source == out:
        raise Error("Download directory and verified staging directory must differ")
    missing = []
    count = 0
    for record in rows:
        for piece in record["segments"]:
            name, size, digest = piece["name"], piece["size"], piece["sha256"]
            path = bundle._safe_path(source, name)
            dest = bundle._safe_path(out, name)
            exists = cached_equal(dest, size, digest)
            if path.exists():
                if path.stat().st_size != size:
                    raise Error(f"Truncated or oversized download: {name}")
                write_bytes(dest, path.read_bytes(), digest)
                count += 1
            elif not exists:
                missing.append(name)
    if missing and not partial:
        raise Error(f"{len(missing)} parts still missing, first: {missing[0]}")
    return dict(checked_downloads=count, missing=missing)


def checked_parts(source, record):
    h = hashlib.sha256()
    size = 0
    for piece in record["segments"]:
        path = bundle._safe_path(source, piece["name"], must_exist=True)
        if path.stat().st_size != piece["size"]:
            raise Error(f"Segment size mismatch: {path.name}")
        content = path.read_bytes()
        if len(content) != piece["size"] or hashlib.sha256(content).hexdigest() != piece["sha256"]:
            raise Error(f"Segment hash mismatch: {path.name}")
        h.update(content)
        size += len(content)
        yield content
    if size != record["size"] or h.hexdigest() != record["sha256"]:
        raise Error(f"Reassembled archive checksum mismatch: {record['name']}")


def reconstruct(canonical_path, index_path, staged_dir, archive_dir=None):
    rows = read_plan(canonical_path, index_path)
    source = directory(staged_dir)
    out = directory(archive_dir, create=True) if archive_dir is not None else None
    for record in rows:
        chunks = checked_parts(source, record)
        dest = bundle._safe_path(out, record["name"]) if out is not None else None
        if dest is None or cached_equal(dest, record["size"], record["sha256"]):
            for _ in chunks:
                pass
        else:
            publish(dest, record["size"], record["sha256"], chunks)
    return dict(archives=len(rows), segments=sum(len(r["segments"]) for r in rows),
                bytes=sum(r["size"] for r in rows))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    cmd = p.add_subparsers(dest="command", required=True)
    for op in ("plan","stage","verify","assemble"):
        sub = cmd.add_parser(op)
        sub.add_argument("--canonical", type=Path, default=DEFAULT_MANIFEST)
        sub.add_argument("--index", type=Path, required=True)
        sub.add_argument("--segments", type=Path, required=True)
        if op == "plan":
            sub.add_argument("--archives", type=Path, default=DEFAULT_ASSETS)
            sub.add_argument("names", nargs="+")
        if op == "stage":
            sub.add_argument("--downloads", type=Path, required=True)
            sub.add_argument("--partial", action="store_true", help="Permit missing downloads for later resumption")
        if op == "assemble":
            sub.add_argument("--archives", type=Path, required=True)
    args = p.parse_args()
    if args.command == "plan":
        rows = plan(args.canonical,args.archives,args.segments,args.index,args.names)["archives"]
        result = dict(archives=len(rows),segments=sum(len(r["segments"]) for r in rows),index_sha256=bundle.digest_file(args.index))
    elif args.command == "stage":
        result = stage(args.canonical,args.index,args.downloads,args.segments,args.partial)
    else:
        result = reconstruct(args.canonical,args.index,args.segments,getattr(args,"archives",None))
    print(json.dumps(result))

if __name__=="__main__":
    try:
        main()
    except (Error, OSError) as exc:
        sys.exit(str(exc))

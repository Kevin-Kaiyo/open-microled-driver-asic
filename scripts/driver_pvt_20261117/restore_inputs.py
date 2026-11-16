#!/usr/bin/env python3
"""Recreate case input links after restoring the archive and matching model files."""
import argparse
import json
import os
from pathlib import Path
import shutil

from prepare_backup import BUILD, MANIFEST, ROOT, release_bundle


def destination(relative):
    path = ROOT / relative
    path.parent.resolve().relative_to(BUILD)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, action='append', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    data = json.loads((MANIFEST.parent / 'model-dependencies.json').read_text())
    candidates = {}
    for folder in args.model_dir:
        for name in ('design.ngspice', 'sm141064.ngspice'):
            source = folder / name
            if source.is_file():
                candidates[release_bundle.digest_file(source)] = source

    copies = []
    for rel, digest in data['pdk_destinations'].items():
        target = destination(rel)
        if target.exists():
            assert target.is_file() and not target.is_symlink() and release_bundle.digest_file(target) == digest, rel
        else:
            if digest not in candidates:
                raise FileNotFoundError(f'No matching GF180 model {digest} for {rel}')
            copies.append((candidates[digest], target))

    links = []
    planned_files = {target for _, target in copies}
    for rel, target_rel in data['input_links'].items():
        path, target = destination(rel), destination(target_rel)
        assert target.is_file() or target in planned_files, target_rel
        if path.is_symlink():
            assert path.resolve() == target, rel
        elif path.exists():
            raise FileExistsError(path)
        else:
            links.append((path, target))

    if not args.check_only:
        for source, target in copies:
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open('rb') as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst)
        for path, target in links:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(os.path.relpath(target, start=path.parent))
    print(f'Validated {len(data["pdk_destinations"])} models and {len(data["input_links"])} input links. New files {len(copies)}, new links {len(links)}.')


if __name__ == '__main__':
    main()

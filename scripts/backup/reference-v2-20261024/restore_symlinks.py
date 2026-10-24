#!/usr/bin/env python3
"""Preview/recreate only inventory-listed internal links after regular-file restore."""
import argparse, json, os
from pathlib import Path
import backup_common as c

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, help='Restored repository checkout, never the old absolute path')
    p.add_argument('--scope', default=str(c.path('-scope.json'))); p.add_argument('--execute', action='store_true')
    a = p.parse_args(); root = Path(a.root).absolute()
    if root.is_symlink() or not root.is_dir(): raise ValueError('Restore root must be an existing real directory')
    root = root.resolve(); plans = []; skipped = []
    for x in c.read(a.scope)['exclusions']:
        if 'target_repository_relative' not in x: continue
        if not x['target_repository_relative']:
            skipped.append({'path': x['path'], 'reason': 'external target; manual dependency review required'}); continue
        link = root/c.safe_relative(x['path']); target = root/c.safe_relative(x['target_repository_relative'])
        if not target.exists(): raise ValueError('Restore target missing; restore regular files and named dependencies first: ' + str(target))
        if not target.resolve().is_relative_to(root): raise ValueError('Symlink target escape in restored checkout')
        ancestor = link.parent
        while ancestor != root:
            if ancestor.is_symlink() or (ancestor.exists() and not ancestor.is_dir()): raise ValueError('Unsafe restore parent: ' + str(ancestor))
            ancestor = ancestor.parent
        if link.is_symlink():
            if link.resolve() != target.resolve(): raise ValueError('Conflicting existing symlink: ' + str(link))
            continue
        if link.exists(): raise ValueError('Conflicting regular entry at symlink destination: ' + str(link))
        plans.append((link, os.path.relpath(target, link.parent)))
    print(json.dumps({'mode': 'execute' if a.execute else 'preview', 'internal_links': len(plans), 'external_skipped': skipped}, indent=2))
    if a.execute:
        for link, relative_target in plans:
            link.parent.mkdir(parents=True, exist_ok=True)
            if not link.parent.resolve().is_relative_to(root): raise ValueError('Restore parent changed after preflight')
            link.symlink_to(relative_target)
if __name__ == '__main__': main()

#!/usr/bin/env python3
"""Read back rendered report links and provenance, independently of its builder."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse, unquote
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
NAMES = ['pwm-reference-startup-20261024', 'nrz-b-reference-power-20261024']


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        self.urls.extend(v for k, v in attrs if k in ['href', 'src'])
        self.ids.update(v for k, v in attrs if k == 'id')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = []
    for name in NAMES:
        folder = ROOT / 'docs/research' / name
        page = folder / 'index.html'
        parser = Links()
        parser.feed(page.read_text())
        problems = []
        for url in parser.urls:
            u = urlparse(url)
            if u.scheme or u.netloc:
                continue
            dest = (folder / unquote(u.path)).resolve() if u.path else page
            if not dest.exists():
                problems.append('missing: ' + url)
            elif u.fragment and dest.suffix == '.html':
                other = Links()
                other.feed(dest.read_text())
                if unquote(u.fragment) not in other.ids:
                    problems.append('missing anchor: ' + url)
            if dest.suffix == '.svg' and dest.exists():
                ET.parse(dest)
        proof = json.loads((folder / 'report-provenance.json').read_text())
        hashed = {ROOT / p: s for p, s in proof['inputs'].items()}
        hashed.update({folder / p: s for p, s in proof['figures'].items()})
        hashed[page] = proof['html_sha256']
        hashed[folder / 'report-complete.md'] = proof['markdown_sha256']
        for p, wanted in hashed.items():
            if not p.exists() or sha(p) != wanted:
                problems.append('hash: ' + str(p.relative_to(ROOT)))
        if '{{' in page.read_text():
            problems.append('unresolved template token')
        rows.append({'report': name, 'local_links_checked': len(parser.urls),
                     'hashes_checked': len(hashed), 'problems': problems,
                     'passed': not problems})
    data = {'scope': 'Local files, anchors, XML and recorded bytes; browser visual review is separate.',
            'passed': all(r['passed'] for r in rows), 'reports': rows,
            'validator_sha256': sha(Path(__file__))}
    target = ROOT / 'evidence/reference-v2-audit/report-readback.json'
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(data, ensure_ascii=False))
    raise SystemExit(0 if data['passed'] else 1)


if __name__ == '__main__':
    main()

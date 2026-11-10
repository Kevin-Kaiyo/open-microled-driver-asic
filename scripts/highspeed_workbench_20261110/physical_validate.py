"""Validate and record the physical workbench's compact, versioned delivery."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'docs/research/highspeed-workbench-20261110/physical'
EVID = ROOT / 'evidence/highspeed-workbench-20261110'
OUT = EVID / 'physical-delivery.json'


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'img':
            assert attrs['alt']
            self.refs.append(attrs['src'])
        if tag == 'a':
            self.refs.append(attrs['href'])


def main():
    sources = json.loads((EVID / 'physical-sources.json').read_text())
    blender = json.loads((EVID / 'physical-blender-checks.json').read_text())
    assert blender['reopened_saved_blend']
    core_checks = {item['route']: item for item in blender['checks']}
    for core in sources['cores']:
        for name, expected in core['source_sha256'].items():
            assert hash_file(ROOT / name) == expected, name
        check = core_checks[core['route']]
        assert check['polygons'] == core['selected_polygons']
        assert all(check[key] for key in ('exact_xy_vertices_in_original_dbu', 'nominal_z_metadata',
                                          'frame_1_connected', 'frame_60_exploded'))
    parser = References()
    parser.feed((DOC / 'index.html').read_text())
    local_refs = set()
    for ref in parser.refs:
        parts = urlsplit(ref)
        if parts.scheme:
            assert parts.scheme == 'https'
        elif not parts.path:
            assert parts.fragment in parser.ids, ref
        else:
            path = (DOC / parts.path).resolve()
            assert path.is_file() or path == OUT, ref
            local_refs.add(path.relative_to(ROOT).as_posix())

    assets = [DOC / f for f in ('index.html','actual-layout-2d.svg','tx-floorplan.svg','highspeed-cores.blend')]
    for name, size in [('actual-layout-2d.png', (2015, 1271)), ('core-a-3d.png', (1280, 1080)),
                       ('core-b-3d.png', (1280, 1080))]:
        path = DOC / name
        with Image.open(path) as image:
            assert image.size == size and image.format == 'PNG'
            image.verify()
        assets.append(path)
    for path in assets:
        if path.suffix == '.svg':
            assert ElementTree.parse(path).getroot().tag == '{http://www.w3.org/2000/svg}svg'
    inputs = [EVID / 'physical-sources.json', EVID / 'physical-blender-checks.json',
              *sorted(Path(__file__).parent.glob('physical_*.py'))]
    receipt = dict(schema_version=1, local_html_refs=sorted(local_refs),
                   historical_source_files_rechecked=sum(len(c['source_sha256']) for c in sources['cores']),
                   png_decode_and_size_check=True, svg_xml_parse=True,
                   artifacts={p.relative_to(ROOT).as_posix(): dict(bytes=p.stat().st_size, sha256=hash_file(p))
                              for p in assets + inputs})
    OUT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(f"Physical workbench verified: {len(assets)} assets, {len(local_refs)} local links, "
          f"{receipt['historical_source_files_rechecked']} original evidence hashes")


if __name__ == '__main__':
    main()

"""Check deliverable files, links, provenance and declared schematic boundaries.

This checks a research document, not a high-speed electrical design.
"""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
from urllib.request import urlopen
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/research/highspeed-driver-routes-20261019'
EVIDENCE = ROOT / 'evidence/highspeed-routes'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.images, self.ids = [], [], []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            self.ids.append(a['id'])
        if tag == 'a' and 'href' in a:
            self.links.append(a['href'])
        if tag == 'img':
            assert a.get('alt'), 'Image missing alt text'
            self.images.append(a['src'])

def main():
    p = Page()
    p.feed((OUT / 'index.html').read_text())
    assert len(p.ids) == len(set(p.ids)), 'Duplicate HTML ids'
    checked = []
    for raw in p.links + p.images:
        u = urlsplit(raw)
        if u.scheme or u.netloc:
            continue
        if u.path:
            path = OUT / unquote(u.path)
            assert path.is_file(), path
            checked.append(u.path)
        else:
            assert u.fragment in p.ids, raw
    sources = json.loads((OUT / 'evidence-sources.json').read_text())
    assert len(sources['records']) == 8
    assert all(r['primary_url'].startswith('https://') and r['locator'] for r in sources['records'])
    for asset in sources['local_files']:
        path = ROOT / asset['path']
        assert path.is_file() and sha(path) == asset['sha256'], path
    for image in p.images:
        assert not image.startswith('build/'), 'Private source imagery in report'
    svgs = list((OUT/'figures').glob('*.svg'))
    for path in svgs:
        ET.parse(path)
    metadata_path = OUT/'figures/circuit-metadata.json'
    metadata = json.loads(metadata_path.read_text())
    assert all(metadata['checks'].values())
    for entry in metadata['connections']:
        assert sha(OUT/'figures'/entry['file']) == entry['sha256'], entry['file']
    review = json.loads((EVIDENCE/'circuit-validation.json').read_text())
    amendments = []
    for old in review['checks']:
        path = OUT/'figures'/old['figure']
        current = sha(path)
        if current != old['sha256']:
            # C's unsupported subscript-i was replaced by ASCII i for PNG portability.
            restored = path.read_text()
            for a,b in [('ti =','tᵢ ='),('Gi+','Gᵢ+'),('Gi−','Gᵢ−'),('RDi','RDᵢ'),('MDi','MDᵢ'),('Gi±','Gᵢ±')]:
                restored = restored.replace(a,b)
            assert hashlib.sha256(restored.encode()).hexdigest() == old['sha256']
            amendments.append({'file':old['figure'], 'change':'subscript i to ASCII i; no geometry/net change',
                               'previous_sha256':old['sha256'], 'current_sha256':current})
    budget = json.loads((EVIDENCE/'analytical-budget-validation.json').read_text())
    assert budget['all_self_checks_pass']
    for path,h in budget['sha256'].items():
        assert sha(ROOT/path) == h, path
    package = json.loads((OUT/'package-concept.json').read_text())
    assert package['source_gds'] is None
    assert sha(OUT/'package-concept.blend') == package['scene_sha256']
    assert sha(ROOT/'scripts/highspeed_routes/package_concept.py') == package['script_sha256']
    http_checks = []
    for relative in sorted(set(checked + ['index.html'])):
        url = 'http://127.0.0.1:8771/highspeed-driver-routes-20261019/' + relative
        with urlopen(url, timeout=10) as r:
            assert r.status == 200
            assert int(r.headers['Content-Length']) == (OUT/relative).stat().st_size
        http_checks.append(relative)
    with urlopen('http://127.0.0.1:8772/', timeout=10) as r:
        assert r.status == 200
    result = {
        'date':'2026-10-19', 'pass':True,
        'scope':'Research diagrams and analytical teaching report; NOT electrical/physical/optical validation',
        'sources':len(sources['records']), 'private_source_files_hash_verified':len(sources['local_files']),
        'svg_xml_files':len(svgs), 'image_references':len(p.images),
        'local_file_links_verified':sorted(set(checked)), 'http_files_200_and_length_verified':http_checks,
        'conceptual_mos_count':review['device_count'], 'drawing_lead_review_count':review['d_g_s_lead_count'],
        'analytical_self_checks':budget['self_check_count'], 'schematic_label_amendments':amendments,
        'original_schematic_review_preserved':'circuit-validation.json',
        'rasterizer':'CairoSVG 2.8.2; system Cairo; Arial Unicode MS for PNG; SVG preferred font unchanged',
        'review_repairs':['Unified PAM4 thermometer order with drawing: 000/100/110/111',
                          'Corrected DLC source locator to Fig2 and section IV-B/Fig7',
                          'Clarified differential gate common mode and swing',
                          'Separated candidate PDK choice from evidence-based process acceptance'],
        'deliverable_hashes':{str(path.relative_to(ROOT)):sha(path) for path in sorted(OUT.rglob('*')) if path.is_file()},
        'generator_hashes':{str(path.relative_to(ROOT)):sha(path) for path in sorted((ROOT/'scripts/highspeed_routes').glob('*.py'))}
    }
    (EVIDENCE/'report-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['pass','sources','private_source_files_hash_verified','svg_xml_files','image_references','analytical_self_checks']},ensure_ascii=False))

if __name__ == '__main__':
    main()

"""Verify the editorial scope revision and its independent arithmetic examples."""
from pathlib import Path
from fractions import Fraction
from datetime import datetime
import argparse
import hashlib
import json
import re
import subprocess
import unicodedata
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'evidence/methodology/validation.json'
BASELINE = 'b4b28d613c51c444c83cd322d0b7ec7fe303fa43'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--main-pages-reviewed', type=int, required=True)
    parser.add_argument('--methods-pages-reviewed', type=int, required=True)
    args = parser.parse_args()
    checks = []

    def check(name, value):
        checks.append({'name': name, 'passed': bool(value)})
        if not value:
            raise RuntimeError(name)

    active = list((ROOT / 'docs').rglob('*.md')) + [ROOT / 'README.md', ROOT / 'AGENTS.md']
    forbidden = re.compile(r'EVIYOS|画芯|晶合光电|LP5860|JBD|对标|benchmark|商业对照', re.I)
    matches = [str(p.relative_to(ROOT)) for p in active if forbidden.search(p.read_text())]
    check('Current Markdown has no product-comparison objectives', not matches)
    missing = []
    for p in active + [ROOT / 'evidence/strategy/README.md']:
        for href in re.findall(r'\]\(([^)]+)\)', p.read_text()):
            if '://' in href or href.startswith('#') or ' ' in href:
                continue
            target = (p.parent / href.split('#')[0].strip('<>')).resolve()
            if target != OUT and not target.exists():
                missing.append([str(p.relative_to(ROOT)), href])
    check('Current documentation local links resolve', not missing)
    check('Superseded product-study artifacts removed from current tree',
          not list((ROOT / 'docs/research/automotive').glob('*')) and
          not list((ROOT / 'evidence/automotive').glob('*')) and
          not any((ROOT / 'scripts/research' / n).exists() for n in
                  ['render_automotive.py', 'print_automotive.cjs', 'verify_automotive.py']))

    old = json.loads(subprocess.check_output(['git', 'show', BASELINE + ':evidence/research/current-manifest.json'], cwd=ROOT))
    protected = ('analog/', 'rtl/', 'sim/', 'layout/', 'scripts/characterization/', 'scripts/digital/',
                 'scripts/physical/', 'scripts/layout/', 'scripts/integration/', 'scripts/interface/',
                 'scripts/joint_pex/', 'scripts/robustness/', 'evidence/characterization/',
                 'evidence/digital/', 'evidence/layout/', 'evidence/physical/', 'evidence/integration/',
                 'evidence/interface/', 'evidence/joint-pex/', 'evidence/robustness/', 'evidence/led-fit/')
    engineering = {n: h for n, h in old['current_file_hashes'].items() if n.startswith(protected)}
    check('Existing engineering inputs and outputs unchanged', bool(engineering) and
          all(sha(ROOT / n) == h for n, h in engineering.items()))
    for name in ['evidence/strategy/sources.json', 'evidence/strategy/claim-ledger.json',
                 'evidence/strategy/validation.json', 'evidence/research/v04-review.json']:
        check('As-run historical record preserved: ' + name, sha(ROOT / name) == old['current_file_hashes'][name])

    revisions = json.loads((ROOT / 'evidence/methodology/document-revisions.json').read_text())
    for name, item in revisions['historical_strategy_documents'].items():
        original = subprocess.check_output(['git', 'show', item['original_commit'] + ':' + name], cwd=ROOT)
        check('Explicit historical prose identity: ' + name, hashlib.sha256(original).hexdigest() == item['original_sha256'])
        check('Explicit current prose identity: ' + name, sha(ROOT / name) == item['current_sha256'])

    budgets = []
    for n in [1, 16, 256]:
        budgets.append({'logical_positions': n, 'command_bits': 12, 'packed_bytes': (n * 12 + 7) // 8,
                        'double_buffer_bytes': 2 * ((n * 12 + 7) // 8),
                        'payload_bps_60hz': n * 12 * 60, 'payload_bps_100hz': n * 12 * 100})
    check('Buffer and payload independent calculations',
          [b['packed_bytes'] for b in budgets] == [2, 24, 384] and
          [b['double_buffer_bytes'] for b in budgets] == [4, 48, 768] and
          [b['payload_bps_60hz'] for b in budgets] == [720, 11520, 184320] and
          [b['payload_bps_100hz'] for b in budgets] == [1200, 19200, 307200])
    check('Illustrative link efficiency budget', Fraction(184320) / Fraction(8, 10) == 230400)
    errors = []
    for bits in [10, 12]:
        denominator = (1 << bits) - 1
        maximum = max(abs(Fraction((512 * g + denominator) // (2 * denominator), 256)
                          - Fraction(g, denominator)) for g in range(denominator + 1))
        check(f'{bits}-bit command quantization bound', maximum <= Fraction(1, 512))
        errors.append({'bits': bits, 'codes': denominator + 1, 'max_normalized_error': float(maximum)})

    review = json.loads((ROOT / 'evidence/methodology/independent-review.json').read_text())
    check('Independent scope review passed', review['passed'] is True)
    for name, expected in review['reviewed_file_sha256'].items():
        check('Reviewed document identity: ' + name, sha(ROOT / name) == expected)
    pdfs = {}
    for name, count, reviewed, layout in [
        ('docs/research/research-report.pdf', 28, args.main_pages_reviewed, 'build/research-report/layout-check.json'),
        ('docs/research/experimental-methods/report.pdf', 9, args.methods_pages_reviewed, 'build/experimental-methods/report/layout-check.json')]:
        reader = PdfReader(ROOT / name)
        text = '\n'.join(unicodedata.normalize('NFKC', p.extract_text()) for p in reader.pages)
        check('PDF reviewed page count: ' + name, len(reader.pages) == count == reviewed)
        check('PDF product-comparison text absent: ' + name, not forbidden.search(text))
        check('PDF text extraction complete: ' + name, '\ufffd' not in text and all(len(p.extract_text()) > 250 for p in reader.pages))
        geometry = json.loads((ROOT / layout).read_text())
        check('PDF A4 geometry: ' + name, len(geometry['sections']) == count and not geometry['overflow']
              and all(s['height'] <= 970 for s in geometry['sections']))
        pdfs[name] = {'sha256': sha(ROOT / name), 'pages': count, 'visual_pages_reviewed': list(range(1, count + 1))}

    files = [ROOT / 'README.md', ROOT / 'AGENTS.md', ROOT / 'docs/project-brief.md', ROOT / 'docs/design.md',
             ROOT / 'docs/roadmap.md', ROOT / 'docs/research/README.md', ROOT / 'docs/research/bench-validation-plan.md',
             ROOT / 'docs/research/technical-value-market.md', ROOT / 'docs/research/research-report.md',
             ROOT / 'docs/research/research-report.html', ROOT / 'docs/research/research-report.pdf',
             ROOT / 'evidence/strategy/README.md']
    files += list((ROOT / 'docs/research/experimental-methods').glob('*'))
    files += [p for p in (ROOT / 'evidence/methodology').glob('*.json') if p != OUT]
    files += [ROOT / 'scripts/research' / n for n in ['render_methods.py', 'print_methods.cjs', 'verify_methods.py',
                                                   'verify_current.py', 'verify_v04_assets.py']]
    result = {'date': datetime.now().astimezone().isoformat(), 'passed': True,
              'scope': 'Editorial positioning, document consistency, historical identity and independent budget arithmetic',
              'project_scope': 'Experimental R&D methodology validation and teaching',
              'engineering_stage': 'one-pixel v0.4', 'new_engineering_or_hardware_validation': False,
              'engineering_files_unchanged': len(engineering), 'checks': checks,
              'budget_assumptions': budgets, 'quantization_calculations': errors, 'pdfs': pdfs,
              'historical_records': 'Prior source/claim and numerical review receipts remain as-run; current project scope is defined by revised documentation.',
              'files_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sorted(set(files))}}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'PASS {len(checks)} documentation and arithmetic checks; {len(engineering)} engineering files unchanged')


if __name__ == '__main__':
    main()

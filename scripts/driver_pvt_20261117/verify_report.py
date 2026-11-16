#!/usr/bin/env python3
"""Check rendered report identity, page geometry, and essential results."""
import hashlib
import json
from pathlib import Path
import re

import pdfplumber
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
TAG = 'driver-pvt-20261117'
DOCS = ROOT / 'docs/research' / TAG
EVIDENCE = ROOT / 'evidence' / TAG


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    source = DOCS / 'technical-stage-report.pdf'
    browser = json.loads((EVIDENCE / 'report-browser.json').read_text())
    audit = json.loads((EVIDENCE / 'validation.json').read_text())
    assert browser['passed'] and audit['passed'] and audit['mode'] == 'final'
    assert sha(source) == browser['pdf_sha256']
    assert sha(DOCS / 'index.html') == browser['html_sha256']
    pdf = PdfReader(source)
    text = re.sub(r'\s+', '', '\n'.join(p.extract_text() for p in pdf.pages))
    for token in ['1.319%', '214.40', '1.387%', '5.073', '0.40962', '1.116', '5.901', '8.8', '1.02847']:
        assert token in text, token
    outliers = []
    with pdfplumber.open(source) as doc:
        for number, page in enumerate(doc.pages, 1):
            assert abs(page.width - 595.28) < 1 and abs(page.height - 841.89) < 1, number
            for char in page.chars:
                if not char['text'].strip():
                    continue
                if char['x0'] < -1 or char['x1'] > page.width + 1 or char['top'] < -1 or char['bottom'] > page.height + 1:
                    outliers.append([number, char['text']])
    assert not outliers, outliers[:12]
    result = {'passed': True, 'pages': len(pdf.pages), 'A4': True, 'unicode_text_extractable': True,
              'outside_page_text': outliers, 'pdf_sha256': sha(source),
              'source_markdown_sha256': sha(DOCS / 'README.md'),
              'audited_simulation_cases': audit['cases_checked']}
    (EVIDENCE / 'report-validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()

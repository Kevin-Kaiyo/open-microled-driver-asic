"""Freeze v0.4 public artifacts against their actual extraction and run receipts.

This validates identities and stated coverage. Independent circuit and numeric
reasoning is recorded by review_v04.py, rather than repeated with runner helpers.
Long waveforms stay local; their recorded hashes are verified here as well.
"""
from pathlib import Path
import gzip
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]


def verify(check, report):
    cache = {}

    def digest(path):
        path = Path(path)
        if path not in cache:
            with path.open('rb') as stream:
                cache[path] = hashlib.file_digest(stream, 'sha256').hexdigest()
        return cache[path]

    def read(name):
        return json.loads((ROOT / name).read_text())

    def hashes(mapping, base=ROOT, label='v0.4 input'):
        for name, expected in mapping.items():
            check(label + ' ' + name, digest(base / name) == expected)

    pex = read('evidence/joint-pex/summary.json')
    styles = ('nominal', 'hrhc', 'lrhc', 'hrlc', 'lrlc')
    check('Five actual PDK RC styles', pex['passed'] is True and set(pex['styles']) == set(styles))
    hashes(pex['packaging_source_sha256'], label='Joint PEX package source')
    for style in styles:
        item = pex['styles'][style]
        base = ROOT / 'evidence/joint-pex'
        check('Joint model identity ' + style, digest(base / item['model']) == item['model_sha256'])
        check('Joint summary identity ' + style, digest(base / item['summary']) == item['summary_sha256'])
        data = read('evidence/joint-pex/' + item['summary'])
        check('Selected actual circuit ' + style,
              data['passed'] is True and data['counts']['selected_MOS'] == 12 and
              data['counts']['selected_R'] == 45 and data['counts']['selected_C'] == 77 and
              len(data['ports']) == 44 and len(data['neighbors']) == 34)
        check('No negative signal capacitor clipping ' + style,
              data['passivity']['negative_dynamic_pairs'] == 0 and
              len(data['negative_capacitors']) == 19 and
              all(c['action'] == 'fixed_pg_only_remove' and
                  set(c['mapped']) <= {'VDD', 'VSS'} for c in data['negative_capacitors']))
        hashes(data['inputs_sha256'], label='Actual PEX source ' + style)
        hashes(data['as_run_outputs_sha256'], ROOT / data['as_run_output_directory'],
               'Original exporter output ' + style)
        hashes(data['public_artifacts_sha256'], base / style, 'Public PEX output ' + style)
        raw = gzip.decompress((base / style / 'projection-ledger.json.gz').read_bytes())
        check('Projection ledger decompresses exactly ' + style,
              hashlib.sha256(raw).hexdigest() == data['as_run_outputs_sha256']['projection-ledger.json'])
    method = read('evidence/joint-pex/extraction-method.json')
    check('Extraction belongs to frozen common GDS', method['passed'] is True and
          method['input_gds_sha256'] == digest(ROOT / 'evidence/integration/pixel_integrated.gds'))
    hashes({method['rc_deck']['path']: method['rc_deck']['sha256']}, label='Actual RC rule deck')
    for name, record in method['records'].items():
        extraction = record['extraction']
        check('Native extraction completed ' + name, extraction['passed'] is True)
        check('Native extraction binary ' + name,
              digest(Path(extraction['argv'][0])) == extraction['tool_binary_sha256'])
        hashes(extraction['inputs_sha256'], label='Native extraction input ' + name)
        outputs = extraction['output_sha256'] if name == 'hierarchical-nominal' else extraction['outputs_sha256']
        hashes(outputs, ROOT / record['run'], 'Native extraction output ' + name)
    for name, archive in method['public_archives'].items():
        path = ROOT / 'evidence/joint-pex' / name
        check('Public raw archive ' + name, digest(path) == archive['public_sha256'])
        check('Archive preserves raw bytes ' + name,
              hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest() ==
              archive['decompressed_sha256'] == digest(ROOT / archive['source_path']))
    fresh = read('evidence/joint-pex/reproduction.json')
    check('Fresh extraction preserves complete circuit graph', fresh['passed'] is True and
          fresh['ordered_ports_identical'] is True and fresh['exact_geometric_multiset_identical'] is True)
    check('Fresh extraction reports actual byte differences',
          fresh['raw_bytes_identical'] is False and fresh['model_bytes_identical'] is False)
    check('Fresh reproduction detects all three mutations', len(fresh['negative_controls']) == 3 and
          all(v['rejected'] for v in fresh['negative_controls'].values()))
    hashes(fresh['inputs_sha256'], label='Fresh extraction input')

    regression = read('evidence/robustness/summary.json')
    hashes(regression['source_hashes'], label='Joint electrical executed source')
    check('Electrical packager identity', digest(ROOT / 'scripts/robustness/publish.py') == regression['packager_sha256'])
    check('Actual total run counts', regression['counts'] ==
          {'transient_runs': 66, 'dc_circuit_runs': 28, 'synthetic_LED_calibration_runs': 3})
    check('Predeclared engineering checks passed', regression['normative_engineering_guards_passed'] is True and
          regression['normative_checks_count'] == 146)
    check('Boundary studies not promoted to qualification',
          regression['boundary_studies_completed_numerically'] is True and
          regression['boundary_studies_are_system_qualification'] is False)
    scope = regression['scope']
    check('Electrical scope excludes full PG and unmeasured dynamics',
          scope['joint_extracted_signal_RC_with_actual_MOS_junctions'] is True and
          all(scope[k] is False for k in ['full_joint_cell_PG_PEX', 'PG_only_capacitance_included',
              'body_PG_series_R_included', 'full_digital_transistor', 'real_reference_generator',
              'real_LED_dynamic', 'full_PG_or_substrate', 'preceding_FF_waveform']))
    check('Actual measured-static supply failure remains a failure',
          len(regression['measured_static_supply_boundary']) == 4 and
          regression['measured_static_supply_boundary'][-1]['series_LED_R_ohm'] == 10000 and
          regression['measured_static_supply_boundary'][-1]['full_on_5pct_target_met'] is False)
    manifest = read('evidence/robustness/manifest.json')
    hashes(manifest['files_sha256'], label='Public electrical output')
    for group, expected_counts in [('probe', (10, 12)), ('main', (37, 12)), ('boundary', (19, 4))]:
        batch = regression['batches'][group]
        check('Batch receipt identity ' + group, digest(ROOT / batch['summary_path']) == batch['summary_sha256'])
        data = read(batch['summary_path'])
        check('Batch actually completed ' + group, data['completed_numerically'] is True and
              (data['transient_runs'], data['dc_runs']) == expected_counts)
        check('Batch calibration ' + group, data['synthetic_LED_calibration']['passed'] is True)
        if group != 'boundary':
            check('Batch prescribed guards ' + group, data['passed'] is True and all(c['passed'] for c in data['checks']))
        hashes(data['source_hashes'], label='Batch frozen source ' + group)
        hashes(data['PDK_models_sha256'], ROOT / 'build/layout/pdk/gf180mcuD/libs.tech/ngspice', 'Executed BSIM model ' + group)
        hashes(data['contract']['required_inputs_sha256'], label='Batch joint contract ' + group)
        hashes(data['raw_artifacts_sha256'], ROOT / data['run_directory'], 'Actual electrical raw ' + group)
    for item in regression['teaching_waveform_slices']:
        hashes({item['path']: item['sha256'], item['source_waveform']: item['source_waveform_sha256']},
               label='Teaching actual waveform provenance')

    review = read('evidence/research/v04-review.json')
    required = {'budget', 'PEX_nominal', 'PEX_hrhc', 'PEX_lrhc', 'PEX_hrlc', 'PEX_lrlc',
                'waveform_probe', 'raw_hierarchy_scope', 'waveform_main', 'fresh_reproduction',
                'endpoint_controls', 'waveform_boundary', 'terminal_power'}
    check('Independent final v0.4 review completed', review['passed'] is True and
          required <= set(review['stages']) and all(s['passed'] for s in review['stages'].values()))
    check('Independent review source identity', digest(ROOT / 'scripts/research/review_v04.py') == review['review_source_sha256'])
    for style in styles:
        controls = review['stages']['PEX_' + style]['negative_controls']
        check('Actual circuit mutants rejected ' + style, len(controls) == 3 and all(c['rejected'] for c in controls))
        for control in controls:
            hashes({control['raw_path']: control['mutant_sha256']}, label='Preserved independent mutant')

    def review_hash_maps(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key.endswith(('hashes', 'sha256')) and isinstance(value, dict):
                    paths = {n: h for n, h in value.items() if '/' in n and isinstance(h, str)
                             and re.fullmatch(r'[0-9a-f]{64}', h)}
                    hashes(paths, label='Independent review recorded input')
                review_hash_maps(value)
        elif isinstance(node, list):
            for value in node:
                review_hash_maps(value)
    review_hash_maps(review)
    for name in ['v04-probe-recomputed.json', 'v04-main-recomputed.json', 'v04-boundary-recomputed.json']:
        check('Independent original raw recalculation ' + name, read('evidence/research/' + name)['passed'] is True)

    strategy = read('evidence/strategy/validation.json')
    check('Strategy arithmetic and primary-source validation', strategy['passed'] is True and
          len(strategy['checks']) == 57 and all(c['passed'] for c in strategy['checks']))
    hashes(strategy['artifacts_sha256'], label='Frozen value and market evidence')
    teaching = read('evidence/teaching/figures.json')
    check('Concept figures not called measurements', teaching['physical_measurement'] is False)
    hashes(teaching['source_sha256'], label='Teaching calculation source')
    hashes(teaching['outputs_sha256'], label='Teaching figure')
    check('Twenty-eight layered report sections', len(report.split('<!-- page -->')) == 28 and
          re.findall(r'^## (\d{2}) ', report, re.M) == [f'{i:02d}' for i in range(1, 29)])
    html = (ROOT / 'docs/research/research-report.html').read_text()
    check('Four working report navigation anchors', all(f'href="#section-{n}"' in html and
          f'id="section-{n}"' in html for n in ['01', '02', '08', '24']))
    layout = read('build/research-report/layout-check.json')
    check('Final A4 report fits without overflow', layout['report_version'] == 'v0.4' and
          len(layout['sections']) == 28 and not layout['overflow'] and
          all(s['height'] <= 970 for s in layout['sections']))

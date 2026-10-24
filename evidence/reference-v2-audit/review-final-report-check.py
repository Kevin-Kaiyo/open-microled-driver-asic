#!/usr/bin/env python3
"""Read-only report checks; only the resulting audit JSON is written.

This runs after independent raw analysis. It does not import report generators,
simulation runners, or analyzers. A later report rebuild may legitimately change
HTML/provenance hashes when review-final.md is incorporated; inputs are a snapshot.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix('.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text())


aud = read('evidence/reference-v2-audit/review-final-pwm-check.json')
rows = {x['name']: x for x in aud['records']}
pwm = ROOT / 'docs/research/pwm-reference-startup-20261024'
text = (pwm / 'results.md').read_text()
display = {
    'nominal_excursion_percent': f"{rows['c15_step']['excursion_pct']:.4f}%",
    'nominal_restore_us': f"{rows['c15_step']['settle_s'] * 1e6:.3f} µs",
    'TT_hold_peak_pA': f"{rows['c15_startup_fullmesh_trap']['held_peak_a'] * 1e12:.3f} pA",
    'SS_recovered_uA': f"{rows['c15_startup_ss_slow']['recovered_a'] * 1e6:.4f} µA",
    'fault_safe_ns': f"{rows['c15_fault']['fault_to_safe_s'] * 1e9:.2f} ns",
    'fault_positive_pC': f"{rows['c15_fault']['fault_charge']['positive_c'] * 1e12:.4f}",
    'fault_negative_pC': f"{rows['c15_fault']['fault_charge']['negative_c'] * 1e12:.4f}",
    'PWM_error_percent': f"{rows['c15_pwm']['d1_charge_error_pct']:.4f}%",
    'PWM_charge_pC': f"{rows['c15_pwm']['d1_charge_c'] * 1e12:.4f} pC",
    'old_100n_SS_recovery_uA': f"{rows['damped_startup_ss_slow']['recovered_a'] * 1e6:.4f} µA",
    'old_47n_SS_startup_uA': f"{rows['c47_startup_ss_slow']['recovered_a'] * 1e6:.4f} µA",
    'old_47n_SS_fast_restore_us': f"{rows['c47_dyn_ss_mmm']['settle_s'] * 1e6:.3f} µs",
    'old_47n_SS_slow_restore_us': f"{rows['c47_dyn_ss_ppp']['settle_s'] * 1e6:.3f} µs",
}
dyn = [r for n, r in rows.items() if n.startswith('c15_dyn_')]
assert len(dyn) == 12
display['dynamic_excursion_percent'] = f"{max(r['excursion_pct'] for r in dyn):.4f}%"
display['dynamic_restore_us'] = f"{max(r['settle_s'] for r in dyn) * 1e6:.4f} µs"
for label, value in display.items():
    assert value in text, (label, value)
for phrase in ['TT 名义供电', 'TT 名义恢复', 'TT 名义启动近零保持窗',
               '144', '不写成全部以 15 nF 重跑', '100 Ω / 15 nF',
               '27 个', '12 点', '100 nF', '47 nF', '超过同一个 5 µs',
               '40 µs', '258.5–514.5 µs', '不代表已经预测或测量了 pA 级硅片漏电',
               '没有覆盖任意同时上电顺序']:
    assert phrase in text, phrase

provenance = []
for stem in ['pwm-reference-startup-20261024', 'nrz-b-reference-power-20261024']:
    base = ROOT / 'docs/research' / stem
    p = base / 'report-provenance.json'
    manifest = json.loads(p.read_text())
    records = []
    for rel, expected in manifest['inputs'].items():
        target = ROOT / rel
        assert sha(target) == expected, target
        records.append({'path': rel, 'sha256': expected})
    for rel, expected in manifest['figures'].items():
        target = base / rel
        assert sha(target) == expected, target
        records.append({'path': str(target.relative_to(ROOT)), 'sha256': expected})
    for name, field in [('report-complete.md', 'markdown_sha256'),
                        ('index.html', 'html_sha256')]:
        assert sha(base / name) == manifest[field]
    assert sha(ROOT / 'scripts/reference_v2_report/build_report.py') == manifest['generator_sha256']
    provenance.append({'report': stem, 'manifest_sha256': sha(p),
                       'verified_inputs_and_figures': records,
                       'markdown_sha256': manifest['markdown_sha256'],
                       'html_sha256': manifest['html_sha256']})

raster = read('evidence/reference-v2-audit/schematic-raster-identity.json')
for r in raster['figures']:
    assert sha(ROOT / r['svg']) == r['svg_sha256']
    assert sha(ROOT / r['png']) == r['png_sha256']
data = json.loads((pwm / 'figures/results-data.json').read_text())
assert data['selected_acceptance'] and data['selected_cases'] == 27
assert sha(ROOT / 'scripts/reference_v2_report/summarize_pwm.py') == data['generator_sha256']
for path, expected in data['inputs'].items():
    assert sha(ROOT / path) == expected

visual_paths = [
    'docs/research/pwm-reference-startup-20261024/figures/external-network.png',
    'docs/research/pwm-reference-startup-20261024/figures/matched-board-step.png',
    'docs/research/pwm-reference-startup-20261024/electrical-figures/启动保持与许可.png',
    'docs/research/nrz-b-reference-power-20261024/figures/body-junction-powerdown.png',
]
result = {
    'script_sha256': sha(Path(__file__)),
    'independent_pwm_raw_audit_sha256': sha(ROOT / 'evidence/reference-v2-audit/review-final-pwm-check.json'),
    'scope': 'Current report text, source manifests and image pair identities; raw calculations performed by separate independent audit. No simulation.',
    'displayed_numbers_matched_to_independent_raw_calculations': display,
    'TT_hold_scope_label_fixed': True,
    'FF_fast_hold_peak_pA_for_scope_comparison': rows['c15_startup_ff_fast']['held_peak_a'] * 1e12,
    'report_provenance_snapshot': provenance,
    'schematic_raster_pairs_verified': len(raster['figures']),
    'PWM_results_data_inputs_current': True,
    'visual_inspection': {
        'image_sha256': {path: sha(ROOT / path) for path in visual_paths},
        'outcome': 'Viewed rendered pixels: readable Chinese, no cropping. Final PWM board network is 15 nF with 10 ohm damping; startup shows total and conductive currents, negative pulses, and full 40 us. NRZ body figure now says 结压 and has no missing Δ glyph.',
        'body_junction_finding_closed': True,
        'geometry_or_circuit_changed': False,
    },
    'historical_failures_retained': ['100 nF SS startup', '47 nF SS fast and slow dynamic recovery', 'NRZ four current-target failures', 'NRZ early-release 03v3 overvoltage and ready failure', 'NRZ residual-restart body-forward risk'],
    'handoff_note': 'review-final.md will be updated after this snapshot, so final packaging must rebuild report-provenance.json to bind that final review. This is an expected last-stage dependency, not a source identity mismatch.',
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'display_metrics': len(display), 'reports': len(provenance),
                  'raster_pairs': len(raster['figures']), 'status': 'passed'}, ensure_ascii=False))

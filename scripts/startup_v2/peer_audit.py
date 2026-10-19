"""Read-only independent arithmetic audit of the frozen startup-v2 experiment.

Never imports the experiment runner or runs EDA. A data-integrity PASS preserves
the original experiment failure. NumPy reads raw vectors; zero-crossing charge
integration uses independently constructed panels and math.fsum.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ENV = {'tt': (3.3, 5.0), 'ss': (2.97, 4.5), 'ff': (3.63, 5.5)}
REF = [
    ('XPBIAS', 'pb', 'pb', 'refrail', 'refrail'),
    ('XPTAIL', 'tail', 'pb', 'refrail', 'refrail'),
    ('XPD1', 'n1', 'vset', 'tail', 'refrail'),
    ('XPD2', 'n2', 'sense', 'tail', 'refrail'),
    ('XND1', 'n1', 'n1', '0', '0'), ('XND2', 'n2', 'n1', '0', '0'),
    ('XNSTAGE', 'ctrl', 'n2', '0', '0'),
    ('XPLOAD', 'ctrl', 'ctrl', 'refrail', 'refrail'),
    ('XPREG', 'sense', 'ctrl', 'refrail', 'refrail'),
    ('XPOUT', 'refout', 'ctrl', 'refrail', 'refrail'),
]
SAFE = [
    ('XFN', 'fault_b', 'fault', '0', '0'),
    ('XFP', 'fault_b', 'fault', 'vdd', 'vdd'),
    ('XNP0', 'nand_n', 'raw', 'vdd', 'vdd'),
    ('XNP1', 'nand_n', 'permit', 'vdd', 'vdd'),
    ('XNP2', 'nand_n', 'fault_b', 'vdd', 'vdd'),
    ('XNN0', 'nand_n', 'raw', 'stack1', '0'),
    ('XNN1', 'stack1', 'permit', 'stack2', '0'),
    ('XNN2', 'stack2', 'fault_b', '0', '0'),
    ('XON', 'out', 'nand_n', '0', '0'),
    ('XOP', 'out', 'nand_n', 'vdd', 'vdd'),
]
ISO = [
    ('XFN', 'fault_b', 'fault', '0', '0'),
    ('XFP', 'fault_b', 'fault', 'vdd', 'vdd'),
    ('XISO', 'isolator_in', 'fault_b', 'bias', '0'),
    ('XPISO', 'bias', 'fault', 'isolator_in', 'vdd'),
    ('XDIS', 'bias', 'fault', '0', '0'),
]
CLAMP = [('XLN0', 'hb', 'fault', '0', '0'),
         ('XCP', 'cathode', 'hb', 'anode', 'anode')]
PMOS = {'XPBIAS', 'XPTAIL', 'XPD1', 'XPD2', 'XPLOAD', 'XPREG', 'XPOUT',
        'XFP', 'XNP0', 'XNP1', 'XNP2', 'XOP', 'XPISO', 'XCP'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bounded(time, value, left, right):
    mask = (time > left) & (time < right)
    return (np.r_[left, time[mask], right],
            np.r_[np.interp(left, time, value), value[mask],
                  np.interp(right, time, value)])


def charges(time, value, left, right):
    x, y = bounded(time, value, left, right)
    crossing = np.flatnonzero(y[:-1] * y[1:] < 0)
    roots = (x[crossing] + (x[crossing + 1] - x[crossing]) *
             abs(y[crossing]) / (abs(y[crossing]) + abs(y[crossing + 1])))
    panels = np.sort(np.r_[x, roots])
    values = np.interp(panels, x, y)
    areas = np.diff(panels) * (values[:-1] + values[1:]) / 2
    return {'positive_c': math.fsum(areas[areas > 0]),
            'negative_c': math.fsum(areas[areas < 0]),
            'signed_c': math.fsum(areas)}


def close(actual, expected, absolute=1e-25):
    return abs(actual - expected) <= max(absolute, abs(expected) * 1e-8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path,
                        default=ROOT / 'evidence/startup-v2/summary.json')
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'evidence/startup-v2/peer-audit.json')
    args = parser.parse_args()
    summary_path = args.summary.resolve()
    summary_hash = sha(summary_path)
    summary = json.loads(summary_path.read_text())
    raw = ROOT / summary['raw_directory']
    contract = json.loads((raw / 'inputs/evidence/safety/contract.json').read_text())
    limits = contract['thresholds']
    checks, cache, body, closure, terminal_max, reference_extrema, rtl_counts = [], {}, [], [], [], [], []

    def check(name, passed, **details):
        checks.append(dict(name=name, passed=bool(passed), **details))

    def window(time, vectors, recorded, name):
        left, right = recorded['left_s'], recorded['right_s']
        branch = vectors['i(VLEDLOAD)']
        cap = vectors['@d.xled.dled[capcur]']
        cond = vectors['@d.xled.dled[id]'] - cap
        _, b = bounded(time, branch, left, right)
        _, c = bounded(time, cond, left, right)
        _, cp = bounded(time, cap, left, right)
        for key, actual in [('branch_max_abs_a', np.max(abs(b))),
                            ('branch_min_a', np.min(b)), ('branch_max_a', np.max(b)),
                            ('conduction_max_abs_a', np.max(abs(c))),
                            ('capacitance_max_abs_a', np.max(abs(cp)))]:
            check(name + '/' + key, close(actual, recorded[key]))
        for field, vector in [('branch_charge', branch), ('conduction_charge', cond),
                              ('capacitance_charge', cap)]:
            for key, actual in charges(time, vector, left, right).items():
                check(name + '/' + field + '/' + key, close(actual, recorded[field][key]))

    for name, expected in summary['source_sha256'].items():
        check('frozen source/' + name, sha(raw / 'inputs' / name) == expected)
        check('current source/' + name, sha(ROOT / name) == expected)
    check('run counts', summary['transient_runs'] == len(summary['results']) and
          summary['dc_runs'] == len(summary['dc_results']))

    for result in summary['results']:
        name = result['name']
        condition = result['conditions']
        folder = raw / name
        for filename, key in [('waveform.dat', 'raw_sha256'), ('waveform.csv', 'csv_sha256'),
                              ('testbench.spice', 'deck_sha256'), ('rtl-events.csv', 'rtl_sha256')]:
            check(name + '/hash/' + filename, sha(folder / filename) == result[key])
        if result.get('csvpath'):
            check(name + '/published CSV', sha(ROOT / result['csvpath']) == result['csv_sha256'])
        with (folder / 'waveform.dat').open() as stream:
            columns = stream.readline().split()
        data = np.loadtxt(folder / 'waveform.dat', skiprows=1)
        time = data[:, 0]
        vectors = {column: data[:, index] for index, column in enumerate(columns)}
        branch = vectors['i(VLEDLOAD)']
        cache[name] = (result, time, branch)
        check(name + '/finite monotonic complete', np.isfinite(data).all() and
              np.all(np.diff(time) > 0) and time[0] == 0 and
              abs(time[-1] - condition['stop_ns'] * 1e-9) < 1e-15)
        check(name + '/classification', result['passed'] == all(c['passed'] for c in result['checks']))
        for field in ['startup', 'fault_release_before_permit', 'permit_before_raw',
                      'recovered_dc_window', 'fault', 'held_fault', 'fault_removal_stopped_clock']:
            if field in result:
                window(time, vectors, result[field], name + '/' + field)
        for index, recorded in enumerate(result.get('startup_slices', [])):
            window(time, vectors, recorded, name + '/slice/' + str(index))
        kind = condition['kind']

        def guard(label, expected):
            recorded = next(c for c in result['checks'] if c['name'] == label)
            check(name + '/guard/' + label, recorded['passed'] == bool(expected))

        if kind == 'startup':
            peak_pass = result['startup']['branch_max_abs_a'] < limits['fault_safe_current_abs_a']
            label = ('Unchanged all-startup 1nA branch peak guard' if condition['isolated'] else
                     'Original all-startup failure is reproduced')
            recorded = next(c for c in result['checks'] if c['name'] == label)
            check(name + '/honest startup guard', recorded['passed'] ==
                  (peak_pass if condition['isolated'] else not peak_pass))
            average = charges(time, branch, 30e-6, 40e-6)['signed_c'] / 10e-6
            recorded = next(c for c in result['checks'] if c['name'] ==
                            'Explicitly recovered full current within 5%')
            check(name + '/recovered average', close(average, recorded['average_a']))
            check(name + '/recovered guard', recorded['passed'] == (abs(average / 100e-6 - 1) < .05))
            _, release_input = bounded(time, vectors['v(input)'], 20e-6, 21.5e-6)
            guard('Fault release alone cannot pass PWM before permit', np.max(abs(release_input)) < .01)
            guard('Model conduction remains below 1nA before permit',
                  result['fault_release_before_permit']['conduction_max_abs_a'] < 1e-9)
        elif kind == 'normal':
            charge = charges(time, branch, 514.5e-6, 1026.5e-6)['signed_c']
            error = (charge / (512e-6 * result['dc_full_a'] / 256) - 1) * 100
            check(name + '/normal charge', close(charge, result['charge_c']))
            check(name + '/normal area error', abs(error - result['area_error_pct']) < 1e-7)
            guard('Unchanged d1 2% charge guard', abs(error) <= 2)
        else:
            fault = condition['fault_ns'] * 1e-9
            x, y = bounded(time, abs(branch), fault, fault + 3e-6)
            over = np.flatnonzero(y > limits['fault_safe_current_abs_a'])
            if not len(over):
                settled = fault
            elif over[-1] == len(y) - 1:
                settled = None
            else:
                j = over[-1]
                settled = x[j] + (limits['fault_safe_current_abs_a'] - y[j]) * (x[j + 1] - x[j]) / (y[j + 1] - y[j])
            delay = None if settled is None else settled - fault
            check(name + '/stable current delay', delay is not None and close(delay, result['fault_to_safe_s']))
            average = charges(time, branch, time[-1] - 3e-6, time[-1])['signed_c'] / 3e-6
            check(name + '/recovered average', close(average, result['recovered_current_a']))
            _, cathode = bounded(time, vectors['v(led_k)'], fault, fault + 1e-6)
            reverse = max(0, np.max(cathode - ENV[condition['envelope']][1]))
            check(name + '/reverse peak', close(reverse, result['fault_reverse_peak_v']))
            guard('Unchanged fault 1us deadline', delay is not None and delay <= limits['fault_deadline_s'])
            guard('Unchanged held-fault 1nA guard',
                  result['held_fault']['branch_max_abs_a'] < limits['fault_safe_current_abs_a'])
            guard('Unchanged fault positive 10pC budget',
                  result['fault']['branch_charge']['positive_c'] <= limits['fault_positive_tail_charge_c'])
            guard('Fault negative 20pC teaching budget',
                  abs(result['fault']['branch_charge']['negative_c']) <= 20e-12)
            guard('Fault negative 10mA teaching peak', result['fault']['branch_min_a'] >= -.01)
            guard('Fault model reverse 0.5V teaching budget', reverse <= .5)
            _, recovery_input = bounded(time, vectors['v(input)'], fault + 3e-6, fault + 5e-6)
            guard('Fault removal/clock stop cannot recover PWM', np.max(abs(recovery_input)) < .01)
            guard('No model conduction before stopped-clock recovery',
                  result['fault_removal_stopped_clock']['conduction_max_abs_a'] < 1e-9)
            guard('After reset/recovery current within 5%', abs(average / 100e-6 - 1) < .05)

        # Each of 27 new MOS: D/G/S/B differences are recomputed from saved nodes.
        zero = np.zeros(len(time))
        logic = np.full(len(time), ENV[condition['envelope']][0])
        ref = {'0': zero, 'refrail': vectors['v(refrail)'], 'vset': vectors['v(vset)'],
               'sense': vectors['v(sense)'], 'refout': vectors['v(refout)']}
        ref.update({n: vectors['v(xref.' + n + ')'] for n in ['pb', 'tail', 'n1', 'n2', 'ctrl']})
        iso = {'0': zero, 'vdd': logic, 'fault': vectors['v(fault_pin)'],
               'fault_b': vectors['v(xiso.fault_b)'], 'bias': vectors['v(bias)'],
               'isolator_in': vectors['v(isolator_in)']}
        safe = {'0': zero, 'vdd': logic, 'raw': vectors['v(raw_pwm)'],
                'fault': vectors['v(fault_pin)'], 'permit': vectors['v(permit)'],
                'out': vectors['v(input)']}
        safe.update({n: vectors['v(xsafe.' + n + ')'] for n in ['fault_b', 'nand_n', 'stack1', 'stack2']})
        clamp = {'0': zero, 'fault': vectors['v(fault_pin)'], 'anode': vectors['v(clamp_anode)'],
                 'cathode': vectors['v(led_k)'], 'hb': vectors['v(xclamp.fault_hb)']}
        maxima = []
        for prefix, devices, nodes in [('ref/', REF, ref), ('iso/', ISO, iso),
                                        ('safe/', SAFE, safe), ('clamp/', CLAMP, clamp)]:
            for device, d, g, so, bulk in devices:
                terminal_pairs = [('VGS', nodes[g] - nodes[so]), ('VGD', nodes[g] - nodes[d]),
                                  ('VDS', nodes[d] - nodes[so]), ('VSB', nodes[so] - nodes[bulk]),
                                  ('VDB', nodes[d] - nodes[bulk])]
                for pair, value in terminal_pairs:
                    recorded = result['terminal_stress'][prefix + device][pair]
                    actual = {'min_v': float(np.min(value)), 'max_v': float(np.max(value)),
                              'max_abs_v': float(np.max(abs(value)))}
                    check(name + '/' + prefix + device + '/' + pair,
                          all(close(v, recorded[k], 1e-12) for k, v in actual.items()))
                    maxima.append((prefix + device, pair, actual['max_abs_v']))
                if device in PMOS:
                    body.append(dict(case=name, device=prefix + device,
                                     finite_reference_junctions=condition['junctions'],
                                     isolated=condition['isolated'],
                                     max_source_body_v=float(np.max(nodes[so] - nodes[bulk])),
                                     max_drain_body_v=float(np.max(nodes[d] - nodes[bulk]))))
        maximum = max(maxima, key=lambda row: row[2])
        terminal_max.append(dict(case=name, device=maximum[0], pair=maximum[1], absolute_v=maximum[2]))
        check(name + '/maximum terminal difference', close(maximum[2], result['max_new_terminal_difference_v'], 1e-12))
        reference_extrema.append(dict(case=name, min_sense_v=float(np.min(ref['sense'])),
                                      max_reference_current_a=float(np.max(vectors['i(VREFLOAD)']))))
        with (folder / 'rtl-events.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        bytime = {float(row['time_ns']): row for row in rows}
        previous, known, unknown, truth, recovery = None, 0, 0, True, True
        for timestamp in sorted(bytime):
            row = bytime[timestamp]
            keys = ['raw_pwm', 'protected_pwm', 'permit', 'fault', 'recover_request', 'clk_run']
            if not all(row[k] in ['0', '1'] for k in keys):
                unknown += 1
                continue
            known += 1
            value = {k: int(row[k]) for k in keys}
            truth &= value['protected_pwm'] == (value['raw_pwm'] and value['permit'] and not value['fault'])
            if previous and not previous['permit'] and value['permit']:
                recovery &= not value['fault'] and value['recover_request'] and not previous['raw_pwm'] and value['clk_run']
            previous = value
        check(name + '/actual RTL combinational truth', truth)
        check(name + '/actual RTL qualified recovery', recovery)
        rtl_counts.append(dict(case=name, known_rows=known, unknown_rows=unknown,
                               scope='Unknown rows are counted, not treated as initialized physical storage or POR.'))
        left, right = ((0, 20e-6) if kind == 'startup' else
                       ((condition['fault_ns'] * 1e-9, condition['fault_ns'] * 1e-9 + 1e-6)
                        if kind == 'fault' else (514.5e-6, 1026.5e-6)))
        _, residual = bounded(time, vectors['@d.xled.dled[id]'] - branch, left, right)
        closure.append(dict(case=name, kind=kind, left_s=left, right_s=right,
                            max_device_diagnostic_branch_difference_a=float(np.max(abs(residual)))))

    for recorded in summary['dc_results']:
        folder = raw / recorded['name']
        check(recorded['name'] + '/deck hash', sha(folder / 'testbench.spice') == recorded['deck_sha256'])
        with (folder / 'waveform.dat').open() as stream:
            columns = stream.readline().split()
        data = np.atleast_2d(np.loadtxt(folder / 'waveform.dat', skiprows=1))
        values = {name: data[0, index] for index, name in enumerate(columns)}
        for field, vector in [('current_a', 'i(VLEDLOAD)'), ('reference_output_a', 'i(VREFLOAD)'),
                              ('BIAS_v', 'v(bias)'), ('refout_v', 'v(refout)')]:
            check(recorded['name'] + '/' + field, close(recorded[field], values[vector]))
        current = values['i(VLEDLOAD)']
        level = int(recorded['name'].split('_')[-1])
        guard = abs(current / 100e-6 - 1) <= .05 if level else abs(current) < 1e-9
        check(recorded['name'] + '/DC guard', recorded['passed'] == guard)

    convergence = []
    for recorded in summary['convergence']:
        a, ta, ia = cache[recorded['coarse']]
        b, tb, ib = cache[recorded['fine']]
        kind = recorded['name']
        left = 0 if kind == 'startup' else (514.5e-6 if kind == 'normal' else a['conditions']['fault_ns'] * 1e-9)
        right = 20e-6 if kind == 'startup' else (1026.5e-6 if kind == 'normal' else left + 1e-6)
        field = 'signed_c' if kind == 'normal' else 'positive_c'
        qa = charges(ta, ia, left, right)[field]
        qb = charges(tb, ib, left, right)[field]
        change = abs(qb / qa - 1) * 100
        check(kind + '/independent convergence', close(qa, recorded['coarse_charge_c']) and
              close(qb, recorded['fine_charge_c']) and abs(change - recorded['change_pct']) < 1e-6 and
              recorded['passed'] == (change <= recorded['original_relative_limit_pct']))
        knots = np.unique(np.r_[ta[(ta >= left) & (ta <= right)], tb[(tb >= left) & (tb <= right)], left, right])
        difference = abs(np.interp(knots, ta, ia) - np.interp(knots, tb, ib))
        j = int(np.argmax(difference))
        convergence.append(dict(name=kind, coarse_charge_c=qa, fine_charge_c=qb,
                                change_pct=change, passed=recorded['passed'],
                                absolute_charge_difference_c=abs(qb - qa),
                                merged_knot_max_branch_difference_a=float(difference[j]),
                                branch_difference_time_s=float(knots[j])))
    functional = [c for c in summary['checks'] if not c['name'].startswith('Legacy startup')]
    legacy = [c for c in summary['checks'] if c['name'].startswith('Legacy startup')]
    check('overall classification is honest', summary['passed'] == all(c['passed'] for c in summary['checks']))
    check('functional classification is honest', summary['functional_contract_passed'] == all(c['passed'] for c in functional))
    check('legacy relative classification is honest', summary['legacy_startup_relative_convergence_passed'] == all(c['passed'] for c in legacy))
    check('summary bytes unchanged during audit', sha(summary_path) == summary_hash)
    audit = dict(schema_version=1, checked_summary=str(summary_path.relative_to(ROOT)),
                 checked_summary_sha256=summary_hash, audit_script_sha256=sha(Path(__file__).resolve()),
                 checked_source_sha256=summary['source_sha256'], raw_directory=summary['raw_directory'],
                 data_integrity_passed=all(c['passed'] for c in checks), checks_count=len(checks),
                 experiment_functional_passed=summary['functional_contract_passed'],
                 experiment_legacy_startup_relative_convergence_passed=summary['legacy_startup_relative_convergence_passed'],
                 experiment_overall_passed=summary['passed'], failed_experiment_checks=[c for c in summary['checks'] if not c['passed']],
                 terminal_maxima=terminal_max, PMOS_terminal_body_bias=body,
                 reference_extrema=reference_extrema, device_diagnostic_closure=closure,
                 actual_RTL_rows=rtl_counts, convergence=convergence, checks=checks,
                 scope='Independent hashes, arithmetic and recorded RTL/terminal captures only. Series branch current defines guards; device conduction/cap currents are diagnostics. SPICE continuous charge is not quantized or floored at electron charge. Instrument resolution is unknown. Auxiliary absolute differences do not pass the original relative guard. No EDA run, POR, arbitrary rail order, SOA/latchup, layout, silicon or optical qualification.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps({'data_integrity_passed': audit['data_integrity_passed'],
                      'checks_count': audit['checks_count'],
                      'experiment_overall_passed': audit['experiment_overall_passed'],
                      'output': str(args.output.relative_to(ROOT)),
                      'failed_audit_checks': [c for c in checks if not c['passed']]}, indent=2))
    return 0 if audit['data_integrity_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())

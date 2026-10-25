#!/usr/bin/env python3
"""Final v2 association statistics from frozen validation samples and symbols."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

GRAY = ((0, 0), (0, 1), (1, 1), (1, 0))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize(samples_uA, symbols, pam4):
    samples, symbols = np.asarray(samples_uA), np.asarray(symbols, dtype=int)
    if len(samples) != len(symbols) or len(symbols) < 2 or not np.isfinite(samples).all():
        raise ValueError('Finite same-length samples and symbols required')
    nlevels = 4 if pam4 else 2
    if not np.isin(symbols, np.arange(nlevels)).all():
        raise ValueError('Invalid symbol')
    thresholds = [37.5, 62.5, 87.5] if pam4 else [62.5]
    targets = np.array([25., 50., 75., 100.] if pam4 else [25., 100.])
    lower, upper = np.array([-np.inf, *thresholds]), np.array([*thresholds, np.inf])
    margins = np.minimum(samples-lower[symbols], upper[symbols]-samples)
    decoded = np.sum(samples[:, None] >= np.array(thresholds), axis=1)
    labels = GRAY if pam4 else ((0, 0), (0, 1))

    def stats(indices):
        ix = np.asarray(indices, dtype=int)
        if not len(ix):
            return {'count': 0}
        local = int(np.argmin(margins[ix])); worst = int(ix[local])
        current_targets = targets[symbols[ix]]
        return {'count': len(ix), 'min_margin_uA': float(margins[worst]),
                'mean_margin_uA': float(margins[ix].mean()),
                'median_margin_uA': float(np.median(margins[ix])),
                'p05_margin_uA': float(np.quantile(margins[ix], .05)),
                'below_7p5uA_count': int(np.count_nonzero(margins[ix] < 7.5)),
                'symbol_errors': int(np.count_nonzero(decoded[ix] != symbols[ix])),
                'sample_min_uA': float(samples[ix].min()), 'sample_max_uA': float(samples[ix].max()),
                'mean_signed_target_error_uA': float(np.mean(samples[ix]-current_targets)),
                'worst_validation_symbol_offset': worst, 'worst_sample_uA': float(samples[worst]),
                'worst_expected_symbol': int(symbols[worst]),
                'worst_target_error_uA': float(samples[worst]-targets[symbols[worst]]),
                'worst_previous_symbols': symbols[max(0, worst-4):worst].tolist(),
                'worst_following_symbols': symbols[worst+1:worst+5].tolist()}

    transitions, flips = [], defaultdict(list)
    previous, current = symbols[:-1], symbols[1:]
    for before in range(nlevels):
        for after in range(nlevels):
            indices = (np.flatnonzero((previous == before) & (current == after))+1).tolist()
            flip = tuple(x ^ y for x, y in zip(labels[before], labels[after]))
            name = ''.join(map(str, flip))
            flips[name].extend(indices)
            transitions.append({'transition': f'{before}->{after}',
                                'previous_symbol': before, 'current_symbol': after,
                                'previous_D1D0': ''.join(map(str, labels[before])),
                                'current_D1D0': ''.join(map(str, labels[after])),
                                'flip_D1D0': name, 'bit_changes': sum(flip),
                                'target_step_uA': float(targets[after]-targets[before]),
                                'self_transition': before == after, **stats(indices)})
    flips_summary = [{'flip_D1D0': name, 'bit_changes': sum(int(c) for c in name),
                      **stats(sorted(ix))} for name, ix in sorted(flips.items())]
    by_level = [{'current_symbol': level, 'target_uA': float(targets[level]),
                 **stats(np.flatnonzero(symbols == level))} for level in range(nlevels)]
    directed = [row for row in transitions if not row['self_transition'] and row['count']]
    worst_directed = min(directed, key=lambda row: row['min_margin_uA']) if directed else None
    all_stats = stats(np.arange(len(symbols)))
    return {'validation_all_symbols': all_stats, 'by_current_level': by_level,
            'transitions': transitions, 'by_bit_flip': flips_summary,
            'worst_directed_transition': worst_directed,
            'all_directed_transitions_present': len(directed) == nlevels*(nlevels-1),
            'transition_total': sum(row['count'] for row in transitions),
            'boundary_sample': {'validation_symbol_offset': 0, 'expected_symbol': int(symbols[0]),
                                'sample_uA': float(samples[0]), 'margin_uA': float(margins[0]),
                                'policy': 'Included in all-symbol and current-level statistics; excluded from transition statistics because predecessor lies outside validation.'}}


def self_check():
    # Hand-checked Gray sequence: 00,01,10,11. Flip groups:01,11,01.
    # Samples give expected-class margins12.5,8,6,11uA; no symbol errors.
    got = summarize([25., 45.5, 93.5, 76.5], [0, 1, 3, 2], True)
    assert got['transition_total'] == 3
    assert got['validation_all_symbols']['min_margin_uA'] == 6.
    assert got['validation_all_symbols']['below_7p5uA_count'] == 1
    assert got['worst_directed_transition']['transition'] == '1->3'
    groups = {row['flip_D1D0']: row for row in got['by_bit_flip']}
    assert groups['11']['count'] == 1 and groups['11']['min_margin_uA'] == 6.
    assert groups['01']['count'] == 2 and groups['01']['min_margin_uA'] == 8.
    # A confidently wrong symbol must have negative expected-class margin.
    bad = summarize([25., 25.], [0, 1], False)
    assert bad['validation_all_symbols']['symbol_errors'] == 1
    assert bad['validation_all_symbols']['min_margin_uA'] == -37.5
    return {'passed': True, 'fixtures': ['hand-checked Gray transitions and below-margin count',
                                        'wrong-symbol negative signed margin']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', type=Path)
    ap.add_argument('--cases', nargs='+')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    fixtures = self_check()
    if args.self_test:
        print(json.dumps(fixtures)); return
    if not args.work or not args.cases or not args.out:
        ap.error('--work --cases --out required')
    if args.out.exists():
        raise FileExistsError('Refuse overwrite: '+str(args.out))
    work = args.work.resolve()
    stimulus_path = work/'stimulus.json'
    stimulus = json.loads(stimulus_path.read_text())
    manifest = json.loads((work/'manifest.json').read_text())
    assert sha(stimulus_path) == manifest['files']['stimulus.json']
    for name,digest in manifest['files'].items():
        assert sha(work/name)==digest
    rows = []
    for name in args.cases:
        path = work/'cases/baseline'/name/'result.json'
        record = json.loads(path.read_text())
        assert record['analysis_version']=='equal-absolute-latency-v2' and record['case']['name']==name
        assert record['v2_stimulus_sha256']==manifest['files']['stimulus.json']
        assert record['v2_receiver_sha256']==manifest['files']['receiver.py']
        rx = record['receiver']; route = record['case']['route']
        pam4 = route == 'C'; bps = 2 if pam4 else 1
        symbols = stimulus['symbols_C' if pam4 else 'symbols_N'][576//bps:4672//bps]
        review = summarize(rx['validation']['samples_uA'], symbols, pam4)
        assert abs(review['validation_all_symbols']['min_margin_uA']-rx['validation']['decision_distance_min_uA']) < 1e-12
        assert review['validation_all_symbols']['symbol_errors'] == rx['validation']['symbol_errors']
        assert {row['transition']: row['count'] for row in review['transitions']} == rx['validation']['transition_counts']
        assert review['transition_total'] == len(symbols)-1
        rows.append({'case': name, 'route': route, 'result_sha256': sha(path),
                     'net_rate_Gbps': record['case']['net_rate_Gbps'],
                     'frozen_sampling_delay_symbol_UI': rx['sampling']['delay_symbol_UI'],
                     'raw_bit_errors': rx['validation']['bit_errors'],
                     'receiver_passed': rx['passed'], **review})
    report = {'schema_version': 2, 'review_source_sha256': sha(__file__),
              'stimulus_sha256': sha(stimulus_path), 'work': str(work),
              'formal_manifest_sha256':sha(work/'manifest.json'),
              'frozen_v2_receiver_sha256':manifest['files']['receiver.py'],
              'self_check': fixtures, 'rows': rows,
              'scope_zh': '只读正式final v2 validation.samples_uA 与共同 stimulus；不使用v1采样相位或数据。D1D0 翻转表示逻辑码变化，不是已观测内部栅极同步行为。',
              'boundaries_zh': [
                  '所有余量都在已冻结训练相位计算，未重新选相、拟合阈值或改变统计窗口。',
                  '12 种非自环 PAM4 转换与 4 种自环分开列出；bit 翻转组和转换计数均排除第一个验证样本，以保持验证段内部统计。',
                  '统计只定位前后符号历史与输出等效电流余量的关联。仅凭 ILED 和滤波后样本不能证明内部译码毛刺、支路抢流或某个内部节点是原因。',
                  '目标偏差混合了静态电流误差、动态未建立、共享参考耦合及共同滤波的效应；这些贡献尚未分离。',
                  '零错误仍可能因小于7.5uA余量而失败；本统计不更新原始 receiver_passed。']}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    for row in rows:
        worst = row['worst_directed_transition']
        print(json.dumps({'case': row['case'], 'worst_transition': worst['transition'],
                          'margin_uA': worst['min_margin_uA'],
                          'below_7p5uA': row['validation_all_symbols']['below_7p5uA_count'],
                          'receiver_passed': row['receiver_passed']}))


if __name__ == '__main__':
    main()

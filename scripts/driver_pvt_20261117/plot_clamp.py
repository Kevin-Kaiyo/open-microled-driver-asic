#!/usr/bin/env python3
"""Plot the forced-bias clamp sweep without using transient metrics."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'evidence/driver-pvt-20261117/clamp-probe.json'
ASSETS = ROOT / 'docs/research/driver-pvt-20261117/assets'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    record = json.loads(EVIDENCE.read_text())
    cases = {(row['corner'], row['mos_temp_C']): row for row in record['cases']}
    plt.rcParams.update({'font.family': ['Hiragino Sans GB', 'DejaVu Sans'],
                         'axes.unicode_minus': False, 'svg.fonttype': 'none',
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(figsize=(8.6, 4.2), layout='constrained')
    for case, color, label in [(('typical', 27), '#187786', 'TT，27 °C'),
                               (('ss', 85), '#b16236', 'SS，85 °C'),
                               (('ff', -40), '#605b9c', 'FF，-40 °C')]:
        row = cases[case]
        waveform = ROOT / row['case'] / 'sweep.dat'
        assert sha(waveform) == row['trace_sha256']
        _, vgs, body, zero = np.loadtxt(waveform, skiprows=1, unpack=True)
        ax.semilogy(vgs, -body * 1e6, color=color, label=label, lw=2)
        if case[0] == 'typical':
            ax.semilogy(vgs, -zero * 1e6, ls='--', color=color, label='TT，VSB = 0 V 对照')
    vgs_history = record['vgs_at_previous_20ns_V']
    ax.axvspan(vgs_history - .165, vgs_history + .165, color='#c9e1de', alpha=.6)
    ax.axvline(vgs_history, color='#587277', lw=1.1, ls=':', label='上一轮 +20 ns 栅源电压')
    ax.set(xlim=(1.1, 2.1), ylim=(.005, 2000), xlabel='栅源电压 VGS (V)',
           ylabel='钳位管漏极支路电流 (µA)',
           title='B 钳位管的体偏置与栅压敏感度')
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:g}'))
    ax.legend(loc='lower right', ncols=1, fontsize=9, framealpha=.95)
    ax.grid(which='major', lw=.6, alpha=.3)
    ASSETS.mkdir(parents=True, exist_ok=True)
    for suffix in ['svg', 'png']:
        fig.savefig(ASSETS / f'b-clamp-bias-probe.{suffix}', dpi=165)
    (ASSETS / 'b-clamp-bias-probe.source.json').write_text(json.dumps({
        'evidence': str(EVIDENCE.relative_to(ROOT)), 'evidence_sha256': sha(EVIDENCE),
        'generator_sha256': sha(Path(__file__)), 'scope': 'DC fixture, not LED current',
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()

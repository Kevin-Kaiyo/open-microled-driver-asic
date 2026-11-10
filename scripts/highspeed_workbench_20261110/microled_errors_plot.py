#!/usr/bin/env python3
"""Render the recorded MicroLED failure controls without access to native traces."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / 'evidence/highspeed-workbench-20261110/microled-errors-controls.json'
FIGURE = ROOT / 'docs/research/highspeed-workbench-20261110/microled-error-controls.png'


def main():
    data = json.loads(RESULT.read_text())
    rows = {(row['route'], row['capacitance_fF'], row['optical_tau_ps'], row['rx_GHz']): row
            for row in data['rows'] if row['input'] == 'native'}
    cases = [(200, 200, 1), (200, 200, 5), (10, 25, 1), (10, 25, 5)]
    fig = plt.figure(figsize=(11.4, 4.45), layout='constrained')
    grid = fig.add_gridspec(2, 2, width_ratios=[2.35, 1])
    ax = fig.add_subplot(grid[:, 0])
    amplitude = fig.add_subplot(grid[0, 1])
    timing = fig.add_subplot(grid[1, 1], sharex=amplitude)
    palette = {'A': '#176467', 'B': '#a45b29', 'C': '#486a8b'}
    positions = np.arange(len(cases))
    for idx, (route, color) in enumerate(palette.items()):
        offset = (idx - 1) * .22
        errors = [rows[(route, *case)]['bit_errors'] for case in cases]
        bars = ax.bar(positions + offset, errors, width=.21, label=route, color=color)
        ax.bar_label(bars, padding=4, fontsize=8, color='#223b48')
    ax.set_xticks(positions, [f'{c} fF / {tau} ps\nRX {rx} GHz' for c, tau, rx in cases])
    ax.set_ylim(0, 1710)
    ax.set_ylabel('Validation bit errors / 4096')
    ax.set_title('A/B/C · RX bandwidth and emitter assumptions', loc='left')
    ax.legend(frameon=False, loc='upper right', ncol=3)
    ax.grid(axis='y', alpha=.20)
    ax.set_axisbelow(True)
    for mark, key, gate, label, maximum in (
        (amplitude, 'min_signed_margin_uA', 7.5, 'Amplitude (µAeq)', 30),
        (timing, 'min_time_margin_ps', 100, 'One-sided time (ps)', 120),
    ):
        values = [rows[('B', 10, 25, rx)][key] for rx in (1, 5)]
        bars = mark.bar(['RX 1 GHz', 'RX 5 GHz'], values, width=.47, color=palette['B'])
        mark.bar_label(bars, fmt='%.2f', padding=3, fontsize=8, color='#223b48')
        mark.axhline(gate, ls='--', lw=1, color='#576e7a')
        mark.set_ylim(0, maximum)
        mark.set_ylabel(label)
        mark.grid(axis='y', alpha=.20)
        mark.set_axisbelow(True)
    amplitude.set_title('B at 10 fF / 25 ps · zero errors', loc='left')
    amplitude.tick_params(axis='x', labelbottom=False)
    for axis in (ax, amplitude, timing):
        axis.spines[['top', 'right']].set_visible(False)
    fig.savefig(FIGURE, dpi=160, facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    main()

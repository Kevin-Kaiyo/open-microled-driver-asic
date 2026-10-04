"""Original conceptual diagrams and explicitly calculated teaching examples.

These drawings explain the design; they are not silicon/optical measurements.
"""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/research/figures'
OUT.mkdir(parents=True, exist_ok=True)
TEAL, NAVY, GRAY = '#187c84', '#254f68', '#667b86'
plt.rcParams.update({'font.family': ['Avenir Next', 'Arial', 'sans-serif'],
                     'font.size': 10, 'text.color': NAVY, 'axes.labelcolor': NAVY,
                     'axes.spines.top': False, 'axes.spines.right': False})
outputs = []

def save(fig, name):
    target = OUT / name
    fig.savefig(target, dpi=190, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    outputs.append(str(target.relative_to(ROOT)))

def box(ax, x, y, w, h, text, color=TEAL):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.035',
                 linewidth=1.2, edgecolor=color, facecolor='#f0f6f6'))
    ax.text(x+w/2, y+h/2, text, ha='center', va='center', color=color)

def arrow(ax, a, b, text='', color=TEAL):
    ax.annotate('', xy=b, xytext=a, arrowprops={'arrowstyle': '->', 'lw': 1.6, 'color': color})
    if text: ax.text((a[0]+b[0])/2, (a[1]+b[1])/2+.14, text, ha='center', va='bottom', color=color, fontsize=9)

fig, ax = plt.subplots(figsize=(9.5, 4.5))
ax.set(xlim=(-.2, 10.7), ylim=(-.2, 5.2)); ax.axis('off')
box(ax, 0, 3.45, 2.0, .8, 'Duty / enable\nregistered PWM')
box(ax, 2.65, 3.45, 1.8, .8, 'buf_2\noutput stage')
box(ax, 5.05, 3.45, 2.0, .8, 'Pass + clamp\ncontrol the gate')
arrow(ax, (2, 3.85), (2.65, 3.85)); arrow(ax, (4.45, 3.85), (5.05, 3.85))
box(ax, 0, 1.45, 2, .8, 'External IREF\n100 µA target')
box(ax, 2.65, 1.45, 1.8, .8, 'MREF\ncurrent → VGS')
arrow(ax, (2, 1.85), (2.65, 1.85))
arrow(ax, (4.45, 1.85), (6.05, 3.4))
ax.text(4.48, 2.72, 'Bias voltage', ha='right', color=TEAL, fontsize=9)
box(ax, 8.35, 2.7, 1.7, .8, 'MOUT\ncurrent sink', NAVY)
box(ax, 8.35, 4.05, 1.7, .6, 'LED load', NAVY)
arrow(ax, (9.2, 5.02), (9.2, 4.65), 'VLED = 5 V', NAVY)
arrow(ax, (9.2, 4.05), (9.2, 3.5), color=NAVY)
arrow(ax, (9.2, 2.7), (9.2, 1.7), color=NAVY)
ax.text(9.42, 2.2, 'VSS', color=NAVY)
arrow(ax, (7.05, 3.85), (8.35, 3.1))
ax.text(7.5, 4.03, 'Gate voltage', ha='center', color=TEAL, fontsize=9)
ax.text(0, .75, 'Timing controls WHEN.  Reference and headroom control HOW MUCH.', fontsize=12)
ax.text(0, .25, 'Original concept drawing. Ports/rails are functional; pads, package and reference generator are outside this diagram.', color=GRAY, fontsize=8.5)
save(fig, 'teaching-architecture.png')

# Ideal slot arithmetic, explicitly distinct from the measured transient CSVs.
fig, axes = plt.subplots(2, 1, figsize=(9.3, 4.6), gridspec_kw={'height_ratios': [1.1, 1]})
for duty, level, color in [(64, 2, TEAL), (255, 0, NAVY)]:
    axes[0].step([0, duty, duty, 256], [level+1, level+1, level, level], where='post', lw=1.8,
                 color=color)
axes[0].set(xlim=(-2, 258), ylim=(-.2, 3.4), yticks=[], xlabel='Time within one frame (µs)', title='Ideal timing explanation: 1 MHz clock, 256 µs frame')
axes[0].text(82, 2.75, 'duty=64: 64/256 slots', color=TEAL)
axes[0].text(82, .45, 'duty=255: 255/256 slots', color=NAVY)
axes[0].axvline(256, color=GRAY, ls=':', lw=1)
axes[1].plot([-.25, 0, 0, 1, 1, 2], [0, 0, 100, 100, 0, 0], color=TEAL, lw=1.8)
axes[1].fill_between([0, 1], [100, 100], color=TEAL, alpha=.15)
axes[1].text(1.16, 73, 'Ideal Q1 = 100 µA × 1 µs\n= 100 pC\nAverage = 100/256 µA', fontsize=10)
axes[1].set(xlim=(-.25, 3.5), ylim=(-8, 120), ylabel='Current (µA)', xlabel='Zoom around the lowest-code pulse (µs)')
fig.tight_layout(rect=(0, .04, 1, 1))
fig.text(.05, .01, 'Calculated rectangular-wave example; not a transistor waveform or optical pulse measurement.', color=GRAY, fontsize=8.5)
save(fig, 'teaching-pwm.png')

fig, ax = plt.subplots(figsize=(9.2, 3.5))
duty = np.array([0, 1, 64, 256])
led_rail_uW = 5*100*duty/256
reference_uW = np.full(4, 3.3*100)
x = np.arange(4)
ax.bar(x, reference_uW, color='#a8bec8', label='Always-on reference input: 330 µW')
ax.bar(x, led_rail_uW, bottom=reference_uW, color=TEAL, label='LED rail: 500 µW × duty/256')
ax.set(xticks=x, xticklabels=['Off', '1/256', '64/256', 'Full-on'], ylabel='Power from ideal rails (µW)', title='Bias cost matters most at low duty')
for pos, value in zip(x, reference_uW+led_rail_uW): ax.text(pos, value+12, f'{value:.2f}', ha='center', fontsize=10)
ax.set_ylim(0, 1030); ax.legend(frameon=False, loc='upper left', fontsize=9)
fig.tight_layout(rect=(0, .08, 1, 1))
fig.text(.05, .01, 'Calculated 100 µA example. Excludes digital logic, real reference-generator overhead and supply conversion losses.', color=GRAY, fontsize=8.3)
save(fig, 'teaching-bias-power.png')

formulas = {
    'clock_hz': 1_000_000, 'slots_per_frame': 256,
    'slot_s': 1e-6, 'frame_s': 256e-6, 'pwm_hz': 3906.25,
    'ideal_full_current_uA': 100, 'ideal_lowest_avg_uA': 100/256,
    'ideal_lowest_charge_pC': 100,
    'ideal_reference_input_power_uW': 330,
    'power_example': [{'duty': int(d), 'reference_uW': float(r), 'led_rail_uW': float(l), 'total_uW': float(r+l)}
                      for d, r, l in zip(duty, reference_uW, led_rail_uW)]
}
interface_path = ROOT/'evidence/interface/summary.json'
interface = json.loads(interface_path.read_text())
def historical(duty):
    return next(r for r in interface['transient_results'] if r['driver']=='buffer_joint' and r['envelope']=='tt'
                and r['duty']==duty and r['led']=='synthetic' and r['maxstep_ns']==10)
full, lowest = historical(256), historical(1)
full_uA, avg_uA = full['average_led_current_uA'], lowest['average_led_current_uA']
q_pC = avg_uA*256
area_pct = (q_pC/full_uA-1)*100
assert abs(area_pct-lowest['area_error_pct'])<1e-9
formulas['v03_historical_worked_example'] = {
    'source_case_names': [full['name'], lowest['name']],
    'full_current_uA': full_uA, 'lowest_average_current_uA': avg_uA,
    'charge_per_frame_pC': q_pC, 'ideal_same_full_current_charge_pC': full_uA,
    'absolute_current_error_pct': (full_uA/100-1)*100, 'lowest_area_error_pct': area_pct,
    'scope': 'v0.3 partial stitched interface model; does not include exact physical analog entry point or output-cell PEX'
}
assert np.isclose(formulas['clock_hz']/formulas['slots_per_frame'], formulas['pwm_hz'])
assert np.isclose(100e-6*1e-6/1e-12, formulas['ideal_lowest_charge_pC'])
hashes = lambda names: {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
record = {'date': datetime.now().astimezone().isoformat(), 'evidence_class': 'original conceptual drawings and ideal arithmetic examples',
          'physical_measurement': False, 'formulas': formulas,
          'source_sha256': hashes(['scripts/research/teaching_figures.py', 'rtl/pixel_pwm.v', 'analog/driver/pixel_driver.spice', 'evidence/interface/summary.json']),
          'outputs_sha256': hashes(outputs),
          'primary_source': {'title': 'GF180MCU PDK 1.4.1 MOSFETs', 'url': 'https://gf180mcu-pdk.readthedocs.io/en/latest/analog/model_parameters/LV/LV_1_4_1.html',
                             'accessed_date': '2026-10-05', 'supports': 'public BSIM4 3.3 V and 6 V MOS model families; not manufacturing acceptance'}}
target = ROOT/'evidence/teaching/figures.json'
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
print('Created 3 conceptual/calculated teaching figures; identities and formulas recorded')

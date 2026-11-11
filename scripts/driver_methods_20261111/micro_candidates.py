"""Bounded supply-efficiency and damped feed-forward experiments."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / 'build/ab-improvement-20261111'

def candidate(name):
    route = 'B' if name.startswith('B_') else 'A'
    parent = OLD / ('B_wide_ff31p275' if route == 'B' else 'a-rin1wide-core03-matched')
    text = (parent / f'inputs/route_{route.lower()}.spice').read_text()
    params = json.loads((parent / 'manifest.json').read_text())['parameters'][route]
    overrides = {}
    if name == 'B_vin3p3_dummy27p6k':
        text = text.replace('RDUMMY VIN DUMMY 50k', 'RDUMMY VIN DUMMY 27.6k')
        overrides = {'vin_V': 3.3}
        hypothesis = 'Lower actual reference/dummy VIN from 5 to 3.3 V; 27.6 kOhm dummy resistor retains approximately 1.23 V drain headroom at 75 uA. LED5V and VDD3.3V unchanged. Tests static supply loss, not changed optical model.'
    elif name == 'B_vin3p3_dummy50k_control':
        overrides = {'vin_V': 3.3}
        hypothesis = 'Single-factor control: VIN reduced 5 to 3.3 V with original 50 kOhm dummy resistor. Same LED supply and targets. Dummy compliance may fail despite LED-only DC target passing; retain internal DC nodes and transient margin.'
    elif name == 'A_rcff31p275':
        text = text.replace('.ends fair_a', '* Damped, DC-open feed-forward from complement N1 to cathode OUT.\nXRF N1 FF VSS ppolyf_u_1k_6p0 r_width=4u r_length=4u\nCFF FF OUT 31.275f\n.ends fair_a')
        hypothesis = 'Add 1-square 4x4um PDK polysilicon series resistor and ideal 31.275 fF capacitor from N1 to OUT. Ahead-of-CTRL capacitive charge assist; resistor bounds ringing/current. Does not alter steady-state current. MIM physical implementation and protection not yet verified.'
    else:
        raise ValueError(name)
    return dict(name=name, route=route, route_text=text, parameters=params,
                notes=dict(hypothesis=hypothesis, parent=str(parent.relative_to(ROOT)),
                           case_overrides=overrides), case_overrides=overrides)

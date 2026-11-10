#!/usr/bin/env python3
"""Route A experimental changes; never modify archived frozen schematics.

Each name is immutable once initialized. RIN-only is a single-factor control.
The optional 03v3 buffer candidate requires a compatible regulated VDD range;
it does not inherit the older 3.65 V FF supply test or physical layout evidence.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'build/blue-emitter-speed-review-20261110/microled/inputs/route_a.spice'
PARAMETERS = {'RH':177683.3997653013,'RL':87444.56014738003}


def mos_geometry(line, *, width_um=None, length_um=None, model=None):
    words=line.split()
    if model is not None:words[5]=model
    parameters={x.split('=',1)[0]:x.split('=',1)[1] for x in words[6:]}
    width=float(parameters['w'].rstrip('u')) if width_um is None else width_um
    length=float(parameters['l'].rstrip('u')) if length_um is None else length_um
    # Same explicitly estimated 0.44 um diffusion depth as the baseline.
    return ' '.join(words[:6])+f' w={width:g}u l={length:g}u ad={width*.44:g}p as={width*.44:g}p pd={2*(width+.44):g}u ps={2*(width+.44):g}u'


def transform(text, name):
    if name not in ['a-base','a-rin1','a-rin1-drive2','a-rin1-buf03','a-rin1wide','a-rin1wide-buf03','a-rin1wide-buf03-out2','a-rin1wide-core03']:
        raise ValueError(name)
    if name=='a-base':return text
    text=text.replace('r_width=1u r_length=8u','r_width=1u r_length=1u')
    assert 'r_length=8u' not in text
    if 'wide' in name:
        text=text.replace('r_width=1u r_length=1u','r_width=4u r_length=4u')
    text=text.replace('* Original A 06v0 MOS sizes and actual PDK RIN geometry are preserved.',
                      '* A improvement experiment; input RIN is 1 square; explicit geometry is in XRIN.')
    text=text.replace('* Original six-MOS voltage-output core and 8-square PDK input resistor.',
                      '* Six-MOS voltage-output core and 1-square PDK input resistor.')
    lines=[]
    for line in text.splitlines():
        instance=line.split()[0] if line.strip() else ''
        if instance in ['XN1','XP1','XN2','XP2']:
            if name=='a-rin1-drive2' and instance in ['XN1','XP1']:
                width=float(re.search(r'\bw=([.0-9]+)u',line).group(1))*2
                line=mos_geometry(line,width_um=width)
            elif name in ['a-rin1-buf03','a-rin1wide-buf03','a-rin1wide-buf03-out2','a-rin1wide-core03']:
                line=mos_geometry(line,length_um=.28,model='nfet_03v3' if instance.startswith('XN') else 'pfet_03v3')
        if instance in ['XNOUT','XPOUT'] and name=='a-rin1wide-buf03-out2':
            width=float(re.search(r'\bw=([.0-9]+)u',line).group(1))*2
            line=mos_geometry(line,width_um=width)
        if instance in ['XNOUT','XPOUT'] and name=='a-rin1wide-core03':
            line=mos_geometry(line,length_um=.28,model='nfet_03v3' if instance.startswith('XN') else 'pfet_03v3')
        lines.append(line)
    return '\n'.join(lines)+'\n'


def candidate(name):
    hypotheses={
      'a-base':'Unchanged 20 MOS A schematic; baseline reproduction.',
      'a-rin1':'Reduce input series PDK resistor from 8 to 1 square while retaining all 20 MOS and calibrated output rails. Test input RC contribution.',
      'a-rin1-drive2':'Relative to a-rin1, double only the first 06V inverter transistor widths, updating diffusion estimates consistently. Measured first-stage delay dominates the buffer chain; retain second-stage load to isolate its output resistance change.',
      'a-rin1wide':'Relative to a-rin1, use4umwidth×4umlength at the same1square resistance. This wider physical-aware resistor allows a conservative current-density budget while explicitly retaining its larger model capacitance; not a completedDRC/EMsignoff.',
      'a-rin1wide-core03':'Relative to a-rin1wide-buf03, change only the two output MOS to03v3L=0.28um at the originalW10/15.72um. Preserve14MOS06Vrailservos. DCfit RH/RL to25/100uA. Tests gm/C without doubledW chargeinjection; requiresregulated3.3V and newfault/stressqualification.',
      'a-rin1wide-buf03-out2':'Relative to a-rin1wide-buf03, double only the two06VoutputMOS widths and consistentestimateddiffusions. RH/RL providedhereareinitialseeds; separately DCfit bothrailsetpoints to25/100uA before ratecomparison.',
      'a-rin1wide-buf03':'Relative to a-rin1wide, replace only the four predriver MOS by03v3L=0.28um at the same widths. Output/5Vrailservosremain06V. Nominal3.3VregulatedVDDisrequired; old3.65VFFcontractnotinherited.',
      'a-rin1-buf03':'Relative to a-rin1, replace only the four predriver MOS by 03v3 L=0.28um at the same widths. Output core and 5V rail servos remain 06V. This candidate requires regulated VDD within 03v3 stress limits; the old3.65V high-supply contract is not inherited.'
    }
    return {'name':name,'route':'A','route_text':transform(BASE.read_text(),name),
            'parameters':PARAMETERS.copy(),'hypothesis':hypotheses[name]}

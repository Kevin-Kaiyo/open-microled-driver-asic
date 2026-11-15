#!/usr/bin/env python3
"""Freeze owned deliverables after consistency checks, without changing raw evidence."""
from datetime import datetime,timezone
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import run
def main():
 v=run.read(run.EV/'vcsel-interface-validation.json');c=run.read(run.EV/'vcsel-interface-confirmation.json');assert v['status']==c['status']=='PASS' and len(v['cases'])==19
 cases=[x['case'] for x in v['cases']];actual=[str(p.parent.relative_to(run.ROOT)) for p in run.BUILD.glob('*/*/manifest.json')];assert set(cases)==set(actual)
 timestamp=datetime.now(timezone.utc).isoformat();summary=run.read(run.EV/'vcsel-interface-summary.json');assert len(summary['dc'])==8 and len(summary['rows'])==9
 summary.update(status='frozen',frozen_at_UTC=timestamp,required_cases=cases);run.emit(run.EV/'vcsel-interface-summary.json',summary)
 assets=sorted((run.ROOT/'docs/research/driver-interface-20261115/assets').glob('vcsel-*'))
 run.emit(run.EV/'vcsel-figures-receipt.json',dict(status='rendered_and_visually_reviewed',files=[dict(path=str(p.relative_to(run.ROOT)),sha256=run.sha(p),bytes=p.stat().st_size) for p in assets],visual_review='All5PNGfigures inspected: standardMOSschematic, native/RXwaveforms, rate comparison, source energy, input burden. Glyphs and connectors corrected. SVG originals retained. No new physical layout is represented.'))
 src=list(Path(__file__).parent.glob('*'));ev=list(run.EV.glob('vcsel-*'));files=[p for p in sorted(src+ev+assets) if p.is_file() and p.name!='vcsel-interface-freeze.json']
 out=dict(status='frozen',frozen_at_UTC=timestamp,required_cases=cases,counts=dict(SPICE_cases=19,paired_DC=8,development_frames=7,half_step_frames=1,holdout_frames=1,open_input_DC_diagnostics=2,figures=5),files=[dict(path=str(p.relative_to(run.ROOT)),sha256=run.sha(p),bytes=p.stat().st_size) for p in files],scope='Owned VCSEL lane ready for independent audit and parent report/backup. Raw native waveform hashes and actual source manifests are in vcsel-interface-validation.json. Failures intentionally retained; PASS here means deliverable consistency, not every circuit passes.',remaining=['Actual PHY/PAD/ESD/transmission-line and earlier logic supply cost','VCSEL continuous electrical/thermal and independent laser shutdown','PVT/independent resistor tolerance/Monte Carlo/noise and jitter','New layout/DRC/LVS/PEX/EMIR and physical opticalBER'])
 run.emit(run.EV/'vcsel-interface-freeze.json',out);print('FROZEN',len(cases),'cases',len(files),'compact/source/assets')
if __name__=='__main__':main()

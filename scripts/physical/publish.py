"""Validate compact physical reports before publishing successful evidence."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'build/physical-flow'
EVIDENCE = ROOT / 'evidence/physical'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def copy(source, relative):
    target = EVIDENCE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def clean(value):
    if isinstance(value, dict):
        return {key: clean(v) for key, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name', default='pwm-v0.2-sized')
    args = parser.parse_args()
    run = BUILD / args.run_name
    metrics = read(run / 'final/metrics.json')
    command = read(BUILD / (args.run_name + '.log.command.json'))
    if command['exit_code'] != 0 or 'Flow complete.' not in (run / 'flow.log').read_text():
        raise RuntimeError('Physical implementation did not complete')
    required_zero = ['route__drc_errors', 'magic__drc_error__count', 'design__lvs_error__count',
        'design__max_slew_violation__count', 'design__max_cap_violation__count',
        'design__max_fanout_violation__count', 'design__critical_disconnected_pin__count',
        'design__disconnected_pin__count', 'antenna__violating__nets', 'antenna__violating__pins',
        'timing__setup_vio__count', 'timing__hold_vio__count']
    for key in required_zero:
        if metrics.get(key) != 0:
            raise RuntimeError(f'Required check not zero or missing: {key}={metrics.get(key)}')
    config = read(run / 'resolved.json')
    corners = {}
    for corner in config['STA_CORNERS']:
        entry = {label:metrics[f'{key}__corner:{corner}'] for label,key in {
            'setup_worst_slack_ns':'timing__setup__ws', 'hold_worst_slack_ns':'timing__hold__ws',
            'setup_violation_count':'timing__setup_vio__count', 'hold_violation_count':'timing__hold_vio__count',
            'max_slew_violation_count':'design__max_slew_violation__count',
            'max_cap_violation_count':'design__max_cap_violation__count'}.items()}
        log = (run / 'register-sta' / (corner + '.log')).read_text()
        for kind in ('SETUP','HOLD'):
            text = log.split('R2R_BEGIN_' + kind)[1].split('R2R_END_' + kind)[0]
            values = [float(v) for v in re.findall(r'([0-9.]+)\s+slack \(MET\)', text)]
            if len(values) != 19 or 'VIOLATED' in text:
                raise RuntimeError(f'Explicit R2R query did not check 19 endpoints: {corner}/{kind}')
            entry['r2r_' + kind.lower()] = dict(endpoint_count=len(values), worst_slack_ns=min(values))
        if any(v != 0 for k,v in entry.items() if k.endswith('violation_count')):
            raise RuntimeError(f'Timing violations in {corner}')
        corners[corner] = entry
    klayout = {}
    for name, folder in [('analog','analog-klayout-v0.2'),('digital','digital-klayout-v0.2')]:
        raw = BUILD / folder
        db = ET.parse(raw / 'drc/input_main.lyrdb').getroot()
        count = len(db.findall('./items/item'))
        command_record = read(raw / 'klayout-drc.log.command.json')
        if count != 0 or command_record['exit_code'] != 0 or 'DRC run is clean' not in (raw / 'klayout-drc.log').read_text():
            raise RuntimeError(f'Independent KLayout failed: {name}')
        inputs = read(raw / 'input-hashes.json')
        if sha(raw/'input.gds') != inputs['gds_sha256']:
            raise RuntimeError('Frozen GDS hash changed')
        if name=='digital' and sha(raw/'input.gds') != sha(run/'final/gds/pixel_pwm.gds'):
            raise RuntimeError('KLayout checked a different digital implementation')
        klayout[name] = dict(topcell=db.findtext('top-cell'), item_count=count,
            category_count=len(db.findall('./categories/category')), input_hashes=inputs,
            enabled=['FEOL','BEOL','connectivity','offgrid'], density=False, antenna=False)
        for source, relative in [('klayout-drc.log','drc.log'),('drc/input_main.lyrdb','drc.lyrdb'),
                                 ('input-hashes.json','input-hashes.json')]:
            copy(raw/source, f'klayout/{name}/{relative}')
    macro = read(BUILD/'analog-macro-read-v0.2/macro-read.json')
    sdf = read(EVIDENCE/'sdf/summary.json')
    if not macro['passed'] or not sdf['passed'] or sdf['implementation_run'] != args.run_name:
        raise RuntimeError('Macro reader or matching SDF replay did not pass')
    for name in ['macro-read.json','macro-read.log','macro-read.log.command.json']:
        copy(BUILD/'analog-macro-read-v0.2'/name, name)
    for path in sorted((run/'final').rglob('*')):
        if path.is_file() and path.parent.name in {'gds','lef','nl','pnl','sdc','nom','min','max'}:
            if path.suffix in {'.gds','.lef','.v','.sdc','.spef'}:
                copy(path, 'digital/' + str(path.relative_to(run/'final')))
    for path in sorted((run/'final/sdf').rglob('*.sdf')):
        copy(path, 'digital/' + str(path.relative_to(run/'final')))
    for corner in corners:
        copy(run/'register-sta'/(corner+'.log'),f'digital/sta/{corner}/registers.log')
        for report in ['checks.rpt','max.rpt','min.rpt']:
            copy(run/'55-openroad-stapostpnr'/corner/report,f'digital/sta/{corner}/{report}')
    for source, dest in [('55-openroad-stapostpnr/summary.rpt','digital/sta/summary.rpt'),
        ('70-netgen-lvs/reports/lvs.netgen.rpt','digital/lvs.rpt'),
        ('70-netgen-lvs/reports/lvs.netgen.json','digital/lvs.json'),
        ('64-magic-drc/reports/drc.magic.rpt','digital/magic-drc.rpt'),
        ('warning.log','digital/warnings.log'),('gds-inspection.json','digital/gds-inspection.json')]:
        copy(run/source,dest)
    copy(BUILD/(args.run_name+'.log.command.json'),'digital/flow-command.json')
    copy(BUILD/'tool-versions.json','tool-versions.json')
    copy(BUILD/'environment-inputs.json','environment-inputs.json')
    copy(ROOT/'scripts/physical/pdk-lock.json','pdk-lock.json')
    frozen = BUILD/'frozen-inputs'/args.run_name
    for name in ['config.json','provenance.json','no-pnr.cells']:
        copy(frozen/name,'digital/inputs/'+name)
    normalized = clean(metrics)
    (EVIDENCE/'digital/metrics.json').write_text(json.dumps(normalized,indent=2,allow_nan=False)+'\n')
    before = []
    for name in ['pwm-v0.2','pwm-v0.2-slew','pwm-v0.2-ss','pwm-v0.2-buffers']:
        cmd = read(BUILD/(name+'.log.command.json'))
        item = dict(run_name=name,exit_code=cmd['exit_code'],log_sha256=sha(BUILD/(name+'.log')),
                    local_log=f'build/physical-flow/{name}.log')
        old = BUILD/name/'final/metrics.json'
        if old.exists():
            item['max_slew_violation_count']=read(old)['design__max_slew_violation__count']
        if name=='pwm-v0.2-slew':
            item['reason']='OpenROAD RepairDesignPostGPL killed by Linux OOM; 50 percent slew margins; kernel evidence retained locally'
        before.append(item)
    sources = [ROOT/'rtl/pixel_pwm.v',ROOT/'layout/digital/config.json',ROOT/'scripts/digital/library-lock.json']
    sources += sorted((ROOT/'sim/rtl').glob('*.v'))
    sources += sorted(p for p in (ROOT/'scripts/physical').iterdir() if p.is_file())
    sources += sorted((ROOT/'docs/digital').glob('*.md'))
    files = {str(p.relative_to(EVIDENCE)):sha(p) for p in sorted(EVIDENCE.rglob('*'))
             if p.is_file() and p != EVIDENCE/'summary.json'}
    summary = dict(schema_version=1,checked_on='2026-10-04 Asia/Tokyo',passed=True,
        evidence_level='Standalone routed PWM macro with 9-corner STA, Magic DRC, Netgen LVS, independent KLayout DRC; supported-path SDF to separately extracted analog RC replay',
        run_name=args.run_name, physical_flow_steps=76, flow_exit_code=command['exit_code'],
        pdk_build='54435919abffb937387ec956209f9cf5fd2dfbee', tools=read(EVIDENCE/'tool-versions.json'),
        actual_frozen_input_provenance=read(frozen/'provenance.json'),
        packaging_source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources},
        checkpoints={key:metrics[key] for key in required_zero}, corners=corners,
        worst_setup_slack_ns=metrics['timing__setup__ws'],worst_hold_slack_ns=metrics['timing__hold__ws'],
        worst_r2r_setup_slack_ns=min(c['r2r_setup']['worst_slack_ns'] for c in corners.values()),
        gds=read(run/'gds-inspection.json'), die_area_um2=metrics['design__die__area'],
        instance_count_including_taps_endcaps_fillers=metrics['design__instance__count'],
        sequential_cell_count=metrics['design__instance__count__class:sequential_cell'],
        independent_klayout=klayout, analog_macro_reader=dict(passed=True,lef_sha256=macro['lef_sha256'],
            size_um=macro['size_um'],origin_um=macro['origin_um'],pin_count=len(macro['pins']),obstruction_count=macro['obstruction_count']),
        sdf_replay_summary='evidence/physical/sdf/summary.json', prior_attempts=before,
        sta_assumptions={key:config[key] for key in ['CLOCK_PERIOD','OUTPUT_CAP_LOAD','MAX_TRANSITION_CONSTRAINT',
            'MAX_CAPACITANCE_CONSTRAINT','MAX_FANOUT_CONSTRAINT','CLOCK_UNCERTAINTY_CONSTRAINT',
            'CLOCK_TRANSITION_CONSTRAINT','TIME_DERATING_CONSTRAINT','IO_DELAY_CONSTRAINT',
            'SYNTH_DRIVING_CELL','SYNTH_CLK_DRIVING_CELL']},
        limitations=['72.91 fF output load is a configured assumption, not measured analog input capacitance',
            'No joint analog/digital placement, top LVS/PEX, pads, silicon or optical measurement',
            'KLayout FEOL/BEOL/connectivity/offgrid pass; KLayout density and antenna modes not run',
            'OpenROAD antenna checks passed; IR drop lacks explicit supply-source locations and is not sign-off',
            'Official cell model unsupported XOR/XNOR paths and timing checks retained; SDF critical output path is verified separately',
            'Flow setup R2R infinity was normalized to null in metrics; explicit 19-endpoint register queries provide finite margins',
            'Full pre-run runner snapshot was not retained for initial attempts; frozen inputs, actual command, image digest and post-run input hashes are retained'],
        raw_outputs=f'build/physical-flow/{args.run_name}', evidence_files_sha256=files)
    (EVIDENCE/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print('PASS physical evidence: 9 STA corners; 0 DRC/LVS/slew errors; analog LEF consumed; actual SDF replay checked')


if __name__=='__main__':
    main()

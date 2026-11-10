#!/usr/bin/env python3
"""Drive the r10 output pair from ideal gate sources to isolate the pre-driver."""
from pathlib import Path
import re

from replay import module, read_json, sha
from vcsel_x10_run import BUILD, FRAME, LEGACY, make_deck, solve, emit


def main():
    folder = BUILD / 'net32-ideal-gates-edge5-s40'
    folder.mkdir(parents=True, exist_ok=False)
    identity = make_deck(folder, 32, 20, 40)
    driver = folder/'driver.spice'
    text = driver.read_text()
    text, count = re.subn(r'(?m)^(\.subckt vcsel_servo .+?) params:', r'\1 GP_FORCE GN_FORCE params:', text)
    assert count == 1
    text, count = re.subn(r'(?m)^(XSTEER_0 OUT) GP VX',r'\1 GP_FORCE VX',text)
    assert count == 1
    text, count = re.subn(r'(?m)^(XDUMP_0 DUMMY) GN VX',r'\1 GN_FORCE VX',text)
    assert count == 1
    driver.write_text(text)
    bits = read_json(folder/'stimulus.json')['bits']
    legacy = module(LEGACY,'vcsel_x10_ideal_gate_stimulus')
    ui = identity['end_s']/FRAME
    base_path = folder/'testbench.spice'
    deck = base_path.read_text()
    new_sources = ''
    new_expressions = []
    for name, node, symbols in [('VGPFORCE','gp_force',bits),('VGNFORCE','gn_force',[1-b for b in bits])]:
        new_sources += f'{name} {node} 0 {legacy.pwl(symbols,ui,3.1,5e-12)}\n'
        identity['ports'][name] = node
        new_expressions.extend([f'v({node})',f'i({name})'])
    deck, count = re.subn(r'(?m)^XDRV (.+) 0 vcsel_servo ',
                          new_sources+r'XDRV \1 0 gp_force gn_force vcsel_servo ',deck)
    assert count == 1
    for command in ['save','wrdata waveform.dat']:
        deck,count = re.subn(rf'(?m)^({command} .+)$',r'\1 '+' '.join(new_expressions),deck)
        assert count == 1
    base_path.write_text(deck)
    identity['expressions'].extend(new_expressions)
    for dev in identity['devices']:
        if dev['instance'] in {'XSTEER_0','XDUMP_0'}:
            dev['nodes'][1] = 'gp_force' if dev['instance']=='XSTEER_0' else 'gn_force'
    identity.update(scope='Ideal 0–3.1 V, 5 ps output gate injection; original GP/GN disconnected from the switches, original buffer left unloaded at its outputs. Actual output MOS, servo, package and load unchanged. Both added energy sources counted; counterfactual energy not comparable to the original driver.',
                    gate_source_edge_ps=5, gate_source_rail_V=3.1,
                    gate_nodes=['v(gp_force)','v(gn_force)'],
                    gate_control_driver_sha256=sha(driver), deck_sha256=sha(base_path),
                    control_script_sha256=sha(Path(__file__)))
    emit(folder/'manifest.json',identity)
    solve(folder,identity)


if __name__=='__main__':
    main()

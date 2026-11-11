#!/usr/bin/env python3
"""Frozen-circuit holdouts, predefined lower-rate fallback, and target diagnosis."""
from micro_engine import BUILD, read
from micro_holdout import run as holdout
from micro_run import run

for name,rate,fallback in [('A_rcff31p275',2.0,1.8),('B_vin3p3_dummy27p6k',1.8,1.6)]:
    holdout(name,rate)
    path=BUILD/(name+'-holdout4c2d')/'cases'/f'TT-net{rate:g}-C200-S40/result.json'
    if not read(path)['analysis']['combined_screen_pass']:
        # Keep circuit fixed. Both the failed selected rate and this lower-rate
        # validation remain visible; no parameter tuning against the holdout.
        run(name,[fallback],dc=False)
        run(name,[fallback],dc=False,steps=80)
        holdout(name,fallback)
for name in ['A_rcff31p275','B_vin3p3_dummy27p6k']:
    run(name,[3.2],dc=False)

#!/usr/bin/env python3
"""Reproduce/reuse the frozen r10 nominal and confirmatory frame matrix.

Existing result inputs must match and are reused, not overwritten. Do not run
while another process owns an unfinished case in the same workspace.
"""
import json
from run_r10 import run
from run_esl_r10 import run as run_esl
from analyze import analyze


def main():
    jobs=[]
    for name,corner,temp,voltage in [('TT','typical',25,3.3),('SS','ss',125,2.97),('FF','ff',-40,3.63)]:
        jobs.append((f'frame-{name}-r10',dict(corner=corner,temp=temp,voltage=voltage),False))
    jobs += [
        ('frame-TT-supply-minus-r10',dict(disturb=-.05),False),
        ('frame-TT-supply-plus-r10',dict(disturb=.05),False),
        ('frame-SS-supply-minus-r10',dict(corner='ss',temp=125,voltage=2.97,disturb=-.02),False),
        ('frame-SS-Rsense-plus-r10',dict(corner='ss',temp=125,voltage=2.97,rscale=1.01),False),
        ('frame-FF-Rsense-minus-r10',dict(corner='ff',temp=-40,voltage=3.63,rscale=.99),False),
        ('frame-TT-seed7B43-r10',dict(seed=0x7B43),False),
        ('frame-TT-halfstep-r10',dict(steps=80),False),
        ('frame-TT-supply-minus-ESL0p5n-r10',dict(disturb=-.05,decap_esl=.5e-9),True)]
    rows=[]
    for name,config,esl in jobs:
        r=(run_esl if esl else run)(name,variant='regulated',mode='frame',**config)
        assert r['simulation_ok'],name
        a=analyze(name,grid_ps=2.5,label='fixed-v3-r2')
        rows.append(dict(case=name,label='fixed-v3-r2',passed=a['combined_screen_passed']))
    a=analyze('frame-TT-r10',grid_ps=1.25,label='fixed-v3-grid1p25')
    rows.append(dict(case='frame-TT-r10',label='fixed-v3-grid1p25',passed=a['combined_screen_passed']))
    print(json.dumps(rows,ensure_ascii=False,indent=2))


if __name__=='__main__':main()

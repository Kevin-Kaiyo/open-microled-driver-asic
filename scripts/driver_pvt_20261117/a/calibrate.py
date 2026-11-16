#!/usr/bin/env python3
"""Fit two physical resistor conductances at TT only, quantize and freeze.

Grid results never influence this calibration; this is not per-corner retuning.
It assumes an external precision resistor network; mismatch/TC not included.
"""
import argparse
import numpy as np
import run as a
def fit(family):
 count=0;history=[]
 def f(x):
  nonlocal count
  variant=family+f'-cal{count:02d}';count+=1
  currents=[a.solve(a.GRID[0],variant,level=l,rh=x[0]*1e6,rl=x[1]*1e6)['current_uA'] for l in [0,1]]
  history.append(dict(variant=variant,RH=x[0]*1e6,RL=x[1]*1e6,current_uA=currents))
  return np.array(currents)/[25,100]-1
 coeff=.37 if family.endswith('a37') else .25
 x=np.array([2.98,2.655])*.25/coeff
 for _ in range(8):
  error=f(x)
  if np.max(np.abs(error))<1e-7:break
  h=1e-4;jac=np.column_stack([(f(x+np.eye(2)[k]*h)-error)/h for k in [0,1]])
  x-=np.linalg.solve(jac,error)
 else:raise RuntimeError('TT calibration did not converge')
 quant=100 if family.startswith('trackwide4gm5') else 1000
 rh,rl=np.round(x*1e6/quant)*quant
 record=dict(family=family,fit_corner='TT27C nominal rails only',feedback_coefficient=coeff,quantization_ohm=quant,RH_ohm=float(rh),RL_ohm=float(rl),RH_GND_ohm=float(1/((1-coeff)*1e-6-1/rh)),RL_GND_ohm=float(1/((1-coeff)*1e-6-1/rl)),resistor_interpretation='Four fixed external precision resistors; complementary conductance pair per servo. No automatic trim or on-chip DAC implemented. Quantization is a design-selection grid; resistor tolerance and temperature coefficients not yet applied.',history=history)
 a.emit(a.EV/(family+'-calibration.json'),record)
 for point in a.GRID:
  for l in [0,1]:a.solve(point,family+'-fixed',level=l,rh=rh,rl=rl)
 a.collect()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('family',choices=['track','tracklong','trackwide4','trackwide4gm5','trackwide4gm5a37']);fit(p.parse_args().family)

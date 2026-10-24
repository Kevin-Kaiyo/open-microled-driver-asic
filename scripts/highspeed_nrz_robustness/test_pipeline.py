#!/usr/bin/env python3
"""Meaningful independent assertions for disturbed-supply deck and energy accounting."""
from pathlib import Path
import json, unittest
import numpy as np
import run as r
import validate as v
W=r.ROOT/'build/highspeed-nrz-robustness/baseline-r1'
class PipelineTest(unittest.TestCase):
    def test_independent_resistor_corner(self):
        c=v.case(W,'A','test',res_corner='ss');deck,*_=r.build_deck(W,c)
        self.assertIn('" ff',deck);self.assertIn('" res_ss',deck);self.assertNotIn('" res_ff',deck)
    def test_fixed_data_not_tied_to_rail(self):
        c=v.case(W,'A','test',vdd=3.65,data_mode='fixed',data_high_V=3.6);deck,*_=r.build_deck(W,c)
        self.assertIn('VDD vdd 0 3.65',deck);self.assertIn('VDATA data 0 PWL(',deck);self.assertIn(' 3.6\n',deck)
    def test_tracking_data_dynamic_energy_sense(self):
        c=v.case(W,'B','test',rail_profiles={'VDD':{'kind':'sine','amplitude_V':.05,'frequency_Hz':10e6}})
        deck,vectors,*_=r.build_deck(W,c)
        self.assertIn('BTRACK data_track 0 V=v(bit)*v(vdd)',deck);self.assertIn('VDATA data data_track 0',deck)
        self.assertIn(('vdd_voltage','v(vdd)'),vectors);self.assertIn(('data_current','i(VDATA)'),vectors)
    def test_varying_voltage_energy_not_constant(self):
        mm=r.module(W/'inputs/legacy/metrics.py','metrics_test');t=np.linspace(0,1e-6,1001);vv=3+.6*t/t[-1];ii=np.full_like(t,-1e-3)
        result=mm.energy_window(t,vv,ii,0,1e-6,1000)
        self.assertAlmostEqual(result['net_J'],3.3e-9,places=18);self.assertNotAlmostEqual(result['net_J'],3e-9,places=12)
    def test_supply_package_source_energy_and_ground(self):
        c=v.case(W,'A','test',supply_package={'r_vdd_ohm':1,'l_vdd_H':2e-9,'r_vss_ohm':1,'l_vss_H':2e-9},data_mode='fixed',data_high_V=3.6)
        deck,vectors,devices,rails=r.build_deck(W,c)
        self.assertEqual(rails['VDD'][0],'vdd_source')
        self.assertIn('RVSSPKG diegnd pvss 1',deck)
        self.assertIn(('vdd_voltage','v(vdd_source)'),vectors)
        self.assertIn(('die_vss_voltage','v(diegnd)'),vectors)
        self.assertIn('XDRV data out vdd vh vl diegnd ',deck)
        self.assertIn('VDATA data 0 PWL(',deck)
    def test_frozen_led_and_rx_identity(self):
        for f in ['legacy/metrics.py','legacy/analyze.py','led.spice']:
            self.assertEqual(r.sha(W/'inputs'/f),r.sha(v.BASE/'inputs'/f))
        self.assertEqual(r.sha(W/'stimulus.json'),r.sha(v.BASE/'stimulus.json'))
if __name__=='__main__':unittest.main()

#!/usr/bin/env python3
"""Focused regression checks for physical composition and measured energy boundaries."""
import json,sys,unittest
from pathlib import Path
import experiment as e
import run as r
import validate as v

class Pipeline(unittest.TestCase):
 def test_compose_preserves_mos_and_passive_counts(self):
  m=json.loads((e.WORK/'manifest.json').read_text());p=e.WORK/'inputs/physical'
  old=r.parse_core(p/'B-AFTER.spice')[2];new=r.parse_core(p/'N-reference-RC.spice')[2];joint=r.parse_core(p/'B-reference-RC.spice')[2]
  self.assertEqual(len(joint),len(old)+len(new));self.assertEqual(len(joint),28)
  def counts(path):
   x=[line.split()[0][0].upper() for line in path.read_text().splitlines() if line and line[0].upper() in ['R','C']];return {k:x.count(k) for k in ['R','C']}
  a,b,c=map(counts,[p/'B-AFTER.spice',p/'N-reference-RC.spice',p/'B-reference-RC.spice'])
  self.assertEqual(c,{k:a[k]+b[k] for k in a})
  self.assertEqual(r.sha(e.WORK/'stimulus.json'),r.sha(e.OLD/'stimulus.json'));self.assertEqual(r.sha(e.WORK/'inputs/led.spice'),r.sha(e.OLD/'inputs/led.spice'))
 def test_independent_reference_resistor_temperature(self):
  case=e.make('test',co='ss',temp=125,vdd=2.95,variant='BASELINE',resistor_errors={'RREF':.01},resistor_tc_ppm={'RREF':100})
  deck,vec,dev,rails=r.build_deck(e.WORK,case)
  self.assertIn('RREF_EXT vdummy bias '+str(88386.1064910889*1.01*1.0098),deck)
  self.assertIn('RDUMMY_EXT vdummy dummy 28000.0',deck)
 def test_real_power_sources_counted_and_no_ideal_dummy(self):
  case=e.make('test',anchor_error=.001,anchor_rout_ohm=10)
  deck,vec,dev,rails=r.build_deck(e.WORK,case)
  self.assertEqual(set(rails),{'VLED','VDD','VRAW','VREF'})
  self.assertNotIn('\nVDUMMY ',deck);self.assertIn('RANCHOR ref_source vref 10',deck)
  for key in rails:
   self.assertIn((key.lower()+'_voltage','v('+rails[key][0]+')'),vec)
   self.assertIn((key.lower()+'_current','i('+key+')'),vec)
  self.assertIn(('data_current','i(VDATA)'),vec)
 def test_startup_keeps_reference_delay_distinct(self):
  case=e.make('test',dc_bit=1,startup={'stop_s':100e-6,'ramp_s':1e-6,'anchor_delay_s':10e-6})
  deck,vec,dev,rails=r.build_deck(e.WORK,case)
  self.assertIn('VREF ref_source 0 PWL(0 0 1e-05 0 1.1000000000000001e-05 2.5)',deck)
  self.assertIn('VRAW vin_source 0 PWL(0 0 1e-06 5.0)',deck)
  self.assertIn('uic\nwrdata',deck)
 def test_restart_retains_residual_rails_and_clamp_energy(self):
  work=r.BUILD/'clamped-r2'
  case=v.case(work,'B','restart_test','ff',-40,3.65,variant='REFERENCE',dc_bit=1,compensation='shunt',vi_comp_F=150e-12,keeper_ohm=1.8e6,startup={'initial_op':True,'rail_pwl':{'VLED':[[0,5]],'VREF':[[0,2.5]],'VRAW':[[0,5],[20e-6,5],[21e-6,0],[23e-6,0],[24e-6,5]],'VDISABLE':[[0,0],[20e-6,3.3],[44e-6,3.3],[44.1e-6,0]]}})
  deck,vec,dev,rails=r.build_deck(work,case)
  self.assertIn('VLED led_a 0 PWL(0 5)',deck);self.assertIn('VREF ref_source 0 PWL(0 2.5)',deck)
  self.assertNotIn(' uic\nwrdata',deck);self.assertIn('RKEEP out 0 1800000.0',deck)
  self.assertIn('CICOMP in2 0 1.5e-10',deck);self.assertIn('VDISABLE',rails)
  self.assertIn(('vdisable_current','i(VDISABLE)'),vec)
 def test_selected_keeper_is_a_real_switched_path_and_comp_pin_is_explicit(self):
  work=r.BUILD/'selected-final-r2'
  case=v.case(work,'B','selected_test','ff',-40,3.65,variant='REFERENCE',dc_bit=1,compensation='shunt',vi_comp_F=150e-12,comp_package={'r_ohm':1.,'l_H':5e-9,'esr_ohm':.5})
  deck,vec,dev,rails=r.build_deck(work,case)
  self.assertEqual(len(dev),21);self.assertIn('RKEEP out kret 1800000.0',deck);self.assertNotIn('RKEEP out 0 ',deck)
  self.assertIn('RCOMPPIN in2 comp_pin 1.0',deck);self.assertIn('LCOMPPIN comp_pin comp_esr 5e-09',deck);self.assertIn('RCOMPESR comp_esr comp_cap 0.5',deck)
  self.assertIn('CICOMP comp_cap 0 1.5e-10',deck);self.assertNotIn('VDUMMY ',deck)
if __name__=='__main__':unittest.main()

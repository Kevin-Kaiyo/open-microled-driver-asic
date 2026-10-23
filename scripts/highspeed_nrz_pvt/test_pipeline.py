#!/usr/bin/env python3
"""Small non-SPICE regression tests for experiment identity and safety guards."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import explore as e
import formal
r=e.r

class PipelineTests(unittest.TestCase):
 def test_parallel_resistor_rejected(self):
  with self.assertRaises(ValueError):e.circuit('A',{'rin':1,'poly_l':1})
 def test_unknown_config_rejected(self):
  with self.assertRaises(ValueError):e.circuit('A',{'rni':20000})
 def test_unaccounted_rail_rejected(self):
  with self.assertRaises(ValueError):e.circuit('B',{'rref_source':'mystery'})
 def test_resistor_model_and_all_mos_remain_explicit(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'core.spice';p.write_text(e.circuit('B',{'poly_l':58}))
   _,_,dev=r.parse_core(p);res=r.parse_passives(p)
   self.assertEqual(len(dev),9);self.assertEqual(len(res),1)
   self.assertEqual(res[0]['nodes'],['data','di','vss'])
 def test_candidate_definition_cannot_change_reference_source(self):
  with tempfile.TemporaryDirectory() as folder:
   w=Path(folder);e.add(w,'B','candidate',{'poly_l':58})
   with self.assertRaises(ValueError):e.add(w,'B','candidate',{'poly_l':58,'rref_source':'vdummy'})
 def test_rref_value_propagated(self):
  with tempfile.TemporaryDirectory() as folder:
   w=Path(folder);e.add(w,'B','candidate',{'rref_ohm':90000})
   c=r.case_spec(w,'B','candidate',.5)
   self.assertIn('RREF_EXT vdd bias 90000',r.build_deck(w,c)[0])
 def test_cache_rejects_deck_drift(self):
  with tempfile.TemporaryDirectory() as folder:
   w=Path(folder);e.add(w,'A','candidate',{});c=r.case_spec(w,'A','candidate',1)
   r.emit(w/'cases'/c['name']/'result.json',{'case':c,'deck_sha256':'wrong'})
   with self.assertRaises(ValueError):r.run_case(w,c)
 def test_included_model_drift_rejected(self):
  with tempfile.TemporaryDirectory() as folder:
   w=Path(folder);e.add(w,'A','candidate',{});c=r.case_spec(w,'A','candidate',1)
   deck=r.build_deck(w,c)[0]
   result={'case':c,'deck_sha256':__import__('hashlib').sha256(deck.encode()).hexdigest(),'input_identity':{'led.spice':r.sha(w/'inputs/led.spice')},'stimulus_sha256':r.sha(w/'stimulus.json')}
   r.emit(w/'cases'/c['name']/'result.json',result)
   (w/'inputs/led.spice').write_text('* mutated model')
   with self.assertRaisesRegex(ValueError,'included input'):r.run_case(w,c)
 def test_frozen_input_drift_rejected(self):
  with tempfile.TemporaryDirectory() as folder:
   w=Path(folder);(w/'inputs').mkdir();p=w/'inputs/file';p.write_text('original');(w/'stimulus.json').write_text('{}')
   r.emit(w/'manifest.json',{'source_hashes':{'file':r.sha(p)},'stimulus_sha256':r.sha(w/'stimulus.json')});formal.verify(w)
   p.write_text('modified')
   with self.assertRaises(ValueError):formal.verify(w)

if __name__=='__main__':unittest.main()

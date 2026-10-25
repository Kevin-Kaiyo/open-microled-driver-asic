import unittest,tempfile,json
from pathlib import Path
import numpy as np
import run as engine
class Harness(unittest.TestCase):
 def test_signed_energy_crossings(self):
  x=engine.signed_integrals(np.array([0.,2.]),np.array([-3.,1.]))
  self.assertAlmostEqual(x['positive_J'],.25);self.assertAlmostEqual(x['returned_J'],2.25);self.assertAlmostEqual(x['net_J'],-2.)
 def test_six_pair_device_inventory(self):
  w=engine.BUILD/'dc-calibration-r1'
  for route,count in [('A',20),('B',21),('C',49)]:
   d,n=engine.inventory(w,route,['d0','d1','out','vin','vdd','vref','0','disable'])
   self.assertEqual(len(d),count);self.assertTrue(all(len(x['nodes'])==4 for x in d));self.assertNotIn('0',n)
 def test_stimulus_tamper_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   w=Path(tmp);(w/'inputs').mkdir();(w/'inputs/source.spice').write_text('original source');(w/'stimulus.json').write_text('{"bits":[0,1]}')
   e={'inputs':{'source.spice':engine.sha(w/'inputs/source.spice')},'stimulus_sha256':engine.sha(w/'stimulus.json')};(w/'manifest.json').write_text(json.dumps(e));engine.verify(w)
   (w/'stimulus.json').write_text('{"bits":[1,1]}')
   with self.assertRaisesRegex(AssertionError,'stimulus drift'):engine.verify(w)
 def test_pwl_has_finite_edges(self):
  s=engine.pwl([0,1,0],1e-9,3.3,20e-12)
  self.assertIn('1.02e-09',s);self.assertIn('2.02e-09',s)
if __name__=='__main__':unittest.main()

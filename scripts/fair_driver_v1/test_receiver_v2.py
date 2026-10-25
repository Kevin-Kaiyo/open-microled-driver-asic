"""Behavioral fairness/guard tests; no SPICE, frozen circuit or result edits."""
import importlib.util
import copy
from pathlib import Path
import unittest

import numpy as np

from scripts.fair_driver_v1 import receiver as legacy
from scripts.fair_driver_v1.rx_audit import reference_filter
from scripts.fair_driver_v1.test_receiver import waveform

MODULE = Path(__file__).with_name('receiver_equal_latency_v2.py')


def module():
    assert MODULE.exists(), 'Equal absolute latency receiver is not implemented'
    spec = importlib.util.spec_from_file_location('fair_receiver_v2_tested', MODULE)
    loaded = importlib.util.module_from_spec(spec); spec.loader.exec_module(loaded)
    return loaded


class EqualLatencyTests(unittest.TestCase):
    def setUp(self):
        self.rx = module(); self.st = self.rx.make_stimulus()

    def trace(self, route, rate=.5, delay_s=0, levels=None):
        pam = route == 'C'; ui=(2 if pam else 1)*self.st['eta']/(rate*1e9)
        levels = levels or ([25,50,75,100] if pam else [25,100])
        t,y=waveform(self.st['symbols_C' if pam else 'symbols_N'], levels, ui, 40)
        if delay_s:
            t=np.r_[0,t+delay_s]; y=np.r_[y[0],y]
        return t,y

    def test_payload_frame_and_gray_bits_are_unchanged(self):
        old=legacy.make_stimulus()
        for key in ['bits','symbols_N','symbols_C','eta','seed','gray_mapping']:
            self.assertEqual(old[key],self.st[key])
        ranges=dict(old['ranges_bits']);ranges['training_scoring']=[64,512]
        self.assertEqual(self.st['ranges_bits'],ranges)

    def test_ideal_routes_decode_with_identical_absolute_candidate_grid(self):
        grids=[]
        for route,rate in [('A',.5),('B',1.),('C',.5)]:
            t,y=self.trace(route,rate)
            r=self.rx.analyze(t,y,self.st,route,rate)
            self.assertTrue(r['passed'],r['checks'])
            self.assertEqual(r['validation']['bit_count'],4096)
            self.assertEqual(r['validation']['bit_errors'],0)
            grids.append([q['delay_s'] for q in r['sampling']['training_scan']])
            self.assertEqual(len(grids[-1]),1601)
            self.assertEqual(r['sampling']['training_scored_bits'],448)
            self.assertEqual(r['sampling']['training_guard_bits'],64)
        self.assertEqual(grids[0],grids[1]);self.assertEqual(grids[1],grids[2])
        np.testing.assert_allclose(np.diff(grids[0]),5e-12,rtol=0,atol=1e-24)
        self.assertEqual(grids[0][0],0.);self.assertEqual(grids[0][-1],8e-9)

    def test_nrz_delay_longer_than_two_symbols_is_recovered(self):
        # This fixture exposed v1's architecture-dependent latency truncation.
        t,y=self.trace('A',1.,delay_s=2.5e-9)
        old=legacy.analyze(t,y,legacy.make_stimulus(),'A',1.)
        new=self.rx.analyze(t,y,self.st,'A',1.)
        self.assertGreater(old['validation']['bit_errors'],100)
        self.assertGreater(new['sampling']['delay_symbol_UI'],2.)
        self.assertLessEqual(new['sampling']['delay_s'],8e-9)
        self.assertEqual(new['validation']['bit_errors'],0)
        self.assertTrue(new['passed'],new['checks'])

    def test_validation_cannot_change_training_including_max_rate(self):
        for route in ['A','C']:
            t,y=self.trace(route,2.)
            r=self.rx.analyze(t,y,self.st,route,2.)
            changed=y.copy();changed[t>=576*self.st['eta']/2e9]=40e-6
            modified=self.rx.analyze(t,changed,self.st,route,2.)
            self.assertEqual(r['sampling'],modified['sampling'])
            self.assertGreater(modified['validation']['bit_errors'],100)
            self.assertGreater(r['sampling']['training_to_validation_slack_s'],19e-9)
            labels=copy.deepcopy(self.st)
            labels['bits'][576:]=[1-x for x in labels['bits'][576:]]
            labels['symbols_N']=list(labels['bits'])
            mapping={(0,0):0,(0,1):1,(1,1):2,(1,0):3}
            labels['symbols_C']=[mapping[tuple(labels['bits'][j:j+2])] for j in range(0,4736,2)]
            relabeled=self.rx.analyze(t,changed,labels,route,2.)
            self.assertEqual(r['sampling'],relabeled['sampling'])

    def test_training_guard_rejects_an_unsupported_extreme_rate(self):
        # Keep a valid monotonic fixture:5ps edges need spacing exceeding5ps.
        t,y=waveform(self.st['symbols_N'],[25,100],self.st['eta']/10e9,8)
        with self.assertRaisesRegex(ValueError,'guard'):
            self.rx.analyze(t,y,self.st,'A',10.)

    def test_horizontal_margin_includes_the_exit_from_a_threshold_plateau(self):
        # Omitting plateau exit at2ns would falsely claim2ns instead of1ns.
        t=np.array([0,1,2,3,5])*1e-9; y=np.array([0.,1.,1.,2.,2.])
        result=self.rx._horizontal(t,y,np.array([3e-9]),np.array([2.]),np.array([1]),
                                   np.array([1.]),0,5e-9,5e-9,5e-9)
        self.assertAlmostEqual(result['min_ps'],1000.)

    def test_plateau_rule_uses_training_absolute_time_then_earliest_tie(self):
        t,y=self.trace('C',.25)
        r=self.rx.analyze(t,y,self.st,'C',.25)
        scan=r['sampling']['training_scan']
        eligible=[z for z in scan if z['amplitude_plateau_eligible']]
        best=max(z['training_time_margin_ps'] for z in eligible)
        expected=min(z['delay_s'] for z in eligible if z['training_time_margin_ps']==best)
        self.assertEqual(r['sampling']['delay_s'],expected)
        self.assertGreater(r['horizontal_margin']['min_ps'],1000)
        self.assertLessEqual(max(z['min_signed_decision_distance_uA'] for z in scan)-next(
            z['min_signed_decision_distance_uA'] for z in scan if z['delay_s']==expected),1.00001e-6)

    def test_independent_parallel_poles_match_filter_on_nonuniform_input(self):
        rng=np.random.default_rng(83)
        t=np.r_[0,np.cumsum(10**rng.uniform(-13,-10,3000))]
        y=rng.uniform(20e-6,105e-6,len(t))
        _,observed=self.rx.filter_trace(t,y)
        independently_filtered=reference_filter(t,y)
        np.testing.assert_allclose(observed,independently_filtered,rtol=0,atol=1e-16)
        _,dc=self.rx.filter_trace(t,np.full(len(t),73e-6))
        np.testing.assert_allclose(dc,73e-6,rtol=0,atol=1e-18)

    def test_wrong_bits_and_low_amplitude_still_fail(self):
        t,y=self.trace('A',levels=[58,67])
        r=self.rx.analyze(t,y,self.st,'A',.5)
        self.assertEqual(r['validation']['bit_errors'],0)
        self.assertFalse(r['checks']['decision_distance_7p5uA'])
        self.assertFalse(r['passed'])
        t,y=self.trace('C')
        start=576*self.st['eta']/.5e9;y[t>=start]=25e-6
        r=self.rx.analyze(t,y,self.st,'C',.5)
        self.assertGreater(r['validation']['bit_errors'],100)
        self.assertFalse(r['passed'])


if __name__=='__main__':
    unittest.main()

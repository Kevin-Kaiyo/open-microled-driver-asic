"""Behavioral tests for the common frozen receiver; no SPICE or EDA calls."""
import importlib.util
import math
from pathlib import Path
import unittest
import numpy as np

MODULE = Path(__file__).with_name('receiver.py')

def receiver():
    assert MODULE.is_file(), 'receiver.py is not implemented yet'
    spec = importlib.util.spec_from_file_location('fair_receiver_tested', MODULE)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def waveform(symbols, levels, ui, subdivisions=12):
    """Independent finite-edge transmitter fixture; constant levels between edges."""
    times, values = [], []
    previous = levels[symbols[0]]
    for j, symbol in enumerate(symbols):
        level = levels[symbol]
        times.extend([j * ui, j * ui + 5e-12])
        values.extend([previous, level])
        for q in range(1, subdivisions):
            times.append((j + q / subdivisions) * ui)
            values.append(level)
        previous = level
    times.append(len(symbols) * ui)
    values.append(previous)
    return np.array(times), np.array(values) * 1e-6

class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.rx = receiver()
        self.s = self.rx.make_stimulus()

    def trace(self, route, symbols=None, levels=None, rate=.5):
        is_c = route == 'C'
        sy = symbols if symbols is not None else self.s['symbols_C' if is_c else 'symbols_N']
        lv = levels if levels is not None else ([25, 50, 75, 100] if is_c else [25, 100])
        ui = (2 if is_c else 1) * (4096 / 4736) / (rate * 1e9)
        return waveform(sy, lv, ui)

    def test_frame_overhead_and_gray_transition_coverage(self):
        # Catches training incorrectly counted as payload, Gray-order errors and poor stimuli.
        self.assertEqual(len(self.s['bits']), 4736)
        self.assertEqual(self.s['ranges_bits'], {'warmup': [0,64], 'training': [64,576], 'training_scoring': [64,572], 'validation': [576,4672], 'tail': [4672,4736]})
        self.assertAlmostEqual(self.s['eta'], 4096/4736)
        self.assertEqual(self.s, self.rx.make_stimulus())
        gray = [(0,0), (0,1), (1,1), (1,0)]
        rebuilt = [b for x in self.s['symbols_C'] for b in gray[x]]
        self.assertEqual(rebuilt, self.s['bits'])
        self.assertEqual(self.s['symbols_N'], self.s['bits'])
        validation = self.s['symbols_C'][288:2336]
        self.assertTrue(all(abs(validation.count(k)-512) <= 26 for k in range(4)))
        self.assertEqual({(a,b) for a,b in zip(validation,validation[1:]) if a!=b}, {(a,b) for a in range(4) for b in range(4) if a!=b})

    def test_ideal_nrz_and_pam4_decode_same_payload(self):
        # Catches wrong line-rate overhead, PAM4 symbol rate and threshold ordering.
        for route in ['A', 'B', 'C']:
            with self.subTest(route=route):
                t,y = self.trace(route)
                r = self.rx.analyze(t,y,self.s,route,.5)
                self.assertTrue(r['passed'], r['checks'])
                self.assertEqual(r['validation']['bit_count'],4096)
                self.assertEqual(r['validation']['bit_errors'],0)
                self.assertEqual(r['validation']['symbol_errors'],0)
                self.assertEqual(r['validation']['symbol_count'],2048 if route=='C' else 4096)
                self.assertAlmostEqual(r['rates']['frame_duration_s'],8.192e-6)
                self.assertAlmostEqual(r['rates']['line_Gbps'],.578125)
                self.assertAlmostEqual(r['rates']['symbol_Gbaud'],.2890625 if route=='C' else .578125)
                self.assertGreaterEqual(r['horizontal_margin']['min_ps'],100)
                self.assertAlmostEqual(r['horizontal_margin']['min_bit_UI'],r['horizontal_margin']['min_symbol_UI']*(2 if route=='C' else 1))
                self.assertEqual(len(r['sampling']['training_scan']),193)

    def test_wrong_validation_bit_and_gray_symbol_are_counted(self):
        # Catches error masking and treating one PAM4 symbol error as one bit error.
        nrz=list(self.s['symbols_N']);nrz[576+513]^=1
        t,y=self.trace('A',nrz)
        a=self.rx.analyze(t,y,self.s,'A',.5)
        self.assertEqual(a['validation']['bit_errors'],1)
        self.assertEqual(a['validation']['error_bit_offsets'],[513])
        self.assertFalse(a['passed'])
        pam=list(self.s['symbols_C']);pam[288+513]=(pam[288+513]+2)%4
        t,y=self.trace('C',pam)
        c=self.rx.analyze(t,y,self.s,'C',.5)
        self.assertEqual(c['validation']['symbol_errors'],1)
        self.assertEqual(c['validation']['bit_errors'],2)
        self.assertEqual(c['validation']['error_bit_offsets'],[1026,1027])
        self.assertFalse(c['passed'])

    def test_insufficient_amplitude_fails_even_with_zero_raw_errors(self):
        # Catches normalizing away the smaller PAM4 level separation.
        for route,levels in [('A',[58,67]),('C',[32,55,70,93])]:
            t,y=self.trace(route,levels=levels)
            r=self.rx.analyze(t,y,self.s,route,.5)
            self.assertEqual(r['validation']['bit_errors'],0)
            self.assertLess(r['validation']['decision_distance_min_uA'],7.5)
            self.assertFalse(r['checks']['decision_distance_7p5uA'])
            self.assertFalse(r['passed'])

    def test_validation_waveform_cannot_change_training_choice(self):
        # Catches the last training samples reaching into validation during delay search.
        for route in ['A','C']:
            t,y=self.trace(route)
            baseline=self.rx.analyze(t,y,self.s,route,.5)
            modified=y.copy();start=576*(4096/4736)/(.5e9)
            modified[t>=start]=40e-6
            altered=self.rx.analyze(t,modified,self.s,route,.5)
            self.assertEqual(baseline['sampling'],altered['sampling'])
            self.assertGreater(altered['validation']['bit_errors'],100)

    def test_absolute_time_margin_is_not_symbol_ui(self):
        # Catches unit confusion between PAM4 symbols and bits.
        t,y=self.trace('C')
        r=self.rx.analyze(t,y,self.s,'C',.5)
        margin=r['horizontal_margin']
        self.assertAlmostEqual(margin['min_ps'],margin['min_symbol_UI']*r['rates']['symbol_UI_s']*1e12)
        self.assertAlmostEqual(margin['min_ps'],margin['min_bit_UI']*r['rates']['bit_UI_s']*1e12)
        self.assertEqual(r['checks']['time_margin_100ps'],margin['min_ps']>=100)

    def test_noise_ber_uses_gray_hamming_and_shared_current_units(self):
        # Increasing physical noise must increase conditional BER; PAM4 has closer thresholds.
        out={}
        for route in ['A','C']:
            t,y=self.trace(route)
            out[route]=self.rx.analyze(t,y,self.s,route,.5)['conditional_noise_BER']
            errors=[x['conditional_BER'] for x in out[route]]
            self.assertTrue(all(a<=b for a,b in zip(errors,errors[1:])))
        self.assertGreater(out['C'][-1]['conditional_BER'],out['A'][-1]['conditional_BER'])

    def test_filter_preserves_dc_and_matches_independent_step_solution(self):
        # Catches accidental zero-state optical/RX startup and wrong cascade dynamics.
        t=np.array([0,1e-13,1e-11,5e-11,2e-10,1e-9,4e-9])
        a,b=self.rx.filter_trace(t,np.full(len(t),73e-6))
        np.testing.assert_allclose(a,73e-6,rtol=0,atol=1e-18)
        np.testing.assert_allclose(b,73e-6,rtol=0,atol=1e-18)
        t=np.r_[0.,1e-16,np.linspace(1e-12,3e-9,300)]
        y=np.ones_like(t);y[0]=0
        _,got=self.rx.filter_trace(t,y)
        tau1=200e-12;tau2=1/(2*math.pi*1e9)
        want=1-(tau1*np.exp(-t/tau1)-tau2*np.exp(-t/tau2))/(tau1-tau2)
        np.testing.assert_allclose(got,want,rtol=0,atol=2e-7)

    def test_gaussian_tail_probability_does_not_cancel(self):
        # Catches 1-CDF cancellation silently dropping half of high-SNR NRZ errors.
        got=self.rx._noise_ber(np.array([25.,100.]),np.array([0,1]),np.array([62.5]),False)[-1]
        expected=.5*math.erfc(37.5/(4*math.sqrt(2)))
        self.assertAlmostEqual(got['conditional_BER']/expected,1.,places=12)
        # Independent closed-form Gray-PAM4 result for four ideal equally likely levels.
        got=self.rx._noise_ber(np.array([25.,50.,75.,100.]),np.arange(4),np.array([37.5,62.5,87.5]),True)[-1]
        q=lambda x:.5*math.erfc(x/(4*math.sqrt(2)))
        expected=.75*q(12.5)+.5*q(37.5)-.25*q(62.5)
        self.assertAlmostEqual(got['conditional_BER']/expected,1.,places=12)

    def test_horizontal_margin_interpolates_crossings_in_absolute_time(self):
        # A hand-drawn 20ps triangular pulse has 5ps one-sided decision margin,
        # regardless of a much longer nominal symbol interval.
        t=np.array([0,90,100,110,200])*1e-12
        r=self.rx._horizontal(t,np.array([25.,25.,100.,25.,25.]),np.array([100e-12]),
                              np.array([100.]),np.array([1]),np.array([62.5]),0,200e-12,100e-12,50e-12)
        self.assertAlmostEqual(r['min_ps'],5.,places=9)
        self.assertAlmostEqual(r['min_symbol_UI'],.05,places=12)
        self.assertAlmostEqual(r['min_bit_UI'],.1,places=12)

    def test_slow_plateau_uses_training_time_margin_not_roundoff_winner(self):
        # Catches an almost-flat amplitude plateau selecting its late edge at low rate.
        margins=[]
        for rate in [.1,.25,.5]:
            ui=2*self.s['eta']/(rate*1e9)
            t,y=waveform(self.s['symbols_C'],[25,50,75,100],ui,subdivisions=40)
            r=self.rx.analyze(t,y,self.s,'C',rate)
            scan=r['sampling']['training_scan'];chosen=next(x for x in scan if x['delay_symbol_UI']==r['sampling']['delay_symbol_UI'])
            best=max(x['min_signed_decision_distance_uA'] for x in scan)
            self.assertLessEqual(best-chosen['min_signed_decision_distance_uA'],1.00001e-6)
            margins.append(r['horizontal_margin']['min_ps'])
        self.assertGreater(margins[1],1000)
        self.assertGreater(margins[0],margins[1])
        self.assertGreater(margins[1],margins[2])

    def test_explicit_time_origin_does_not_change_decisions(self):
        # Catches interpreting absolute timestamp offset as data delay.
        t,y=self.trace('A')
        a=self.rx.analyze(t,y,self.s,'A',.5)
        shifted=dict(self.s);shifted['time_origin_s']=2e-6
        b=self.rx.analyze(t+2e-6,y,shifted,'A',.5)
        self.assertEqual(a['validation']['decoded_symbols'],b['validation']['decoded_symbols'])
        self.assertAlmostEqual(a['sampling']['delay_symbol_UI'],b['sampling']['delay_symbol_UI'])
        self.assertAlmostEqual(a['horizontal_margin']['min_ps'],b['horizontal_margin']['min_ps'],places=6)

    def test_rejects_bad_or_truncated_time_series(self):
        # Catches silently extrapolating missing tail or accepting duplicate/nonfinite times.
        t,y=self.trace('A')
        for tt,yy in [(t[:-100],y[:-100]),(np.r_[t[0],t[0],t[2:]],y),(t,np.where(np.arange(len(y))==10,np.nan,y))]:
            with self.assertRaises(ValueError):self.rx.analyze(tt,yy,self.s,'A',.5)

if __name__=='__main__':
    unittest.main()

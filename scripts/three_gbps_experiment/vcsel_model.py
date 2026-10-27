#!/usr/bin/env python3
"""Independent public-figure VCSEL optical proxy (W), never measured optical output.

Use conduction current from vcsel_research.spice JMON (1 V = 1 A).
`figure3mA_proxy` is a magnitude-only normalized S21 shape approximation.
It is NOT de-embedded and can double-count electrical roll-off with assumed CJ.
Only numpy is required. Exact zero-order-hold pole integration is used.
"""
from pathlib import Path
import json
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
PARAMETER_PATH=ROOT/'analog/models/vcsel_research_20261027/parameters.json'
PARAMETERS=json.loads(PARAMETER_PATH.read_text())

def _linear_extend(x,xp,fp):
    a=np.asarray(x,dtype=float)
    y=np.interp(a,xp,fp)
    y=np.where(a>xp[-1],fp[-1]+(a-xp[-1])*(fp[-1]-fp[-2])/(xp[-1]-xp[-2]),y)
    return y

def static_power(current_A):
    """25 C source-figure P(I) proxy in W. >7.5mA extrapolation is unvalidated."""
    p=PARAMETERS['pi']
    return _linear_extend(np.maximum(np.asarray(current_A,dtype=float),0),p['current_A'],p['power_W'])

def static_voltage(current_A):
    """Approximate 25 C terminal I-V; simulator uses identical rounded knots."""
    p=PARAMETERS['iv']
    return _linear_extend(np.maximum(np.asarray(current_A,dtype=float),0),[0]+p['current_A'],[0]+p['voltage_V'])

def _poles(response):
    if response=='figure3mA_proxy':
        d=PARAMETERS['dynamic'];w=2*np.pi*d['f0_Hz'];z=d['zeta'];wp=2*np.pi*d['fp_Hz']
        return np.array([-w*z+1j*w*np.sqrt(1-z*z),-w*z-1j*w*np.sqrt(1-z*z),-wp],dtype=complex),w*w*wp
    if response in ['lowpass8GHz_assumed','lowpass4GHz_assumed']:
        wp=2*np.pi*PARAMETERS['alternative_responses'][response]['pole_Hz']
        return np.array([-wp],dtype=complex),wp
    raise ValueError('Unknown response '+response)

def transfer_function(frequency_Hz,response='figure3mA_proxy'):
    f=np.asarray(frequency_Hz,dtype=float)
    if response=='static':return np.ones(f.shape,dtype=complex)
    poles,numerator=_poles(response)
    return numerator/np.prod(2j*np.pi*f[...,None]-poles,axis=-1)

def filter_power(time_s,power_W,response='figure3mA_proxy'):
    """Uniform samples; each input sample holds until the next sample.

    Initial state is equilibrium at power_W[0]. No added delay, noise or clipping.
    Negative optical overshoots, if present, remain visible as proxy invalidity.
    """
    t=np.asarray(time_s,dtype=float);x=np.asarray(power_W,dtype=float)
    if t.ndim!=1 or x.shape!=t.shape or t.size<2:raise ValueError('Need matching 1D arrays, >=2 samples')
    dt=np.diff(t)
    if not np.isfinite(t).all() or not np.isfinite(x).all() or np.any(dt<=0):raise ValueError('Non-finite or unordered inputs')
    if np.max(abs(dt-dt.mean()))>max(1e-18,dt.mean()*1e-5):raise ValueError('Resample to uniform grid before optical filtering')
    if response=='static':return x.copy()
    poles,numerator=_poles(response);out=np.zeros(x.size,dtype=complex)
    for k,pole in enumerate(poles):
        residue=numerator/np.prod(pole-np.delete(poles,k))
        decay=np.exp(pole*dt.mean());gain=residue*np.expm1(pole*dt.mean())/pole
        state=-residue*x[0]/pole
        out[0]+=state
        for n in range(1,x.size):
            state=decay*state+gain*x[n-1]
            out[n]+=state
    if np.max(np.abs(out.imag))>1e-10:raise RuntimeError('Complex conjugate cancellation failed')
    return out.real

def optical_power(time_s,current_A,response='figure3mA_proxy'):
    """Public authoritative API: current A -> research optical-power proxy W."""
    return filter_power(time_s,static_power(current_A),response=response)

def response_metadata(response='figure3mA_proxy'):
    if response=='figure3mA_proxy':return dict(PARAMETERS['dynamic'])
    if response not in PARAMETERS['alternative_responses']:raise ValueError(response)
    return {'name':response,**PARAMETERS['alternative_responses'][response]}

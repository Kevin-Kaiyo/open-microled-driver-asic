#!/usr/bin/env python3
"""Independent numerical audit of source extraction and RC reference-plane math.

Reads the frozen ZIP directly with OOXML relationships; imports none of the
producer's extraction or plotting routines. This is not an optical-model fit.
"""
from pathlib import Path
from io import BytesIO
import csv, hashlib, json, math, posixpath, re, zipfile
import xml.etree.ElementTree as ET
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / 'evidence/microled-dynamic-20261029'
OUT = Path(__file__).parent / 'audit-microled-contract.json'
N = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def xlsx(blob):
    with zipfile.ZipFile(BytesIO(blob)) as z:
        ss = []
        if 'xl/sharedStrings.xml' in z.namelist():
            ss = [''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rel = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        books = {}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).find(N+'sheets'):
            target = rel[sheet.attrib[R+'id']]
            target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            cells = {}
            for node in ET.fromstring(z.read(target)).iter(N+'c'):
                value = node.find(N+'v')
                value = None if value is None else value.text
                if node.attrib.get('t') == 's':
                    value = ss[int(value)]
                elif node.attrib.get('t') == 'inlineStr':
                    value = ''.join(node.find(N+'is').itertext())
                cells[node.attrib['r']] = value
            books[sheet.attrib['name']] = cells
        return books


def run():
    ledger = json.loads((EV/'source-ledger.json').read_text())
    source = ledger['assets'][0]
    archive = ROOT/source['original_archive']
    assert sha(archive) == source['archive_sha256']
    books = {}
    with zipfile.ZipFile(archive) as z:
        for w in source['workbooks']:
            blob = z.read(w['archive_member'])
            assert hashlib.sha256(blob).hexdigest() == w['sha256']
            books[w['archive_member']] = xlsx(blob)
    book = books['yellow20_s21_bandwidths.xlsx']
    s = book['Shifted_Curves']
    header = {float(v[:-1]): re.sub(r'\d', '', k) for k,v in s.items() if re.fullmatch('[A-Z]+1',k) and k!='A1'}
    selected = np.genfromtxt(EV/'yellow20-s21-selected.csv', delimiter=',', names=True)
    freq = np.array([float(s[f'A{row}'])*1e6 for row in range(2,2003)])
    assert np.array_equal(freq, selected['frequency_Hz'])
    source_bw = book['Bandwidths']
    report = []
    for bias in [25,50,60,80,100]:
        col = next(c for current,c in header.items() if math.isclose(current,bias/1e6,abs_tol=1e-16))
        db = np.array([float(s[f'{col}{row}']) for row in range(2,2003)])
        assert np.array_equal(db, selected[f'S21_dB_at_{bias}uA'])
        bwrow = next(row for row in range(2,47) if math.isclose(float(source_bw[f'A{row}']), bias/1e6, abs_tol=1e-16))
        cutoffs = []
        for level, c in [(-3,'C'),(-6,'D')]:
            k = next(k for k in range(len(db)-1) if db[k]>level and db[k+1]<=level)
            crossing = np.interp(level, [db[k+1], db[k]], [freq[k+1],freq[k]]) / 1e6
            claimed = float(source_bw[f'{c}{bwrow}'])
            assert abs(crossing-claimed) < 1e-8
            cutoffs.append(float(crossing))
        report.append({'bias_uA':bias,'points_matching_source_exactly':len(db),'BW3_MHz':cutoffs[0], 'BW6_MHz':cutoffs[1], 'S21_at_1p85GHz_dB':float(np.interp(1.85e9,freq,db))})
    low = books['frequency_response_low_current.xlsx']['Sheet1']
    assert all(float(low[f'B{k}']) == selected['S21_dB_at_100uA'][k-2] for k in range(2,2003))
    pi = books['diamond-optical-power.xlsx']['Sheet1']
    pi_csv = list(csv.DictReader((EV/'yellow20-optical-power.csv').open()))
    source_pi = [(float(pi[f'A{k}']),float(pi[f'B{k}'])) for k in range(3,1000) if pi.get(f'A{k}') is not None and pi.get(f'B{k}') is not None]
    assert source_pi == [(float(r['current_A']),float(r['source_optical_power_uW'])) for r in pi_csv]
    rc = json.loads((EV/'reference-plane-calculation.json').read_text())
    ivp = ROOT/'analog/models/measured-led/lin2026-yellow20-diamond-iv.csv'
    assert sha(ivp) == rc['static_iv_sha256']
    iv = list(csv.DictReader(ivp.open()))
    currents = [float(r['current_A']) for r in iv]
    rc_results = []
    for row in rc['points']:
        b = row['bias_uA']*1e-6
        k = next(k for k in range(len(iv)-1) if currents[k] <= b <= currents[k+1])
        rd = (float(iv[k+1]['voltage_V'])-float(iv[k]['voltage_V']))/(currents[k+1]-currents[k])
        C = row['assumed_C_F']; Rs = row['illustrative_Rsource_Ohm']
        assert math.isclose(rd, row['rd_Ohm'],rel_tol=1e-12)
        # Solve the one-node KCL directly, rather than use the producer's pole.
        omega = 2*np.pi*np.geomspace(1e3,1e11,4096)
        Y = 1/rd+1j*omega*C
        conductive_from_1A = 1/Y/rd
        conductive_from_1V = 1/(1+Rs*Y)/rd
        normalized_voltage = conductive_from_1V*(rd+Rs)
        predicted_I = 1/(1+1j*omega*row['current_drive_tau_ps']*1e-12)
        predicted_V = 1/(1+1j*omega*row['voltage_drive_tau_ps']*1e-12)
        err = max(float(np.max(abs(conductive_from_1A-predicted_I))),float(np.max(abs(normalized_voltage-predicted_V))))
        assert err<1e-14
        rc_results.append({'bias_uA':row['bias_uA'],'rd_Ohm':rd,'direct_KCL_vs_report_max_complex_error':err})
    contract = json.loads((EV/'response-contract.json').read_text())
    assert contract['observed_response']['phase'] is None
    assert 'no new transient model activated' in contract['status']
    result = {'status':'PASS within stated audit scope', 'audit_script_sha256':sha(Path(__file__)),
        'scope':'Independent OOXML cell/CSV equality, source hashes, cutoffs, units and reference-plane circuit algebra. Primary article wording, instrumentation calibration and licenses are ledger-reviewed, not independently remeasured or newly reverified here.',
        'source_archive_sha256':sha(archive), 'reviewed_files':{p.name:sha(p) for p in [EV/'response-contract.json',EV/'source-ledger.json',EV/'reference-plane-calculation.json']},
        'magnitude':report,'PI_rows_match':len(source_pi),'RC_direct_KCL':rc_results,
        'limitations':['Composite source S21 includes fixture, electrical-to-optical conversion and receiver response; no unique intrinsic lifetime follows.','Magnitude-only data do not determine phase, eye or BER.','200 fF and 50 ohm are explicit illustrations, not fits or actual A-route impedance.','Physical-pixel pairing, measurement temperature, receiver deembedding and S21 phase remain unknown.','No model switch or route ranking is justified by this extraction alone.'],
        'recommendations':['Keep old baseline frozen; use new model ID plus DC and coupled regression for any future fit.','Retain complete-chain versus deembedded-block alternatives and never count RC/RX twice.']}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'curves':len(report),'PI_rows':len(source_pi),'output':str(OUT)}))


if __name__ == '__main__':
    run()

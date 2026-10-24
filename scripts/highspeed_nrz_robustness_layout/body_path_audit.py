"""Explain body self/transfer equality from actual resistor graph and GDS positions."""
from pathlib import Path
import json
import hashlib
import re
import numpy as np
import klayout.db as k
ROOT=Path(__file__).resolve().parents[2]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def inspect(folder):
    c=json.loads((folder/'physical-contract.json').read_text());top=c['top']
    rc=folder/'full-rc'/(top+'_rc.spice');res_ext=folder/'full-rc'/(top+'.res.ext')
    text=rc.read_text();rawext=res_ext.read_text()
    original=(folder/'unmodified-full-rc'/(top+'_rc.spice')).read_text()
    def device_r_lines(t):return [l for l in re.sub(r'\n\+\s*',' ',t).splitlines() if l.startswith(('R','X'))]
    assert device_r_lines(text)==device_r_lines(original)
    edges=[]
    for line in text.splitlines():
        t=line.split()
        if t and t[0].startswith('R') and all(n.startswith('VSS') for n in t[1:3]):edges.append((t[0],t[1],t[2],float(t[3])))
    source=c['extracted_resistor_mapping'][0]['rc_nodes']['B']
    sink=next(d for d in c['extracted_device_mapping'] if d['original_instance']=='XN2')['rc_nodes']['B']
    assert source!=sink
    names=sorted({n for _,a,b,_ in edges for n in (a,b)}-{'VSS'});idx={n:i for i,n in enumerate(names)}
    g=np.zeros((len(names),len(names)));rhs=np.zeros(len(names));rhs[idx[source]]=1
    for _,a,b,r in edges:
        for n in (a,b):
            if n!='VSS':g[idx[n],idx[n]]+=1/r
        if a!='VSS' and b!='VSS':g[idx[a],idx[b]]-=1/r;g[idx[b],idx[a]]-=1/r
    v=np.linalg.solve(g,rhs);voltage={n:float(v[i]) for n,i in idx.items()}|{'VSS':0}
    flows=[]
    for name,a,b,r in edges:
        current=(voltage[a]-voltage[b])/r
        flows.append(dict(name=name,nodes=[a,b],resistance_ohm=r,current_A=current,power_W=current*current*r,voltage_drop_V=voltage[a]-voltage[b]))
    incident=[e for e in flows if sink in e['nodes']]
    assert len(incident)==1 and source in incident[0]['nodes']
    assert abs(incident[0]['current_A'])<1e-12
    assert abs(voltage[source]-voltage[sink])<1e-9
    assert abs(sum(e['power_W'] for e in flows)-voltage[source])<1e-8
    scale=float(next(l.split()[3] for l in rawext.splitlines() if l.startswith('scale ')))/100
    coords={m.group(1):[float(m.group(2))*scale,float(m.group(3))*scale] for m in re.finditer(r'^rnode "([^"]+)" \S+ \S+ (\S+) (\S+) \S+',rawext,re.M)}
    gdspath=folder/'generate'/(top+'.gds');lay=k.Layout();lay.read(str(gdspath));cell=lay.cell(top)
    poly=k.Region(cell.begin_shapes_rec(lay.layer(30,0)));active=k.Region(cell.begin_shapes_rec(lay.layer(22,0)));hr=k.Region(cell.begin_shapes_rec(lay.layer(110,5)))
    rin=c['resistors'][0];d=next(x for x in c['devices'] if x['name']=='N2')
    rpoly=(poly&hr).merged();assert rpoly.count()==1
    rbox=rpoly.bbox();rcenter=[rbox.center().x*lay.dbu,rbox.center().y*lay.dbu]
    win=k.Region(k.DBox(d['cx']-.6,d['cy']-d['w_um']/2-.01,d['cx']+.6,d['cy']+d['w_um']/2+.01).to_itype(lay.dbu))
    chan=(poly&active&win).merged();assert chan.count()==1
    nbox=chan.bbox();ncenter=[nbox.center().x*lay.dbu,nbox.center().y*lay.dbu]
    assert np.allclose(coords[source],rcenter,atol=1e-12)
    assert np.allclose(coords[sink],ncenter,atol=1e-12)
    native=(folder/'readback'/(top+'.ext')).read_text()
    native_lines=[l for l in native.splitlines() if l.startswith('device ') and ('ppolyf_u_1k_6p0' in l or ('nfet_06v0' in l and f' {int((d["cx"]-d["l_um"]/2)/scale)} ' in l))]
    return dict(folder=str(folder.relative_to(ROOT)),rc_sha256=sha(rc),res_ext_sha256=sha(res_ext),gds_sha256=sha(gdspath),
      source_node=source,target_node=sink,source_coord_um=coords[source],target_coord_um=coords[sink],
      actual_gds_resistor_center_um=rcenter,actual_gds_n2_channel_center_um=ncenter,distinct_nodes_and_actual_positions=True,
      target_degree=1,target_single_resistor=incident[0],self_ohm=voltage[source],target_transfer_ohm=voltage[sink],
      total_network_power_W=sum(e['power_W'] for e in flows),dominant_resistors=sorted(flows,key=lambda e:e['power_W'],reverse=True)[:8],
      source_incident_resistors=[e for e in flows if source in e['nodes']],native_device_records=native_lines,
      conclusion='Exact equality is the open-circuit DC voltage of a degree-one target body node connected only to the source body node; it is not node merging and not a MOS/substrate field result.')

def main():
    result={'schema_version':1,'passed':True,'method':'Independent nodal 1 A DC solution of unchanged extracted VSS resistor graph; no MOS current or capacitance, no substrate field solver.',
     'runs':[inspect(ROOT/'build/highspeed-nrz-robustness-layout'/run/'A') for run in ('hv-A8-r3','hv-A8-ties-r5')],
     'source_locators':{str(p.relative_to(ROOT)):{'sha256':sha(p),'role':role} for p,role in [
        (ROOT/'build/layout/tools/magic/resis/ResUtils.c','ResEachTile records substrate tile from lower-left device position; lines 970-999'),
        (ROOT/'build/layout/tools/magic/resis/ResBasic.c','Device substrate terminal breakpoint is placed at device tile center; lines 370-384'),
        (ROOT/'build/layout/tools/magic/resis/ResJunct.c','ResNewSubDevice creates substrate breakpoint in tile; lines 124-169')]},
     'limitations':['This proves the topology exported by pinned Magic. It does not prove physical substrate transfer resistance or a particular extraction bug.',
       'Adding body contacts changed real GDS but did not change the degree-one XN2 body link, so this network cannot establish local collection improvement.',
       'Both original/native .res.ext and capacitance-corrected RC retain these same R/device body connections. C bookkeeping does not create the topology.',
       'Further local body-return claims require independently validated substrate extraction or field solution. No further speculative layout edits are justified.']}
    out=ROOT/'evidence/highspeed-nrz-robustness-layout/body-path-audit.json';out.write_text(json.dumps(result,indent=2)+'\n')
    for r in result['runs']:print(r['folder'],r['source_coord_um'],r['target_coord_um'],r['self_ohm'],r['target_single_resistor'],r['dominant_resistors'][:2])
if __name__=='__main__':main()

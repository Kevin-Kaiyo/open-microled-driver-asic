"""Independent label-free Metal1…5/Via1…4 physical connectivity audit.
Net names do not join shapes. This distinguishes a real join from label aliases.
"""
from pathlib import Path
import argparse,hashlib,json
import klayout.db as k
ROOT=Path(__file__).resolve().parents[2]
def check(path,routing):
 l=k.Layout();l.read(str(path));c=l.cell('pixel_integrated');n=k.LayoutToNetlist('pixel_integrated',l.dbu)
 a={}
 for name,lv in {'m1':34,'v1':35,'m2':36,'v2':38,'m3':42,'v3':40,'m4':46,'v4':41,'m5':81}.items():
  a[name]=k.Region(c.begin_shapes_rec(l.layer(lv,0)));n.register(a[name],name);n.connect(a[name])
 for i in range(1,5):n.connect(a[f'm{i}'],a[f'v{i}']);n.connect(a[f'v{i}'],a[f'm{i+1}'])
 n.extract_netlist()
 def probe(layer,x,y):
  found=n.probe_net(a[layer],k.Point(round(x/l.dbu),round(y/l.dbu)))
  return found.cluster_id if found else None
 endpoints={'digital_pwm':('m3',150.28,111.52),'analog_pwm':('m3',119.7,111.52),'digital_VDD':('m4',173.04,57.33),'analog_VDD':('m3',26,117.52),'digital_VSS':('m5',160,60.63),'analog_VSS':('m3',26,105.52)}
 ids={name:probe(*point)for name,point in endpoints.items()}
 for name,p in routing['ports'].items():
  b=p['rect_um'];ids[name]=probe('m'+p['layer'][-1],(b[0]+b[2])/2,(b[1]+b[3])/2)
 expected={'VDD':['digital_VDD','analog_VDD','VDD'],'VSS':['digital_VSS','analog_VSS','VSS'],'pwm_monitor':['digital_pwm','analog_pwm','pwm_monitor']}
 joins={name:len(set(ids[v] for v in group))==1 and ids[group[0]] is not None for name,group in expected.items()}
 unique=len(set(ids[p] for p in routing['ports']))==len(routing['ports'])
 checks=dict(all_endpoint_geometry_present=all(v is not None for v in ids.values()),all_three_required_macro_joins=all(joins.values()),nineteen_unique_external_nets=unique,correct_external_count=len(routing['ports'])==19,no_power_short=ids['digital_VDD']!=ids['digital_VSS'],no_pwm_power_short=ids['digital_pwm']not in [ids['digital_VDD'],ids['digital_VSS']])
 return dict(gds_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),method='KLayout label-free flattened polygon extraction; actual Metal1-5 and Via1-4 geometry only; no global or same-name joining',endpoint_cluster_ids=ids,macro_joins=joins,checks=checks,passed=all(checks.values()))
def main():
 p=argparse.ArgumentParser();p.add_argument('--run',default='r3');a=p.parse_args();folder=ROOT/'build/integration'/a.run
 result=check(folder/'pixel_integrated.gds',json.loads((folder/'routing.json').read_text()))
 (folder/'geometry-connectivity.json').write_text(json.dumps(result,indent=2)+'\n');print(result['passed'])
if __name__=='__main__':main()

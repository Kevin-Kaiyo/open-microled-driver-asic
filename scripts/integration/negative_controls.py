"""Create physical-open/physical-PG-short GDS controls; golden design unchanged."""
from pathlib import Path
import argparse,json,shutil
import klayout.db as k
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--baseline',default='r3');a=p.parse_args();base=ROOT/'build/integration'/a.baseline
 for mode in ['pwm-open','pg-short']:
  folder=ROOT/'build/integration'/f'{a.baseline}-{mode}';folder.mkdir(parents=True,exist_ok=True)
  l=k.Layout();l.read(str(base/'pixel_integrated.gds'));c=l.cell('pixel_integrated')
  if mode=='pwm-open':
   layer=l.layer(42,0);r=k.Region(c.shapes(layer));r-=k.Region(k.DBox(130,111.1,132,111.95).to_itype(l.dbu));c.shapes(layer).clear();c.shapes(layer).insert(r)
  else:
   for layer,r in [(46,[134.65,79.65,140.35,80.35]),(81,[134.65,79.65,135.35,80.35]),(41,[134.87,79.87,135.13,80.13])]:c.shapes(l.layer(layer,0)).insert(k.DBox(*r))
  l.write(str(folder/'pixel_integrated.gds'))
  for name in ['extract.tcl','routing.json']:shutil.copyfile(base/name,folder/name)
  data=dict(control=mode,baseline_gds=str(base/'pixel_integrated.gds'),mutation='Actual Metal3 gap x=130…132µm; endpoint labels/ports and golden unchanged'if mode=='pwm-open'else'Actual top Metal4/Metal5/Via4 conductive bridge between common VDD/VSS; golden unchanged')
  (folder/'control.json').write_text(json.dumps(data,indent=2)+'\n')
  print(folder)
if __name__=='__main__':main()

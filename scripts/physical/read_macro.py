"""Read the actual analog abstract with OpenROAD/OpenDB and check its interface.

Executed by the pinned Linux OpenROAD; creates no joint design or placement.
"""
from pathlib import Path
import collections
import hashlib
import json
import os
import odb

root = Path(os.environ['ASICFLOW_ROOT'])
folder = Path(os.environ['ASICFLOW_OUTPUT'])
lef = folder / 'input.lef'
technology = root / 'build/layout/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef'
db = odb.dbDatabase.create()
odb.read_lef(db, str(technology))
library = odb.read_lef(db, str(lef))
master = library.findMaster('pixel_driver_layout')
if master is None:
    raise RuntimeError('Analog macro was not read into OpenDB')
units = db.getTech().getDbUnitsPerMicron()
size = [master.getWidth() / units, master.getHeight() / units]
origin = [v / units for v in master.getOrigin()]
expected = {'VSS':('INOUT','GROUND'), 'bias':('INOUT','SIGNAL'),
            'gate':('OUTPUT','SIGNAL'), 'pwm':('INPUT','SIGNAL'),
            'pwm_b':('OUTPUT','SIGNAL'), 'led_k':('INOUT','SIGNAL'),
            'vlogic':('INOUT','POWER')}
pins = {}
def rectangle(box):
    return [v / units for v in [box.xMin(), box.yMin(), box.xMax(), box.yMax()]]
def in_boundary(rect):
    moved = [rect[0]+origin[0], rect[1]+origin[1], rect[2]+origin[0], rect[3]+origin[1]]
    return min(moved[0:2]) >= -1e-6 and moved[2] <= size[0]+1e-6 and moved[3] <= size[1]+1e-6
for terminal in master.getMTerms():
    boxes = [box for pin in terminal.getMPins() for box in pin.getGeometry()]
    pins[terminal.getName()] = dict(direction=str(terminal.getIoType()), use=str(terminal.getSigType()),
        geometry=[dict(layer=box.getTechLayer().getName(), rect_um=rectangle(box)) for box in boxes])
obstructions = list(master.getObstructions())
checks = dict(size=all(abs(a-b)<1e-6 for a,b in zip(size,[95.0,37.66])),
              origin=all(abs(a-b)<1e-6 for a,b in zip(origin,[0.0,0.3])),
              seven_named_pins=set(pins)==set(expected),
              directions_and_uses=all((pins[p]['direction'],pins[p]['use'])==expected[p] for p in expected),
              all_pin_geometry_on_metal3=all(p['geometry'] and all(g['layer']=='Metal3' for g in p['geometry']) for p in pins.values()),
              pin_rectangles_inside_origin_adjusted_boundary=all(in_boundary(g['rect_um']) for p in pins.values() for g in p['geometry']),
              obstructions_present=bool(obstructions),
              obstructions_inside_origin_adjusted_boundary=all(in_boundary(rectangle(b)) for b in obstructions))
result = dict(evidence_level='Actual analog LEF consumed by pinned OpenROAD/OpenDB; no common top or placement',
              macro=master.getName(), db_units_per_um=units, size_um=size, origin_um=origin, pins=pins,
              obstruction_count=len(obstructions), obstruction_layers=dict(collections.Counter(b.getTechLayer().getName() for b in obstructions)),
              lef_sha256=hashlib.sha256(lef.read_bytes()).hexdigest(), technology_lef_sha256=hashlib.sha256(technology.read_bytes()).hexdigest(),
              checks=checks, passed=all(checks.values()))
(folder / 'macro-read.json').write_text(json.dumps(result,indent=2)+'\n')
if not result['passed']:
    raise RuntimeError('Analog macro interface check failed')
print('PASS actual analog LEF: 95 x 37.66 um; origin (0, 0.3); seven pins; Metal3 ports and OBS')

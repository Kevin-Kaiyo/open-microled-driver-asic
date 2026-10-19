"""Generate a 39-MOS external-passive test macro from frozen electrical sources."""
from pathlib import Path
import re,json,hashlib
import klayout.db as k
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'layout/startup_v3'; OUT.mkdir(exist_ok=True)
PDK=ROOT/'build/layout/pdk/gf180mcuD'
TOP='startup_test_macro'
PORTS='VSS VREF VSAFE VBUF LED_A RAW_PWM FAULT PERMIT VSET SENSE PB N2 CTRL FAULT_HB LED_K REFOUT BIAS GATE PWM_B SAFE_OUT PWM_DRIVE'.split()
dev=[];sources=[]
def parse(path,prefix,mapping):
 text=path.read_text();sources.append(str(path.relative_to(ROOT)))
 for line in text.splitlines():
  if not line.upper().startswith('X'):continue
  t=line.split(); model={'nmos_6p0':'nfet_06v0','pmos_6p0':'pfet_06v0'}.get(t[5],t[5]); p=dict(re.findall(r'(\w+)=([^ ]+)',line))
  dev.append(dict(name=prefix+t[0][1:],model=model,w=float(p['w'].rstrip('u')),l=float(p['l'].rstrip('u')),nodes=[mapping.get(n,prefix+n.upper()) for n in t[1:5]]))
parse(ROOT/'analog/reference/vset_servo_with_junctions.spice','R_',{'vdd':'VREF','vss':'VSS','vset':'VSET','sense':'SENSE','iout':'REFOUT','pb':'PB','n2':'N2','ctrl':'CTRL'})
parse(ROOT/'analog/startup_v2/reference_isolator_tg.spice','I_',{'refout':'REFOUT','bias':'BIAS','fault':'FAULT','vdd':'VSAFE','vss':'VSS'})
parse(ROOT/'analog/safety/fault_gate.spice','F_',{'raw':'RAW_PWM','fault':'FAULT','permit':'PERMIT','out':'SAFE_OUT','vdd':'VSAFE','vss':'VSS'})
parse(ROOT/'analog/safety/fault_led_clamp.spice','C_',{'fault':'FAULT','anode':'LED_A','cathode':'LED_K','vss':'VSS','fault_hb':'FAULT_HB'})
parse(ROOT/'analog/driver/pixel_driver.spice','P_',{'led_k':'LED_K','pwm':'PWM_DRIVE','vlogic':'VBUF','bias':'BIAS','gate':'GATE','pwm_b':'PWM_B','0':'VSS'})
assert len(dev)==33
# Spacious single-row analog teaching macro, not area optimized.
cx=14
for d in dev:
 d['cx']=cx;d['cy']=145 if d['w']>=20 else 100
 cx += max(18,d['l']+12)
width=cx+28;buf_x=cx+4;buf_y=100
nets=PORTS.copy()
for d in dev:
 for n in d['nodes']:
  if n not in nets:nets.append(n)
buses={n:(0 if i==0 else 5+3*i) for i,n in enumerate(nets)}
# Local buses stop at actual terminals; VSS wide star rail is contacted near centre.
xs={n:[] for n in nets}
for d in dev:
 cx0=d['cx'];dx=d['l']/2+.26;bx=cx0-max(3.5,d['l']/2+2.5)
 for n,x in zip(d['nodes'],[cx0-dx,cx0,cx0+dx,bx]):xs[n].append(x)
for n,x in [('SAFE_OUT',buf_x+1.2),('PWM_DRIVE',buf_x+3.5),('VBUF',buf_x+4.4),('VSS',buf_x+.3)]:xs[n].append(x)
spans={n:[min(v)-.5,max(v)+.5] for n,v in xs.items()}
anchors={n:((spans[n][0]+spans[n][1])/2 if n in ['VSS','VREF','VSAFE','VBUF','LED_A'] else spans[n][0]+.3) for n in PORTS}
assert max(buses.values()) < 90
# Gold schematic is flattened original electrical source connectivity; official
# library is included independently and retains its original license notice.
lib=PDK/'libs.ref/gf180mcu_fd_sc_mcu7t5v0/spice/gf180mcu_fd_sc_mcu7t5v0.spice'
body=re.search(r'(?im)^\.SUBCKT gf180mcu_fd_sc_mcu7t5v0__buf_2 .*?^\.ENDS',lib.read_text(),re.S).group(0)
(OUT/'official_buf_2.spice').write_text('* From GF180MCU public standard cell library, Apache-2.0.\n* Full source and license retained in pinned PDK.\n'+body+'\n')
gold=['* 39 MOS physical test macro. All four resistors/compensation are external.','* No ideal passive is claimed as manufactured inside this cell.', '.include official_buf_2.spice',f'.subckt {TOP} '+ ' '.join(PORTS)]
for d in dev:gold.append(f"X{d['name']} {' '.join(d['nodes'])} {d['model']} w={d['w']:g}u l={d['l']:g}u")
gold += ['XBUF SAFE_OUT PWM_DRIVE VBUF VBUF VSS VSS gf180mcu_fd_sc_mcu7t5v0__buf_2',f'.ends {TOP}']
(OUT/'startup_test_macro.spice').write_text('\n'.join(gold)+'\n')
# Extract exact official GDS cell; recursively retain all geometry.
lay=k.Layout();lay.read(str(PDK/'libs.ref/gf180mcu_fd_sc_mcu7t5v0/gds/gf180mcu_fd_sc_mcu7t5v0.gds'))
opt=k.SaveLayoutOptions();opt.select_cell(lay.cell('gf180mcu_fd_sc_mcu7t5v0__buf_2').cell_index());opt.add_cell(lay.cell('gf180mcu_fd_sc_mcu7t5v0__filltie').cell_index());lay.write(str(OUT/'official_buf_2.gds'),opt)
manifest=dict(top=TOP,ports=PORTS,buses_um=buses,bus_spans_um=spans,port_anchor_um=anchors,devices=dev,buffer=dict(cell='gf180mcu_fd_sc_mcu7t5v0__buf_2',origin_um=[buf_x,buf_y],mos=6),external_passives=[dict(name='RBIAS',nodes=['PB','VSS'],nominal='100k'),dict(name='CCOMP',nodes=['N2','CTRL'],nominal='3p'),dict(name='RRELEASE',nodes=['LED_A','FAULT_HB'],nominal='100k'),dict(name='RSET',nodes=['SENSE','VSS'],nominal='5k')],external_voltage=dict(nodes=['VSET','VSS'],nominal=.5),source_sha256={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},physical_claim='Pre-pad external-passive 39-MOS macro; not a complete ASIC or validated external PCB')
(OUT/'contract.json').write_text(json.dumps(manifest,indent=2)+'\n')
base=(ROOT/'scripts/layout/generate_pixel.tcl').read_text().split('set devices {')[0]
tcl=[base,'set devices {']
for d in dev:tcl.append(' {'+' '.join([d['name'],d['model'],str(d['w']),str(d['l']),str(d['cx']),str(d['cy'])]+d['nodes'])+'}')
tcl += ['}', 'foreach device $devices {',' lassign $device name type w l cx cy d g s b',' load $name',' box values 0 0 0 0',' gf180mcu::${type}_draw [dict merge [gf180mcu::${type}_defaults] [dict create w $w l $l]]',' save $name','}',f'gds read {OUT}/official_buf_2.gds','load startup_assembly','foreach device $devices {',' lassign $device name type w l cx cy d g s b',' getcell $name child 0 0 parent ${cx}um ${cy}um','}',f'getcell gf180mcu_fd_sc_mcu7t5v0__buf_2 child 0 0 parent {buf_x}um {buf_y}um',f'getcell gf180mcu_fd_sc_mcu7t5v0__filltie child 0 0 parent {buf_x+4.48}um {buf_y}um','select top cell',f'flatten -nolabels {TOP}',f'load {TOP}']
tcl += ['set buses [dict create '+' '.join(f'{n} {y}' for n,y in buses.items())+']']
for n,y in buses.items():
 tcl += [f'rect metal3 {spans[n][0]} {y-(4 if n=="VSS" else .3)} {spans[n][1]} {y+(4 if n=="VSS" else .3)}',f'box values {anchors.get(n,spans[n][0]+.3)-.2}um {y-.2}um {anchors.get(n,spans[n][0]+.3)+.2}um {y+.2}um',f'label {n} center metal3']
 if n in PORTS:tcl+=['port make']
tcl += ['foreach device $devices {',' lassign $device name type w l cx cy d g s b',' set dx [expr {$l/2.0+0.26}]',' set gx $cx',' set gy [expr {$cy-$w/2.0-0.28}]',' set bx [expr {$cx-max(3.5,$l/2.0+2.5)}]',' set ringx [expr {$cx-$l/2.0-0.98}]',' rect metal1 $bx [expr {$cy-0.25}] [expr {$ringx+0.15}] [expr {$cy+0.25}]',' foreach pin [list [list $d [expr {$cx-$dx}] $cy] [list $s [expr {$cx+$dx}] $cy] [list $g $gx $gy] [list $b $bx $cy]] {','  lassign $pin net x y','  padvia metal1 metal2 via1 $x $y','  set by [dict get $buses $net]','  rect metal2 [expr {$x-0.2}] [expr {$by-0.2}] [expr {$x+0.2}] [expr {$y+0.2}]','  padvia metal2 metal3 via2 $x $by',' }','}']
for n,x,y in [('SAFE_OUT',buf_x+1.2,buf_y+1.85),('PWM_DRIVE',buf_x+3.5,buf_y+2.45),('VBUF',buf_x+4.4,buf_y+3.92),('VSS',buf_x+.3,buf_y)]:
 by=buses[n];tcl += [f'padvia metal1 metal2 via1 {x} {y}',f'rect metal2 {x-.2} {by-.2} {x+.2} {y+.2}',f'padvia metal2 metal3 via2 {x} {by}']
tcl += ['select top cell','drc style drc(full)','drc style','drc check','drc catchup','puts "V3_DRC_COUNT [drc list count total]"','puts "V3_DRC_ERRORS [drc listall why]"',f'save {TOP}','extract all','ext2spice lvs','ext2spice',f'gds write {TOP}.gds','quit -noprompt']
(OUT/'generate.tcl').write_text('\n'.join(tcl)+'\n')
print(json.dumps(dict(mos=39,width=width,buses=len(nets),buffer=[buf_x,buf_y],output=str(OUT))))

#!/usr/bin/env python3
"""Actual B-v6r schematic, derived from preserved B-v6 with verified source-R delta."""
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/driver-interface-20261115/assets'
CASE=ROOT/'build/driver-interface-20261115/MicroLED/B-protected_v6r/fault-f2-net1.6-s40'
NS='http://www.w3.org/2000/svg';ET.register_namespace('',NS)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def tag(s):return '{'+NS+'}'+s
def main():
 base=OUT/'micro-protection-v6.svg';base_source=OUT/'micro-protection-v6.source.json'
 old=json.loads(base_source.read_text());m=json.loads((CASE/'manifest.json').read_text())
 deck=(CASE/'testbench.spice').read_text()
 ds={line.split()[0]:line.split() for line in deck.splitlines() if line and line[0] not in ['+','*']}
 previous={line.split()[0]:line.split() for line in (ROOT/old['source_case']/'testbench.spice').read_text().splitlines() if line and line[0] not in ['+','*']}
 assert ds['RDISABLE']==['RDISABLE','disable_src','disable','100']
 assert ds['VDISABLE'][1:3]==['disable_src','0']
 assert m['sources']['VDISABLE']=='disable_src' and len(m['devices'])==39
 for name,row in previous.items():
  if name.startswith(('XEN','XLS','XISO','XCLAMP','XFASTOFF','XREADY','XNAND','XSAFE','XDATAIN','RGATE','RREADY','CREADY','XDRV')):assert ds[name]==row,name
 assert ds['XFASTOFF'][6:8]==['w=4u','l=0.7u']
 assert 'let fp=-v(disable_src)*i(VDISABLE)' in deck
 root=ET.fromstring(base.read_text())
 for el in list(root):
  if el.tag!=tag('text'):continue
  value=''.join(el.itertext())
  if 'protected_v6' in value:el.text=value.replace('protected_v6','protected_v6r')
  if value.startswith('disable 高时主动放电'):
   root.remove(el)
  if value.startswith('本图省略原参考源'):
   el.text='本图省略原参考源、输出核心与 6 MOS 电平转换；高边其余端接同 v3r。v6r 新增保护命令 100 Ω。'
  if value.startswith('新增电阻及 MOS'):
   el.text='VDISABLE 在 disable_src 端计能，含 100 Ω 损耗；所有 7 源计能。图对应实际候选，不代表 PVT、PEX 或流片资格。'
 # Add the actual command-source series resistor inside READY panel, as a separate named net.
 fragment=ET.fromstring(f'''<g xmlns="{NS}">
 <text x="760" y="415" font-size="18" fill="#385568">disable_src</text>
 <text x="970" y="415" font-size="18" text-anchor="middle" fill="#385568">RDISABLE 100 Ω</text>
 <text x="1140" y="415" font-size="18" fill="#385568">disable</text>
 <path d="M700 435 H900 M1040 435 H1240" stroke="#385568" stroke-width="2.5" fill="none"/>
 <rect x="900" y="427" width="140" height="16" fill="white" stroke="#385568" stroke-width="2.5"/>
 </g>''')
 idx=next(i for i,e in enumerate(list(root)) if e.tag==tag('rect') and e.get('y')=='500')
 for offset,el in enumerate(list(fragment)):root.insert(idx+offset,el)
 svg=OUT/'micro-protection-v6r.svg';svg.write_text(ET.tostring(root,encoding='unicode')+'\n')
 import cairosvg
 cairosvg.svg2png(url=str(svg),write_to=str(svg.with_suffix('.png')),scale=1.3)
 result=dict(status='actual_candidate_schematic_not_qualification',source_case=str(CASE.relative_to(ROOT)),deck_sha256=sha(CASE/'testbench.spice'),manifest_sha256=sha(CASE/'manifest.json'),generator_sha256=sha(Path(__file__)),generator_path=str(Path(__file__).relative_to(ROOT)),source_svg=str(base.relative_to(ROOT)),source_svg_sha256=sha(base),source_receipt=str(base_source.relative_to(ROOT)),source_receipt_sha256=sha(base_source),MOS_count=len(m['devices']),source_ports=m['sources'],delta_from_preserved_v6={'RDISABLE':ds['RDISABLE'],'VDISABLE_port':ds['VDISABLE'][1:3]},scope='Same v6 protection devices and passive values verified against actual v6r deck; only control-source 100 ohm delta depicted. No passing, PVT, PEX or silicon qualification claim.')
 (OUT/'micro-protection-v6r.source.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(svg)
if __name__=='__main__':main()

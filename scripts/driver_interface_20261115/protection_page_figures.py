#!/usr/bin/env python3
"""Make auditable, larger-type SVG panel derivatives without changing source art."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def tag(name):
    return '{'+NS+'}'+name


def addtext(root, y, value, size=20, color='#385568'):
    el = ET.SubElement(root, tag('text'), x='20', y=str(y), fill=color,
                       attrib={'font-size': str(size)})
    el.text = value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config', type=Path)
    args = parser.parse_args()
    cfg_path = args.config.resolve()
    cfg = json.loads(cfg_path.read_text())
    source_svg = ROOT/cfg['source_svg']
    source_receipt_path = ROOT/cfg['source_receipt']
    receipt = json.loads(source_receipt_path.read_text())
    case = ROOT/receipt['source_case']
    assert sha(case/'testbench.spice') == receipt['deck_sha256']
    assert sha(case/'manifest.json') == receipt['manifest_sha256']
    children = list(ET.fromstring(source_svg.read_text()))
    panel_starts = [i for i,e in enumerate(children)
                    if e.tag == tag('rect') and e.get('x') == '25']
    panel_starts.append(len(children))
    by_y = {}
    for first,last in zip(panel_starts,panel_starts[1:]):
        rect = children[first]
        y,h = float(rect.get('y')),float(rect.get('height'))
        els = []
        for el in children[first:last]:
            # Original final-page notes belong outside the last panel.
            if el.tag == tag('text') and float(el.get('y', '0')) > y+h:
                continue
            els.append(el)
        by_y[int(y)] = (h,els)
    for page in cfg['pages']:
        width = 1300
        selected = [by_y[y] for y in page['panels']]
        body_height = sum(h for h,_ in selected)+20*(len(selected)-1)
        footer = page['footer']+[
            '实际网表：'+page['case_label']+'；本图不升级仿真、PVT 或版图证据等级。',
            'Deck SHA-256：'+receipt['deck_sha256']]
        height = int(110+body_height+40+30*len(footer))
        root = ET.Element(tag('svg'), width=str(width),height=str(height),viewBox=f'0 0 {width} {height}')
        style = ET.SubElement(root,tag('style'))
        style.text='text{font-family:"Arial Unicode MS","PingFang SC",Arial,sans-serif}'
        ET.SubElement(root,tag('rect'),width=str(width),height=str(height),fill='#f7f9fb')
        addtext(root,38,page['title'],28)
        addtext(root,76,'标准器件连接局部展开；W/L 单位 µm；同名网络相连。数据结论以该候选的原生仿真为准。',20)
        current_y=110
        for y,(h,els) in zip(page['panels'],selected):
            group=ET.SubElement(root,tag('g'),transform=f'translate(-20,{current_y-y:g})')
            for old in els:
                el=copy.deepcopy(old)
                if el.tag == tag('text'):
                    value=''.join(el.itertext())
                    if any(value.startswith(p) for p in page.get('remove_text_prefixes',[])):
                        continue
                    if value in page.get('text_replacements',{}):
                        el.text=page['text_replacements'][value]
                    size=max(20,float(el.get('font-size','20')))
                    el.set('font-size',f'{size:g}')
                    if value in page.get('text_moves',{}):
                        for attr,val in page['text_moves'][value].items():el.set(attr,str(val))
                group.append(el)
            current_y+=h+20
        footer_y=110+body_height+40
        for line in footer:
            addtext(root,footer_y,line,20);footer_y+=30
        out=ROOT/page['output_svg'];out.write_text(ET.tostring(root,encoding='unicode')+'\n')
        import cairosvg
        cairosvg.svg2png(url=str(out),write_to=str(out.with_suffix('.png')),scale=1.3)
        meta={
            'status':'print_panel_derivative_not_qualification',
            'source_case':receipt['source_case'],
            'deck_sha256':receipt['deck_sha256'],
            'manifest_sha256':receipt['manifest_sha256'],
            'source_svg':str(source_svg.relative_to(ROOT)),
            'source_svg_sha256':sha(source_svg),
            'source_receipt':str(source_receipt_path.relative_to(ROOT)),
            'source_receipt_sha256':sha(source_receipt_path),
            'generator_path':str(Path(__file__).resolve().relative_to(ROOT)),
            'generator_sha256':sha(Path(__file__)),
            'config_path':str(cfg_path.relative_to(ROOT)),
            'config_sha256':sha(cfg_path),
            'source_panel_top_y':page['panels'],
            'minimum_text_px':20,
            'minimum_text_pt_at_170mm_width':20*170/width/25.4*72,
            'scope':'Vector panel derivative; typography enlarged, explanatory text may move to footer. No circuit connections changed; full historical art preserved.'}
        out.with_suffix('.source.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
        print(out)


if __name__=='__main__':main()

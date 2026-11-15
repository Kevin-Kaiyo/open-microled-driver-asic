#!/usr/bin/env python3
"""Render every final PDF page for human visual review; never mark review passed."""
from pathlib import Path
import argparse,hashlib,json,subprocess
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/driver-interface-20261115'
OUT=ROOT/'build/driver-interface-20261115/render'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pdftoppm',default='pdftoppm');args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    pdf=DOC/'technical-stage-report.pdf'
    subprocess.run([args.pdftoppm,'-r','100','-png',str(pdf),str(OUT/'page')],check=True)
    pages=sorted(OUT.glob('page-*.png'))
    assert pages
    sheets=[]
    for start in range(0,len(pages),6):
        batch=pages[start:start+6]
        sheet=Image.new('RGB',(860,1860),'#dfe8e7');draw=ImageDraw.Draw(sheet)
        for i,p in enumerate(batch):
            with Image.open(p) as im:
                im.thumbnail((410,580),Image.Resampling.LANCZOS)
                x=10+(i%2)*430;y=25+(i//2)*620
                sheet.paste(im,(x,y));draw.text((x,y-18),p.stem,fill='#213e49')
        dest=OUT/f'contact-{start//6+1:02d}.png';sheet.save(dest);sheets.append(str(dest.relative_to(ROOT)))
    receipt=dict(pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),pages=len(pages),
                 render_dpi=100,rendered_pages=[str(p.relative_to(ROOT)) for p in pages],
                 contact_sheets=sheets,scope='Rendered for manual inspection. Rendering alone is not a visual pass.')
    (OUT/'render-index.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'pages':len(pages),'contact_sheets':len(sheets)}))

if __name__=='__main__':main()

#!/usr/bin/env python3
"""Build comparison from a fixed report selection, not implicit best-case search."""
from pathlib import Path
import argparse,csv,hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/pwm-reference-startup-20261024/figures';OUT.mkdir(parents=True,exist_ok=True)
font_manager.fontManager.addfont(str(ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'))
plt.rcParams.update({'font.family':'Noto Sans CJK SC','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'path','axes.unicode_minus':False})
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--selection',required=True);a=ap.parse_args();sel=json.loads((ROOT/a.selection).read_text());inputs={};fig,axs=plt.subplots(3,1,figsize=(11,8.6),sharex=True,layout='constrained')
 for r in sel['traces']:
  p=ROOT/r['csv'];d=np.loadtxt(p,delimiter=',',skiprows=1);names=p.read_text().splitlines()[0].split(',')
  # ngspice vector names contain comma in differential voltages; the CSV header
  # is unquoted legacy text. Use explicitly frozen column positions from runner.
  cols=r['columns'];t=d[:,cols['time']]*1e6
  for ax,key,scale in zip(axs,['current','sense','refrail'],[1e6,1,1]):
   col=cols[key];value=(d[:,col[0]]-d[:,col[1]]) if isinstance(col,list) else d[:,col]
   ax.plot(t,value*scale,lw=1.25,label=r['label'],color=r['color'])
  inputs[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
 axs[0].set_ylabel('LED 支路电流 (µA)');axs[1].set_ylabel('SENSE (V)');axs[2].set_ylabel('参考源芯片电源电压 (V)');axs[2].set_xlabel('时间 (µs)')
 for ax in axs:ax.grid(alpha=.2);ax.set_xlim(*sel['xlim_us'])
 axs[0].legend(frameon=False,fontsize=9,loc='best');fig.suptitle(sel['title'],fontsize=14)
 for ext in ['svg','png']:fig.savefig(OUT/(sel['name']+'.'+ext),dpi=160)
 plt.close(fig);(OUT/(sel['name']+'-sources.json')).write_text(json.dumps({'selection':a.selection,'selection_sha256':hashlib.sha256((ROOT/a.selection).read_bytes()).hexdigest(),'inputs':inputs,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
 print(json.dumps({'plot':sel['name'],'inputs':len(inputs)}))
if __name__=='__main__':main()

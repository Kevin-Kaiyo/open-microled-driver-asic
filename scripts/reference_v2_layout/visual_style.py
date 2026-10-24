"""Portable Chinese labels and bounded-canvas checks for presentation figures."""
from pathlib import Path
import hashlib
from matplotlib import font_manager, pyplot as plt
from matplotlib.text import Text

ROOT=Path(__file__).resolve().parents[2]
FONT=ROOT/'build/blender-pwm-animation/fonts/NotoSansCJKsc-Regular.otf'

def configure():
    font_manager.fontManager.addfont(str(FONT))
    family=font_manager.FontProperties(fname=str(FONT)).get_name()
    plt.rcParams.update({'font.family':family,'font.size':10,'axes.unicode_minus':False,'svg.fonttype':'path'})
    return dict(path=str(FONT.relative_to(ROOT)),family=family,sha256=hashlib.sha256(FONT.read_bytes()).hexdigest(),svg_glyphs='outlined from the same font used for PNG')

def text_bounds(fig):
    fig.canvas.draw();renderer=fig.canvas.get_renderer();canvas=fig.bbox;checked=0;outside=[]
    # Matplotlib retains locator ticks outside the displayed interval but does
    # not draw those labels. Exclude them instead of reporting false clipping.
    excluded=set()
    for axes in fig.axes:
        for axis in (axes.xaxis,axes.yaxis):
            lo,hi=sorted(axis.get_view_interval())
            for tick in axis.get_major_ticks()+axis.get_minor_ticks():
                if not lo<=tick.get_loc()<=hi:excluded.update([id(tick.label1),id(tick.label2)])
    for text in fig.findobj(Text):
        if id(text) in excluded or not text.get_visible() or not text.get_text().strip():continue
        box=text.get_window_extent(renderer);checked+=1
        if box.x0<canvas.x0-.5 or box.y0<canvas.y0-.5 or box.x1>canvas.x1+.5 or box.y1>canvas.y1+.5:
            outside.append(dict(text=text.get_text(),bbox_pixels=list(box.extents)))
    assert not outside,outside
    return dict(checked_text_objects=checked,outside_canvas=outside,canvas_pixels=list(canvas.bounds))

def file_record(path):
    return dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())

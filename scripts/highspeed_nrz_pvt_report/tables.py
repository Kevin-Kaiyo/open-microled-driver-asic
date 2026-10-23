"""Evidence-derived tables; keep receive and voltage screens separate."""
from html import escape

KINDS=['nominal','slow_hot','fast_cold']
LABEL={'nominal':'TT / 27°C / 3.3 V','slow_hot':'SS / 125°C / 3.0 V','fast_cold':'FF / −40°C / 3.6 V'}
RATES=[.1,.25,.5,1,2,4,8]
ENERGY='rail_plus_DATA_positive_draw_fJ_per_gross_bit'

def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+escape(str(v))+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'

def find(rows,route,variant,kind,rate):
    found=[r for r in rows if r['route']==route and r['variant']==variant and r['kind']==kind and r.get('rate_Gbps')==rate]
    assert len(found)<=1, 'Ambiguous comparison row'
    return found[0] if found else None

def energy_comparison(rows):
    result=[]
    for route,rate in [('A',.5),('A',1),('B',.5)]:
        for kind in KINDS:
            b=find(rows,route,'BEFORE',kind,rate);a=find(rows,route,'AFTER',kind,rate)
            if b is None or a is None:continue
            result.append([f'{route} / {rate:g}',LABEL[kind],f'{b[ENERGY]/1000:.3f}',f'{a[ENERGY]/1000:.3f}',f'{(a[ENERGY]/b[ENERGY]-1)*100:+.1f}%',
                f"{b['errors']} → {a['errors']}",f"{b['threshold_margin_normalized']:.3f} → {a['threshold_margin_normalized']:.3f}",f"{b['timing_min_margin_ui']:.3f} → {a['timing_min_margin_ui']:.3f}",
                f"{(3.63-b['max_abs_terminal_V'])*1000:+.1f} → {(3.63-a['max_abs_terminal_V'])*1000:+.1f}"])
    return table(['路线 / Gb/s','条件','修改前 pJ/bit','修改后 pJ/bit','取能变化','错误 / 511','垂直余量','水平余量 UI','电压余量 mV'],result)

def rate_grid(rows):
    result=[]
    for route in 'AB':
        for variant in ['BEFORE','AFTER']:
            for kind in KINDS:
                cells=[]
                for rate in RATES:
                    r=find(rows,route,variant,kind,rate)
                    if r is None:cells.append('未完成');continue
                    rx=r['comparison_screen_passed'];v=not r['above_3p63V_screen']
                    label='双通过' if rx and v else '接收失败' if not rx and v else '电压超筛查' if rx else '两项失败'
                    cells.append('<span class="'+('pass' if rx and v else 'fail')+'">'+label+'</span>')
                result.append([route,'修改前' if variant=='BEFORE' else '修改后',LABEL[kind]]+cells)
    return table(['路线','版本','条件']+[f'{v:g} G' for v in RATES],result)

def dc_table(rows):
    result=[]
    for route in 'AB':
        for variant in ['BEFORE','AFTER']:
            for corner,temp,vdd in [('typical',27,3.3),('ss',125,3.0),('ff',-40,3.6)]:
                rr=[r for r in rows if r['route']==route and r['variant']==variant and r['kind']=='dc' and r['corner']==corner and r['temp_C']==temp and r['vdd_V']==vdd]
                if len(rr)!=2:continue
                vals={r['dc_bit']:r['LED_current_A']*1e6 for r in rr}
                result.append([route,'修改前' if variant=='BEFORE' else '修改后',f'{corner.upper()} / {temp}°C / {vdd:g} V',f'{vals[0]:.3f}',f'{vals[1]:.3f}',f'{100*(vals[1]/100-1):+.2f}%'])
    return table(['路线','版本','条件','I₀ µA','I₁ µA','I₁ 对 100 µA 误差'],result)

def device_table(c):
    rows=[]
    for d in c['devices']:rows.append([d['name'],d['model'],f"{d['w_um']:g} / {d['l_um']:g}",*d['nodes']])
    return table(['MOS','模型','W / L µm','D','G','S','B'],rows)

def all_rows(rows):
    rr=[]
    for r in rows:
        if r['kind'] not in KINDS or r['variant'] not in ['BEFORE','AFTER']:continue
        link='../../../'+r['analysis_json']
        rr.append([f"<a href='{link}'>{escape(r['name'])}</a>",r['errors'],f"{r['threshold_margin_normalized']:.6f}",f"{r['timing_min_margin_ui']:.6f}",f"{r['max_abs_terminal_V']:.6f}",f"{r[ENERGY]:.6f}"])
    return table(['逐 case 分析（原始附件）','错误','垂直余量','水平余量 UI','最大端差 V','正向取能 fJ/bit'],rr)

#!/usr/bin/env python3
"""Independent teaching budgets; no transistor, optical, eye or BER claims.

Run with Python 3 (standard library only). All numerical inputs are declared
below in SI units. SVG plots and the JSON ledger are generated together.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/research/highspeed-driver-routes-20261019"
FIG = OUT / "figures"

A = {
    "probability_one": 0.5,
    "probability_zero_to_one": 0.25,
    "gross_rate_per_lane_bps": 4e9,
    "net_to_gross_efficiency": 0.9,
    "led_supply_V": 3.2,
    "led_zero_current_A": 0.0,
    "led_one_current_A": 100e-6,
    "steering_tail_current_A": 100e-6,
    "effective_switched_capacitance_F": 80e-15,
    "effective_switched_supply_swing_V": 1.0,
    "per_lane_predriver_bias_clock_power_W": 0.2e-3,
    "shared_tx_logic_power_W": 1e-3,
    "lane_counts": [1, 2, 4, 8, 16, 32, 64],
}


def cap_energy(C: float, swing: float, p01: float = 0.25) -> float:
    """Supply energy / gross bit, rail-to-rail ideal capacitor, no recovery."""
    assert C >= 0 and swing >= 0 and 0 <= p01 <= 1
    return p01 * C * swing**2


def eo_bandwidth(f_carrier: float, f_rc: float) -> float:
    """Exact amplitude -3 dB frequency for two independent first-order poles.

    (1 + (f/f_carrier)^2) (1 + (f/f_rc)^2) = 2.
    Rationalized positive quadratic root avoids subtractive cancellation.
    """
    assert f_carrier > 0 and f_rc > 0
    lo, hi = sorted((f_carrier, f_rc))
    r2 = (lo / hi)**2
    return lo * math.sqrt(2 / (1 + r2 + math.sqrt((1 + r2)**2 + 4*r2)))


def calculate() -> dict:
    p1 = A["probability_one"]
    p01 = A["probability_zero_to_one"]
    Rg = A["gross_rate_per_lane_bps"]
    eta = A["net_to_gross_efficiency"]
    V = A["led_supply_V"]
    Iavg = (1-p1)*A["led_zero_current_A"] + p1*A["led_one_current_A"]
    ecap = cap_energy(A["effective_switched_capacitance_F"], A["effective_switched_supply_swing_V"], p01)
    pcap = Rg*ecap
    pled = V*Iavg
    pdummy = V*(A["steering_tail_current_A"]-Iavg)
    paux = A["per_lane_predriver_bias_clock_power_W"]
    routes = {}
    for name, dummy in [("direct_switching_budget", 0.0), ("current_steering_same_supply_budget", pdummy)]:
        parts = {"led_branch_supply_dc_W": pled, "dummy_branch_supply_dc_W": dummy,
                 "equivalent_capacitor_switching_W": pcap,
                 "predriver_bias_clock_other_W": paux}
        total = sum(parts.values())
        routes[name] = {"parts_W": parts, "total_lane_power_W": total,
                        "energy_per_gross_bit_J": total/Rg,
                        "energy_per_net_bit_J": total/(eta*Rg)}
    arrays = []
    for n in A["lane_counts"]:
        row = {"lanes": n, "gross_rate_bps": n*Rg, "net_rate_bps": n*Rg*eta}
        for name, d in routes.items():
            power = n*d["total_lane_power_W"] + A["shared_tx_logic_power_W"]
            row[name] = {"total_tx_power_W": power,
                         "energy_per_net_bit_J": power/row["net_rate_bps"]}
        arrays.append(row)
    bw = []
    for tau in [50e-12, 200e-12, 1e-9]:
        for C in [50e-15, 200e-15, 1e-12]:
            R = 100.0
            fc = 1/(2*math.pi*tau)
            fr = 1/(2*math.pi*R*C)
            f = eo_bandwidth(fc, fr)
            bw.append({"carrier_lifetime_s": tau, "effective_resistance_ohm": R,
                       "effective_capacitance_F": C, "carrier_pole_Hz": fc,
                       "RC_pole_Hz": fr, "combined_amplitude_minus_3dB_Hz": f})
    return {
        "schema": "microled-highspeed-teaching-budget-v1",
        "evidence_level": "Independent analytical assumptions; not SPICE, silicon, measured optical or BER evidence",
        "created_for": "2026-10-19 research diagrams",
        "assumptions_SI": A,
        "conditions": {
            "NRZ": "Independent equiprobable bits: p(1)=0.5, p(0->1)=0.25; total transition probability=0.5.",
            "efficiency": "eta=Rnet/Rgross=0.9; includes an assumed aggregate framing/coding loss. This is not a claim that FEC overhead is 10% of payload.",
            "cap_model": "An equivalent capacitance is switched between 0 and a dedicated supply DeltaV, fully settling each time, without energy recovery. Supply energy per 0->1 is C*DeltaV^2. Ecap=0.25*C*DeltaV^2. Nonzero bias, voltage-dependent LED C, finite settling and extra nodes require circuit integration.",
            "no_double_counting": "Equivalent switching power is an additional AC supply budget; static LED branch supply power excludes capacitive charging. The 0.2mW auxiliary budget excludes the explicit capacitor term.",
            "same_supply_steering": "The ideal tail current always flows from the same 3.2V rail, through LED or dummy branch. Total static power=Vrail*Itail, not only VLED*ILED. Tail-source compliance is assumed, not demonstrated.",
            "cross_route_comparison": "Both hypothetical routes use the same LED current levels (0/100uA), p(1), switching-C budget, and other per-lane budget solely to isolate continuous tail-current cost. This does not establish equal OMA, actual swing, BER, maximum rate or implementation quality.",
            "throughput": "4Gb/s/lane is a selected budget input; N lanes scale only if each complete optical link attains that rate and there are independent channels and adequate receiver/serializer capacity.",
            "power_boundary": "Illustrative TX-side LED supply + driver switching + per-lane predriver/bias/clock allowance + separately declared shared TX logic. Excludes RX/TIA/CDR, regulator loss, fiber/coupling loss, cooling and host-system power.",
            "bandwidth": "Two independent first-order poles, constant R and C, no inductive peaking, diffusion nonlinearity, relaxation, bias dependence or feedback. -3dB is not a maximum bit rate and proves no eye or BER.",
        },
        "route_budgets": routes,
        "parallel_scaling": arrays,
        "cap_sweep": [{"C_F": c*1e-15, "swing_V": v, "energy_J": cap_energy(c*1e-15,v)}
                      for v in [0.2,0.5,1.0,1.8] for c in [0,20,40,80,120,160,200]],
        "two_pole_bandwidth": bw,
        "inductive_scale": [{"L_H": 0.5e-9, "delta_I_A": di, "edge_time_s": 100e-12,
                              "L_di_dt_V": 0.5e-9*di/100e-12} for di in [100e-6,5e-3]],
        "current_definition_example": {
            "V_V": 3.2, "R_bps": 4e9, "specified_current_A": 100e-6,
            "if_current_is_time_average_supply_energy_J_per_gross_bit": 3.2*100e-6/4e9,
            "if_current_is_one_level_with_zero_off_p1_half_J_per_gross_bit": 3.2*100e-6*0.5/4e9,
            "interpretation": "80fJ/bit vs 40fJ/bit are conditional arithmetic only; the meaning of 100uA must be known. Neither includes the whole driver automatically.",
        },
    }


def checks(d: dict) -> list[dict]:
    results = []
    def check(name, passed):
        results.append({"name": name, "pass": bool(passed)})
        assert passed, name
    def near(a,b): return math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-24)
    check("NRZ p01=p0*p1=0.25", near(A["probability_zero_to_one"], (1-A["probability_one"])*A["probability_one"]))
    check("80fF*1V^2*0.25=20fJ", near(cap_energy(80e-15,1),20e-15))
    check("doubling swing quadruples energy", near(cap_energy(80e-15,2),4*cap_energy(80e-15,1)))
    check("zero C has zero switching energy", cap_energy(0,1)==0)
    check("zero swing has zero switching energy", cap_energy(80e-15,0)==0)
    dr=d["route_budgets"]["direct_switching_budget"]
    cs=d["route_budgets"]["current_steering_same_supply_budget"]
    check("direct average LED supply = 0.16mW",near(dr["parts_W"]["led_branch_supply_dc_W"],.16e-3))
    check("steering LED plus dummy = Vrail Itail",near(cs["parts_W"]["led_branch_supply_dc_W"]+cs["parts_W"]["dummy_branch_supply_dc_W"],3.2*100e-6))
    check("direct lane total = 0.44mW",near(dr["total_lane_power_W"],.44e-3))
    check("steering lane total = 0.60mW",near(cs["total_lane_power_W"],.6e-3))
    for name,v in d["route_budgets"].items():
        check(name+" power sum",near(v["total_lane_power_W"],sum(v["parts_W"].values())))
        check(name+" E gross=P/R",near(v["energy_per_gross_bit_J"]*A["gross_rate_per_lane_bps"],v["total_lane_power_W"]))
        check(name+" E net=E gross/eta",near(v["energy_per_net_bit_J"]*A["net_to_gross_efficiency"],v["energy_per_gross_bit_J"]))
    for row in d["parallel_scaling"]:
        check(f"N={row['lanes']} net/gross efficiency",near(row["net_rate_bps"]/row["gross_rate_bps"],.9))
        for name in d["route_budgets"]:
            v=row[name]
            check(f"N={row['lanes']} {name} shared power counted once",near(v["total_tx_power_W"],row["lanes"]*d["route_budgets"][name]["total_lane_power_W"]+.001))
            check(f"N={row['lanes']} {name} E net=P/R net",near(v["energy_per_net_bit_J"]*row["net_rate_bps"],v["total_tx_power_W"]))
    for j,row in enumerate(d["two_pole_bandwidth"]):
        f=row["combined_amplitude_minus_3dB_Hz"]
        a=row["carrier_pole_Hz"]; b=row["RC_pole_Hz"]
        check(f"bandwidth case {j}: power response=0.5",near(1/((1+(f/a)**2)*(1+(f/b)**2)),.5))
        check(f"bandwidth case {j}: below both poles",f < min(a,b))
    check("equal poles analytic identity",near(eo_bandwidth(1e9,1e9),1e9*math.sqrt(math.sqrt(2)-1)))
    check("wide pole separation tends to lower pole",math.isclose(eo_bandwidth(1e6,1e12),1e6,rel_tol=1e-10))
    ex=d["current_definition_example"]
    check("100uA average gives 80fJ",near(ex["if_current_is_time_average_supply_energy_J_per_gross_bit"],80e-15))
    check("100uA on gives 40fJ with p1=.5",near(ex["if_current_is_one_level_with_zero_off_p1_half_J_per_gross_bit"],40e-15))
    check("0.5nH 5mA/100ps gives 25mV",near(d["inductive_scale"][1]["L_di_dt_V"],.025))
    return results


COL={"ink":"#183b4e","sub":"#5c7080","line":"#d5dfe4","teal":"#188b7d","orange":"#d77a1d","blue":"#386a9c","purple":"#8a5ab3","grey":"#8a9da8"}

class SVG:
    def __init__(self,w,h,title,desc):
        self.s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img"><title>{escape(title)}</title><desc>{escape(desc)}</desc>',
                '<style>text{font-family:"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif} .sub{fill:#5c7080} .small{font-size:15px}</style>',f'<rect width="{w}" height="{h}" fill="#fafcfb"/>']
    def text(self,x,y,t,size=18,color=None,weight=None,anchor=None):
        attrs=f' fill="{color or COL["ink"]}"'
        if weight:attrs+=f' font-weight="{weight}"'
        if anchor:attrs+=f' text-anchor="{anchor}"'
        self.s.append(f'<text x="{x}" y="{y}" font-size="{size}"{attrs}>{escape(str(t))}</text>')
    def line(self,x1,y1,x2,y2,color=None,width=1,dash=None):
        self.s.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color or COL["line"]}" stroke-width="{width}"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')
    def rect(self,x,y,w,h,fill,rx=0):
        self.s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" rx="{rx}"/>')
    def path(self,pts,color,width=3):
        self.s.append(f'<polyline points="'+" ".join(f'{x:.2f},{y:.2f}' for x,y in pts)+f'" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"/>')
    def circle(self,x,y,r,color): self.s.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>')
    def save(self,p):p.write_text("\n".join(self.s+["</svg>"]),encoding="utf-8")


def energy_svg(d):
    s=SVG(1360,950,"高速驱动能耗：开关电容与连续偏置的不同代价","所有参数均为教学假设。左图为简单电容供电能量计算；右图为相同LED电流条件下的TX单通道预算，不能证明速率、光输出或BER。")
    s.text(48,43,"独立教学计算 · 不是器件实测 / SPICE / BER 结果",15,COL["sub"])
    s.text(48,85,"先分清电容切换能量，再计算连续偏置功耗",29,weight=600)
    s.text(48,119,"随机独立 NRZ：p(1) = 0.5，p(0→1) = 0.25；Ecap = 0.25 Ceff ΔV²",20)
    s.line(48,142,1312,142)
    s.text(70,183,"A  电压摆幅的平方关系",22,weight=600)
    s.text(70,211,"Ceff 为额外计入的等效开关电容；ΔV 为其驱动电源摆幅。",16,COL["sub"])
    x0,y0,w,h=100,585,545,315
    for val in [0,40,80,120,160]:
        y=y0-h*val/180;s.line(x0,y,x0+w,y);s.text(x0-14,y+5,str(val),15,anchor="end")
    for val in [0,40,80,120,160,200]:
        x=x0+w*val/200;s.line(x,y0,x,y0+7);s.text(x,y0+29,str(val),15,anchor="middle")
    s.line(x0,y0,x0+w,y0,COL["ink"]);s.line(x0,y0,x0,y0-h,COL["ink"])
    s.text(100,247,"Ecap / gross bit（fJ/bit）",17)
    s.text(350,642,"Ceff（fF）",17,anchor="middle")
    for v,color in [(1.8,COL["purple"]),(1.,COL["blue"]),(.5,COL["teal"]),(.2,COL["orange"])]:
        s.path([(x0+w*c/200,y0-h*(cap_energy(c*1e-15,v)*1e15)/180) for c in range(201)],color)
    for j,(v,color) in enumerate([(1.8,COL["purple"]),(1.,COL["blue"]),(.5,COL["teal"]),(.2,COL["orange"])]):
        xx=87+(j%2)*265;yy=683+(j//2)*30;s.line(xx,yy-5,xx+27,yy-5,color,4);s.text(xx+37,yy,f"ΔV = {v:.1f} V",17)
    s.text(70,764,"例：80 fF × 1 V² × 0.25 = 20 fJ/毛比特",18,weight=600)
    s.text(70,792,"这只计算电容供电项，不等于整个 LED 发射器能耗。",16,COL["sub"])
    s.line(700,170,700,805)
    s.text(750,183,"B  同一电流条件下的预算分解",22,weight=600)
    s.text(750,211,"3.2 V，ILED = 0 / 100 μA，输入预算 4 Gb/s / 通道",16,COL["sub"])
    bx,by,bw,bh=810,585,390,315
    for val in [0,40,80,120,160]:
        y=by-bh*val/160;s.line(bx-20,y,bx+bw+25,y);s.text(bx-31,y+5,str(val),15,anchor="end")
    s.text(780,247,"供电能量 / gross bit（fJ/bit）",17)
    components=[("led_branch_supply_dc_W",COL["teal"],"LED 支路供电"),("dummy_branch_supply_dc_W",COL["orange"],"Dummy 支路"),("equivalent_capacitor_switching_W",COL["blue"],"等效电容切换"),("predriver_bias_clock_other_W",COL["grey"],"前驱动 / 偏置 / 时钟")]
    for j,(key,label) in enumerate([("direct_switching_budget","直接开关预算"),("current_steering_same_supply_budget","电流转向预算")]):
        row=d["route_budgets"][key];x=bx+35+j*220;y=by
        for k,color,_ in components:
            e=row["parts_W"][k]/A["gross_rate_per_lane_bps"]*1e15
            if not e:continue
            hh=bh*e/160;y-=hh;s.rect(x,y,125,hh,color)
            s.text(x+62.5,y+hh/2+6,f"{e:.0f}",19,"#fff",600,"middle")
        s.text(x+62.5,y-15,f"{row['energy_per_gross_bit_J']*1e15:.0f} fJ/bit",20,weight=600,anchor="middle")
        s.text(x+62.5,by+31,label,18,anchor="middle")
    for j,(_,color,label) in enumerate(components):
        xx=750+(j%2)*260;yy=683+(j//2)*30;s.rect(xx,yy-13,16,16,color,3);s.text(xx+26,yy,label,16)
    s.text(750,764,"LED 平均电流相同；连续尾电流增加 Dummy 供电项。",17,weight=600)
    s.text(750,792,"为隔离这一项，两路均假设 Ceff = 80 fF、ΔV = 1 V。",16,COL["sub"])
    s.rect(48,827,1264,87,"#eaf1f2",9)
    s.text(68,854,"边界：右图不含共享逻辑与接收端；两路都另设 0.20 mW / 通道的外围功耗占位。",17)
    s.text(68,879,"实际电流转向可减小部分节点摆幅，但也增加互补控制等开销；须由具体电路求和，不能据此给技术路线排名。",16)
    s.text(68,903,"简单电容模型要求从 0 到 ΔV 充分充放电、无能量回收；有直流偏置的 LED 结电容应积分实际供电波形。",15,COL["sub"])
    s.save(FIG/"energy-budget.svg")


def parallel_svg(d):
    s=SVG(1360,950,"并行通道：吞吐与功耗一起增长","教学预算：每通道毛速率固定4Gb/s，净毛效率0.9，增加通道数不提高单个LED的速度。两幅图分别表示总净吞吐和总TX供电功耗。")
    s.text(48,43,"独立教学计算 · 每通道速率是输入条件，不是已验证性能",15,COL["sub"])
    s.text(48,85,"并行能提高总吞吐，共享电路影响每比特能耗",29,weight=600)
    s.text(48,119,"Rg = 4 Gb/s / 通道；η = Rnet / Rgross = 0.90；Pshared = 1.00 mW（假设）",20)
    s.line(48,142,1312,142)
    s.text(70,182,"A  净吞吐：Rnet,total = N × η × Rg",22,weight=600)
    s.text(743,182,"B  总发射功耗：Ptotal = N × Plane + Pshared",22,weight=600)
    xs=[105+j*83 for j in range(7)]; xs2=[780+j*80 for j in range(7)]
    y0=535;h=270
    for val in [0,60,120,180,240]:
        y=y0-h*val/240;s.line(xs[0],y,xs[-1],y);s.text(xs[0]-15,y+5,str(val),15,anchor="end")
    for val in [0,10,20,30,40]:
        y=y0-h*val/40;s.line(xs2[0],y,xs2[-1],y);s.text(xs2[0]-15,y+5,str(val),15,anchor="end")
    s.text(105,236,"总净吞吐（Gb/s）",17);s.text(780,236,"总 TX 供电功耗（mW）",17)
    for axis in [xs,xs2]:
        s.line(axis[0],y0,axis[-1],y0,COL["ink"])
        for x,n in zip(axis,A["lane_counts"]):s.line(x,y0,x,y0+7);s.text(x,y0+29,n,15,anchor="middle")
        s.text((axis[0]+axis[-1])/2,592,"独立通道数 N（倍增刻度）",17,anchor="middle")
    pts=[(x,y0-h*row["net_rate_bps"]/1e9/240) for x,row in zip(xs,d["parallel_scaling"])]
    s.path(pts,COL["teal"])
    for x,y in pts:s.circle(x,y,4,COL["teal"])
    for key,col in [("direct_switching_budget",COL["teal"]),("current_steering_same_supply_budget",COL["orange"])]:
        pts=[(x,y0-h*row[key]["total_tx_power_W"]*1e3/40) for x,row in zip(xs2,d["parallel_scaling"])]
        s.path(pts,col)
        for x,y in pts:s.circle(x,y,4,col)
    s.line(786,627,817,627,COL["teal"],4);s.text(828,632,"直接开关：0.44 mW / 通道",17)
    s.line(786,658,817,658,COL["orange"],4);s.text(828,663,"电流转向：0.60 mW / 通道",17)
    s.text(70,630,"固定 4 Gb/s 并不证明单个 LED 可达该速率。",18,weight=600)
    s.text(70,658,"通道需要独立可用的光链路、并行接收器与数据接口。",17,COL["sub"])
    s.rect(48,695,1264,155,"#edf3f3",8)
    headings=[(70,"N"),(155,"净吞吐 Gb/s"),(390,"直接开关 mW"),(650,"电流转向 mW"),(940,"直接开关 fJ / 净比特")]
    for x,label in headings:s.text(x,725,label,17,weight=600)
    for j,row in enumerate(r for r in d["parallel_scaling"] if r["lanes"] in [1,4,16,64]):
        yy=752+j*27
        vals=[str(row["lanes"]),f"{row['net_rate_bps']/1e9:.1f}",f"{row['direct_switching_budget']['total_tx_power_W']*1e3:.2f}",f"{row['current_steering_same_supply_budget']['total_tx_power_W']*1e3:.2f}",f"{row['direct_switching_budget']['energy_per_net_bit_J']*1e15:.1f}"]
        for (x,_),v in zip(headings,vals):s.text(x,yy,v,17)
    s.text(48,883,"共享功耗被更多比特分摊，Etotal,net = Plane / (η Rg) + Pshared / (N η Rg)；单通道本身并未变得更省电。",18)
    s.text(48,914,"未计入接收端、稳压损耗、散热和光耦合要求。实际阵列还需验证热耦合、串扰、同时切换噪声与每通道 BER。",16,COL["sub"])
    s.save(FIG/"parallel-throughput-power.svg")


def notes(d):
    bw="\n".join(f"| {r['carrier_lifetime_s']*1e12:.0f} | {r['effective_capacitance_F']*1e15:.0f} | {r['RC_pole_Hz']/1e9:.3f} | {r['carrier_pole_Hz']/1e9:.3f} | {r['combined_amplitude_minus_3dB_Hz']/1e9:.3f} |" for r in d['two_pole_bandwidth'])
    return f"""# 高速 MicroLED 驱动：独立教学计算说明

本文件由 `scripts/highspeed_routes/tradeoffs.py` 生成。数字都是显式假设及解析计算，**不引用论文性能、不拟合现有 PWM 模型、不代表高速电路已实现**。本文件和 `calculations.json` 是 SVG 的数值来源。

## 1. 先确定能耗分母

毛速率 Rg 包括在线路上传输的编码/帧比特；净速率 Rnet 是有效载荷速率。本例直接定义 η = Rnet/Rg = 0.9。E_gross = P/Rg，E_net = P/(η Rg)。不要把 η = 0.9 写成“相对有效载荷增加 10% 开销”；若全部损失都归于开销，其相对有效载荷比为 1/0.9 − 1 ≈ 11.11%。实际 FEC、帧格式和重传需另建预算。

## 2. 电容切换与平均电流分别计算

随机独立 NRZ 中，p(1)=p(0)=0.5，而 p(0→1)=0.25。对于由 0 / ΔV 两级专用电源完全充放电的理想等效电容，单次充电从电源获得 CΔV²；整次充放电无能量回收，因此每毛比特供电能量为 **0.25 CΔV²**，不是把总边沿概率 0.5 再乘 CΔV²。该模型不能直接替代带直流偏置、非线性结电容与多个电源的 LED 电路，应使用 ∫ΣVrail·Irail dt 计算实际供电能量。

本例 Ceff=80 fF、ΔV=1 V，Ecap=20 fJ/毛比特；Rg=4 Gb/s 时 Pcap=0.08 mW。此项是额外 AC 预算，不重复计入静态 LED 支路和外围功耗占位。

同一 LED 电流状态 0/100 μA、p(1)=0.5，3.2 V 电源的平均 LED 支路供电为 0.16 mW。这里是 **电源端功率**，不是仅算 LED 结上的功率；电源与 LED 压降之差所对应的支路耗散已经包含在此项中。

理想电流转向的 100 μA 尾电流持续流动：同电源基线下 P_DC=Vrail·Itail=0.32 mW，其中平均 LED 支路 0.16 mW、Dummy 支路 0.16 mW。假设两路都保留同样的 0.08 mW 电容项和 0.20 mW / 通道的前驱动/偏置/时钟占位，则分别为 **0.44 mW（110 fJ/毛比特）和 0.60 mW（150 fJ/毛比特）**。这是隔离连续尾电流成本的预算，不是公平工艺或实物性能排行榜；真实电流转向可能降低摆幅和切换电容，也增加互补控制等功耗，必须重新逐电源求和。

这两个预算仅保持相同的 LED 电流高低值；并未证明相同的光调制幅度 OMA、相同速率、相同 BER 或尾电流源具备足够电压余量。所有 0.20 mW 等占位值应由后续电路实现替换。

## 3. 100 μA、3.2 V、4 Gb/s 到底是多少 fJ/bit

- 若 100 μA 是时间平均电源电流，则 3.2 V × 100 μA / 4 Gb/s = **80 fJ/毛比特**。
- 若 100 μA 仅是“1”的导通电流、关断为 0，随机独立比特的“1”概率为 0.5，则平均电流 50 μA，对应 **40 fJ/毛比特**。
- 上述均为条件乘除，不是某篇论文的完整能耗结论；未明确 current 是 average、on-level、bias 还是 peak 之前，不能互相替换。更不能自动代表含前驱动、时钟、编码、接收器的系统能耗。

## 4. 两极点电光带宽的尺度计算

用独立一阶载流子与 RC 极点作简化模型：f_carrier = 1/(2πτ)，f_RC = 1/(2πRC)，且 |H(f)|² = 1 / [(1+(f/f_carrier)²)(1+(f/f_RC)²)]。令 |H|²=1/2，令 a=f_carrier²、b=f_RC²，则 f_−3dB² = 2ab/[a+b+√((a+b)²+4ab)]。脚本使用等价归一化形式减少消减误差。

下表统一假设 R=100 Ω。τ、C 都是假设，未按实测 LED 标定。

| 载流子寿命 τ / ps | C / fF | fRC / GHz | fcarrier / GHz | 综合 −3 dB / GHz |
| ---: | ---: | ---: | ---: | ---: |
{bw}

综合 −3 dB 小于每个独立极点；当两极点相同时，综合 −3 dB 为单极点的 √(√2−1)≈0.6436 倍。该解析模型没有电感、峰化、反馈、偏置依赖和大信号非线性。

**−3 dB 带宽不能直接写成最大 Gb/s。** 最大可用速率需要同时明确调制格式、码型、均衡、发射摆幅、接收噪声/带宽、眼图与 BER 门限。本文没有生成伪眼图或 BER 验证结果。

## 5. 封装/连线电感的边沿尺度

ΔV≈L·ΔI/Δt 仅是局部尺度估计。假设 L=0.5 nH、Δt=100 ps，则 ΔI=100 μA 时约 **0.5 mV**，ΔI=5 mA 时约 **25 mV**。这不包含完整回路、互感、传输线、反射或寄生谐振；高速设计应提取包括回流路径在内的互连模型。

## 6. 并行不自动提高单个 LED 的速度

每通道 Rg=4 Gb/s、η=0.9、共享发射逻辑占位 1 mW 时，N 条独立通道的 Rnet=NηRg，Ptotal=NPlane+Pshared。共享功耗只计算一次。图中 64 通道的 230.4 Gb/s 是条件总净吞吐，要求每条光链路都能达到设定速率，并具备对应的并行接收器与接口能力。

这组功耗边界不含 RX/TIA/CDR、稳压转换损耗、冷却、主机以及光耦合要求。热、串扰、同时切换噪声与实际光路可能限制并行扩展。

## 7. 自检与复现

在仓库根目录运行 `python3 scripts/highspeed_routes/tradeoffs.py`。脚本无第三方依赖，检查 NRZ 概率、能量单位换算、逐项功耗求和、共享功耗只计一次、净/毛比特换算、两极点根的 −3 dB 条件与边界、80/40 fJ 两种口径，以及 Ldi/dt 换算。共 **{len(d['self_checks'])} 项自检**；这些检查保证所列公式与程序一致，不证明假设器件可实现。
"""


def main():
    FIG.mkdir(parents=True,exist_ok=True)
    d=calculate();d["self_checks"]=checks(d)
    d["generator_sha256"]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    energy_svg(d);parallel_svg(d)
    (OUT/"numerical-notes.md").write_text(notes(d),encoding="utf-8")
    d["artifact_sha256"]={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [FIG/"energy-budget.svg",FIG/"parallel-throughput-power.svg",OUT/"numerical-notes.md"]}
    (OUT/"calculations.json").write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"checks":len(d["self_checks"]),"pass":all(c["pass"] for c in d["self_checks"]),"output":str(OUT)},ensure_ascii=False))


if __name__=="__main__":main()

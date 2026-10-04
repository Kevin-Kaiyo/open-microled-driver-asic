"""Independent v0.4 physical/netlist and raw-waveform review.

Does not import extraction, export, simulation, or their validation methods.
No long SPICE job is repeated. Actual erroneous netlist copies are rejected by
the same strict checker used for the released model; raw copies stay in build/.
"""
from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re
import shlex

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "evidence/research/v04-review.json"
RAW = ROOT / "build/research/v04-review"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return str(path.relative_to(ROOT))


def number(token):
    m = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(.*)", token)
    if not m:
        raise ValueError(token)
    units = {"": "1", "f": "1e-15", "p": "1e-12", "n": "1e-9", "u": "1e-6", "m": "1e-3", "k": "1e3", "meg": "1e6"}
    return Decimal(m[1]) * Decimal(units[m[2].lower()])


def spice(text):
    lines = []
    for s in text.splitlines():
        s = s.strip()
        if not s or s.startswith("*"):
            continue
        if s.startswith("+"):
            lines[-1] += " " + s[1:]
        else:
            lines.append(s)
    definitions = [s.split() for s in lines if s.lower().startswith(".subckt ")]
    devices = [s.split() for s in lines if s[0].upper() in "XRC"]
    return definitions, devices


class Components:
    def __init__(self):
        self.parent = {}

    def root(self, s):
        self.parent.setdefault(s, s)
        n = s
        while n != self.parent[n]:
            n = self.parent[n]
        while s != n:
            nxt = self.parent[s]
            self.parent[s] = n
            s = nxt
        return n

    def merge(self, a, b):
        a, b = self.root(a), self.root(b)
        if a != b:
            self.parent[b] = a


def parameters(tokens):
    return {k.lower(): number(v) for k, v in (s.split("=", 1) for s in tokens)}


def neighboring_identity(flat_ext,neighbors):
    """Map all actual flat MOS gates through hierarchical geometry and net ties."""
    directory=ROOT/"build/joint-pex/full-nominal-r1"
    ties=Components();physical=defaultdict(list);masters={}
    def descend(cell,path,matrix):
        masters[path.rstrip("/")]=cell
        for line in (directory/(cell+".ext")).read_text().splitlines():
            if not line.startswith(("use ","merge ","equiv ","device msubckt ")):continue
            q=shlex.split(line)
            if q[0]=="use":
                a,b,c,d,e,f=map(int,q[3:9]);local=np.array([[a,b,c],[d,e,f],[0,0,1]])
                descend(q[1],path+q[2]+"/",matrix@local)
            elif q[0] in ("merge","equiv"):ties.merge(path+q[1],path+q[2])
            else:
                dims={k:int(v) for k,v in (s.split("=") for s in q[7:9])}
                x,y=map(int,q[3:5]);vertices=np.array([[x,y,1],[x+dims["l"],y,1],[x,y+dims["w"],1],[x+dims["l"],y+dims["w"],1]])
                result=vertices@matrix.T
                lo=result[:,:2].min(axis=0);hi=result[:,:2].max(axis=0)
                key=(q[2],int(lo[0]),int(lo[1]),int(hi[0]-lo[0]),int(hi[1]-lo[1]))
                physical[key].append((path,q))
    descend("pixel_integrated","",np.eye(3,dtype=int))
    mapping=defaultdict(set);count=0
    for line in flat_ext.read_text().splitlines():
        if not line.startswith("device msubckt "):continue
        q=shlex.split(line);dims={k:int(v) for k,v in (s.split("=") for s in q[7:9])}
        key=(q[2],int(q[3]),int(q[4]),dims["l"],dims["w"])
        matches=physical[key];assert len(matches)==1,(key,"hierarchy/flat physical MOS not unique")
        path,original=matches[0];count+=1
        mapping[q[10]].add(ties.root(path+original[10]));mapping[q[9]].add(ties.root(path+original[9]))
        for node,ap in [(q[13],q[15]),(q[16],q[18])]:
            physical_candidates={ties.root(path+n) for n,v in [(original[13],original[15]),(original[16],original[18])] if v==ap}
            if len(physical_candidates)==1:mapping[node]|=physical_candidates
    assert count==5644
    checks=[]
    for q in neighbors:
        declared=ties.root(q["hierarchical_net"])
        candidates=mapping[q["physical_net"]]
        assert candidates=={declared},(q["port"],candidates,declared,"neighbor identity differs")
        aliases=q["hierarchical_aliases"]
        assert aliases and all(ties.root(s)==declared for s in aliases)
        paths={s.rsplit("/",1)[0] for s in aliases if "/" in s}
        kinds=sorted({masters[path] for path in paths if path in masters})
        checks.append(dict(port=q["port"],physical_net=q["physical_net"],hierarchical_net=q["hierarchical_net"],masters=kinds))
    return dict(matched_physical_MOS=count,explicit_neighbors=len(checks),neighbors=checks,
                method="Independent homogeneous matrix transforms of gate LxW rectangles, model+four geometric dimensions; hierarchical merge/equiv ties; D/S diffusion A/P used only when one distinct terminal is identified; declared aliases checked against actual ties")


def output_placement():
    """Derive the cell transform from actual DEF placement and official LEF size."""
    import klayout.db as k
    gds = ROOT / "evidence/integration/pixel_integrated.gds"
    defs = ROOT / "build/physical-flow/pwm-v0.2-sized/44-openroad-detailedrouting/pixel_pwm.def"
    lef = ROOT / "build/layout/pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lef/gf180mcu_fd_sc_mcu7t5v0.lef"
    dt = defs.read_text()
    scale = int(re.search(r"UNITS DISTANCE MICRONS (\d+)", dt)[1])
    m = re.search(r"- output12 (\S+).*?PLACED \( (\d+) (\d+) \) (\w+) ;", dt)
    cell, x, y, orient = m.groups()
    assert orient == "S"
    lt = lef.read_text().split("MACRO " + cell + "\n", 1)[1].split("END " + cell, 1)[0]
    width, height = map(float, re.search(r"SIZE ([.\d]+) BY ([.\d]+)", lt).groups())
    routes = json.loads((ROOT / "evidence/integration/routing.json").read_text())
    # Frozen common top digital macro translation is independently checked in GDS.
    expected = [150 + int(x) / scale + width, 25 + int(y) / scale + height]
    layout = k.Layout(); layout.read(str(gds))
    matches = []
    def walk(c, transform):
        for instance in c.each_inst():
            tr = transform * instance.trans
            if instance.cell.name == cell and tr.rot == 2 and not tr.is_mirror():
                origin = [tr.disp.x * layout.dbu, tr.disp.y * layout.dbu]
                if max(abs(a-b) for a, b in zip(expected, origin)) < 1e-8:
                    matches.append((instance.cell, tr))
            walk(instance.cell, tr)
    walk(layout.top_cell(), k.Trans())
    assert len(matches) == 1
    leaf, transform = matches[0]
    return dict(instance="output12", master=cell, DEF_placement_um=[int(x)/scale, int(y)/scale],
                orientation=orient, official_LEF_size_um=[width, height],
                common_GDS_transform=str(transform), origin_um=expected,
                cell_site_um=[expected[0]-width, expected[1]-height, *expected],
                source_hashes={rel(p):sha(p) for p in [gds,defs,lef]})


def physical_expected(summary_path):
    summary = json.loads(summary_path.read_text())
    run = ROOT / summary["source_run"]
    raw_path = run / "pixel_flat_rc.spice"
    ext_path = run / "pixel_flat.ext"
    extraction = json.loads((run / "extraction.json").read_text())
    assert extraction["passed"] and extraction["exit_code"] == 0
    assert extraction["drc_count"] == ["0"]
    assert sha(raw_path) == extraction["outputs_sha256"][raw_path.name]
    assert sha(run/"input.gds") == sha(ROOT/"evidence/integration/pixel_integrated.gds")
    for p,h in extraction["inputs_sha256"].items():assert sha(ROOT/p)==h,(p,"physical extraction input drift")
    tool=ROOT/"build/layout/tools/install/bin/magic"
    assert sha(tool)==extraction["tool_binary_sha256"]
    lock=ROOT/"scripts/physical/pdk-lock.json";pdk=ROOT/"build/layout/pdk/gf180mcuD"
    for p,h in json.loads(lock.read_text())["files"].items():assert sha(pdk/p)==h,(p,"pinned PDK identity")
    index_path=ROOT/"evidence/joint-pex/summary.json";index=json.loads(index_path.read_text())
    released=index["styles"][summary["rc_style"]]
    assert released["summary_sha256"]==sha(summary_path)
    assert released["model_sha256"]==sha(summary_path.parent/"output_pixel_pex.spice")
    for p,h in summary["inputs_sha256"].items():
        assert sha(ROOT/p) == h, (p,"input drift")
    _, items = spice(raw_path.read_text())
    ds = Components()
    for t in items:
        if t[0].upper().startswith("R"):
            ds.merge(t[1], t[2])
    # Map .ext identities through the actual extresist killnode/rnode records.
    # This aliases geometric net identities for review, without adding a new
    # physical circuit edge or relying on the exporter's regular expression.
    res_ext_path=run/"pixel_flat.res.ext"
    res_lines=[shlex.split(s) for s in res_ext_path.read_text().splitlines() if s.strip()]
    killed={t[1] for t in res_lines if t[0]=="killnode"}
    rnodes={t[1] for t in res_lines if t[0]=="rnode"}
    for original in killed:
        base=original.removesuffix("#")
        members={n for n in rnodes if n.startswith(base+".t") or n.startswith(base+".n")}
        if members:
            roots={ds.root(n) for n in members}
            assert len(roots)==1,(original,"resistively disconnected extresist segments")
            ds.merge(original,next(iter(members)))
    r = ds.root
    power = {r("VDD"):"VDD", r("VSS"):"VSS"}
    assert len(power)==2
    placement = output_placement()
    x0,y0,x1,y1=placement["cell_site_um"]
    ext_devices=[]
    for s in ext_path.read_text().splitlines():
        if not s.startswith("device msubckt "):
            continue
        t=shlex.split(s)
        x,y=int(t[3])*.005,int(t[4])*.005
        group="analog" if t[2] in ("nfet_06v0","pfet_06v0") else "output12" if x0<=x<=x1 and y0<=y<=y1 else None
        if group:
            ext_devices.append((t,group,x,y))
    assert Counter(q[1] for q in ext_devices)=={"analog":6,"output12":6}
    def raw_key(t):
        q=parameters(t[6:])
        return (t[5],r(t[2]),r(t[4]),q["w"],q["l"],tuple(sorted([(r(t[1]),q["ad"],q["pd"]),(r(t[3]),q["as"],q["ps"])])))
    by_key=defaultdict(list)
    for t in items:
        if t[0].upper().startswith("X"):
            by_key[raw_key(t)].append(t)
    chosen=[]; matches=[]
    for t,group,x,y in ext_devices:
        dimensions={n:Decimal(v)*Decimal("5e-9") for n,v in (s.split("=") for s in t[7:9])}
        ends=[]
        for node,ap in [(t[13],t[15]),(t[16],t[18])]:
            area,perimeter=map(Decimal,ap.split(","))
            ends.append((r(node),area*Decimal("2.5e-17"),perimeter*Decimal("5e-9")))
        key=(t[2],r(t[10]),r(t[9]),dimensions["w"],dimensions["l"],tuple(sorted(ends)))
        assert len(by_key[key])==1, (group,x,y,"ambiguous actual device")
        actual=by_key[key][0];chosen.append(actual)
        matches.append(dict(group=group,gate_um=[x,y],raw_device=actual[0],model=actual[5],
                            properties_SI={n:str(v) for n,v in parameters(actual[6:]).items()},
                            ext_terminals=[t[9],t[10],t[13],t[16]],raw_terminals=actual[1:5]))
    dynamic={r(s) for t in chosen for s in t[1:5]}-set(power)
    neighbor={q["physical_net"]:q["port"] for q in summary["neighbors"]}
    aliases={"DRIVER_I":"I","DRIVER_Z":"PWM_DRIVE","ANALOG_PWM":"PWM","pwm_monitor":"PWM_MON","bias":"BIAS","led_k":"LED_K","gate":"GATE","pwm_b":"PWM_B"}
    def project(s):
        root=r(s)
        if root in power:return power[root]
        if root not in dynamic:
            # Match by actual component identity, independent of exporter root choice.
            ports={p for n,p in neighbor.items() if r(n)==root}
            assert len(ports)==1, (s,"undeclared neighboring boundary")
            return ports.pop()
        return aliases.get(s,s)
    resistors=Counter(); capacitors=defaultdict(Decimal); negatives=[]; disposition=Counter()
    for t in items:
        if t[0][0].upper()=="R":
            component=r(t[1])
            if component in dynamic:
                resistors[(tuple(sorted((project(t[1]),project(t[2])))),number(t[3]))]+=1
                disposition["dynamic_R_retained"]+=1
            elif component in power:disposition["ideal_PG_R_removed"]+=1
            else:disposition["outside_R_removed"]+=1
        elif t[0][0].upper()=="C":
            roots=[r(s) for s in t[1:3]]; value=number(t[3])
            if any(s in dynamic for s in roots):
                capacitors[tuple(sorted(project(s) for s in t[1:3]))]+=value
                disposition["dynamic_C_aggregated"]+=1
                assert value>=0, (t,"negative C at dynamic boundary")
            elif all(s in power for s in roots):
                disposition["fixed_PG_C_removed"]+=1
            else:disposition["outside_C_removed"]+=1
            if value<0:
                assert all(s in power for s in roots), (t,"undeclared negative C projection")
                negatives.append(dict(id=t[0],nodes=t[1:3],value_F=str(value),mapped_nodes=[power[s] for s in roots]))
    assert all(v>=0 for v in capacitors.values())
    expected_mos=Counter()
    for t in chosen:
        expected_mos[(tuple(project(n) for n in t[1:5]), t[5], tuple(sorted(parameters(t[6:]).items())))]+=1
    expected_C=Counter((pair,v) for pair,v in capacitors.items() if v)
    model_path=summary_path.parent/"output_pixel_pex.spice"
    def check(text):
        defs,records=spice(text)
        assert len(defs)==1 and defs[0][1]=="output_pixel_pex" and defs[0][2:]==summary["ports"],"ordered ports differ"
        M=Counter();R=Counter();C=Counter()
        for t in records:
            if t[0][0].upper()=="X":M[(tuple(t[1:5]),t[5],tuple(sorted(parameters(t[6:]).items())))]+=1
            elif t[0][0].upper()=="R":R[(tuple(sorted(t[1:3])),number(t[3]))]+=1
            else:C[(tuple(sorted(t[1:3])),number(t[3]))]+=1
        assert M==expected_mos,"actual MOS W/L/body/junction properties or multiplicity differ"
        assert R==resistors,"actual signal R topology/value/multiplicity differ"
        # Export uses 12 decimal mantissa; value rounding is at most 0.5e-12 relative.
        assert len(C)==len(expected_C) and sum(C.values())==sum(expected_C.values()),"C endpoint pair/multiplicity differ"
        expected_by_pair={p:v for p,v in expected_C}
        for (pair,value),count in C.items():
            assert count==1 and pair in expected_by_pair,"duplicate or undeclared C pair"
            assert abs(value-expected_by_pair[pair])<=max(abs(value)*Decimal("6e-13"),Decimal("1e-30")),"C algebraic sum differs"
        return True
    check(model_path.read_text())
    identities=neighboring_identity(ext_path,summary["neighbors"]) if summary["rc_style"]=="nominal" else None
    _,exported=spice(model_path.read_text())
    exported_R=[q for q in exported if q[0][0]=="R"]
    exported_C=[q for q in exported if q[0][0]=="C"]
    assert all(number(q[3])>0 for q in exported_R)
    assert all(number(q[3])>=0 for q in exported_C)
    # Independently solve the actual signal resistor graph for a 1A test current.
    connections=defaultdict(set)
    for q in exported_R:
        connections[q[1]].add(q[2]);connections[q[2]].add(q[1])
    connected={"PWM_DRIVE"};todo=["PWM_DRIVE"]
    while todo:
        node=todo.pop()
        for nxt in connections[node]-connected:connected.add(nxt);todo.append(nxt)
    assert "PWM" in connected
    nodes=sorted(connected-{"PWM"});lookup={n:i for i,n in enumerate(nodes)}
    matrix=np.zeros((len(nodes),len(nodes)));current=np.zeros(len(nodes));current[lookup["PWM_DRIVE"]]=1
    for q in exported_R:
        a,b=q[1:3]
        if a not in connected:continue
        g=1/float(number(q[3]))
        if a!="PWM":matrix[lookup[a],lookup[a]]+=g
        if b!="PWM":matrix[lookup[b],lookup[b]]+=g
        if a!="PWM" and b!="PWM":matrix[lookup[a],lookup[b]]-=g;matrix[lookup[b],lookup[a]]-=g
    resistance=float(np.linalg.solve(matrix,current)[lookup["PWM_DRIVE"]])
    incident=sum((number(q[3]) for q in exported_C if any(n in connected for n in q[1:3])),Decimal(0))
    controls=[]; RAW.mkdir(parents=True,exist_ok=True)
    text=model_path.read_text()
    p=spice(text)[0][0][2:]
    mutants={"swapped_ordered_ports":text.replace(".subckt output_pixel_pex "+" ".join(p),".subckt output_pixel_pex "+" ".join([p[1],p[0],*p[2:]]),1)}
    _,records=spice(text)
    cap=max((q for q in records if q[0][0]=="C"),key=lambda q:number(q[3]))
    mutants["omitted_actual_dynamic_capacitor"]="\n".join(s for s in text.splitlines() if not s.startswith(cap[0]+" "))+"\n"
    buf=next(q for q in records if q[0][0]=="X" and q[5]=="nfet_05v0")
    old=" ".join(buf); change=old.replace(next(s for s in buf[6:] if s.startswith("w=")),"w="+str(parameters(buf[6:])["w"]*2))
    mutants["doubled_actual_buffer_MOS_width"]=text.replace(old,change,1)
    for name,mutation in mutants.items():
        path=RAW/(summary["rc_style"]+"-"+name+".spice");path.write_text(mutation)
        assert mutation!=text
        try:check(mutation)
        except AssertionError as error:
            controls.append(dict(name=name,rejected=True,reason=str(error),mutant_sha256=sha(path),raw_path=rel(path)))
        else:raise AssertionError("negative control accepted: "+name)
    return dict(passed=True,rc_style=summary["rc_style"],placement=placement,
                raw_counts=dict(C=sum(t[0][0]=="C" for t in items),R=sum(t[0][0]=="R" for t in items),MOS=sum(t[0][0]=="X" for t in items)),
                independently_selected_MOS=matches,disposition=dict(disposition),
                extraction_tool_version=extraction["tool_version"],extraction_tool_SHA256=extraction["tool_binary_sha256"],
                exported_counts=dict(MOS=sum(expected_mos.values()),R=sum(resistors.values()),C=sum(expected_C.values())),
                negative_raw_capacitors=negatives,negative_controls=controls,
                independent_neighbor_identity=identities,
                independent_RC_metrics=dict(output_drive_to_actual_analog_entry_R_ohm=resistance,output_component_incident_C_F=str(incident),
                                            all_exported_C_sum_F=str(sum((number(q[3]) for q in exported_C),Decimal(0))),
                                            passive_model=True,passivity_proof="Every explicit C>=0 and R>0; each passive capacitor stamp has energy C*(Va-Vb)^2/2>=0"),
                source_hashes={rel(p):sha(p) for p in [summary_path,model_path,raw_path,ext_path,res_ext_path,run/"extraction.json"]},
                method="DEF/LEF/GDS instance identity; raw R connected components; actual ext dimensions and terminal diffusion A/P; ordered MOS terminal identities; independent exact R/C multisets and algebraic cap aggregation; fixed ideal-PG projection only")


def budget_review():
    bpath=ROOT/"evidence/strategy/budget.json";b=json.loads(bpath.read_text())
    area_path=ROOT/"evidence/characterization/actual-w20-l4-area.json"
    load_path=ROOT/"evidence/characterization/measured-load-summary.json"
    area=json.loads(area_path.read_text());loads=json.loads(load_path.read_text())
    x0,y0,x1,y1=area["bbox_dbu"];unit=Fraction(str(area["dbu_um"]))
    a=(x1-x0)*(y1-y0)*unit*unit
    nominal=next(q for q in loads["dc_results"] if q["name"]=="typical_5.00_3.30_100")
    full=Fraction(str(nominal["led_rail_power_uW"]))+Fraction(str(nominal["logic_rail_power_uW"]))
    checks=[]
    def eq(name,value,want):
        assert Fraction(str(value))==want,(name,value,str(want));checks.append(name)
    for row in b["rows"]:
        n=row["pixels"]
        for key,want in {"analog_copies_bbox_sum_mm2":a*n/1_000_000,"independent_reference_floor_mW":Fraction(33,100)*n,
                         "full_on_analog_plus_LED_mW":full*n/1000,"single_buffer_bits":9*n,"double_buffer_bits":18*n,
                         "raw_60Hz_bps":60*9*n,"raw_each_PWM_frame_bps":Fraction(1_000_000,256)*9*n,
                         "proposed_packet_bits":32+16*n,"proposed_packet_60Hz_bps":60*(32+16*n),
                         "proposed_packet_each_PWM_frame_bps":Fraction(1_000_000,256)*(32+16*n)}.items():eq(str(n)+"/"+key,row[key],want)
    eq("20um current density",b["additional"]["current_density_20um_square_A_per_cm2"],Fraction(100,1_000_000)/Fraction(4,1_000_000))
    eq("4um hypothetical density",b["additional"]["hypothetical_current_density_4um_square_A_per_cm2"],625)
    eq("analog area to 4um square",b["additional"]["analog_bbox_to_4um_square_area_ratio"],a/16)
    for name,want in b["source_hashes"].items():assert sha(ROOT/name)==want
    return dict(passed=True,exact_arithmetic_checks=len(checks),method="Independent Fraction arithmetic from original geometry and DC input records; no budget runner import",
                analog_bbox_um2=str(float(a)),common_top_span_um=[305,180],array_implemented=False,
                TI_comparison=dict(source="https://www.ti.com/lit/ds/symlink/lp5860.pdf",locator="Rev.A p7 §7.5, independently visually read",
                                   current_uA=100,device_error_pct=7,channel_error_pct=5.5,
                                   device_denominator="ISET; numerator device mean minus ISET",channel_denominator="device channel mean; numerator selected channel minus mean",
                                   project_denominator="100uA target for a single model branch",ranked=False),
                source_hashes={rel(p):sha(p) for p in [bpath,area_path,load_path,ROOT/"evidence/strategy/claim-ledger.json",ROOT/"evidence/strategy/sources.json"]})


def hierarchy_review():
    path=ROOT/"build/joint-pex/full-nominal-r1/pixel_integrated_rc.spice"
    definitions,records=spice(path.read_text());caps=[q for q in records if q[0][0]=="C"]
    negative=[q for q in caps if number(q[3])<0]
    assert len(definitions)==33 and len(negative)==661
    assert sha(path.parent/"input.gds")==sha(ROOT/"evidence/integration/pixel_integrated.gds")
    index=ROOT/"evidence/joint-pex/summary.json";release=json.loads(index.read_text())
    styles={}
    for style,entry in release["styles"].items():
        p=index.parent/entry["summary"];s=json.loads(p.read_text())
        assert "flat-" in s["source_run"] and sha(p)==entry["summary_sha256"]
        styles[style]=dict(flat_run=s["source_run"],negative_raw_C=s["counts"]["negative_raw_C"],
                           input_identity_matches_v03=True)
    return dict(passed=True,method="Read preserved raw hierarchy and frozen flat-export provenance; do not treat unweighted subcircuit definition counts as physical total capacitance",
                literal_hierarchy_definitions=len(definitions),literal_unweighted_C_records=len(caps),
                literal_unweighted_negative_C_records=len(negative),literal_unweighted_negative_C_sum_F=str(sum((number(q[3]) for q in negative),Decimal(0))),
                examples=[dict(name=q[0],nodes=q[1:3],value_F=str(number(q[3]))) for q in negative[:4]],
                raw_hierarchy_not_instantiated_in_v04=True,raw_hierarchy_not_clipped=True,
                flat_exports=styles,
                interpretation="The 661 signed raw records span 33 subcircuit definitions and include hierarchy/template corrections. They are not 661 physical negative capacitors. Direct clipping would change the correction algebra. Released models use fresh actual flat extraction, then independently checked fixed-PG projection; no raw hierarchy or old route RC is stacked.",
                source_hashes={rel(p):sha(p) for p in [path,index]})


def reproduction_review():
    record_path=ROOT/"evidence/joint-pex/reproduction.json";record=json.loads(record_path.read_text())
    for name,h in record["inputs_sha256"].items():assert sha(ROOT/name)==h,(name,"reproduction input drift")
    def canonical(model,extres):
        definitions,items=spice(model.read_text());assert len(definitions)==1
        ports=definitions[0][2:];used={n for q in items for n in (q[1:5] if q[0][0]=="X" else q[1:3])}
        physical={}
        for line in extres.read_text().splitlines():
            if line.startswith("rnode "):
                q=shlex.split(line)
                if q[1] in used-set(ports):
                    base=q[1].rsplit(".",1)[0] if re.search(r"\.[tn]\d+$",q[1]) else q[1]
                    token=(base,int(q[4]),int(q[5]))
                    assert q[1] not in physical or physical[q[1]]==token,"ambiguous repeated physical rnode"
                    physical[q[1]]=token
        assert len(set(physical.values()))==len(physical),"geometric mapping is not injective"
        def node(n):
            if n in ports:return ("formal",n)
            return ("geometric",*physical[n]) if n in physical else ("unresisted",n)
        rows=[]
        for q in items:
            if q[0][0]=="X":rows.append(("X",tuple(node(n) for n in q[1:5]),q[5],tuple(sorted(parameters(q[6:]).items()))))
            else:rows.append((q[0][0],tuple(sorted(node(n) for n in q[1:3])),number(q[3])))
        return ports,Counter(rows),len(physical)
    old=ROOT/"evidence/joint-pex/nominal/output_pixel_pex.spice";new=ROOT/record["model"]
    old_ext=ROOT/"build/joint-pex/flat-nominal-r3/pixel_flat.res.ext";new_ext=ROOT/record["run"]/"pixel_flat.res.ext"
    a=canonical(old,old_ext);b=canonical(new,new_ext)
    assert a==b and old.read_bytes()!=new.read_bytes()
    return dict(passed=True,ordered_formal_ports_equal=True,formal_identity_preserved_before_geometry=True,
                injective_nonformal_geometric_nodes=a[2],exact_ordered_MOS_and_symmetric_RC_multisets_equal=True,
                model_records=dict(Counter(q[0] for q in a[1].elements())),
                original_model_SHA256=sha(old),fresh_model_SHA256=sha(new),byte_identical=False,
                method="Independent parser keeps every formal port name first, maps remaining actual .res.ext nodes to unique(netbase,x,y), requires injectivity and no ambiguous repeated record, then compares full Decimal values and multiplicities; no RC stats-only test",
                source_hashes={rel(p):sha(p) for p in [record_path,old,new,old_ext,new_ext]})


def endpoint_review():
    summary_path=ROOT/"evidence/robustness/boundary-summary.json";summary=json.loads(summary_path.read_text())
    case=next(q for q in summary["results"] if q["name"]=="RTL_reset")
    path=ROOT/summary["run_directory"]/case["name"]/"waveform.dat"
    a=np.loadtxt(path,skiprows=1);tail=a[-3:].copy();right=case["measurement_window_s"][1];left=tail[0,0]
    ulp=abs(np.spacing(right));RAW.mkdir(parents=True,exist_ok=True)
    good=tail.copy();good[-1,0]=right-2*ulp
    integrate_linear(good[:,0],good[:,8],left,right)
    accepted=RAW/"endpoint-two-ULP.dat";np.savetxt(accepted,good,fmt="%.17e")
    controls=[]
    for name,mutation in [("endpoint_32_ULP",tail.copy()),("missing_actual_last_sample",tail[:-1].copy())]:
        if name=="endpoint_32_ULP":mutation[-1,0]=right-32*ulp
        output=RAW/(name+".dat");np.savetxt(output,mutation,fmt="%.17e")
        try:integrate_linear(mutation[:,0],mutation[:,8],left,right)
        except AssertionError:controls.append(dict(name=name,rejected=True,input_sha256=sha(output),endpoint_gap_s=right-mutation[-1,0]))
        else:raise AssertionError("endpoint negative control accepted")
    return dict(passed=True,representation_only_allowance_ULP=8,positive_control_ULP=2,negative_controls=controls,
                actual_serialized_stop_gap_ULP=float((right-a[-1,0])/ulp),
                source_hashes={rel(p):sha(p) for p in [summary_path,path,accepted]},
                method="Actual raw RTL_reset tail retains all 18 saved columns. Only final text-coordinate is changed for 2 versus 32 ULP, plus actual endpoint sample omission. Declared denominator unchanged; no SPICE rerun or physical guard change")


def terminal_power_review():
    aggregate=ROOT/"evidence/robustness/summary.json";starting_sha=sha(aggregate);package=json.loads(aggregate.read_text())
    recomputations={}
    batches={}
    for group in ("probe","main","boundary"):
        path=ROOT/("evidence/robustness/"+group+"-summary.json")
        batch=json.loads(path.read_text());batches[group]=batch
        assert sha(path)==package["batches"][group]["summary_sha256"]
        proof=ROOT/("evidence/research/v04-"+group+"-recomputed.json")
        independent=json.loads(proof.read_text());assert independent["source_hashes"][rel(path)]==sha(path)
        recomputations[group]={q["name"]:q for q in independent["results"]}
    worst_J=0.;worst_uW=0.;results=[];expected_all={}
    def compare(row,expected):
        nonlocal worst_J,worst_uW
        duration=row["window_s"][1]-row["window_s"][0]
        assert set(row["energies_j"])==set(expected)
        for name,value in expected.items():
            delta=abs(value-row["energies_j"][name]);worst_J=max(worst_J,delta)
            assert delta<=max(1e-23,abs(value)*2e-11),(row["name"],name,"nested terminal energy differs")
            change=abs(value/duration*1e6-row["duration_average_uW"][name]);worst_uW=max(worst_uW,change)
            assert change<=max(1e-11,abs(value/duration*1e6)*2e-11)
    for row in package["selected_terminal_power_decomposition"]:
        batch=batches[row["group"]];original=recomputations[row["group"]][row["name"]]
        path=ROOT/batch["run_directory"]/row["name"]/"waveform.dat";assert sha(path)==row["raw_waveform_sha256"]
        columns=batch["vector_columns"]
        # Only three saved factors are needed; all other energies were already
        # independently reconstructed from the full original vector dataset.
        data=np.loadtxt(path,skiprows=1,usecols=(0,columns.index("i(VLEDLOAD)"),columns.index("v(led_k)")))
        left,right=row["window_s"]
        cathode=integrate_product(data[:,0],data[:,1],data[:,2],left,right)
        e=original["energies_J"];bias=e["reference_rail_absorbed_j"]-e["reference_B_source_absorbed_j"]
        expected=dict(external_LED_branch_rail_load=e["LED_load_absorbed_j"],
                      LED_device_terminal_load=e["LED_load_absorbed_j"]-cathode,
                      selected_joint_LED_K_terminal_input=cathode,
                      reference_supply_rail_load=e["reference_rail_absorbed_j"],
                      behavioral_reference_element_load=e["reference_B_source_absorbed_j"],
                      selected_joint_BIAS_terminal_input=bias,
                      selected_joint_VDD_terminal_input=e["logic_joint_load_absorbed_j"],
                      selected_joint_all_terminal_net_input=e["logic_joint_load_absorbed_j"]+bias+cathode+e["input_stimulus_generated_j"]+e["neighbor_stimulus_generated_j"],
                      declared_external_source_net_supply=e["LED_source_generated_j"]+e["logic_source_generated_j"]+e["input_stimulus_generated_j"]+e["neighbor_stimulus_generated_j"])
        compare(row,expected);expected_all[row["name"]]=expected
        results.append(dict(name=row["name"],group=row["group"],duration_average_uW={k:v/(right-left)*1e6 for k,v in expected.items()}))
    actual=next(q for q in package["selected_terminal_power_decomposition"] if q["name"]=="tt_post_d1")
    wrong=copy.deepcopy(actual)
    wrong["energies_j"]["selected_joint_all_terminal_net_input"]+=wrong["energies_j"]["behavioral_reference_element_load"]
    RAW.mkdir(parents=True,exist_ok=True);mutant=RAW/"double_count_behavioral_reference.json";mutant.write_text(json.dumps(wrong,indent=2)+"\n")
    try:compare(wrong,expected_all["tt_post_d1"])
    except AssertionError:control=dict(name="double_count_behavioral_reference",rejected=True,input_sha256=sha(mutant))
    else:raise AssertionError("nested double-counting control accepted")
    # Negative control differences must not pollute valid-record residuals.
    assert sha(aggregate)==starting_sha,"Terminal power package drifted during review"
    return dict(passed=True,terminal_accounts=len(results),results=results,
                maximum_valid_energy_residual_J=max(abs(expected_all[q["name"]][k]-q["energies_j"][k]) for q in package["selected_terminal_power_decomposition"] for k in q["energies_j"]),
                maximum_valid_power_residual_uW=max(abs(expected_all[q["name"]][k]/(q["window_s"][1]-q["window_s"][0])*1e6-q["duration_average_uW"][k]) for q in package["selected_terminal_power_decomposition"] for k in q["energies_j"]),
                negative_control=control,
                method="Independent original raw integral I_LED * V_LED_K, plus previously independently recomputed VDD, reference, input and neighbor energies; signed nested terminal account identities and explicit duration; no packager import",
                interpretation="Reference rail=B-element+BIAS, LED_A=LED device+LED_K. VDD draw alone is not all joint terminal input. Selected terminal net input includes internal stored-energy change; no pure-heat/full-PG power claim.",
                source_hashes={rel(aggregate):sha(aggregate)})


def panels(t, left, right):
    assert np.isfinite(t).all() and np.all(np.diff(t)>0) and left<right
    # Text output may round the declared endpoint down by 1-2 double ULP.
    # This representation-only allowance never admits a missing time interval.
    assert t[0]<=left or t[0]-left<=8*abs(np.spacing(left))
    assert right<=t[-1] or right-t[-1]<=8*abs(np.spacing(right))
    indices=np.flatnonzero((t[:-1]<right)&(t[1:]>left))
    dt=t[indices+1]-t[indices]
    lo=(np.maximum(t[indices],left)-t[indices])/dt
    hi=(np.minimum(t[indices+1],right)-t[indices])/dt
    return indices,dt,lo,hi


def integrate_linear(t,y,left,right):
    """Integrate the original linear panels by their normalized coordinate."""
    i,dt,a,b=panels(t,left,right)
    start=y[i]; slope=y[i+1]-start
    return float(np.sum(dt*(start*(b-a)+slope*(b*b-a*a)/2)))


def integrate_product(t,y,z,left,right):
    """Analytical integral of (y0+dy*u)(z0+dz*u), clipped in u."""
    i,dt,a,b=panels(t,left,right)
    y0,z0=y[i],z[i];dy,dz=y[i+1]-y0,z[i+1]-z0
    return float(np.sum(dt*(y0*z0*(b-a)+(y0*dz+z0*dy)*(b*b-a*a)/2+dy*dz*(b**3-a**3)/3)))


def negative_product_integral(t,y,z,left,right):
    ids,dt,a,b=panels(t,left,right);negative=0.0
    ys=y[ids]+(y[ids+1]-y[ids])*a;ye=y[ids]+(y[ids+1]-y[ids])*b
    zs=z[ids]+(z[ids+1]-z[ids])*a;ze=z[ids]+(z[ids+1]-z[ids])*b
    candidates=np.flatnonzero((np.minimum(ys,ye)<0)|(np.minimum(zs,ze)<0))
    for k in candidates:
        i=ids[k];y0,z0=y[i],z[i];dy,dz=y[i+1]-y0,z[i+1]-z0
        cuts=[a[k],b[k]]
        if dy and a[k]<-y0/dy<b[k]:cuts.append(-y0/dy)
        if dz and a[k]<-z0/dz<b[k]:cuts.append(-z0/dz)
        cuts=sorted(set(cuts))
        for lo,hi in zip(cuts[:-1],cuts[1:]):
            mid=(lo+hi)/2
            if (y0+dy*mid)*(z0+dz*mid)<0:
                negative+=dt[k]*(y0*z0*(hi-lo)+(y0*dz+z0*dy)*(hi**2-lo**2)/2+dy*dz*(hi**3-lo**3)/3)
    return negative


def threshold_events(t,y,threshold):
    up=[];down=[]
    for positive,out in [(True,up),(False,down)]:
        mask=(y[:-1]<threshold)&(y[1:]>=threshold) if positive else (y[:-1]>threshold)&(y[1:]<=threshold)
        ids=np.flatnonzero(mask)
        out.extend((t[ids]+(threshold-y[ids])*(t[ids+1]-t[ids])/(y[ids+1]-y[ids])).tolist())
    return np.array(up),np.array(down)


def waveform_review(summary_path):
    start_sha=sha(summary_path);summary=json.loads(summary_path.read_text());work=ROOT/summary["run_directory"]
    frozen=work/"inputs"
    for name,h in summary["source_hashes"].items():
        assert sha(frozen/name)==h,(name,"as-run input changed")
        assert sha(ROOT/name)==h,(name,"current release drift")
    for name,h in summary["raw_artifacts_sha256"].items():assert sha(work/name)==h,(name,"raw output changed")
    columns=summary["vector_columns"];assert columns[0]=="time_s" and len(columns)==18
    recomputed=[];deltas=defaultdict(float);assertions=0
    def close(name,a,b,unit,absolute=1e-12):
        nonlocal assertions
        difference=abs(a-b);deltas[unit]=max(deltas[unit],difference);assertions+=1
        assert difference<=max(absolute,abs(b)*2e-11),(name,a,b)
    for case in summary["dc_results"]:
        data=np.atleast_2d(np.loadtxt(work/case["name"]/"values.dat",skiprows=1))
        assert data.shape==(1,len(columns)) and np.isfinite(data).all()
        values=dict(zip(columns,data[0]));cur=values["i(VLEDLOAD)"]*1e6
        for key,actual in {"current_uA":cur,"logic_pin_v":values["v(logic_rail)"],
                           "LED_anode_v":values["v(led_a)"],"bias_v":values["v(bias)"],"pwm_v":values["v(pwm)"],
                           "reference_uA":values["i(VLREF)"]*1e6,
                           "load_power_uW":values["v(led_a)"]*cur}.items():
            close(case["name"]+" DC "+key,float(actual),case[key],"DC_scalar")
        if summary["group"] in ("main","probe"):
            assert (95<=cur<=105) if case["level"] else abs(cur)<.001
    for case in summary["results"]:
        path=work/case["name"]/"waveform.dat";data=np.loadtxt(path,skiprows=1)
        assert data.ndim==2 and data.shape[1]==len(columns) and np.isfinite(data).all()
        t=data[:,0];v={name:data[:,i] for i,name in enumerate(columns) if i};left,right=case["measurement_window_s"];duration=right-left
        close(case["name"]+" duration",duration,case["measurement_duration_s"],"duration_s",1e-16)
        current=v["i(VLEDLOAD)"];Q=integrate_linear(t,current,left,right);average=Q/duration*1e6
        close(case["name"]+" average",average,case["current_uA"],"current_uA")
        close(case["name"]+" Q",Q,case["LED_load_charge_c"],"charge_C",1e-22)
        c=summary["conditions"]["envelopes"][case.get("envelope","tt")]
        def supply(name,value):
            start=case.get(name)
            return np.full_like(t,value) if start is None else np.clip((t-start)/1e-7,0,1)*value
        logic=supply("logic_start_s",c["logic_v"]);led=supply("led_start_s",c["led_v"])
        E={"LED_source_generated_j":integrate_product(t,-v["i(VSUPLED)"],led,left,right),
           "logic_source_generated_j":integrate_product(t,-v["i(VSUPLOG)"],logic,left,right),
           "LED_load_absorbed_j":integrate_product(t,current,v["v(led_a)"],left,right),
           "logic_joint_load_absorbed_j":integrate_product(t,v["i(VLANA)"]+v["i(VLBUF)"],v["v(logic_rail)"],left,right),
           "reference_rail_absorbed_j":integrate_product(t,v["i(VLREF)"],v["v(logic_rail)"],left,right),
           "reference_B_source_absorbed_j":integrate_product(t,v["i(VLREF)"],v["v(logic_rail)"]-v["v(bias)"],left,right),
           "input_stimulus_generated_j":integrate_product(t,-v["i(BVIN)"],v["v(input)"],left,right),
           "neighbor_stimulus_generated_j":integrate_product(t,v["neighborcurrent"],v["v(logic_rail)"],left,right),
           "logic_series_R_loss_j":integrate_product(t,v["i(VSUPLOG)"],v["i(VSUPLOG)"],left,right)*case.get("rlogic_ohm",0),
           "LED_series_R_loss_j":integrate_product(t,v["i(VSUPLED)"],v["i(VSUPLED)"],left,right)*case.get("rled_ohm",0)}
        cap=case.get("decap_f",0)
        for label,node in [("logic","v(logic_rail)"),("LED","v(led_a)")]:
            ends=np.interp([left,right],t,v[node]);E[label+"_decap_stored_energy_change_j"]=float(cap*(ends[1]**2-ends[0]**2)/2)
        for key,value in E.items():
            close(case["name"]+"/"+key,value,case["energies_j"][key],"energy_J",1e-23)
            close(case["name"]+"/power/"+key,value/duration*1e6,case["powers_uW"][key],"power_uW")
        mask=(t>=left)&(t<=right)
        close(case["name"]+" peak",float(current[mask].max()*1e6),case["peak_LED_branch_current_uA"],"extremum_uA")
        close(case["name"]+" minimum",float(current[mask].min()*1e6),case["minimum_LED_branch_current_uA"],"extremum_uA")
        if "reference_B_source_active_delivery_energy_j" in case:
            delivery=-negative_product_integral(t,v["i(VLREF)"],v["v(logic_rail)"]-v["v(bias)"],left,right)
            close(case["name"]+" active reference delivery",delivery,case["reference_B_source_active_delivery_energy_j"],"negative_energy_J",1e-23)
        # Independent conservation across only the explicitly simulated rails.
        # Missing real PG charging is an exclusion, not an unaccounted simulation loss.
        residual_logic=E["logic_source_generated_j"]-E["logic_joint_load_absorbed_j"]-E["reference_rail_absorbed_j"]-E["logic_series_R_loss_j"]-E["logic_decap_stored_energy_change_j"]
        residual_LED=E["LED_source_generated_j"]-E["LED_load_absorbed_j"]-E["LED_series_R_loss_j"]-E["LED_decap_stored_energy_change_j"]
        row=dict(name=case["name"],envelope=case.get("envelope","tt"),view=case["view"],
                 post_rc_style=case.get("post_rc_style"),
                 current_uA=average,charge_C=Q,measurement_duration_s=duration,energies_J=E,
                 supply_KCL_energy_residual_J=dict(logic=residual_logic,LED=residual_LED))
        row["minimum_bias_V"]=float(v["v(bias)"][mask].min())
        row["peak_LED_current_uA"]=float(current[mask].max()*1e6)
        row["minimum_LED_current_uA"]=float(current[mask].min()*1e6)
        if "reference_B_source_active_delivery_energy_j" in case:row["ideal_reference_active_delivery_energy_J"]=delivery
        if summary["group"]=="main":
            frames=[integrate_linear(t,current,left+k*256e-6,left+(k+1)*256e-6)/256e-6*1e6 for k in (0,1)]
            for i,value in enumerate(frames):close(case["name"]+" frame"+str(i),value,case["frame_average_currents_uA"][i],"frame_current_uA")
            spread=abs(frames[1]-frames[0]);allowed=.001 if abs(average)<.001 else abs(average)*.002
            assert spread<=allowed,(case["name"],"frame repeatability")
            row["frame_current_uA"]=frames;row["frame_spread_uA"]=spread
            rises,falls=threshold_events(t,v["v(pwm)"],c["logic_v"]*.5)
            rise=rises[(rises>left)&(rises<right)];fall=falls[(falls>left)&(falls<right)]
            row["50pct_edge_count"]=[len(rise),len(fall)]
            duty=case["duty"]
            endpoints=(t>=left)&(t<=right)
            if duty in (1,64,255):
                assert len(rise)==len(fall)==2,(case["name"],"missing PWM pulse")
                metrics={}
                for label,ascending in [("rise",True),("fall",False)]:
                    low,high=(.3,.7) if ascending else (.7,.3)
                    lo=threshold_events(t,v["v(pwm)"],c["logic_v"]*low)[0 if ascending else 1]
                    hi=threshold_events(t,v["v(pwm)"],c["logic_v"]*high)[0 if ascending else 1]
                    mids=rise if ascending else fall
                    widths=[]
                    for event in mids:
                        a=lo[lo<=event];b=hi[hi>=event]
                        assert len(a) and len(b)
                        widths.append((b[0]-a[-1])*1e9)
                    key="rise_30_70_ns" if ascending else "fall_70_30_ns"
                    metrics[key]=max(widths);close(case["name"]+key,metrics[key],case[key],"slew_ns",1e-8)
                    assert metrics[key]<=3
                for label,begin,end in [("high",rise,fall),("low",fall,rise)]:
                    spans=[(end[end>a][0]-a)*1e9 for a in begin if np.any(end>a)]
                    assert spans and min(spans)>=950
                    close(case["name"]+label,min(spans),case[label+"_pulse_min_ns"],"pulse_ns",1e-7)
                row["slew_ns"]=metrics
            elif duty==0:
                assert not len(rise) and not len(fall) and np.max(v["v(pwm)"][endpoints])<c["logic_v"]*.3
                assert abs(average)<.001
            elif duty==256:
                assert not len(rise) and not len(fall) and np.min(v["v(pwm)"][endpoints])>c["logic_v"]*.7
                assert 95<=average<=105
            row["duty"]=duty
        recomputed.append(row)
    if summary["group"]=="main":
        for row,case in zip(recomputed,summary["results"]):
            full=next(q for q in recomputed if q["view"]==row["view"] and q["envelope"]==row["envelope"] and q["post_rc_style"]==row["post_rc_style"] and q["duty"]==256)
            if row["duty"]==1:
                # Two measured frames, one 1us on slot per frame, unadjusted full-on denominator.
                area=100*(row["charge_C"]/2/(full["current_uA"]*1e-6*1e-6)-1)
                close(row["name"]+" lowest area",area,case["area_error_pct"],"area_error_pct",1e-9)
                assert abs(area)<=2;row["lowest_code_area_error_pct"]=area
            if row["name"].endswith("_fine"):
                base=next(q for q in recomputed if q["name"]==row["name"].replace("_fine",""))
                change=abs(row["current_uA"]-base["current_uA"])
                allowed=.001 if abs(base["current_uA"])<.001 else abs(base["current_uA"])*.002
                assert change<=allowed;row["fine_step_current_change_pct"]=change/abs(base["current_uA"])*100
    for row in recomputed:
        for domain,residual in row["supply_KCL_energy_residual_J"].items():
            # This compares the declared ideal circuit, not unknown physical PG.
            scale=max(abs(row["energies_J"][domain+"_source_generated_j"]),1e-12)
            assert abs(residual)<=max(1e-15,scale*.002),(row["name"],domain,"source/load/R/decap conservation")
    result=dict(passed=True,group=summary["group"],transient_cases=len(recomputed),DC_cases=len(summary["dc_results"]),
                scalar_recalculation_assertions=assertions,maximum_recalculation_residuals=dict(deltas),results=recomputed,
                method="Original raw linear panels clipped in normalized u; current antiderivative and quadratic V*I polynomial antiderivative; explicit signed sources and actual case duration (main512us); independent threshold interpolation and engineering guards; no runner import",
                source_hashes={rel(summary_path):sha(summary_path)},
                scope="Actual selected-signal 12MOS ideal-PG projection; startup/series-R source energies omit extracted PG-only charging and full digital logic")
    assert sha(summary_path)==start_sha,"Waveform summary drifted during review"
    PUBLIC.parent.mkdir(parents=True,exist_ok=True)
    (PUBLIC.parent/("v04-"+summary["group"]+"-recomputed.json")).write_text(json.dumps(result,indent=2)+"\n")
    return {k:v for k,v in result.items() if k!="results"}


def main():
    p=argparse.ArgumentParser();p.add_argument("--stage",choices=["budget","hierarchy","reproduction","endpoint","terminal","pex","waveform","freeze"],required=True);p.add_argument("--pex-summary",type=Path);p.add_argument("--waveform-summary",type=Path)
    args=p.parse_args()
    document=json.loads(PUBLIC.read_text()) if PUBLIC.exists() else dict(schema_version=1,date="2026-10-05",stages={},limitations=["No new silicon/optical evidence","Ideal PG projection is not full PG/substrate signoff","RC variants are deck variants, distinct from MOS envelopes"])
    if args.stage=="budget":document["stages"]["budget"]=budget_review()
    elif args.stage=="hierarchy":document["stages"]["raw_hierarchy_scope"]=hierarchy_review()
    elif args.stage=="reproduction":document["stages"]["fresh_reproduction"]=reproduction_review()
    elif args.stage=="endpoint":document["stages"]["endpoint_controls"]=endpoint_review()
    elif args.stage=="terminal":document["stages"]["terminal_power"]=terminal_power_review()
    elif args.stage=="freeze":
        required={"budget","PEX_nominal","PEX_hrhc","PEX_lrhc","PEX_hrlc","PEX_lrlc","waveform_probe","raw_hierarchy_scope","waveform_main","fresh_reproduction","endpoint_controls","waveform_boundary","terminal_power"}
        assert required==set(document["stages"]),"Required independent review stage missing"
        all_inputs={}
        for stage in document["stages"].values():
            assert stage["passed"]
            for path,h in stage["source_hashes"].items():
                assert sha(ROOT/path)==h,(path,"final frozen review input drift")
                assert path not in all_inputs or all_inputs[path]==h
                all_inputs[path]=h
        document["all_verified_inputs_sha256"]=all_inputs
        document["passed"]=True
        document["scope"]="Independent input/provenance, 5 RC-style physical/netlist structure, fresh-reproduction exact graph, 66 transient + 28 DC raw mathematical/engineering checks; only SSxHRHC and FFxLRLC additional electrical cross points; ideal PG, artificial neighbor clamps and synthetic LED dynamics remain explicit exclusions"
        controls=[]
        for name,stage in document["stages"].items():
            for q in stage.get("negative_controls",[]):controls.append(name+": "+q["name"]+" -> REJECT ("+q.get("reason","endpoint completeness guard")+")")
        controls.append("terminal_power: double_count_behavioral_reference -> REJECT (nested terminal account identity)")
        control_path=PUBLIC.parent/"v04-controls.txt";control_path.write_text("Actual copied netlist / waveform-tail / terminal-account negative controls. Baseline inputs are unchanged.\n"+"\n".join(controls)+"\n")
        document["negative_controls_total"]=len(controls)
        document["public_recalculation_artifacts_sha256"]={rel(q):sha(q) for q in [control_path,*sorted(PUBLIC.parent.glob("v04-*-recomputed.json"))]}
        document["freeze_schema"]="Each stages.*.source_hashes and all_verified_inputs_sha256 is a repository-relative path->sha256 map; public_recalculation_artifacts_sha256 covers independent full small outputs; review_source_sha256 is scripts/research/review_v04.py. Preserve original as-run input hashes, not rewritten snapshots."
    elif args.stage=="pex":
        assert args.pex_summary
        q=physical_expected(args.pex_summary.resolve());document["stages"]["PEX_"+q["rc_style"]]=q
    else:
        assert args.waveform_summary
        q=waveform_review(args.waveform_summary.resolve());document["stages"]["waveform_"+q["group"]]=q
    document["review_source_sha256"]=sha(Path(__file__))
    document["review_completed_stages"]=list(document["stages"])
    document["passed_completed_stages"]=all(s["passed"] for s in document["stages"].values())
    PUBLIC.parent.mkdir(parents=True,exist_ok=True);PUBLIC.write_text(json.dumps(document,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(dict(passed=document["passed_completed_stages"],stages=document["review_completed_stages"]),indent=2))


if __name__=="__main__":main()

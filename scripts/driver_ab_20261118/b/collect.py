"""Keep per-case results and derive FF reconnect slew directly from full-density short traces."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
BUILD = ROOT/"build/driver-ab-20261118/b"
EV = ROOT/"evidence/driver-ab-20261118/b"

def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()

def cross(t, y, level):
    idx = np.flatnonzero((y[:-1] < level) & (y[1:] >= level))
    if not len(idx):
        return None
    k = idx[0]
    return float(t[k] + (level-y[k])/(y[k+1]-y[k])*(t[k+1]-t[k]))

def diagnostic(folder, manifest):
    m = manifest["case"]["mode"]
    with np.load(folder/"preview.npz") as trace:
        t = (trace["time_s"]-manifest["diagnostic"]["edge_s"])*1e9
        keep = t>=0
        z={key:trace[key][keep] for key in ["out","ib1","led_a","led_k","iso_p","clamp_g","data_safe","iled_cond","ipkg","iso0_id"]}
        t = t[keep]
        k=int(np.argmax(z["out"]))
        result = dict(postcommand_out_peak_V=float(z["out"][k]),time_out_peak_ns=float(t[k]),
                    out_peak_state={key:float(y[k]) for key,y in z.items()},
                    whole_trace_ib1_max_V=float(trace["ib1"].max()))
        if m=="release":
            final_voltage = manifest["pvt"]["VLED_V"]
            t10 = cross(t,z["led_a"],.1*final_voltage)
            t90 = cross(t,z["led_a"],.9*final_voltage)
            if t10 is not None and t90 is not None and t90>t10:
                result["anode_10_90"] = dict(
                    t10_ns=t10,t90_ns=t90,interval_ns=t90-t10,mean_slew_V_per_ns=.8*final_voltage/(t90-t10))
        return result

def main():
    rows=[]
    for path in sorted(BUILD.glob("*/*/result.json")):
        if path.parent.parent.name.startswith("_"):
            continue
        r=json.loads(path.read_text())
        folder=path.parent
        m=json.loads((folder/"manifest.json").read_text())
        result=dict(path=str(folder.relative_to(ROOT)),case=r["case"],source_snapshot_sha256=m["execution_sha256"],
                    result_sha256=digest(path),deck_sha256=r["deck_sha256"],raw_sha256=r["raw_sha256"],
                    simulation_ok=r["simulation_ok"],analysis_error=r.get("analysis_error"))
        if "stress" in r:
            result.update(MOS=r["MOS"],terminal_pass=r["terminal_pass"],body_pass=r["body_pass"],
                body_peak_V=r["body_forward_V"],out_pair_V=next(x["peak_pair_V"] for x in r["stress"] if x["instance"]=="xdrv.xbase"),
                failed_devices=[x for x in r["stress"] if not (x["terminal_pass"] and x["body_pass"])])
        if "DC_error_percent" in r:
            result.update(current_uA=r["current_uA"],error_percent=r["DC_error_percent"],DC_pass=r["DC_pass"])
        if "diagnostic" in m and (folder/"preview.npz").is_file():
            result["edge"]=diagnostic(folder,m)
        if "shutdown" in r:
            result["off"]={k:v for k,v in r["shutdown"].items() if k in ["last_above_threshold_ns","max_abs_current_uA","recovery_screen","post_guard_current_range_uA","off_current_screen_pass"]}
        if "frames" in r:
            result["frames"]=[dict(frame=f["frame"],full=f["full_receiver"],fixed=f["first_frame_phase_receiver"],
                      energy_pJ_per_attempted_payload_bit=f["energy_pJ_per_attempted_payload_bit"]) for f in r["frames"]]
        rows.append(result)
    output=dict(generator_sha256=digest(Path(__file__)),count=len(rows),rows=rows)
    EV.mkdir(parents=True,exist_ok=True)
    (EV/"results.json").write_text(json.dumps(output,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    print(len(rows),"complete cases")

if __name__=="__main__":
    main()

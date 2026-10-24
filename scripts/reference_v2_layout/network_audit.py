"""Independent DC graph solve of all extracted interconnect R networks.

Checks reachability and computes actual terminal-to-port effective R. A branch
sum is never reported as effective R. Substrate values describe pinned Magic's
exported graph only, not a validated substrate field solution.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--module", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    folder = ROOT/args.module
    c = json.loads((folder/"physical-contract.json").read_text())
    rc = folder/"full-rc"/(c["top"]+"_rc.spice")
    lines = re.sub(r"\n\+\s*", " ", rc.read_text()).splitlines()
    names = set(c["buses_um"])
    edges = []
    for line in lines:
        t = line.split()
        if t and t[0].startswith("R"):
            r = float(t[3])
            assert np.isfinite(r) and r > 0
            edges.append((t[0],t[1],t[2],r))
    result = {}
    for net in sorted(names):
        terminals = [(d["original_instance"],pin,node) for d in c["extracted_device_mapping"]+c.get("extracted_resistor_mapping",[])
                     for pin,node in d["rc_nodes"].items() if d["original_nodes"][pin] == net]
        local = [r for r in edges if all(n == net or n.startswith(net+".") for n in r[1:3])]
        nodes = set(n for _,a,b,_ in local for n in (a,b)) | {net}
        assert all(node in nodes for _,_,node in terminals)
        adjacency = {n:set() for n in nodes}
        for _,a,b,_ in local:
            adjacency[a].add(b)
            adjacency[b].add(a)
        reached, todo = {net}, [net]
        while todo:
            at = todo.pop()
            for n in adjacency[at] - reached:
                reached.add(n)
                todo.append(n)
        assert reached == nodes
        ordered = sorted(nodes-{net})
        index = {n:i for i,n in enumerate(ordered)}
        g = np.zeros((len(ordered),len(ordered)))
        for _,a,b,r in local:
            for n in (a,b):
                if n != net:
                    g[index[n],index[n]] += 1/r
            if a != net and b != net:
                g[index[a],index[b]] -= 1/r
                g[index[b],index[a]] -= 1/r
        z = np.linalg.solve(g,np.eye(len(ordered))) if ordered else g
        residual = float(np.max(np.abs(g@z-np.eye(len(ordered))))) if ordered else 0
        assert residual < 1e-8
        values = [dict(instance=d,pin=pin,node=n,
                       effective_ohm=0 if n==net else float(z[index[n],index[n]]))
                  for d,pin,n in terminals]
        result[net] = dict(anchor_is_external_port=net in c["ports"],
            nodes=len(nodes), branches=len(local), all_terminals_connected=True,
            inverse_residual=residual, terminal_to_anchor=values,
            max_terminal_to_anchor_ohm=max(v["effective_ohm"] for v in values))
    assert sum(r["branches"] for r in result.values()) == len(edges)
    output = dict(schema_version=1,passed=True,
        rc=str(rc.relative_to(ROOT)), rc_sha256=hashlib.sha256(rc.read_bytes()).hexdigest(),
        method="Independent full nodal conductance inversion; 1 A terminal injection to the named net anchor; "
               "no MOS current/capacitance active. All R branches and mapped terminals included.",
        limitations=["Terminal effective R is not a sum of branch R.",
                     "Substrate values establish only the graph exported by pinned Magic, not local physical substrate collection.",
                     ("Actual intermodule metal is included; package/PCB resistance and EM effects are excluded."
                      if c.get("intermodule_bridges") else "No intermodule/package/PCB resistances or EM effects included.")], networks=result)
    (ROOT/args.out).write_text(json.dumps(output,indent=2)+"\n")
    print(json.dumps(dict(passed=True,nets=len(result),resistors=len(edges),
        supply_max_effective_ohm={n:r["max_terminal_to_anchor_ohm"] for n,r in result.items() if n in ["VIN","VSS"]})))


if __name__ == "__main__":
    main()

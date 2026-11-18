"""Register exactly the sources represented in each delivered figure."""
import run as a

def main():
    sources={}
    dc=[]
    original=a.read(a.EV/'TT-ideal.json')['codes']
    for point in a.GRID:
        row=a.read(a.EV/f'{point}-ideal.json')
        for level in (0,1):
            dc.append(a.PARENT/f'{point}-DC-L{level}'/'result.json')
            dc.append(a.BUILD/f'sense-{point}'/f'dc{level}-h{original[0]}-l{original[1]}'/'result.json')
            dc.append(a.ROOT/row['final'][level]['case_path']/'result.json')
    scripts=a.ROOT/'scripts/driver_ab_20261118/a'
    rendered=a.ROOT/'docs/research/driver-ab-20261118/assets'
    sources['a-current-error']=[scripts/'report.py',a.EV/'dc-summary.json',*dc]
    codes=a.read(a.EV/'TT-ideal.json')['codes']
    p=a.BUILD/'sense-TT'/f'dc0-h{codes[0]}-l{codes[1]}'
    sources['a-sense-schematic']=[scripts/'report.py',scripts/'run.py',p/'testbench.spice',p/'route_a.spice']
    sources['a-fault-waves']=[scripts/'report.py',*[next((a.BUILD/k).glob('fault*/preview.npz')) for k in ['sense-SShotlow','baseline-SShotlow']]]
    sources['a-shutdown-cap']=[scripts/'edge_figure.py',*[a.BUILD/'edge-SS'/f'assert-c{cap}-s40'/'preview.npz' for cap in (0,150)]]
    a.emit(a.EV/'figure-sources.json',{name:dict(figure_sha256=a.sha(rendered/(name+'.png')),
        inputs={str(p.relative_to(a.ROOT)):a.sha(p) for p in files}) for name,files in sources.items()})
if __name__=='__main__':main()

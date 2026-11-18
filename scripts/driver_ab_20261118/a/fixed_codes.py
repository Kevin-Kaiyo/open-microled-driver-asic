"""Apply the nominally calibrated pair to all nine original environments, without recalibration."""
import run as a

if __name__=='__main__':
    codes=tuple(a.read(a.EV/'TT-ideal.json')['codes'])
    for point in a.GRID:
        for level in (0,1):
            a.run(point,codes,level)

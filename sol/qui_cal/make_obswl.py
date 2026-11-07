"""Daily observed QUI water level table for fix_finund_obswl.

Reads WTD_GAPFILLED_m (m, positive above the surface) from the PE-QFR forcing source CSV, averages to daily means
(2018-2019) and writes 'year doy level_m' for each model year in [y0, y1]. Model year Y uses forcing year
2018 + mod(Y - 1980, 2), the DATM alignment of the QUI cases (streams 1980 2018 2019, taxmode cycle).
Usage: python make_obswl.py <forcing_csv.gz> <out.txt> [y0 y1]
"""
import csv, gzip, sys
from collections import defaultdict

src, out = sys.argv[1], sys.argv[2]
y0, y1 = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (2015, 2019)
cum = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
acc = defaultdict(list)
for r in csv.DictReader(gzip.open(src, 'rt')):
    t = r['TIMESTAMP_START']
    if r['WTD_GAPFILLED_m'] in ('', '-9999'): continue
    acc[(int(t[:4]), cum[int(t[4:6]) - 1] + int(t[6:8]))].append(float(r['WTD_GAPFILLED_m']))
lev = {k: sum(v) / len(v) for k, v in acc.items()}
for fy in (2018, 2019):
    miss = [d for d in range(1, 366) if (fy, d) not in lev]
    assert not miss, f'{fy}: missing days {miss[:10]}'
with open(out, 'w') as f:
    for y in range(y0, y1 + 1):
        fy = 2018 + (y - 1980) % 2
        for d in range(1, 366):
            f.write(f'{y} {d} {lev[(fy, d)]:.4f}\n')
print(f'wrote {out}: model years {y0}-{y1}, forcing years 2018/2019; 2019 mean {sum(lev[(2019,d)] for d in range(1,366))/365:.4f} m')

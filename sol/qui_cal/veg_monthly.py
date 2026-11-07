import sys, json, numpy as np, netCDF4 as nc
from pathlib import Path
run = Path(sys.argv[1]); W = np.array([0.64, 0.36]); md = [31,28,31,30,31,30,31,31,30,31,30,31]
pv = ['GPP','NPP','AR','ER','HR','NEE','TLAI','LITFALL','LEAFC','FROOTC','RR','FROOTC_ALLOC','LEAFC_ALLOC','LEAF_MR','QVEGT','FSA','BTRAN','FPSN']
cv = ['HR','SOILC_HR','LITTERC_HR','DOMC','CDOCS','FSDS']
out = {}
for m in range(1, 13):
    p = next(run.glob(f'*.clm2.h0.2019-{m:02d}.nc'))
    with nc.Dataset(p) as d:
        ci = np.arange(d.dimensions['pft'].size) // (d.dimensions['pft'].size // 2)   # 17 pfts per column, columns in order
        wc = np.ma.filled(d['pfts1d_wtcol'][:], 0).astype(float)
        for k in pv:
            if k not in d.variables: continue
            x = np.ma.filled(d[k][:], np.nan).astype(float)[0]
            if x.ndim == 1 and x.size == wc.size:
                col = np.array([np.nansum((x * wc)[ci == c]) for c in range(2)])
            else:
                col = x[:2]
            out.setdefault(k, []).append(float(col @ W))
print(json.dumps(out))

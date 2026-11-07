"""Monthly 2019 CH4 drivers for one QUI run with full h0 output, against the tower.

Usage: python diag_qui_cycle.py <run_dir> <tower_csv> [year]
Columns weighted 0.64 (hummock) / 0.36 (hollow). Prints a table and writes cycle_<year>.json in the cwd.
"""
import csv, json, sys
from pathlib import Path
import numpy as np, netCDF4 as nc

run, tower = Path(sys.argv[1]), Path(sys.argv[2])
yr = sys.argv[3] if len(sys.argv) > 3 else '2019'
W = np.array([0.64, 0.36])
cum = np.cumsum([0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])

h0 = sorted(run.glob('*.clm2.h0.*.nc'))
with nc.Dataset(h0[0]) as d:
    dz = np.ma.filled(d['DZSOI'][:], np.nan).astype(float)[:, :2]   # (lev, col)
    zs = np.ma.filled(d['ZSOI'][:], np.nan).astype(float)[:, :2]
f = lambda d, k: np.ma.filled(d[k][:], np.nan).astype(float)[0]

rows = []
for m in range(1, 13):
    p = next(run.glob(f'*.clm2.h0.{yr}-{m:02d}.nc'))
    with nc.Dataset(p) as d:
        r = {}
        col = lambda k: f(d, k)[:2]
        integ = lambda k: np.nansum(f(d, k)[:dz.shape[0], :2] * dz[:f(d, k).shape[0]][:dz.shape[0]], axis=0)
        r['flux'] = col('CH4_SURF_NETFLUX') @ W * 1e9
        prod = f(d, 'CH4_PROD_TOT_DEPTH')[:, :2]; nl = prod.shape[0]
        pz = prod * dz[:nl]
        r['prod'] = np.nansum(pz, 0) @ W * 1e9
        r['prod_hum'], r['prod_hol'] = np.nansum(pz, 0) * 1e9
        ox = (f(d, 'CH4_OXID_O2_DEPTH')[:, :2] + f(d, 'CH4_OXID_AOM_DEPTH')[:, :2]) * dz[:nl]
        r['oxid'] = np.nansum(ox, 0) @ W * 1e9
        for lo, hi, tag in [(0, .3, 'p0_30'), (.3, 1., 'p30_100'), (1., 99, 'p100_')]:
            sel = (zs[:nl] >= lo) & (zs[:nl] < hi)
            r[tag] = np.nansum(np.where(sel, pz, 0), 0) @ W * 1e9
        ts = f(d, 'TSOI')[:, :2] - 273.15
        k10 = np.argmin(abs(zs[:, 0] - .1)); k50 = np.argmin(abs(zs[:, 0] - .5))
        r['T10'], r['T50'] = ts[k10] @ W, ts[k50] @ W
        r['Tprod'] = float(np.nansum(ts[:nl] * pz) / np.nansum(pz))      # production-weighted temperature
        r['zwt_hum'], r['zwt_hol'] = col('ZWT')
        r['fin_hum'], r['fin_hol'] = col('FINUNDATED')
        r['fh2osfc'] = col('FH2OSFC') @ W
        r['snow'] = col('SNOW_DEPTH') @ W
        r['ice_top'] = np.nansum(f(d, 'SOILICE')[:3, :2], 0) @ W
        r['ace'] = np.nansum(f(d, 'CACES')[:nl, :2] * dz[:nl], 0) @ W
        r['doc'] = np.nansum(f(d, 'CDOCS')[:nl, :2] * dz[:nl], 0) @ W
        r['ch4_stock'] = np.nansum(f(d, 'CCON_CH4S')[:nl, :2] * dz[:nl], 0) @ W
        r['aere'] = col('CH4_SURF_AERE') @ W * 1e9
        r['ebul'] = col('CH4_SURF_EBUL') @ W * 1e9
        r['diff'] = col('CH4_SURF_DIFF') @ W * 1e9
        r['gpp'] = np.nan
    rows.append({k: float(v) for k, v in r.items()})

# tower monthly FCH4 and TS (days with >= 12 valid half-hours)
obs, ts = {}, {}
for rr in csv.DictReader(x for x in tower.open() if not x.startswith('#')):
    t = rr['TIMESTAMP_START']
    if t[:4] != yr: continue
    k = int(cum[int(t[4:6]) - 1] + int(t[6:8]))
    if float(rr['FCH4']) > -9999: obs.setdefault(k, []).append(float(rr['FCH4']))
    if float(rr['TS_1_1_1']) > -9999: ts.setdefault(k, []).append(float(rr['TS_1_1_1']))
dm = lambda o: np.array([np.mean(o[k]) if len(o.get(k, [])) >= 12 else np.nan for k in range(1, 366)])
od, td = dm(obs), dm(ts)
for m, r in enumerate(rows):
    sl = slice(cum[m], cum[m + 1])
    r['tower'] = float(np.nanmean(od[sl])) if np.isfinite(od[sl]).sum() >= 3 else float('nan')
    r['tower_TS'] = float(np.nanmean(td[sl])) if np.isfinite(td[sl]).sum() >= 3 else float('nan')

keys = ['tower', 'flux', 'prod', 'oxid', 'p0_30', 'p30_100', 'p100_', 'prod_hum', 'prod_hol', 'aere', 'ebul', 'diff',
        'ch4_stock', 'tower_TS', 'T10', 'T50', 'Tprod', 'snow', 'ice_top', 'zwt_hum', 'zwt_hol', 'fin_hum', 'fin_hol',
        'fh2osfc', 'ace', 'doc']
print(f'{"":10s}' + ''.join(f'{m:>7d}' for m in range(1, 13)))
for k in keys:
    print(f'{k:10s}' + ''.join(f'{r[k]:7.3g}' for r in rows))
json.dump(rows, open(f'cycle_{yr}.json', 'w'), indent=1)

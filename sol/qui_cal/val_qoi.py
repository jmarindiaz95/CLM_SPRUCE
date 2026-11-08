#!/usr/bin/env python3
"""CH4 model vs tower for one QUI run and one year (validation; same definitions as member_qoi.py).

Model: area-weighted CH4_SURF_NETFLUX from h1 (half-hourly instantaneous, step-start assignment), daily means.
Tower: AmeriFlux BASE FCH4, daily means of days with >= 12 valid half-hours; monthly means of months with >= 3 such
days. Model monthly values are taken both over all days and over tower days only (paired). Windows: wet DOY 32-120,
dry DOY 213-273 (the 2019 calibration windows), model all days and tower days. Prints JSON.
Usage: python val_qoi.py <run_dir> <tower BASE csv> <year>
"""
import csv, json, sys
from pathlib import Path
import numpy as np
import netCDF4 as nc

d, TOWER, Y = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
w = np.array([.64, .36])
md = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]); cum = np.concatenate([[0], np.cumsum(md)])
q = dict(run=str(d), year=Y, ok=any('SUCCESSFUL TERMINATION' in p.read_text(errors='replace') for p in d.glob('cpl.log.*')))
v = {k: [] for k in ['mcdate', 'mcsec', 'CH4_SURF_NETFLUX', 'CH4_SURF_DIFF', 'CH4_SURF_AERE', 'CH4_SURF_EBUL', 'FINUNDATED']}
for p in sorted(d.glob('*.clm2.h1.*.nc')):
    with nc.Dataset(p) as f:
        for k in v: v[k].append(np.ma.filled(f[k][:], np.nan).astype(float))
v = {k: np.concatenate(x) for k, x in v.items()}
ymd = v['mcdate'].astype(int); sec = v['mcsec'].astype(int)
yr, mo, dy = ymd // 10000, (ymd // 100) % 100, ymd % 100
tsec = (cum[mo - 1] + dy - 1) * 86400 + sec - 1800
yr = np.where(tsec < 0, yr - 1, yr); tsec = np.where(tsec < 0, tsec + 365 * 86400, tsec)
doy = tsec // 86400 + 1
iy = yr == Y
assert iy.sum() == 365 * 48, f'{iy.sum()} model steps in {Y}'
em = v['CH4_SURF_NETFLUX'] @ w * 1e9
daily = np.array([np.mean(em[iy & (doy == k)]) for k in range(1, 366)])
fin = np.array([np.mean(v['FINUNDATED'][iy & (doy == k)] @ w) for k in range(1, 366)])
q['annual_gC'] = float(np.mean(em[iy]) * 1e-9 * 86400 * 365 * 12)
tot = {k: float(np.sum((v[f'CH4_SURF_{k}'] @ w)[iy])) for k in ['DIFF', 'AERE', 'EBUL']}
q['share'] = {k: x / sum(tot.values()) for k, x in tot.items()}

obs = {}
for r in csv.DictReader(x for x in TOWER.open() if not x.startswith('#')):
    t = r['TIMESTAMP_START']
    if int(t[:4]) != Y or t[4:8] == '0229': continue
    x = float(r['FCH4'])
    if x > -9999: obs.setdefault(int(cum[int(t[4:6]) - 1] + int(t[6:8])), []).append(x)
od = np.array([np.mean(obs[k]) if len(obs.get(k, [])) >= 12 else np.nan for k in range(1, 366)])
ok = np.isfinite(od)
q['tower_days'] = int(ok.sum())
q['tower_mean_on_days'] = float(np.mean(od[ok])); q['model_mean_on_days'] = float(np.mean(daily[ok]))
q['daily_r'] = float(np.corrcoef(daily[ok], od[ok])[0, 1])
M = []
for m in range(12):
    sl = slice(cum[m], cum[m + 1]); o = ok[sl]
    M.append(dict(month=m + 1, model=float(np.mean(daily[sl])), fin=float(np.mean(fin[sl])), tower_days=int(o.sum()),
                  tower=float(np.mean(od[sl][o])) if o.sum() >= 3 else None,
                  model_paired=float(np.mean(daily[sl][o])) if o.sum() >= 3 else None))
q['monthly'] = M
mm = np.array([x['model'] for x in M if x['tower'] is not None]); mp = np.array([x['model_paired'] for x in M if x['tower'] is not None])
mt = np.array([x['tower'] for x in M if x['tower'] is not None])
q['monthly_n'] = len(mt)
q['monthly_r'] = float(np.corrcoef(mm, mt)[0, 1]); q['monthly_r_paired'] = float(np.corrcoef(mp, mt)[0, 1])
q['monthly_nrmse'] = float(np.sqrt(np.mean((mm - mt) ** 2)) / mt.mean())
q['monthly_nrmse_paired'] = float(np.sqrt(np.mean((mp - mt) ** 2)) / mt.mean())
for lab, a, b in [('wet', 31, 120), ('dry', 212, 273)]:
    o = ok[a:b]
    q[f'{lab}_model'] = float(np.mean(daily[a:b]))
    q[f'{lab}_model_on_tower_days'] = float(np.mean(daily[a:b][o])) if o.any() else None
    q[f'{lab}_tower'] = float(np.mean(od[a:b][o])) if o.any() else None
    q[f'{lab}_tower_days'] = int(o.sum())
print(json.dumps(q))

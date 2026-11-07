#!/usr/bin/env python3
"""Quantities of interest for one calibration member (2015-2019 run): 2019 area-weighted CH4 annual, wet (DOY 32-120)
and dry (DOY 213-273) daily-mean CH4, monthly means and correlation with the tower, pathway shares, GPP, budget
residual, stock change, termination. Prints JSON."""
import csv, json, sys
from pathlib import Path
import numpy as np
import netCDF4 as nc

d = Path(sys.argv[1])
TOWER = Path('/scratch/jmarindi/elm_work/qui_cal/inputs/AMF_PE-QFR_BASE_HH_3-5.csv')
w = np.array([.64, .36]); parts = ['SAT', 'UNSAT']; dt = 1800.
md = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]); cum = np.concatenate([[0], np.cumsum(md)])
q = dict(member=d.name, ok=any('SUCCESSFUL TERMINATION' in p.read_text(errors='replace') for p in d.glob('cpl.log.*')))
h1 = sorted(d.glob('*.clm2.h1.*.nc'))
if not q['ok'] or not h1:
    print(json.dumps(q)); sys.exit()
names = ['mcdate', 'mcsec', 'FINUNDATED', 'CH4_SURF_NETFLUX', 'CH4_SURF_DIFF', 'CH4_SURF_AERE', 'CH4_SURF_EBUL'] + \
        [f'CH4BUD_{a}_{p}' for a in ['NORM_RES', 'STOCK'] for p in parts]
v = {k: [] for k in names}
for p in h1:
    with nc.Dataset(p) as f:
        for k in names: v[k].append(np.ma.filled(f[k][:], np.nan).astype(float))
v = {k: np.concatenate(x) for k, x in v.items()}
# timestamp of each instantaneous sample = end of step; assign to the step's start (subtract one step)
ymd = v['mcdate'].astype(int); sec = v['mcsec'].astype(int)
yr, mo, dy = ymd // 10000, (ymd // 100) % 100, ymd % 100
doy = cum[mo - 1] + dy
tsec = (doy - 1) * 86400 + sec - 1800
yr = np.where(tsec < 0, yr - 1, yr); tsec = np.where(tsec < 0, tsec + 365*86400, tsec)
doy = tsec // 86400 + 1; hh = (tsec % 86400) // 1800
f = v['FINUNDATED']; fr = np.stack([f, 1 - f], -1)
area = lambda k: (np.stack([v[f'{k}_{p}'] for p in parts], -1) * fr).sum(-1) @ w
em = v['CH4_SURF_NETFLUX'] @ w * 1e9                      # nmol m-2 s-1 (= area-weighted with fix_micfin_agg)
i19 = yr == 2019
q['res_2015_2019_mol_m2'] = float(np.nansum(area('CH4BUD_NORM_RES')) * dt)
stock = ((np.stack([v[f'CH4BUD_STOCK_{p}'] for p in parts], -1)/12) * fr).sum(-1) @ w
s19 = np.flatnonzero(i19)
q['stock_change_2019_mol_m2'] = float(stock[s19[-1]] - stock[s19[0]])
q['annual_2019_gC'] = float(np.nanmean(em[i19]) * 1e-9 * 86400 * 365 * 12)
daily = np.array([np.nanmean(em[i19 & (doy == k)]) for k in range(1, 366)])
q['wet_mean'] = float(np.mean(daily[31:120])); q['dry_mean'] = float(np.mean(daily[212:273]))
q['monthly'] = [float(np.mean(daily[cum[m]:cum[m+1]])) for m in range(12)]
tot = {k: float(np.nansum((v[f'CH4_SURF_{k}'] @ w)[i19])) for k in ['DIFF', 'AERE', 'EBUL']}
q['share'] = {k: x / sum(tot.values()) for k, x in tot.items()}
# tower 2019: daily means from days with >= 12 valid half-hours; monthly from those days
obs = {}
rows = [r for r in TOWER.open() if not r.startswith('#')]
for r in csv.DictReader(rows):
    t = r['TIMESTAMP_START']
    if t[:4] != '2019': continue
    x = float(r['FCH4'])
    if x > -9999:
        k = int(cum[int(t[4:6]) - 1] + int(t[6:8])); obs.setdefault(k, []).append(x)
od = np.array([np.mean(obs[k]) if len(obs.get(k, [])) >= 12 else np.nan for k in range(1, 366)])
ok = np.isfinite(od)
q['tower_days'] = int(ok.sum())
q['model_on_tower_days_mean'] = float(np.mean(daily[ok]))
mo_m, mo_o = [], []
for m in range(12):
    sl = slice(cum[m], cum[m+1]); o = od[sl][ok[sl]]
    if len(o) >= 3: mo_m.append(np.mean(daily[sl][ok[sl]])); mo_o.append(np.mean(o))
q['monthly_r'] = float(np.corrcoef(mo_m, mo_o)[0, 1]); q['monthly_n'] = len(mo_m)
# GPP 2019 from h0 (active pft of each column)
g = []
for m in range(1, 13):
    p = next(d.glob(f'*.clm2.h0.2019-{m:02d}.nc'))
    with nc.Dataset(p) as fh:
        x = np.ma.filled(fh['GPP'][:], 0).reshape(-1); g.append(x[x > 0][:2] @ w * md[m-1] * 86400)
q['gpp_2019_gC'] = float(np.sum(g))
print(json.dumps(q))

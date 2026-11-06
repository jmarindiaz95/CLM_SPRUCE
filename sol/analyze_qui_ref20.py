#!/usr/bin/env python3
"""Task 7: 20-year reference run. Annual area-weighted CH4 stock and emission (convergence: stock gain < 1% of
annual emission), budget residual, and monthly area-weighted emission vs PE-QFR tower FCH4 (AmeriFlux BASE v3-5)."""
from pathlib import Path
import csv, json
import numpy as np
import netCDF4 as nc

root = Path('/work/results/qui_ref20')
tower_csv = Path('/work/inputs/tower/AMF_PE-QFR_BASE_HH_3-5.csv')
parts = ['SAT', 'UNSAT']
w = np.array([.64, .36])
dt = 1800.
mdays = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])

names = ['time', 'FINUNDATED', 'CH4_SURF_NETFLUX']
names += [f'CH4BUD_{k}_{p}' for k in ['STOCK', 'NORM_RES'] for p in parts]
names += [f'CH4_SURF_{k}_{p}' for k in ['NETFLUX', 'DIF', 'AERE', 'EBUL'] for p in parts]
ch = {k: [] for k in names}
for p in sorted(root.glob('*.h1.*.nc')):
    with nc.Dataset(p) as d:
        for k in names:
            ch[k].append(np.ma.filled(d[k][:].astype(float), np.nan))
v = {k: np.concatenate(x) for k, x in ch.items()}
nyr = 20
assert len(v['time']) == nyr*17520 + 1, len(v['time'])

f = v['FINUNDATED']; fr = np.stack([f[1:], 1 - f[1:]], -1)
area = lambda k: (np.stack([v[f'{k}_{p}'][1:] for p in parts], -1) * fr).sum(-1) @ w
I = lambda x: float(np.sum(x) * dt)
stock = ((np.stack([v[f'CH4BUD_STOCK_{p}'] for p in parts], -1) / 12) * np.stack([f, 1 - f], -1)).sum(-1) @ w
tmid = v['time'][1:] - dt/2/86400                      # days since start, step midpoint (noleap)
year = np.floor(tmid/365).astype(int) + 1
doy = tmid - (year - 1)*365
month = np.searchsorted(np.cumsum(mdays), doy, side='right') + 1
em = area('CH4_SURF_NETFLUX')
assert np.max(np.abs(em - v['CH4_SURF_NETFLUX'][1:] @ w)) < 1e-20   # fix_micfin_agg: model field = area-weighted

annual = []
for y in range(1, nyr+1):
    i = np.flatnonzero(year == y)
    e = I(em[i]); s0, s1 = float(stock[i[0]]), float(stock[i[-1]+1])
    annual.append(dict(year=y, forcing_year=2018 + (y-1) % 2, emission_mol_m2=e, emission_gC_m2=12*e,
                       stock_end_mol_m2=s1, stock_gain_mol_m2=s1 - s0, gain_over_emission=(s1 - s0)/e,
                       norm_res_mol_m2=I(area('CH4BUD_NORM_RES')[i]),
                       pathways_mol_m2={k: I(area(f'CH4_SURF_{k}')[i]) for k in ['DIF', 'AERE', 'EBUL']}))
conv = next((a['year'] for a in annual if abs(a['gain_over_emission']) < 0.01), None)

# tower: half-hourly FCH4 nmol m-2 s-1, -9999 missing
tw = {}
with tower_csv.open() as fh:
    rows = [r for r in fh if not r.startswith('#')]
rd = csv.DictReader(rows)
for r in rd:
    t = r['TIMESTAMP_START']; yv, mv = int(t[:4]), int(t[4:6])
    x = float(r['FCH4'])
    tw.setdefault((yv, mv), []).append(np.nan if x <= -9999 else x)
monthly = []
for y, fy in [(nyr-1, 2018), (nyr, 2019)]:
    for m in range(1, 13):
        i = (year == y) & (month == m)
        obs = np.array(tw.get((fy, m), []), float)
        n_ok = int(np.sum(np.isfinite(obs)))
        monthly.append(dict(model_year=y, forcing_year=fy, month=m,
                            model_nmol_m2_s=float(np.mean(em[i]) * 1e9),
                            tower_nmol_m2_s=float(np.nanmean(obs)) if n_ok else None,
                            tower_valid_fraction=n_ok / (mdays[m-1]*48)))
def stats(fy):
    x = [(r['model_nmol_m2_s'], r['tower_nmol_m2_s']) for r in monthly if r['forcing_year'] == fy
         and r['tower_nmol_m2_s'] is not None and r['tower_valid_fraction'] >= 0.1]
    if len(x) < 3:
        return dict(n_months=len(x))
    a, b = np.array(x).T
    return dict(n_months=len(x), model_mean=float(a.mean()), tower_mean=float(b.mean()), ratio=float(a.mean()/b.mean()),
                r=float(np.corrcoef(a, b)[0, 1]), rmse=float(np.sqrt(np.mean((a-b)**2))))
rep = dict(annual=annual, first_year_gain_below_1pct=conv, monthly_last2=monthly,
           tower_comparison={str(fy): stats(fy) for fy in [2018, 2019]},
           total_norm_res_mol_m2=I(area('CH4BUD_NORM_RES')))
(root/'comparison.json').write_text(json.dumps(rep, indent=2) + '\n')
with (root/'annual.csv').open('w', newline='') as fh:
    wr = csv.writer(fh); wr.writerow(['year', 'forcing_year', 'emission_mol_m2', 'emission_gC_m2', 'stock_end_mol_m2',
                                      'stock_gain_mol_m2', 'gain_over_emission', 'norm_res_mol_m2'])
    for a in annual:
        wr.writerow([a[k] for k in ['year', 'forcing_year', 'emission_mol_m2', 'emission_gC_m2', 'stock_end_mol_m2',
                                    'stock_gain_mol_m2', 'gain_over_emission', 'norm_res_mol_m2']])
with (root/'monthly_vs_tower.csv').open('w', newline='') as fh:
    wr = csv.DictWriter(fh, fieldnames=list(monthly[0])); wr.writeheader(); wr.writerows(monthly)
for a in annual:
    print(a['year'], a['forcing_year'], round(a['emission_mol_m2'], 4), round(a['emission_gC_m2'], 2),
          round(a['stock_end_mol_m2'], 4), round(a['gain_over_emission'], 4), f"{a['norm_res_mol_m2']:.1e}")
print('converged year', conv, 'total residual', rep['total_norm_res_mol_m2'])
for r in monthly:
    print(r['forcing_year'], r['month'], round(r['model_nmol_m2_s'], 2), r['tower_nmol_m2_s'] and round(r['tower_nmol_m2_s'], 2),
          round(r['tower_valid_fraction'], 2))
print(json.dumps(rep['tower_comparison'], indent=1))

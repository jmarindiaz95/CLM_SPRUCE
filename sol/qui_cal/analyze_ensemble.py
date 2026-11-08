#!/usr/bin/env python3
"""Summarize a calibration ensemble (design.csv + m*/qoi.json): completion, QoI ranges vs 2019 tower targets,
Spearman rank correlations of each parameter with each QoI, and members closest to the targets.
Usage: analyze_ensemble.py <ensemble dir>"""
import csv, json, sys
from pathlib import Path
import numpy as np

d = Path(sys.argv[1])
T = dict(wet_mean=67.25, dry_mean=28.72, annual_2019_gC=22.0)     # tower 2019 (our file); annual from Griffis 2020
# tower 2019 monthly FCH4 (nmol m-2 s-1), days with >= 12 valid half-hours (sol/diag_qui_cycle.py); Jan-Feb no data
TOWER_MON = np.array([np.nan, np.nan, 59.3, 77.0, 88.4, 55.0, 49.2, 28.6, 28.9, 38.0, 24.5, 45.1])
design = {r['member']: {k: float(v) for k, v in r.items() if k != 'member'} for r in csv.DictReader((d/'design.csv').open())}
pars = list(next(iter(design.values())))
Q = {}
for m in design:
    p = d/m/'qoi.json'
    try:
        Q[m] = json.loads(p.read_text())
    except Exception:
        Q[m] = dict(ok=False)
ok = [m for m in design if Q[m].get('ok') and 'wet_mean' in Q[m]]
print(f'members {len(design)}, completed {len(ok)}')
keys = ['annual_2019_gC', 'wet_mean', 'dry_mean', 'monthly_r', 'gpp_2019_gC', 'res_2015_2019_mol_m2', 'stock_change_2019_mol_m2']
X = np.array([[design[m][p] for p in pars] for m in ok]); Y = {k: np.array([Q[m][k] for m in ok]) for k in keys}
Y['wet_dry'] = Y['wet_mean'] / Y['dry_mean']
for s in ['EBUL', 'AERE', 'DIFF']: Y[f'share_{s}'] = np.array([Q[m]['share'][s] for m in ok])
vm = np.isfinite(TOWER_MON)
MON = np.array([Q[m]['monthly'] for m in ok])
Y['monthly_nrmse'] = np.sqrt(np.mean((MON[:, vm] - TOWER_MON[vm])**2, axis=1)) / np.mean(TOWER_MON[vm])
print('\nQoI range (min / median / max)  [target]')
for k, y in Y.items():
    print(f'  {k:26s} {np.min(y):10.4g} {np.median(y):10.4g} {np.max(y):10.4g}   {T.get(k, "")}')
rank = lambda a: np.argsort(np.argsort(a)).astype(float)
print('\nSpearman rank correlation (parameter vs QoI)')
cols = ['annual_2019_gC', 'wet_mean', 'dry_mean', 'wet_dry', 'monthly_r', 'monthly_nrmse', 'share_EBUL']
print('  ' + ' '.join(f'{c[:10]:>10s}' for c in [''] + cols))
for j, p in enumerate(pars):
    rx = rank(np.log(X[:, j]))
    print(f'  {p[:22]:22s}' + ''.join(f'{np.corrcoef(rx, rank(Y[c]))[0, 1]:11.2f}' for c in cols))
err = np.sqrt(((Y['wet_mean'] - T['wet_mean'])/T['wet_mean'])**2 + ((Y['dry_mean'] - T['dry_mean'])/T['dry_mean'])**2
              + ((Y['annual_2019_gC'] - T['annual_2019_gC'])/T['annual_2019_gC'])**2)
score = np.sqrt(err**2 + Y['monthly_nrmse']**2)    # windows + annual, plus the monthly cycle (Mar-Dec)
for lab, e in [('relative error over wet, dry, annual', err), ('combined: wet, dry, annual + monthly NRMSE', score)]:
    print(f'\nClosest members ({lab})')
    for i in np.argsort(e)[:8]:
        m = ok[i]
        print(f"  {m} err {e[i]:.2f} annual {Y['annual_2019_gC'][i]:.1f} wet {Y['wet_mean'][i]:.1f} dry {Y['dry_mean'][i]:.1f} "
              f"r {Y['monthly_r'][i]:.2f} nrmse {Y['monthly_nrmse'][i]:.2f} gpp {Y['gpp_2019_gC'][i]:.0f} | "
              + ' '.join(f'{p}={design[m][p]:.3g}' for p in pars))
(d/'summary.json').write_text(json.dumps(dict(completed=len(ok), qoi={k: [float(x) for x in y] for k, y in Y.items()},
                                              members=ok), indent=1))

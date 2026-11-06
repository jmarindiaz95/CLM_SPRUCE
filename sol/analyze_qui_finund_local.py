#!/usr/bin/env python3
"""Conservation comparison using instantaneous fraction/stock diagnostics."""
from pathlib import Path
import json
import csv
import hashlib
import numpy as np
import netCDF4 as nc

root = Path('/work/results/qui_finund_repart')
weights = np.array([0.64, 0.36])
dt = 1800.0
controls = ['GPP', 'TOTSOMC', 'TOTVEGC', 'ZWT', 'FINUNDATED', 'CBAL_ERR', 'NBAL_ERR', 'ERRH2O', 'ERRSEB']

def read(files, names):
    chunks = {k: [] for k in names}
    for f in files:
        with nc.Dataset(f) as d:
            for k in names:
                chunks[k].append(np.ma.filled(d[k][:].astype(float), np.nan))
    return {k: np.concatenate(v) for k, v in chunks.items()}

def stats(x):
    assert np.isfinite(x).all()
    return dict(mean=float(x.mean()), mean_abs=float(np.abs(x).mean()),
                max_abs=float(np.abs(x).max()), integrated_mol_m2=float(x.sum()*dt))

report = {'weights': weights.tolist(), 'dt_seconds': dt, 'branches': {}, 'controls': {}}
all_controls = {}
for branch in ['off', 'on']:
    folder = root / branch
    files = sorted(folder.glob('*.h1.*.nc'))
    names = ['time', 'FINUNDATED'] + [f'CH4BUD_{k}_{part}' for k in ['STOCK', 'RESX', 'RES', 'SRC'] for part in ['SAT', 'UNSAT']]
    v = read(files, names)
    assert len(v['time']) == 5*365*48, len(v['time'])
    assert np.allclose(np.diff(v['time'])*86400, dt, rtol=0, atol=0.02)
    f = v['FINUNDATED'][1:]
    fp = v['FINUNDATED'][:-1]
    # RESX stores concentration-stock changes separately for each fraction. The
    # moving-area term is essential: the old stocks occupied the OLD areas.
    fraction_only = f*v['CH4BUD_RESX_SAT'][1:] + (1-f)*v['CH4BUD_RESX_UNSAT'][1:]
    moving_area = (f-fp)*(v['CH4BUD_STOCK_SAT'][:-1]-v['CH4BUD_STOCK_UNSAT'][:-1])/dt
    external = fraction_only + moving_area
    internal = f*v['CH4BUD_RES_SAT'][1:] + (1-f)*v['CH4BUD_RES_UNSAT'][1:]
    weighted = external @ weights
    report['branches'][branch] = {
        'timesteps': len(v['time']), 'external_residual': stats(weighted),
        'external_by_column': [stats(external[:,i]) for i in range(2)],
        'internal_residual': stats(internal @ weights),
        'total_residual': stats((external+internal) @ weights),
        'naive_fraction_only_residual': stats(fraction_only @ weights),
        'fraction_min': v['FINUNDATED'].min(axis=0).tolist(),
        'fraction_max': v['FINUNDATED'].max(axis=0).tolist()}
    with (folder/'residual_annual.csv').open('w') as stream:
        writer = csv.writer(stream)
        writer.writerow(['model_year','mean_external_mol_m2_s','mean_abs_external_mol_m2_s','max_abs_external_mol_m2_s'])
        years = np.floor(v['time'][1:]/365 - 1e-8).astype(int)+1
        for year in np.unique(years):
            s = stats(weighted[years == year])
            writer.writerow([int(year),s['mean'],s['mean_abs'],s['max_abs']])
    monthly = sorted(folder.glob('*.h0.*.nc'))
    all_controls[branch] = read(monthly, ['time']+controls)
    assert len(all_controls[branch]['time']) == 60

np.testing.assert_array_equal(all_controls['off']['time'], all_controls['on']['time'])
for k in controls:
    a,b = all_controls['off'][k], all_controls['on'][k]
    assert np.array_equal(np.isfinite(a),np.isfinite(b))
    diff = b-a
    report['controls'][k] = dict(max_abs_delta=float(np.nanmax(np.abs(diff))),
        off_max_abs=float(np.nanmax(np.abs(a))),on_max_abs=float(np.nanmax(np.abs(b))),
        mean_delta=float(np.nanmean(diff)),
        relative_max_delta=float(np.nanmax(np.abs(diff))/max(np.nanmax(np.abs(a)),1e-30)))
off = report['branches']['off']['external_residual']['mean_abs']
on = report['branches']['on']['external_residual']['mean_abs']
report['external_residual_reduction_factor'] = off/on if on else None
report['target_pass'] = on < 1e-12 and on < off*0.01
(root/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

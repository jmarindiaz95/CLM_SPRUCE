#!/usr/bin/env python3
"""Production sensitivity: per branch, annual emission (yr 1-5), year-4 (2019 forcing) monthly emission and
Feb-Apr / Aug-Sep ratio, pathway shares, CH4 stock, internal residual, and GPP/HR/TOTSOMC/C-N balance (last 12 months)."""
from pathlib import Path
import json
import numpy as np
import netCDF4 as nc

root = Path('/work/results')
cases = {'base': root/'qui_finund_hum_datum/on'} | {k: root/'qui_sens_prod'/k for k in ['ace2', 'ace4', 'kace05', 'ace2_kace05']}
w = np.array([.64, .36]); parts = ['SAT', 'UNSAT']; dt = 1800.
rep = {}
for lab, d in cases.items():
    h0 = sorted(d.glob('*.h0.*.nc'))
    mon = {}
    for p in h0:
        y, m = int(p.name.split('.h0.')[1][:4]), int(p.name.split('.h0.')[1][5:7])
        with nc.Dataset(p) as f:
            g = lambda k: np.ma.filled(f[k][:], np.nan).astype(float).reshape(-1)
            pg = g('GPP')
            mon[(y, m)] = dict(em=float(g('CH4_SURF_NETFLUX')[:2] @ w)*1e9, gpp=float(pg[pg > 0].mean()),
                               hr=float(g('HR')[:2] @ w), som=float(g('TOTSOMC')[:2] @ w),
                               cbal=float(g('CBAL_ERR')[:2] @ w), nbal=float(g('NBAL_ERR')[:2] @ w))
    md = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
    annual = [float(sum(mon[(y, m)]['em']*md[m-1] for m in range(1, 13))*86400*1e-9*12) for y in range(1, 6)]
    y4 = [mon[(4, m)]['em'] for m in range(1, 13)]
    last = [mon[(5, m)] for m in range(1, 13)]
    v = {k: [] for k in ['time', 'FINUNDATED'] + [f'CH4BUD_{a}_{p}' for a in ['NORM_RES', 'STOCK'] for p in parts]
         + [f'CH4_SURF_{a}_{p}' for a in ['DIF', 'AERE', 'EBUL'] for p in parts]}
    for p in sorted(d.glob('*.h1.*.nc')):
        with nc.Dataset(p) as f:
            for k in v: v[k].append(np.ma.filled(f[k][:].astype(float), np.nan))
    v = {k: np.concatenate(x) for k, x in v.items()}
    f_ = v['FINUNDATED']; fr = np.stack([f_[1:], 1 - f_[1:]], -1)
    area = lambda k: (np.stack([v[f'{k}_{p}'][1:] for p in parts], -1) * fr).sum(-1) @ w
    path = {k: float(np.sum(area(f'CH4_SURF_{k}'))) for k in ['DIF', 'AERE', 'EBUL']}
    stock = ((np.stack([v[f'CH4BUD_STOCK_{p}'] for p in parts], -1)/12) * np.stack([f_, 1 - f_], -1)).sum(-1) @ w
    rep[lab] = dict(annual_gC=annual, year4_monthly_nmol=y4, wet_FebApr=float(np.mean(y4[1:4])),
                    dry_AugSep=float(np.mean(y4[7:9])), wet_dry=float(np.mean(y4[1:4])/np.mean(y4[7:9])),
                    pathway_share={k: x/sum(path.values()) for k, x in path.items()},
                    norm_res_mol_m2=float(np.sum(area('CH4BUD_NORM_RES'))*dt),
                    stock_end_mol_m2=float(stock[-1]), stock_gain_yr5_mol_m2=float(stock[-1] - stock[-17521]),
                    last12=dict(gpp=float(np.mean([x['gpp'] for x in last])), hr=float(np.mean([x['hr'] for x in last])),
                                som=float(np.mean([x['som'] for x in last])), cbal=float(np.mean([x['cbal'] for x in last])),
                                nbal=float(np.mean([x['nbal'] for x in last]))))
(root/'qui_sens_prod/comparison.json').write_text(json.dumps(rep, indent=2) + '\n')
for lab, r in rep.items():
    print(f"{lab:12s} yr5 {r['annual_gC'][-1]:5.2f} gC | wet {r['wet_FebApr']:5.1f} dry {r['dry_AugSep']:5.1f} ratio {r['wet_dry']:.2f} | "
          f"paths {' '.join(f'{k}:{x:.2f}' for k, x in r['pathway_share'].items())} | res {r['norm_res_mol_m2']:.1e} | "
          f"stock {r['stock_end_mol_m2']:.2f} (+{r['stock_gain_yr5_mol_m2']:.3f}) | GPP {r['last12']['gpp']:.3e} HR {r['last12']['hr']:.3e} SOM {r['last12']['som']:.0f}")

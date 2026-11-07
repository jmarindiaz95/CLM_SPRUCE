#!/usr/bin/env python3
"""Transient 1980-2020: annual emission (h0, exact area-weighted since fix_micfin_agg) and CO2 check; 2019 evaluation
against PE-QFR FCH4 with Yuan et al. (2023) metrics: daily r, RMSE, SD; wet (DOY 32-120) and dry (DOY 213-273) means;
annual total. Model 2018/2019 from h1 (area-weighted, instantaneous f)."""
from pathlib import Path
import csv, json, sys
import numpy as np
import netCDF4 as nc

root = Path(sys.argv[1] if len(sys.argv) > 1 else '/work/results/qui_trans')
tower_csv = Path('/work/inputs/tower/AMF_PE-QFR_BASE_HH_3-5.csv')
parts, w, dt = ['SAT', 'UNSAT'], np.array([.64, .36]), 1800.
mdays = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])

# h0: annual emission, CO2, GPP, ZWT
h0 = sorted(root.glob('*.h0.*.nc'))
ann = {}
for p in h0:
    y = int(p.name.split('.h0.')[1][:4]); m = int(p.name.split('.h0.')[1][5:7])
    with nc.Dataset(p) as d:
        g = lambda k: np.ma.filled(d[k][:], np.nan).astype(float).reshape(-1)
        a = ann.setdefault(y, dict(em=0., co2=[], gpp=[], zwt=[]))
        a['em'] += float(g('CH4_SURF_NETFLUX')[:2] @ w) * mdays[m-1] * 86400
        a['co2'].append(float(np.nanmean(g('PCO2')[:2])))
        pg = g('GPP'); a['gpp'].append(float(pg[pg > 0].mean()) if np.any(pg > 0) else 0.)
        a['zwt'].append(float(g('ZWT')[:2] @ w))
annual = [dict(year=y, emission_mol_m2=a['em'], emission_gC_m2=12*a['em'], pco2_Pa=float(np.mean(a['co2'])),
               gpp_gC_m2_yr=float(np.mean(a['gpp'])*86400*365), zwt_m=float(np.mean(a['zwt']))) for y, a in sorted(ann.items())]

# h1: half-hourly area-weighted emission for 2018-2019
names = ['time', 'FINUNDATED', 'CH4_SURF_NETFLUX', 'CH4_SURF_DIFF', 'CH4_SURF_AERE', 'CH4_SURF_EBUL'] + [f'CH4_SURF_NETFLUX_{p}' for p in parts] + \
        [f'CH4BUD_NORM_RES_{p}' for p in parts] + [f'CH4BUD_STOCK_{p}' for p in parts] + \
        [f'CH4_SURF_{k}_{p}' for k in ['DIF', 'AERE', 'EBUL'] for p in parts]
ch = {k: [] for k in names}; mcd = []
for p in sorted(root.glob('*.h1.*.nc')):
    with nc.Dataset(p) as d:
        for k in names:
            ch[k].append(np.ma.filled(d[k][:].astype(float), np.nan))
        mcd.append(d['mcdate'][:])
v = {k: np.concatenate(x) for k, x in ch.items()}; mcdate = np.concatenate(mcd)
f = v['FINUNDATED']; fr = np.stack([f, 1 - f], -1)
area = lambda k: (np.stack([v[f'{k}_{p}'] for p in parts], -1) * fr).sum(-1) @ w
em_area = area('CH4_SURF_NETFLUX')
em_rep = v['CH4_SURF_NETFLUX'] @ w           # the model's own field (what OLMT/Yuan report); = em_area only with fix_micfin_agg
reported_equals_area = bool(np.nanmax(np.abs(em_area - em_rep)) < 1e-20)
# instantaneous value at end of each step; assign to the step's start date (mcdate of previous sample)
tend = (v['time'] - dt/2/86400)                       # days since 1980-01-01 (noleap), step midpoint
yr = 1980 + np.floor(tend/365).astype(int); doy = np.floor(tend - (yr-1980)*365).astype(int) + 1
hh = np.floor((tend - np.floor(tend))*48).astype(int)
def tokeys(em):
    return {(int(yr[i]), int(doy[i]), int(hh[i])): em[i]*1e9 for i in range(len(em))}   # nmol m-2 s-1

# tower
obs = {}
rows = [r for r in tower_csv.open() if not r.startswith('#')]
for r in csv.DictReader(rows):
    t = r['TIMESTAMP_START']; y = int(t[:4])
    if y not in (2018, 2019): continue
    mm, dd, H, M = int(t[4:6]), int(t[6:8]), int(t[8:10]), int(t[10:12])
    if mm == 2 and dd == 29: continue
    doy_ = int(np.sum(mdays[:mm-1])) + dd
    x = float(r['FCH4'])
    obs[(y, doy_, H*2 + M//30)] = np.nan if x <= -9999 else x

def evaluate(y, mod):
    days = range(1, 366)
    md = np.array([np.mean([mod[(y, d, h)] for h in range(48) if (y, d, h) in mod]) for d in days])
    od, on = [], []
    for d in days:
        o = np.array([obs.get((y, d, h), np.nan) for h in range(48)]); od.append(np.nanmean(o) if np.isfinite(o).any() else np.nan); on.append(np.isfinite(o).sum())
    od, on = np.array(od), np.array(on)
    ok = on >= 12                                       # days with >= 25% valid half-hours
    paired = []                                         # half-hour pairs: model at the tower's valid times only
    for d in days:
        for h in range(48):
            o = obs.get((y, d, h), np.nan)
            if np.isfinite(o) and (y, d, h) in mod: paired.append((mod[(y, d, h)], o))
    pm, po = np.array(paired).T if paired else (np.array([]), np.array([]))
    doy = np.arange(1, 366)
    wet, dry = (doy >= 32) & (doy <= 120), (doy >= 213) & (doy <= 273)
    out = dict(year=y, model_annual_gC_m2=float(np.mean(md)*1e-9*86400*365*12),
               model_daily_mean=float(md.mean()), model_daily_sd=float(md.std()),
               model_wet_mean=float(md[wet].mean()), model_dry_mean=float(md[dry].mean()))
    if ok.sum() >= 10:
        a, b = md[ok], od[ok]
        out.update(n_days=int(ok.sum()), tower_daily_mean=float(b.mean()), tower_daily_sd=float(b.std()),
                   model_on_tower_days_mean=float(a.mean()), daily_r=float(np.corrcoef(a, b)[0, 1]),
                   daily_rmse=float(np.sqrt(np.mean((a-b)**2))),
                   tower_wet_mean=float(np.mean(od[ok & wet])) if (ok & wet).any() else None,
                   tower_dry_mean=float(np.mean(od[ok & dry])) if (ok & dry).any() else None,
                   model_wet_mean_on_tower_days=float(np.mean(md[ok & wet])) if (ok & wet).any() else None,
                   model_dry_mean_on_tower_days=float(np.mean(md[ok & dry])) if (ok & dry).any() else None,
                   n_halfhours=int(len(pm)), halfhour_model_mean=float(pm.mean()), halfhour_tower_mean=float(po.mean()),
                   tower_annual_gC_from_monthly_means=float(np.nansum([np.nanmean([obs.get((y, dd, h), np.nan)
                       for dd in range(int(np.sum(mdays[:m]))+1, int(np.sum(mdays[:m+1]))+1) for h in range(48)])
                       * mdays[m] for m in range(12)]) * 86400 * 1e-9 * 12)
                       if all(np.isfinite([np.nanmean([obs.get((y, dd, h), np.nan) for dd in range(int(np.sum(mdays[:m]))+1, int(np.sum(mdays[:m+1]))+1) for h in range(48)]) for m in range(12)])) else None)
    return out, md, od, on

shares = {}
for y in (2018, 2019):
    i = yr == y
    tot = {k: float(np.nansum(area(f'CH4_SURF_{k}')[i])) for k in ['DIF', 'AERE', 'EBUL']}
    shares[f'area_weighted_{y}'] = {k: x/sum(tot.values()) for k, x in tot.items()}
    tot = {k: float(np.nansum((v[f'CH4_SURF_{k2}'] @ w)[i])) for k, k2 in [('DIF', 'DIFF'), ('AERE', 'AERE'), ('EBUL', 'EBUL')]}
    shares[f'model_reported_{y}'] = {k: x/sum(tot.values()) for k, x in tot.items()}
ev = {}; daily = []
for lab, em in [('area_weighted', em_area), ('model_reported', em_rep)]:
    mod = tokeys(em)
    for y in (2018, 2019):
        e, md, od, on = evaluate(y, mod); ev[f'{lab}_{y}'] = e
        daily += [dict(series=lab, year=y, doy=d+1, model=float(md[d]), tower=(None if not np.isfinite(od[d]) else float(od[d])),
                       tower_n=int(on[d])) for d in range(365)]
rep = dict(annual=annual, reported_equals_area=reported_equals_area, evaluation=ev, pathway_shares=shares, total_norm_res_2018_2019_mol_m2=float(np.nansum(area('CH4BUD_NORM_RES'))*dt),
           yuan2023_2019=dict(daily_r=0.79, daily_rmse=17.5, model_daily_sd=11.5, obs_daily_sd=19.1, annual_gC=16.04,
                              annual_gC_sd=4.47, wet_mean_obs=71.0, wet_mean_model=50.5, dry_mean_obs=33.5, dry_mean_model=27.7,
                              pathway_share=dict(ebullition=0.470, plant=0.334, diffusion=0.196),
                              source='Yuan et al. 2023 AFM, Section 3 CH4 fluxes and Fig. 5c'),
           griffis2020_annual_gC=dict(value=22, range=[20, 24]))
(root/'comparison.json').write_text(json.dumps(rep, indent=2) + '\n')
with (root/'daily_2018_2019.csv').open('w', newline='') as fh:
    wr = csv.DictWriter(fh, fieldnames=list(daily[0])); wr.writeheader(); wr.writerows(daily)
for a in annual:
    print(a['year'], round(a['emission_gC_m2'], 2), round(a['pco2_Pa'], 2), round(a['gpp_gC_m2_yr']), round(a['zwt_m'], 3))
print(json.dumps(ev, indent=1)); print(shares); print('residual 2018-2019', rep['total_norm_res_2018_2019_mol_m2'])

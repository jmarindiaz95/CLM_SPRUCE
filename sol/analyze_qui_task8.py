#!/usr/bin/env python3
"""Task 8: effect of fix_nppratio (paired off/on): pathways, emission, CH4 stock, budget, prognostic effects."""
from pathlib import Path
import csv, json
import numpy as np
import netCDF4 as nc

root = Path('/work/results/qui_nppratio')
parts = ['SAT', 'UNSAT']
blocks = ['PRE', 'REACT', 'REMOVE', 'CLIP', 'MOVE', 'SURF', 'REPORT', 'OTHER']
w = np.array([.64, .36])          # column weights used by SoilHydrologyMod / the budget
dt = 1800.


def load(folder, names):
    ch = {k: [] for k in names}
    for p in sorted(folder.glob('*.h1.*.nc')):
        with nc.Dataset(p) as d:
            for k in names:
                ch[k].append(np.ma.filled(d[k][:].astype(float), np.nan))
    v = {k: np.concatenate(x) for k, x in ch.items()}
    assert len(v['time']) == 87601
    return v


def diff_files(a, b):
    out = {}
    for tape in ['h0', 'h1']:
        changed, checked = {}, set()
        for pa, pb in zip(sorted(a.glob(f'*.{tape}.*.nc')), sorted(b.glob(f'*.{tape}.*.nc'))):
            with nc.Dataset(pa) as da, nc.Dataset(pb) as db:
                for k in (set(da.variables) & set(db.variables)) - {'date_written', 'time_written'}:
                    x, y = np.ma.filled(da[k][:], np.nan), np.ma.filled(db[k][:], np.nan)
                    if x.dtype.kind not in 'fiu':
                        continue
                    checked.add(k)
                    x, y = x.astype(float), y.astype(float)
                    if not np.array_equal(x, y, equal_nan=True):
                        d = float(np.nanmax(np.abs(x - y)))
                        s = float(np.nanmax(np.abs(x))) or 1.0
                        old = changed.get(k, (0, 0))
                        changed[k] = (max(old[0], d), max(old[1], d / s))
        out[tape] = dict(checked=len(checked), unchanged=len(checked - set(changed)),
                         changed={k: dict(max_abs=v[0], max_rel_to_max=v[1]) for k, v in sorted(changed.items())})
    return out


def monthly(folder, names):
    v = {k: [] for k in names}
    for p in sorted(folder.glob('*.h0.*.nc')):
        with nc.Dataset(p) as d:
            for k in names:
                v[k].append(np.ma.filled(d[k][:].astype(float), np.nan))
    return {k: np.concatenate(x) for k, x in v.items()}


names = ['time', 'FINUNDATED']
names += [f'CH4BUD_{k}_{p}' for k in ['STOCK', 'NORM_RES', 'DDIF', 'DLAT', 'PRE_INIT'] for p in parts]
names += [f'CH4BUD_RES_{b}_{p}' for b in blocks for p in parts]
names += [f'CH4_SURF_{k}_{p}' for k in ['NETFLUX', 'DIF', 'AERE', 'EBUL'] for p in parts]
names += ['CH4_SURF_NETFLUX']
data = {lab: load(root/lab, names) for lab in ['off', 'on']}
rep = {'files_on_vs_off': diff_files(root/'off', root/'on'), 'branches': {}}

for lab, v in data.items():
    f = v['FINUNDATED']
    fr = np.stack([f[1:], 1 - f[1:]], -1)
    area = lambda k: (np.stack([v[f'{k}_{p}'][1:] for p in parts], -1) * fr).sum(-1) @ w
    I = lambda x: float(np.sum(x) * dt)
    stocks = np.stack([v[f'CH4BUD_STOCK_{p}'] for p in parts], -1) / 12
    stock = (stocks * np.stack([f, 1 - f], -1)).sum(-1) @ w
    years = np.floor(v['time'][1:] / 365 - 1e-8).astype(int) + 1
    em = area('CH4_SURF_NETFLUX')
    model = v['CH4_SURF_NETFLUX'][1:] @ w
    b = dict(
        area_weighted_emission_mol_m2=I(em),
        model_CH4_SURF_NETFLUX_mol_m2=I(model),
        model_minus_area_max_abs_mol_m2_s=float(np.max(np.abs(model - em))),
        emission_by_pathway_mol_m2={k: I(area(f'CH4_SURF_{k}')) for k in ['DIF', 'AERE', 'EBUL']},
        normalized_residual_mol_m2=I(area('CH4BUD_NORM_RES')),
        blocks_mol_m2={bl: I(area(f'CH4BUD_RES_{bl}')) for bl in blocks},
        pre_split_mol_m2={k: I(area(f'CH4BUD_{k}')) for k in ['PRE_INIT', 'DDIF', 'DLAT']},
        stock_initial=float(stock[0]), stock_final=float(stock[-1]),
        annual=[dict(year=int(y), emission=I(em[years == y]), model_netflux=I(model[years == y]),
                     stock_end=float(stock[np.flatnonzero(years == y)[-1] + 1])) for y in np.unique(years)])
    # Lateral exchange test: gas_diffusion (DDIF) and lateral_bgc (DLAT) per fraction and column.
    # Vertical diffusion is pairwise within a fraction, so it cannot change a fraction's column stock.
    lat = {}
    for k in ['DDIF', 'DLAT']:
        for p_i, p in enumerate(parts):
            x = v[f'CH4BUD_{k}_{p}'][1:]                 # mol m-2 s-1 per unit area of the fraction
            fx = fr[:, :, p_i]
            lat[f'{k}_{p}'] = dict(
                hardcoded_075_025_sum=I(x @ np.array([.75, .25])),
                hardcoded_075_025_max_abs=float(np.max(np.abs(x @ np.array([.75, .25])))),
                hummock_only=I(x[:, 0]), hollow_only=I(x[:, 1]),
                budget_weighted=I((x * fx) @ w))
    b['lateral_test'] = lat
    f12 = v['FINUNDATED'][1:]
    b['guard_steps'] = dict(sat=int(np.sum(np.minimum(.64*f12[:, 0], .36*f12[:, 1]) < 1e-6)),
                            unsat=int(np.sum(np.minimum(.64*(1-f12[:, 0]), .36*(1-f12[:, 1])) < 1e-6)),
                            total=int(len(f12)))
    rep['branches'][lab] = b

# prognostic effects (monthly means, column-weighted)
keys = ['TOTSOMC', 'TOTVEGC', 'GPP', 'HR', 'NEE', 'CBAL_ERR', 'NBAL_ERR', 'ZWT', 'FINUNDATED', 'DOC_CH4MOD_LOSS',
        'SMINN', 'CH4_SURF_NETFLUX']
mo = {}
for lab in ['off', 'on']:
    with nc.Dataset(next((root/lab).glob('*.h0.*.nc'))) as d:
        avail = [k for k in keys if k in d.variables]
    mo[lab] = monthly(root/lab, avail)
with nc.Dataset(sorted((root/'off').glob('*.h0.*.nc'))[0]) as d:
    pft_idx = np.flatnonzero(np.ma.filled(d['pfts1d_wtgcell'][:], 0) > 0)   # the active pft of each column
    pft_dim = {k: d[k].dimensions[-1] for k in keys if k in d.variables}
assert len(pft_idx) == 2
def colw(x, k):
    if x.ndim == 1:
        return x
    x = x.reshape(x.shape[0], -1)
    return (x[:, pft_idx] if pft_dim[k] == 'pft' else x[:, :2]) @ w
pe = {}
for k in mo['off']:
    a, c = mo['off'][k], mo['on'][k]
    a2, c2 = colw(a, k), colw(c, k)
    pe[k] = dict(off_last12_mean=float(np.mean(a2[-12:])), on_last12_mean=float(np.mean(c2[-12:])),
                 max_abs_monthly_diff=float(np.max(np.abs(c2 - a2))))
rep['monthly_column_weighted'] = pe

# column-integrated tracer profiles (monthly means), per column and weighted 0.64/0.36, last 12 months
prof = ['CDOCS', 'CDONS', 'CACES', 'CCON_O2S', 'CCON_CH4S', 'CCON_CO2S',
        'CDOCS_SAT', 'CDOCS_UNSAT', 'CCON_O2S_SAT', 'CCON_O2S_UNSAT', 'CCON_CH4S_SAT', 'CCON_CH4S_UNSAT']
pr = {}
for lab in ['off', 'on']:
    with nc.Dataset(sorted((root/lab).glob('*.h0.*.nc'))[0]) as d:   # time-constant fields: first file
        dz = np.ma.filled(d['DZSOI'][:], np.nan).astype(float)       # (levgrnd, column)
    m = monthly(root/lab, prof)
    for k, x in m.items():                                          # (month, lev, column)
        nl = x.shape[1]
        colint = np.nansum(x * dz[None, :nl, :], axis=1)            # (month, column)
        pr.setdefault(k, {})[lab] = dict(hummock=float(np.mean(colint[-12:, 0])), hollow=float(np.mean(colint[-12:, 1])),
                                         weighted=float(np.mean(colint[-12:, :2] @ w)),
                                         min_value=float(np.nanmin(x)))
for k, v in pr.items():
    v['rel_change_weighted'] = (v['on']['weighted'] - v['off']['weighted']) / abs(v['off']['weighted']) \
        if v['off']['weighted'] else float('nan')
rep['profiles_colint_last12'] = pr
(root/'comparison.json').write_text(json.dumps(rep, indent=2) + '\n')
print(json.dumps({k: v for k, v in rep.items() if k != 'files_on_vs_off'}, indent=1))
print(json.dumps({t: dict(checked=x['checked'], unchanged=x['unchanged'], changed=list(x['changed']))
                  for t, x in rep['files_on_vs_off'].items()}, indent=1))

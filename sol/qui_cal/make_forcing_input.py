#!/usr/bin/env python3
"""PE-QFR half-hourly forcing input CSV (input to sol/make_qui_forcing.py) for any span of 2018-2022.

Reproduces the assembly of elm_forcing/PE-QFR_forcing_input_2018-2019.csv (README in the Sol forcing directory):
- Met: AmeriFlux FLUXNET v1.3 FLUXMET HH, TA_F, PA_F, WS_F, SW_IN_F, LW_IN_F (+ _QC). RH = 100 (1 - VPD_F / es(TA_F)),
  es = 6.112 exp(17.67 T / (T + 243.5)) hPa. 2020-2021 are ERA5-downscaled in FLUXMET (no tower met).
- Rain: tower gauge rain_mm_interval (analysis_ready_20261004 harmonized file; local end time -> start time).
  A gauge month totalling < 10 mm is treated as a dead gauge (the Jun 2018 - Jan 2019 zeros); missing and dead
  half-hours use FLUXMET P_ERA * 0.26435 (tower/ERA5 ratio of the 2018-2019 assembly).
- With --check, the 2018-2019 rows must match the original CSV (met exact, P within 1e-3 mm, P_SOURCE exact).
Usage: python make_forcing_input.py <EddyCovariance-Analysis dir> <out.csv.gz> [--years 2018 2022] [--check]
"""
import argparse
import numpy as np
import pandas as pd

ERA_SCALE = 0.26435
p = argparse.ArgumentParser()
p.add_argument('base'); p.add_argument('out')
p.add_argument('--years', nargs=2, type=int, default=[2018, 2022])
p.add_argument('--check', action='store_true')
a = p.parse_args()
B = a.base.rstrip('/')

f = pd.read_csv(f'{B}/website/AMF_PE-QFR_FLUXNET_2018-2022_v1.3_r1/AMF_PE-QFR_FLUXNET_FLUXMET_HH_2018-2022_v1.3_r1.csv',
                na_values=[-9999])
f = f[(f.TIMESTAMP_START // 10**8 >= a.years[0]) & (f.TIMESTAMP_START // 10**8 <= a.years[1])].reset_index(drop=True)
assert f[['TA_F', 'VPD_F', 'PA_F', 'WS_F', 'SW_IN_F', 'LW_IN_F', 'P_ERA']].notna().all().all(), 'FLUXMET gaps'

h = pd.read_csv(f'{B}/analysis_ready_20261004/flux_halfhourly_harmonized_2017_2025.csv.gz', low_memory=False,
                usecols=['timestamp_local_end', 'year', 'rain_mm_interval'])
h = h[h.year.between(a.years[0] - 1, a.years[1] + 1)]
ts = (pd.to_datetime(h.timestamp_local_end) - pd.Timedelta('30min')).dt.strftime('%Y%m%d%H%M').astype(np.int64)
assert not ts.duplicated().any(), 'duplicate gauge timestamps'
t = f.TIMESTAMP_START
gauge = pd.Series(h.rain_mm_interval.to_numpy(), index=ts.to_numpy()).reindex(t).to_numpy()
mon = (t // 10**6).to_numpy()
tot = pd.Series(gauge).groupby(mon).sum(min_count=1)
dead = np.isin(mon, tot.index[(tot < 10) | tot.isna()])
use_g = ~np.isnan(gauge) & ~dead

T, V = f.TA_F, f.VPD_F
es = 6.112 * np.exp(17.67 * T / (T + 243.5))
out = pd.DataFrame({'TIMESTAMP_START': t, 'TA': f.TA_F, 'RH': 100 * (1 - V / es), 'PA': f.PA_F, 'WS': f.WS_F,
                    'SW_IN': f.SW_IN_F, 'LW_IN': f.LW_IN_F,
                    'P': np.where(use_g, gauge, ERA_SCALE * f.P_ERA), 'P_SOURCE': np.where(use_g, 'tower', 'era5_scaled'),
                    'TA_QC': f.TA_F_QC, 'SW_QC': f.SW_IN_F_QC, 'WS_QC': f.WS_F_QC})
out.to_csv(a.out, index=False)

yr = t // 10**8
for y in range(a.years[0], a.years[1] + 1):
    m = yr == y
    print(f'{y}: P {out.P[m].sum():.0f} mm ({(out.P_SOURCE[m] == "era5_scaled").mean():.0%} ERA5-filled), '
          f'TA measured {(f.TA_F_QC[m] == 0).mean():.0%}, SW measured {(f.SW_IN_F_QC[m] == 0).mean():.0%}, '
          f'dead-gauge months {sorted(int(v) for v in set(mon[m & dead] % 100))}')

if a.check:
    x = pd.read_csv(f'{B}/elm_forcing/PE-QFR_forcing_input_2018-2019.csv')
    x = x[x.TIMESTAMP_START < 202001010000].reset_index(drop=True)
    o = out[out.TIMESTAMP_START < 202001010000].reset_index(drop=True)
    assert (o.TIMESTAMP_START.to_numpy() == x.TIMESTAMP_START.to_numpy()).all()
    for c in ['TA', 'PA', 'WS', 'SW_IN', 'LW_IN', 'TA_QC', 'SW_QC', 'WS_QC']:
        assert (o[c] == x[c]).all(), c
    assert np.abs(o.RH - x.RH).max() < 1e-10
    assert (o.P_SOURCE == x.P_SOURCE).all()
    dp = np.abs(o.P - x.P).max()
    assert dp < 1e-3, dp
    print(f'check: 2018-2019 rows match the original input (max |dP| {dp:.1e} mm per half-hour)')
print(f'wrote {a.out}: {len(out)} half-hours')

#!/usr/bin/env python3
"""Daily observed QUI water level table (fix_finund_obswl) for the 2020-2022 validation continuation.

Reads WTBL_24 (m above ground, daily) from the ESS-DIVE package QFR_2018_2019_2022_AGGREGATED_*.csv. It equals the
WTD_GAPFILLED_m daily means used for calibration (2018-2019: |diff| <= 6 mm, r 1.000).
- 2022: observed; the 39 missing days (longest 21 days, doy 208-228) are linearly interpolated (ends held).
- 2020-2021: no level record; the 2018/2019 mean daily cycle is used.
- 2023: day 1 only (the last time step of a run ending 2022-12-31 is dated 2023-01-01), the 2022 day-365 value.
Writes 'year doy level_m' for 2020-2023. Usage: python make_obswl_val.py <aggregated.csv> <out.txt>
"""
import sys
import numpy as np
import pandas as pd

d = pd.read_csv(sys.argv[1], na_values=[-9999, '-9999'])
for c in ['YEAR', 'DOY', 'WTBL_24']:
    d[c] = pd.to_numeric(d[c], errors='coerce')
d = d.dropna(subset=['YEAR', 'DOY'])
lev = {int(y): g.set_index(g.DOY.astype(int)).WTBL_24.reindex(range(1, 366)) for y, g in d.groupby('YEAR')}
for y in (2018, 2019):
    assert lev[y].notna().all(), f'{y} has gaps'
clim = (lev[2018] + lev[2019]) / 2
obs = lev[2022]
print(f'2022: {obs.notna().sum()} observed days, {obs.isna().sum()} interpolated')
obs = obs.interpolate(limit_direction='both')
rows = [(2020, clim), (2021, clim), (2022, obs)]
with open(sys.argv[2], 'w') as f:
    for y, s in rows:
        for doy, v in s.items():
            f.write(f'{y} {doy} {v:.4f}\n')
    f.write(f'2023 1 {obs[365]:.4f}\n')
print(f'wrote {sys.argv[2]}: 2020-2021 clim (mean {clim.mean():.4f} m), 2022 obs (mean {obs.mean():.4f} m), 2023 day 1')

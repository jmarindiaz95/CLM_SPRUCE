#!/usr/bin/env python3
"""Half-hourly CLM1PT forcing for PE-QFR (2x1pt) from the AmeriFlux BASE file, with ERA5 precipitation gap fill.

Usage:
  python3 sol/make_qui_forcing.py AMF_PE-QFR_BASE_HH_<ver>.csv [--era5 era5_tp.nc] [--years 2018 2019]
         [--out inputdata/atm/datm7/CLM1PT_data/2x1pt_PE-QFR] [--utc-offset -5]

Follows Yuan et al. (2023): tower air temperature, humidity, shortwave, wind, pressure and
precipitation, with hourly ERA5 total precipitation filling precipitation gaps.
- AmeriFlux timestamps are local standard time (Peru UTC-5); the model clock is UTC, so data are shifted.
- Short gaps (<= 2 h) are interpolated; longer gaps use the mean diurnal cycle of a +-15 day window.
- Shortwave gaps are first filled from PPFD_IN / 2.04 when PPFD is present.
- Incoming longwave uses LW_IN when present; otherwise (and for its gaps) Brutsaert clear-sky
  emissivity corrected with a daily cloud fraction from shortwave clearness (Crawford & Duchon 1999 form).
- Precipitation gaps use ERA5 (hourly, metres of water, split evenly into two half-hours); without
  --era5 they are set to 0 and reported.
Writes one netCDF per month (YYYY-MM.nc, noleap, 48 steps per day), same layout as the US-SPR files,
and gapfill_report.txt.
"""
import argparse, os, sys
import numpy as np
import pandas as pd
import netCDF4 as nc

LAT, LON = -3.834417, 360.0 - 73.318917
LONS = [LON - 0.05, LON + 0.05]           # stream points (US-SPR files sit 0.05 deg west of each gridcell centre)
ZBOT = 40.0                               # m, tower measurement height (Griffis et al. 2020)
SOLAR = 1361.0

p = argparse.ArgumentParser()
p.add_argument('csv')
p.add_argument('--era5', default=None, help='ERA5 single-level hourly total precipitation (tp, m) netCDF or CSV with time,tp')
p.add_argument('--years', nargs=2, type=int, default=[2018, 2019])
p.add_argument('--out', default='inputdata/atm/datm7/CLM1PT_data/2x1pt_PE-QFR')
p.add_argument('--utc-offset', type=float, default=-5.0)
a = p.parse_args()

# ---------------------------------------------------------------- read AmeriFlux BASE
raw = pd.read_csv(a.csv, comment='#', na_values=[-9999, '-9999'], low_memory=False)
t_loc = pd.to_datetime(raw['TIMESTAMP_START'].astype(str), format='%Y%m%d%H%M')
t_utc = t_loc - pd.Timedelta(hours=a.utc_offset)


def pick(prefix):
    """First column for a variable: exact name, then _F, then _1_1_1-style replicates (mean of replicates)."""
    cols = [c for c in raw.columns if c == prefix or c.startswith(prefix + '_')]
    cols = [c for c in cols if not c.startswith(prefix + '_PI') and 'QC' not in c and 'SSITC' not in c]
    if not cols:
        return None, []
    if prefix in cols:
        return raw[prefix].to_numpy(float), [prefix]
    return raw[cols].mean(axis=1, skipna=True).to_numpy(float), cols


series, used = {}, {}
for v in ['TA', 'RH', 'PA', 'WS', 'SW_IN', 'LW_IN', 'P', 'PPFD_IN']:
    x, cols = pick(v)
    if x is not None:
        series[v] = pd.Series(x, index=t_utc).sort_index()
        series[v] = series[v][~series[v].index.duplicated()]
        used[v] = cols

for need in ['TA', 'RH', 'WS', 'SW_IN', 'P']:
    if need not in series:
        sys.exit(f'ERROR: {need} not found in {a.csv}. Columns: {list(raw.columns)[:40]} ...')

idx = pd.date_range(f'{a.years[0]}-01-01 00:00', f'{a.years[1]}-12-31 23:30', freq='30min')
idx = idx[~((idx.month == 2) & (idx.day == 29))]          # noleap calendar
df = pd.DataFrame({k: s.reindex(idx) for k, s in series.items()}, index=idx)

# plausibility screens
df.loc[(df.TA < 10) | (df.TA > 45), 'TA'] = np.nan
df.loc[(df.RH < 5) | (df.RH > 105), 'RH'] = np.nan
df['RH'] = df['RH'].clip(upper=100)
df.loc[(df.WS < 0) | (df.WS > 30), 'WS'] = np.nan
df.loc[(df.SW_IN < -20) | (df.SW_IN > 1400), 'SW_IN'] = np.nan
df['SW_IN'] = df['SW_IN'].clip(lower=0)
df.loc[(df.P < 0) | (df.P > 150), 'P'] = np.nan
if 'PA' in df: df.loc[(df.PA < 90) | (df.PA > 105), 'PA'] = np.nan
if 'LW_IN' in df: df.loc[(df.LW_IN < 250) | (df.LW_IN > 550), 'LW_IN'] = np.nan

report = [f'source: {a.csv}', f'columns used: {used}', f'period (UTC): {idx[0]} to {idx[-1]}, {len(idx)} half-hours', '']
gap0 = {k: float(df[k].isna().mean()) for k in df.columns}

# ---------------------------------------------------------------- solar geometry (for longwave clouds)
doy = idx.dayofyear.to_numpy(); hr = idx.hour.to_numpy() + idx.minute.to_numpy() / 60 + 0.25
decl = np.deg2rad(23.44) * np.sin(2 * np.pi * (284 + doy) / 365)
solar_time = hr + (LON - 360.0) / 15.0
ha = np.deg2rad(15 * (solar_time - 12))
cosz = np.sin(np.deg2rad(LAT)) * np.sin(decl) + np.cos(np.deg2rad(LAT)) * np.cos(decl) * np.cos(ha)
sw_pot = np.maximum(SOLAR * cosz, 0)


def fill(s, maxint=4):
    s = s.copy()
    s = s.interpolate(limit=maxint, limit_area='inside')
    if s.isna().any():
        hh = s.index.hour * 2 + s.index.minute // 30
        clim = s.groupby([s.index.dayofyear // 1, hh]).mean()
        out = s.copy()
        dayk = s.index.dayofyear.to_numpy()
        for i in np.where(s.isna().to_numpy())[0]:
            d0, h0 = dayk[i], hh[i]
            w = [((d0 - 1 + k) % 365) + 1 for k in range(-15, 16)]
            vals = [clim.get((d, h0), np.nan) for d in w]
            out.iloc[i] = np.nanmean(vals) if np.isfinite(vals).any() else np.nan
        s = out
        if s.isna().any():
            s = s.fillna(s.groupby(s.index.hour * 2 + s.index.minute // 30).transform('mean'))
    return s


if 'PPFD_IN' in df:
    m = df.SW_IN.isna() & df.PPFD_IN.notna()
    df.loc[m, 'SW_IN'] = (df.PPFD_IN[m] / 2.04).clip(lower=0)
for v in ['TA', 'RH', 'WS', 'SW_IN'] + (['PA'] if 'PA' in df else []):
    df[v] = fill(df[v])
df['SW_IN'] = np.minimum(df['SW_IN'], np.maximum(sw_pot, 0) * 1.1 + 20)
if 'PA' not in df:
    df['PA'] = 99.6
    report.append('PA not in file: constant 99.6 kPa')

# humidity
es = 611.2 * np.exp(17.67 * df.TA / (df.TA + 243.5))
e = df.RH / 100 * es
psrf = df.PA * 1000
q = 0.622 * e / (psrf - 0.378 * e)
tk = df.TA + 273.15

# longwave
day = idx.floor('D')
kt = pd.Series(df.SW_IN.to_numpy(), index=idx).groupby(day).transform('sum') / \
     pd.Series(sw_pot, index=idx).groupby(day).transform('sum')
cloud = (1 - kt.clip(0, 1)).to_numpy()
eps_clear = 1.24 * (e / 100 / tk) ** (1 / 7)
lw_model = (cloud + (1 - cloud) * eps_clear) * 5.670374e-8 * tk ** 4
if 'LW_IN' in df:
    lw = df.LW_IN.interpolate(limit=4, limit_area='inside')
    n_mod = int(lw.isna().sum()); lw = lw.fillna(lw_model)
    report.append(f'LW_IN: tower, {n_mod} half-hours from Brutsaert + cloud model')
else:
    lw = lw_model
    report.append('LW_IN not in file: Brutsaert clear-sky emissivity with daily cloud fraction from SW clearness')

# precipitation
prec = df.P.copy()                      # mm per half-hour
n_pgap = int(prec.isna().sum())
if a.era5:
    if a.era5.endswith('.nc'):
        d = nc.Dataset(a.era5)
        tv = [v for v in ['valid_time', 'time'] if v in d.variables][0]
        tt = pd.to_datetime(nc.num2date(d[tv][:], d[tv].units, only_use_cftime_datetimes=False, only_use_python_datetimes=True))
        tp = np.array(d['tp'][:]).reshape(len(tt), -1)
        la = np.array(d[[v for v in ['latitude', 'lat'] if v in d.variables][0]][:])
        lo = np.array(d[[v for v in ['longitude', 'lon'] if v in d.variables][0]][:]) % 360
        if tp.shape[1] > 1:
            ii = np.argmin(abs(la - LAT)); jj = np.argmin(abs(lo - LON))
            tp = np.array(d['tp'][:])[:, ii, jj] if np.array(d['tp'][:]).ndim == 3 else tp[:, 0]
        else:
            tp = tp[:, 0]
        era = pd.Series(tp * 1000.0, index=tt)          # mm per hour, accumulation ending at the timestamp
    else:
        e5 = pd.read_csv(a.era5, parse_dates=['time'])
        era = pd.Series(e5['tp'].to_numpy() * 1000.0, index=e5['time'])
    era = era[~era.index.duplicated()].sort_index()
    # hour ending at T -> half-hours starting T-60 and T-30 min
    hh = pd.concat([pd.Series(era.to_numpy() / 2, index=era.index - pd.Timedelta('60min')),
                    pd.Series(era.to_numpy() / 2, index=era.index - pd.Timedelta('30min'))]).sort_index()
    hh = hh[~hh.index.duplicated()].reindex(idx)
    filled = prec.isna() & hh.notna()
    prec[filled] = hh[filled]
    report.append(f'P: {n_pgap} half-hour gaps, {int(filled.sum())} filled from ERA5, {int(prec.isna().sum())} set to 0')
    both = df.P.notna() & hh.notna()
    if both.sum() > 1000:
        report.append(f'   tower vs ERA5 over common half-hours: tower {df.P[both].sum():.0f} mm, ERA5 {hh[both].sum():.0f} mm')
else:
    report.append(f'P: {n_pgap} half-hour gaps set to 0 (no --era5 given)')
prec = prec.fillna(0.0)

report.append('')
report.append('initial gap fraction: ' + ', '.join(f'{k} {v:.1%}' for k, v in gap0.items()))
for y in range(a.years[0], a.years[1] + 1):
    m = idx.year == y
    report.append(f'{y}: P {prec[m].sum():.0f} mm, mean TA {df.TA[m].mean():.2f} C, SW {df.SW_IN[m].mean():.1f} W/m2, '
                  f'LW {np.nanmean(lw[m]):.1f} W/m2, RH {df.RH[m].mean():.1f} %, WS {df.WS[m].mean():.2f} m/s')

# ---------------------------------------------------------------- write monthly CLM1PT files
os.makedirs(a.out, exist_ok=True)
out = pd.DataFrame({'TBOT': tk, 'QBOT': q, 'PSRF': psrf, 'WIND': df.WS, 'FSDS': df.SW_IN,
                    'FLDS': np.asarray(lw), 'PRECTmms': prec / 1800.0, 'ZBOT': ZBOT}, index=idx)
meta = {'QBOT': ('kg/kg', 'specific humidity at the lowest atm level (QBOT)'),
        'PRECTmms': ('kg/m2/s', 'precipitation (PRECTmms)'), 'ZBOT': ('m', 'observational height'),
        'FSDS': ('W/m2', 'incident solar (FSDS)'), 'FLDS': ('W/m2', 'incident longwave (FLDS)'),
        'TBOT': ('K', 'temperature at the lowest atm level (TBOT)'), 'WIND': ('m/s', 'wind at the lowest atm level (WIND)'),
        'PSRF': ('Pa', 'pressure at the lowest atm level (PSRF)')}
for (y, mo), g in out.groupby([out.index.year, out.index.month]):
    f = nc.Dataset(f'{a.out}/{y:04d}-{mo:02d}.nc', 'w', format='NETCDF3_CLASSIC')
    f.createDimension('lon', 2); f.createDimension('lat', 1); f.createDimension('scalar', 1); f.createDimension('time', len(g))
    for v, (u, ln) in meta.items():
        x = f.createVariable(v, 'f4', ('time', 'lat', 'lon')); x.units = u; x.long_name = ln; x.mode = 'time-dependent'
        x[:] = np.repeat(g[v].to_numpy(np.float32)[:, None, None], 2, axis=2)
    t = f.createVariable('time', 'f8', ('time',)); t.units = f'days since {y:04d}-{mo:02d}-01 00:00:00'
    t.long_name = 'Time axis'; t.calendar = 'noleap'; t[:] = np.arange(len(g)) / 48.0
    x = f.createVariable('LONGXY', 'f8', ('lon',)); x.units = 'degrees E'; x.long_name = 'longitude'; x[:] = LONS
    x = f.createVariable('LATIXY', 'f8', ('lat',)); x.units = 'degrees N'; x.long_name = 'latitude'; x[:] = [LAT]
    for v, val, u, ln in [('EDGEE', LON + 0.1, 'degrees E', 'eastern edge in atmospheric data'),
                          ('EDGEW', LON - 0.1, 'degrees E', 'western edge in atmospheric data'),
                          ('EDGEN', LAT + 0.05, 'degrees N', 'northern edge in atmospheric data'),
                          ('EDGES', LAT - 0.05, 'degrees N', 'southern edge in atmospheric data')]:
        x = f.createVariable(v, 'f8', ('scalar',)); x.units = u; x.long_name = ln; x[:] = val
    for v, val in [('start_year', a.years[0]), ('end_year', a.years[1])]:
        x = f.createVariable(v, 'i4', ('scalar',)); x[:] = val
    f.close()

open(f'{a.out}/gapfill_report.txt', 'w').write('\n'.join(report) + '\n')
print('\n'.join(report))
print(f'wrote {len(out.groupby([out.index.year, out.index.month]))} monthly files to {a.out}')

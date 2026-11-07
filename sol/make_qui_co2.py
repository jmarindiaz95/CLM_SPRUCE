#!/usr/bin/env python3
"""CO2 stream file 1765-2021 for the QUI transient: fco2_datm_1765-2007_c100614.nc (CMIP5 global mean, runs to
mid-2009) + NOAA GML Mauna Loa annual means for 2010-2021 (co2_annmean_mlo.txt, file creation 2026-10-09) minus the
2007-2009 mean offset MLO - file, so the series is continuous."""
import numpy as np, netCDF4 as nc
src = '/work/CLM_SPRUCE/inputdata/atm/datm7/CO2/fco2_datm_1765-2007_c100614.nc'
dst = '/work/inputs/co2/fco2_datm_1765-2021_qui_c20261106.nc'
mlo = {2007: 384.02, 2008: 385.83, 2009: 387.64, 2010: 390.10, 2011: 391.85, 2012: 394.06, 2013: 396.74,
       2014: 398.81, 2015: 401.01, 2016: 404.41, 2017: 406.76, 2018: 408.72, 2019: 411.65, 2020: 414.21, 2021: 416.41}
s = nc.Dataset(src)
t = s['time'][:]; c = s['CO2'][:, 0, 0]; yr = np.round(1765 + t/365. - 0.5).astype(int)
assert yr[-1] == 2009
off = np.mean([mlo[y] - c[yr == y][0] for y in (2007, 2008, 2009)])
new_y = np.arange(2010, 2022)
d = nc.Dataset(dst, 'w', format='NETCDF3_CLASSIC')
for k, v in s.dimensions.items():
    d.createDimension(k, None if v.isunlimited() else (len(t) + len(new_y) if k == 'time' else len(v)))
for k, v in s.variables.items():
    o = d.createVariable(k, v.dtype, v.dimensions)
    o.setncatts({a: v.getncattr(a) for a in v.ncattrs()})
    x = v[:]
    if 'time' in v.dimensions:
        if k == 'time':
            ext = t[-1] + 365.*(new_y - 2009)
        elif k == 'CO2':
            ext = (np.array([mlo[y] for y in new_y]) - off).reshape(-1, 1, 1)
        elif k == 'date':
            ext = np.array([y*10000 + 701 for y in new_y])
        else:
            raise SystemExit(k)
        x = np.concatenate([x, ext.astype(v.dtype)])
    o[:] = x
d.setncatts({**{a: s.getncattr(a) for a in s.ncattrs()},
             'history_qui': f'Extended 2010-2021 with NOAA GML MLO annual mean minus {off:.3f} ppm (2007-2009 offset); make_qui_co2.py'})
d.close()
print('offset', off); print({int(y): float(v) for y, v in zip(new_y, np.array([mlo[y] for y in new_y]) - off)})

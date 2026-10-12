#!/usr/bin/env python3
"""Static PE-QFR (Quistococha) inputs for ELM-SPRUCE, built from the US-SPR 2x1pt templates.

Run from the repository root:  python3 sol/make_qui_static.py
Writes into inputdata/ (same layout as the US-SPR files):
  surfdata_2x1pt_PE-QFR.nc, domain.lnd.2x1pt_PE-QFR_navy.nc (share/ and datm7/ copies),
  ndep, aerosol, population density and lightning streams relabelled to the site,
  clm_params_qui.nc (Yuan et al. 2023 Table 1 optimized values on PFT 4) and microbepar_in_qui.

Assumptions (see docs): two gridcells kept for the HUM_HOL hummock/hollow build; 100% PFT 4
(broadleaf evergreen tropical tree); peat (organic 130 kg/m3) to 2.3 m and 65 kg/m3 in the last
layer; mineral fraction 10% sand / 50% clay; ndep, aerosol, population and lightning values kept
from US-SPR (placeholders, coordinates changed only).
"""
import os, shutil
import numpy as np
import netCDF4 as nc

LAT, LON = -3.834417, 360.0 - 73.318917          # 3 50'03.9" S, 73 19'08.1" W
DLON = 0.1                                       # second gridcell offset (as in the US-SPR file)
IN = 'inputdata'
SITE_OLD, SITE = 'US-SPR', 'PE-QFR'


def clone(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    return nc.Dataset(dst, 'a')


# ---------------------------------------------------------------- surface data
d = clone(f'{IN}/lnd/clm2/surfdata_map/surfdata_2x1pt_{SITE_OLD}.nc',
          f'{IN}/lnd/clm2/surfdata_map/surfdata_2x1pt_{SITE}.nc')
d['LATIXY'][:] = LAT
d['LONGXY'][0, :] = [LON, LON + DLON]
pct = np.zeros(d['PCT_PFT'].shape); pct[4] = 100.0
d['PCT_PFT'][:] = pct
for v in ['PCT_WETLAND', 'PCT_LAKE', 'PCT_GLACIER']:
    d[v][:] = 0.0
d['PCT_URBAN'][:] = 0.0
org = np.full(d['ORGANIC'].shape, 130.0); org[-1] = 65.0
d['ORGANIC'][:] = org
d['PCT_SAND'][:] = 10.0
d['PCT_CLAY'][:] = 50.0
d['TOPO'][:] = 105.0                          # m a.s.l., Iquitos lowland
d['STD_ELEV'][:] = 2.0
d['SLOPE'][:] = 0.1
# prescribed (SP-mode) phenology for PFT 4, not used by CN but keep it sensible
lai = d['MONTHLY_LAI'][:]; lai[:, 4] = 4.5; d['MONTHLY_LAI'][:] = lai
sai = d['MONTHLY_SAI'][:]; sai[:, 4] = 1.0; d['MONTHLY_SAI'][:] = sai
ht = d['MONTHLY_HEIGHT_TOP'][:]; ht[:, 4] = 21.3; d['MONTHLY_HEIGHT_TOP'][:] = ht
hb = d['MONTHLY_HEIGHT_BOT'][:]; hb[:, 4] = 10.0; d['MONTHLY_HEIGHT_BOT'][:] = hb
d.history = 'PE-QFR site file cloned from surfdata_2x1pt_US-SPR.nc by sol/make_qui_static.py'
d.close()

# ---------------------------------------------------------------- domain (two copies, as for US-SPR)
for sub in ['share/domains/domain.clm', 'atm/datm7/domain.clm']:
    d = clone(f'{IN}/{sub}/domain.lnd.2x1pt_{SITE_OLD}_navy.nc', f'{IN}/{sub}/domain.lnd.2x1pt_{SITE}_navy.nc')
    xc_old = np.array(d['xc'][0, :]); yc_old = np.array(d['yc'][0, :])
    xc = np.array([LON, LON + DLON])
    d['xv'][0, :, :] = np.array(d['xv'][0, :, :]) - xc_old[:, None] + xc[:, None]   # shift template vertices
    d['yv'][0, :, :] = np.array(d['yv'][0, :, :]) - yc_old[:, None] + LAT
    d['xc'][0, :] = xc; d['yc'][:] = LAT
    d.history = 'PE-QFR domain cloned from US-SPR by sol/make_qui_static.py'
    d.close()

# ---------------------------------------------------------------- deposition and fire streams (coordinates only)
streams = [
    ('lnd/clm2/ndepdata/fndep_clm_hist_simyr1849-2006_2x1pt_{s}.nc', 'latlon2'),
    ('atm/cam/chem/trop_mozart_aero/aero/aerosoldep_monthly_1849-2006_2x1pt_{s}.nc', 'latlon2'),
    ('lnd/clm2/firedata/clmforc.Li_2012_hdm_1x1pt_{s}_AVHRR_simyr1850-2010_c130401.nc', 'global'),
    ('atm/datm7/NASA_LIS/clmforc.Li_2012_climo1995-2011.1x1pt_{s}.lnfm_c130327.nc', 'global'),
]
for pat, kind in streams:
    d = clone(f'{IN}/' + pat.format(s=SITE_OLD), f'{IN}/' + pat.format(s=SITE))
    if kind == 'latlon2':
        d['lat'][:] = [LAT - 0.0005, LAT + 0.0005]
        d['lon'][:] = LON - 0.105   # same offset as the US-SPR file; a source lon equal to the gridcell lon gives dx=dy=0 in shr_map_getWts
    else:
        # keep the template's offset from the US-SPR gridcell (an exact match gives dx=dy=0 in shr_map_getWts)
        for v in ['lat', 'LAT', 'LATIXY']:
            if v in d.variables: d[v][:] = LAT + (float(np.array(d[v][:]).ravel()[0]) - 47.563)
        for v in ['lon', 'LON', 'LONGXY']:
            if v in d.variables:
                x0 = float(np.array(d[v][:]).ravel()[0]); x0e = x0 % 360.0
                d[v][:] = (LON + (x0e - 266.562)) - (360.0 if x0 < 0 else 0.0)
    d.history = 'PE-QFR placeholder: values from US-SPR, coordinates changed (sol/make_qui_static.py)'
    d.close()

# ---------------------------------------------------------------- PFT parameters: Yuan et al. 2023 Table 1 (optimized)
d = clone(f'{IN}/lnd/clm2/paramdata/clm_params_spruce_calveg.nc', f'{IN}/lnd/clm2/paramdata/clm_params_qui.nc')
P = 4  # broadleaf_evergreen_tropical_tree
pft_opt = {'dleaf': 0.04, 'fcur': 1.0, 'flnr': 0.1135, 'froot_leaf': 2.5, 'frootcn': 42.0,
           'leaf_long': 1.78, 'mp': 7.0, 'slatop': 0.012, 'k_dom': 0.025}
for v, val in pft_opt.items():
    a = d[v][:]; a[P] = val; d[v][:] = a
glob_opt = {'br_mr': 1.50e-6, 'q10_mr': 1.3, 'r_mort': 0.05}
for v, val in glob_opt.items():
    d[v][:] = val
# not applied: bdnr (Table 1 optimum equals its own default; file value is a different scale),
# livewdcn (Table 1 value 0.763 is outside its own 25-75 range; file keeps 50)
d.history = 'clm_params_spruce_calveg.nc with Yuan et al. (2023) Table 1 optimized values on PFT 4 (sol/make_qui_static.py)'
d.close()

# ---------------------------------------------------------------- microbial parameters: Table 1 (optimized)
mic_opt = {'m_dAceProdACmax': 1.0e-7, 'm_dACMinQ10': 3.0, 'm_dGrowRAceMethanogens': 0.008,
           'm_dH2ProdAcemax': 5.0e-8, 'm_dYAceMethanogens': 0.162, 'm_dKCH4OxidCH4': 1.0,
           'm_dPlantTrans': 0.014}
src = f'{IN}/lnd/clm2/paramdata/microbepar_in'
out = []
seen = set()
for line in open(src):
    parts = line.split()
    if parts and parts[0] in mic_opt:
        out.append(f'{parts[0]}\t{mic_opt[parts[0]]:.6g}\n'); seen.add(parts[0])
    else:
        out.append(line)
missing = set(mic_opt) - seen
assert not missing, missing
open(f'{IN}/lnd/clm2/paramdata/microbepar_in_qui', 'w').writelines(out)
print('done')

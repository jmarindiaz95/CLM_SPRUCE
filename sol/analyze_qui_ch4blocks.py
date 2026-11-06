#!/usr/bin/env python3
"""Verify diagnostic invariance and integrate the non-overlapping CH4 residual blocks."""
from pathlib import Path
import json
import csv
import hashlib
import numpy as np
import netCDF4 as nc

root=Path('/work/results/qui_ch4bud_blocks')
baseline=Path('/work/results/qui_finund_repart/on')
blocks=['PRE','REACT','REMOVE','CLIP','MOVE','SURF','REPORT','OTHER']
parts=['SAT','UNSAT']
weights=np.array([0.64,0.36])
dt=1800.0

def load(folder,tape,names):
    chunks={k:[] for k in names}
    for path in sorted(folder.glob(f'*.{tape}.*.nc')):
        with nc.Dataset(path) as d:
            for k in names:
                chunks[k].append(np.ma.filled(d[k][:].astype(float),np.nan))
    return {k:np.concatenate(v,axis=0) for k,v in chunks.items()}

names=['time','FINUNDATED']+[f'CH4BUD_{k}_{p}' for k in ['RES','NORM_RES','RES_UNITS','SRC'] for p in parts]+[f'CH4BUD_RES_{b}_{p}' for b in blocks for p in parts]
v=load(root,'h1',names)
assert len(v['time'])==87601
assert np.allclose(np.diff(v['time'])*86400,dt,atol=0.02,rtol=0)
f=v['FINUNDATED'][1:]
fraction=np.stack([f,1-f],axis=-1)
years=np.floor(v['time'][1:]/365-1e-8).astype(int)+1
report={'records':len(v['time']),'intervals':len(v['time'])-1,'dt_seconds':dt,
        'weights':weights.tolist(),'blocks':{},'closure':{},'invariance':{}}
total_by_part=np.stack([v[f'CH4BUD_NORM_RES_{p}'][1:] for p in parts],axis=-1)
legacy=np.stack([v[f'CH4BUD_RES_{p}'][1:] for p in parts],axis=-1)
unit_gap=np.stack([v[f'CH4BUD_RES_UNITS_{p}'][1:] for p in parts],axis=-1)
reported=np.stack([v[f'CH4BUD_SRC_{p}'][1:] for p in parts],axis=-1)
np.testing.assert_allclose(total_by_part,(legacy+reported)/12-reported,rtol=1e-11,atol=1e-15)
summed=np.zeros_like(total_by_part)
rows=[]
for block in blocks:
    x=np.stack([v[f'CH4BUD_RES_{block}_{p}'][1:] for p in parts],axis=-1)
    assert np.isfinite(x).all()
    summed+=x
    by_part=(x*fraction*weights[None,:,None]).sum(axis=(0,1))*dt
    by_column=(x*fraction).sum(axis=(0,2))*weights*dt
    weighted=(x*fraction).sum(axis=-1)@weights
    report['blocks'][block]={'integrated_mol_m2':float(weighted.sum()*dt),
        'sat_mol_m2':float(by_part[0]),'unsat_mol_m2':float(by_part[1]),
        'hummock_mol_m2':float(by_column[0]),'hollow_mol_m2':float(by_column[1]),
        'mean_mol_m2_s':float(weighted.mean()),'mean_abs_mol_m2_s':float(np.abs(weighted).mean()),
        'max_abs_mol_m2_s':float(np.abs(weighted).max())}
    for year in np.unique(years):
        rows.append([block,int(year),float(weighted[years==year].sum()*dt)])
delta=summed-total_by_part
report['closure']={'max_abs_fraction_error_mol_m2_s':float(np.abs(delta).max()),
    'total_integrated_mol_m2':float(((total_by_part*fraction).sum(axis=-1)@weights).sum()*dt),
    'sum_blocks_integrated_mol_m2':sum(x['integrated_mol_m2'] for x in report['blocks'].values()),
    'legacy_mixed_unit_integral':float(((legacy*fraction).sum(axis=-1)@weights).sum()*dt),
    'unit_mismatch_integral':float(((unit_gap*fraction).sum(axis=-1)@weights).sum()*dt),
    'max_legacy_reconstruction_error':float(np.max(np.abs(summed+unit_gap-legacy)))}
assert report['closure']['max_abs_fraction_error_mol_m2_s']<1e-12
assert report['closure']['max_legacy_reconstruction_error']<1e-12

# Compare every pre-existing history variable, except wall-clock writing timestamps.
# Missing-value masks must also match. Scientific fields and timestep counters are included.
for tape in ['h0','h1']:
    original=sorted(baseline.glob(f'*.{tape}.*.nc'))
    current=sorted(root.glob(f'*.{tape}.*.nc'))
    assert len(original)==len(current)
    checked=set(); changed={}
    for a,b in zip(original,current):
        with nc.Dataset(a) as da,nc.Dataset(b) as db:
            common=set(da.variables)&set(db.variables)-{'date_written','time_written'}
            for key in common:
                va,vb=da[key],db[key]
                assert va.dimensions==vb.dimensions, key
                aa,bb=va[:],vb[:]
                assert aa.shape==bb.shape, key
                np.testing.assert_array_equal(np.ma.getmaskarray(aa),np.ma.getmaskarray(bb),err_msg=key)
                checked.add(key)
                avalues=np.ma.getdata(aa); bvalues=np.ma.getdata(bb)
                valid=~np.ma.getmaskarray(aa)
                if avalues.dtype.kind in 'fiu':
                    if not np.array_equal(avalues[valid],bvalues[valid],equal_nan=True):
                        difference=float(np.nanmax(np.abs(avalues[valid]-bvalues[valid])))
                        changed[key]=max(changed.get(key,0),difference)
                        np.testing.assert_allclose(avalues[valid],bvalues[valid],rtol=1e-12,atol=1e-14,err_msg=key)
                else:
                    np.testing.assert_array_equal(avalues[valid],bvalues[valid],err_msg=key)
    report['invariance'][tape]={'common_variables_checked':len(checked),'files_checked':len(original),
        'bitwise_equal_values':not changed,'changed_variables_max_abs':changed}

with (root/'contributions.csv').open('w',newline='') as stream:
    writer=csv.writer(stream)
    writer.writerow(['block','integrated_mol_m2','sat_mol_m2','unsat_mol_m2','hummock_mol_m2','hollow_mol_m2'])
    for b,x in report['blocks'].items():
        writer.writerow([b]+[x[k] for k in ['integrated_mol_m2','sat_mol_m2','unsat_mol_m2','hummock_mol_m2','hollow_mol_m2']])
with (root/'contributions_annual.csv').open('w',newline='') as stream:
    writer=csv.writer(stream); writer.writerow(['block','model_year','integrated_mol_m2']); writer.writerows(rows)
(root/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

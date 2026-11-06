#!/usr/bin/env python3
"""Verify baseline preservation, surface routing, and unchanged prognostic behavior."""
from pathlib import Path
import csv
import json
import re
import numpy as np
import netCDF4 as nc

root=Path('/work/results/qui_unsat_surf')
baseline=Path('/work/results/qui_ch4bud_task4')
parts=['SAT','UNSAT']
blocks=['PRE','REACT','REMOVE','CLIP','MOVE','SURF','REPORT','OTHER']
weights=np.array([.64,.36])
dt=1800.

def load(folder,names):
    chunks={k:[] for k in names}
    for path in sorted(folder.glob('*.h1.*.nc')):
        with nc.Dataset(path) as d:
            for k in names:
                chunks[k].append(np.ma.filled(d[k][:].astype(float),np.nan))
    v={k:np.concatenate(x) for k,x in chunks.items()}
    assert len(v['time'])==87601
    np.testing.assert_allclose(np.diff(v['time'])*86400,dt,atol=.02,rtol=0)
    return v

def compare(a,b,allowed):
    result={}
    for tape in ['h0','h1']:
        aa=sorted(a.glob(f'*.{tape}.*.nc'));bb=sorted(b.glob(f'*.{tape}.*.nc'))
        assert len(aa)==len(bb)
        checked=set();changed={}
        for pa,pb in zip(aa,bb):
            with nc.Dataset(pa) as da,nc.Dataset(pb) as db:
                for key in (set(da.variables)&set(db.variables))-{'date_written','time_written'}:
                    assert da[key].dimensions==db[key].dimensions,key
                    x,y=da[key][:],db[key][:]
                    np.testing.assert_array_equal(np.ma.getmaskarray(x),np.ma.getmaskarray(y),err_msg=key)
                    mask=~np.ma.getmaskarray(x)
                    x,y=np.ma.getdata(x)[mask],np.ma.getdata(y)[mask]
                    checked.add(key)
                    if x.dtype.kind in 'fiu':
                        if not np.array_equal(x,y,equal_nan=True):
                            changed[key]=max(changed.get(key,0),float(np.max(np.abs(x-y))))
                            assert key in allowed,f'Unexpected changed field: {key}'
                    else:
                        np.testing.assert_array_equal(x,y,err_msg=key)
        result[tape]={'common_variables_checked':len(checked),'files_checked':len(aa),
                      'unchanged_variables':len(checked-set(changed)),
                      'changed_variables_max_abs':changed}
    return result

allowed={f'CH4_SURF_{kind}{suffix}' for kind in ['AERE','EBUL','NETFLUX'] for suffix in ['','_UNSAT']}
allowed|={f'CH4BUD_{kind}_UNSAT' for kind in ['SRC','SRC_LEGACY','RES','NORM_RES','RES_UNITS','RES_REPORT']}
report={'default_off_vs_task4':compare(baseline,root/'off',set()),
        'on_vs_off':compare(root/'off',root/'on',allowed),'branches':{},'checks':{}}
names=['time','FINUNDATED','CH4_AERE_DEPTH_UNSAT','CH4_EBUL_DEPTH_UNSAT']
names += [f'CH4BUD_{k}_{p}' for k in ['STOCK','RESX','NORM_RES'] for p in parts]
names += [f'CH4BUD_RES_{b}_{p}' for b in blocks for p in parts]
names += [f'CH4_SURF_{k}_{p}' for k in ['NETFLUX','DIF','AERE','EBUL'] for p in parts]
names += ['CH4_SURF_NETFLUX','CH4_SURF_DIFF','CH4_SURF_AERE','CH4_SURF_EBUL']
data={label:load(root/label,names) for label in ['off','on']}
off,on=data['off'],data['on']
np.testing.assert_array_equal(off['time'],on['time'])
np.testing.assert_array_equal(off['FINUNDATED'],on['FINUNDATED'])
years=np.floor(on['time'][1:]/365-1e-8).astype(int)+1
fractions=np.stack([on['FINUNDATED'][1:],1-on['FINUNDATED'][1:]],axis=-1)

def area(v,k):
    x=np.stack([v[f'{k}_{p}'][1:] for p in parts],axis=-1)
    return (x*fractions).sum(axis=-1)@weights

def integral(x):
    return float(np.sum(x)*dt)

annual=[]
for label,v in data.items():
    f=v['FINUNDATED']
    stocks=np.stack([v[f'CH4BUD_STOCK_{p}'] for p in parts],axis=-1)/12
    stock=(stocks*np.stack([f,1-f],axis=-1)).sum(axis=-1)@weights
    block_arrays={b:area(v,f'CH4BUD_RES_{b}') for b in blocks}
    total=area(v,'CH4BUD_NORM_RES')
    per_part_sum=sum(np.stack([v[f'CH4BUD_RES_{b}_{p}'][1:] for p in parts],axis=-1) for b in blocks)
    per_part_total=np.stack([v[f'CH4BUD_NORM_RES_{p}'][1:] for p in parts],axis=-1)
    closure=float(np.max(np.abs(per_part_sum-per_part_total)))
    assert closure<2e-18
    emission={k:area(v,f'CH4_SURF_{k}') for k in ['NETFLUX','DIF','AERE','EBUL']}
    np.testing.assert_allclose(emission['NETFLUX'],emission['DIF']+emission['AERE']+emission['EBUL'],rtol=1e-12,atol=1e-20)
    # External repartition needs the moving-area term, with all stocks in molar units.
    resx=np.stack([v[f'CH4BUD_RESX_{p}'][1:]/12 for p in parts],axis=-1)
    external=(resx*fractions).sum(axis=-1)+(f[1:]-f[:-1])*(stocks[:-1,:,0]-stocks[:-1,:,1])/dt
    external=external@weights
    report['branches'][label]={'blocks_mol_m2':{b:integral(x) for b,x in block_arrays.items()},
        'normalized_residual_mol_m2':integral(total),'max_block_closure_error_mol_m2_s':closure,
        'emissions_mol_m2':{k:integral(x) for k,x in emission.items()},
        'model_aggregated_emissions_mol_m2':{k:integral(v[f'CH4_SURF_{field}'][1:]@weights) for k,field in [('NETFLUX','NETFLUX'),('DIF','DIFF'),('AERE','AERE'),('EBUL','EBUL')]},
        'stock_initial_mol_m2':float(stock[0]),'stock_final_mol_m2':float(stock[-1]),
        'stock_gain_mol_m2':float(stock[-1]-stock[0]),
        'external_residual_integral_mol_m2':integral(external),
        'external_residual_max_abs_mol_m2_s':float(np.max(np.abs(external)))}
    for year in np.unique(years):
        select=years==year;i=np.flatnonzero(select)
        row={'branch':label,'model_year':int(year),'stock_mean_mol_m2':float(stock[1:][select].mean()),
             'stock_end_mol_m2':float(stock[i[-1]+1]),'normalized_residual_mol_m2':integral(total[select])}
        row.update({f'{k.lower()}_mol_m2':integral(x[select]) for k,x in emission.items()})
        row.update({f'block_{b.lower()}_mol_m2':integral(x[select]) for b,x in block_arrays.items()})
        annual.append(row)

# Independent depth-to-surface check uses the runtime soil layer thicknesses.
log=next((root/'on').glob('lnd.log.*')).read_text(errors='replace')
line=next(x for x in log.splitlines() if 'dzsoi:' in x)
dz=np.fromstring(line.split('dzsoi:',1)[1],sep=' ')
assert len(dz)==15
report['soil_layer_thickness_m']=dz.tolist()
for kind in ['AERE','EBUL']:
    depth=on[f'CH4_{kind}_DEPTH_UNSAT'][1:]
    # History dimensions: time, levgrnd, column. No inactive-layer transport.
    assert np.max(np.abs(depth[:,10:,:]))==0
    integrated=np.sum(depth*dz[None,:,None],axis=1)
    surface=on[f'CH4_SURF_{kind}_UNSAT'][1:]
    error=float(np.max(np.abs(integrated-surface)))
    np.testing.assert_allclose(surface,integrated,rtol=1e-12,atol=1e-20)
    report['checks'][f'{kind.lower()}_depth_to_surface_max_error_mol_m2_s']=error
    np.testing.assert_array_equal(on[f'CH4_{kind}_DEPTH_UNSAT'],off[f'CH4_{kind}_DEPTH_UNSAT'])

surface_delta=on['CH4_SURF_NETFLUX_UNSAT'][1:]-off['CH4_SURF_NETFLUX_UNSAT'][1:]
old_report=off['CH4BUD_RES_REPORT_UNSAT'][1:]
np.testing.assert_allclose(surface_delta,-old_report,rtol=1e-11,atol=2e-18)
np.testing.assert_allclose(on['CH4BUD_RES_REPORT_UNSAT'][1:],0,atol=2e-18,rtol=0)
np.testing.assert_allclose(on['CH4BUD_NORM_RES_UNSAT'][1:]-off['CH4BUD_NORM_RES_UNSAT'][1:],surface_delta,rtol=1e-11,atol=2e-18)
report['checks']['surface_delta_equals_omitted_flux_max_error_mol_m2_s']=float(np.max(np.abs(surface_delta+old_report)))
report['checks']['on_report_max_abs_mol_m2_s']=float(np.max(np.abs(on['CH4BUD_RES_REPORT_UNSAT'][1:])))
report['emission_change_mol_m2']={k:report['branches']['on']['emissions_mol_m2'][k]-report['branches']['off']['emissions_mol_m2'][k] for k in ['NETFLUX','DIF','AERE','EBUL']}
report['emission_change_percent']=100*report['emission_change_mol_m2']['NETFLUX']/report['branches']['off']['emissions_mol_m2']['NETFLUX']
report['target_pass']=True
with (root/'annual.csv').open('w',newline='') as stream:
    w=csv.DictWriter(stream,fieldnames=list(annual[0]));w.writeheader();w.writerows(annual)
(root/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

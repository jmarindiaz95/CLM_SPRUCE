#!/usr/bin/env python3
"""Verify diagnostic invariance and integrate the non-overlapping CH4 residual blocks."""
from pathlib import Path
import json
import csv
import hashlib
import numpy as np
import netCDF4 as nc

root=Path('/work/results/qui_ch4bud_task4')
baseline=Path('/work/results/qui_ch4bud_blocks')
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

names=['time','FINUNDATED']+[f'CH4BUD_{k}_{p}' for k in ['STOCK','SRC_LEGACY','PRE_INIT','DDIF','DLAT'] for p in parts]+[f'CH4_SURF_{k}_{p}' for k in ['NETFLUX','DIF','AERE','EBUL'] for p in parts]+['CH4_SURF_NETFLUX','CH4_SURF_DIFF','CH4_SURF_AERE','CH4_SURF_EBUL']+[f'CH4BUD_{k}_{p}' for k in ['RES','NORM_RES','RES_UNITS','SRC'] for p in parts]+[f'CH4BUD_RES_{b}_{p}' for b in blocks for p in parts]
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

expected_changes={f'CH4BUD_{k}_{p}' for k in ['SRC','RES','NORM_RES','RES_REACT','RES_UNITS'] for p in parts}

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
                        assert key in expected_changes, f'Unexpected changed output: {key}'
                else:
                    np.testing.assert_array_equal(avalues[valid],bvalues[valid],err_msg=key)
    report['invariance'][tape]={'common_variables_checked':len(checked),'files_checked':len(original),
        'bitwise_equal_except_expected_diagnostics':set(changed)<=expected_changes,'changed_variables_max_abs':changed}

# Independently check the reporting correction against the unmodified diagnostic replay.
old=load(baseline,'h1',[f'CH4BUD_{k}_{p}' for k in ['SRC','NORM_RES','RES_REACT'] for p in parts])
report['reporting_correction']={}
for p in parts:
    np.testing.assert_array_equal(v[f'CH4BUD_SRC_LEGACY_{p}'],old[f'CH4BUD_SRC_{p}'])
    actual=v[f'CH4BUD_NORM_RES_{p}'][1:]
    expected=old[f'CH4BUD_NORM_RES_{p}'][1:]-old[f'CH4BUD_RES_REACT_{p}'][1:]
    np.testing.assert_allclose(actual,expected,atol=2e-18,rtol=1e-10)
    report['reporting_correction'][p]={'max_expected_correction_error':float(np.max(np.abs(actual-expected)))}

# PRE is a telescoping stock difference: before diffusion + diffusion + lateral exchange.
pre_parts={}
pre_sum=np.zeros_like(total_by_part)
for block in ['PRE_INIT','DDIF','DLAT']:
    x=np.stack([v[f'CH4BUD_{block}_{p}'][1:] for p in parts],axis=-1)
    pre_sum+=x
    weighted=(x*fraction).sum(axis=-1)@weights
    pre_parts[block]={'integrated_mol_m2':float(weighted.sum()*dt),
        'sat_mol_m2':float((x[:,:,0]*f@weights).sum()*dt),
        'unsat_mol_m2':float((x[:,:,1]*(1-f)@weights).sum()*dt)}
pre=np.stack([v[f'CH4BUD_RES_PRE_{p}'][1:] for p in parts],axis=-1)
np.testing.assert_allclose(pre_sum,pre,atol=2e-18,rtol=1e-10)
report['pre_split']=pre_parts
report['pre_split_max_error']=float(np.max(np.abs(pre_sum-pre)))

# Integrate instantaneous fluxes with instantaneous inundation fraction: no monthly mean products.
flux={}
model_flux={}
aggregation_errors={}
mapping={'NETFLUX':'NETFLUX','DIF':'DIFF','AERE':'AERE','EBUL':'EBUL'}
for pathway,model_name in mapping.items():
    x=np.stack([v[f'CH4_SURF_{pathway}_{p}'][1:] for p in parts],axis=-1)
    flux[pathway]=(x*fraction).sum(axis=-1)@weights
    model_flux[pathway]=v[f'CH4_SURF_{model_name}'][1:]@weights
    # Existing surface aggregation retains micfinundated from the bottom layer.
    # Save its observed difference from true area weighting without changing it.
    # The original unsuffixed Fortran literal 0.99 is first rounded to real32.
    surface_fraction=float(np.float32(0.99))
    fixed_099=(surface_fraction*x[:,:,0]+(1-surface_fraction)*x[:,:,1])@weights
    aggregation_errors[pathway]=float(np.max(np.abs(model_flux[pathway]-fixed_099)))
np.testing.assert_allclose(flux['NETFLUX'],flux['DIF']+flux['AERE']+flux['EBUL'],atol=1e-20,rtol=1e-12)
np.testing.assert_allclose(model_flux['NETFLUX'],model_flux['DIF']+model_flux['AERE']+model_flux['EBUL'],atol=1e-20,rtol=1e-12)
report['emissions_mol_m2']={k:float(x.sum()*dt) for k,x in flux.items()}
report['model_aggregated_emissions_mol_m2']={k:float(x.sum()*dt) for k,x in model_flux.items()}
report['model_aggregation_max_error_vs_099_mol_m2_s']=aggregation_errors
report['existing_surface_saturated_fraction']=surface_fraction
stock=np.stack([v[f'CH4BUD_STOCK_{p}'] for p in parts],axis=-1)/12
all_f=v['FINUNDATED']
stock_weighted=(stock*np.stack([all_f,1-all_f],axis=-1)).sum(axis=-1)@weights
assert np.isfinite(stock_weighted).all()
report['stock_mol_m2']={'initial':float(stock_weighted[0]),'final':float(stock_weighted[-1]),
                       'change':float(stock_weighted[-1]-stock_weighted[0])}
annual=[]
for year in np.unique(years):
    select=years==year
    i=np.flatnonzero(select)
    row={'model_year':int(year),'stock_start_mol_m2':float(stock_weighted[i[0]]),
         'stock_end_mol_m2':float(stock_weighted[i[-1]+1]),
         'stock_mean_mol_m2':float(stock_weighted[1:][select].mean())}
    row.update({f'{k.lower()}_mol_m2':float(x[select].sum()*dt) for k,x in flux.items()})
    row.update({f'model_{k.lower()}_mol_m2':float(x[select].sum()*dt) for k,x in model_flux.items()})
    annual.append(row)
report['annual']=annual
with (root/'emissions_stocks_annual.csv').open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(annual[0]));writer.writeheader();writer.writerows(annual)
emission=report['emissions_mol_m2']['NETFLUX']
report['relative_scale']={'report_fraction_of_emission':report['blocks']['REPORT']['integrated_mol_m2']/emission,
    'normalized_residual_fraction_of_emission':report['closure']['total_integrated_mol_m2']/emission,
    'stock_gain_fraction_of_emission':report['stock_mol_m2']['change']/emission,
    'model_aggregation_relative_difference':report['model_aggregated_emissions_mol_m2']['NETFLUX']/emission-1,
    'report_magnitude_over_plant_plus_ebullition':abs(report['blocks']['REPORT']['integrated_mol_m2'])/(report['emissions_mol_m2']['AERE']+report['emissions_mol_m2']['EBUL'])}

# New total fields are exact aliases of existing ACE fields. The new ACETO fields
# subtract H2 and HCH4 at the process assignment; HCH4 is identically zero here.
pathway_errors={}
for path in sorted(root.glob('*.h0.*.nc')):
    with nc.Dataset(path) as d:
        for suffix in ['', '_SAT', '_UNSAT']:
            total=d[f'CH4_PROD_TOT_DEPTH{suffix}'][:]
            legacy_total=d[f'CH4_PROD_ACE_DEPTH{suffix}'][:]
            aceto=d[f'CH4_PROD_ACETO_DEPTH{suffix}'][:]
            h2=d[f'CH4_PROD_CO2_DEPTH{suffix}'][:]
            np.testing.assert_array_equal(total,legacy_total)
            np.testing.assert_array_equal(np.ma.getmaskarray(aceto),np.ma.getmaskarray(total))
            np.testing.assert_allclose(aceto+h2,total,atol=1e-20,rtol=1e-12)
            pathway_errors[suffix or 'COMBINED']=max(pathway_errors.get(suffix or 'COMBINED',0),float(np.ma.max(np.abs(aceto+h2-total))))
report['production_pathway_max_error_mol_m3_s']=pathway_errors

with (root/'contributions.csv').open('w',newline='') as stream:
    writer=csv.writer(stream)
    writer.writerow(['block','integrated_mol_m2','sat_mol_m2','unsat_mol_m2','hummock_mol_m2','hollow_mol_m2'])
    for b,x in report['blocks'].items():
        writer.writerow([b]+[x[k] for k in ['integrated_mol_m2','sat_mol_m2','unsat_mol_m2','hummock_mol_m2','hollow_mol_m2']])
with (root/'contributions_annual.csv').open('w',newline='') as stream:
    writer=csv.writer(stream); writer.writerow(['block','model_year','integrated_mol_m2']); writer.writerows(rows)
(root/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

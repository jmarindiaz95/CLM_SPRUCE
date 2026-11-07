#!/usr/bin/env python3
"""Transient (Yuan et al. 2023 phase 3): 1980-2020 from the end of the 50-year final spinup (qui_final50).
Time-varying CO2 (datm co2diag stream, CCSM_BGC=CO2A, CLM_CO2_TYPE=diagnostic; inputs/co2 file from make_qui_co2.py)
and N deposition (fndep 1849-2006, held at 2006 afterwards by the stream's taxmode 'extend').
Tower forcing 2018-2019 cycled, aligned so model years 2018 and 2019 use the real 2018 and 2019 forcing."""
from pathlib import Path
import os, re, runpy, shutil, subprocess


VARIANT = os.environ.get('QUI_VARIANT', 'fix')        # 'fix': accepted switches on; 'pub': all fix switches 0 (published code)
SWITCHES = ['fix_dom_n', 'fix_co2_dt', 'fix_ch4_unsat', 'fix_finund_repart', 'fix_unsat_surf', 'fix_micfin_agg', 'fix_lat_weights']
def variant_params(params):
    if VARIANT in ('fix', 'npp', 'yuan'):
        for sw in SWITCHES[2:]:
            assert re.search(rb'^' + sw.encode() + rb'\s+1\s*$', params, re.M), sw
        assert not re.search(rb'^fix_nppratio\s', params, re.M)
        extra = {'fix': b'', 'npp': b'\nfix_nppratio\t1', 'yuan': b'\nfix_nppratio\t1\nfix_finund_ponded\t1\nfix_finund_rates\t1\nfix_finund_hum_datum\t1'}[VARIANT]
        return params if VARIANT == 'fix' else params.rstrip(b'\n') + extra + b'\n'
    for sw in SWITCHES:
        params, n = re.subn(rb'^' + sw.encode() + rb'\s+1\s*$', sw.encode() + b'\t0', params, flags=re.M)
        assert n == 1, sw
    return params
name = 'qui_trans' + {'fix': '', 'pub': '_pub', 'npp': '_npp', 'yuan': '_yuan'}[VARIANT]
os.environ['CH4REPORT_CASE'] = name
runpy.run_path('/work/CLM_SPRUCE/sol/setup_qui_task4.py', run_name='__main__')
case = Path('/work/cases')/name
run = Path('/work/runs')/name
co2file = Path('/work/inputs/co2/fco2_datm_1765-2021_qui_c20261106.nc')
assert co2file.exists()
p = case/'user_nl_clm'
t = p.read_text().rstrip()+",\n 'CH4_AERE_DEPTH_UNSAT', 'CH4_EBUL_DEPTH_UNSAT'\n"
sfx = {'fix': '', 'pub': '_pub', 'npp': '_npp', 'yuan': '_yuan'}[VARIANT]
fin = f'/work/runs/qui_final50{sfx}/qui_final50{sfx}.clm2.r.0051-01-01-00000.nc'
t, n1 = re.subn(r"^ finidat = .*$", f" finidat = '{fin}'", t, flags=re.M)
t, n2 = re.subn(r"^ spinup_state = 1$", " spinup_state = 0", t, flags=re.M)
assert n1 == 1 and n2 == 1
t += " stream_year_first_ndep = 1849\n stream_year_last_ndep = 2006\n model_year_align_ndep = 1849\n"
p.write_text(t)
for x in ['RUN_STARTDATE=1980-01-01', 'STOP_OPTION=nyears,STOP_N=41,REST_OPTION=nyears,REST_N=5',
          'DATM_CLMNCEP_YR_ALIGN=1980', 'CCSM_BGC=CO2A', 'CLM_CO2_TYPE=diagnostic']:
    subprocess.run(['./xmlchange', x], cwd=case, check=True)
(case/'user_nl_datm').write_text(
    " taxmode = 'cycle','cycle','extend'\n"
    " dtlimit = 1.5,1.5,1.5\n fillalgo = 'nn','nn','nn'\n fillmask = 'nomask','nomask','nomask'\n"
    " mapalgo = 'nn','nn','nn'\n mapmask = 'nomask','nomask','nomask'\n tintalgo = 'nearest','linear','linear'\n"
    ' streams = "datm.streams.txt.CLM1PT.CLM_USRDAT 1980 2018 2019", "datm.streams.txt.presaero.clim_1850 1 1 1",'
    ' "datm.global1val.streams.co2.txt 1765 1765 2021"\n')
# CO2 stream description (OLMT method): CLM UsersGuide template pointed at the spliced file
s = Path('/work/CLM_SPRUCE/models/lnd/clm/doc/UsersGuide/co2_streams.txt').read_text()
s = s.replace('/fis/cgd/cseg/csm/inputdata/atm/datm7/CO2', str(co2file.parent))
s = s.replace('fco2_datm_1765-2007_c100614.nc', co2file.name)
assert s.count(str(co2file.parent)) == 2 and s.count(co2file.name) == 2, s
(case/'datm.global1val.streams.co2.txt').write_text(s)
params = variant_params(Path('/work/results/qui_ref20/microbepar_in').read_bytes())
(case/'microbepar_in').write_bytes(params)
subprocess.run(['./preview_namelists'], cwd=case, check=True)
with (case/'build_out.txt').open('w') as log:
    subprocess.run([f'./{name}.build'], cwd=case, stdout=log, stderr=subprocess.STDOUT, check=True)
for d in [case/'Buildconf/datmconf', run]:
    shutil.copy2(case/'datm.global1val.streams.co2.txt', d/'datm.global1val.streams.co2.txt')
print(open(run/'datm_atm_in').read()); print([l for l in open(run/'lnd_in') if re.search('co2|ndep|spinup_state|finidat', l)])
print([l for l in open(run/'drv_in') if 'co2' in l.lower()])

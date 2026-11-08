#!/usr/bin/env python3
"""Create calibration members (ranges: pilot | revised | obswl) from the built template run directory (runs/qui_cal_tmpl): Latin hypercube over the
parameters below, per-member microbepar_in, lnd_in (finund_k, finund_min, fpftcon -> member copy with k_dom) and
namelists; writes design.csv and a Slurm array script.  Usage: make_members.py <set> <n> <seed> [pilot|revised|obswl]
'obswl': revised ranges with finund_min 0.15-0.60, template/executable qui_cal_exud (has fix_finund_obswl and
root_exud_frac), fix_finund_obswl 1 and ./finund_obswl.txt (sol/qui_cal/make_obswl.py) in every member; root_exud_frac off."""
import csv, re, shutil, sys
from pathlib import Path
import numpy as np
import netCDF4 as nc

W = Path('/scratch/jmarindi/elm_work')
TMPL = W/'runs/qui_cal_tmpl'
EXE = W/'builds/qui_cal_tmpl/cesm.exe'
PFT = 4                                    # tropical broadleaf evergreen (active pft at QUI)
# name, kind (microbe | lnd | kdom), low, high, log
PARAMS = [('m_dAceProdACmax', 'microbe', 2e-8, 2e-6, True), ('m_dKAce', 'microbe', 4., 64., True),
          ('m_dYAceMethanogens', 'microbe', 0.037, 0.3, False), ('m_dGrowRAceMethanogens', 'microbe', 0.004, 0.1, True),
          ('m_dH2ProdAcemax', 'microbe', 5e-9, 5e-7, True), ('m_dPlantTrans', 'microbe', 0.002, 0.2, True),
          ('m_dCH4min', 'microbe', 0.01, 0.2, True), ('m_dKCH4OxidCH4', 'microbe', 0.0025, 1.5, True),
          ('k_dom', 'kdom', 0.006, 0.0375, False), ('finund_k', 'lnd', 100., 400., False),
          ('finund_min', 'lnd', 0.3, 0.6, False)]

# Main-ensemble ranges (approved 2026-11-07 after the pilot): oxidation half-saturation extended above Yuan's 1.5,
# water-coverage floor below Yuan's 0.45, production and CH4 threshold narrowed.
REVISED = {'m_dKCH4OxidCH4': (0.1, 3.0, True), 'finund_min': (0.10, 0.45, False),
           'm_dAceProdACmax': (5e-8, 1e-6, True), 'm_dCH4min': (0.01, 0.1, True)}
# Observed-water-level ensemble (2026-11-07): the low floor of the main ensemble compensated for a model water table
# 5-10 cm too low (results/qui_finund_obswl); with the observed level the floor range returns to bracket Yuan's 0.45.
OBSWL = dict(REVISED, finund_min=(0.15, 0.60, False))
OBSWL_TMPL, OBSWL_EXE = W/'runs/qui_cal_exud', W/'builds/qui_cal_exud/cesm.exe'
OBSWL_TABLE = W/'qui_cal/obswl/finund_obswl.txt'

def lhs(n, k, rng):
    u = (np.argsort(rng.random((n, k)), axis=0) + rng.random((n, k))) / n
    return u

def main(setname, n, seed, ranges='pilot'):
    global PARAMS, TMPL, EXE
    if ranges in ('revised', 'obswl'):
        R = REVISED if ranges == 'revised' else OBSWL
        PARAMS = [(pn, kind) + R.get(pn, (lo, hi, lg)) for pn, kind, lo, hi, lg in PARAMS]
    if ranges == 'obswl':
        TMPL, EXE = OBSWL_TMPL, OBSWL_EXE
        assert OBSWL_TABLE.exists() and len(OBSWL_TABLE.read_text().splitlines()) == 6 * 365
    out = W/'qui_cal'/setname
    out.mkdir(parents=True)
    assert EXE.exists() and (TMPL/'lnd_in').exists() and (TMPL/'datm.global1val.streams.co2.txt').exists()
    rng = np.random.default_rng(seed)
    u = lhs(n, len(PARAMS), rng)
    rows = []
    mp0 = (TMPL/'microbepar_in').read_text()
    lnd0 = (TMPL/'lnd_in').read_text()
    fp0 = Path(re.search(r"fpftcon\s*=\s*'([^']+)'", lnd0).group(1))
    for i in range(n):
        name = f'm{i+1:03d}'
        d = out/name
        (d/'timing/checkpoints').mkdir(parents=True)
        for p in TMPL.iterdir():
            if p.is_file() and (p.name.endswith('_in') or p.name.endswith('.nml') or p.name.startswith('datm.')
                                or p.name == 'seq_maps.rc'):
                (d/p.name).write_text(p.read_text().replace(str(TMPL), str(d)))
        vals = {}
        for j, (pn, kind, lo, hi, lg) in enumerate(PARAMS):
            vals[pn] = float(np.exp(np.log(lo) + u[i, j]*(np.log(hi) - np.log(lo)))) if lg else float(lo + u[i, j]*(hi - lo))
        mp, lnd = mp0, (d/'lnd_in').read_text()
        for pn, kind, *_ in PARAMS:
            if kind == 'microbe':
                mp, k = re.subn(r'^(' + pn + r')([ \t]+)([0-9.eE+-]+)', lambda m: m.group(1) + m.group(2) + repr(vals[pn]), mp, flags=re.M)
                assert k == 1, pn
            elif kind == 'lnd':
                lnd, k = re.subn(r'^(\s*' + pn + r'\s*=\s*)[0-9.eE+-]+', lambda m: m.group(1) + repr(vals[pn]), lnd, flags=re.M)
                assert k == 1, pn
        shutil.copy2(fp0, d/'clm_params_member.nc')
        with nc.Dataset(d/'clm_params_member.nc', 'a') as f:
            f['k_dom'][PFT] = vals['k_dom']
        lnd, k = re.subn(r"(fpftcon\s*=\s*')[^']+'", lambda m: m.group(1) + str(d/'clm_params_member.nc') + "'", lnd)
        assert k == 1
        if ranges == 'obswl':
            assert 'fix_finund_obswl' not in mp and 'root_exud_frac' not in mp
            mp = mp.rstrip('\n') + '\nfix_finund_obswl\t1\n'
            shutil.copy2(OBSWL_TABLE, d/'finund_obswl.txt')
        (d/'microbepar_in').write_text(mp); (d/'lnd_in').write_text(lnd)
        rows.append(dict(member=name, **vals))
    with (out/'design.csv').open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (out/'run_array.sh').write_text(f"""#!/bin/bash
#SBATCH --job-name=qcal_{setname}
#SBATCH -p public
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --mem=3G
#SBATCH -t 01:00:00
#SBATCH --array=1-{n}%50
#SBATCH -o {out}/slurm.%A_%a.out
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export LD_LIBRARY_PATH=/scratch/jmarindi/clm_work/netcdf_merged_oneapi/lib:$LD_LIBRARY_PATH
export UCX_TLS=sm,tcp,self
M=$(printf m%03d $SLURM_ARRAY_TASK_ID)
cd {out}/$M
srun -n 1 {EXE} > cesm.log 2>&1
{W}/conda_perl/bin/python3 {W}/CLM_SPRUCE/sol/qui_cal/member_qoi.py {out}/$M > qoi.json 2> qoi.err
""")
    print(f'{n} members in {out}; submit: sbatch {out}/run_array.sh')

if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else 'pilot')

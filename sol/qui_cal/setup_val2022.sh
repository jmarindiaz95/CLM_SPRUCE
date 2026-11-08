#!/bin/bash
# 2020-2022 validation continuation of calibration members (results/qui_val2022).
# Each member restarts (startup from finidat, as the 2015 members do) from its own 2020-01-01 restart, with the
# 2018-2022 PE-QFR forcing (sol/qui_cal/make_forcing_input.py + sol/make_qui_forcing.py, real years 2020-2022) and
# the 2020-2022 observed-level table (sol/qui_cal/make_obswl_val.py). Everything else (parameters, switches,
# history fields, executable) is the member's own. Calibration directories are only read.
# Usage: setup_val2022.sh <ensemble dir> <out dir> <member> [member ...]
set -euo pipefail
ENS=$1; OUT=$2; shift 2
FORC=/scratch/jmarindi/clm_work/clm-microbe/inputdata/atm/datm7/CLM1PT_data/2x1pt_PE-QFR_2018-2022
TABLE=$OUT/finund_obswl_2020-2022.txt
EXE=${EXE:-/scratch/jmarindi/elm_work/builds/qui_cal_exud/cesm.exe}   # override for another build
[ -f $TABLE ] && [ -f $FORC/2022-12.nc ] && [ -f $FORC/2020-01.nc ] || { echo "ERROR: forcing or level table missing"; exit 1; }
[ $(wc -l < $TABLE) -eq 1096 ] || { echo "ERROR: table must have 1096 lines"; exit 1; }
for M in "$@"; do
  S=$ENS/$M; D=$OUT/$M
  R=$(ls $S/*.clm2.r.2020-01-01-00000.nc 2>/dev/null | head -1 || true); R=${R:-$S/missing.clm2.r.2020-01-01-00000.nc}   # case name differs per build
  [ -f $R ] || { echo "ERROR: $R missing"; exit 1; }
  [ -e $D ] && { echo "ERROR: $D exists"; exit 1; }
  mkdir -p $D
  for f in $S/*_in $S/*_modelio.nml $S/datm.streams.txt.* $S/datm.global1val.streams.co2.txt $S/microbepar_in \
           $S/clm_params_member.nc; do cp $f $D/; done
  cp $R $D/finidat_2020-01-01.nc
  cp $TABLE $D/finund_obswl.txt
  sed -i -e "s#^ finidat = .*# finidat = '$D/finidat_2020-01-01.nc'#" \
         -e "s#^ fpftcon = .*# fpftcon = '$D/clm_params_member.nc'#" $D/lnd_in
  sed -i -e "s#^ start_ymd = .*# start_ymd = 20200101#" -e "s#^ stop_n = .*# stop_n = 3#" \
         -e "s#^ restart_n = .*# restart_n = 3#" $D/drv_in
  # logs into the validation directory (the copied *_modelio.nml point diro at the calibration member), timing dir
  sed -i -e "s#^ diro = .*# diro = '$D'#" $D/*_modelio.nml
  mkdir -p $D/timing/checkpoints
  grep -h "diro" $D/*_modelio.nml | sort -u | grep -qv "'$D'" && { echo "ERROR: diro not rewritten"; exit 1; }
  sed -i "s#datm.streams.txt.CLM1PT.CLM_USRDAT 1980 2018 2019#datm.streams.txt.CLM1PT.CLM_USRDAT 2020 2020 2022#" $D/datm_atm_in
  # forcing stream: new directory, files 2020-01 .. 2022-12
  python3 - $D/datm.streams.txt.CLM1PT.CLM_USRDAT $FORC <<'EOF'
import sys, re
p, forc = sys.argv[1], sys.argv[2]
s = open(p).read()
old = '/scratch/jmarindi/clm_work/clm-microbe/inputdata/atm/datm7/CLM1PT_data/2x1pt_PE-QFR\n'
assert s.count(old) == 1, 'forcing filePath not found once'
s = s.replace(old, forc + '\n')
files = ''.join(f'            {y}-{m:02d}.nc\n' for y in (2020, 2021, 2022) for m in range(1, 13))
s, n = re.subn(r'(<fileNames>\n)(\s+2018-01\.nc\n(?:\s+\d{4}-\d{2}\.nc\n)*)', lambda m: m.group(1) + files, s)
assert n == 1, 'forcing fileNames block not found'
open(p, 'w').write(s)
EOF
  grep -q "^fix_finund_obswl" $D/microbepar_in || { echo "ERROR: $M has no fix_finund_obswl"; exit 1; }
  echo "== $M"; grep -E "^ (finidat|fpftcon)" $D/lnd_in; grep -E "^ (start_ymd|stop_n|restart_n)" $D/drv_in
  grep -E "streams" $D/datm_atm_in | head -1; grep -c "\.nc$" $D/datm.streams.txt.CLM1PT.CLM_USRDAT
done
cat > $OUT/run_val.sh <<EOF
#!/bin/bash
#SBATCH --job-name=qui_val2022
#SBATCH -p public
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --mem=3G
#SBATCH -t 01:00:00
#SBATCH --array=0-$(( $# - 1 ))
#SBATCH -o $OUT/slurm.%A_%a.out
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export LD_LIBRARY_PATH=/scratch/jmarindi/clm_work/netcdf_merged_oneapi/lib:\$LD_LIBRARY_PATH
export UCX_TLS=sm,tcp,self
MS=($*)
cd $OUT/\${MS[\$SLURM_ARRAY_TASK_ID]}
srun -n 1 $EXE > cesm.log 2>&1
EOF
echo "submit: sbatch $OUT/run_val.sh"

#!/bin/bash
# Build the current code and run two simultaneous 20-year cold-start AD spinups with column-level output:
#   fixon : fix_dom_n=1, fix_co2_dt=1  (N-conserving DON reset, corrected CO2 source)
#   fixoff: fix_dom_n=0, fix_co2_dt=0  (original microbial dynamics)
# Both have the HR bookkeeping fix and the C/N balance checks (CBAL_ERR, NBAL_ERR, DOC_CH4MOD_LOSS).
# Usage (login node, any shell):  bash /scratch/jmarindi/elm_work/CLM_SPRUCE/sol/run_diag_test.sh
set -e
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 \
  intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export I_MPI_CC=icc I_MPI_CXX=icpc I_MPI_FC=ifort I_MPI_F90=ifort I_MPI_F77=ifort
export UCX_TLS=sm,tcp,self
NCDF=/scratch/jmarindi/clm_work/netcdf_merged_oneapi
export LD_LIBRARY_PATH=$NCDF/lib:$LD_LIBRARY_PATH

W=/scratch/jmarindi/elm_work
SRC=$W/CLM_SPRUCE
CASE=$W/cases/spruce_microbe_test
R=$W/runs/spruce_microbe_test
BLD=$W/builds/spruce_microbe_test
EXE=$BLD/cesm.exe
DIN=/scratch/jmarindi/clm_work/clm-microbe/inputdata
NYRS=20

command -v mpif90 >/dev/null || { echo "ERROR: mpif90 not found after module load"; exit 1; }

# 1. code + parameter file
echo "source: $(cd $SRC && git log --oneline -1)"   # run git pull BEFORE this script
cp $SRC/inputdata/lnd/clm2/paramdata/microbepar_in $DIN/lnd/clm2/paramdata/microbepar_in
cp $SRC/models/lnd/clm/bld/clm.buildnml.csh $CASE/Buildconf/clm.buildnml.csh
rm -f $CASE/microbepar_in

# 2. build
cd $CASE
if ./spruce_microbe_test.build > build_out.txt 2>&1 && grep -q "SUCCESSFULLY" build_out.txt; then
  echo "== BUILD OK"
else
  echo "== BUILD FAILED, error:"
  grep -a -i -m5 -B1 -A4 "error" $(ls -t $BLD/lnd.bldlog.* | head -1) | cut -c1-300
  exit 1
fi

# 3. namelists: 20-year cold-start AD spinup, column-level history (hummock and hollow separately)
./xmlchange -file env_run.xml -id STOP_OPTION -val nyears
./xmlchange -file env_run.xml -id STOP_N -val $NYRS
./xmlchange -file env_run.xml -id REST_OPTION -val nyears
./xmlchange -file env_run.xml -id REST_N -val $NYRS
./xmlchange -file env_run.xml -id CONTINUE_RUN -val FALSE
grep -q spinup_state user_nl_clm || echo " spinup_state = 1" >> user_nl_clm
grep -q "use_c13" user_nl_clm || printf " use_c13 = .false.\n use_c14 = .false.\n" >> user_nl_clm
cp user_nl_clm user_nl_clm.main
grep -v -E "hist_dov2xy|hist_nhtfrq|hist_mfilt" user_nl_clm.main > user_nl_clm
printf " hist_dov2xy = .false.\n hist_nhtfrq = 0\n hist_mfilt = 12\n" >> user_nl_clm   # monthly, by column
./preview_namelists > /dev/null
cp user_nl_clm.main user_nl_clm          # leave the main case unchanged
for f in drv_in lnd_in datm_in microbepar_in lnd_modelio.nml; do
  [ -f $R/$f ] || { echo "ERROR: $R/$f not generated"; exit 1; }
done
grep -q "hist_dov2xy *= *.false." $R/lnd_in || { echo "ERROR: hist_dov2xy not in lnd_in"; exit 1; }
grep -q "fix_dom_n" $R/microbepar_in || { echo "ERROR: microbepar_in has no fix_dom_n line"; exit 1; }

# 4. one run directory per test
for T in fixon fixoff; do
  D=$W/runs/diag_$T
  rm -rf $D; mkdir -p $D
  find $R -maxdepth 1 -type f ! -name '*.nc' ! -name '*.log.*' ! -name 'rpointer.*' ! -name '*.gz' -exec cp {} $D/ \;
  sed -i "s#$R#$D#g" $D/*_modelio.nml
  if [ $T = fixoff ]; then
    sed -i -e 's/^fix_dom_n.*/fix_dom_n\t0/' -e 's/^fix_co2_dt.*/fix_co2_dt\t0/' $D/microbepar_in
  fi
  echo "== $T: $(grep -E '^fix_' $D/microbepar_in | tr '\n\t' '  ')"
  cat > $D/job.sh <<EOF
#!/bin/bash
#SBATCH --job-name=diag_$T
#SBATCH -p public
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 02:00:00
#SBATCH --mem=8G
#SBATCH -o $D/job.%j.out
#SBATCH -e $D/job.%j.err
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export LD_LIBRARY_PATH=$NCDF/lib:\$LD_LIBRARY_PATH
export UCX_TLS=sm,tcp,self
export OMP_NUM_THREADS=1
cd $D
srun -n 1 $EXE > cesm.log 2>&1
echo "exit code \$?" >> cesm.log
EOF
  sbatch $D/job.sh
done
echo
echo "Both submitted (about 20-30 min each). Check: squeue -u jmarindi"
echo "When done:  cd $W/runs && tar czf ~/diag20.tgz diag_*/*.clm2.h0.*.nc diag_*/lnd.log.* diag_*/cesm.log"

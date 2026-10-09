#!/bin/bash
# Run the DOC-diffusion control test as two simultaneous 40-year AD-spinup jobs sharing one executable.
#   A: dom_diffus = 0    (diffusion off; old and new code are identical)  -> is diffusion the cause?
#   B: dom_diffus default (fixed, mass-conserving diffusion)               -> is the fixed model stable?
# Prerequisite: spruce_microbe_test rebuilt with commit e565b81 or later (microbeMod diffusion fix).
# Usage (login node):  bash /scratch/jmarindi/elm_work/CLM_SPRUCE/sol/run_dom_test.sh
set -e
W=/scratch/jmarindi/elm_work
CASE=$W/cases/spruce_microbe_test
R=$W/runs/spruce_microbe_test
EXE=$W/builds/spruce_microbe_test/cesm.exe
NCDF=/scratch/jmarindi/clm_work/netcdf_merged_oneapi
NYRS=40

[ -x "$EXE" ] || { echo "ERROR: $EXE missing - build the case first"; exit 1; }
grep -q "cdocs_sat_temp(c,j) / dz(c,j-1)" $W/CLM_SPRUCE/models/lnd/clm/src/clm4_5/biogeochem/microbeMod.F90 \
  || { echo "ERROR: source does not have the diffusion fix - git pull and rebuild"; exit 1; }
[ "$EXE" -nt $W/CLM_SPRUCE/models/lnd/clm/src/clm4_5/biogeochem/microbeMod.F90 ] \
  || { echo "ERROR: cesm.exe is older than microbeMod.F90 - rebuild the case first"; exit 1; }

# 1. regenerate namelists for a 40-year cold-start AD spinup into the case RUNDIR
cd $CASE
cp $W/CLM_SPRUCE/models/lnd/clm/bld/clm.buildnml.csh Buildconf/clm.buildnml.csh
rm -f microbepar_in
./xmlchange -file env_run.xml -id STOP_OPTION -val nyears
./xmlchange -file env_run.xml -id STOP_N -val $NYRS
./xmlchange -file env_run.xml -id REST_OPTION -val nyears
./xmlchange -file env_run.xml -id REST_N -val 20
./xmlchange -file env_run.xml -id CONTINUE_RUN -val FALSE
grep -q spinup_state user_nl_clm || echo " spinup_state = 1" >> user_nl_clm
./preview_namelists > /dev/null
for f in drv_in lnd_in datm_in microbepar_in lnd_modelio.nml; do
  [ -f $R/$f ] || { echo "ERROR: $R/$f not generated"; exit 1; }
done
grep -q "spinup_state *= *1" $R/lnd_in || { echo "ERROR: spinup_state=1 not in lnd_in"; exit 1; }

# 2. one run directory per test, same inputs
for T in A B; do
  D=$W/runs/domtest_$T
  rm -rf $D; mkdir -p $D
  find $R -maxdepth 1 -type f ! -name '*.nc' ! -name '*.log.*' ! -name 'rpointer.*' ! -name '*.gz' -exec cp {} $D/ \;
  sed -i "s#$R#$D#g" $D/*_modelio.nml
  if [ $T = A ]; then
    sed -i 's/^dom_diffus.*/dom_diffus\t\t0.0/' $D/microbepar_in
  fi
  echo "== test $T: $(grep dom_diffus $D/microbepar_in)"

  cat > $D/job.sh <<EOF
#!/bin/bash
#SBATCH --job-name=domtest_$T
#SBATCH -p public
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 04:00:00
#SBATCH --mem=8G
#SBATCH -o $D/job.%j.out
#SBATCH -e $D/job.%j.err
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0
module load intel-oneapi-mpi-2021.10.0-gcc-12.1.0
module load intel-oneapi-mkl-2022.1.0-aocc-3.1.0
module load netcdf-c-4.8.1-oneapi-2022.1.0
module load netcdf-fortran-4.5.3-oneapi-2022.1.0
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
echo "Both submitted. Check with:  squeue -u jmarindi"
echo "Output: $W/runs/domtest_A and $W/runs/domtest_B"

#!/bin/bash
# Sol case for QUI with the local-port code: same configuration and history fields as the Mac task-10 'on'
# case (sol/qui_cal/user_nl_clm.template, sol/qui_cal/microbepar_in_allfixes), Intel build as setup_qui.sh.
# Usage (login node):  CNAME=qui_sol_ref NYRS=5 bash sol/setup_qui_sol.sh
#   then:              sbatch $CASE/build_and_submit.sh   (builds on htc, then submits the run on public)
# Optional: FINIDAT=<restart>  PARAMS=<microbepar_in file>  SPINUP=1|0
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
CNAME=${CNAME:?set CNAME}
CASE=$W/cases/$CNAME
BLD=$W/builds/$CNAME
RUN=$W/runs/$CNAME
DIN=/scratch/jmarindi/clm_work/clm-microbe/inputdata
SITE=2x1pt_PE-QFR
NYRS=${NYRS:-5}
FINIDAT=${FINIDAT:-$W/runs/qui_ad500_restart/qui_microbe.clm2.r.0501-01-01-00000.nc}
PARAMS=${PARAMS:-$SRC/sol/qui_cal/microbepar_in_allfixes}
SPINUP=${SPINUP:-1}

[ -e "$CASE" ] && { echo "ERROR: $CASE exists."; exit 1; }
[ -f "$FINIDAT" ] || { echo "ERROR: $FINIDAT not found"; exit 1; }
cd $SRC && echo "source: $(git log --oneline -1)"
rsync -a $SRC/inputdata/ $DIN/

cd $SRC/scripts
./create_newcase -case $CASE -mach userdefined -compset I1850CLM45CN -res CLM_USRDAT -compiler intel
cd $CASE
./xmlchange -file env_build.xml -id OS -val LINUX
./xmlchange -file env_build.xml -id COMPILER -val intel
./xmlchange -file env_build.xml -id MPILIB -val openmpi
./xmlchange -file env_build.xml -id EXEROOT -val $BLD
./xmlchange -file env_build.xml -id GMAKE_J -val 4
./xmlchange -file env_build.xml -id CLM_CONFIG_OPTS -val "-phys clm4_5 -bgc cn -vsoilc_centbgc no-cent -microbe on"
./xmlchange -file env_run.xml   -id RUNDIR -val $RUN
./xmlchange -file env_run.xml   -id DIN_LOC_ROOT -val $DIN
./xmlchange -file env_run.xml   -id CLM_USRDAT_NAME -val $SITE
./xmlchange -file env_run.xml   -id CLM_BLDNML_OPTS -val "-mask navy"
./xmlchange -file env_run.xml   -id DATM_MODE -val CLM1PT
./xmlchange -file env_run.xml   -id DATM_CLMNCEP_YR_START -val 2018
./xmlchange -file env_run.xml   -id DATM_CLMNCEP_YR_END -val 2019
./xmlchange -file env_run.xml   -id DATM_CLMNCEP_YR_ALIGN -val 1
./xmlchange -file env_run.xml   -id STOP_OPTION -val nyears
./xmlchange -file env_run.xml   -id STOP_N -val $NYRS
./xmlchange -file env_run.xml   -id REST_OPTION -val nyears
./xmlchange -file env_run.xml   -id REST_N -val $NYRS
./xmlchange -file env_run.xml   -id DOUT_S -val FALSE
./xmlchange -file env_mach_pes.xml -id MAX_TASKS_PER_NODE -val 32
for c in ATM LND ICE OCN CPL GLC ROF WAV; do
  ./xmlchange -file env_mach_pes.xml -id NTASKS_$c -val 1
  ./xmlchange -file env_mach_pes.xml -id NTHRDS_$c -val 1
  ./xmlchange -file env_mach_pes.xml -id ROOTPE_$c -val 0
done
cp $W/cases/spruce_microbe_test/Macros Macros 2>/dev/null || cp $SRC/sol/Macros.test_case_intel_june2026 Macros
grep -q HUM_HOL Macros || sed -i 's/^CPPDEFS+=/CPPDEFS+= -DHUM_HOL/' Macros
sed -e "s#@DIN@#$DIN#g" -e "s#@FINIDAT@#$FINIDAT#" -e "s#^ spinup_state = .*# spinup_state = $SPINUP#" \
    $SRC/sol/qui_cal/user_nl_clm.template > user_nl_clm
echo " taxmode = 'cycle', 'cycle'" > user_nl_datm
cp $PARAMS microbepar_in
./cesm_setup
cp $SRC/models/lnd/clm/bld/clm.buildnml.csh Buildconf/clm.buildnml.csh
./preview_namelists > /dev/null
echo "==== checks"
grep -E "spinup_state|finidat|use_zwt_finundation|finund_wt_only" $RUN/lnd_in || true
grep -E "^fix_" $RUN/microbepar_in || true

cat > submit_run.sh <<SUBEOF
#!/bin/bash
#SBATCH --job-name=$CNAME
#SBATCH -p public
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 04:00:00
#SBATCH --mem=8G
#SBATCH -o $CASE/run.%j.out
#SBATCH -e $CASE/run.%j.err
cd $CASE
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export LD_LIBRARY_PATH=$NCDF/lib:\$LD_LIBRARY_PATH
export I_MPI_CC=icc I_MPI_CXX=icpc I_MPI_FC=ifort I_MPI_F90=ifort I_MPI_F77=ifort
export UCX_TLS=sm,tcp,self
./$CNAME.run
SUBEOF
chmod +x submit_run.sh
cat > build_and_submit.sh <<SUBEOF
#!/bin/bash
#SBATCH --job-name=${CNAME}_build
#SBATCH -p htc
#SBATCH -N 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 01:00:00
#SBATCH -o $CASE/build.log
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export LD_LIBRARY_PATH=$NCDF/lib:\$LD_LIBRARY_PATH
export I_MPI_CC=icc I_MPI_CXX=icpc I_MPI_FC=ifort I_MPI_F90=ifort I_MPI_F77=ifort
cd $CASE
if ./$CNAME.build > build_out.txt 2>&1 && grep -q SUCCESSFULLY build_out.txt && strings $BLD/cesm.exe | grep -q fix_finund_hum_datum; then
  echo "== BUILD OK \$(date); fix_finund_hum_datum in cesm.exe"
  for v in \$(env | grep -o '^SLURM_[A-Za-z_]*'); do unset \$v; done
  sbatch submit_run.sh
else
  echo "== BUILD FAILED"
  zcat -f \$(ls -t $BLD/*.bldlog.* | head -1) | grep -a -i -m5 -B1 -A4 error | cut -c1-300
fi
SUBEOF
chmod +x build_and_submit.sh
echo "Setup done. Next:  sbatch $CASE/build_and_submit.sh   then   cat $CASE/build.log"

#!/bin/bash
# Calibration template case on Sol: transient settings (CO2 stream, N deposition 1849-2006), start 2015-01-01 from the
# all-fixes transient restart, 5 years, lean history (sol/qui_cal/user_nl_clm.cal.template), all fix switches on.
# Builds on htc; the template run directory is then cloned per member by sol/qui_cal/make_members.py.
# Usage (login node):  bash sol/setup_qui_cal_sol.sh   then   sbatch $CASE/build.sh
set -e
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 \
  intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export I_MPI_CC=icc I_MPI_CXX=icpc I_MPI_FC=ifort I_MPI_F90=ifort I_MPI_F77=ifort
NCDF=/scratch/jmarindi/clm_work/netcdf_merged_oneapi
export LD_LIBRARY_PATH=$NCDF/lib:$LD_LIBRARY_PATH
W=/scratch/jmarindi/elm_work
SRC=$W/CLM_SPRUCE
CNAME=${CNAME:-qui_cal_tmpl}   # override for a separate build (e.g. CNAME=qui_cal_obswl)
CASE=$W/cases/$CNAME
BLD=$W/builds/$CNAME
RUN=$W/runs/$CNAME
DIN=/scratch/jmarindi/clm_work/clm-microbe/inputdata
CAL=$W/qui_cal/inputs
FINIDAT=$CAL/qui_trans_yuan.clm2.r.2015-01-01-00000.nc
CO2=$CAL/fco2_datm_1765-2021_qui_c20261106.nc
SITE=2x1pt_PE-QFR
[ -e "$CASE" ] && { echo "ERROR: $CASE exists."; exit 1; }
[ -f $FINIDAT ] && [ -f $CO2 ] || { echo "ERROR: inputs missing in $CAL"; exit 1; }
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
./xmlchange -file env_run.xml -id RUNDIR -val $RUN
./xmlchange -file env_run.xml -id DIN_LOC_ROOT -val $DIN
./xmlchange -file env_run.xml -id CLM_USRDAT_NAME -val $SITE
./xmlchange -file env_run.xml -id CLM_BLDNML_OPTS -val "-mask navy"
./xmlchange -file env_run.xml -id DATM_MODE -val CLM1PT
./xmlchange -file env_run.xml -id DATM_CLMNCEP_YR_START -val 2018
./xmlchange -file env_run.xml -id DATM_CLMNCEP_YR_END -val 2019
./xmlchange -file env_run.xml -id DATM_CLMNCEP_YR_ALIGN -val 1980
./xmlchange -file env_run.xml -id RUN_STARTDATE -val 2015-01-01
./xmlchange -file env_run.xml -id STOP_OPTION -val nyears
./xmlchange -file env_run.xml -id STOP_N -val 5
./xmlchange -file env_run.xml -id REST_OPTION -val nyears
./xmlchange -file env_run.xml -id REST_N -val 5
./xmlchange -file env_run.xml -id DOUT_S -val FALSE
./xmlchange -file env_run.xml -id CCSM_BGC -val CO2A
./xmlchange -file env_run.xml -id CLM_CO2_TYPE -val diagnostic
./xmlchange -file env_mach_pes.xml -id MAX_TASKS_PER_NODE -val 32
for c in ATM LND ICE OCN CPL GLC ROF WAV; do
  ./xmlchange -file env_mach_pes.xml -id NTASKS_$c -val 1
  ./xmlchange -file env_mach_pes.xml -id NTHRDS_$c -val 1
  ./xmlchange -file env_mach_pes.xml -id ROOTPE_$c -val 0
done
cp $W/cases/spruce_microbe_test/Macros Macros 2>/dev/null || cp $SRC/sol/Macros.test_case_intel_june2026 Macros
grep -q HUM_HOL Macros || sed -i 's/^CPPDEFS+=/CPPDEFS+= -DHUM_HOL/' Macros
sed -e "s#@DIN@#$DIN#g" -e "s#@FINIDAT@#$FINIDAT#" $SRC/sol/qui_cal/user_nl_clm.cal.template > user_nl_clm
cat > user_nl_datm <<DEOF
 taxmode = 'cycle','cycle','extend'
 dtlimit = 1.5,1.5,1.5
 fillalgo = 'nn','nn','nn'
 fillmask = 'nomask','nomask','nomask'
 mapalgo = 'nn','nn','nn'
 mapmask = 'nomask','nomask','nomask'
 tintalgo = 'nearest','linear','linear'
 streams = "datm.streams.txt.CLM1PT.CLM_USRDAT 1980 2018 2019", "datm.streams.txt.presaero.clim_1850 1 1 1", "datm.global1val.streams.co2.txt 1765 1765 2021"
DEOF
sed -e "s#/fis/cgd/cseg/csm/inputdata/atm/datm7/CO2#$CAL#g" -e "s#fco2_datm_1765-2007_c100614.nc#$(basename $CO2)#g" \
    $SRC/models/lnd/clm/doc/UsersGuide/co2_streams.txt > datm.global1val.streams.co2.txt
cp $SRC/sol/qui_cal/microbepar_in_allfixes microbepar_in
./cesm_setup
cp $SRC/models/lnd/clm/bld/clm.buildnml.csh Buildconf/clm.buildnml.csh
./preview_namelists > /dev/null
cp datm.global1val.streams.co2.txt $RUN/
echo "==== checks"
grep -E "spinup_state|finidat|co2_type|finund_k|finund_min|stream_year_last_ndep" $RUN/lnd_in || true
grep -E "streams|taxmode" $RUN/datm_atm_in || true
grep -c "^fix_.*1" $RUN/microbepar_in
cat > build.sh <<BEOF
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
if ./$CNAME.build > build_out.txt 2>&1 && grep -q SUCCESSFULLY build_out.txt && strings $BLD/cesm.exe | grep -q ${STRCHK:-fix_finund_hum_datum}; then
  cp $CASE/datm.global1val.streams.co2.txt $RUN/
  echo "== BUILD OK \$(date)"
else
  echo "== BUILD FAILED"
fi
BEOF
chmod +x build.sh
echo "Setup done. Next: sbatch $CASE/build.sh"

#!/bin/bash
# PE-QFR (Quistococha) ELM-SPRUCE case with the Yuan et al. (2023) configuration.
# Same build as the SPRUCE test (MICROBE + HUM_HOL, VERTSOILC, NITRIF_DENITRIF), site inputs from
# sol/make_qui_static.py and forcing from sol/make_qui_forcing.py (both committed under inputdata/).
#
# Usage (login node):  bash /scratch/jmarindi/elm_work/CLM_SPRUCE/sol/setup_qui.sh
#   then:              sbatch $CASE/build_and_submit.sh     (builds on a compute node, then submits the run)
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
CNAME=qui_microbe
CASE=$W/cases/$CNAME
BLD=$W/builds/$CNAME
RUN=$W/runs/$CNAME
DIN=/scratch/jmarindi/clm_work/clm-microbe/inputdata
SITE=2x1pt_PE-QFR
NYRS=${NYRS:-20}          # first test: 20-year AD spinup

[ -e "$CASE" ] && { echo "ERROR: $CASE exists. Remove it first: rm -rf $CASE $BLD $RUN"; exit 1; }
[ -f $SRC/inputdata/atm/datm7/CLM1PT_data/$SITE/2019-12.nc ] || { echo "ERROR: forcing missing in $SRC/inputdata/atm/datm7/CLM1PT_data/$SITE (git pull?)"; exit 1; }
cd $SRC && echo "source: $(git log --oneline -1)"

# site inputs into DIN_LOC_ROOT
rsync -a $SRC/inputdata/ $DIN/

# ---------------------------------------------------------------- case
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
./xmlchange -file env_run.xml   -id REST_N -val 20
./xmlchange -file env_run.xml   -id DOUT_S -val FALSE
./xmlchange -file env_mach_pes.xml -id MAX_TASKS_PER_NODE -val 32
for c in ATM LND ICE OCN CPL GLC ROF WAV; do
  ./xmlchange -file env_mach_pes.xml -id NTASKS_$c -val 1
  ./xmlchange -file env_mach_pes.xml -id NTHRDS_$c -val 1
  ./xmlchange -file env_mach_pes.xml -id ROOTPE_$c -val 0
done
cp $W/cases/spruce_microbe_test/Macros Macros 2>/dev/null || cp $SRC/sol/Macros.test_case_intel_june2026 Macros
grep -q HUM_HOL Macros || sed -i 's/^CPPDEFS+=/CPPDEFS+= -DHUM_HOL/' Macros

# ---------------------------------------------------------------- land namelist: Yuan et al. (2023) options
cat > user_nl_clm <<EOF
 fsurdat = '$DIN/lnd/clm2/surfdata_map/surfdata_$SITE.nc'
 fpftcon = '$DIN/lnd/clm2/paramdata/clm_params_qui.nc'
 stream_fldfilename_ndep = '$DIN/lnd/clm2/ndepdata/fndep_clm_hist_simyr1849-2006_$SITE.nc'
 stream_fldfilename_popdens = '$DIN/lnd/clm2/firedata/clmforc.Li_2012_hdm_1x1pt_PE-QFR_AVHRR_simyr1850-2010_c130401.nc'
 stream_fldfilename_lightng = '$DIN/atm/datm7/NASA_LIS/clmforc.Li_2012_climo1995-2011.1x1pt_PE-QFR.lnfm_c130327.nc'
 use_c13 = .false.
 use_c14 = .false.
 spinup_state = 1
 use_vg_retention = .true.
 use_zwt_finundation = .true.
 use_seasonal_leafcn = .true.
 gapmort_off_year = 9999
 hist_dov2xy = .false.
 hist_nhtfrq = 0
 hist_mfilt = 12
EOF
echo " taxmode = 'cycle', 'cycle'" > user_nl_datm
cp $SRC/inputdata/lnd/clm2/paramdata/microbepar_in_qui microbepar_in     # case copy overrides the default

./cesm_setup
cp $SRC/models/lnd/clm/bld/clm.buildnml.csh Buildconf/clm.buildnml.csh
./preview_namelists > /dev/null
echo "==== checks"
grep -E "use_vg_retention|use_zwt_finundation|use_seasonal_leafcn|gapmort_off_year|spinup_state|fpftcon|fsurdat" $RUN/lnd_in || true
grep -E "^m_dPlantTrans|^m_dAceProdACmax|^fix_" $RUN/microbepar_in || true
grep -h "PE-QFR" $RUN/datm.streams.txt.CLM1PT.* 2>/dev/null | head -3 || true

# ---------------------------------------------------------------- run and build jobs
cat > submit_run.sh <<SUBEOF
#!/bin/bash
#SBATCH --job-name=qui
#SBATCH -p public
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 08:00:00
#SBATCH --mem=8G
#SBATCH -o $CASE/qui.%j.out
#SBATCH -e $CASE/qui.%j.err
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
#SBATCH --job-name=qui_build
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
if ./$CNAME.build > build_out.txt 2>&1 && grep -q SUCCESSFULLY build_out.txt; then
  echo "== BUILD OK"
  for v in \$(env | grep -o '^SLURM_[A-Za-z_]*'); do unset \$v; done
  sbatch submit_run.sh
else
  echo "== BUILD FAILED"
  grep -a -i -m5 -B1 -A4 error \$(ls -t $BLD/*.bldlog.* | head -1) | cut -c1-300
fi
SUBEOF
chmod +x build_and_submit.sh

echo
echo "Setup done. Next:  sbatch $CASE/build_and_submit.sh   then   cat $CASE/build.log"

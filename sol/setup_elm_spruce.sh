#!/bin/bash
# Fresh ELM-SPRUCE (microbial CH4) test case on Sol.
# Source: dmricciuto/CLM_SPRUCE master (ELM-SPRUCE, Ricciuto et al. 2021)
# Test:   US-SPR site, hummock-hollow, vertical soil C, CLM4Me + microbial CH4, site forcing, 1 year cold start.
# Run from a Sol login node:  bash setup_elm_spruce.sh 2>&1 | tee setup.log
set -e

# ---------------------------------------------------------------- Sol environment (stack that built and ran test_case_intel, June 2026)
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0
module load intel-oneapi-mpi-2021.10.0-gcc-12.1.0
module load intel-oneapi-mkl-2022.1.0-aocc-3.1.0
module load netcdf-c-4.8.1-oneapi-2022.1.0
module load netcdf-fortran-4.5.3-oneapi-2022.1.0
export I_MPI_CC=icc I_MPI_CXX=icpc I_MPI_FC=ifort I_MPI_F90=ifort I_MPI_F77=ifort
export UCX_TLS=sm,tcp,self

# ---------------------------------------------------------------- paths (all on scratch; code is a git clone, so a purge is recoverable)
W=/scratch/jmarindi/elm_work
SRC=$W/CLM_SPRUCE                                        # source code
CASE=$W/cases/spruce_microbe_test                        # case dir
BLD=$W/builds/spruce_microbe_test                        # build
RUN=$W/runs/spruce_microbe_test                          # run
DIN=/scratch/jmarindi/clm_work/clm-microbe/inputdata     # existing CESM inputdata (re-downloads anything purged)
NCDF=/scratch/jmarindi/clm_work/netcdf_merged_oneapi     # merged NetCDF used by the working June build

# ---------------------------------------------------------------- checks
for t in ifort icc mpif90 mpicc; do
  command -v $t >/dev/null || { echo "ERROR: $t not found. Load the modules used for test_case_intel first."; exit 1; }
done
[ -d "$NCDF/lib" ] || { echo "ERROR: $NCDF/lib missing (scratch purge?). Tell Claude."; exit 1; }
[ -d "$DIN" ]      || { echo "ERROR: $DIN missing. Tell Claude."; exit 1; }
[ -e "$CASE" ]     && { echo "ERROR: $CASE already exists. Remove it or change CASE."; exit 1; }
echo "compilers: $(command -v ifort) | $(command -v mpif90)"

# ---------------------------------------------------------------- 1. source code
mkdir -p $W/cases
if [ ! -d "$SRC/.git" ]; then
  git clone https://github.com/jmarindiaz95/CLM_SPRUCE.git "$SRC"
fi
cd "$SRC"
git pull -q
# SPRUCE PFT parameter file (Sphagnum + hummock-hollow parameters) is committed in this fork
# (copied from upstream branch dmricciuto/CLM_SPRUCE:respiration, Jul 2018 version)
[ -f inputdata/lnd/clm2/paramdata/clm_params_spruce_calveg.nc ] || { echo "ERROR: SPRUCE param file missing"; exit 1; }
echo "source commit: $(git log -1 --format='%h %cd' --date=short)"

# ---------------------------------------------------------------- 2. site input data into DIN_LOC_ROOT
rsync -a "$SRC/inputdata/" "$DIN/"

# ---------------------------------------------------------------- 3. new case
cd "$SRC/scripts"
./create_newcase -case "$CASE" -mach userdefined -compset I1850CLM45CN -res CLM_USRDAT -compiler intel
cd "$CASE"

./xmlchange -file env_build.xml -id OS -val LINUX
./xmlchange -file env_build.xml -id COMPILER -val intel
./xmlchange -file env_build.xml -id MPILIB -val openmpi
./xmlchange -file env_build.xml -id EXEROOT -val $BLD
./xmlchange -file env_build.xml -id GMAKE_J -val 4
./xmlchange -file env_build.xml -id CLM_CONFIG_OPTS -val "-phys clm4_5 -bgc cn -vsoilc_centbgc on -clm4me on -microbe on"
./xmlchange -file env_run.xml   -id RUNDIR -val $RUN
./xmlchange -file env_run.xml   -id DIN_LOC_ROOT -val $DIN
./xmlchange -file env_run.xml   -id CLM_USRDAT_NAME -val 2x1pt_US-SPR
./xmlchange -file env_run.xml   -id CLM_BLDNML_OPTS -val "-mask navy"
./xmlchange -file env_run.xml   -id DATM_MODE -val CLM1PT
./xmlchange -file env_run.xml   -id DATM_CLMNCEP_YR_START -val 2011
./xmlchange -file env_run.xml   -id DATM_CLMNCEP_YR_END -val 2017
./xmlchange -file env_run.xml   -id DATM_CLMNCEP_YR_ALIGN -val 1
./xmlchange -file env_run.xml   -id STOP_OPTION -val nyears
./xmlchange -file env_run.xml   -id STOP_N -val 1
./xmlchange -file env_run.xml   -id DOUT_S -val FALSE
./xmlchange -file env_mach_pes.xml -id MAX_TASKS_PER_NODE -val 32
for c in ATM LND ICE OCN CPL GLC ROF WAV; do
  ./xmlchange -file env_mach_pes.xml -id NTASKS_$c -val 1
  ./xmlchange -file env_mach_pes.xml -id NTHRDS_$c -val 1
  ./xmlchange -file env_mach_pes.xml -id ROOTPE_$c -val 0
done

# ---------------------------------------------------------------- 4. Sol Macros (the working June 2026 port)
# Same as test_case_intel, except -DMICROBE is gone (configure adds it now) and -DHUM_HOL is added.
cat > Macros <<EOF
CPPDEFS+= -DHUM_HOL -DFORTRANUNDERSCORE -DNO_R16 -DLINUX -DCPRINTEL

SLIBS+= -L$NCDF/lib -lnetcdf -lnetcdff -qmkl

CFLAGS:= -O2 -fp-model precise

CONFIG_ARGS:=

CXX_LDFLAGS:= -cxxlib

CXX_LINKER:=FORTRAN

ESMF_LIBDIR:=

FC_AUTO_R8:= -r8

FFLAGS:= -O2 -fp-model source -convert big_endian -assume byterecl -ftz -traceback

FFLAGS_NOOPT:= -O0

FIXEDFLAGS:= -fixed -132

FREEFLAGS:= -free

MPICC:= mpicc

MPICXX:= mpicxx

MPIFC:= mpif90

MPI_LIB_NAME:=

MPI_PATH:=

NETCDF_PATH:= $NCDF

PNETCDF_PATH:=

SCC:= icc

SCXX:= icpc

SFC:= ifort

SUPPORTS_CXX:=TRUE

ifeq (\$(DEBUG), TRUE)
   FFLAGS += -g -CU -check pointers -fpe0
endif

ifeq (\$(compile_threaded), true)
   CFLAGS += -openmp
   LDFLAGS += -openmp
   FFLAGS += -openmp
endif
EOF

# ---------------------------------------------------------------- 5. land namelist (same files runCLM.py writes for US-SPR)
cat > user_nl_clm <<EOF
 fsurdat = '$DIN/lnd/clm2/surfdata_map/surfdata_2x1pt_US-SPR.nc'
 fpftcon = '$DIN/lnd/clm2/paramdata/clm_params_spruce_calveg.nc'
 stream_fldfilename_ndep = '$DIN/lnd/clm2/ndepdata/fndep_clm_hist_simyr1849-2006_2x1pt_US-SPR.nc'
 stream_fldfilename_popdens = '$DIN/lnd/clm2/firedata/clmforc.Li_2012_hdm_1x1pt_US-SPR_AVHRR_simyr1850-2010_c130401.nc'
 stream_fldfilename_lightng = '$DIN/atm/datm7/NASA_LIS/clmforc.Li_2012_climo1995-2011.1x1pt_US-SPR.lnfm_c130327.nc'
 hist_nhtfrq = 0
 hist_mfilt  = 12
EOF

# ---------------------------------------------------------------- 6. setup + checks
./cesm_setup
echo "==== cppdefs from configure (want VERTSOILC CENTURY_DECOMP NITRIF_DENITRIF LCH4 MICROBE):"
cat Buildconf/clmconf/CESM_cppdefs
echo "==== Macros CPPDEFS (want HUM_HOL):"
grep CPPDEFS Macros
echo "==== datm streams:"
ls CaseDocs | grep -i streams
./check_input_data -inputdata $DIN -check || true

# ---------------------------------------------------------------- 7. batch script (same launch as the June runs)
cat > submit_run.sh <<SUBEOF
#!/bin/bash
#SBATCH --job-name=elm_spruce
#SBATCH -p public
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 04:00:00
#SBATCH --mem=8G
#SBATCH -o elm_spruce.%j.out
#SBATCH -e elm_spruce.%j.err
cd $CASE
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0
module load intel-oneapi-mpi-2021.10.0-gcc-12.1.0
module load intel-oneapi-mkl-2022.1.0-aocc-3.1.0
module load netcdf-c-4.8.1-oneapi-2022.1.0
module load netcdf-fortran-4.5.3-oneapi-2022.1.0
export LD_LIBRARY_PATH=$NCDF/lib:\$LD_LIBRARY_PATH
export I_MPI_CC=icc I_MPI_CXX=icpc I_MPI_FC=ifort I_MPI_F90=ifort I_MPI_F77=ifort
export UCX_TLS=sm,tcp,self
./spruce_microbe_test.run
SUBEOF
chmod +x submit_run.sh

echo
echo "Setup done. Next:"
echo "  cd $CASE && ./spruce_microbe_test.build 2>&1 | tail -20"
echo "  sbatch submit_run.sh"

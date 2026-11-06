#!/bin/bash
# Run inside elm-local with the workspace mounted at /work.
set -euo pipefail
export USER=${USER:-root}
SRC=/work/CLM_SPRUCE
CNAME=${CNAME:-qui_microbe_local}
CASE=/work/cases/$CNAME
RUN=/work/runs/$CNAME
DIN=$SRC/inputdata
RST=/work/inputs/scratch/jmarindi/elm_work/runs/qui_ad500_restart/qui_microbe.clm2.r.0501-01-01-00000.nc
test -f "$RST"
AERO=atm/cam/chem/trop_mozart_aero/aero/aerosoldep_monthly_1850_mean_1.9x2.5_c090421.nc
if [ ! -s "$DIN/$AERO" ]; then
  mkdir -p "$(dirname "$DIN/$AERO")"
  wget -O "$DIN/$AERO" "https://web.lcrc.anl.gov/public/e3sm/inputdata/$AERO"
fi
test ! -e "$CASE" || { echo "Case already exists: $CASE"; exit 1; }
cd "$SRC/scripts"
./create_newcase -case "$CASE" -mach userdefined -compset I1850CLM45CN -res CLM_USRDAT -compiler gnu
cd "$CASE"
./xmlchange OS=LINUX,COMPILER=gnu,MPILIB=mpich,EXEROOT=$RUN/bld,GMAKE_J=4
./xmlchange CLM_CONFIG_OPTS="-phys clm4_5 -bgc cn -vsoilc_centbgc no-cent -microbe on"
./xmlchange RUNDIR="$RUN",DIN_LOC_ROOT="$DIN",CLM_USRDAT_NAME=2x1pt_PE-QFR
./xmlchange CLM_BLDNML_OPTS="-mask navy"
./xmlchange DATM_MODE=CLM1PT,DATM_CLMNCEP_YR_START=2018,DATM_CLMNCEP_YR_END=2019,DATM_CLMNCEP_YR_ALIGN=1
./xmlchange STOP_OPTION=nyears,STOP_N=5,REST_OPTION=nyears,REST_N=5,DOUT_S=FALSE
./xmlchange MAX_TASKS_PER_NODE=1
for c in ATM LND ICE OCN CPL GLC ROF WAV; do
  ./xmlchange NTASKS_$c=1,NTHRDS_$c=1,ROOTPE_$c=0
done
cp "$SRC/sol/Macros.local_gnu" Macros
cat > user_nl_clm <<EOF
 fsurdat = '$DIN/lnd/clm2/surfdata_map/surfdata_2x1pt_PE-QFR.nc'
 fpftcon = '$DIN/lnd/clm2/paramdata/clm_params_qui.nc'
 finidat = '$RST'
 stream_fldfilename_ndep = '$DIN/lnd/clm2/ndepdata/fndep_clm_hist_simyr1849-2006_2x1pt_PE-QFR.nc'
 stream_fldfilename_popdens = '$DIN/lnd/clm2/firedata/clmforc.Li_2012_hdm_1x1pt_PE-QFR_AVHRR_simyr1850-2010_c130401.nc'
 stream_fldfilename_lightng = '$DIN/atm/datm7/NASA_LIS/clmforc.Li_2012_climo1995-2011.1x1pt_PE-QFR.lnfm_c130327.nc'
 use_c13 = .false.
 use_c14 = .false.
 spinup_state = 1
 use_vg_retention = .true.
 use_zwt_finundation = .true.
 finund_wt_only = .true.
 use_seasonal_leafcn = .true.
 gapmort_off_year = 9999
 hist_dov2xy = .false., .false.
 hist_nhtfrq = 0, 1
 hist_mfilt = 12, 17520
 hist_ndens = 1, 1
 hist_avgflag_pertape = 'A', 'I'
 hist_fincl2 = 'FINUNDATED', 'CH4BUD_STOCK_SAT', 'CH4BUD_STOCK_UNSAT',
 'CH4BUD_RESX_SAT', 'CH4BUD_RESX_UNSAT', 'CH4BUD_RES_SAT', 'CH4BUD_RES_UNSAT',
 'CH4BUD_SRC_SAT', 'CH4BUD_SRC_UNSAT'
EOF
echo " taxmode = 'cycle', 'cycle'" > user_nl_datm
cp "$DIN/lnd/clm2/paramdata/microbepar_in_qui" microbepar_in
./cesm_setup
cp "$SRC/models/lnd/clm/bld/clm.buildnml.csh" Buildconf/clm.buildnml.csh
./preview_namelists

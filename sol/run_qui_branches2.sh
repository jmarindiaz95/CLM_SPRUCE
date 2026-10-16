#!/bin/bash
# Second branch set from the year-500 AD-spinup restart (30 years each, monthly column output).
# frac_ch4aom (used in run_qui_branches.sh) is the isotope fractionation factor for AOM, not a rate,
# so the "noaom" branch there was identical to base. AOM is switched here through the AOM
# methanotroph growth rate. All three branches use finund_wt_only = .true.
#   aom0       : m_dGrowRAOMMethanotrophs = 0        (no anaerobic oxidation)
#   aom10      : m_dGrowRAOMMethanotrophs = 0.0004   (10% of the default 0.004)
#   aom0_min   : AOM off and m_dCH4min 0.05 -> 0.005 (plant transport and ebullition start at lower CH4)
# Usage:  sbatch /scratch/jmarindi/elm_work/CLM_SPRUCE/sol/run_qui_branches2.sh ; cat /scratch/jmarindi/elm_work/runs/qui_br2_setup.log
#SBATCH --job-name=qui_br2_setup
#SBATCH -p htc
#SBATCH -N 1
#SBATCH -c 1
#SBATCH --mem=4G
#SBATCH -t 00:20:00
#SBATCH -o /scratch/jmarindi/elm_work/runs/qui_br2_setup.log
W=/scratch/jmarindi/elm_work
CASE=$W/cases/qui_microbe
R=$W/runs/qui_microbe
BLD=$W/builds/qui_microbe
NCDF=/scratch/jmarindi/clm_work/netcdf_merged_oneapi
RST=$W/runs/qui_ad500_restart/qui_microbe.clm2.r.0501-01-01-00000.nc
[ -f $RST ] || { echo "ERROR: $RST not found"; exit 1; }
[ -x $BLD/cesm.exe ] || { echo "ERROR: $BLD/cesm.exe not found"; exit 1; }
SRCD=$W/runs/qui_br_noaom_wt          # template: run directory of the previous branch (same exe, finidat, monthly output)
grep -q "qui_ad500_restart" $SRCD/lnd_in && grep -q "finund_wt_only = .true." $SRCD/lnd_in || { echo "ERROR: template lnd_in not as expected"; exit 1; }

setp() { sed -i "s/^$1[[:space:]].*/$1\t$2/" $3; grep -q "^$1[[:space:]]*$2\$" $3 || { echo "ERROR: $1 not set"; exit 1; }; }

for v in $(env | grep -o '^SLURM_[A-Za-z_]*'); do unset $v; done
for T in aom0 aom10 aom0_min; do
  D=$W/runs/qui_br_$T
  rm -rf $D; mkdir -p $D/timing/checkpoints
  find $SRCD -maxdepth 1 -type f ! -name '*.nc' ! -name '*.log*' ! -name 'rpointer.*' ! -name '*.gz' ! -name 'job*' ! -name 'cesm.log' -exec cp {} $D/ \;
  sed -i "s#$SRCD#$D#g" $D/*_modelio.nml
  setp frac_ch4aom 1.0 $D/microbepar_in
  case $T in
    aom0)     setp m_dGrowRAOMMethanotrophs 0.0 $D/microbepar_in ;;
    aom10)    setp m_dGrowRAOMMethanotrophs 0.0004 $D/microbepar_in ;;
    aom0_min) setp m_dGrowRAOMMethanotrophs 0.0 $D/microbepar_in; setp m_dCH4min 0.005 $D/microbepar_in ;;
  esac
  echo "== $T: $(grep -E '^(m_dGrowRAOMMethanotrophs|m_dCH4min|frac_ch4aom)' $D/microbepar_in | tr '\t\n' '  ') | $(grep -c 'finund_wt_only = .true.' $D/lnd_in) wt_only"
  cat > $D/job.sh <<EOF
#!/bin/bash
#SBATCH --job-name=qui_$T
#SBATCH -p htc
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 01:30:00
#SBATCH --mem=8G
#SBATCH -o $D/job.%j.out
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export LD_LIBRARY_PATH=$NCDF/lib:\$LD_LIBRARY_PATH
export UCX_TLS=sm,tcp,self OMP_NUM_THREADS=1
cd $D
srun -n 1 $BLD/cesm.exe > cesm.log 2>&1
echo "exit code \$?" >> cesm.log
EOF
  sbatch $D/job.sh
done
echo "When all three finish:  cd $W/runs && tar czf ~/qui_branches2.tgz qui_br_aom*/*.clm2.h0.*.nc qui_br_aom*/lnd.log.* qui_br_aom*/cesm.log"

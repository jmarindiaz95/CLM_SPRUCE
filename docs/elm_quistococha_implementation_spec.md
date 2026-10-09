# ELM-SPRUCE tropical rebuild: implementation spec (Yuan et al. 2023 at PE-QFR)

Source: Yuan F., Ricciuto D.M., Xu X., et al. (2023) Evaluation and improvement of the E3SM land model for simulating energy and carbon fluxes in an Amazonian peatland. Agricultural and Forest Meteorology 332, 109364. doi:10.1016/j.agrformet.2023.109364, plus its Supplementary Material (Eqs. 1 to 3, Table S1).

Goal: reproduce the Yuan et al. (2023) configuration at Quistococha (PE-QFR) on SOL, then use it as the base for dissertation development. Their code branch is not public, so the three algorithm changes are re-implemented from the paper.

## 1. Code base

| Role | Repository | Notes |
|---|---|---|
| Base model | `dmricciuto/CLM_SPRUCE`, branch `master` (last change Mar 2022) | This is ELM-SPRUCE as cited in Ricciuto et al. 2021 (Zenodo 10.5281/zenodo.3733924). ELMv0 lineage (branched from CLM4.5). Microbial CH4 module in `models/lnd/clm/src/clm4_5/biogeochem/microbeMod.F90`, parameters in `inputdata/lnd/clm2/paramdata/microbepar_in`. Hummock–hollow via `-DHUM_HOL` cpp flag. |
| Microbial fixes to merge | `email-clm/CLM-Microbe`, branch `master` (Xu lab; code changes Jun 2024 CH4 oxidation, Feb 2025 HR bug fix) | About 100 differing lines in `microbeMod.F90`, includes `micfinundated = finundated(c)` instead of hardcoded 0.99 and unsaturated-zone surface gas fluxes scaled (0.01×) rather than zeroed. |
| Run workflow (Python) | OLMT bundled in `CLM_SPRUCE/scripts/` (`site_fullrun.py`, `runCLM.py`, `makepointdata.py`, `makemetdata.py`, `UQ/UQ_runens.py`) | Matches the old `create_newcase`. Standalone `dmricciuto/OLMT` (master May 2025, `dmricciuto/2024_refactor`) targets modern E3SM/CIME; borrow its `run_GSA.py`, `MCMC.py`, `surrogate_NN.py`, `metdata_tools/`. |
| Parts bin for later | `dmricciuto/E3SM` branch `ELM-Peatlands-rbOct2024` (ELMv2, Oct 2024) | Has `use_obs_zwt` observed water table forcing and ERA5-daymet forcing; CH4 is CLM4Me (no microbial module). |

Naming for the prospectus: "ELM-SPRUCE, the E3SM Land Model configuration with the microbial functional group CH4 module (Ricciuto et al., 2021; Yuan et al., 2023)".

## 2. Simulation protocol used by Yuan et al. (2023)

- Site: PE-QFR, 3°50′03.9″ S, 73°19′08.1″ W. Mauritia flexuosa 61%, Tabebuia insignis 15%. Canopy height 21.3 m, LAI 3.9 to 4.9. Peat 1.9 to 2.5 m, soil C about 740 Mg C/ha.
- Vegetation: a single PFT, tropical broadleaf evergreen tree.
- Forcing: hourly PE-QFR tower data 2018 to 2019 (air temperature, specific humidity, solar radiation, wind speed, air pressure, PAR, precipitation). Precipitation gaps (<20%) filled with hourly ERA5. The 2-year forcing was cycled for all phases.
- Spinup: AD spinup 600 years, final spinup 50 years, transient 1980 to 2020. Evaluation years 2018 and 2019 (CH4 only 2019; 2018 CH4 lost to lightning damage).
- Seasons (Griffis et al. 2020): wet DOY 32 to 120 (both years); dry DOY 152 to 304 (2018) and DOY 213 to 273 (2019).
- All three phases were rerun after the algorithm changes and the parameter optimization.

## 3. The three algorithm modifications

### 3.1 Soil water retention: van Genuchten replaces Clapp–Hornberger

Supplement Eq. 1 (as intended; the printed equation repeats θ_liq in the denominator, which is a typo):

ψ_i = 10 · [ ( ((θ_liq,i − θ_res,i) / (θ_sat,i − θ_res,i))^( n/(1−n) ) − 1 ) / α ]^(1/n)

- ψ_i: matric suction (mm, positive; ELM `smp` is negative, so smp = −ψ).
- θ_res = 0.26, n = 1.4, α = 0.01 (1/cm, so the inner term is cm and the factor 10 converts to mm). Values from Iiyama et al. (2012).
- θ_sat = peat porosity (`watsat`). Fig. S2 shows θ ≈ 0.61 near saturation, 0.36 at 10^3 cm H2O.
- Guard: clamp (θ_liq − θ_res) to a small positive value; below θ_res the function is undefined.

Code points in CLM_SPRUCE (every Clapp–Hornberger evaluation `-sucsat*s**(-bsw)` must switch, or the hydrology and stress terms become inconsistent):

- `biogeophys/SoilHydrologyMod.F90`: lines 1243 and 1258 (`zq`, equilibrium), 1299 (`smp`), 1430 (`smp1`)
- `biogeophys/Hydrology2Mod.F90`: lines 644 (`psi`, MPa) and 665 (`smp_l`)
- `biogeophys/CanopyFluxesMod.F90`: lines 746 and 756 (`smp_node`, root water stress)
- `biogeophys/Biogeophysics1Mod.F90`: line 372 (`psit`, surface evaporation)
- `main/mkarbinitMod.F90`: line 566 (initial `psi`)
- `main/iniTimeConst.F90`: lines about 1276 to 1278 (`watsat`, `bsw`, `sucsat` set from sand and clay); add the VG parameters here per column and layer.

Also check the hydraulic conductivity routine (`hk` uses `bsw` in Clapp–Hornberger form). Yuan et al. only describe the retention curve, so decide whether to keep Clapp–Hornberger conductivity (closest to the paper) or move to the Mualem–van Genuchten conductivity (more consistent). Record the choice.

### 3.2 Water coverage scalar for CH4 processes

Supplement Eq. 2:

f_inundation = exp(−219.4 · ZWT) + 0.45

- Applied as a limiter on acetate production and on CH4 production, oxidation and transport when the surface is not fully covered by water.
- Floor 0.45: the swamp is assumed never more than 55% dry.
- Units: the supplement says ZWT in cm, but Fig. S3 (f ≈ 0.58 at 1 cm, about 0.47 at 2 cm, sensitive between about 0.3 and 1.5 cm) only works if ZWT is in metres inside the exponent (e^(−2.194) + 0.45 ≈ 0.56 at 0.01 m). ELM `zwt(c)` is in metres, so use it directly.
- Cap at 1.0: the expression gives 1.45 at ZWT = 0, so apply `min(f, 1.0)`. Standing water (zwt ≤ 0) gives f = 1.

Code points:

- `biogeochem/microbeMod.F90`: `micfinundated` assignments (lines 775, 777, 896, 903, 2482, 2484, 2486), the `finundated(c) = 0.99` override at line 766, and `subroutine update_finundated` (line 2763).
- `biogeochem/ch4Mod.F90` lines 309 to 322 compute the default `finundated` (h2osfc fraction or the f0·exp(−zwt/zwt0) form). Replace it with Eq. 2 under a tropical switch (namelist flag or parameter) so SPRUCE behaviour is preserved.

### 3.3 Seasonally varying leaf C:N

Supplement Eq. 3:

LCN = LCN0 · exp( −(M − M0)² / (2a²) )

- M = month of year (1 to 12; a fractional month from day of year is smoother).
- LCN0 = 49.294, M0 = 7.43, a = 5.634 (fit R² = 0.703, Fig. S4). This gives about 26 in January and peaks in late July.
- Applied in the FvCB photosynthesis only, not to allocation stoichiometry.

Code point:

- `biogeophys/CanopyFluxesMod.F90` line 1825: `lnc(p) = 1._r8 / (slatop(ivt(p)) * leafcn(ivt(p)))`. Replace `leafcn(ivt(p))` with the seasonal LCN for the tropical PFT. Leave `leafcn` in `CNAllocationMod.F90` and `CNPhenologyMod.F90` unchanged, consistent with the paper.

## 4. Parameters

Table 1, the 21 parameters optimized by the surrogate-assisted MCMC:

| Parameter | Range | Default | Optimized |
|---|---|---|---|
| bdnr | 0.125 to 0.375 | 0.141 | 0.141 |
| br_mr | 1.26e-6 to 3.75e-6 | 3.75e-6 | 1.50e-6 |
| dleaf | 0.01 to 1 | 0.04 | 0.04 |
| fcur | 0 to 1 | 1 | 1 |
| flnr | 0.0231 to 0.264 | 0.2014 | 0.1135 |
| froot_leaf | 0.3 to 2.5 | 0.5645 | 2.5 (upper bound) |
| frootcn | 21 to 63 | 45.25 | 42 |
| leaf_long | 0 to 7 | 1.1 | 1.78 |
| livewdcn | 25 to 75 | 0.763 (as printed) | 0.763 |
| mp | 4.5 to 13.5 | 4.23 | 7.0 |
| q10_mr | 1.3 to 3.3 | 2.21 | 1.3 (lower bound) |
| r_mort | 0.0025 to 0.05 | 0.05 | 0.05 (upper bound) |
| slatop | 0.002 to 0.03 | 0.009 | 0.012 |
| k_dom | 0.00595 to 0.0375 | 0.007 | 0.025 |
| m_dAceProdACmax | 1e-8 to 0.035 | 2.40e-6 | 1.00e-7 |
| m_dACMinQ10 | 1.5 to 4.5 | 3 | 3 |
| m_dGrowRAceMethanogens | 0.004 to 2.88 | 0.008 | 0.008 |
| m_dH2ProdAcemax | 2.5e-9 to 1.24 | 5.00e-8 | 5.00e-8 |
| m_dYAceMethanogens | 0.037 to 0.3 | 0.2 | 0.162 |
| m_dKCH4OxidCH4 | 0.0025 to 1.5 | 1 | 1 |
| m_dPlantTrans | 0.008 to 17.2 | 0.00595 | 0.014 |

Table S1 lists the full 65-parameter screening set with ranges. Some defaults differ between Table S1 and Table 1 (bdnr, br_mr, k_dom, m_dPlantTrans, leaf_long); use Table 1 values for the reproduction run and note the inconsistency.

Optimization workflow: 6000-member Monte Carlo over 65 parameters, Sobol main and total effects (UQTk, Bayesian compressive sensing), down-selection to 21, a second 4000-member ensemble, NN surrogates (80/20 train/validation), and MCMC with 100,000 evaluations per surrogate. Quantities of interest: NEE, CH4 flux, GPP, ER, LE, split by wet and dry season.

## 5. Benchmark targets (to confirm the reproduction)

- Rn daily: r 0.91, RMSE 20.4 W m⁻².
- LE daily: r 0.75 (2018) and 0.44 (2019), mean RMSE about 13 W m⁻²; 2019 wet-season diel LE peak 220 W m⁻² (observed 225).
- H daily: r 0.02 (2018) and 0.69 (2019); model overestimates H in the dry season.
- NEE daily: mean r 0.85, RMSE 1.2 µmol m⁻² s⁻¹. Diel peak uptake is underestimated (wet 2019: −16.2 vs −20.4 observed). The model is a weak source in the dry season while observations show a weak sink.
- CH4 daily (2019): r 0.79, RMSE 17.5 nmol m⁻² s⁻¹, simulated SD 11.5 vs observed 19.1. Wet-season mean 50.6 vs dry-season mean 27.5 nmol m⁻² s⁻¹. Annual 16.04 ± 4.47 g C m⁻² yr⁻¹ vs observed 22 ± 2.
- CH4 pathways: ebullition 47.0%, plant transport 33.4%, diffusion 19.6%.
- LAI: simulated 4.7 to 4.8 with no seasonality; MODIS shows a higher dry-season LAI.

## 6. Known gaps the authors flag (starting points for dissertation development)

- Plant-mediated CH4 is likely underestimated: soil diffusion plus ebullition is overestimated by about 51% against chambers (Hergoualc'h et al. 2020), and there is no stem or non-aerenchymatous transport.
- Hydrogenotrophic methanogenesis parameters were not in the sensitivity set, although tropical peat studies (Holmes et al. 2015; Finn et al. 2020) indicate hydrogenotrophic dominance.
- Single-layer canopy causes LE and H partition errors and warm midday canopy temperature.
- Leaf phenology, and LAI seasonality, are missing.
- Several optimized parameters sit at their bounds (froot_leaf, r_mort, q10_mr), which suggests structural error.
- The water coverage scalar is a site-specific empirical fit to the PE-QFR water table and CH4 relationship.

## 7. Build order on SOL

1. Clone `CLM_SPRUCE` master to `/scratch/jmarindi/`; port the machine using the existing CLM-Microbe port on SOL; build with `-DHUM_HOL`; run the stock SPRUCE case.
2. Merge the 2024 to 2025 `microbeMod.F90` fixes from `email-clm/CLM-Microbe`.
3. Build the PE-QFR point data with `makepointdata.py` and the forcing from `AMF_PE-QFR_BASE_HH_3-5.csv` with ERA5 precipitation gap fill; single tropical broadleaf evergreen PFT.
4. Run the default model and compare with Fig. S1 (poor seasonality expected).
5. Implement 3.1, 3.2 and 3.3 behind switches; apply the Table 1 optimized values; rerun spinup and transient.
6. Compare against the Section 5 benchmarks. Once matched, the reproduction is complete and dissertation-specific development starts from that commit.

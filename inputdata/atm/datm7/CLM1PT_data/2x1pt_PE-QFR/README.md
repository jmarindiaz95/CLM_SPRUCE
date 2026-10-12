# PE-QFR forcing, 2018-2019 (half-hourly, UTC, noleap)

Built by `sol/make_qui_forcing.py` from `source/PE-QFR_forcing_input_2018-2019.csv.gz`, which was assembled from:

- AmeriFlux FLUXNET product `AMF_PE-QFR_FLUXNET_FLUXMET_HH_2018-2022_v1.3_r1` (ONEFlux): TA_F, VPD_F, PA_F, WS_F, SW_IN_F, LW_IN_F.
  Tower-measured share: TA 94% (2018) and 100% (2019); SW 94% and 99%; WS 63% and 88%; the rest MDS or ERA5-downscaled fill.
  LW_IN_F is entirely ERA5-downscaled (no tower longwave). RH from VPD_F and TA_F.
- Tower rain gauge (`rain_mm_interval`, Tyler logger files, harmonized package `analysis_ready_20261004`).
  The gauge reported near-zero rain from June 2018 to January 2019 (every month < 10 mm), so those months are treated as missing.
- Missing rain filled with FLUXNET ERA5 `P_ERA` scaled by 0.2644, the tower/ERA5 ratio over periods with a working gauge.
  Unscaled `P_ERA` sums to about 10,000 mm per year at this site, roughly 3.7 times the tower total, so it cannot be used as is.

Annual precipitation: 2018 2934 mm (61% of half-hours ERA5-filled), 2019 2773 mm (9% filled).
Yuan et al. (2023) report < 20% precipitation gaps for 2018-2019. That figure is consistent with the June 2018 to January 2019 zeros being counted as observations, which would give 2018 only about 1390 mm.

Timestamps: AmeriFlux local standard time (UTC-5) shifted to UTC. Measurement height ZBOT = 40 m.
The source CSV also carries the tower water table (gap-filled and measured) for model evaluation.

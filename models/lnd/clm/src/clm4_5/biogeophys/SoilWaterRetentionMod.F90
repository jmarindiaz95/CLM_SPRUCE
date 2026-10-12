module SoilWaterRetentionMod

!-----------------------------------------------------------------------
! van Genuchten (1980) soil water retention for peat, used when use_vg_retention = .true.
! (Yuan et al. 2023, Agric. For. Meteorol. 332:109364, Supplement Eq. 1; parameters from
! Iiyama et al. 2012: theta_res = 0.26, n = 1.4, alpha = 0.01 1/cm).
!
!   Se  = (theta - theta_res) / (theta_sat - theta_res)
!   psi = ((Se^(-1/m) - 1) / alpha)^(1/n),  m = 1 - 1/n         [cm suction]
!   smp = -10 * psi                                              [mm, ELM sign convention]
!
! This is Eq. 1 as printed (alpha inside the 1/n power). It reproduces the Fig. S2 points
! (RMSE 0.03 m3/m3 with theta_sat 0.61) much better than the textbook form
! (1/alpha)*(Se^(-1/m)-1)^(1/n) with the same parameters (RMSE 0.08).
! Hydraulic conductivity keeps the Clapp-Hornberger form (Yuan et al. describe only the
! retention curve).
!-----------------------------------------------------------------------

  use shr_kind_mod, only : r8 => shr_kind_r8
  use clm_varctl,   only : vg_theta_res, vg_n, vg_alpha

  implicit none
  private

  public :: vg_smp        ! matric potential (mm, <= 0) from volumetric water content
  public :: vg_dsmpdw     ! d(smp)/d(theta) (mm per m3/m3, >= 0)
  public :: vg_theta      ! volumetric water content from suction (mm, >= 0)
  public :: vg_vol_eq     ! layer-mean water content at hydrostatic equilibrium with the water table
  public :: vg_sy         ! specific yield for a water table at depth zwt (m)

  real(r8), parameter :: se_min = 1.e-3_r8     ! lower limit of effective saturation
  real(r8), parameter :: se_dmax = 0.99_r8     ! upper limit used in the derivative (VG slope is infinite at Se = 1)

contains

  pure real(r8) function theta_r(watsat)
    real(r8), intent(in) :: watsat
    theta_r = min(vg_theta_res, 0.9_r8*watsat)   ! keep theta_res below porosity in mineral layers
  end function theta_r

  pure real(r8) function vg_se(theta, watsat)
    real(r8), intent(in) :: theta, watsat
    real(r8) :: tr
    tr = theta_r(watsat)
    vg_se = (theta - tr) / (watsat - tr)
    vg_se = min(1._r8, max(se_min, vg_se))
  end function vg_se

  pure real(r8) function vg_smp(theta, watsat)
    real(r8), intent(in) :: theta, watsat
    real(r8) :: se, m
    m  = 1._r8 - 1._r8/vg_n
    se = vg_se(theta, watsat)
    vg_smp = -10._r8 * (max(se**(-1._r8/m) - 1._r8, 0._r8) / vg_alpha)**(1._r8/vg_n)
  end function vg_smp

  pure real(r8) function vg_dsmpdw(theta, watsat)
    real(r8), intent(in) :: theta, watsat
    real(r8) :: se, m, x, tr
    m  = 1._r8 - 1._r8/vg_n
    tr = theta_r(watsat)
    se = min(vg_se(theta, watsat), se_dmax)
    x  = se**(-1._r8/m) - 1._r8
    vg_dsmpdw = 10._r8 / (vg_alpha * vg_n * m) * (x/vg_alpha)**(1._r8/vg_n - 1._r8) * se**(-1._r8/m - 1._r8) / (watsat - tr)
  end function vg_dsmpdw

  pure real(r8) function vg_theta(suction_mm, watsat)
    real(r8), intent(in) :: suction_mm, watsat
    real(r8) :: m, tr, psi_cm
    m  = 1._r8 - 1._r8/vg_n
    tr = theta_r(watsat)
    psi_cm = max(suction_mm, 0._r8) / 10._r8
    vg_theta = tr + (watsat - tr) * (1._r8 + vg_alpha*psi_cm**vg_n)**(-m)
  end function vg_theta

  pure real(r8) function vg_vol_eq(zwtmm, ztop, zbot, watsat)
    ! mean water content of the layer [ztop, zbot] (mm, positive down) when suction above the
    ! water table equals the height above it (hydrostatic equilibrium); saturated below it
    real(r8), intent(in) :: zwtmm, ztop, zbot, watsat
    integer, parameter :: nq = 20
    real(r8) :: zt, zb, dzq, zmid, s
    integer :: k
    if (zwtmm <= ztop .or. zbot <= ztop) then
       vg_vol_eq = watsat
       return
    end if
    zt = ztop
    zb = min(zbot, zwtmm)
    dzq = (zb - zt) / real(nq, r8)
    s = 0._r8
    do k = 1, nq
       zmid = zt + (real(k, r8) - 0.5_r8) * dzq
       s = s + vg_theta(zwtmm - zmid, watsat) * dzq
    end do
    s = s + watsat * max(zbot - zwtmm, 0._r8)
    vg_vol_eq = s / (zbot - ztop)
  end function vg_vol_eq

  pure real(r8) function vg_sy(zwt, watsat)
    ! drainable porosity: water released between saturation and equilibrium at the water table depth
    real(r8), intent(in) :: zwt, watsat
    vg_sy = watsat - vg_theta(1.e3_r8*max(zwt, 0._r8), watsat)
  end function vg_sy

end module SoilWaterRetentionMod

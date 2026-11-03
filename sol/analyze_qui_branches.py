# Branch analysis: python3 sol/analyze_qui_branches.py <dir containing qbr/qui_br_*> (edit the branch list for new sets)
import netCDF4 as nc, numpy as np, glob, sys, warnings
warnings.filterwarnings('ignore')
S=sys.argv[1]; sec=365*86400.; w=np.array([0.64,0.36]); C=12.011
zi=np.r_[0,0.0175,0.0451,0.0906,0.1655,0.2891,0.4929,0.8289,1.3828,2.2961,3.8019]; dz=np.diff(zi)
out={}
for T in ['base','noaom','noaom_wt']:
    fs=sorted(glob.glob(f'{S}/qbr/qui_br_{T}/*.h0.*.nc'))
    d0=nc.Dataset(fs[0]); wt=np.array(d0['pfts1d_wtcol'][:]); ci=np.array(d0['pfts1d_ixy'][:])-1
    keys=['CH4_SURF_NETFLUX','CH4_SURF_AERE','CH4_SURF_EBUL','CH4_SURF_DIFF','ZWT','H2OSFC','FINUNDATED','GPP','TLAI','TOTSOMC','TOTVEGC','SMINN','CBAL_ERR','NBAL_ERR',
        'CH4_PROD_ACE_DEPTH','CH4_PROD_CO2_DEPTH','CH4_OXID_AOM_DEPTH','CH4_OXID_O2_DEPTH','CCON_CH4S','CCON_O2S']
    acc={k:[] for k in keys}
    for f in fs:
        d=nc.Dataset(f)
        for k in keys:
            V=d[k]; x=np.ma.filled(V[:].astype(float),np.nan)
            if V.dimensions[-1]=='pft':
                x=np.stack([np.nansum(np.where(ci==c, x*wt, 0)[:, wt>0],1) for c in range(2)],1)
            acc[k].append(x)
        d.close()
    v={k:np.concatenate(acc[k],0) for k in keys}
    n=v['ZWT'].shape[0]; last=slice(n-24,n)
    print(f'===== {T}  ({n} months; stats = last 2 years)')
    for k,nm in enumerate(['hummock','hollow']):
        m=lambda x: np.nanmean(v[x][last,k])
        integ=lambda x: np.nanmean(np.sum(v[x][last,:10,k]*dz,1))*sec*C
        tot=m('CH4_SURF_NETFLUX'); s=m('CH4_SURF_AERE')+m('CH4_SURF_EBUL')+m('CH4_SURF_DIFF')
        print(f"  {nm:8s} net {tot*1e9:6.2f} nmol/m2/s = {tot*sec*C:5.2f} gC/yr | plant {m('CH4_SURF_AERE')*1e9:5.2f} ebul {m('CH4_SURF_EBUL')*1e9:5.2f} diff {m('CH4_SURF_DIFF')*1e9:5.2f}")
        print(f"           prod ace {integ('CH4_PROD_ACE_DEPTH'):5.1f} h2 {integ('CH4_PROD_CO2_DEPTH'):5.1f} | AOM {integ('CH4_OXID_AOM_DEPTH'):5.1f} O2-ox {integ('CH4_OXID_O2_DEPTH'):5.2f} gC/yr | ZWT {m('ZWT'):.3f} m H2OSFC {m('H2OSFC'):.0f} mm FIN {m('FINUNDATED'):.2f}")
        print(f"           CH4 gC/m3 L1-9 {np.round(np.nanmean(v['CCON_CH4S'][last,:9,k],0),2)}")
        print(f"           O2  gO/m3 L1-9 {np.round(np.nanmean(v['CCON_O2S'][last,:9,k],0),2)}")
        print(f"           GPP {m('GPP')*sec:.0f} LAI {m('TLAI'):.1f} vegC {m('TOTVEGC')/1e3:.2f} SOMC {m('TOTSOMC')/1e3:.2f} kg/m2 SMINN {m('SMINN'):.1f} | Cerr max {np.nanmax(abs(v['CBAL_ERR'][:,k])):.1e} Nerr max {np.nanmax(abs(v['NBAL_ERR'][:,k])):.1e}")
    net=v['CH4_SURF_NETFLUX'][:,:2]@w
    yr=net.reshape(-1,12).mean(1)*sec*C
    print('  weighted annual gC/m2/yr, yr 1,2,5,10,20,29,30:', np.round(yr[[0,1,4,9,19,28,29]],2))
    clim=net[last].reshape(2,12)*1e9
    print('  weighted monthly nmol/m2/s yr29(2018):', np.round(clim[0],1)); print('                        yr30(2019):', np.round(clim[1],1))
    print('  hollow ZWT monthly 2019:', np.round(v['ZWT'][n-12:,1],2), ' hummock:', np.round(v['ZWT'][n-12:,0],2))
    out[T]=dict(net=net, zwt=v['ZWT'][:, :2], pl=v['CH4_SURF_AERE'][:,:2]@w, eb=v['CH4_SURF_EBUL'][:,:2]@w, df=v['CH4_SURF_DIFF'][:,:2]@w)
np.save(f'{S}/br_out.npy', out, allow_pickle=True)

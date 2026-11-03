# Branch analysis for QUI (PE-QFR) runs.
#   python3 sol/analyze_qui_branches.py <dir containing qbr/qui_br_*> [branch ...] [--tower <ameriflux_ch4_halfhourly.csv>]
#   default branches: aom0 aom10 aom0_min ; first set: base noaom noaom_wt
# Tower CSV: half-hourly CH4 in nmol m-2 s-1 (column FCH4* or ch4_net*), timestamp column TIMESTAMP_START / TIMESTAMP / datetime.
import netCDF4 as nc, numpy as np, glob, sys, os, re, warnings
warnings.filterwarnings('ignore')
args=sys.argv[1:]; tower=None
if '--tower' in args:
    i=args.index('--tower'); tower=args[i+1]; del args[i:i+2]
S=args[0]; branches=args[1:] or ['aom0','aom10','aom0_min']
sec=365*86400.; w=np.array([0.64,0.36]); C=12.011
zi=np.r_[0,0.0175,0.0451,0.0906,0.1655,0.2891,0.4929,0.8289,1.3828,2.2961,3.8019]; dz=np.diff(zi)
yuan=dict(ebul=0.47, plant=0.33, diff=0.20)
mon=['J','F','M','A','M','J','J','A','S','O','N','D']

tw=None
if tower:
    import pandas as pd
    t=pd.read_csv(tower)
    tc=[c for c in t.columns if re.match(r'(?i)^(TIMESTAMP_START|TIMESTAMP|datetime|date_?time|time)$',c)][0]
    fc=[c for c in t.columns if re.match(r'(?i)^(FCH4|ch4_net)',c)][0]
    ts=pd.to_datetime(t[tc].astype(str), format='%Y%m%d%H%M') if t[tc].astype(str).str.fullmatch(r'\d{12}').all() else pd.to_datetime(t[tc])
    x=pd.Series(pd.to_numeric(t[fc],errors='coerce').where(lambda v: v>-9000).values, index=ts)
    tw=x[x.index.year==2019].groupby(x[x.index.year==2019].index.month).mean().reindex(range(1,13)).values
    print(f'tower {fc} 2019 monthly nmol/m2/s:', np.round(tw,1))

out={}
for T in branches:
    D=f'{S}/qbr/qui_br_{T}'
    fs=sorted(glob.glob(f'{D}/*.h0.*.nc'))
    if not fs: print(f'===== {T}: no history files in {D}'); continue
    lg=sorted(glob.glob(f'{D}/lnd.log.*'))
    sw=[l.strip() for l in open(lg[-1]) if re.search(r'fix_ch4_unsat|m_dGrowRAOMMethanotrophs =|m_dCH4min =',l)] if lg else ['no lnd.log']
    mm=[float(l.split('=')[1].replace('D','E')) for l in sw if 'm_dCH4min' in l]; cmin=mm[0] if mm else 0.05
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
    print(f'===== {T}  ({n} months; stats = last 2 years) | ' + ' ; '.join(sw))
    for k,nm in enumerate(['hummock','hollow']):
        m=lambda x: np.nanmean(v[x][last,k])
        integ=lambda x: np.nanmean(np.sum(v[x][last,:10,k]*dz,1))*sec*C
        tot=m('CH4_SURF_NETFLUX')
        print(f"  {nm:8s} net {tot*1e9:6.2f} nmol/m2/s = {tot*sec*C:5.2f} gC/yr | plant {m('CH4_SURF_AERE')*1e9:5.2f} ebul {m('CH4_SURF_EBUL')*1e9:5.2f} diff {m('CH4_SURF_DIFF')*1e9:5.2f}")
        print(f"           prod ace {integ('CH4_PROD_ACE_DEPTH'):5.1f} h2 {integ('CH4_PROD_CO2_DEPTH'):5.1f} | AOM {integ('CH4_OXID_AOM_DEPTH'):5.1f} O2-ox {integ('CH4_OXID_O2_DEPTH'):5.2f} gC/yr | ZWT {m('ZWT'):.3f} m H2OSFC {m('H2OSFC'):.0f} mm FIN {m('FINUNDATED'):.2f}")
        print(f"           CH4 gC/m3 L1-9 {np.round(np.nanmean(v['CCON_CH4S'][last,:9,k],0),2)}  (m_dCH4min {cmin} mol/m3 = {cmin*C:.2f} gC/m3)")
        print(f"           O2  gO/m3 L1-9 {np.round(np.nanmean(v['CCON_O2S'][last,:9,k],0),2)}")
        print(f"           GPP {m('GPP')*sec:.0f} LAI {m('TLAI'):.1f} vegC {m('TOTVEGC')/1e3:.2f} SOMC {m('TOTSOMC')/1e3:.2f} kg/m2 SMINN {m('SMINN'):.1f} | Cerr max {np.nanmax(abs(v['CBAL_ERR'][:,k])):.1e} Nerr max {np.nanmax(abs(v['NBAL_ERR'][:,k])):.1e}")
    net=v['CH4_SURF_NETFLUX'][:,:2]@w
    pl,eb,df=[v[x][:,:2]@w for x in ('CH4_SURF_AERE','CH4_SURF_EBUL','CH4_SURF_DIFF')]
    gross=np.nanmean(pl[last]+eb[last]+df[last])
    print(f"  pathway share (weighted): ebul {np.nanmean(eb[last])/gross:.2f} plant {np.nanmean(pl[last])/gross:.2f} diff {np.nanmean(df[last])/gross:.2f}   | Yuan 2023: ebul {yuan['ebul']} plant {yuan['plant']} diff {yuan['diff']}")
    yr=net.reshape(-1,12).mean(1)*sec*C
    idx=[i for i in (0,1,4,9,19,len(yr)-2,len(yr)-1) if i<len(yr)]
    print('  weighted annual gC/m2/yr, yrs', [i+1 for i in idx], np.round(yr[idx],2))
    clim=net[last].reshape(2,12)*1e9
    print('  weighted monthly nmol/m2/s', ' '.join(f'{m_:>6s}' for m_ in mon))
    print('                 2018 cycle', ' '.join(f'{x:6.1f}' for x in clim[0]))
    print('                 2019 cycle', ' '.join(f'{x:6.1f}' for x in clim[1]))
    if tw is not None:
        print('                 tower 2019', ' '.join(f'{x:6.1f}' for x in tw))
        ok=np.isfinite(tw)
        r=np.corrcoef(clim[1][ok],tw[ok])[0,1]; ratio=np.nanmean(tw)/np.nanmean(clim[1])
        print(f'  vs tower 2019: tower/model mean {ratio:.1f}x, monthly r {r:.2f}, RMSE {np.sqrt(np.nanmean((clim[1]-tw)**2)):.1f} nmol/m2/s')
    print('  hollow ZWT monthly 2019:', np.round(v['ZWT'][n-12:,1],2), ' hummock:', np.round(v['ZWT'][n-12:,0],2))
    out[T]=dict(net=net, zwt=v['ZWT'][:, :2], pl=pl, eb=eb, df=df, ch4=v['CCON_CH4S'][:,:,:2], o2=v['CCON_O2S'][:,:,:2])
np.save(f'{S}/br2_out.npy' if branches!=['base','noaom','noaom_wt'] else f'{S}/br_out.npy', out, allow_pickle=True)

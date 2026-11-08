import netCDF4 as nc, numpy as np, glob, json
W = np.array([0.64, 0.36]); res = {}
FL = ('ROOT_EXUDC', 'GPP', 'NPP', 'HR')
for r in ['x000', 'x005', 'x010']:
    out = {}
    for m in range(1, 13):
        d = nc.Dataset(glob.glob(f'{r}/*.h0.2019-{m:02d}.nc')[0])
        wc = np.ma.filled(d['pfts1d_wtcol'][:], 0); ci = np.arange(wc.size) // (wc.size // 2)
        for k in ['ROOT_EXUDC', 'CBAL_ERR', 'NBAL_ERR', 'LITR1C', 'DOMC', 'TOTVEGC', 'XSMRPOOL', 'FPG', 'GPP', 'NPP', 'HR', 'TOTSOMC', 'LEAFC', 'FROOTC', 'SMINN']:
            if k not in d.variables: continue
            x = np.ma.filled(d[k][:], np.nan).astype(float)[0]
            if x.ndim == 1 and x.size == wc.size:
                x = np.array([np.nansum((x * wc)[ci == c]) for c in range(2)])
            out.setdefault(k, []).append(float(x[:2] @ W))
    res[r] = out
json.dump(res, open('out/extra_2019.json', 'w'))
for k in ['ROOT_EXUDC', 'GPP', 'NPP', 'HR', 'LITR1C', 'DOMC', 'TOTVEGC', 'LEAFC', 'FROOTC', 'XSMRPOOL', 'FPG', 'SMINN', 'CBAL_ERR', 'NBAL_ERR']:
    print(f'{k:11s}', ' | '.join(f'{r}: {np.mean(res[r][k]) * (86400 if k in FL else 1):.4g}' for r in res if k in res[r]))

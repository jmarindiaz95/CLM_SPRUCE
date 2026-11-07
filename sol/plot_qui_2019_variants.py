#!/usr/bin/env python3
"""2019 monthly CH4 flux: model variants (daily_2018_2019.csv, area-weighted) vs tower (days >= 25% valid half-hours).
Run from /work/results (or ~/elm_local/results); needs matplotlib."""
import csv, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
md = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]; c = [0]
for m in md: c.append(c[-1] + m)
def monthly(v):
    R = [r for r in csv.DictReader(open(f'{v}/daily_2018_2019.csv')) if r['series'] == 'area_weighted' and r['year'] == '2019']
    mod, tow = [], []
    for i in range(12):
        rr = R[c[i]:c[i+1]]; mod.append(sum(float(r['model']) for r in rr) / len(rr))
        t = [float(r['tower']) for r in rr if r['tower'] and int(r['tower_n']) >= 12]; tow.append(sum(t)/len(t) if t else None)
    return mod, tow
series = [('qui_trans', 'Accepted fixes', '#9ec5f4'), ('qui_trans_npp', '+ nppratio', '#5598e7'),
          ('qui_trans_yuan', '+ ponding, rate limiter, hummock datum', '#184f95')]
ink, muted, grid, orange = '#1f1f1e', '#6b6a64', '#e6e5e0', '#eb6834'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': muted, 'xtick.color': muted, 'ytick.color': muted,
                     'axes.spines.top': False, 'axes.spines.right': False})
fig, ax = plt.subplots(figsize=(8.5, 4))
x = list(range(1, 13))
for v, lab, col in series:
    mod, tow = monthly(v); ax.plot(x, mod, color=col, lw=2, marker='o', ms=4, label=lab)
tx = [i+1 for i, t in enumerate(tow) if t is not None]; ty = [t for t in tow if t is not None]
ax.plot(tx, ty, color=orange, lw=2, marker='s', ms=5, label='Tower FCH4 (days ≥ 25% valid)')
ax.set_xticks(x); ax.set_xticklabels('JFMAMJJASOND'); ax.set_ylim(0, 100); ax.set_xlim(0.5, 12.5)
ax.set_ylabel('CH$_4$ flux (nmol m$^{-2}$ s$^{-1}$)', color=ink); ax.grid(axis='y', color=grid, lw=.8)
ax.set_title('2019 monthly CH$_4$ emission, model variants vs PE-QFR tower', loc='left', color=ink, fontsize=10)
ax.legend(frameon=False, fontsize=8, loc='upper right')
fig.tight_layout(); fig.savefig('qui_trans_yuan/qui_2019_variants.png', dpi=160, facecolor='white')

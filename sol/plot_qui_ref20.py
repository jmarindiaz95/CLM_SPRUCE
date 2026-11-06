#!/usr/bin/env python3
"""Task 7 overview figure from annual.csv and monthly_vs_tower.csv (run in results/qui_ref20; needs matplotlib)."""
import csv, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
A = list(csv.DictReader(open('annual.csv'))); M = list(csv.DictReader(open('monthly_vs_tower.csv')))
blue, orange, ink, muted, grid = '#2a78d6', '#eb6834', '#1f1f1e', '#6b6a64', '#e6e5e0'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': muted, 'axes.labelcolor': ink, 'xtick.color': muted,
                     'ytick.color': muted, 'axes.spines.top': False, 'axes.spines.right': False})
fig, ax = plt.subplots(1, 3, figsize=(12, 3.8))
y = [int(a['year']) for a in A]
for k, (col, lab, yl, top) in enumerate([('emission_gC_m2', 'Annual CH4 emission (area-weighted)', 'g C m$^{-2}$ yr$^{-1}$', 25),
                                         ('stock_end_mol_m2', 'CH4 stock, end of year', 'mol m$^{-2}$', None)]):
    a = ax[k]; v = [float(r[col]) for r in A]
    a.plot(y, v, color=blue, lw=2, marker='o', ms=4)
    a.set_title(lab, loc='left', color=ink, fontsize=10); a.set_ylabel(yl)
    a.set_xlabel('Model year (odd = 2018, even = 2019 forcing)')
    a.grid(axis='y', color=grid, lw=.8); a.set_xticks([1, 5, 10, 15, 20]); a.set_ylim(0, top)
ax[0].axhline(22, color=orange, lw=1.5, ls='--')
ax[0].text(20, 22.7, 'Tower ≈ 22 (Griffis et al. 2020)', ha='right', color=ink, fontsize=8)
ax[0].text(20, float(A[-1]['emission_gC_m2']) + 1.2, f"Model {float(A[-1]['emission_gC_m2']):.1f}", ha='right', color=ink, fontsize=8)
a = ax[2]; m = [r for r in M if r['forcing_year'] == '2019']
x = [int(r['month']) for r in m]; mod = [float(r['model_nmol_m2_s']) for r in m]
ok = [r for r in m if r['tower_nmol_m2_s'] and float(r['tower_valid_fraction']) >= 0.1]
tx = [int(r['month']) for r in ok]; ty = [float(r['tower_nmol_m2_s']) for r in ok]
a.plot(x, mod, color=blue, lw=2, marker='o', ms=4, label='Model, year 20 (2019 forcing)')
a.plot(tx, ty, color=orange, lw=2, marker='s', ms=5, label='Tower FCH4, months ≥10% valid')
a.text(12.3, mod[-1], 'Model', color=ink, fontsize=8, va='center'); a.text(12.3, ty[-1], 'Tower', color=ink, fontsize=8, va='center')
a.set_title('2019 monthly CH4 flux', loc='left', color=ink, fontsize=10); a.set_ylabel('nmol m$^{-2}$ s$^{-1}$')
a.set_xticks(range(1, 13)); a.set_xticklabels('JFMAMJJASOND'); a.set_xlim(.5, 13.4); a.set_ylim(0, 110)
a.grid(axis='y', color=grid, lw=.8); a.legend(frameon=False, fontsize=8, loc='upper right')
fig.tight_layout()
fig.savefig('qui_ref20_overview.png', dpi=160, facecolor='white')

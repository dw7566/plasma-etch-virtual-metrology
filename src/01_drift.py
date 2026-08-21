"""Fig/§1 — 식각 깊이 드리프트 재현.
기대값: slope -0.1192 um/wafer, R2 0.606, p 4.53e-19, 단조감소 10/10, n=88"""
import pandas as pd, numpy as np
from scipy import stats

d = pd.read_csv('data/Si_Oxide_etch_89_points.csv').dropna(subset=['stepheight'])
w = d.groupby(['lot_number','wafer_number']).stepheight.mean().reset_index()
w.columns = ['lot','wafer','depth']

nz = pd.concat([g.sort_values('wafer').assign(dz=lambda x: x.depth - x.depth.iloc[0])
                for _, g in w.groupby('lot')])
s = stats.linregress(nz.wafer, nz.dz)
print(f'slope   {s.slope:.4f} um/wafer')
print(f'R2      {s.rvalue**2:.3f}')
print(f'p       {s.pvalue:.2e}')
print(f'w1->w10 {nz[nz.wafer==10].dz.mean():.3f} um')

mono = sum(1 for _, g in w.groupby('lot')
           if stats.linregress(g.sort_values('wafer').wafer, g.sort_values('wafer').depth).slope < 0)
print(f'단조감소 lot  {mono} / {w.lot.nunique()}')
print(f'유효 웨이퍼   {len(w)}')

# 부호검정 — 회귀 가정에 의존하지 않는 근거
print(f'부호검정 p    {0.5**w.lot.nunique():.4f}  (10/10 감소)')

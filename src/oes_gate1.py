"""OES Gate 1 — 전 채널 상관 + 이상치 강건성 (Wafer_01 제외).
기대값: 파장 185.89~883.97nm / |rho|>0.8 327개 / w1제외 219개 / 교집합 182개"""
import netCDF4 as nc, numpy as np, pickle, os
from scipy.stats import spearmanr
os.makedirs('out', exist_ok=True)

D = np.asarray(nc.Dataset('data/Dictionary_OES.nc')['data'][:], dtype=np.float64)
ds = nc.Dataset('data/Day_2024_07_02.nc')
wl = np.asarray(ds.groups['Wafer_01']['wavelengths'][:])
print(f'파장 범위  {wl.min():.2f} ~ {wl.max():.2f} nm  (간격 {np.median(np.diff(wl)):.4f} nm)')

spec = {}
for i in range(1, 11):
    g = ds.groups[f'Wafer_{i:02d}']
    raw = np.asarray(g['data'][:])
    spec[i] = D[raw].mean(axis=0)          # 시간평균 -> (3648,)  * 전량 상주 금지
    print(f'  Wafer_{i:02d}  시점수={raw.shape[0]}')
pickle.dump({'wl': wl, 'spec': spec}, open('out/oes_spec.pkl','wb'))

wafers = sorted(spec)
rho_all = np.array([spearmanr(wafers, [spec[w][c] for w in wafers])[0] for c in range(3648)])
w9 = wafers[1:]
rho_9 = np.array([spearmanr(w9, [spec[w][c] for w in w9])[0] for c in range(3648)])

sa, s9 = set(np.where(np.abs(rho_all)>0.8)[0]), set(np.where(np.abs(rho_9)>0.8)[0])
print(f'\n10장 |rho|>0.8      {len(sa)}')
print(f'9장(w1제외)        {len(s9)}')
print(f'교집합 (강건)       {len(sa & s9)}')
for c in sorted(sa & s9, key=lambda c: -abs(rho_all[c]))[:5]:
    print(f'  {wl[c]:7.2f} nm  전체={rho_all[c]:+.3f}  w1제외={rho_9[c]:+.3f}')

"""§3 정본 — 플라즈마 ON 구간(SourceRFLoadPower > 2000 W)에 한정한 상관.
전체 평균을 쓰면 대기/펌핑 구간이 신호를 희석한다 (pk-pk rho 0.716 -> 0.364).
기대값: refl -0.577, pkpk +0.716, tunecap -0.857 / Pressure sd=0.0000"""
import pickle, numpy as np, pandas as pd
from scipy import stats

W = pickle.load(open('out/wafers.pkl','rb'))
d = pd.read_csv('data/Si_Oxide_etch_89_points.csv').dropna(subset=['stepheight'])
dep = d.groupby(['lot_number','wafer_number']).stepheight.mean()

rows = []
for (lot, wf), v in W.items():
    if (lot, wf) not in dep.index: continue
    feat, A = v['feat'], v['A']
    on = A[:, feat.index('SourceRFLoadPower')] > 2000.0
    if on.sum() == 0: continue
    r = {'lot':lot, 'wafer':wf, 'depth':dep[(lot,wf)], 'n_on':int(on.sum())}
    for i in range(min(len(feat), A.shape[1])):
        r[feat[i]] = A[on, i].mean()
    rows.append(r)
P = pd.DataFrame(rows).sort_values(['lot','wafer'])
P.to_pickle('out/wafer_means_plasma.pkl')

Q = P.copy()
for c in P.columns:
    if c in ('lot','wafer'): continue
    Q[c] = P.groupby('lot')[c].transform(lambda s: s - s.mean())

print(f'웨이퍼 {len(P)}   ON구간 중앙값 {int(P.n_on.median())} 샘플')
print('\n[원인 신호]  lot 정규화 후')
for s in ['SourceRFReflectedPower','SourceRFPeakToPeak','PlatenRFTuningCapacitor']:
    sub = Q[[s,'depth']].dropna(); rho, p = stats.spearmanr(sub[s], sub.depth)
    m = P.groupby('wafer')[s].mean()
    print(f'  {s:26s} rho={rho:+.3f} p={p:.1e} w1->w10={m.get(10,np.nan)-m.get(1,np.nan):+.3f}')

print('\n[음성 대조군]  변화가 0이어야 함')
for s in ['Pressure','PlatenRFLoadPower']:
    m = P.groupby('wafer')[s].mean()
    print(f'  {s:26s} w1->w10={m.get(10,np.nan)-m.get(1,np.nan):+.4f}  '
          f'88장 전체 sd={P[s].std():.4f}')

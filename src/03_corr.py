"""§3 — RF 상관 (전체 시계열 평균).
주의: 정본은 03b_corr_plasma.py 다. 이 스크립트는 전처리 구간 효과를 보이기 위한 대조용."""
import pickle, numpy as np, pandas as pd
from scipy import stats

W = pickle.load(open('out/wafers.pkl','rb'))
d = pd.read_csv('data/Si_Oxide_etch_89_points.csv').dropna(subset=['stepheight'])
dep = d.groupby(['lot_number','wafer_number']).stepheight.mean()

rows = []
for (lot, wf), v in W.items():
    if (lot, wf) not in dep.index: continue
    feat, A = v['feat'], v['A']
    r = {'lot': lot, 'wafer': wf, 'depth': dep[(lot, wf)]}
    for i in range(min(len(feat), A.shape[1])):   # 웨이퍼마다 채널 수가 다름(31 또는 44)
        r[feat[i]] = A[:, i].mean()
    rows.append(r)
P = pd.DataFrame(rows).sort_values(['lot','wafer'])
P.to_pickle('out/wafer_means.pkl')
print(f'매칭 웨이퍼 {len(P)}')

SIG = ['SourceRFReflectedPower','SourceRFPeakToPeak','PlatenRFTuningCapacitor']
NEG = ['Pressure','PlatenRFLoadPower']
Q = P.copy()
for c in P.columns:
    if c in ('lot','wafer'): continue
    Q[c] = P.groupby('lot')[c].transform(lambda s: s - s.mean())

print('\n[원인 신호]  전체 시계열 평균')
for s in SIG:
    sub = Q[[s,'depth']].dropna()
    rho, p = stats.spearmanr(sub[s], sub.depth)
    m = P.groupby('wafer')[s].mean()
    print(f'  {s:26s} rho={rho:+.3f} p={p:.1e} w1->w10={m.get(10,np.nan)-m.get(1,np.nan):+.3f}')

print('\n[음성 대조군]')
for s in NEG:
    m = P.groupby('wafer')[s].mean()
    print(f'  {s:26s} w1->w10={m.get(10,np.nan)-m.get(1,np.nan):+.4f}  sd={P[s].std():.4f}')

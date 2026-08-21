"""OES Gate 2 — 발광선 동정 + 정규화 후 체리피킹 판정.
결론: 원자선 가설 기각. F I 685는 1824채널 중 126위, 유의채널 77.5%가 증가방향."""
import pickle, numpy as np
from scipy.stats import spearmanr

d = pickle.load(open('out/oes_spec.pkl','rb'))
wl, spec = d['wl'], d['spec']
wafers = sorted(spec)
S = np.array([spec[w] for w in wafers])
total = S.sum(axis=1)

LINES = {'F I 685':685.60, 'F I 703':703.75, 'CF2 251':251.9, 'CF2 259':259.0,
         'SiF 440':440.0, 'CO 483':483.5, 'O I 844':844.64, 'Si I 288':288.16,
         'Ar I 727':727.29, 'Ar I 750':750.39, 'Ar I 811':811.53}

print('선          근접파장   오프셋   정규화전rho   정규화후rho(p)')
for name, lam in LINES.items():
    i = np.argmin(np.abs(wl - lam))
    raw = S[:, i]; r1,_ = spearmanr(wafers, raw)
    r2,p2 = spearmanr(wafers, raw/total)
    print(f'{name:10s} {wl[i]:8.2f} {wl[i]-lam:+7.2f} {r1:12.3f} {r2:12.3f} ({p2:.3f})')

print(f'\n전체 적분강도  rho={spearmanr(wafers, total)[0]:+.3f} '
      f'p={spearmanr(wafers,total)[1]:.4f}  변화율={100*(total[-1]/total[0]-1):+.2f}%')

# 체리피킹 방지 — 전 채널 분포에서 F의 위치
norm = S / total[:, None]
rho_n = np.array([spearmanr(wafers, norm[:,c])[0] for c in range(3648)])
p_n   = np.array([spearmanr(wafers, norm[:,c])[1] for c in range(3648)])
strong = S.mean(axis=0) > np.percentile(S.mean(axis=0), 50)
sig = (np.abs(rho_n)>0.6) & (p_n<0.1) & strong
i685 = np.argmin(np.abs(wl - 685.60))
rank = (np.abs(rho_n[strong]) >= abs(rho_n[i685])).sum()
print(f'\n강도 상위 50% 중 정규화후 유의: {sig.sum()} / {strong.sum()} ({100*sig.sum()/strong.sum():.1f}%)')
print(f'F I 685 순위: {rank} / {strong.sum()}  ({100*rank/strong.sum():.1f}%ile)')
print(f'유의 채널 중 감소방향: {100*(rho_n[sig]<0).mean():.1f}%')

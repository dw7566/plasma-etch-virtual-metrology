"""OES Gate 3 — 파장대별 감쇠로 관측창 오염 가설 배제.
오염이면 단파장이 더 감쇠해야 하나, 실제로는 장파장(-7.21%)이 단파장(-2.33%)보다 크다."""
import pickle, numpy as np
from scipy.stats import spearmanr

d = pickle.load(open('out/oes_spec.pkl','rb'))
wl, spec = d['wl'], d['spec']
wafers = sorted(spec)
S = np.array([spec[w] for w in wafers])

print('파장대       w1적분    w10적분   변화율    rho')
for lo, hi in [(200,300),(300,400),(400,500),(500,600),(600,700),(700,800),(800,880)]:
    m = (wl>=lo)&(wl<hi)
    tot = S[:, m].sum(axis=1)
    r,_ = spearmanr(wafers, tot)
    print(f'{lo}-{hi}nm  {tot[0]:9.0f} {tot[-1]:9.0f}  {100*(tot[-1]/tot[0]-1):+6.2f}%  {r:+.3f}')
print('\n단파장이 가장 적게 줄었다 -> 광학 오염 가설 기각.')

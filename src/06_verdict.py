"""§6 — 판정 규칙 k 스윕.
기대값: k=1.0 생략률 76.1% 미검출 0 / k=0.0 미검출 4 / OK 최소깊이 43.585"""
import pandas as pd, numpy as np

MEAN  = np.array([31.594624, 235.833020, 3183.828880, 5.170455])
SCALE = np.array([ 0.843497,   5.914905,   14.850293, 2.857294])
COEF  = np.array([-0.16945869,-0.07170805,-0.23648162,-0.38696030])
B0, SIGMA, LSL = 44.011698110316644, 0.15049298773322664, 43.554
M = np.array([[ 0.07014046,-0.00754927, 0.06827679, 0.00724730],
              [-0.00754927, 0.01513164,-0.01341293, 0.00065064],
              [ 0.06827679,-0.01341293, 0.08091695, 0.00897127],
              [ 0.00724730, 0.00065064, 0.00897127, 0.01277782]])

def predict(x, k=1.0):
    z = (np.asarray(x, float) - MEAN) / SCALE
    pred = B0 + COEF @ z
    h = max(0.0, z @ M @ z)
    sd = SIGMA * np.sqrt(1.0 + h)
    if   sd > 0.22:         v = 'UNCERTAIN'
    elif pred + k*sd < LSL: v = 'OOS'
    elif pred - k*sd > LSL: v = 'OK'
    else:                   v = 'BORDER'
    return pred, sd, v

F = pd.read_pickle('out/feat1c.pkl')
X = F[['tunecap','reflpwr','pkpk','wafer']].values
y = F.depth.values

print('k     생략률   조기중단  적중  오경보  생략중미검출  OK최소깊이')
for k in (0.0, 0.5, 1.0, 1.5, 2.0):
    vs = [predict(x, k) for x in X]
    ok  = [i for i,(p,s,v) in enumerate(vs) if v=='OK']
    oos = [i for i,(p,s,v) in enumerate(vs) if v=='OOS']
    hit  = sum(1 for i in oos if y[i] < LSL)
    miss = sum(1 for i in ok  if y[i] < LSL)
    mind = y[ok].min() if ok else float('nan')
    print(f'{k:<5.1f} {len(ok)/len(y)*100:6.1f}%  {len(oos):8d}  {hit:4d}  {len(oos)-hit:6d}  '
          f'{miss:12d}  {mind:.3f}')
print(f'\n실제 LSL({LSL}) 이탈 {int((y < LSL).sum())} / {len(y)}')

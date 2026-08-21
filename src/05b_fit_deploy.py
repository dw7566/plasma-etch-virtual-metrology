"""§5b — 배포 모델 계수 산출. 출력이 곧 vm_board/vm_model.h 의 내용이다.
주의: SIGMA 는 학습 잔차가 아니라 LOLO RMSE 여야 한다."""
import pandas as pd, numpy as np
from sklearn.linear_model import Ridge
from sklearn.model_selection import LeaveOneGroupOut

F = pd.read_pickle('out/feat1c.pkl')
X = F[['tunecap','reflpwr','pkpk','wafer']].values
y, g = F.depth.values, F.lot.values
ALPHA = 0.1

MEAN, SCALE = X.mean(0), X.std(0)         # ddof=0 — StandardScaler와 동일
Z = (X - MEAN) / SCALE
r = Ridge(alpha=ALPHA).fit(Z, y)          # 전체학습 = 보드 대조 기준
M = np.linalg.inv(Z.T @ Z + ALPHA*np.eye(X.shape[1]))

pred = np.zeros(len(y))
for tr, te in LeaveOneGroupOut().split(Z, y, g):
    m_, s_ = X[tr].mean(0), X[tr].std(0)
    rr = Ridge(alpha=ALPHA).fit((X[tr]-m_)/s_, y[tr])
    pred[te] = rr.predict((X[te]-m_)/s_)
SIGMA = np.sqrt(((y-pred)**2).mean())

np.set_printoptions(precision=8, suppress=True)
print('MEAN  =', repr(MEAN));   print('SCALE =', repr(SCALE))
print('COEF  =', repr(r.coef_)); print('B0    =', repr(r.intercept_))
print('SIGMA =', repr(SIGMA));  print('M     =\n', repr(M))

REF = dict(B0=44.011698110316644, SIGMA=0.15049298773322664,
           COEF=np.array([-0.16945869,-0.07170805,-0.23648162,-0.38696030]))
print(f'\nB0    차이 {abs(r.intercept_-REF["B0"]):.2e}')
print(f'SIGMA 차이 {abs(SIGMA-REF["SIGMA"]):.2e}')
print(f'COEF  최대차이 {np.abs(r.coef_-REF["COEF"]).max():.2e}')

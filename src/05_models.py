"""§5 — 전수 비교 (Leave-One-Lot-Out).  5 특징셋 x 13 모델 = 65 조합
   (+ 순서만 baseline 1행, 28특징에서 PLS k=5,8 추가 2행 = CSV 총 68행)

기대값: 1사이클 4특징  GPR-Matern 0.8775 / Ridge 0.8554
        전공정 28특징  LassoCV 0.9325 / Ridge -1.78 / PLS(k=1) -16.2
        MLP 은 전 조건 실패 (최악 -357,124)

실행 후 model_comparison_full.csv 와 자동 대조한다. 불일치가 나오면
MEANS_PKL 설정(아래)부터 확인할 것.
"""
import os, pickle, warnings
import pandas as pd, numpy as np
warnings.filterwarnings('ignore')
from sklearn.model_selection import LeaveOneGroupOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge, RidgeCV, LassoCV, ElasticNetCV
from sklearn.cross_decomposition import PLSRegression
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, Matern, WhiteKernel, ConstantKernel
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import r2_score

# '전공정' 특징의 정의 — 03_corr.py 가 만드는 전체 시계열 평균이 정본이다.
# 플라즈마 ON 구간 평균(03b)으로 바꿔 보려면 아래를 wafer_means_plasma.pkl 로 교체한다.
MEANS_PKL = 'out/wafer_means.pkl'
RF3 = ['PlatenRFTuningCapacitor', 'SourceRFReflectedPower', 'SourceRFPeakToPeak']
META = {'lot', 'wafer', 'depth', 'n_on'}
PLS_LADDER = (1, 2, 3, 5, 8)      # k <= 특징수 인 것만 사용

# ---------------------------------------------------------------- 데이터
F = pd.read_pickle('out/feat1c.pkl').sort_values(['lot', 'wafer']).reset_index(drop=True)
P = pd.read_pickle(MEANS_PKL).sort_values(['lot', 'wafer']).reset_index(drop=True)
P = P.set_index(['lot', 'wafer']).loc[list(zip(F.lot, F.wafer))].reset_index()
assert len(P) == len(F), f'전공정 평균 {len(P)} != 1사이클 특징 {len(F)}'

y, g = F.depth.values, F.lot.values

# 전공정 27 파라미터: 88장 전부에서 관측됐고 웨이퍼 간 변동이 있는 채널만.
# (Pressure 는 sd 가 정확히 0 이라 여기서 자동 탈락한다 — §3 음성 대조군)
cand = [c for c in P.columns if c not in META and pd.api.types.is_numeric_dtype(P[c])]
ALL27 = [c for c in cand if P[c].notna().all() and P[c].std() > 1e-12]
print(f'전공정 채널  후보 {len(cand)} -> 변동채널 {len(ALL27)}')
if len(ALL27) != 27:
    print(f'  ! 기준값 27 과 다르다. 탈락 채널: {sorted(set(cand) - set(ALL27))}')

SETS = {
    '[1사이클] RF3만':      F[['tunecap', 'reflpwr', 'pkpk']].values,
    '[1사이클] RF3+순서':   F[['tunecap', 'reflpwr', 'pkpk', 'wafer']].values,
    '[전공정] RF3만':       P[RF3].values,
    '[전공정] RF3+순서':    np.column_stack([P[RF3].values, F.wafer.values]),
    '[전공정] 전체27+순서': np.column_stack([P[ALL27].values, F.wafer.values]),
}

# ---------------------------------------------------------------- 모델
sc = lambda m: Pipeline([('s', StandardScaler()), ('m', m)])


def kern(n, matern=True):
    base = Matern(length_scale=np.ones(n), nu=1.5) if matern else RBF(np.ones(n))
    return ConstantKernel(1.0) * base + WhiteKernel(1e-2)


def build(n):
    """CSV 와 동일한 생성 순서를 유지한다."""
    M = {
        'Ridge(a=0.1)': sc(Ridge(alpha=0.1)),
        'RidgeCV':      sc(RidgeCV(alphas=np.logspace(-3, 4, 50))),
        'LassoCV':      sc(LassoCV(cv=5, max_iter=50000)),
        'ElasticNetCV': sc(ElasticNetCV(cv=5, max_iter=50000)),
    }
    for k in PLS_LADDER:
        if k <= n:
            M[f'PLS(k={k})'] = sc(PLSRegression(n_components=k))
    M.update({
        'GPR-RBF':      sc(GaussianProcessRegressor(kernel=kern(n, False), normalize_y=True,
                           alpha=1e-6, n_restarts_optimizer=2, random_state=0)),
        'GPR-Matern':   sc(GaussianProcessRegressor(kernel=kern(n), normalize_y=True,
                           alpha=1e-6, n_restarts_optimizer=2, random_state=0)),
        'SVR-RBF':      sc(SVR(kernel='rbf', C=10, epsilon=0.05)),
        'RandomForest': RandomForestRegressor(n_estimators=400, min_samples_leaf=2,
                           random_state=0, n_jobs=-1),
        'GBR':          GradientBoostingRegressor(n_estimators=300, max_depth=2,
                           learning_rate=0.05, random_state=0),
        'MLP(32,16)':   sc(MLPRegressor((32, 16), max_iter=4000, random_state=0)),
    })
    return M


def evaluate(X, model):
    p = cross_val_predict(model, X, y, cv=LeaveOneGroupOut(), groups=g)
    folds = [np.sqrt(((y[te] - p[te]) ** 2).mean())
             for _, te in LeaveOneGroupOut().split(X, y, g)]
    return r2_score(y, p), np.sqrt(((y - p) ** 2).mean()), np.std(folds)


# ---------------------------------------------------------------- 실행
out = []

# baseline — 웨이퍼 순서 1특징. "센서가 왜 필요한가"의 대조군 (§9-2)
r2, rmse, fsd = evaluate(F[['wafer']].values, sc(Ridge()))
out.append(dict(feat='[기준] 순서만', model='Ridge', nf=1, R2=r2, RMSE=rmse, fold_sd=fsd))
print(f"\n===== [기준] 순서만  1특징 =====\n{'Ridge':14s} R2={r2:9.4f}  RMSE={rmse:.4f}  fold_sd={fsd:.4f}")

for name, X in SETS.items():
    n = X.shape[1]
    print(f'\n===== {name}  {n}특징 =====')
    for nm, m in build(n).items():
        r2, rmse, fsd = evaluate(X, m)
        out.append(dict(feat=name, model=nm, nf=n, R2=r2, RMSE=rmse, fold_sd=fsd))
    for r in sorted([o for o in out if o['feat'] == name], key=lambda r: -r['R2']):
        print(f"{r['model']:14s} R2={r['R2']:12.4f}  RMSE={r['RMSE']:8.4f}  fold_sd={r['fold_sd']:.4f}")

R = pd.DataFrame(out)[['feat', 'model', 'nf', 'R2', 'RMSE', 'fold_sd']]
os.makedirs('out', exist_ok=True)
R.to_csv('out/model_comparison.csv', index=False)
print(f'\n총 {len(R)} 행 -> out/model_comparison.csv')

# ---------------------------------------------------------------- 기준표 대조
REF = 'model_comparison_full.csv'
if os.path.exists(REF):
    ref = pd.read_csv(REF)
    j = R.merge(ref, on=['feat', 'model'], how='outer', suffixes=('', '_ref'), indicator=True)
    missing = j[j._merge != 'both']
    both = j[j._merge == 'both'].copy()
    both['dR2'] = (both.R2 - both.R2_ref).abs()
    print(f'\n[기준표 대조]  공통 {len(both)} 행,  최대 |dR2| = {both.dR2.max():.2e}')
    bad = both[both.dR2 > 5e-3].sort_values('dR2', ascending=False)
    if len(bad):
        print(f'  ! {len(bad)} 행 불일치 (상위 5):')
        for _, r in bad.head().iterrows():
            print(f'    {r.feat:20s} {r.model:14s} {r.R2:12.4f} vs {r.R2_ref:12.4f}')
        print('  -> MEANS_PKL 설정과 ALL27 채널 목록을 먼저 확인할 것')
    if len(missing):
        print(f'  ! 한쪽에만 있는 행 {len(missing)}:')
        for _, r in missing.iterrows():
            print(f'    [{r._merge}] {r.feat} / {r.model}')

"""§4 — 1사이클 특징 추출 (상태머신).
점화(>2000W) 시점부터 누적, SF6 2번째 상승엣지에서 종료.
기대값: 88장, 누적샘플 중앙값 24, tunecap 31.5946 / reflpwr 235.8330 / pkpk 3183.8289"""
import pickle, numpy as np, pandas as pd

TH_PLASMA, TH_SF6 = 2000.0, 300.0
NEED = ['SourceRFLoadPower','Gas5Flow','PlatenRFTuningCapacitor',
        'SourceRFReflectedPower','SourceRFPeakToPeak']

W = pickle.load(open('out/wafers.pkl','rb'))
P = pd.read_pickle('out/wafer_means.pkl')
valid = set(zip(P.lot, P.wafer))

def extract(A, feat):
    ix = {}
    for k in NEED:
        if k not in feat: return None, 0, f'{k} 없음'
        i = feat.index(k)
        if i >= A.shape[1]: return None, 0, f'{k} 인덱스 초과'
        ix[k] = i
    idx = [ix['PlatenRFTuningCapacitor'], ix['SourceRFReflectedPower'], ix['SourceRFPeakToPeak']]
    state, nedge, prev, acc, cnt = 0, 0, 0.0, np.zeros(3), 0
    for t in range(A.shape[0]):
        pw, sf6 = A[t, ix['SourceRFLoadPower']], A[t, ix['Gas5Flow']]
        if state == 0:
            if pw <= TH_PLASMA: continue
            state, prev = 1, sf6            # 점화. 이 샘플부터 누적
        if state == 1:
            if prev < TH_SF6 <= sf6:
                nedge += 1
                if nedge == 2: break        # 1사이클 완료
            prev = sf6
            acc += A[t, idx]; cnt += 1
    if cnt == 0: return None, 0, '누적 0'
    return acc/cnt, cnt, None

rows, cnts, skipped = [], [], []
for (lot, wf), v in sorted(W.items()):
    if (lot, wf) not in valid: continue
    x, c, err = extract(v['A'], v['feat'])
    if x is None: skipped.append((lot, wf, err)); continue
    rows.append({'lot':lot,'wafer':wf,'tunecap':x[0],'reflpwr':x[1],'pkpk':x[2],'nsamp':c})
    cnts.append(c)

F = pd.DataFrame(rows)
F['depth'] = P.set_index(['lot','wafer']).loc[list(zip(F.lot, F.wafer)), 'depth'].values
F.to_pickle('out/feat1c.pkl')
print(f'웨이퍼 {len(F)}  누적샘플 중앙값 {int(np.median(cnts))}  범위 {min(cnts)}~{max(cnts)}')
print(F[['tunecap','reflpwr','pkpk']].mean().round(4).to_string())
if skipped: print(f'\n제외 {len(skipped)}장:', skipped[:5])

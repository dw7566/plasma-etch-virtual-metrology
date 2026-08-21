"""§7 — 보드용 재생 데이터 생성. 리틀엔디언 packed binary.
헤더: magic 'VMW0' / lot / wafer / nsamp / nsig=5 / dt=0.2  이후 float[nsamp][5]"""
import pickle, numpy as np, struct, os, pandas as pd

SIGS = ['SourceRFLoadPower','Gas5Flow','PlatenRFTuningCapacitor',
        'SourceRFReflectedPower','SourceRFPeakToPeak']
MAGIC = 0x564D5730   # 'VMW0'

W = pickle.load(open('out/wafers.pkl','rb'))
P = pd.read_pickle('out/wafer_means.pkl')
valid = set(zip(P.lot, P.wafer))
os.makedirs('replay', exist_ok=True)

n = 0
for (lot, wf), v in sorted(W.items()):
    if (lot, wf) not in valid: continue
    feat, A = v['feat'], v['A']
    if any(s not in feat for s in SIGS): continue
    idx = [feat.index(s) for s in SIGS]
    data = np.ascontiguousarray(A[:, idx], dtype=np.float32)
    with open(f'replay/w_L{lot:02d}_W{wf:02d}.bin','wb') as f:
        f.write(struct.pack('<5if', MAGIC, lot, wf, data.shape[0], 5, 0.2))
        f.write(data.tobytes())
    n += 1
total = sum(os.path.getsize('replay/'+x) for x in os.listdir('replay') if x.endswith('.bin'))
print(f'{n} 파일, 총 {total/1e6:.1f} MB')

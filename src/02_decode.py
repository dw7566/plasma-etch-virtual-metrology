"""§2 — 사전 복호. 이 단계가 전체의 급소다.
원시 인덱스로 회귀하면 R2가 0.887 -> 0.681로 떨어진다.
기대값: D[619]=0.0, 96그룹, 44채널, dt 0.200s, 변동채널 27"""
import netCDF4 as nc, numpy as np, re, pickle, os
os.makedirs('out', exist_ok=True)

D = np.asarray(nc.Dataset('data/Dictionary_process.nc')['data'][:], dtype=np.float64)
print(f'사전 길이   {len(D)}')
print(f'정렬 여부   {bool(np.all(np.diff(D) >= 0))}')
print(f'D[619]      {D[619]}')
print(f'범위        {D.min():.2f} ~ {D.max():.2f}')

DATE2LOT = {'2024_07_02':1,'2024_07_05':2,'2024_07_09':3,'2024_07_11':4,
            '2024_07_19':5,'2024_08_01':6,'2024_08_05':7,'2024_08_07':8,
            '2024_08_21':9,'2024_08_22':10}

ds = nc.Dataset('data/Process_data.nc')
W = {}
for gn, g in ds.groups.items():
    m = re.match(r'Day_(\d{4}_\d{2}_\d{2})_Wafer_(\d+)', gn)
    feat = [str(x).replace('Stat3_Etch_MV_','') for x in g['feature'][:]]
    A = D[np.asarray(g['data'][:])]          # <- 복호. 이 줄이 없으면 전부 어긋난다
    t = np.asarray(g['times'][:]); t = t - t[0]
    W[(DATE2LOT[m.group(1)], int(m.group(2)))] = dict(feat=feat, A=A, t=t)

k0 = sorted(W)[0]
print(f'그룹 수     {len(W)}')
print(f'채널 수     {len(W[k0]["feat"])}')
print(f'dt          {np.median(np.diff(W[k0]["t"])):.3f} s')
var = sum(1 for i in range(W[k0]['A'].shape[1]) if W[k0]['A'][:,i].std() > 1e-9)
print(f'변동 채널   {var}')
pickle.dump(W, open('out/wafers.pkl','wb'))

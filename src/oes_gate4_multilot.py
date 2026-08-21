"""OES Gate 4 — lot 간 재현성. 결정적 단계.
전역 지표는 3/4 lot (lot 6 미검출), 543-562nm 대역은 4/4 lot 전부 유의."""
import netCDF4 as nc, numpy as np, pickle, os
from scipy.stats import spearmanr

D = np.asarray(nc.Dataset('data/Dictionary_OES.nc')['data'][:], dtype=np.float64)
FILES = {1:'Day_2024_07_02.nc', 3:'Day_2024_07_09.nc',
         6:'Day_2024_08_01.nc', 10:'Day_2024_08_22.nc'}
BANDS = [(200,300),(300,400),(400,500),(500,600),(600,700),(700,800),(800,880)]

result = {}
for lot, fname in FILES.items():
    if not os.path.exists(f'data/{fname}'):
        print(f'lot {lot}: {fname} 없음, 건너뜀'); continue
    ds = nc.Dataset(f'data/{fname}')
    wl = np.asarray(ds.groups['Wafer_01']['wavelengths'][:])
    spec = {i: D[np.asarray(ds.groups[f'Wafer_{i:02d}']['data'][:])].mean(axis=0)
            for i in range(1,11) if f'Wafer_{i:02d}' in ds.groups}
    ws = sorted(spec); total = np.array([spec[w].sum() for w in ws])
    rho, p = spearmanr(ws, total)
    band_rho = {}
    for lo, hi in BANDS:
        m = (wl>=lo)&(wl<hi)
        tb = np.array([spec[w][m].sum() for w in ws])
        band_rho[(lo,hi)] = (spearmanr(ws, tb)[0], 100*(tb[-1]/tb[0]-1))
    result[lot] = dict(rho=rho, p=p, pct=100*(total[-1]/total[0]-1),
                       wl=wl, spec=spec, band_rho=band_rho)
    print(f'lot {lot:2d}  전역 rho={rho:+.3f} p={p:.4f}  변화율={100*(total[-1]/total[0]-1):+.2f}%')
pickle.dump(result, open('out/oes_multilot.pkl','wb'))

lots = sorted(result)
print('\n=== 파장대별 rho ===')
print('파장대        ' + '   '.join(f'lot{l}' for l in lots))
for b in BANDS:
    print(f'{b[0]}-{b[1]}nm   ' + '   '.join(f'{result[l]["band_rho"][b][0]:+.2f}' for l in lots))

print('\n=== 543-562nm 대역 적분 (정본 지표) ===')
wl = result[lots[0]]['wl']; m = (wl>=543)&(wl<=562)
print('lot   대역rho (p)        대역변화%   전역rho')
for l in lots:
    s = result[l]['spec']; ws = sorted(s)
    band = np.array([s[w][m].sum() for w in ws])
    rb, pb = spearmanr(ws, band)
    print(f'{l:3d}  {rb:+.3f} ({pb:.4f})   {100*(band[-1]/band[0]-1):+6.2f}%   {result[l]["rho"]:+.3f}')

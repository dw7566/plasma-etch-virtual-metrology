"""OES Gate 0 — 구조 탐색. 파장축(wavelengths)이 있는지가 통과 조건이다.
기대값: 사전 61,443개 정렬 / 그룹 Wafer_01~10 / data (시점,3648) uint16 / wavelengths 존재"""
import netCDF4 as nc, numpy as np

print('=== Dictionary_OES.nc ===')
d = nc.Dataset('data/Dictionary_OES.nc')
print('변수:', list(d.variables.keys()))
for k, v in d.variables.items():
    a = np.asarray(v[:])
    print(f'  {k}: shape={a.shape} dtype={a.dtype}')
    if a.ndim == 1 and a.size > 10:
        print(f'     정렬={bool(np.all(np.diff(a)>=0))}  범위={a.min():.4f}~{a.max():.4f}')

print('\n=== Day_2024_07_02.nc ===')
ds = nc.Dataset('data/Day_2024_07_02.nc')
gs = list(ds.groups.keys())
print(f'그룹 {len(gs)}개:', gs[:5])
if gs:
    for k, v in ds.groups[gs[0]].variables.items():
        print(f'  {k}: shape={v.shape} dtype={v.dtype}')

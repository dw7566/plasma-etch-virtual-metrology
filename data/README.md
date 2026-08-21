# 데이터 배치 위치

Zenodo에서 내려받아 이 디렉토리에 둔다.
DOI: 10.5281/zenodo.17122442  (CC BY 4.0)

## 최소 착수 (9.6 MB) — §1~7 재현에 필요
```
Process_data.nc                 8.8 MB
Dictionary_process.nc            88 kB
Si_Oxide_etch_89_points.csv     648 kB
Lot_status.xlsx                  12 kB
```

## OES 확장 — §OES 재현에 필요
```
Dictionary_OES.nc                90 kB
Day_2024_07_02.nc   (lot 1)     476 MB
Day_2024_07_09.nc   (lot 3)
Day_2024_08_01.nc   (lot 6)
Day_2024_08_22.nc   (lot 10)
```

날짜 → lot 매핑은 `src/02_decode.py` 의 `DATE2LOT` 참조.

# 보드용 재생 데이터 (88 웨이퍼)

`src/07_export.py` 가 생성한 **2차 저작물**이다. 원본은 아래 데이터셋이며
동일 라이선스(CC BY 4.0)를 따른다.

> *A Multi-Model Dataset for BOSCH Plasma-Etching*
> Chemnitz University of Technology (ZFM) + Fraunhofer ENAS + TU Freiberg
> DOI [10.5281/zenodo.17122442](https://doi.org/10.5281/zenodo.17122442) · CC BY 4.0

원본 `Process_data.nc` 에서 웨이퍼별로 **5개 신호만 추출해 float32 로 재배열**한
것이며, 그 외의 가공은 없다. (사전 복호는 적용된 상태 — README §8 참조)

## 형식

웨이퍼 1장 = 파일 1개. 리틀엔디언 packed binary.

```
오프셋  크기   내용
  0     4 B   magic  = 0x564D5730 ('VMW0')
  4     4 B   lot                    int32
  8     4 B   wafer                  int32
 12     4 B   nsamp  샘플 수         int32
 16     4 B   nsig   = 5             int32
 20     4 B   dt     = 0.2 s         float32
 24     ...   float32[nsamp][5]  인터리브
```

신호 순서 (`vm_model.h` 의 `SIG_*` 와 일치):

| # | 신호 | 용도 |
|---|---|---|
| 0 | `SourceRFLoadPower` | 플라즈마 점화 검출 (> 2000 W) |
| 1 | `Gas5Flow` (SF₆) | 사이클 검출 (상승엣지, 임계 300) |
| 2 | `PlatenRFTuningCapacitor` | 특징 |
| 3 | `SourceRFReflectedPower` | 특징 |
| 4 | `SourceRFPeakToPeak` | 특징 |

`index.csv` 에 파일명·lot·wafer·nsamp·dt 목록이 있다.

## 검증

`tests/test_replay.py` 가 88개 파일을 전부 디코드해 `vm_verify.csv` 와 대조한다.

```bash
python -m pytest tests/ -v
```

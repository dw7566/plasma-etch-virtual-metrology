# BOSCH 식각 가상계측 — APACHE6 보드 실장 패키지

식각 공정 시작 **약 5초** 시점의 RF 정합 신호로 최종 식각 깊이를 예측하고,
불확실성을 함께 산출해 **실계측 생략 / 조기중단 / 계측필요** 를 판정한다.

## 1. 모델 요약

| 항목 | 값 |
|---|---|
| 특징 | Platen RF 튜닝커패시터, Source RF 반사파워, Source RF peak-to-peak, 웨이퍼 순서 |
| 관측 구간 | 플라즈마 점화 ~ 2번째 SF₆ 상승엣지 (1 사이클, 약 24 샘플 = 4.8 초) |
| 모델 | Ridge (α=0.1), 표준화 선형 |
| 검증 | Leave-One-Lot-Out, **R² = 0.855, RMSE = 0.151 µm** |
| 불확실성 | leverage 기반  sd = σ·√(1+h),  h = zᵀMz |
| 학습 | 88 웨이퍼 / 10 lot (ZFM BOSCH 데이터셋) |

**추론 비용**: 곱셈 약 40회. NPU·GPU 불필요.

## 2. 파일

```
vm_model.h    자동생성 계수 (수정 금지)
vm_engine.h/c 스트리밍 상태머신 + 예측 + 불확실성
vm_ipc.h      System V 공유메모리/세마포어 정의
vm_master.c   다중 챔버 벤치마크 (fork + shm + semaphore)
Makefile      크로스컴파일
run_bench.sh  보드용 일괄 벤치마크 (PVT 로깅 포함)
replay/       재생 데이터 88 웨이퍼 (5.7 MB) + index.csv
```

## 3. 빌드

```bash
# VM에서 (aarch64 크로스컴파일)
make                    # SDK 기본과 동일한 -mcpu=cortex-a53
make ARCH=a65           # Cortex-A65AE 타깃 (dotprod/fp16 활성)
make both               # 두 개 동시 빌드 → 성능 비교용
make native             # x86 자체검증

file vm_master          # ELF 64-bit, ARM aarch64 확인
```

## 4. 보드로 전송

```bash
# VM에서
sudo cp -r vm_master* run_bench.sh replay /nfsroot/vm/
sudo chmod -R 777 /nfsroot/vm
```

```bash
# 보드에서
mount -t nfs -o nolock 192.168.13.29:/nfsroot /mnt/nfs   # 이미 마운트돼 있으면 생략
cd /mnt/nfs/vm
```

## 5. 실행

```bash
# (1) 정확성 검증 — 이것부터
./vm_master -d ./replay -c 1 -o /tmp/out.csv

# (2) 챔버 수 스윕 (최고속) → 처리량 한계
for C in 1 2 4 8 16 32; do ./vm_master -d ./replay -c $C -k $C; done

# (3) 실시간 5Hz 마감 준수 → 몇 챔버까지 가능한가
for C in 1 4 8 16 32; do ./vm_master -d ./replay -c $C -k $C -r -n 50; done

# (4) 세마포어 경합
for K in 1 2 4 8; do ./vm_master -d ./replay -c 8 -k $K; done

# (5) 판정 임계값 스윕
for T in 0.0 0.5 1.0 1.5 2.0; do ./vm_master -d ./replay -c 1 -t $T; done

# (6) 내구/발열 시험 (PVT 로깅과 함께)
./run_bench.sh ./replay
./vm_master -d ./replay -c 8 -R 200        # 데이터셋 200회 반복

# (7) A53 vs A65AE 컴파일 타깃 비교
./vm_master_a53 -d ./replay -c 4
./vm_master_a65 -d ./replay -c 4
```

## 6. 기대 출력 (x86 검증 기준 — 보드에서는 값이 달라짐)

```
[처리량]
  샘플당 처리     평균 36 ns   최대 23818 ns
  판정 1회        평균 79 ns
[실시간성]
  샘플주기 200ms 대비 여유율  약 5,000,000 배
  마감 초과 횟수  0 / 800  (0.0000%)
[판정 분포]  (LSL 43.554, k=1.00)
  OK(계측생략) 67   OOS(조기중단) 2   BORDER(계측필요) 19   UNCERTAIN 0
  -> 실계측 생략률 76.1%   조기중단 대상 2.3%
```

## 7. 정확성 검증 방법

`/tmp/out.csv` 를 VM으로 가져와 `vm_verify.csv` 의 `pred_full` 컬럼과 대조.

```python
import pandas as pd, numpy as np
C = pd.read_csv('out.csv'); V = pd.read_csv('vm_verify.csv')
J = C.merge(V, on=['lot','wafer'], suffixes=('_c','_py'))
print(np.abs(J.pred - J.pred_full).max())   # 1e-5 um 미만이어야 정상
print((J.n_acc == J.nsamp).sum(), '/', len(J))   # 88/88 이어야 정상
```

x86 검증 결과: 예측 최대오차 **9.9e-6 µm**, 누적 샘플수 **88/88 일치**.

> 주의: `vm_verify.csv` 의 `pred` 컬럼은 LOLO 교차검증 예측이라 C 출력과 다르다.
> 반드시 **`pred_full`** 과 비교할 것.

## 8. 판정 규칙

신뢰구간 [pred − k·sd, pred + k·sd] 와 관리하한 LSL 의 관계로 3분류.

| 조건 | 판정 | 조치 |
|---|---|---|
| pred − k·sd > LSL | **OK** | 실계측 생략 |
| pred + k·sd < LSL | **OOS** | 조기중단 |
| 구간이 LSL 걸침 | **BORDER** | 실계측 수행 |
| sd > 0.22 µm | **UNCERTAIN** | 실계측 + 모델 재검토 (학습분포 밖) |

k 값에 따른 트레이드오프 (88 웨이퍼, 실제 이탈 12장):

| k | 계측생략 | 조기중단 | 적중 | 오경보 | 생략 중 미검출 |
|---|---|---|---|---|---|
| 0.0 | 86.4% | 12 | 8 | 4 | **4** ⚠ |
| 0.5 | 80.7% | 7 | 5 | 2 | 0 |
| **1.0** | **76.1%** | 2 | 2 | **0** | **0** |
| 2.0 | 64.8% | 0 | 0 | 0 | 0 |

**k=1.0 권장**: 오경보 0, 미검출 0, 계측 76% 생략.
불확실성을 쓰지 않는 점추정(k=0)은 미검출 4건이 발생한다 — 불확실성 도입의 실효.

## 9. 재생 데이터 형식

리틀엔디언 바이너리. 웨이퍼 1장 = 파일 1개.

```
int32  magic = 0x564D5730 ('VMW0')
int32  lot
int32  wafer
int32  nsamp
int32  nsig = 5
float  dt            (샘플 간격 [s], 0.2 = 5 Hz)
float  data[nsamp][5]  인터리브
```

신호 순서:
```
0  SourceRFLoadPower        플라즈마 검출 (임계 2000 W)
1  Gas5Flow (SF6)           사이클 검출  (임계 300 sccm)
2  PlatenRFTuningCapacitor  모델 입력 1
3  SourceRFReflectedPower   모델 입력 2
4  SourceRFPeakToPeak       모델 입력 3
```

## 10. 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| `shmget: No space left on device` | 이전 실행이 남김 → `ipcs -m` 확인 후 `ipcrm -M 0x564D3031` |
| `semget` 실패 | `ipcrm -S 0x564D3032` |
| `bad magic` | 재생 파일 전송 중 손상 → `md5sum` 대조 |
| 판정 0건 | 임계값 미달. `-n` 제한이 너무 작지 않은지 확인 (최소 400샘플 필요) |
| 예측이 PC와 다름 | `pred` 대신 `pred_full` 과 비교했는지 확인 |
| 실시간 모드가 안 끝남 | 정상. 웨이퍼당 649초. `-n 50` 으로 제한 |

## 11. 커널 요구사항

`CONFIG_SYSVIPC=y`, `CONFIG_SYSVIPC_SYSCTL=y` — 이미 defconfig에 반영됨.

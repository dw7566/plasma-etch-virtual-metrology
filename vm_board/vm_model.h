/* vm_model.h - 자동생성. 수정 금지.
 * BOSCH 식각 가상계측 모델  (1 사이클 조기예측)
 * 학습: 88 웨이퍼 / 10 lot, Leave-One-Lot-Out R2 = 0.8554
 * 타깃: mean etch depth (um), 89-point average
 */
#ifndef VM_MODEL_H
#define VM_MODEL_H

#define VM_MODEL_VERSION "vm_bosch_1cycle_v1"
#define VM_NFEAT 4
#define VM_SIGMA 1.5049298773e-01f            /* LOLO 잔차 표준편차 [um] */
#define VM_ALPHA 0.100000f

/* 특징 순서: PlatenRFTuningCapacitor, SourceRFReflectedPower, SourceRFPeakToPeak, wafer */

/* 원시입력 직접 사용 선형식:  pred = B0 + sum(B[i]*x[i]) */
static const float VM_B0 = 1.0461884566e+02f;
static const float VM_B[VM_NFEAT] = { -2.0090016439e-01f, -1.2123279468e-02f, -1.5924374513e-02f, -1.3542895732e-01f };


/* 표준화 형태 계수 (수치적으로 안정 — 이쪽을 사용) */
static const float VM_INTERCEPT_STD = 4.4011698110e+01f;
static const float VM_COEF_STD[VM_NFEAT] = { -1.6945868850e-01f, -7.1708047132e-02f, -2.3648162409e-01f, -3.8696030130e-01f };

/* 표준화 파라미터 */
static const float VM_MU[VM_NFEAT] = { 3.1594624303e+01f, 2.3583301960e+02f, 3.1838288796e+03f, 5.1704545455e+00f };
static const float VM_SD[VM_NFEAT] = { 8.4349701262e-01f, 5.9149050653e+00f, 1.4850292794e+01f, 2.8572936612e+00f };

/* leverage 행렬  M = (Xs^T Xs + alpha I)^-1   (대칭) */
static const float VM_M[VM_NFEAT][VM_NFEAT] = {
  { +7.0140460394e-02f, -7.5492671346e-03f, +6.8276794993e-02f, +7.2473005789e-03f },
  { -7.5492671346e-03f, +1.5131640881e-02f, -1.3412934549e-02f, +6.5064045900e-04f },
  { +6.8276794993e-02f, -1.3412934549e-02f, +8.0916953791e-02f, +8.9712739968e-03f },
  { +7.2473005789e-03f, +6.5064045900e-04f, +8.9712739968e-03f, +1.2777820677e-02f }
};

/* ---- 신호 인덱스 (재생 파일 컬럼 순서) ---- */
#define SIG_RF_POWER   0   /* SourceRFLoadPower      : 플라즈마 검출 */
#define SIG_SF6        1   /* Gas5Flow               : 사이클 검출  */
#define SIG_TUNECAP    2   /* PlatenRFTuningCapacitor*/
#define SIG_REFLPWR    3   /* SourceRFReflectedPower */
#define SIG_PKPK       4   /* SourceRFPeakToPeak     */
#define VM_NSIG        5

/* ---- 검출 임계값 (88/88 웨이퍼에서 학습 특징과 정확히 일치 검증) ---- */
#define TH_PLASMA_ON   2000.0f   /* W. 램프구간 1400 초과, 정상 2800 미만 */
#define TH_SF6_ON       300.0f   /* sccm. OFF=0, ON=600 */

/* ---- 관리한계 (예시: 평균 44.0um 기준 -1%) ---- */
#define SPEC_LSL       43.554f
#define SPEC_TARGET    44.000f

#endif

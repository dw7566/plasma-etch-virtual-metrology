/* vm_engine.h - BOSCH 식각 가상계측 스트리밍 추론 엔진
 *
 * 사용법:
 *   vm_state_t st;  vm_init(&st, wafer_no);
 *   for (each sample) {
 *       int r = vm_push(&st, sample);      // sample: float[VM_NSIG]
 *       if (r == VM_READY) { ... st.pred, st.sd, st.h ... }
 *   }
 */
#ifndef VM_ENGINE_H
#define VM_ENGINE_H

#include <stdint.h>
#include "vm_model.h"

/* vm_push 반환값 */
#define VM_WAIT     0   /* 아직 판정 불가 */
#define VM_READY    1   /* 이 샘플에서 예측 완료 */
#define VM_DONE     2   /* 이미 판정 완료됨 (추가 샘플 무시) */

/* 판정 등급 — 신뢰구간이 관리한계와 겹치는지로 3분류 */
#define VM_OK          0   /* pred - k*sd > LSL : 확신 합격 -> 실계측 생략 */
#define VM_OOS         1   /* pred + k*sd < LSL : 확신 이탈 -> 조기중단 */
#define VM_BORDER      2   /* 신뢰구간이 LSL 걸침 -> 실계측 필요 */
#define VM_UNCERTAIN   3   /* sd 과대(학습분포 밖) -> 실계측 + 모델 재검토 */

typedef enum { S_IDLE = 0, S_ACC = 1, S_DONE = 2 } vm_phase_t;

typedef struct {
    /* 입력 */
    int   wafer;              /* lot 내 웨이퍼 순서 (1~) */

    /* 상태머신 */
    vm_phase_t phase;
    int   n_edge;             /* 관측된 SF6 상승엣지 수 */
    float sf6_prev;
    int   n_acc;              /* 누적 샘플 수 */
    double sum[3];            /* RF 3신호 누적합 (배정도: 누적오차 방지) */
    long  n_sample;           /* 처리한 총 샘플 수 */
    long  idx_plasma_on;      /* 플라즈마 검출 시점 */

    /* 출력 */
    float feat[VM_NFEAT];     /* 특징 4개 */
    float pred;               /* 예측 식각깊이 [um] */
    float h;                  /* leverage */
    float sd;                 /* 예측 표준편차 [um] */
    int   verdict;            /* VM_OK / VM_OOS / VM_UNCERTAIN */
} vm_state_t;

void vm_init(vm_state_t *s, int wafer);
int  vm_push(vm_state_t *s, const float *sample);   /* sample[VM_NSIG] */
const char *vm_verdict_str(int v);

/* 판정 파라미터 */
extern float vm_k;          /* 신뢰구간 배수 (기본 1.0) */
extern float vm_lsl;        /* 관리하한 [um] (기본 SPEC_LSL) */
#define VM_SD_LIMIT   0.220f   /* sd 상한. 초과 시 학습분포 밖으로 간주 */

#endif

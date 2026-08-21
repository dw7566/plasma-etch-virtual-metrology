/* vm_engine.c - 스트리밍 상태머신 + 선형 예측 + leverage 기반 불확실성 */
#include <math.h>
#include <string.h>
#include "vm_engine.h"

float vm_k   = 1.0f;
float vm_lsl = SPEC_LSL;

void vm_init(vm_state_t *s, int wafer)
{
    memset(s, 0, sizeof(*s));
    s->wafer = wafer;
    s->phase = S_IDLE;
    s->idx_plasma_on = -1;
}

/* 예측 + 불확실성.  누적이 끝난 시점에 한 번만 호출된다. */
static void vm_infer(vm_state_t *s)
{
    int i, j;

    /* --- 특징 확정 --- */
    for (i = 0; i < 3; i++)
        s->feat[i] = (float)(s->sum[i] / (double)s->n_acc);
    s->feat[3] = (float)s->wafer;

    /* --- 표준화 (z) --- */
    /* 주의: 원시입력 직접 형태(B0 + sum(B*x))는 B0=104.6, 항들이 -50 규모라
     *       파괴적 상쇄로 float32에서 0.05um 오차가 발생한다.
     *       표준화 형태는 절편이 y평균(~44)이고 항들이 작아 수치적으로 안정. */
    double z[VM_NFEAT];
    for (i = 0; i < VM_NFEAT; i++)
        z[i] = ((double)s->feat[i] - (double)VM_MU[i]) / (double)VM_SD[i];

    /* --- 예측: pred = intercept_std + sum(coef_std[i]*z[i]) --- */
    double p = (double)VM_INTERCEPT_STD;
    for (i = 0; i < VM_NFEAT; i++)
        p += (double)VM_COEF_STD[i] * z[i];
    s->pred = (float)p;

    double h = 0.0;
    for (i = 0; i < VM_NFEAT; i++) {
        double acc = 0.0;
        for (j = 0; j < VM_NFEAT; j++)
            acc += (double)VM_M[i][j] * z[j];
        h += z[i] * acc;
    }
    if (h < 0.0) h = 0.0;            /* 수치오차 방어 */
    s->h  = (float)h;
    s->sd = (float)((double)VM_SIGMA * sqrt(1.0 + h));

    /* --- 판정: 신뢰구간 [pred-k*sd, pred+k*sd] 와 LSL 의 관계 --- */
    if (s->sd > VM_SD_LIMIT)                    s->verdict = VM_UNCERTAIN;
    else if (s->pred + vm_k * s->sd < vm_lsl)   s->verdict = VM_OOS;
    else if (s->pred - vm_k * s->sd > vm_lsl)   s->verdict = VM_OK;
    else                                        s->verdict = VM_BORDER;
}

int vm_push(vm_state_t *s, const float *x)
{
    s->n_sample++;

    if (s->phase == S_DONE) return VM_DONE;

    /* --- 1) 플라즈마 점화 검출 --- */
    if (s->phase == S_IDLE) {
        if (x[SIG_RF_POWER] <= TH_PLASMA_ON) return VM_WAIT;
        s->phase        = S_ACC;
        s->idx_plasma_on = s->n_sample - 1;
        s->sf6_prev     = x[SIG_SF6];
        /* 점화 샘플부터 누적 시작 (학습 정의와 동일) */
    }

    /* --- 2) SF6 상승엣지 카운트 --- */
    if (s->sf6_prev < TH_SF6_ON && x[SIG_SF6] >= TH_SF6_ON) {
        s->n_edge++;
        if (s->n_edge == 2) {            /* 2번째 엣지 = 1사이클 완료 */
            s->phase = S_DONE;
            if (s->n_acc > 0) { vm_infer(s); return VM_READY; }
            return VM_DONE;              /* 비정상: 누적 0 */
        }
    }
    s->sf6_prev = x[SIG_SF6];

    /* --- 3) 누적 --- */
    s->sum[0] += (double)x[SIG_TUNECAP];
    s->sum[1] += (double)x[SIG_REFLPWR];
    s->sum[2] += (double)x[SIG_PKPK];
    s->n_acc++;

    return VM_WAIT;
}

const char *vm_verdict_str(int v)
{
    switch (v) {
        case VM_OK:        return "OK";
        case VM_OOS:       return "OOS";
        case VM_BORDER:    return "BORDER";
        case VM_UNCERTAIN: return "UNCERTAIN";
        default:           return "?";
    }
}

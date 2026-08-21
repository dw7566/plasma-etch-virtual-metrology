/* vm_ipc.h - System V 공유메모리 / 세마포어 정의
 *
 * 다중 챔버 동시 감시 실험용.
 *   - 공유메모리: 챔버별 판정 결과 + 전역 통계
 *   - 카운팅 세마포어: 동시 판정 가능 챔버 수를 K로 제한 -> 경합 측정
 */
#ifndef VM_IPC_H
#define VM_IPC_H

#include <sys/types.h>

#define VM_SHM_KEY   0x564D3031      /* 'VM01' */
#define VM_SEM_KEY   0x564D3032      /* 'VM02' */
#define VM_MAX_RES   256
#define VM_MAX_CH     64

/* 세마포어 집합의 두 원소 — 역할이 다르므로 반드시 분리해야 한다.
 *   GATE : 초기값 K. 동시 판정 챔버 수를 제한해 '경합'을 측정하는 실험 장치.
 *          K>1 이면 정의상 여러 프로세스가 동시에 통과한다.
 *   BUF  : 초기값 1. 결과 버퍼(n_res)의 read-modify-write 를 보호하는 뮤텍스.
 * GATE 를 버퍼 보호에 겸용하면 K>1 에서 두 챔버가 같은 인덱스를 잡아
 * 서로의 판정 결과를 덮어쓴다. */
#define VM_SEM_GATE   0
#define VM_SEM_BUF    1
#define VM_NSEM       2

/* 웨이퍼 1장 판정 결과 */
typedef struct {
    int   ch;                 /* 챔버 번호 */
    int   lot, wafer;
    float feat[4];
    float pred, sd, h;
    int   verdict;
    long  infer_ns;           /* 추론 소요시간 */
    long  sem_wait_ns;        /* 세마포어 대기시간 */
    long  n_sample;           /* 판정까지 처리한 샘플 수 */
    long  n_acc;              /* 누적에 사용된 샘플 수 */
} vm_res_t;

/* 챔버별 런타임 통계 */
typedef struct {
    long n_sample;            /* 처리한 총 샘플 수 */
    long sum_push_ns;         /* vm_push 누적 시간 */
    long max_push_ns;
    long n_deadline_miss;     /* 샘플주기 초과 횟수 */
    long n_wafer;
    int  alive;
} vm_chstat_t;

typedef struct {
    int  n_ch;                /* 챔버 수 */
    int  sem_limit;           /* 동시 판정 허용 수 */
    int  realtime;            /* 1이면 5Hz 실시간 재생 */
    int  n_res;               /* 기록된 결과 수 */
    vm_res_t    res[VM_MAX_RES];
    vm_chstat_t st[VM_MAX_CH];
} vm_shm_t;

/* 세마포어 P/V */
int  vm_sem_wait(int semid);     /* GATE P — 동시 판정 K 제한 (대기시간이 B4 측정값) */
int  vm_sem_post(int semid);     /* GATE V */
int  vm_buf_lock(int semid);     /* BUF  P — 결과 버퍼 배타 접근 */
int  vm_buf_unlock(int semid);   /* BUF  V */

#endif

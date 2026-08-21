/* vm_master.c - 다중 챔버 가상계측 벤치마크
 *
 *   ./vm_master -d <replay_dir> [-c 챔버수] [-k 동시판정한도] [-r] [-o out.csv]
 *      -c N   챔버(프로세스) 수            기본 1
 *      -k K   동시 판정 허용 수 (세마포어)  기본 = N (무제한)
 *      -r     실시간 재생 (5Hz). 없으면 최고속
 *      -o F   결과 CSV 저장
 *
 * 각 챔버는 독립 프로세스로 fork 되어 자기에게 배정된 웨이퍼 파일들을
 * 순차 재생하며, 판정 시점에 세마포어를 잡고 공유메모리에 결과를 쓴다.
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <dirent.h>
#include <errno.h>
#include <time.h>
#include <math.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <sys/sem.h>
#include <sys/wait.h>
#include "vm_engine.h"
#include "vm_ipc.h"

#define MAX_FILES 512
#define HDR_BYTES 24

static vm_shm_t *g_shm = NULL;
static int g_semid = -1;

/* ---------- 세마포어 ---------- */
union semun { int val; struct semid_ds *buf; unsigned short *array; };

static int sem_op(int semid, unsigned short idx, short delta)
{
    struct sembuf o; o.sem_num = idx; o.sem_op = delta; o.sem_flg = 0;
    return semop(semid, &o, 1);
}
int vm_sem_wait(int semid)   { return sem_op(semid, VM_SEM_GATE, -1); }
int vm_sem_post(int semid)   { return sem_op(semid, VM_SEM_GATE, +1); }
int vm_buf_lock(int semid)   { return sem_op(semid, VM_SEM_BUF,  -1); }
int vm_buf_unlock(int semid) { return sem_op(semid, VM_SEM_BUF,  +1); }

static inline long ns_now(void)
{
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1000000000L + t.tv_nsec;
}

/* ---------- 재생 파일 ---------- */
typedef struct { int lot, wafer, nsamp; float dt; float *d; } wafer_t;

static int g_maxsamp = 0;      /* 0 = 전체 */
static int g_repeat  = 1;      /* 데이터셋 반복 횟수 (내구시험용) */

static int load_wafer(const char *path, wafer_t *w)
{
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "open %s: %s\n", path, strerror(errno)); return -1; }
    int hdr[5]; float dt;
    if (fread(hdr, 4, 5, f) != 5 || fread(&dt, 4, 1, f) != 1) { fclose(f); return -1; }
    if (hdr[0] != 0x564D5730) { fprintf(stderr, "%s: bad magic\n", path); fclose(f); return -1; }
    w->lot = hdr[1]; w->wafer = hdr[2]; w->nsamp = hdr[3]; w->dt = dt;
    if (hdr[4] != VM_NSIG) { fprintf(stderr, "%s: nsig=%d\n", path, hdr[4]); fclose(f); return -1; }
    size_t n = (size_t)w->nsamp * VM_NSIG;
    w->d = malloc(n * sizeof(float));
    if (!w->d || fread(w->d, sizeof(float), n, f) != n) { fclose(f); return -1; }
    fclose(f);
    return 0;
}

/* ---------- 챔버 프로세스 ---------- */
static void chamber_run(int ch, char **files, int nf, const char *dir)
{
    vm_chstat_t *st = &g_shm->st[ch];
    st->alive = 1;
    char path[1024];

    for (int rep = 0; rep < g_repeat; rep++)
    for (int k = 0; k < nf; k++) {
        wafer_t w;
        snprintf(path, sizeof(path), "%s/%s", dir, files[k]);
        if (load_wafer(path, &w) < 0) continue;

        vm_state_t s;
        vm_init(&s, w.wafer);
        long next = ns_now();
        long period = (long)(w.dt * 1e9f);

        int lim = (g_maxsamp > 0 && g_maxsamp < w.nsamp) ? g_maxsamp : w.nsamp;
        for (int i = 0; i < lim; i++) {
            if (g_shm->realtime) {
                next += period;
                long now = ns_now();
                if (now < next) {
                    struct timespec ts = { (next-now)/1000000000L, (next-now)%1000000000L };
                    nanosleep(&ts, NULL);
                } else if (now - next > period) {
                    st->n_deadline_miss++;
                }
            }
            long t0 = ns_now();
            int r = vm_push(&s, &w.d[(size_t)i * VM_NSIG]);
            long el = ns_now() - t0;
            st->n_sample++; st->sum_push_ns += el;
            if (el > st->max_push_ns) st->max_push_ns = el;

            if (r == VM_READY) {
                /* --- 판정 결과 기록 --- */
                /* GATE: 동시 판정 수를 K 로 제한. 이 대기시간만이 B4 의 측정 대상이므로
                 *       버퍼 뮤텍스 대기가 섞이지 않도록 여기서 먼저 끊는다. */
                long w0 = ns_now();
                vm_sem_wait(g_semid);
                long wns = ns_now() - w0;

                /* BUF: K>1 이면 GATE 를 통과한 프로세스가 여럿이므로
                 *      n_res 증가는 별도 뮤텍스로 직렬화해야 한다. */
                vm_buf_lock(g_semid);
                int idx = g_shm->n_res;
                if (idx < VM_MAX_RES) {
                    vm_res_t *o = &g_shm->res[idx];
                    o->ch = ch; o->lot = w.lot; o->wafer = w.wafer;
                    memcpy(o->feat, s.feat, sizeof(o->feat));
                    o->pred = s.pred; o->sd = s.sd; o->h = s.h;
                    o->verdict = s.verdict; o->infer_ns = el;
                    o->sem_wait_ns = wns; o->n_sample = s.n_sample; o->n_acc = s.n_acc;
                    g_shm->n_res = idx + 1;
                }
                vm_buf_unlock(g_semid);

                vm_sem_post(g_semid);

                if (!g_shm->realtime) break;   /* 최고속 모드: 판정 후 다음 웨이퍼 */
            }
        }
        st->n_wafer++;
        free(w.d);
    }
    st->alive = 0;
    _exit(0);
}

/* ---------- main ---------- */
int main(int argc, char **argv)
{
    const char *dir = NULL, *outcsv = NULL;
    int nch = 1, klim = -1, rt = 0, c;
    while ((c = getopt(argc, argv, "d:c:k:ro:t:L:n:R:h")) != -1) {
        switch (c) {
        case 'd': dir = optarg; break;
        case 'c': nch = atoi(optarg); break;
        case 'k': klim = atoi(optarg); break;
        case 'r': rt = 1; break;
        case 'o': outcsv = optarg; break;
        case 't': vm_k   = (float)atof(optarg); break;
        case 'L': vm_lsl = (float)atof(optarg); break;
        case 'n': g_maxsamp = atoi(optarg); break;
        case 'R': g_repeat  = atoi(optarg); if (g_repeat < 1) g_repeat = 1; break;
        default:
            printf("usage: %s -d <dir> [옵션]\n", argv[0]);
            printf("  -c N   챔버(프로세스) 수            기본 1\n");
            printf("  -k K   동시 판정 허용 수 (세마포어)  기본 = N\n");
            printf("  -r     실시간 재생 (5Hz)            기본 최고속\n");
            printf("  -n N   웨이퍼당 최대 샘플 수         기본 전체(3245)\n");
            printf("  -R N   데이터셋 반복 횟수 (내구시험) 기본 1\n");
            printf("  -t K   신뢰구간 배수                기본 1.0\n");
            printf("  -L X   관리하한 [um]                기본 %.3f\n", SPEC_LSL);
            printf("  -o F   결과 CSV\n");
            return 1;
        }
    }
    if (!dir) { fprintf(stderr, "-d <replay_dir> 필요\n"); return 1; }
    if (nch < 1 || nch > VM_MAX_CH) { fprintf(stderr, "챔버수 1~%d\n", VM_MAX_CH); return 1; }
    if (klim < 1) klim = nch;

    /* 재생 파일 목록 */
    char *files[MAX_FILES]; int nf = 0;
    DIR *dp = opendir(dir);
    if (!dp) { fprintf(stderr, "opendir %s: %s\n", dir, strerror(errno)); return 1; }
    struct dirent *de;
    while ((de = readdir(dp)) && nf < MAX_FILES) {
        size_t L = strlen(de->d_name);
        if (L > 4 && !strcmp(de->d_name + L - 4, ".bin")) files[nf++] = strdup(de->d_name);
    }
    closedir(dp);
    if (!nf) { fprintf(stderr, "%s 에 .bin 없음\n", dir); return 1; }
    /* 파일명 정렬 */
    for (int i = 0; i < nf; i++) for (int j = i+1; j < nf; j++)
        if (strcmp(files[i], files[j]) > 0) { char *t=files[i]; files[i]=files[j]; files[j]=t; }

    /* 공유메모리 */
    int shmid = shmget(VM_SHM_KEY, sizeof(vm_shm_t), IPC_CREAT | 0666);
    if (shmid < 0) { perror("shmget"); return 1; }
    g_shm = shmat(shmid, NULL, 0);
    if (g_shm == (void*)-1) { perror("shmat"); return 1; }
    memset(g_shm, 0, sizeof(*g_shm));
    g_shm->n_ch = nch; g_shm->sem_limit = klim; g_shm->realtime = rt;

    /* 세마포어 집합 2개: [0] GATE=K (경합 측정), [1] BUF=1 (결과 버퍼 뮤텍스) */
    g_semid = semget(VM_SEM_KEY, VM_NSEM, IPC_CREAT | 0666);
    if (g_semid < 0 && errno == EINVAL) {
        /* 구버전(1개짜리) 집합이 남아 있으면 제거 후 재생성 */
        int stale = semget(VM_SEM_KEY, 1, 0666);
        if (stale >= 0) semctl(stale, 0, IPC_RMID);
        g_semid = semget(VM_SEM_KEY, VM_NSEM, IPC_CREAT | 0666);
    }
    if (g_semid < 0) { perror("semget"); return 1; }
    union semun su;
    su.val = klim;
    if (semctl(g_semid, VM_SEM_GATE, SETVAL, su) < 0) { perror("semctl GATE"); return 1; }
    su.val = 1;
    if (semctl(g_semid, VM_SEM_BUF, SETVAL, su) < 0) { perror("semctl BUF"); return 1; }

    printf("=== BOSCH 식각 가상계측 다중챔버 벤치마크 ===\n");
    printf("모델      : %s  (LOLO R2 0.8554, sigma %.4f um)\n", VM_MODEL_VERSION, VM_SIGMA);
    printf("재생파일  : %d 개 (%s)\n", nf, dir);
    printf("챔버수    : %d  | 동시판정한도 K = %d  | 모드 = %s\n",
           nch, klim, rt ? "실시간 5Hz" : "최고속");
    printf("판정기준  : LSL = %.3f um,  신뢰배수 k = %.2f\n", vm_lsl, vm_k);
    if (g_maxsamp) printf("샘플제한  : 웨이퍼당 %d 개 (%.1f s 상당)\n", g_maxsamp, g_maxsamp*0.2);
    if (g_repeat>1) printf("반복      : %d 회\n", g_repeat);
    printf("---------------------------------------------\n");

    long T0 = ns_now();
    for (int ch = 0; ch < nch; ch++) {
        pid_t pid = fork();
        if (pid < 0) { perror("fork"); return 1; }
        if (pid == 0) {
            /* 웨이퍼를 라운드로빈 배정 */
            char *mine[MAX_FILES]; int nm = 0;
            for (int i = ch; i < nf; i += nch) mine[nm++] = files[i];
            chamber_run(ch, mine, nm, dir);
        }
    }
    int status; while (wait(&status) > 0) {}
    double T = (ns_now() - T0) / 1e9;

    /* ---------- 집계 ---------- */
    long tot_s = 0, tot_ns = 0, maxp = 0, miss = 0, tot_w = 0;
    for (int i = 0; i < nch; i++) {
        tot_s  += g_shm->st[i].n_sample;
        tot_ns += g_shm->st[i].sum_push_ns;
        tot_w  += g_shm->st[i].n_wafer;
        if (g_shm->st[i].max_push_ns > maxp) maxp = g_shm->st[i].max_push_ns;
        miss += g_shm->st[i].n_deadline_miss;
    }
    double sem_avg = 0, sem_max = 0, inf_avg = 0;
    int n = g_shm->n_res;
    for (int i = 0; i < n; i++) {
        sem_avg += g_shm->res[i].sem_wait_ns;
        inf_avg += g_shm->res[i].infer_ns;
        if (g_shm->res[i].sem_wait_ns > sem_max) sem_max = g_shm->res[i].sem_wait_ns;
    }
    if (n) { sem_avg /= n; inf_avg /= n; }

    printf("\n[처리량]\n");
    printf("  경과시간        %.3f s\n", T);
    printf("  웨이퍼          %ld 장  (판정 %d 건)\n", tot_w, n);
    printf("  샘플            %ld 개  -> %.0f 샘플/s\n", tot_s, tot_s / T);
    printf("  샘플당 처리     평균 %.0f ns   최대 %ld ns\n", tot_s ? (double)tot_ns/tot_s : 0.0, maxp);
    printf("  판정 1회        평균 %.0f ns\n", inf_avg);
    printf("\n[실시간성]\n");
    if (rt) {
        printf("  샘플주기 200ms 대비 여유율  %.0f 배\n", 200e6 / (tot_s ? (double)tot_ns/tot_s : 1));
        printf("  마감 초과 횟수              %ld / %ld  (%.4f%%)\n", miss, tot_s, tot_s ? 100.0*miss/tot_s : 0);
    } else {
        printf("  (최고속 모드 - 마감 측정 없음)\n");
        printf("  샘플주기 200ms 대비 여유율  %.0f 배\n", 200e6 / (tot_s ? (double)tot_ns/tot_s : 1));
    }
    printf("\n[세마포어 경합]  K = %d\n", klim);
    printf("  대기시간 평균 %.0f ns   최대 %.0f ns\n", sem_avg, sem_max);

    printf("\n[판정 분포]  (LSL %.3f, k=%.2f)\n", vm_lsl, vm_k);
    int cnt[4] = {0,0,0,0};
    for (int i = 0; i < n; i++) if (g_shm->res[i].verdict >= 0 && g_shm->res[i].verdict < 4)
        cnt[g_shm->res[i].verdict]++;
    printf("  OK(계측생략) %d   OOS(조기중단) %d   BORDER(계측필요) %d   UNCERTAIN %d\n",
           cnt[0], cnt[1], cnt[2], cnt[3]);
    if (n) printf("  -> 실계측 생략률 %.1f%%   조기중단 대상 %.1f%%\n",
           100.0*cnt[0]/n, 100.0*cnt[1]/n);

    if (outcsv) {
        FILE *f = fopen(outcsv, "w");
        if (f) {
            fprintf(f, "ch,lot,wafer,n_sample,n_acc,tunecap,reflpwr,pkpk,pred,sd,h,verdict,infer_ns,sem_wait_ns\n");
            for (int i = 0; i < n; i++) {
                vm_res_t *o = &g_shm->res[i];
                fprintf(f, "%d,%d,%d,%ld,%ld,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%s,%ld,%ld\n",
                    o->ch, o->lot, o->wafer, o->n_sample, o->n_acc,
                    o->feat[0], o->feat[1], o->feat[2],
                    o->pred, o->sd, o->h, vm_verdict_str(o->verdict),
                    o->infer_ns, o->sem_wait_ns);
            }
            fclose(f);
            printf("\n결과 저장: %s\n", outcsv);
        }
    }

    shmdt(g_shm);
    shmctl(shmid, IPC_RMID, NULL);
    semctl(g_semid, 0, IPC_RMID);
    return 0;
}

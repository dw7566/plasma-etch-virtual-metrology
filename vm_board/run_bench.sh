#!/bin/sh
# 보드에서 실행: 다중 챔버 스윕 벤치마크
# 사용법:  ./run_bench.sh <replay_dir> [bin]
D=${1:-./replay}
B=${2:-./vm_master}
H=/sys/class/hwmon/hwmon0
LOG=/tmp/vm_bench.log
: > $LOG

echo "재생 데이터: $D  ($(ls $D/*.bin 2>/dev/null | wc -l) 웨이퍼)" | tee -a $LOG
echo "실행 바이너리: $B" | tee -a $LOG
echo | tee -a $LOG

# ---------------------------------------------------------------------------
# ⚠ PVT 주기 폴링 — README §9-12 의 제약과 충돌한다.
#   지속 부하(B6) 중 벤더 감시 데몬과 이 루프가 동일 PVT 를 동시에 읽어
#   3379.4 C 오독 -> 시스템 halt 가 발생한 적이 있다.
#   B6(-R 반복) 실행 시에는 이 블록을 끄고 부하 전후 단발 읽기만 사용할 것.
#   PVT_POLL=0 ./run_bench.sh ... 로 비활성화한다.
# ---------------------------------------------------------------------------
PVT_POLL=${PVT_POLL:-1}
if [ -d $H ] && [ "$PVT_POLL" = "1" ]; then
  ( while true; do
      printf "%s" "$(cut -d' ' -f1 /proc/uptime)"
      for i in 1 2 3 4; do printf " %s" "$(cat $H/temp${i}_input)"; done
      for i in 0 1 2 3; do printf " %s" "$(cat $H/in${i}_input)"; done
      printf "\n"; sleep 1
    done ) > /tmp/vm_pvt.log &
  MON=$!
  echo "PVT 로깅 시작 (pid $MON)" | tee -a $LOG
  sleep 5
fi

# 1) 정확성 검증 (챔버 1개, 최고속)
echo "=== [1] 정확성 검증 ===" | tee -a $LOG
$B -d "$D" -c 1 -o /tmp/vm_out_c1.csv 2>&1 | tee -a $LOG

# 2) 챔버 수 스윕 (최고속) - 처리량 한계
echo "" | tee -a $LOG
echo "=== [2] 챔버 수 스윕 (최고속) ===" | tee -a $LOG
for C in 1 2 4 8 16; do
  echo "--- 챔버 $C ---" | tee -a $LOG
  $B -d "$D" -c $C -k $C 2>&1 | grep -E "샘플 |샘플당|판정 1회|경과시간|여유율" | tee -a $LOG
done

# 3) 실시간 5Hz 모드 - 마감 준수
echo "" | tee -a $LOG
echo "=== [3] 실시간 5Hz 마감 준수 ===" | tee -a $LOG
for C in 1 4 8 16 32; do
  echo "--- 챔버 $C ---" | tee -a $LOG
  $B -d "$D" -c $C -k $C -r 2>&1 | grep -E "샘플 |샘플당|마감|여유율" | tee -a $LOG
done

# 4) 세마포어 한도 변화 - 경합 측정
echo "" | tee -a $LOG
echo "=== [4] 세마포어 경합 (챔버 8개 고정) ===" | tee -a $LOG
for K in 1 2 4 8; do
  echo "--- K=$K ---" | tee -a $LOG
  $B -d "$D" -c 8 -k $K 2>&1 | grep -E "대기시간|경과시간" | tee -a $LOG
done

[ -n "$MON" ] && { sleep 5; kill $MON; echo "" | tee -a $LOG; echo "PVT: $(wc -l < /tmp/vm_pvt.log) 샘플 -> /tmp/vm_pvt.log" | tee -a $LOG; }
echo "" | tee -a $LOG
echo "전체 로그: $LOG" | tee -a $LOG

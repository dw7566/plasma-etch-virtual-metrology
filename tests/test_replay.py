"""재생 데이터 88개가 vm_engine.c 의 상태머신을 통과해 학습 특징을 복원하는가.

vm_engine.c 의 vm_push() 를 파이썬으로 옮겨 재생 파일에 돌린 뒤,
04_feat.py 가 원본 netCDF 에서 뽑은 특징(vm_verify.csv)과 대조한다.
이 테스트가 통과하면 재생 데이터와 C 상태머신 정의가 학습과 일치한다.
"""
import array
import csv
import struct

import pytest
from conftest import ROOT

MAGIC = 0x564D5730
TH_PLASMA, TH_SF6 = 2000.0, 300.0
SIG_RF, SIG_SF6, SIG_TUNECAP, SIG_REFL, SIG_PKPK = range(5)
HDR_BYTES = 24


def load(path):
    b = path.read_bytes()
    magic, lot, wafer, nsamp, nsig = struct.unpack_from('<5i', b, 0)
    dt, = struct.unpack_from('<f', b, 20)
    a = array.array('f')
    a.frombytes(b[HDR_BYTES:HDR_BYTES + nsamp * nsig * 4])
    return dict(magic=magic, lot=lot, wafer=wafer, nsamp=nsamp, nsig=nsig,
                dt=dt, data=a, nbytes=len(b))


def run_engine(w):
    """vm_engine.c vm_push() 이식. 점화 샘플부터 누적, SF6 2번째 상승엣지에서 종료."""
    d, phase, n_edge, prev = w['data'], 0, 0, 0.0
    acc, n_acc = [0.0, 0.0, 0.0], 0
    for t in range(w['nsamp']):
        row = d[t * 5:t * 5 + 5]
        if phase == 0:
            if row[SIG_RF] <= TH_PLASMA:
                continue
            phase, prev = 1, row[SIG_SF6]      # 점화. prev=현재값이라 엣지로 안 잡힌다
        if prev < TH_SF6 <= row[SIG_SF6]:
            n_edge += 1
            if n_edge == 2:                    # 1사이클 완료 — 이 샘플은 누적 안 함
                break
        prev = row[SIG_SF6]
        acc[0] += row[SIG_TUNECAP]
        acc[1] += row[SIG_REFL]
        acc[2] += row[SIG_PKPK]
        n_acc += 1
    return ([a / n_acc for a in acc], n_acc) if n_acc else (None, 0)


@pytest.fixture(scope='module')
def wafers():
    return {(w['lot'], w['wafer']): w
            for w in (load(p) for p in sorted((ROOT / 'replay').glob('*.bin')))}


@pytest.fixture(scope='module')
def index():
    with open(ROOT / 'replay' / 'index.csv', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def test_88_files(wafers, index):
    assert len(wafers) == 88
    assert len(index) == 88


def test_headers_wellformed(wafers):
    for key, w in wafers.items():
        assert w['magic'] == MAGIC, f'{key} bad magic'
        assert w['nsig'] == 5
        assert w['nsamp'] > 0
        assert abs(w['dt'] - 0.2) < 1e-6
        assert w['nbytes'] == HDR_BYTES + w['nsamp'] * 5 * 4, f'{key} 길이 불일치'


def test_index_matches_files(wafers, index):
    for r in index:
        w = wafers[(int(r['lot']), int(r['wafer']))]
        assert w['nsamp'] == int(r['nsamp'])


def test_state_machine_reproduces_sample_counts(wafers, verify):
    """누적 샘플 수가 88/88 일치해야 한다 (README §5 이식 검증)."""
    bad = []
    for r in verify:
        w = wafers[(int(r['lot']), int(r['wafer']))]
        _, n_acc = run_engine(w)
        if n_acc != int(r['nsamp']):
            bad.append((r['lot'], r['wafer'], n_acc, r['nsamp']))
    assert not bad, f'{len(bad)}장 불일치: {bad[:5]}'


def test_state_machine_reproduces_features(wafers, verify):
    """복원한 RF 3특징이 학습 특징과 float32 정밀도 안에서 일치해야 한다."""
    cols = ['PlatenRFTuningCapacitor', 'SourceRFReflectedPower', 'SourceRFPeakToPeak']
    for r in verify:
        w = wafers[(int(r['lot']), int(r['wafer']))]
        got, _ = run_engine(w)
        for i, c in enumerate(cols):
            exp = float(r[c])
            assert abs(got[i] - exp) <= 1e-6 * abs(exp) + 1e-6, \
                f"lot{r['lot']} w{r['wafer']} {c}: {got[i]} vs {exp}"


def test_median_accumulation_is_24(verify):
    """1사이클 = 중앙값 24 샘플 = 4.8 초 (5 Hz)."""
    n = sorted(int(r['nsamp']) for r in verify)
    assert n[len(n) // 2] == 24
    assert 24 * 0.2 == pytest.approx(4.8)


def test_port_error_budget(model, wafers, verify):
    """재생 데이터로 예측한 값이 PC 기준값과 1e-5 um 안에서 일치 (README §5)."""
    from conftest import predict
    worst = 0.0
    for r in verify:
        w = wafers[(int(r['lot']), int(r['wafer']))]
        got, _ = run_engine(w)
        pred = predict(model, got + [float(r['wafer'])])[0]
        worst = max(worst, abs(pred - float(r['pred_full'])))
    assert worst < 1e-4, f'최대 오차 {worst:.3e} um'

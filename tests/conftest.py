"""저장소 자산만으로 도는 검증. Zenodo 데이터도 scikit-learn도 필요 없다."""
import csv
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

LSL = 43.554
SD_LIMIT = 0.220
K = 1.0


@pytest.fixture(scope='session')
def root():
    return ROOT


@pytest.fixture(scope='session')
def model():
    with open(ROOT / 'vm_model.json', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture(scope='session')
def verify():
    with open(ROOT / 'vm_verify.csv', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def predict(m, x, k=K):
    """vm_engine.c 의 vm_infer() 와 동일한 계산 순서."""
    z = [(x[i] - m['scaler_mean'][i]) / m['scaler_scale'][i] for i in range(4)]
    pred = m['intercept_std'] + sum(m['coef_std'][i] * z[i] for i in range(4))
    h = sum(z[i] * sum(m['leverage_matrix'][i][j] * z[j] for j in range(4))
            for i in range(4))
    h = max(0.0, h)
    sd = m['sigma'] * (1.0 + h) ** 0.5
    if sd > SD_LIMIT:
        v = 'UNCERTAIN'
    elif pred + k * sd < LSL:
        v = 'OOS'
    elif pred - k * sd > LSL:
        v = 'OK'
    else:
        v = 'BORDER'
    return pred, sd, v


def feats(row):
    return [float(row['PlatenRFTuningCapacitor']),
            float(row['SourceRFReflectedPower']),
            float(row['SourceRFPeakToPeak']),
            float(row['wafer'])]

"""저장소 산출물끼리 어긋나지 않는가.

vm_model.h 는 자동생성 헤더라 vm_model.json 과 벌어지기 쉽다.
model_comparison_full.csv 는 README §2 표의 근거다.
"""
import csv
import re

import pytest
from conftest import ROOT


# ------------------------------------------------------------------ vm_model.h
def parse_header():
    txt = (ROOT / 'vm_board' / 'vm_model.h').read_text(encoding='utf-8')
    num = r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?'

    def arr(name):
        m = re.search(rf'{name}\[[^\]]*\]\s*=\s*\{{(.*?)\}};', txt, re.S)
        return [float(x) for x in re.findall(num + r'(?=f)', m.group(1))]

    def scalar(name):
        m = re.search(rf'{name}\s*=\s*({num})f', txt)
        return float(m.group(1))

    m = re.search(r'VM_M\[VM_NFEAT\]\[VM_NFEAT\]\s*=\s*\{(.*?)\n\};', txt, re.S)
    rows = [[float(x) for x in re.findall(num + r'(?=f)', r)]
            for r in re.findall(r'\{([^{}]*)\}', m.group(1))]

    return dict(
        intercept_std=scalar('VM_INTERCEPT_STD'),
        coef_std=arr('VM_COEF_STD'),
        scaler_mean=arr('VM_MU'),
        scaler_scale=arr('VM_SD'),
        sigma=float(re.search(rf'#define VM_SIGMA\s+({num})f', txt).group(1)),
        lsl=float(re.search(rf'#define SPEC_LSL\s+({num})f', txt).group(1)),
        leverage_matrix=rows,
    )


@pytest.fixture(scope='module')
def header():
    return parse_header()


@pytest.mark.parametrize('key', ['coef_std', 'scaler_mean', 'scaler_scale'])
def test_header_vectors_match_json(header, model, key):
    got, exp = header[key], model[key]
    assert len(got) == len(exp) == 4
    for g, e in zip(got, exp):
        assert g == pytest.approx(e, rel=1e-9), f'{key}: {g} vs {e}'


def test_header_scalars_match_json(header, model):
    assert header['intercept_std'] == pytest.approx(model['intercept_std'], rel=1e-9)
    assert header['sigma'] == pytest.approx(model['sigma'], rel=1e-9)


def test_header_leverage_matrix_matches_json(header, model):
    for i, (gr, er) in enumerate(zip(header['leverage_matrix'], model['leverage_matrix'])):
        for j, (g, e) in enumerate(zip(gr, er)):
            assert g == pytest.approx(e, rel=1e-8), f'VM_M[{i}][{j}]'


def test_header_lsl_matches_tests(header):
    from conftest import LSL
    assert header['lsl'] == pytest.approx(LSL)


def test_feature_order_documented(model):
    assert model['features'] == ['PlatenRFTuningCapacitor', 'SourceRFReflectedPower',
                                 'SourceRFPeakToPeak', 'wafer']


# ------------------------------------------------- model_comparison_full.csv
@pytest.fixture(scope='module')
def comparison():
    with open(ROOT / 'model_comparison_full.csv', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def test_comparison_row_count(comparison):
    """5 특징셋 x 13 모델 = 65, + baseline 1 + PLS(k=5,8) 2 = 68."""
    assert len(comparison) == 68
    assert len({(r['feat'], r['model']) for r in comparison}) == 68


def test_comparison_backs_readme_table(comparison):
    """README §2 의 '구성별 최고 모델' 표."""
    best = {}
    for r in comparison:
        f, r2 = r['feat'], float(r['R2'])
        if f not in best or r2 > best[f][1]:
            best[f] = (r['model'], r2)
    expect = {
        '[기준] 순서만':        ('Ridge',      0.7019),
        '[1사이클] RF3만':      ('GPR-RBF',    0.1430),
        '[1사이클] RF3+순서':   ('GPR-Matern', 0.8775),
        '[전공정] RF3만':       ('GPR-Matern', 0.8399),
        '[전공정] RF3+순서':    ('GPR-Matern', 0.9058),
        '[전공정] 전체27+순서': ('LassoCV',    0.9325),
    }
    assert set(best) == set(expect)
    for f, (mdl, r2) in expect.items():
        assert best[f][0] == mdl, f'{f}: 최고 모델이 {best[f][0]}'
        assert best[f][1] == pytest.approx(r2, abs=5e-5)


def test_deployed_ridge_matches_model_json(comparison, model):
    """배포 모델(1사이클 4특징 Ridge)의 LOLO R2/RMSE 가 vm_model.json 과 일치."""
    row = next(r for r in comparison
               if r['feat'] == '[1사이클] RF3+순서' and r['model'] == 'Ridge(a=0.1)')
    assert float(row['R2']) == pytest.approx(model['lolo_r2'], rel=1e-9)
    assert float(row['RMSE']) == pytest.approx(model['sigma'], rel=1e-9)


def test_mlp_fails_everywhere(comparison):
    """README §3 의 근거: MLP 는 전 조건에서 음수 R2."""
    mlp = [float(r['R2']) for r in comparison if r['model'].startswith('MLP')]
    assert len(mlp) == 5
    assert all(r2 < 0 for r2 in mlp)
    assert min(mlp) == pytest.approx(-357124.7729, rel=1e-6)


def test_lasso_survives_where_ridge_diverges(comparison):
    """§2-② 28특징에서는 정규화 종류가 결정적이다."""
    rows = {r['model']: float(r['R2']) for r in comparison
            if r['feat'] == '[전공정] 전체27+순서'}
    assert rows['LassoCV'] > 0.93
    assert rows['Ridge(a=0.1)'] < -1.0
    assert rows['PLS(k=1)'] < -16.0

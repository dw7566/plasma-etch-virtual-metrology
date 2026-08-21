"""vm_model.json 이 vm_verify.csv 를 재현하는가 + README §4 수치 검증."""
from conftest import LSL, feats, predict


def test_verify_has_88_wafers(verify):
    assert len(verify) == 88
    assert len({(r['lot'], r['wafer']) for r in verify}) == 88


def test_predictions_match_pred_full(model, verify):
    """배포 계수로 다시 계산한 예측이 PC 기준값(pred_full)과 일치해야 한다.

    pred (LOLO 교차검증 예측) 가 아니라 pred_full (전체학습 모델) 이 대조 기준이다.
    LOLO 는 fold 마다 다른 모델이라 원래 값이 다르다. (README §9-9)
    """
    worst = max(abs(predict(model, feats(r))[0] - float(r['pred_full']))
                for r in verify)
    assert worst < 1e-5, f'최대 오차 {worst:.3e} um'


def test_sd_matches(model, verify):
    worst = max(abs(predict(model, feats(r))[1] - float(r['sd'])) for r in verify)
    assert worst < 1e-6, f'최대 오차 {worst:.3e}'


def test_verdict_distribution(model, verify):
    """README §5 실행 화면의 판정 분포."""
    counts = {}
    for r in verify:
        v = predict(model, feats(r))[2]
        counts[v] = counts.get(v, 0) + 1
    assert counts == {'OK': 67, 'BORDER': 19, 'OOS': 2}


def test_skip_rate_and_missed_detections(model, verify):
    """§4 판정 규칙의 실효: k=1.0 에서 생략 76.1%, 미검출 0."""
    ok_depths = [float(r['depth']) for r in verify
                 if predict(model, feats(r))[2] == 'OK']
    assert len(ok_depths) == 67
    assert round(len(ok_depths) / len(verify) * 100, 1) == 76.1
    assert sum(1 for d in ok_depths if d < LSL) == 0, '규격이탈 미검출 발생'
    assert round(min(ok_depths), 3) == 43.585
    assert min(ok_depths) > LSL


def test_point_estimate_misses_four(model, verify):
    """불확실성을 빼면(k=0) 미검출 4건 — 불확실성 추정의 실효 근거."""
    ok = [float(r['depth']) for r in verify
          if predict(model, feats(r), k=0.0)[2] == 'OK']
    assert sum(1 for d in ok if d < LSL) == 4


def test_dataset_actually_has_excursions(verify):
    """판정 문제가 자명하지 않음을 확인 — 실제 규격이탈이 12장 있다."""
    assert sum(1 for r in verify if float(r['depth']) < LSL) == 12


def test_sigma_is_lolo_rmse(model):
    """배포 sigma 는 학습 잔차가 아니라 LOLO RMSE 여야 한다 (05b_fit_deploy.py)."""
    assert abs(model['sigma'] - 0.15049298773322664) < 1e-12
    assert abs(model['lolo_r2'] - 0.8553638151647743) < 1e-12
    assert model['n_train'] == 88

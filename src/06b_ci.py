"""§6b — n=88 방어. 모든 비율에 Wilson 신뢰구간을 병기한다.
미검출 0/67 은 '0%'가 아니라 '95% 상한 5.4%' 다."""
import numpy as np

def wilson(k, n, z=1.96):
    p = k/n; d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return max(0.0, c-h), min(1.0, c+h)

for label, k, n in [('생략률', 67, 88), ('미검출률(OK중)', 0, 67),
                    ('1sd 포함 GPR', 60, 88), ('1sd 포함 Ridge', 55, 88)]:
    lo, hi = wilson(k, n)
    print(f'{label:18s} {k:3d}/{n:3d} = {k/n*100:5.1f}%   95% CI [{lo*100:5.1f}, {hi*100:5.1f}]')
print('\nGPR/Ridge 구간이 겹치므로 캘리브레이션 우위는 통계적으로 유의하지 않다.')

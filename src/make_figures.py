"""figs/ 생성. 01~04, oes_gate4 를 먼저 실행해야 한다."""
import pandas as pd, numpy as np, pickle, os
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats

os.makedirs('figs', exist_ok=True)
plt.rcParams.update({'figure.dpi':140, 'font.size':10, 'axes.grid':True,
                     'grid.alpha':0.3, 'axes.spines.top':False, 'axes.spines.right':False})

# Fig 1 — 드리프트
d = pd.read_csv('data/Si_Oxide_etch_89_points.csv').dropna(subset=['stepheight'])
w = d.groupby(['lot_number','wafer_number']).stepheight.mean().reset_index()
w.columns = ['lot','wafer','depth']
fig, ax = plt.subplots(1, 2, figsize=(11,4))
for lot, g in w.groupby('lot'):
    g = g.sort_values('wafer')
    ax[0].plot(g.wafer, g.depth, 'o-', alpha=.55, lw=1.2, ms=4, label=f'lot {lot}')
ax[0].set_xlabel('Wafer order in lot'); ax[0].set_ylabel('Etch depth [um]')
ax[0].set_title('Etch depth per lot - all 10 lots decrease'); ax[0].legend(fontsize=7, ncol=2)
nz = pd.concat([g.sort_values('wafer').assign(dz=lambda x: x.depth-x.depth.iloc[0])
                for _, g in w.groupby('lot')])
s = stats.linregress(nz.wafer, nz.dz)
ax[1].scatter(nz.wafer, nz.dz, s=22, alpha=.55, color='#2b6cb0')
xs = np.array([1,10])
ax[1].plot(xs, s.intercept+s.slope*xs, 'r-', lw=2,
           label=f'{s.slope:.4f} um/wafer\nR2={s.rvalue**2:.3f}, p={s.pvalue:.1e}')
ax[1].set_xlabel('Wafer order'); ax[1].set_ylabel('Drift vs wafer 1 [um]')
ax[1].set_title('Normalized drift (n=88)'); ax[1].legend()
plt.tight_layout(); plt.savefig('figs/fig1_drift.png', bbox_inches='tight'); plt.close()

# Fig 2 — 판정 k 스윕
MEAN=np.array([31.594624,235.833020,3183.828880,5.170455])
SCALE=np.array([0.843497,5.914905,14.850293,2.857294])
COEF=np.array([-0.16945869,-0.07170805,-0.23648162,-0.38696030])
B0,SIGMA,LSL=44.011698110316644,0.15049298773322664,43.554
M=np.array([[0.07014046,-0.00754927,0.06827679,0.00724730],
            [-0.00754927,0.01513164,-0.01341293,0.00065064],
            [0.06827679,-0.01341293,0.08091695,0.00897127],
            [0.00724730,0.00065064,0.00897127,0.01277782]])
F = pd.read_pickle('out/feat1c.pkl')
X = F[['tunecap','reflpwr','pkpk','wafer']].values; y = F.depth.values
Z = (X-MEAN)/SCALE
pred = B0 + Z@COEF
sd = SIGMA*np.sqrt(1+np.maximum(0,(Z@M*Z).sum(1)))
ks = np.linspace(0,2.5,60)
skip = [100*(pred-k*sd > LSL).mean() for k in ks]
miss = [int((y[(pred-k*sd > LSL)] < LSL).sum()) for k in ks]
fig, ax1 = plt.subplots(figsize=(6.2,4))
ax1.plot(ks, skip, color='#2b6cb0', lw=2); ax1.set_xlabel('Confidence multiplier k')
ax1.set_ylabel('Metrology skip rate [%]', color='#2b6cb0')
ax2 = ax1.twinx(); ax2.grid(False)
ax2.plot(ks, miss, color='#c53030', lw=2)
ax2.set_ylabel('Missed out-of-spec wafers', color='#c53030')
ax1.axvline(1.0, ls='--', c='gray')
ax1.annotate('k=1.0\n76.1% skip\n0 miss', xy=(1.0,76.1), xytext=(1.35,80), fontsize=8,
             arrowprops=dict(arrowstyle='->', color='gray', lw=1))
ax1.set_title('Skip rate vs missed detections', pad=12); plt.tight_layout()
plt.savefig('figs/fig2_verdict.png', bbox_inches='tight'); plt.close()

# Fig 3 — 보드 벤치마크 (실측값 하드코딩)
C=[1,2,4,8,16,32]; el=[0.435,0.231,0.132,0.117,0.115,0.114]
K=[1,2,4,8]; wait=[34258,7872,4634,4668]
fig, ax = plt.subplots(1,2, figsize=(11,4))
ax[0].plot(C, [el[0]/e for e in el], 'o-', lw=2, color='#2b6cb0', label='measured speedup')
ax[0].plot(C, C, '--', c='gray', lw=1, label='ideal (linear)')
ax[0].axhline(3.82, ls=':', c='#c53030', label='saturation 3.8x')
ax[0].set_xscale('log', base=2); ax[0].set_xlabel('Chambers (processes)')
ax[0].set_ylabel('Speedup'); ax[0].set_title('B2 - saturates at 3.8x (4 physical cores)')
ax[0].legend(fontsize=8)
ax[1].plot(K, wait, 'o-', lw=2, color='#c53030')
ax[1].axhline(544, ls='--', c='gray', label='inference 544 ns')
ax[1].set_xscale('log', base=2); ax[1].set_yscale('log')
ax[1].set_xlabel('Concurrent verdict limit K'); ax[1].set_ylabel('Semaphore wait [ns]')
ax[1].set_title('B4 - saturates at K=4'); ax[1].legend(fontsize=8)
plt.tight_layout(); plt.savefig('figs/fig3_board.png', bbox_inches='tight'); plt.close()

# Fig 4 — OES 4 lot
if os.path.exists('out/oes_multilot.pkl'):
    R = pickle.load(open('out/oes_multilot.pkl','rb'))
    lots = sorted(R); wl = R[lots[0]]['wl']; m = (wl>=543)&(wl<=562)
    from scipy.stats import spearmanr
    fig, ax = plt.subplots(1,2, figsize=(11,4))
    for l in lots:
        sp=R[l]['spec']; ws=sorted(sp)
        band=np.array([sp[w][m].sum() for w in ws])
        rb,_ = spearmanr(ws, band)
        ax[0].plot(ws, 100*(band/band[0]-1), 'o-', lw=1.5, ms=4,
                   label=f'lot {l}  (rho={rb:+.2f})')
    ax[0].axhline(0, c='k', lw=.8)
    ax[0].set_xlabel('Wafer order'); ax[0].set_ylabel('Band intensity change [%]')
    ax[0].set_title('543-562 nm band - monotonic decrease in all 4 lots\n'
                    '(Spearman rho -0.73 to -0.83, all p<0.02)', fontsize=10)
    ax[0].legend(fontsize=8)
    bands=[(200,300),(300,400),(400,500),(500,600),(600,700),(700,800),(800,880)]
    x=np.arange(len(bands)); wdt=0.2
    for i,l in enumerate(lots):
        ax[1].bar(x+(i-1.5)*wdt, [R[l]['band_rho'][b][0] for b in bands], wdt, label=f'lot {l}')
    ax[1].axhline(0, c='k', lw=.8); ax[1].axhline(-0.6, ls='--', c='#c53030', lw=1)
    ax[1].set_xticks(x); ax[1].set_xticklabels([f'{a}-{b}' for a,b in bands], rotation=45, fontsize=8)
    ax[1].set_ylabel('Spearman rho'); ax[1].set_title('Wavelength band consistency')
    ax[1].legend(fontsize=8)
    plt.tight_layout(); plt.savefig('figs/fig4_oes.png', bbox_inches='tight'); plt.close()

print('saved:', sorted(os.listdir('figs')))

"""Render the paper's real-world completion results (mean ± SD across humans)."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
font_manager.fontManager.addfont(ROOT / 'docs/static/css/fonts/LinLibertine_R.ttf')
plt.rcParams.update({
    'font.family': font_manager.FontProperties(fname=ROOT / 'docs/static/css/fonts/LinLibertine_R.ttf').get_name(),
    'font.size': 15,
    'svg.fonttype': 'path',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.spines.left': False,
    'axes.edgecolor': '#9dacad',
    'text.color': '#000000',
    'axes.labelcolor': '#000000',
    'xtick.color': '#334a4d',
    'ytick.color': '#000000',
})
labels = ['Bathing / Policy', 'Bathing / Direct execution', 'Scratching / Policy', 'Scratching / Policy\nwith arm movement']
means = [80, 39, 79, 63]
sd = [11, 25, 16, 20]
colors = ['#95d2d3', '#b0cce5', '#95d2d3', '#95d2d3']
fig, ax = plt.subplots(figsize=(9, 5.5))
fig.subplots_adjust(left=.34, right=.965, bottom=.17, top=.87)
ax.barh(range(4), means, xerr=sd, height=.53, color=colors,
        edgecolor=['#398184', '#5a84b0', '#398184', '#398184'], linewidth=.9,
        error_kw={'ecolor': '#18353d', 'elinewidth': 1.5, 'capsize': 6, 'capthick': 1.5})
ax.set_yticks(range(4), labels)
ax.invert_yaxis()
ax.set_xlim(0, 100)
ax.set_xticks(range(0, 101, 20))
ax.set_xlabel('Target completion (%)', labelpad=13)
ax.set_axisbelow(True)
ax.xaxis.grid(True, color='#e2e8e8', linewidth=.8)
ax.tick_params(axis='y', length=0, pad=14, labelsize=15)
ax.tick_params(axis='x', length=4, labelsize=14)
for i, mean in enumerate(means):
    ax.text(3, i, str(mean), va='center', ha='left', fontsize=16)
fig.text(.965, .955, 'Mean ± SD across participants', ha='right', va='top', fontsize=16)
out = ROOT / 'docs/images/results'
out.mkdir(parents=True, exist_ok=True)
fig.savefig(out / 'target-completion.svg', facecolor='white')
fig.savefig(out / 'target-completion.png', dpi=170, facecolor='white')

# A separate layout keeps labels legible on phones without horizontal scrolling.
fig.set_size_inches(6, 5.7)
fig.subplots_adjust(left=.34, right=.95, bottom=.14, top=.88)
ax.set_yticks(range(4), ['Bathing\nPolicy', 'Bathing\nDirect execution', 'Scratching\nPolicy', 'Scratching\nPolicy + arm\nmovement'])
ax.tick_params(axis='y', labelsize=16, pad=9)
ax.tick_params(axis='x', labelsize=14)
ax.set_xlabel('Target completion (%)', fontsize=16, labelpad=10)
fig.texts[0].set_fontsize(14)
fig.savefig(out / 'target-completion-mobile.svg', facecolor='white')
fig.savefig(out / 'target-completion-mobile.png', dpi=170, facecolor='white')

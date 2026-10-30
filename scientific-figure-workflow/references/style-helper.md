# 将可选助手接入 Notebook

把本技能 `assets/publication_style.py` 复制到 Notebook 同目录。它只处理样式和导出；核心科学计算及绘图仍保持可见。以下是接入片段，须将输入路径和字段替换为实际保存结果，不能直接当作真实研究图运行。

```python
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from publication_style import figure_size_mm, publication_style, export_figure

# 输入身份/缓存校验采用 result-contract.md，在绘图前完成。
RESULT_CSV = Path('output/summary.csv')
WIDTH_MM, HEIGHT_MM = 85, 65  # 试稿尺寸，替换为目标规范
FONT_FAMILY, FONT_SIZE, DPI = 'DejaVu Sans', 9, 300
SERIES_COLOR = '#4477AA'  # 用户可改；不是统计优劣编码
plot_data = pd.read_csv(RESULT_CSV)
assert len(plot_data) > 0
assert np.isfinite(plot_data['estimate']).all()

with publication_style(font_family=FONT_FAMILY, font_size=FONT_SIZE):
    fig, ax = plt.subplots(figsize=figure_size_mm(WIDTH_MM, HEIGHT_MM),
                           layout='constrained')
    # 点图可关注非零范围；不伪造没有保存的误差线。
    ax.scatter(np.arange(len(plot_data)), plot_data['estimate'],
               color=SERIES_COLOR, marker='o')
    ax.set_xticks(np.arange(len(plot_data)), plot_data['group'])
    ax.set_ylabel('Estimate (replace with actual unit)')
    evidence = export_figure(fig, 'output/figures/estimate',
                             formats=('pdf', 'svg', 'png'), dpi=DPI)
    plt.show()
plt.close(fig)
```

将 evidence、样式配置、输入哈希和图注一并写入项目图件清单；返回值中的 visual_check 保留 NOT-RUN，直到实际打开导出图检查。助手不会检查输入身份、有效样本、统计含义或空图；调用者按协议负责。确认字体安装不等于字形齐全，实际渲染缺字形仍会失败。

精确尺寸模式保持整个 canvas，负责布局的调用者须在该尺寸内留足标签空间；`exact_size=False` 会紧裁切，其实际宽高可能变化。函数不关闭 Figure，方便 Notebook 显示；调用者显示后显式关闭。此工具仅支持 PDF/SVG/PNG，需要其他格式时保留显式的原生 savefig 代码。

# 科研绘图：独立、可编辑、可追溯

1. **计算与绘图分离**：先保存数值表（CSV/Parquet）、必要分布/数组（NPZ/NetCDF/HDF5/Zarr 等）；绘图块重新读取缓存，禁用隐藏的大计算。
2. **一图一标题、一图一代码单元**：图前放可直接修改的 `FIGSIZE`, `FONT_SIZE`, `X_LIM`, `Y_LIM`, `SHOW_LEGEND`, `DPI` 等。
3. **两类图**：诊断图（算法步骤/分布/QC）与结果图（科学问题/对比/模型表现），按研究需要选择，不硬性要求每个指标固定多图。
4. **格式**：每图只输出一种格式，默认 PNG，可改 TIFF（RGB + LZW）；按要求设置 DPI（如 300–600）。仅在用户或目标规范明确要求矢量图时改用 PDF/SVG，不输出重复预览。保留绘图代码供修改。
5. **一致性**：分组颜色跨图统一，平台/实验条件尽量用点形或线型，图例清楚、误差含义清楚、刻度单位准确；考虑色盲和黑白可读性。
6. **不误导**：不伪造显著性星号、不默认假定独立重复；零和缺失分离；不要让缩窄坐标轴或平滑掩盖数据。
7. **复现元数据**：引用共用结果表，在 `provenance.json` 的 figures 部分保存图名、代码/notebook 版本、输入路径/哈希、绘图参数、执行时间或批次编号；图注说明样本数/统计口径。
8. **交互与出图**：可选 Plotly/ipympl 探索，正式论文静态图保留项目原有绘图库的可编辑代码；不依赖交互界面才能生成论文图。
9. **字体与文字编码**：图内文字含中文等非拉丁字符时，必须在样式单元显式配置含相应字形的字体族（如 `mpl.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "DejaVu Sans"]`，按平台可用字体调整）。matplotlib 默认 DejaVu Sans 不含 CJK 字形，未配置时中文会整片渲染为空白方块，并伴随大量 `Glyph ... missing from font(s) ...` 警告。**交付的 Notebook 输出中不得残留此类警告**——警告出现即视为图件 FAIL，须配置字体后重绘。
10. **空图守卫**：绘图单元在画图前必须断言过滤后的数据非空；已知预期行数时同时核对行数。pandas 布尔组合中每个比较都必须加括号——`&`/`|` 的优先级高于 `==`，`a & b & df["x"] == "ok"` 会被解析为 `(a & b & df["x"]) == "ok"`，在部分 pandas 版本下**静默**得到全 False，进而"成功"保存一张空图。空表出图必须显式 `raise`，不得静默通过；不用 `assert`，`python -O` 会移除它。

## 推荐独立绘图块伪流程

```python
# 仅绘图：不调用原始昂贵算法
from pathlib import Path
import warnings
import pandas as pd
import matplotlib.pyplot as plt

FIGSIZE = (7, 4.5)
DPI = 600
# 关闭默认 NA 识别，名为 None/NA 的组是合法字符串；数值列再显式转换
data = pd.read_csv(Path('output') / 'metrics' / 'summary.csv', dtype=str, keep_default_na=False)
data["value"] = data["value"].replace("", "nan").astype(float)
# 布尔过滤：每个比较都加括号（& 优先级高于 ==）
sel = data[(data["group"] == "treatment") & (data["Status"] == "ok")]
if sel["value"].notna().sum() == 0:   # 空图守卫：有行不等于有可绘制值
    raise RuntimeError("绘图输入为空：检查过滤条件与上游结果表")
# 已知预期行数时同样核对 len(sel) == EXPECTED_ROWS

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    # 将每一个散点/误差条/坐标轴/图例/标注分开写清楚
    # ax.scatter(...)
    # ax.set_xlabel(...)
    fig.canvas.draw()
    fig.savefig(...)
    glyph = [x for x in w if "missing from font" in str(x.message)]
    if glyph:
        raise RuntimeError(f"缺字形警告 {len(glyph)} 条：配置含相应字形的字体后重绘")

# 来源记录引用 summary.csv 的哈希与过滤条件，不另存逐图数据副本
```

图表正文要保留字段来源；不能用随机生成的演示数据作为真正结果。

## 投稿版面补充

先设置最终毫米宽高与最终字号，再安排多面板和专用图例空间；无投稿规范时可用 85/180 mm 作可调整试稿，不当作期刊标准。缩印后检查字体和线条。用局部 `mpl.rc_context` 管理样式，避免图间污染；非零柱基线优先改点区间图，趋势阴影必须来自真实区间。热图的缺失与零分离，可比面板共享色标。精确物理尺寸导出时关闭 tight 裁切，因为它会改变画幅；实际打开图件检查裁切、打印辨识和面板标签。以上规则在单独安装本技能时同样适用。

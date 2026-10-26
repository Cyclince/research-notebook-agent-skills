# 科研绘图：独立、可编辑、可追溯

1. **计算与绘图分离**：先保存数值表（CSV/Parquet）、必要分布/数组（NPZ/NetCDF/HDF5/Zarr 等）；绘图块重新读取缓存，禁用隐藏的大计算。
2. **一图一标题、一图一代码单元**：图前放可直接修改的 `FIGSIZE`, `FONT_SIZE`, `X_LIM`, `Y_LIM`, `SHOW_LEGEND`, `DPI` 等。
3. **两类图**：诊断图（算法步骤/分布/QC）与结果图（科学问题/对比/模型表现），按研究需要选择，不硬性要求每个指标固定多图。
4. **格式**：PNG（例如 300–600 DPI，按期刊要求）、SVG 和 PDF；使用 `mpl.rcParams['svg.fonttype']='none'`、`mpl.rcParams['pdf.fonttype']=42` 尽量保证文本可编辑。矢量元素是否保留须抽样检查；密集点云可选择局部栅格化。
5. **一致性**：分组颜色跨图统一，平台/实验条件尽量用点形或线型，图例清楚、误差含义清楚、刻度单位准确；考虑色盲和黑白可读性。
6. **不误导**：不伪造显著性星号、不默认假定独立重复；零和缺失分离；不要让缩窄坐标轴或平滑掩盖数据。
7. **复现元数据**：保存绘图数据、图名、代码/notebook 版本、输入路径/哈希、绘图参数、执行时间或批次编号；图注说明样本数/统计口径。
8. **交互与出图**：可选 Plotly/ipympl 探索，正式论文静态图建议有可编辑的 Matplotlib 输出；不依赖交互界面才能生成论文图。
9. **字体与文字编码**：图内文字含中文等非拉丁字符时，必须在样式单元显式配置含相应字形的字体族（如 `mpl.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "DejaVu Sans"]`，按平台可用字体调整）。matplotlib 默认 DejaVu Sans 不含 CJK 字形，未配置时中文会整片渲染为空白方块，并伴随大量 `Glyph ... missing from font(s) ...` 警告。**交付的 Notebook 输出中不得残留此类警告**——警告出现即视为图件 FAIL，须配置字体后重绘。
10. **空图守卫**：绘图单元在画图前必须断言过滤后的数据非空；已知预期行数时同时核对行数。pandas 布尔组合中每个比较都必须加括号——`&`/`|` 的优先级高于 `==`，`a & b & df["x"] == "ok"` 会被解析为 `(a & b & df["x"]) == "ok"`，在部分 pandas 版本下**静默**得到全 False，进而"成功"保存一张空图。空表出图必须 `assert` 报错，不得静默通过。

## 推荐独立绘图块伪流程

```python
# 仅绘图：不调用原始昂贵算法
from pathlib import Path
import warnings
import pandas as pd
import matplotlib.pyplot as plt

FIGSIZE = (7, 4.5)
DPI = 600
data = pd.read_csv(Path('output') / 'metrics' / 'summary.csv')
# 布尔过滤：每个比较都加括号（& 优先级高于 ==）
sel = data[(data["group"] == "treatment") & (data["Status"] == "ok")]
assert len(sel) > 0, "绘图输入为空：检查过滤条件与上游结果表"   # 空图守卫
# assert len(sel) == EXPECTED_ROWS  # 已知预期行数时启用行数核对

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    fig, ax = plt.subplots(figsize=FIGSIZE)
    # 将每一个散点/误差条/坐标轴/图例/标注分开写清楚
    # ax.scatter(...)
    # ax.set_xlabel(...)
    fig.savefig(...)
    glyph = [x for x in w if "missing from font" in str(x.message)]
    assert not glyph, f"缺字形警告 {len(glyph)} 条：配置含相应字形的字体后重绘"

# 保存后复核：绘图数据落盘且非空
# sel.to_csv(FIG_DIR / "figure_data" / "fig1.csv")  # 落盘后断言行数 > 0
```

图表正文要保留字段来源；不能用随机生成的演示数据作为真正结果。

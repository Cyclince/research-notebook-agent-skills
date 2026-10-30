---
name: scientific-figure-workflow
description: 从保存的科研结果创建或改进可独立运行的 Notebook 论文图。用于图型选择、多面板布局、字体与配色调整、统计含义核查，以及可编辑 SVG/PDF 和高分辨率 PNG 导出；保留源数据和溯源信息，不重跑原科学模型。Use for publication figures and independent redraws from saved results.
metadata:
  version: "1.3.0"
  language: "zh-CN"
---

# 研究者可编辑的论文图件

从已保存的结果开始，让每张图的输入、统计定义、样式和导出过程清楚可改。保留用户现有绘图库；Matplotlib 工具为可选资源，不把任务改造成另一套框架。整个项目重构用 scientific-code-to-notebook；只做方法审计用 scientific-reproducibility-audit。本技能可单独安装。

## 执行流程

1. **确认图件任务**：从现有说明确定研究问题、读者、图型、投稿/报告用途、最终物理宽度和所需格式。有目标规范就遵循；缺省时给出可修改的试稿设置，不臆造期刊标准。仅对影响科学解释或交付的缺口提问。
2. **核验结果与统计**：检查样本、单位、分组、缺失、QC 和来源。说明 n 的独立性层级以及 SD/SE/CI 的定义；无真实误差数据就不画误差带，无实际检验不加显著性。数据缺失时说明阻断，不用模拟结果冒充。
3. **选择图型与编码**：根据研究问题读取 [图型与统计规则](references/chart-decisions.md)。先确定比较对象、类别顺序、系列映射及坐标含义，再调整外观；样式不能改变筛选、排名、分母或统计定义。
4. **设计最终版面**：读取 [排版与导出](references/publication-design.md)。先设毫米尺寸和缩印后字号，再安排面板与图例；共用坐标范围/色标须科学可比。颜色之外提供点形、线型或纹理，避免黑白打印失去区分。
5. **显式独立绘图**：每图一个小节，包含可独立导入的绘图入口、结果读取和集中样式参数；核心绘图语句留在 Notebook。仅做所需轻量显示变换，不自动拟合或重跑模型。可选复制 [样式与导出助手](assets/publication_style.py) 到绘图目录；使用 [接入示例](references/style-helper.md)。它不负责数据处理或统计推断。
6. **渲染、检查、修正**：实际运行每张交付图，打开导出的图检查文字、裁切、图例、样本数和误差定义。按最终版面尺寸看可读性；验证一次改变样式后的干净 Kernel 独立重绘。多轮修改不改变来源数据；未做的检查保留 NOT-RUN。
7. **保存证据**：导出任务要求的格式，保留绘图输入、参数快照、来源/代码身份、图注及输出索引；明确何者是人工示意、何者是观测或估计。

## 必守边界

- 结果/缓存的身份、主键、缺失与 QC 按 [统一验收协议](references/result-contract.md) 检查，使用 [验收表](assets/validation_matrix_template.csv)。一幅示范图通过不代表所有图通过。
- 柱长编码通常从零开始；小差异优先用点区间图。裁剪范围、对数轴、归一化和雷达指标顺序均显式说明，不能为突出某方法临时调整。
- 字体检查覆盖实际渲染的字形；缺字形和空图为 FAIL。存在有限数据不等于布局已通过人工检查。
- 跨图系列语义一致，不按“最好/最差”自动赋色。用户指定的风格优先于默认值；不强制 Helvetica、LaTeX、超宽画布或三种导出格式。
- 改图时不暗中重计算；交互控件可选，普通代码仍须可运行。运行环境不足则标注 BLOCKED/NOT-RUN。

## 按需资源

- [图件验收](references/plotting-acceptance.md)：逐图检查与记录项。
- [图型与统计规则](references/chart-decisions.md)：柱/点、趋势、热图、散点和特殊图。
- [排版与导出](references/publication-design.md)：物理尺寸、局部样式、共享图例、打印和矢量导出。
- [参考来源与取舍](references/source-notes.md)：figures4papers 的固定版本、借鉴范围及许可说明。

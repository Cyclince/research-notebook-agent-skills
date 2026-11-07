---
name: scientific-code-to-notebook
description: 将难理解的既有科研代码、算法脚本和多模块分析工程重构为清晰、可交互、可维护的 Jupyter Notebook 科研流程。适用于 Python、R、MATLAB、Julia 或混合语言项目，需要保留原始方法与数值结果、独立算法分析单元、分离计算与绘图、支持科研复现和论文制图时使用。Use when refactoring existing scientific pipelines into readable, reproducible, researcher-editable notebooks.

metadata:
  version: "1.5.0"
  language: "zh-CN"
---

# 科研代码转 Notebook

将既有科研代码整理成可读、可独立运行的 Notebook，保留科学方法与数值结果。仅改图或做审计时，直接完成对应任务，不启动整套重构。

## 执行流程

1. **接入真实输入**：按 [输入工作流](references/input-workflow.md) 确认来源、路径、字段、单位、QC 与数据预览；区分论文复现、方法迁移、输入示例。缺少数据标记 BLOCKED，不用模拟数据替代。
2. **锁定基线**：读取原代码、参数和可核实的方法来源，建立原函数到 Notebook 单元的映射，覆盖全部输出字段及标识符变换。保留原文件；未核实的方法不宣称复现。复杂项目参考 [盘点](references/audit-and-planning.md)。
3. **迁移计算**：按科学研究单元组织 Notebook，顺序为问题与依据 → 集中参数 → 输入/QC → 显式核心计算 → 验证与保存 → 独立绘图。仅抽取重复 I/O 等辅助逻辑，不把算法藏进封装；公式、阈值、单位、聚合和缺失规则不静默改变。跨语言迁移缺少可比基线时保留原语言调用，并注明边界。结构按需参考 [单元设计](references/notebook-design.md)、[目录](references/project-layout.md)。
4. **独立绘图**：读取保存结果，改样式不重跑模型。每图默认只导出 PNG；需要 TIFF 时用 tif/tiff 替代，不附带 PDF/SVG 或额外预览副本。保留可编辑绘图代码与必要绘图输入。尺寸、字体、统计表达见 [绘图规则](references/figure-guidelines.md)。
5. **验证**：按 [统一协议](references/result-contract.md) 对齐主键、字段、缺失/QC 与预设容差；验证干净 Kernel 执行和仅绘图路径。差异先查输入、方法、版本和随机性，不笼统归因浮点误差。特殊边界见 [验证参考](references/verification.md)。

## 精简交付

交付 Notebook、必要结果/绘图输入、一份来源与参数记录及一份验收表；运行说明集中在一个入口。现有文件可满足要求时直接引用，不另建同义清单、方法卡或逐图数据副本。多个图共用同一结果表；诊断图仅在能解释问题时添加。

同一任务中，输入、代码、参数与环境未变的检查复用已有证据；变化后只重做受影响的检查。报告仅列关键结果、未通过/未运行项和文件入口，不重复完整流程及已通过检查。状态不得把未运行写成通过。

## 可选模板

- `assets/notebook_template.ipynb`：真实输入待配置入口；`assets/real_data_example.ipynb`：真实观测输入示例，不能替代目标论文算法。
- `assets/input_adapter.py`、`assets/input_config.json`：CSV/TSV 预检；示例配置 `assets/penguins_input.json`。
- `assets/method_registry_template.csv`、`assets/validation_matrix_template.csv`：缺少对应记录时使用，不重复生成。

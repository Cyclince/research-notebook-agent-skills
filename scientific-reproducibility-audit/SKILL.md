---
name: scientific-reproducibility-audit
description: 审核科研代码重构或算法复现是否保持原论文方法、输入范围、计算参数、QC状态和数值结果。适用于 Python、R、MATLAB、Julia 及混合语言的科研模型、结构指标、数值仿真和数据分析；输出逐指标对照、失败原因、版本溯源及可重复运行检查。Use when verifying scientific methods and regression results before accepting refactored notebooks.

metadata:
  version: "1.3.0"
  language: "zh-CN"
---

# 科研算法复现与重构验收

## 目标

防止“代码运行成功但科学结果变了”，以可审计证据判断原算法和新 Notebook 是否一致，而非以图表相似或程序无报错替代验证。跨学科使用，不绑定特定文件格式或指标。

## 操作顺序

1. **锁定来源**：记录原始论文、章节/公式、原作者源码及版本/commit、项目适配与原始实现的不同。
2. **冻结基线**：旧源码及依赖、实际输入数据哈希、样本集/分组、参数、seed、有效和无效输出以及时间/空间单位。
3. **审查映射**：为每个指标建立原代码计算链与 Notebook 单元关系。检查数据筛选、公式、归一化、聚合、缺失处理。
4. **运行对照**：在相同输入/条件下分别产生基线和新结果；按指标预设合理绝对/相对容差，记录差值和 QC 变化。
5. **随机算法**：若结果依赖随机性，记录种子/算法及版本，按重复性/分布评估，不盲目强制逐数一致。
6. **边界与稳健性**：空输入、缺失、异常单位、不收敛、数据版本差、并行/精度差、仪器/平台差异、敏感性。
7. **Notebook 验收**：从干净 Kernel 运行，检查无隐藏状态；“仅重绘”是否可在不运行计算阶段下完成；核查误差带、坐标/色标、最终尺寸和多面板视觉检查，见 references/audit-checklist.md。
8. **出具报告**：逐指标 PASS、PASS-WITH-DIFF、FAIL、BLOCKED、NOT-RUN 或 NOT-APPLICABLE；留下必要复现指令和后续阻断项。

## 禁止行为

- 引用未核实的文献或臆造源代码测试通过。
- 把 `NaN`、算法未收敛、非适用转换为 0 或插值，除非论文方法明确支持且作标注。
- 把同一样本不同平台、分组或处理版本视作独立重复。
- 通过悄悄改阈值、放大容差或挑选部分样本使验证“通过”。
- 将模拟/示例输入结果声称为真实科研结论。

## 验收文件

优先生成可机器读取的 `validation_matrix.csv`、`input_manifest.csv`、`method_registry.csv`、`environment_manifest` 以及简短审计结论。缺数据时，保留结构但报告 `BLOCKED`。

详细模板与常见问题见 `references/audit-checklist.md`。

## 验收协议与执行边界

数值对照、缓存或独立绘图交付前，读取 [结果对齐与验收协议](references/result-contract.md)，使用 [统一验收表](assets/validation_matrix_template.csv)。按主键对齐、预先确定容差、核对缺失与 QC；遵循协议的总体状态判定。技能可独立安装，无须其他技能目录。运行环境缺失时说明限制，不宣称已执行。

## 标量 CSV 对照工具

需要比较按样本保存的标量 CSV 时使用标准库脚本；运行前 `python scripts/compare_csv.py --help`。例如在本技能目录执行：

```bash
python scripts/compare_csv.py old.csv new.csv --keys sample_id --numeric estimate --qc status --atol 1e-8 --rtol 1e-6 --dataset-id dataset-v1 --method method-a --source-code-version OLD_COMMIT --refactor-code-version NEW_COMMIT --output validation_matrix.csv
```

脚本按字符串主键对齐，逐字段检查，输出统一 schema；退出码 0 表示所执行的表格检查通过，1 表示 FAIL，2 表示输入不可读取或调用条件阻断。数值列需显式指定，未指定列按原字符串比较；空字符串和 NaN 为数值缺失，Inf 为 FAIL。不同容差的指标分别运行并保存独立报告。缺失字段/键、重复键、空表不会通过。它不验证数据同源、单位、论文方法或随机等效性，也不自动生成 PASS-WITH-DIFF；完整审计仍须履行上述流程。

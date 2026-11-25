<div align="center">

# Research Notebook Agent Skills

**把科研代码整理成看得懂、改得动、可验证的 Notebook。**

<img src="./assets/banner.png" alt="Research Notebook Agent Skills — 真实数据、可读方法与可复现结果的概念封面" width="100%">

[![Release](https://img.shields.io/github/v/release/Cyclince/research-notebook-agent-skills?style=flat-square&color=18B7B5)](https://github.com/Cyclince/research-notebook-agent-skills/releases/latest)
[![Validation](https://github.com/Cyclince/research-notebook-agent-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/Cyclince/research-notebook-agent-skills/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-EA4C89?style=flat-square)](./LICENSE)

[三个技能](#三个技能) · [安装](#安装) · [怎么用](#怎么用) · [五分钟示例](#五分钟示例) · [对照工具](#对照工具) · [支持范围](#支持范围)

</div>

---

这是一组给 AI Agent 使用的技能。它们约束 Agent 在处理科研代码时**接真实数据、不改算法、不伪造结果**，并把每一步的证据留下来：

```text
真实输入  →  可读计算  →  独立绘图  →  结果核验
```

它解决三类常见问题：

- 代码能跑但读不懂，改一张图要重跑整个模型。
- 重构之后程序没报错，但没人确认数值、缺失和 QC 是否变了。
- 缺少数据时 Agent 自动造数，图看起来没问题，结论却没有依据。

## 三个技能

| 技能 | 什么时候用 | 得到什么 |
| --- | --- | --- |
| [**代码转 Notebook**](./scientific-code-to-notebook/SKILL.md) | 已有代码难读、难改 | 步骤展开的 Notebook、输入配置、结果与来源记录 |
| [**论文绘图**](./scientific-figure-workflow/SKILL.md) | 已有结果，要出图或改图 | 可编辑绘图代码和单一格式图件，不重跑模型 |
| [**复现审计**](./scientific-reproducibility-audit/SKILL.md) | 要确认重构或复现没有改变结果 | 逐字段验收表、差异说明、未验证项 |

可以单独安装，也可以按上面的顺序串联。

## 安装

安装技能只需复制目录，不需要 Python 依赖。

**1. 下载**（当前版本 v1.6.0）

| 内容 | 下载 |
| --- | --- |
| 代码转 Notebook | [scientific-code-to-notebook-1.6.0.zip](https://github.com/Cyclince/research-notebook-agent-skills/releases/download/v1.6.0/scientific-code-to-notebook-1.6.0.zip) |
| 论文绘图 | [scientific-figure-workflow-1.6.0.zip](https://github.com/Cyclince/research-notebook-agent-skills/releases/download/v1.6.0/scientific-figure-workflow-1.6.0.zip) |
| 复现审计 | [scientific-reproducibility-audit-1.6.0.zip](https://github.com/Cyclince/research-notebook-agent-skills/releases/download/v1.6.0/scientific-reproducibility-audit-1.6.0.zip) |
| 整套（含测试与维护脚本） | [research-notebook-agent-skills-1.6.0.zip](https://github.com/Cyclince/research-notebook-agent-skills/releases/download/v1.6.0/research-notebook-agent-skills-1.6.0.zip) |

也可以克隆仓库：

```bash
git clone https://github.com/Cyclince/research-notebook-agent-skills.git
cd research-notebook-agent-skills
```

**2. 复制**：把**完整的技能目录**放进客户端的 Skills 搜索路径。

| 客户端 | 目标位置 |
| --- | --- |
| Claude Code（个人） | `~/.claude/skills/` |
| Claude Code（项目） | `你的项目/.claude/skills/` |
| 支持 `.agents/skills/` 的客户端 | `你的项目/.agents/skills/` |

例如在仓库或整套包的目录中，安装全部三个到 Claude Code：

```bash
mkdir -p ~/.claude/skills && cp -R scientific-* ~/.claude/skills/
```

> [!NOTE]
> 从 1.5.0 升级：先删除旧技能目录再复制，避免残留旧文件。旧版 `provenance.json` 与新绘图单元不兼容，需重新计算一次。其他变化见 [v1.6.0 发布说明](https://github.com/Cyclince/research-notebook-agent-skills/releases/tag/v1.6.0)。

<details>
<summary>校验下载文件（SHA-256）</summary>

从 [v1.6.0](https://github.com/Cyclince/research-notebook-agent-skills/releases/tag/v1.6.0) 下载全部附件后运行：

```bash
shasum -a 256 -c SHA256SUMS
```

`RELEASE-MANIFEST.json` 记录源提交与压缩包哈希。只下载一个包时，用 `shasum -a 256 文件名.zip` 与 `SHA256SUMS` 中对应条目核对。

</details>

## 怎么用

告诉 Agent 代码在哪、真实数据在哪、要什么结果。三个可直接改写的请求：

**整理代码**

> 使用 scientific-code-to-notebook，把这个项目整理为可读 Notebook。先接入项目里的真实数据，保留原算法与 QC，展示关键计算步骤，并对照原输出验证结果。

**改图**

> 使用 scientific-figure-workflow，从保存的结果表重绘这三张图。开放尺寸、字体、坐标轴和图例参数，每张图只导出 PNG。不要重新拟合模型。

**核验**

> 使用 scientific-reproducibility-audit，对比旧输出与新版 Notebook。按 sample_id 和 time 对齐，检查数值、缺失状态、QC 和单位，只报告关键差异与未验证项。

## 五分钟示例

用随包的 Palmer Penguins 真实观测数据体验完整流程（Python 3.11+）：

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -r requirements-example.txt
```

在支持 Jupyter 的编辑器中选择该环境，把工作目录设为 `scientific-code-to-notebook/assets/`，打开 [real_data_example.ipynb](./scientific-code-to-notebook/assets/real_data_example.ipynb) 并运行全部单元。

结果写入 `example_output/`：344 条观测中 342 条有效，2 条因声明的缺失值被排除，并生成分组统计和一张图。示例只演示流程，不代表任何论文算法已被复现；数据来源与 CC0 许可见[数据说明](./scientific-code-to-notebook/assets/data/SOURCE.md)。

### 换成自己的数据

1. 在 `assets/` 目录生成配置草稿，自动填写哈希、行数和可用字段：

   ```bash
   python input_adapter.py --init 你的数据.csv --config input_config.json
   ```

2. 编辑 `input_config.json`，补全来源、科学角色、字段映射、单位和缺失标记。重复测量用 `key_columns` 声明联合主键，如 `["id", "time"]`。
3. 预检，未补全的项会一次列出：

   ```bash
   python input_adapter.py --config input_config.json
   ```

4. 打开 [notebook_template.ipynb](./scientific-code-to-notebook/assets/notebook_template.ipynb)，或 R 版 [notebook_template_r.ipynb](./scientific-code-to-notebook/assets/notebook_template_r.ipynb)（需 IRkernel），把分组统计替换为你的算法。

> [!IMPORTANT]
> 修改计算代码后，请**保存、重启内核、Run All**。Python 模板会核对实际执行的代码与已保存的 Notebook，不一致就拒绝保存结果。只改图形样式时，单独运行绘图单元即可。

数组、影像和时空数据使用各自的读取器，约定见[输入工作流](./scientific-code-to-notebook/references/input-workflow.md)。

## 对照工具

位于 `scientific-reproducibility-audit/scripts/`，以下命令在 `scientific-reproducibility-audit/` 目录运行。

**标量 CSV**（仅用标准库）：按主键对齐，逐列设容差。

```bash
python scripts/compare_csv.py old.csv new.csv --keys sample_id time --tol estimate=1e-8,1e-6 area=0.1,0 --qc status --missing-values NA --output validation_matrix.csv
```

**数组**（npy / npz / NetCDF）：比较形状、类型、单位、缺失掩码和数值。

```bash
python scripts/compare_arrays.py old.nc new.nc --tol temperature=1e-6,0 --output validation_matrix.csv --append
```

- 容差格式为 `列=绝对,相对`，应在看到结果之前确定。
- R 的 `NA` 等标记必须声明，不会自动当作缺失。
- 中文编码文件加 `--encoding gb18030`；需要逐条明细加 `--full`（均限 CSV 工具）。
- 退出码：`0` 通过，`1` 有差异，`2` 无法读取或条件不足。

工具只比较文件内容，不判断数据是否同源、方法是否正确。详见[审计技能](./scientific-reproducibility-audit/SKILL.md#标量-csv-对照工具)。

## 输出与状态

每个任务围绕两份记录，不堆积同义文件：

| 文件 | 内容 |
| --- | --- |
| `provenance.json` | 输入、参数、代码与环境身份，以及每张图的来源 |
| `validation_matrix.csv` | 所有检查的统一验收表 |

| 状态 | 含义 |
| --- | --- |
| `PASS` | 实际检查过并满足预先定义的判据 |
| `PASS-WITH-DIFF` | 有依据的可接受差异 |
| `FAIL` | 违反要求 |
| `BLOCKED` | 缺少输入、来源或环境 |
| `NOT-RUN` | 还没有实际检查 |
| `NOT-APPLICABLE` | 有明确理由不适用 |

**结果、输入、科学参数或计算代码变化时，绘图会停止并要求重算。** 图件每张只导出一种格式：默认 PNG，可选 TIFF（RGB + LZW），投稿规范要求矢量图时用 PDF/SVG。完整规则见[验收协议](./scientific-reproducibility-audit/references/result-contract.md)。

## 支持范围

方法约定适用于 Python、R、MATLAB、Julia 及混合语言项目；随附的模板与工具覆盖如下：

| 能力 | 已提供 | 未提供 |
| --- | --- | --- |
| Notebook 模板 | Python、R | MATLAB、Julia |
| 输入适配器 | CSV/TSV，含联合主键 | 数组、影像、数据库 |
| 结果对照 | 标量 CSV、npy/npz、NetCDF | HDF5、MAT、影像、随机算法等效性 |
| 图件助手 | Matplotlib | ggplot2 等其他绘图库 |

已知限制：

- **R 模板**不能核对实际执行的代码，也不能自动发现缺字形和越界，相关项保持 `NOT-RUN`；中文需设置 `FONT_FAMILY`。在 macOS 上导出 TIFF 需要 XQuartz。
- **自动检查不能代替看图**：文字重叠、可读性和科学含义须人工确认。
- **技能不能证明论文结论正确**：示例跑通、图表相似或与旧结果一致，都不等于方法正确。

## 仓库结构

```text
scientific-code-to-notebook/       代码转 Notebook：SKILL.md、参考资料、模板与示例数据
scientific-figure-workflow/        论文绘图：SKILL.md、参考资料、Matplotlib 导出助手
scientific-reproducibility-audit/  复现审计：SKILL.md、参考资料、对照脚本
scripts/  tests/                   包检查、Notebook 冒烟测试、单元测试
```

## 参与维护

```bash
python -m pip install -r requirements-example.txt -r requirements-optional.txt
python scripts/check_package.py
python -m unittest discover -s tests -v
python scripts/smoke_notebook.py
python scripts/smoke_notebook_r.py   # 可选，需 R 及 jsonlite、digest
```

GitHub Actions 在 Python 3.11 和 3.12 上运行包检查、单元测试和 Notebook 冒烟测试，并单独验证 R 模板。`requirements-optional.txt` 仅用于 NetCDF 测试。

发布时先统一三个 `SKILL.md` 的版本号并提交，再生成附件：

```bash
python scripts/build_release.py --output-dir 新目录
```

`references/result-contract.md` 和 `references/input-workflow.md` 在三个技能中各有一份，修改时须同步。

## 许可与来源

项目基于 [MIT License](./LICENSE)。外部数据、论文与原作者代码遵循各自许可。绘图流程参考了 [figures4papers](https://github.com/ChenLiu-1996/figures4papers) 的部分设计思路，未收录其代码或图像，范围与许可见[参考来源](./scientific-figure-workflow/references/source-notes.md)。

作者：[@Cyclince](https://github.com/Cyclince)

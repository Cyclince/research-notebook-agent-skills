<div align="center">

# Research Notebook Agent Skills

**从真实数据开始，把科研代码整理成看得懂、改得动、可验证的 Notebook。**

<img src="./assets/banner.png" alt="Research Notebook Agent Skills — 真实数据、可读方法与可复现结果的概念封面" width="100%">

[![Release](https://img.shields.io/badge/release-1.5.0-18B7B5?style=flat-square)](https://github.com/Cyclince/research-notebook-agent-skills/releases/latest)
[![Validation](https://github.com/Cyclince/research-notebook-agent-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/Cyclince/research-notebook-agent-skills/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-EA4C89?style=flat-square)](./LICENSE)

**[下载 Skills](https://github.com/Cyclince/research-notebook-agent-skills/releases/latest)** · [快速开始](#快速开始) · [真实数据示例](#运行真实数据示例) · [使用方式](#使用方式)

</div>

---

## 让科研流程更容易理解与复现

从分散的算法脚本到可编辑的 Notebook，这套技能帮助你接通真实数据、展开关键计算、独立调整论文图，并对照原输出核验结果。支持 Python、R、MATLAB、Julia 及混合语言项目，运行时使用对应环境。

**真实输入 → 可读计算 → 独立绘图 → 结果核验**

## 选择适合你的技能

| 技能 | 适用场景 | 交付结果 |
| --- | --- | --- |
| [代码转 Notebook](./scientific-code-to-notebook/SKILL.md) | 既有科研代码难读、难改 | 显式计算步骤、真实输入配置和可独立运行的 Notebook |
| [论文绘图](./scientific-figure-workflow/SKILL.md) | 已有结果，需要论文绘图或调整版式 | 可编辑绘图代码、单一 PNG/TIFF 图件与来源记录 |
| [复现审计](./scientific-reproducibility-audit/SKILL.md) | 需要确认重构或复现是否改变结果 | 按字段对齐的验收表、差异解释与未验证项 |

三个技能按任务选用，也可以串联完成从代码整理到结果核验的流程。

## 快速开始

### 1. 下载并安装

在 [Releases](https://github.com/Cyclince/research-notebook-agent-skills/releases/latest) 下载单个技能或整套 ZIP。解压后，将**完整技能目录**放入客户端的 Skills 搜索路径，保留目录中的说明和资源文件。三个技能可独立安装，安装本身无需 Python 依赖。

<details>
<summary>通过 Git 克隆安装</summary>

以下以支持项目级 `.agents/skills/` 的客户端为例，将 `/path/to/your-project` 换成实际路径：

```bash
git clone https://github.com/Cyclince/research-notebook-agent-skills.git
cd research-notebook-agent-skills
mkdir -p /path/to/your-project/.agents/skills
cp -R scientific-code-to-notebook /path/to/your-project/.agents/skills/
```

绘图和审计技能按需复制；其他客户端按其配置选择安装路径。

</details>

<details>
<summary>校验下载文件（SHA-256）</summary>

Release 附带 `SHA256SUMS` 与记录源提交、压缩包哈希的 `RELEASE-MANIFEST.json`。下载完整附件后执行：

```bash
shasum -a 256 -c SHA256SUMS
```

只下载一个包时，使用 `shasum -a 256 文件名.zip`，与 `SHA256SUMS` 对应条目核对。

</details>

### 2. 提供代码与数据

告诉 Agent 项目位置、真实输入路径和目标。已有结果只需改图时，直接提供结果表与图件要求；需要算法复现时，一并提供论文或原实现。

### 3. 选择任务并开始

使用下面对应的请求，或先体验随包提供的 [真实数据示例](#运行真实数据示例)。

## 使用方式

把项目代码、数据路径和任务目标交给 Agent，并指定需要的技能。

**整理已有科研代码**

> 使用 scientific-code-to-notebook，把这个项目整理为可读 Notebook。先接入项目里的真实数据，保留原算法与 QC，展示关键计算步骤，并对照原输出验证结果。

**调整论文图件**

> 使用 scientific-figure-workflow，从保存的结果表重绘这三张图。开放尺寸、字体、坐标轴和图例参数，每张图只导出 PNG。不要重新拟合模型。

**核验算法复现**

> 使用 scientific-reproducibility-audit，对比旧输出与新版 Notebook。按 sample_id 和 time 对齐，检查数值、缺失状态、QC 和单位，只报告关键差异与未验证项。

## 运行真实数据示例

仓库提供两个 Notebook 入口：

| 入口 | 用途 |
| --- | --- |
| [real_data_example.ipynb](./scientific-code-to-notebook/assets/real_data_example.ipynb) | 使用随包提供的 Palmer Penguins 真实观测数据，体验输入、QC、统计与独立重绘 |
| [notebook_template.ipynb](./scientific-code-to-notebook/assets/notebook_template.ipynb) | 接入自己的论文或项目数据，再替换为目标算法 |

<details>
<summary>展开示例运行步骤 · Python 3.11+</summary>

在仓库根目录安装示例依赖，需要 Python 3.11+：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-example.txt
```

Windows 使用 `.venv\Scripts\activate`。在支持 Jupyter 的编辑器中选择此环境，将工作目录设为 `scientific-code-to-notebook/assets/`，打开 `real_data_example.ipynb` 并运行全部单元。

</details>

示例从 344 条观测中识别出 342 条有效喙长记录，展示分组统计和绘图；数据来源、固定版本与 CC0 许可见 [数据说明](./scientific-code-to-notebook/assets/data/SOURCE.md)。它用于演示真实输入接入，不代表目标论文算法已被复现。

接入自己的数据时，编辑 [input_config.json](./scientific-code-to-notebook/assets/input_config.json)，填写实际路径、来源、哈希、字段映射、单位和缺失规则，再运行模板。表格示例适配器支持 CSV/TSV；数组、影像和时空数据使用对应读取器，详见 [输入工作流](./scientific-code-to-notebook/references/input-workflow.md)。

## 输出保持精简，证据保留完整

- **图片**：每图只输出一种格式，默认 PNG，可改为 TIFF；绘图代码保留可编辑参数。
- **计算**：读取保存结果独立重绘，调整样式无需重跑模型；输入、代码或科学参数变化会拦截不匹配缓存。
- **记录**：共用结果表与来源信息，复用仍有效的检查证据，报告聚焦差异、阻断项和未运行项。

> [!NOTE]
> 缺少真实输入时会报告 `BLOCKED`，不会自动以模拟数据替代。公开数据示例跑通不代表原论文算法复现通过。

详细约定见 [结果验收协议](./scientific-reproducibility-audit/references/result-contract.md)；CSV 对照工具见 [审计技能](./scientific-reproducibility-audit/SKILL.md#标量-csv-对照工具)。

## 本地验证

<details>
<summary>展开维护与验证命令</summary>

安装示例依赖后，在仓库根目录运行：

```bash
python scripts/check_package.py
python -m unittest discover -s tests -v
python scripts/smoke_notebook.py
```

检查覆盖技能结构、数据接入、结果对照、PNG/TIFF 导出、Notebook 完整执行、独立重绘与缓存失效。GitHub Actions 在 Python 3.11 和 3.12 上运行这些检查；真实项目仍需核验方法依据、科学结果与实际图件。

需要保留示例输出供查看时，使用 `python scripts/smoke_notebook.py --output-dir /tmp/research-notebook-qa`，输出目录须尚不存在。

</details>

## 参考与许可

论文绘图流程参考了 [figures4papers](https://github.com/ChenLiu-1996/figures4papers) 的部分设计思路，具体范围与许可说明见 [参考来源](./scientific-figure-workflow/references/source-notes.md)。

项目基于 [MIT License](./LICENSE) 开源，外部数据、论文与原作者代码遵循各自许可。

作者：[@Cyclince](https://github.com/Cyclince)

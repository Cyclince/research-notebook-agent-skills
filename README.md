# Research Notebook Agent Skills

把既有科研代码整理成研究者能读懂、修改和验证的 Jupyter Notebook，并保留方法、数据与结果之间的证据链。

本仓库提供三个可独立安装的 Agent Skill，覆盖代码重构、论文绘图和复现审计。适用于 Python、R、MATLAB、Julia 及混合语言项目；实际执行需要对应语言环境。跨语言调用与 Python 算法迁移会明确区分。

| Skill | 何时使用 | 主要交付 |
|---|---|---|
| [scientific-code-to-notebook](scientific-code-to-notebook/SKILL.md) | 旧科研工程难以阅读，需要保守重构 | 可读 Notebook、方法映射、结果与复现说明 |
| [scientific-figure-workflow](scientific-figure-workflow/SKILL.md) | 已有计算结果，只需独立重绘或调整图件 | 绘图 Notebook、图件、绘图数据与样式记录 |
| [scientific-reproducibility-audit](scientific-reproducibility-audit/SKILL.md) | 要核验重构是否改变科学方法和结果 | 逐字段验收矩阵、差异解释与阻断项 |

## 精简输出（1.5.0）

每图默认只生成 PNG；需要 TIFF 时将 FORMAT 改为 tif/tiff。保留绘图代码以便修改，不附带 PDF/SVG。示例移除重复输入清单、绘图数据副本和独立样式文件：输入证据并入 provenance.json，样式并入 figure_provenance.json，绘图直接引用已保存结果。输入预览仅显示前 5 行。

检查证据在输入、代码、参数与环境未变时复用；最终报告只保留关键结果、异常和文件入口。

## 工作原则

- 先锁定旧实现、真实输入、科学参数和基线，再重构；不静默修正原算法。
- 核心科学步骤在 Notebook 中可见；共享 I/O 和经过验证的性能内核可以保留为辅助代码。
- 计算和绘图解耦。独立绘图从已保存结果开始，校验来源，不自动触发重计算。
- 新旧结果先核对联合主键、字段和样本集合，再比较数值、缺失与 QC。
- 区分已通过、带差异通过、失败、阻断、未运行与不适用；部分检查通过不代表整体验收通过。

这些技能提供工作流程和辅助工具，不保证任意科研方法正确；没有真实数据、方法来源或运行环境时，必须报告验证范围。

## 安装

下载本仓库，选择需要的**整个技能目录**复制到客户端的 Skills 搜索路径。保留目录内的 `SKILL.md`、`references/`、`assets/` 和存在的 `scripts/`。

例如，在支持项目级 `.agents/skills/` 的客户端中：

```bash
git clone https://github.com/Cyclince/research-notebook-agent-skills.git
cd research-notebook-agent-skills
mkdir -p /path/to/your-project/.agents/skills
cp -R scientific-code-to-notebook /path/to/your-project/.agents/skills/
```

将 `/path/to/your-project` 换成实际项目路径。其他客户端（包括 DeepSeek Harness）的扫描路径和启用方式以其配置为准。三个技能不要求同时安装；仓库根目录的检查脚本和示例依赖仅用于维护与演示。

## 使用示例

**重构旧科研项目**

> 使用 scientific-code-to-notebook 审查这个旧项目，先冻结基线和方法映射，再按研究问题拆分 Notebook。保留算法、样本选择和 QC，展示核心计算，计算与绘图分离，并逐字段比较旧版结果。

**只调整图件**

> 使用 scientific-figure-workflow，从保存的结果表重绘这三张图。开放字体、尺寸、坐标轴和图例参数；默认仅导出 PNG，需要时改为 TIFF，保存绘图数据及参数。不要重新拟合模型。

**核验复现结果**

> 使用 scientific-reproducibility-audit，对比旧输出和新版 Notebook。联合主键是 sample_id、time；先检查完整样本集合，再核对数值、缺失、QC 和单位，生成统一验收表，列出未运行与阻断项。

## 真实输入与可运行示例（1.4.0）

先安装 Python 3.11+ 的示例依赖：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-example.txt
```

Windows 使用 `.venv\Scripts\activate`。在支持 Jupyter 的编辑器选择此环境，工作目录设为 scientific-code-to-notebook/assets/。

**自己的论文/项目数据**：编辑 [input_config.json](scientific-code-to-notebook/assets/input_config.json)，填实际路径、来源、论文引用、文件 SHA-256、字段映射、单位与缺失标记；再执行：

```bash
shasum -a 256 /path/to/your/data.csv  # 将实际哈希填写到配置中
python input_adapter.py --config input_config.json
```

预检通过后打开 [notebook_template.ipynb](scientific-code-to-notebook/assets/notebook_template.ipynb)。默认配置尚未接入用户数据，会明确 BLOCKED，不再自动使用模拟 CSV。映射器只承担本示例 CSV/TSV 读取；真实算法需要在可见计算单元中实现，其他数据格式使用对应适配器。

**先体验真实数据工作流**：打开 [real_data_example.ipynb](scientific-code-to-notebook/assets/real_data_example.ipynb) 并 Run All。包内包含固定版本、CC0 许可的 [Palmer Penguins 真实观测数据](scientific-code-to-notebook/assets/data/SOURCE.md)，通过 [penguins_input.json](scientific-code-to-notebook/assets/penguins_input.json) 接入 344 条测量记录，342 条有效喙长用于分组统计。示例仅展示接入与重绘，不宣称复现目标论文算法。无需运行时联网下载。

输入来源、字段/单位、缺失规则、哈希与 QC 排除记录随结果保存到 example_output/；重启 Kernel 后可单独运行绘图单元。输入、配置或适配器改变会拦截旧缓存。缺少真实输入时按 [输入工作流](scientific-code-to-notebook/references/input-workflow.md) 获取数据或生成具体请求清单。

## CSV 结果对照

审计技能自带标准库脚本，无需安装第三方包：

```bash
python scientific-reproducibility-audit/scripts/compare_csv.py old.csv new.csv \
  --keys sample_id time \
  --numeric estimate \
  --qc status \
  --atol 1e-8 --rtol 1e-6 \
  --dataset-id dataset-v1 --method method-a \
  --source-code-version OLD_COMMIT --refactor-code-version NEW_COMMIT \
  --output validation_matrix.csv
```

命令中的列名、版本和容差须替换为实际方法设定。不同容差的指标分别比较。工具按字符串联合键对齐，保留前导零，拒绝重复/空键、缺行、多行、缺字段和空表；检查数值缺失掩码与 QC。未指定为数值的字段按原字符串比较。

退出码：`0` 表示本次表格检查通过，`1` 表示存在 FAIL，`2` 表示读取或调用条件阻断。它不核实论文、单位、输入同源性或随机算法等效性，不能替代完整科研审计。

三个技能使用同一份 [结果对齐与验收协议](scientific-reproducibility-audit/references/result-contract.md) 和相同验收表字段；各技能携带副本以支持独立安装，仓库检查会检测副本漂移。

## 论文绘图增强（1.3.0）

参考 [figures4papers](https://github.com/ChenLiu-1996/figures4papers) 后增加图型决策、多面板/共享图例、打印辨识和最终物理尺寸规范，同时保留已有的科学保真与独立重绘边界。[来源与取舍](scientific-figure-workflow/references/source-notes.md) 记录所审阅的提交及范围。

可选 [publication_style.py](scientific-figure-workflow/assets/publication_style.py) 提供局部样式、毫米转英寸及明确画幅的导出；不读取数据、不计算统计、不隐藏核心绘图。参见 [接入示例](scientific-figure-workflow/references/style-helper.md)。

## 本地验证

安装示例依赖后运行：

```bash
python scripts/check_package.py
python -m unittest discover -s tests -v
python scripts/smoke_notebook.py
```

验证覆盖元数据和资源链接、协议与 CSV schema 一致性、对照工具边界条件、真实 Kernel Run All、干净 Kernel 独立重绘、样式变更、缓存失效拦截、真实观测数据接入、缺失 QC 与未配置输入阻断。Notebook 验证使用临时目录，不写入提交的模板。

保留可查看的 QA 图件：

```bash
python scripts/smoke_notebook.py --output-dir /tmp/research-notebook-qa
```

该目录必须尚不存在。自动测试不能替代图件视觉检查或真实项目的科学验收。GitHub Actions 在 Linux 的 Python 3.11 和 3.12 上运行相同检查；CI 状态以实际运行结果为准。

## 维护

当前技能版本为 `1.5.0`，统一验收 schema 为 `1.0`。修改协议时同步更新三个 `references/result-contract.md`；修改验收列时同步更新三个 CSV 模板和对照工具的 `FIELDS`，并运行检查。

提交示例请使用可公开的数据，并提供预期行为和实际输出。不要提交原始敏感数据、凭据或大型计算产物。

## 许可

[MIT](LICENSE)。外部论文、数据、原作者代码及其运行环境遵循各自许可证与使用条件。

# Research Notebook Agent Skills

把既有科研代码整理成研究者能读懂、修改和验证的 Jupyter Notebook，并保留方法、数据与结果之间的证据链。

本仓库提供三个可独立安装的 Agent Skill，覆盖代码重构、论文绘图和复现审计。适用于 Python、R、MATLAB、Julia 及混合语言项目；实际执行需要对应语言环境。跨语言调用与 Python 算法迁移会明确区分。

| Skill | 何时使用 | 主要交付 |
|---|---|---|
| [scientific-code-to-notebook](scientific-code-to-notebook/SKILL.md) | 旧科研工程难以阅读，需要保守重构 | 可读 Notebook、方法映射、结果与复现说明 |
| [scientific-figure-workflow](scientific-figure-workflow/SKILL.md) | 已有计算结果，只需独立重绘或调整图件 | 绘图 Notebook、图件、绘图数据与样式记录 |
| [scientific-reproducibility-audit](scientific-reproducibility-audit/SKILL.md) | 要核验重构是否改变科学方法和结果 | 逐字段验收矩阵、差异解释与阻断项 |

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

> 使用 scientific-figure-workflow，从保存的结果表重绘这三张图。开放字体、尺寸、坐标轴和图例参数；按投稿要求导出 PDF 与 PNG，保存绘图数据及参数。不要重新拟合模型。

**核验复现结果**

> 使用 scientific-reproducibility-audit，对比旧输出和新版 Notebook。联合主键是 sample_id、time；先检查完整样本集合，再核对数值、缺失、QC 和单位，生成统一验收表，列出未运行与阻断项。

## 可运行教学模板

[notebook_template.ipynb](scientific-code-to-notebook/assets/notebook_template.ipynb) 使用 [人工示例数据](scientific-code-to-notebook/assets/example_measurements.csv)，演示读取、QC、分组统计、来源记录、独立重绘和图件检查。**示例均值不是任何学科的论文算法，示例输出不能用于科研结论。**

使用 Python 3.11 或更新版本：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-example.txt
```

Windows 使用 `.venv\Scripts\activate` 激活。通过支持 Jupyter 的编辑器选择这个 Python 环境，将 Notebook 工作目录设为 `scientific-code-to-notebook/assets/`，然后 Run All。若需要浏览器版 JupyterLab，可在该环境另行安装。

运行结果写入该目录的 `example_output/`，包含统计表、被排除记录及原因、来源哈希、绘图数据、参数和 SVG/PDF/PNG。默认图内使用英文以支持跨平台运行；中文标签需配置实际可用的 CJK 字体。

仅重绘时，重启 Kernel，单独运行“4. 独立绘图”代码单元。修改样式不改变计算缓存；输入、科学参数、科学代码或结果文件变化时会停止，并提示显式重算。图件视觉检查默认记录为 NOT-RUN，必须实际打开图件检查后才能改为 PASS。

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

## 本地验证

安装示例依赖后运行：

```bash
python scripts/check_package.py
python -m unittest discover -s tests -v
python scripts/smoke_notebook.py
```

验证覆盖元数据和资源链接、协议与 CSV schema 一致性、对照工具边界条件、真实 Kernel Run All、干净 Kernel 独立重绘、样式变更、缓存失效拦截、单样本 SD 与非有限值 QC。Notebook 验证使用临时目录，不写入提交的模板。

保留可查看的 QA 图件：

```bash
python scripts/smoke_notebook.py --output-dir /tmp/research-notebook-qa
```

该目录必须尚不存在。自动测试不能替代图件视觉检查或真实项目的科学验收。GitHub Actions 在 Linux 的 Python 3.11 和 3.12 上运行相同检查；CI 状态以实际运行结果为准。

## 维护

当前技能版本为 `1.2.0`，统一验收 schema 为 `1.0`。修改协议时同步更新三个 `references/result-contract.md`；修改验收列时同步更新三个 CSV 模板和对照工具的 `FIELDS`，并运行检查。

提交示例请使用可公开的数据，并提供预期行为和实际输出。不要提交原始敏感数据、凭据或大型计算产物。

## 许可

[MIT](LICENSE)。外部论文、数据、原作者代码及其运行环境遵循各自许可证与使用条件。

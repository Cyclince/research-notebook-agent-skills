# 目录：只描述角色，不绑定特定学科

```text
project/
├── data/
│   ├── raw/                 # 不覆盖的原始输入；敏感数据按权限管理
│   └── metadata/            # 单位、采集/实验分组、边界、批次
├── notebooks/
│   ├── 00_preprocessing.ipynb
│   ├── 01_method_a.ipynb
│   ├── 02_method_b.ipynb
│   └── 90_comparison.ipynb
├── src/                     # 仅必要的共享 I/O / 缓存 / 专业外部内核
├── references/              # 方法卡、论文及来源清单
├── tests/
├── output/
│   ├── preprocessing/
│   ├── method_a/{data,tables,figures,qc}/
│   ├── method_b/{data,tables,figures,qc}/
│   ├── comparisons/
│   └── publication_figures/{svg,pdf,png,figure_data}/
├── archive/                 # 原脚本快照（或 Git 标签/分支）
├── environment.yml          # 或 requirements.txt、renv.lock 等
└── README.md
```

约定：
- 大文件/不应公开的数据不要默认提交到 Git。
- 文件名使用 `{dataset}_{group}_{method}_{content}_{version}` 等可理解格式；输出索引注明实际路径。
- 再运行可以选择新 batch_id 或显式覆盖该批次派生文件；始终保留原始数据。
- 设计为“公共预处理一次 + 科学单元分别计算 + 汇总 Notebook 只读指标表”。
- 不需要为每个文件创建数层复杂目录；优先科研人员快速定位。

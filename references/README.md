# 参考资料导航

本目录采用渐进式加载。先确定当前阶段，只读取对应角色入口；遇到具体任务再读取一份或少量参考文件。

## 根目录

- `SKILL_ROOT`：本仓库根目录，只读。
- `PROJECT_ROOT`：用户项目目录，所有产物写入这里。

任何参考文档中的相对路径均以其所属 `SKILL.md` 目录为基准。角色文档通过 `../../..` 回到 `SKILL_ROOT`。

## 三角色

| 阶段 | 入口 | 固定交付物 |
|---|---|---|
| 建模分析 | `roles/建模手/SKILL.md` | `题目分析报告.md`、`术语表格.md` |
| 代码实现 | `roles/编程手/SKILL.md` | Python/MATLAB 求解代码、结果表格、创新证据清单、候选证据池、图表论证清单、复现清单 |
| 论文撰写 | `roles/论文手/SKILL.md` | 默认交付 `完整论文.docx`；用户显式要求时同时交付 LaTeX 源码项目与编译 PDF |


## 高分机制模块（2026-08 新增）

| 模块 | 位置 | 何时用 |
|---|---|---|
| 题面拆解与必答清单（盲做，陌生题对靶） | `roles/建模手/references/题面拆解与必答清单前置.md` | 建模前（复杂题） |
| 创新专项（自由发散/证据收敛） | `roles/innovation-special/SKILL.md` | 建模/编程/论文 |
| 创新元能力（双表示/尺度/结构/反例） | `roles/innovation-special/元能力.md` | 发现跨题结构时按需读取 |
| 物理几何简化与证明 | `roles/innovation-special/references/物理几何简化.md` | 物理或几何候选 |
| 求解创新路由 | `roles/innovation-special/references/求解创新路由.md` | 算法简化或求解改进 |
| 创新证据协议 | `roles/innovation-special/references/创新证据协议.md` | 原型、P2、W1、W2 |
| 验证完备性（风险驱动） | `roles/编程手/references/验证完备性.md` | 编程阶段 |
| 发散—收敛温度策略（提示词级调数） | `温度策略.md` | 建模手发散 / 编程手求解 / 论文写作 |
| 评分导向自检 | `roles/论文手/references/评分导向自检.md` | 论文阶段（复杂题必做） |
| 文献规范（中文核心/零OA/确有所指） | `roles/论文手/references/文献规范.md` | 论文阶段 |
| 盲做经验库（知识累积） | `knowledge/盲做经验库/` | 陌生题查库 + 完成后回写（只存题面拆解与自洽结果） |

## 按任务加载

| 任务 | 读取 |
|---|---|
| 选模型 | `roles/建模手/references/建模设计理论.md` |
| 查具体算法 | `算法索引.md`，再读取一个匹配的 `../assets/*.md` |
| Python/MATLAB 实现 | `roles/编程手/references/工作流程.md` |
| MATLAB 工具箱与出图 | `roles/编程手/references/MATLAB规范.md` |
| 数据图与选图 | `../tools/figure/SKILL.md` |
| 机理、几何、流程、架构和拓扑图 | `../tools/diagram/SKILL.md`、`视觉论证与配图策略.md` |
| 图型选择与科研绘图避坑 | `../tools/figure/references/chart-types/chart_selection.md` |
| Subagent 调度与阶段质检 | `Subagent调度.md` |
| 创新证据审计 | `roles/innovation-special/scripts/innovation_audit.py` |
| 论文结构 | `roles/论文手/references/章节模板.md` |
| Word 格式 | `roles/论文手/references/论文格式规范.md` |
| LaTeX 格式 | `roles/论文手/references/LaTeX格式规范.md` |

## 工具

| 工具 | 入口 |
|---|---|
| 科研可视化 | `../tools/figure/SKILL.md` |
| 数模非数据图 | `../tools/diagram/SKILL.md` |
| 双引擎论文搜索 | `../tools/paper_search/SKILL.md` |
| PDF | `../tools/pdf/SKILL.md` |
| Excel | `../tools/xlsx/SKILL.md` |
| DOCX | `../tools/docx/SKILL.md` |
| LaTeX | `../tools/latex/SKILL.md` |

外部论文只在确有需要时搜索和读取并保留来源；按盲做规则，不检索官方评阅要点/参考答案/赛后解析/赛后同题论文，文献只用竞赛年及更早。

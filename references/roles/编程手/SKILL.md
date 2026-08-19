---
name: 编程手
description: 数学建模的 Python 或 MATLAB 求解实现、运行、表格输出，以及 Python 单轨正式配图和复现阶段。
---

# 编程手

## 路径

- `ROLE_ROOT`：本文件所在目录。
- `SKILL_ROOT`：`ROLE_ROOT/../../..`，只读。
- `PROJECT_ROOT`：用户项目目录，所有代码、结果和图只写这里。

## 输入

优先读取 `PROJECT_ROOT/题目分析报告.md`、`PROJECT_ROOT/术语表格.md` 和题目附件。若用户只执行本阶段，可从用户提供的模型说明开始；若说明不足以实现，先反馈缺项。

## 固定产物

- Python `.py`、MATLAB `.m`，或用户要求的两套求解实现。
- `results/` 中的运行结果表格和必要文本结果。
- `figures/` 中由真实模型、代码和结果生成的候选图。数据图可使用 `raw_qN_*`、`process_qN_*`、`result_qN_*` 来源标签；非数据图使用语义前缀。Matplotlib 和 GeoGebra 2D 图同源导出 SVG 与至少 300 DPI PNG；GeoGebra 3D 图保留 `.ggb` 源文件并导出高分辨率 PNG；复杂流程图的 Mermaid 源码 `.mmd` 作为可编辑源并同源导出 SVG 与 300 DPI PNG。无法自动渲染时交付 `.geogebra.txt`、`.mmd` + 渲染说明，不按类别或子问题凑数。
- `results/图表论证清单.json`，记录每个正式证据单元的主张、来源、载体、视觉角色、落点、前后论述和采用决策。
- `results/复现清单.json`。
- `results/创新证据清单.json`；允许 `items` 为空，不为满足数量制造创新。
- `results/竞争性搜索账本.json`；仅在题目分析报告含 `competitive` 子问题时创建，记录 baseline、内部标尺、incumbent、结构性挑战、预算和停止证书。

## 执行顺序

1. 按用户要求或现有项目语言选择 Python/MATLAB 作为求解语言；没有偏好时按模型依赖和现有环境选择并说明。无论求解语言为何，正式配图统一使用 Python/Matplotlib；MATLAB 求解结果先导出为可追溯 CSV/MAT 再绘图。
2. 按选中的模型功能动态检查依赖，禁止一次性要求全部包：
   - Python：`python scripts/check_env.py --features data visualization optimization`
   - MATLAB 求解：`check_matlab_env(["data","optimization"])`；正式配图另行检查 Python/Matplotlib/NetworkX 与 GeoGebra。
2.5 估算计算量。只有预计耗时、内存或规模会阻碍完整求解时才加载 `references/计算加速.md`；根据真实负载选择向量化、稀疏计算、并行或 GPU。加速后必须与合适的串行或高保真基线核对，容差由模型精度和量纲确定，不得套用固定阈值或改变模型结果。
3. 实现数据读取、预处理和核心求解链，用真实输入或结构等价小实例跑通从 `PROJECT_ROOT` 执行的最小命令；任何结论必须来自真实输出。
4. 在全量计算、参数扫描和正式出图前，派发独立质检 Subagent 执行 `P1` 最小可运行结果门禁；实现问题由编程手修正，模型合同问题携证据返回建模手。未返回 `PASS` 不得继续扩展。
5. 按 `../innovation-special/SKILL.md` 把题目分析报告中的候选登记到 `results/创新证据清单.json`。先完整运行合理基线；达标型按验证风险收敛。竞赛型按 `../../竞争型问题协议.md` 创建 `results/竞争性搜索账本.json`，建立内部标尺并冻结可行 incumbent，再在隔离分支挑战目标口径、决策表示、结构分解、模型信息或求解结构。**每次决策表示/求解结构挑战前，按 `../../算法选择双源对照.md` 执行双源对照（强制查库匹配 → 独立思考 → 碰头裁决），把 `source_reconciliation` 写入对应挑战条目**；库有 AI 无的盲区项默认最小原型或证据性拒绝。高竞争价值候选在预算内必须最小原型化；按实际证据更新为 `PROTOTYPED/VERIFIED/ADOPTED/DROPPED`。
6. 从题目分析报告提取全部子问题并规范为 `q1…qN`，读取 `../../../references/视觉论证与配图策略.md`，先建立 `results/图表论证清单.json`。对每个候选证据先判断文字、公式、表格、数据图或非数据图哪个最直接；无明确读者疑问、核心主张和证据来源时不画图。
7. 趋势、分布、误差、对比、收敛和敏感性等数据图加载 `../../../tools/figure/SKILL.md`；机理、几何、流程、架构和拓扑图加载 `../../../tools/diagram/SKILL.md`。NetworkX 只建立离散结构；连续二维/三维几何优先使用 GeoGebra Classic，无法自动渲染时输出逐行指令与生成说明，Matplotlib 作为自动后备。复杂判定/算法流程图（判定树、多分支判据、算法流程）优先使用 Mermaid，以 `.mmd` 为可编辑源、渲染失败时交付源码与渲染说明；几何图不落入 Mermaid；MATLAB 不进入正式配图路由。
8. Matplotlib 正式候选图使用 `../../../tools/figure/scripts/export_figure.py` 导出；GeoGebra 图按 `../../../tools/diagram/SKILL.md` 保存源文件、指令和图片。显式固定最终尺寸且禁用 `bbox_inches="tight"`。先运行 `check_figure.py`，再运行带 `--manifest` 和全部 `--questions` 的 `figure_audit.py --strict`；实际打开彩色 PNG 和灰度预览检查语义、层级、缺字、裁切、遮挡、颜色、尺度和面板一致性。有问题则改源文件或指令、重跑、重审，不能直接修改位图。
9. 生成复现清单，并运行 `innovation_audit.py <创新证据清单> --project-root <PROJECT_ROOT> --strict`。存在竞赛型子问题时，再运行 `challenge_audit.py <竞争性搜索账本> --project-root <PROJECT_ROOT> --questions <竞赛型题号...> --strict`。任一审计失败时不得进入 `P2`；首个可行解或没有官方值不能替代挑战审计。
10. 按 `references/质检清单.md` 完成作者自检，再派发独立质检 Subagent 执行 `P2` 编程终检；未返回 `PASS` 不得进入论文阶段或宣称编程交付完成。

## 阶段内独立门禁

- `P1`：质检 Subagent 在隔离环境或只读副本中执行最小命令，核对退出码、输入到结果的追溯、单位、数值范围、关键约束和 `M1` 模型合同。它是纵向切片，不要求完整图表或最终性能。
- `P2`：代码、结果、创新证据清单、竞争性搜索账本（如有）、候选证据池、图表论证清单和复现清单冻结后，质检 Subagent 独立运行唯一复现命令并核对输入哈希、种子、关键数值、边界、量纲、每个子问题的正式证据覆盖及文件完整性。逐项检查 `VERIFIED/ADOPTED` 的代码、证明、基线、量化结果和失效边界；对竞赛型逐项核对内部标尺、结构性挑战、incumbent 晋升、预算和停止证书，禁止把可行当成完成。机械图审使用带 `--manifest` 和全部 `--questions` 的 `figure_audit.py --strict`；Subagent 负责实际读图，检查图是否回答登记的读者疑问、是否与模型/数据一致、放置建议和图后推论是否成立，而不是只确认文件能打开。

两次门禁均按 `../../../references/Subagent调度.md` 返回证据；被审代码、数据或参数发生实质变化时重跑受影响门禁。

## 何时加载

| 情形 | 读取 |
|---|---|
| 开始实现 | `references/工作流程.md` |
| 存在竞赛型子问题 | `../../竞争型问题协议.md` |
| 计算量过大 / 需 GPU 或并行加速 | `references/计算加速.md` |
| 验证完备性（采样收敛/网格收敛/边界校验） | `references/验证完备性.md` |
| 创新候选、状态和证据门控 | `../innovation-special/SKILL.md`、`../innovation-special/references/创新证据协议.md` |
| 物理或几何简化证明 | `../innovation-special/references/物理几何简化.md` |
| 算法简化或求解创新 | `../innovation-special/references/求解创新路由.md` |
| 使用 MATLAB | `references/MATLAB规范.md` |
| 画趋势、分布、误差、对比、收敛等数据图 | `../../../tools/figure/SKILL.md` |
| 画机理、几何、流程、架构或拓扑图 | `../../../tools/diagram/SKILL.md`、`../../../references/视觉论证与配图策略.md` |
| 不确定用什么图，或需审查指定图型 | `../../../tools/figure/references/chart-types/chart_selection.md` |
| 需要图表函数 | `../../../tools/figure/references/api-templates/plot_recipes.md` |
| 选模型/算法或结构挑战（强制双源对照） | `../../../references/算法选择双源对照.md`，再走 `../../../references/算法索引.md` → 匹配 `../../../assets/*.md`（需要时 `knowledge/` 精读） |
| 处理 Excel | `../../../tools/xlsx/SKILL.md` |
| 交付前 | `references/质检清单.md` |
| 阶段内独立验收 | `../../../references/Subagent调度.md` |

若实际运行证明模型公式、约束或参数定义冲突，停止通过改算法规避问题，把证据反馈给建模手。

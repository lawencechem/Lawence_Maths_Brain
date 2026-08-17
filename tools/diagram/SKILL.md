---
name: math-modeling-diagram
description: 为数学建模论文生成可复现的机理图、二维或三维几何图、算法流程图、模型架构图和网络拓扑图。几何机理图优先使用 GeoGebra Classic，其他非数据图使用 Python、Matplotlib、NetworkX 与 NumPy；不能自动渲染时交付可直接粘贴的 GeoGebra 指令和生成说明。
---

# 数模非数据图工具

## 路径与边界

- `DIAGRAM_ROOT`：本文件所在目录，只读。
- `SKILL_ROOT`：`DIAGRAM_ROOT/../..`，只读。
- `PROJECT_ROOT`：用户项目目录；源代码和图只写入这里。
- 数据分布、趋势、对比、误差、收敛、热力图和统计图使用 `../figure/SKILL.md`。
- 本工具只处理机理、几何、流程、架构和拓扑等非数据图。

## 运行环境

当前验证基线：

| 组件 | 验证版本 | 职责 |
|---|---:|---|
| Python | 3.14.3 | 唯一绘图运行时 |
| Matplotlib | 3.11.1 | 节点、箭头、几何对象、三维视图、文字和最终导出 |
| NetworkX | 3.6.1 | 离散图的节点、边、DAG、层级和路径关系 |
| NumPy | 2.5.1 | 坐标、曲线、网格和几何计算 |
| GeoGebra Classic 5 | 5.4.920.0 | 连续二维/三维几何构造、交互调整和高分辨率导出 |
| Mermaid CLI（可选） | mmdc 或 `npx @mermaid-js/mermaid-cli` | 复杂判定/算法流程图的渲染；缺失时交付 `.mmd` 源码与渲染说明 |

运行前执行：

```powershell
python "<SKILL_ROOT>/tools/diagram/scripts/check_env.py"
```

本轮必须自动生成 GeoGebra 图片时加 `--require-geogebra`；仅输出逐行指令时不加。

记录实际版本，不要求运行环境与验证基线逐补丁版本相同。缺少 Matplotlib、NetworkX 或 NumPy 时明确报告；几何任务优先探测 GeoGebra Classic，缺失或无法自动调用时仍生成逐行指令和人工生成说明，几何机理图不落入 Mermaid 或 MATLAB。复杂判定/算法流程图优先使用 Mermaid，其渲染失败时交付 `.mmd` 源码与渲染说明。

## 单轨工具策略

- 流程、架构和拓扑图：NetworkX 建立离散结构，Matplotlib 手动绘制节点形状、连接线、箭头、标签和图例。
- **复杂判定/算法流程图**（判定树、多分支判据、相位提取算法流程等逻辑难以用文字说清的）：优先使用 **Mermaid** 表达，以 `.mmd` 源码为可编辑交付物；渲染失败时交付源码 + 渲染说明并标记 `PENDING_RENDER`，不伪造完成状态。
- 连续二维/三维几何：优先用 GeoGebra Classic 按“建系、定点、连线、成域/成体、标注、锁视角、导出”顺序构造；Matplotlib `patches`、坐标变换和 `mplot3d` 是可自动渲染的后备。
- 组合图：使用 Matplotlib `GridSpec` 把示意图与同一论点的定量证据组合；定量面板仍遵循 `../figure/SKILL.md`。
- 几何机理图不调用 Mermaid 或 MATLAB；GeoGebra 无法自动运行时不伪造完成状态，改为输出可粘贴指令与生成说明。

## 工作流

### 第 1 步：读取视觉论证需求

读取 `../../references/视觉论证与配图策略.md`、`PROJECT_ROOT/题目分析报告.md` 和已有 `results/图表论证清单.json`。先确认读者疑问、核心主张、证据来源、图类型、必须出现的对象与关系以及章节落点。

没有明确论证缺口时停止生成并把理由写入清单。禁止从通用模板、喜欢的布局或“论文应该有流程图”的预设出发。

### 第 2 步：填写非数据图契约

每张图至少明确：

```text
claim_id：
question_id：
reader_gap：
claim：
diagram_type：mechanism / geometry / flow / architecture / topology
must_show：对象、变量、关键关系
must_not_show：无证据装饰、未使用模块、伪精度
evidence_source：模型章节、公式、代码或真实数据路径
placement：章节与前后段落
final_size：最终宽高
```

### 第 3 步：选择结构表达

| 图类型 | 结构层 | 绘制层 | 布局要求 |
|---|---|---|---|
| 机理图 | 模型对象与因果/作用关系 | Matplotlib patches + arrows | 关键机制居中，次要边界弱化 |
| 二维几何图 | GeoGebra 点、线、圆锥曲线、区域与参数 | GeoGebra 2D；Matplotlib 后备 | 坐标、角度、长度和可见性与公式一致 |
| 三维几何图 | GeoGebra 点、向量、平面、曲面与立体 | GeoGebra 3D；mplot3d 后备 | 锁定视角、范围和关键遮挡关系 |
| 流程图 | 逻辑复杂（判定树、多分支判据、算法流程）优先 Mermaid；其余 NetworkX `DiGraph` | Mermaid 渲染 SVG/PNG；Matplotlib patches/arrows | 判断、循环和回退必须真实存在；Mermaid 显式设 `direction` 与子图层级 |
| 架构图 | NetworkX `DiGraph`/`MultiDiGraph` | Matplotlib patches/arrows | 按输入、模型、求解、输出或实际模块分区 |
| 拓扑图 | NetworkX `Graph`/`DiGraph` | Matplotlib + NetworkX draw primitives | 布局种子固定，关键路径手动微调 |

流程和架构图优先显式提供 `pos` 坐标，不直接接受默认 spring、shell 或 multipartite 布局作为终稿。真实复杂拓扑可用固定种子的算法布局作为初稿，但必须根据重叠、边交叉和论证重点手动调整。

### 第 4 步：绘制与统一样式

- 优先复用 `../figure/scripts/style_constants.py` 的语义颜色与字体逻辑；国赛统一品牌四色时用
  `../figure/scripts/cumcm_theme.py`（国奖主题：`PALETTE`/`TINTS`/`apply()`/`validate_theme_compliance()`）。
- 无项目配色时使用低饱和回退：主色 `#2E5EAA`、辅色 `#C84630`、强调色 `#E08E45`、基准灰 `#7A7A7A`（即
  `cumcm_theme.PALETTE`）。数据图与示意图必须同源——主题固定为 `cumcm`（无 theme 参数切换），两套图共用同一色板，避免论文两套色系。
- 西文优先 Times New Roman，中文优先 SimSun；缺失时按 SimHei、Microsoft YaHei 和可用中文字体回退。绘制前用 `matplotlib.font_manager` 实际检查字体；主题模式下直接调 `cumcm_theme.apply()`（具体字体列表进 `font.family`，见 `design_theory.md` §13 硬坑 1）。
- 同一物理量、模块或路径跨图保持相同颜色、线型和符号。颜色不是唯一编码，必要时增加线型、边框或标记。
- 关键路径加深，次要路径降低饱和度；不使用渐变阴影、立体方框、装饰图标或默认彩虹色。
- 箭头含义必须可由标签、图注或视觉词汇解释；不同语义的箭头不能只靠颜色区分。
- 节点不机械等宽等距。布局允许局部偏移以避让文字和突出主路径，但不得以“随机不对称”破坏真实关系。

### 第 5 步：逐类检查

#### 机理与几何

- 建系、定点、连线、成域、标注的顺序与模型推导一致。
- 可见、遮挡、边界、轨迹和辅助线使用可区分的实虚线。
- 角度、距离、坐标和时间窗由模型变量计算或显式引用，不硬编码伪精确数值。
- 三维图锁定视角和纵横比，减少网格与刻度；二维投影能更清楚表达时不用三维。
- GeoGebra 指令必须按人工构造顺序逐行输出，不把多步构造压成无法调试的单行表达式。
- 指令中的数值来自参数表或模型计算；需要用户交互调整的视角、标签偏移和导出框在生成说明中列出建议值。

#### 流程与架构

- 每个节点对应真实步骤、函数、模块或状态；节点文字使用动宾短语，不写长段正文。
- 判断节点必须具有可核验的条件和不同出口；循环必须明确返回位置和终止条件。
- 通用的“数据输入 -> 模型计算 -> 输出结果”不单独成图。
- 架构图中的输入、状态、参数、控制量和输出不得混用同一种箭头语义。
- **文字块纪律**：所有文字块不得与其他文字块或连线/箭头重叠——Mermaid 自动布局后人工复核节点间距与文字是否压线；Matplotlib 手绘时显式错开坐标，不让标注落在连线/箭头上。

#### 复杂逻辑流程图（Mermaid）

- **触发**：判定树、多分支判据（如多光束判据）、相位提取等算法流程，判断/循环/回退多到仅靠文字难以描述时，优先用 Mermaid 表达；Mermaid 只表达真实存在的分支与回退，禁止用分支美化不存在的逻辑。
- **源码**：用 `flowchart` 类型，以 `.mmd` 文件为可编辑交付物；节点用动宾短语，判断节点写清条件与各出口。
- **渲染**：
  ```powershell
  mmdc -i <stem>.mmd -o <stem>.svg -o <stem>.png
  # mmdc 缺失时：npx -y @mermaid-js/mermaid-cli -i <stem>.mmd -o <stem>.svg -o <stem>.png
  ```
- **渲染后必须人工复核**：方向是否符合阅读顺序、子图/节点是否互相重叠、文字块是否压连线或箭头；自动布局混乱时用 `direction`、子图分组或节点顺序约束修正，不把未经检查的默认布局当作终稿。
- **无法渲染**：交付 `<stem>.mmd` + `<stem>_生成说明.md`，在 `results/图表论证清单.json` 标记 `PENDING_RENDER`，不伪造完成状态。

#### 拓扑

- 节点和边来自真实数据、装配结构、路径候选或模型定义。
- NetworkX 只负责结构和图算法；最终位置、节点形状、边路由和文字由 Matplotlib 控制。
- 关键路径、割集、层级或装配关系应有一种主编码和一种冗余编码。

### 第 6 步：导出与审查

Matplotlib 图使用 `../figure/scripts/export_figure.py` 同源导出 SVG 和至少 300 DPI PNG；LaTeX 安全链需要时额外导出 PDF。显式设置最终尺寸并保留固定边距，不使用 `bbox_inches="tight"` 改变合同尺寸。

```python
from export_figure import export_figure

export_figure(
    fig,
    basename="figures/geometry_q2_occlusion",
    formats=["svg", "png"],
    size_inches=(6.3, 3.8),
    dpi=300,
    grayscale_preview=True,
    tight=False,
)
```

GeoGebra 2D 图优先保存 `.ggb`，并使用英文属性名的 `ExportImage` 同源导出 SVG 与 300 DPI PNG，例如：

```text
Export_1 = (-1, -1)
Export_2 = (12, 8)
ExportImage("filename", "geometry_q2_occlusion.svg", "type", "svg", "view", 1)
ExportImage("filename", "geometry_q2_occlusion.png", "type", "png", "view", 1, "dpi", 300, "width", 2000)
```

GeoGebra 3D 视图不强制 SVG，因为其 3D 导出通常只支持位图；保留 `.ggb` 或逐行指令作为可编辑源，并导出宽度至少 2000 px 的 PNG：

```text
ExportImage("filename", "geometry_q2_scene3d.png", "view", -1, "width", 2400)
```

无法自动调用 GeoGebra 时，至少生成：

```text
figures/<stem>.geogebra.txt       # 可逐行粘贴的完整构造与导出指令
figures/<stem>_生成说明.md         # 参数来源、2D/3D 视图、标签偏移、视角和导出步骤
```

并在 `results/图表论证清单.json` 中使用 `PENDING_RENDER`。用户生成图后，将状态改为 `KEEP` 或其他最终决策，再运行文件审计和 `P2`；存在 `PENDING_RENDER` 时不得声称论文配图完成。

Mermaid 复杂流程图（`.mmd` 为可编辑源）同源导出 SVG 与至少 300 DPI PNG；无法自动渲染时交付 `<stem>.mmd` + `<stem>_生成说明.md` 并同样标记 `PENDING_RENDER`。Mermaid 渲染出的 SVG 文字可编辑，可直接通过 `figure_audit.py` 的 SVG 文本检查。

随后运行：

```powershell
python "<SKILL_ROOT>/tools/figure/scripts/check_figure.py" "<PROJECT_ROOT>/figures" --strict
python "<SKILL_ROOT>/references/roles/编程手/scripts/figure_audit.py" "<PROJECT_ROOT>/figures" --manifest "<PROJECT_ROOT>/results/图表论证清单.json" --questions q1 q2 --strict
```

实际打开 PNG 和灰度预览，检查缺字、裁切、箭头方向、边交叉、标签遮挡、**文字块互相重叠（文字-文字/文字-线）**、空间关系、视角和最终尺寸可读性。问题只能通过修改源代码和重绘修正，不直接编辑位图。

## 论文放置接口

每张 `KEEP` 图在清单中必须填写 `placement`、`lead_in`、`post_observation` 和 `post_implication`。论文手负责把图放在对应推导或算法附近，并形成：

```text
图前：为什么此处需要看图，以及图要回答什么。
图中：只呈现完成该论证所需的对象与关系。
图后：先陈述可见事实，再说明其对模型、算法或决策的含义。
```

项目已有 `[[fig:...]]` 占位协议时使用既有语法和字段；没有时按 Word/LaTeX 工具的图片与题注接口插入，不自行创造无法渲染的占位符。

## 红线

- 禁止编造数据、节点、模块、箭头、空间关系和未实现的算法步骤。
- 禁止为满足图数、题号覆盖或形式完整度生成无论证价值的图。
- 禁止使用 MATLAB 或在线绘图服务作为回退；几何机理图不落入 Mermaid。复杂流程图的 Mermaid 渲染失败时交付 `.mmd` 源码与渲染说明并标记 `PENDING_RENDER`，不得用在线服务静默代渲或伪造完成。
- 禁止默认自动布局直接作为终稿（Mermaid 渲染后必须人工复核方向、子图间距和文字是否压线）。
- 禁止只导出位图而不保留可运行源代码和可编辑 SVG。

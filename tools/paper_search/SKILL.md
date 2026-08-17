---
name: 双引擎论文搜索
description: 使用 OpenAlex 与 AnySearch 两个真实数据源并行搜索、交叉匹配和输出可追溯论文元数据。
---

# 双引擎论文搜索

## 数据源

- OpenAlex：结构化学术元数据。
- AnySearch Academic：学术垂直搜索，支持当前 MCP Markdown 响应解析。

默认并行调用两个引擎。DOI 相同的记录直接交叉验证；无 DOI 时仅在标题高度相似且年份相容时合并。同一引擎中标题规范化后相同的预印本与正式出版记录也会折叠，并优先保留引用信息和元数据更完整的记录。交叉匹配结果、OpenAlex 独有结果和 AnySearch 独有结果分开输出。

融合时按查询词覆盖率过滤和重排，相关性优先于引用量，避免高被引但主题无关的论文挤占结果。包含多个专业术语时，候选文献至少命中两个有效查询词；这一阈值兼顾缺少摘要的元数据，不能代替人工核验。物理、材料和光学主题应组合使用材料名、机理名与模型名，例如 `Sellmeier 4H-SiC Fabry-Perot`；结果过少时逐步放宽查询，不直接接受无关结果。

## 使用

```powershell
python scripts/hybrid_scholar.py --query "robust optimization vehicle routing" --limit 10 --json
```

如 AnySearch 需要鉴权：

```powershell
$env:ANYSEARCH_API_KEY = "<密钥>"
python scripts/hybrid_scholar.py --query "analytic hierarchy process" --limit 8
```

诊断单个引擎时可用 `--openalex-only` 或 `--anysearch-only`；正式文献检索默认不得只运行一个引擎。

## 核验规则

1. 搜索结果只用于发现候选文献。
2. 引用前打开 DOI 或出版机构页面核对作者、题名、年份、期刊/会议、卷期页。
3. 不把引用量当作正确性的证明。
4. 不根据标题或摘要编造不存在的结论。
5. 输出中保留 `sources` 和 `cross_validated` 状态。

## 中文核心期刊检索（CUMCM 等国内竞赛重点，中文核心优先）

先查中文核心（北大核心/CSCD/EI：《红外与激光工程》《兵工学报》《电光与控制》《控制与决策》等），
再补国际文献；低质 OA 同题刊仅数值对照。详见 `../../references/roles/论文手/references/文献规范.md`。

OpenAlex/AnySearch 对国内核心期刊收录与 DOI 覆盖不完整，按命中分级：

1. **双引擎命中**：核 DOI 与题录。
2. **未命中但有原文线索**：WebSearch 定位期刊官网/百度学术 → 提取题录 → OpenAlex 核 DOI（如《红外与激光工程》前缀 `10.3788/IRLA...`）。**国内期刊在 OpenAlex 返回 404/无记录不算校验失败**（OpenAlex 对国内核心期刊收录不完整），改由期刊官网/知网核验题录（题名、作者、年卷期页），核验一致即可引用；只有公开渠道均无法核验时才不引用。
3. **仅知网收录**：主 Agent 出检索式（主题词+期刊+年份+来源类别=核心期刊），用户导出 GB/T 7714 题录（题名/作者前3/刊名/年卷期页/DOI），主 Agent 核验整合。**题录经官网/知网核验一致即视为可追溯、可列入参考文献，不强制 OpenAlex 必须命中**。知网登录为浏览器会话/校园网绑定，不可由 Agent 直接驱动。
4. **无法核验**：全部公开渠道（OpenAlex、期刊官网、知网）均无法核验题录时标 `BLOCKED`，禁编造。

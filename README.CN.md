# Cassotis Lexicon

[English](README.md) | 简体中文

Cassotis IME 词库构建与发布仓库。

## 仓库定位
- 维护词库构建脚本、来源清单与生成产物。
- 支持“外部公开来源启动”与“私有语料融合”的构建流程。
- 维护归因与发布规范，确保与外部发布产物一致。

## 当前词库快照（2026-03-28 构建）

| 文件 | 字体变体 | 词条数 |
|------|---------|--------|
| `data/generated/dict_clean_sc.txt` | 简体中文主词库 | 152,532 |
| `data/generated/dict_clean_tc.txt` | 繁体中文主词库 | 168,638 |
| `data/generated/dict_unihan_sc.txt` | 简体单字（Unihan） | 23,909 |
| `data/generated/dict_unihan_tc.txt` | 繁体单字（Unihan） | 24,064 |

## 外部来源与项目内补充（`external_broad` 配置）

### 外部来源

| 来源 | 许可证 | 用途 |
|------|--------|------|
| Unicode Unihan | Unicode-3.0 | 单字读音兜底与单字词库 |
| CC-CEDICT | CC BY-SA 4.0 | 核心词条与拼音 |
| OpenCC STPhrases | Apache-2.0 | 简繁短语映射 |
| THUOCL | THUOCL 自定义开放条款 | 扩展覆盖与 DF 统计 |
| jieba `dict.txt` | MIT | 频率排序信号 |
| 中文维基词典标题（ns0） | CC BY-SA 4.0 | 日常表达、口语说法与聊天短语种子 |
| 中文维基标题（ns0） | CC BY-SA 4.0 | 命名实体覆盖与高可信专名种子 |
| Wikimedia Pageviews Top（zh.wikipedia） | CC BY-SA 4.0 | 真实热度信号 |
| 经过筛选的 `THUOCL_IT` 子集 | THUOCL 自定义开放条款 | 作为计算机垂直词库候选来源；导入前会先过滤，不按日常聊天词层处理 |
| Wikidata 中文游戏名 / 系列 / 类型 / 主机实体 | CC0-1.0 | 作为独立游戏垂直层的主要作品名/实体来源 |
| 经过筛选的中文维基词典 / 中文维基游戏词汇标题 | CC BY-SA 4.0 | 作为游戏垂直层的轻量游戏词汇补充，导入时会保守过滤 |
| Godot Docs 中文标题索引 | CC BY 3.0 | 作为独立游戏开发术语层的主要术语来源，导入前会先过滤 |
| Wikidata 中文游戏引擎实体 | CC0-1.0 | 作为独立游戏开发术语层的游戏引擎实体补充 |
| MeSH descriptor catalog | NLM MeSH 条款 | 作为医学垂直词库的官方概念白名单，用来把医学层绑定到可识别的 MeSH 术语 |
| Wikidata 中文医学实体（MeSH 关联） | CC0-1.0 | 提供与 MeSH 描述符关联的中文医学名称与别名，作为医学实体主层 |
| 经过筛选的 `THUOCL_medical` 子集 | THUOCL 自定义开放条款 | 作为医学垂直词库候选来源；导入前会过滤并采用比 MeSH 关联医学层更保守的权重 |

### 项目内补充

| 补充层 | 许可证 | 用途 |
|--------|--------|------|
| Cassotis 项目内日常/聊天词表 | 仓库许可证（项目自维护） | 补入公开来源仍容易漏掉、但对日常输入价值很高的常用说法 |
| Cassotis 项目内虚构实体词表 | 仓库许可证（项目自维护） | 存放小说人物、作品名、作品内组织与物件等虚构专名，和日常表达、一般专名分层 |
| Cassotis 项目内专名词表 | 仓库许可证（项目自维护） | 项目内维护的现实风格人名、机构名、品牌名等一般专名词表；不走日常聊天词的 preferred-term 排序链 |
| Cassotis 项目内计算机词表 | 仓库许可证（项目自维护） | 项目内维护的计算机/专业术语词表，供独立的计算机垂直层使用；不走日常聊天词的 preferred-term 排序链 |
| Cassotis 项目内游戏词表 | 仓库许可证（项目自维护） | 项目内维护的游戏行业词汇补充，供独立的游戏垂直层使用；不走日常聊天词的 preferred-term 排序链 |
| Cassotis 项目内游戏开发词表 | 仓库许可证（项目自维护） | 项目内维护的游戏开发术语补充，供独立的游戏开发术语层使用；不走日常聊天词的 preferred-term 排序链 |
| Cassotis 项目内医学词表 | 仓库许可证（项目自维护） | 项目内维护的医学补充词表，用于高价值医学词和显式拼音校正；不走日常聊天词的 preferred-term 排序链 |

详见：
- `manifests/sources.public.yml`
- `attribution/ATTRIBUTION.md`

## 外部词库导入后的优化与过滤思路
- 对多来源词条做格式归一、去重合并，统一拼音与文本键。
- `weight` 由多类信号共同构成（基础频率、DF/词频侧信号、访问热度），并做平衡缩放。
- 从已经被公开来源支持的较长口语表达中，自动派生更短的日常/聊天前缀，让常见句式连接词更容易打出来。
- 对低信号命名实体、疑似人名和长尾噪声做抑制，减少生僻专名挤占常用词排序。
- 应用面向输入法场景的有效性过滤（如可渲染性、字形脚本约束），提升 Windows 场景可用性。
- 通过规则修正和回归样本校验，保持同音竞争与整体排序稳定。

## 覆盖重点
- 重点补强能够显著提升日常聊天顺畅度的常用说法，而不只是追逐网络热词。
- 优先恢复句式衔接词、语气相关短语、口语化表达等高频日常输入单元。
- 对公开来源仍经常漏掉、但输入价值很高的日常短语，保留一小层项目内维护的补充词表。
- 将专名与短期热点视为辅助信号，避免挤占日常用语的核心排序空间。

## 分层原则
- `manifests/curated_daily_phrases.tsv` 只用于日常/聊天表达，这一层会参与日常输入的 preferred-term 偏置。
- `manifests/vertical_layers.public.json` 用来声明独立的垂直术语层。
- `manifests/vertical/*.tsv` 用来存放项目内维护的垂直词表，例如虚构实体、专名词表、计算机词汇、游戏词汇和游戏开发术语。
- 垂直层可以补入专业词，但不会继承日常/聊天词那套 preferred-term 排序偏置，从而避免污染现有日常输入路径。
- 当前启用的虚构实体层会把小说人物、作品名和作品内实体与日常聊天词层、一般专名层分开处理。
- 当前启用的项目内专名层会把现实风格的名称、产品名、机构名等词和日常聊天词层分开处理。
- 当前计算机词库由经过筛选的 `THUOCL_IT` 子集和项目内维护的计算机词表共同组成。
- 当前游戏词库由项目内维护的游戏词表、Wikidata 中文游戏实体，以及经过筛选的中文维基/维基词典游戏词汇标题共同组成。
- 当前游戏开发术语层由项目内维护的游戏开发词表、经过筛选的 Godot Docs 中文标题、Wikidata 中文游戏引擎实体，以及经过筛选的中文维基/维基词典游戏开发词汇标题共同组成。
- 当前医学词库由项目内维护的医学词表、MeSH descriptor catalog、与 MeSH 关联的 Wikidata 中文医学实体，以及经过筛选的 `THUOCL_medical` 子集共同组成，并与日常聊天词层隔离。

## 目录结构
- `data/generated/`：生成词库文件。
- `manifests/`：来源/许可证清单与回归样本。
- `manifests/vertical/`：项目内维护的独立垂直词表。
- `scripts/`：构建、校验、导出辅助脚本。
- `reports/`：构建报告。
- `rules/`：导出与发布规则。

## 构建与校验

```powershell
# 全量重建（external_broad + unihan_single + 回归校验）
.\rebuild_all.ps1

# 直接按单个 profile 构建
.\scripts\build_external_seed.ps1 -Profile external_broad
```

`external_broad` 和 `external_cedict` 在构建时会自动读取
`manifests/vertical_layers.public.json`（如果该文件存在）。

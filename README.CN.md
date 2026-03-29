# Cassotis Lexicon

<p align="center">
  <img src="cassotis_ime_yanquan.png" alt="Cassotis IME logo" width="280">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-CC%20BY--SA%204.0-blue" alt="License: CC BY-SA 4.0"></a>
</p>

[English](README.md) | 简体中文

Cassotis IME 的词库构建与发布仓库。

## 仓库职责
- 维护词库构建脚本、清单文件和生成产物。
- 支持外部来源引导构建和私有语料整合流程。
- 保持署名文件与公开导出产物一致。

## 当前词库快照（2026-03-29 构建）

| 文件 | 变体 | 词条数 |
|------|------|--------|
| `data/generated/dict_clean_sc.txt` | 简体主词库 | 153,031 |
| `data/generated/dict_clean_tc.txt` | 繁体主词库 | 169,097 |
| `data/generated/dict_unihan_sc.txt` | 简体单字（Unihan） | 23,909 |
| `data/generated/dict_unihan_tc.txt` | 繁体单字（Unihan） | 24,064 |

## 外部来源与项目维护补充层（`external_broad`）

### 外部来源

| 来源 | 许可证 | 用途 |
|------|--------|------|
| Unicode Unihan | Unicode-3.0 | 单字级普通话回退与单字词库 |
| CC-CEDICT | CC BY-SA 4.0 | 核心词库词条与拼音 |
| OpenCC STPhrases | Apache-2.0 | 简繁短语映射 |
| THUOCL | THUOCL custom open terms | 扩展覆盖与 DF 统计信号 |
| jieba `dict.txt` | MIT | 频率排序信号 |
| Wiktionary 中文标题（ns0） | CC BY-SA 4.0 | 日常表达、口语短语和聊天类词汇种子 |
| Wikipedia 中文标题（ns0） | CC BY-SA 4.0 | 专名覆盖与高置信专有名词种子 |
| Wikimedia Pageviews Top（zh.wikipedia） | CC BY-SA 4.0 | 真实世界热度信号 |
| 过滤后的 `THUOCL_IT` 子集 | THUOCL custom open terms | 计算机 vertical 候选来源，导入前过滤，避免与日常/聊天词层混在一起 |
| Wikidata 中文电子游戏 / 系列 / 类型 / 主机 | CC0-1.0 | 隔离式 gaming vertical 的主实体来源 |
| 过滤后的 Wiktionary / Wikipedia 中文游戏词条标题 | CC BY-SA 4.0 | 以保守方式导入 gaming vertical 的轻量词汇补充 |
| Godot Docs zh-cn 标题索引 | CC BY 3.0 | game-development vertical 的主术语来源，导入前经过过滤 |
| Wikidata 中文游戏引擎 | CC0-1.0 | game-development vertical 的游戏引擎实体补充 |
| MeSH descriptor catalog | NLM MeSH terms and conditions | 医学 vertical 的 MeSH 概念白名单 |
| Wikidata 中文医学实体（MeSH 关联） | CC0-1.0 | 作为医学实体主层导入的中文医学标签与别名 |
| 过滤后的 `THUOCL_medical` 子集 | THUOCL custom open terms | 医学 vertical 候选来源，过滤后并以比 MeSH 主层更保守的权重使用 |

### 项目维护补充层

| 补充层 | 许可证 | 用途 |
|--------|--------|------|
| Cassotis 日常/聊天短语补充 | 仓库许可证（项目自编写） | 对高价值的日常/聊天表达做稳定补充，弥补公开来源遗漏 |
| Cassotis 小说实体补充 | 仓库许可证（项目自编写） | 项目维护的小说人物、作品名和世界观实体列表，与日常/聊天词及一般专名隔离 |
| Cassotis 一般专名补充 | 仓库许可证（项目自编写） | 项目维护的人名、头衔、组织、品牌等一般专名列表，不与日常/聊天优先路径混用 |
| Cassotis 计算机术语补充 | 仓库许可证（项目自编写） | 隔离式 computing vertical 使用的项目维护计算机/领域术语列表 |
| Cassotis 政务民生术语补充 | 仓库许可证（项目自编写） | 面向税务、房产、户籍和公共服务场景的隔离式 civic vertical 术语层，不走日常/聊天优先路径 |
| Cassotis 游戏术语补充 | 仓库许可证（项目自编写） | 隔离式 gaming vertical 使用的项目维护游戏术语补充 |
| Cassotis 游戏开发术语补充 | 仓库许可证（项目自编写） | 隔离式 game-development vertical 使用的项目维护术语补充 |
| Cassotis 医学术语补充 | 仓库许可证（项目自编写） | 用于高价值医学词汇和显式拼音修正的项目维护医学补充层，与日常/聊天优先路径隔离 |

参见：
- `manifests/sources.public.yml`
- `attribution/ATTRIBUTION.md`

## 导入后的优化与过滤（外部来源）
- 统一并去重来自不同来源格式的词条。
- 综合多个信号（基础频率、DF/频率侧信号、页面热度）计算权重，并做平衡缩放。
- 从已被支持的长口语表达中派生更短的日常/聊天前缀，让常见句式转折更容易前排出现。
- 压低低信号专名、疑似人名和长尾噪声，减少冷门专名挤占常用词位置。
- 应用面向 IME 的有效性过滤（例如可显示性与字符脚本约束），保证输出适合主流 Windows 客户端。
- 通过规则修正与回归样本校验保持排序行为稳定。

## 覆盖重点
- 优先改善日常表达和对话式输入，不只追逐热点词。
- 借助开放词汇来源补回常见短表达、句式转折、语气词和口语连接词。
- 对开放来源仍然缺失但价值很高的日常表达，保留少量项目维护白名单。
- 将专名和网页热点作为次级信号，避免它们主导核心日常输入路径。

## 分层策略
- `manifests/curated_daily_phrases.tsv` 只用于应获得日常输入优待的日常/聊天表达。
- `manifests/vertical_layers.public.json` 声明隔离式 vertical 术语层。
- `manifests/vertical/*.tsv` 存放项目维护的 vertical 词表，例如小说实体、一般专名、计算机术语、政务民生术语、游戏术语和游戏开发术语。
- vertical 层可以补充领域词汇，但不会继承日常/聊天短语的优待偏置。
- fiction 层将小说人物、作品名和世界观实体与日常/聊天表达及一般专名隔离。
- active 的 proper-noun 层将人名、头衔和一般现实专名与日常/聊天表达隔离。
- computing 层目前结合了过滤后的 `THUOCL_IT` 子集与项目维护计算机术语。
- civic 层目前承载税务、房产、户籍及其他公共服务术语。
- gaming 层目前结合了项目维护游戏术语、Wikidata 游戏实体和过滤后的 zhwiki/zhwiktionary 游戏词汇标题。
- game-development 层目前结合了项目维护游戏开发术语、过滤后的 Godot 文档标题、Wikidata 游戏引擎补充，以及过滤后的 zhwiki/zhwiktionary 游戏开发词汇标题。
- medicine 层目前结合了项目维护医学术语、MeSH 描述符目录、MeSH 关联 Wikidata 医学实体，以及过滤后的 `THUOCL_medical` 子集，并始终与日常/聊天优先路径隔离。

## 目录结构
- `data/generated/`：生成的词库文件。
- `manifests/`：来源/许可证清单与回归样本。
- `manifests/vertical/`：项目维护的隔离式 vertical 词表。
- `scripts/`：构建、校验和导出辅助脚本。
- `reports/`：构建报告。
- `rules/`：导出与发布规则。

## 构建与校验

```powershell
# 全量重建（external_broad + unihan_single + regression checks）
.\rebuild_all.ps1

# 直接构建单个 profile
.\scripts\build_external_seed.ps1 -Profile external_broad
```

`external_broad` 和 `external_cedict` 在存在
`manifests/vertical_layers.public.json` 时会自动加载它。

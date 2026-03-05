# Cassotis Lexicon

<p align="center">
  <img src="cassotis_ime_yanquan.png" alt="Cassotis IME logo" width="280">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-CC%20BY--SA%204.0-blue" alt="License: CC BY-SA 4.0"></a>
</p>

[English](README.md) | 简体中文

Cassotis IME 词库产物与构建流程的开源仓库。

## 词库文件（2026-03-05 构建）

| 文件 | 类型 | 词条数 |
|------|------|--------|
| `data/generated/dict_clean_sc.txt` | 简体中文主词库 | 113,559 |
| `data/generated/dict_clean_tc.txt` | 繁体中文主词库 | 97,532 |
| `data/generated/dict_unihan_sc.txt` | 简体单字（Unihan） | 30,397 |
| `data/generated/dict_unihan_tc.txt` | 繁体单字（Unihan） | 31,009 |

## 文件格式

词库文件为 UTF-8 编码 TSV（无表头）：

```text
pinyin<TAB>text<TAB>weight
```

示例：

```text
zhongguo	中国	666
rengongzhineng	人工智能	590
```

- `pinyin`：去声调、无分隔符的 ASCII 拼音键
- `text`：候选中文词（单字或多字）
- `weight`：排序权重（越高优先级越高）

## 构建配置（Profiles）

定义于 `manifests/profiles.public.yml`：

| 配置 | 说明 |
|------|------|
| `external_broad`（默认） | CC-CEDICT + THUOCL + OpenCC + jieba + Unihan + 中文维基标题 + 维基访问热度 |
| `external_cedict` | 仅使用 CC-CEDICT |
| `clean_permissive` | 仅使用 OpenCC STPhrases + Unihan |

## 数据来源（`external_broad`）

| 来源 | 许可证 | 用途 |
|------|--------|------|
| CC-CEDICT | CC BY-SA 4.0 | 核心词条与拼音 |
| THUOCL | THUOCL 自定义开放条款 | 覆盖扩展与 DF 信号 |
| OpenCC STPhrases | Apache-2.0 | 简繁短语映射 |
| jieba `dict.txt` | MIT | 词频信号 |
| Unicode Unihan | Unicode-3.0 | 单字读音兜底 |
| 中文维基标题（ns0） | CC BY-SA 4.0 | 命名实体覆盖 |
| Wikimedia Pageviews Top（zh.wikipedia） | CC BY-SA 4.0 | 真实热度信号 |

来源细节见：
- `manifests/sources.public.yml`
- `attribution/ATTRIBUTION.md`

## 外部词库导入后的优化与过滤思路
- 对多来源词条做格式归一、去重合并，统一拼音与文本键。
- `weight` 由多类信号共同构成（基础频率、DF/词频侧信号、访问热度），并做平衡缩放。
- 对低信号命名实体和长尾噪声做抑制，减少生僻专名挤占常用词排序。
- 应用面向输入法场景的有效性过滤（如可渲染性、字形脚本约束），提升 Windows 场景可用性。
- 通过规则修正和回归样本校验，保持同音竞争与整体排序稳定。

## 构建方式

前置要求：Python 3.8+、PowerShell 7+

```powershell
# 全量重建（external_broad + unihan_single + 回归校验）
.\rebuild_all.ps1

# 或按单个 profile 构建
.\scripts\build_external_seed.ps1 -Profile external_broad
.\scripts\build_external_seed.ps1 -Profile external_cedict
.\scripts\build_external_seed.ps1 -Profile clean_permissive
```

## 许可证

本仓库采用 **CC BY-SA 4.0** 许可证，详见 [LICENSE](LICENSE)。

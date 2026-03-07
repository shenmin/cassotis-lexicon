# Cassotis Lexicon

[English](README.md) | 简体中文

Cassotis IME 词库构建与发布仓库。

## 仓库定位
- 维护词库构建脚本、来源清单与生成产物。
- 支持“外部公开来源启动”与“私有语料融合”的构建流程。
- 维护归因与发布规范，确保与外部发布产物一致。

## 当前词库快照（2026-03-07 构建）

| 文件 | 字体变体 | 词条数 |
|------|---------|--------|
| `data/generated/dict_clean_sc.txt` | 简体中文主词库 | 111,438 |
| `data/generated/dict_clean_tc.txt` | 繁体中文主词库 | 96,725 |
| `data/generated/dict_unihan_sc.txt` | 简体单字（Unihan） | 23,973 |
| `data/generated/dict_unihan_tc.txt` | 繁体单字（Unihan） | 24,130 |

## 外部来源（`external_broad` 配置）

| 来源 | 许可证 | 用途 |
|------|--------|------|
| CC-CEDICT | CC BY-SA 4.0 | 核心词条与拼音 |
| THUOCL | THUOCL 自定义开放条款 | 扩展覆盖与 DF 统计 |
| OpenCC STPhrases | Apache-2.0 | 简繁短语映射 |
| jieba `dict.txt` | MIT | 频率排序信号 |
| Unicode Unihan | Unicode-3.0 | 单字读音兜底与单字词库 |
| 中文维基标题（ns0） | CC BY-SA 4.0 | 命名实体覆盖 |
| Wikimedia Pageviews Top（zh.wikipedia） | CC BY-SA 4.0 | 真实热度信号 |

详见：
- `manifests/sources.public.yml`
- `attribution/ATTRIBUTION.md`

## 外部词库导入后的优化与过滤思路
- 对多来源词条做格式归一、去重合并，统一拼音与文本键。
- `weight` 由多类信号共同构成（基础频率、DF/词频侧信号、访问热度），并做平衡缩放。
- 对低信号命名实体、疑似人名和长尾噪声做抑制，减少生僻专名挤占常用词排序。
- 应用面向输入法场景的有效性过滤（如可渲染性、字形脚本约束），提升 Windows 场景可用性。
- 通过规则修正和回归样本校验，保持同音竞争与整体排序稳定。

## 目录结构
- `data/generated/`：生成词库文件。
- `manifests/`：来源/许可证清单与回归样本。
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

## 约束
- 外部仓库的 commit message 必须使用英文。
- 禁止提交私有原始语料、草稿与作者文稿。

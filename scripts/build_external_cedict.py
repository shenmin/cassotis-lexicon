#!/usr/bin/env python3
"""
Build public lexicon seed files from external sources.

Output format:
  pinyin<TAB>text<TAB>weight[<TAB>scope]
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import io
import json
import math
import fnmatch
import pathlib
import re
import sqlite3
import sys
import tempfile
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from typing import Callable, Dict, Iterable, Iterator, List, Set, Tuple


CEDICT_DEFAULT_URL = (
    "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
)
CEDICT_HOMEPAGE = "https://www.mdbg.net/chinese/dictionary?page=cc-cedict"

OPENCC_STPHRASES_URL = (
    "https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/STPhrases.txt"
)
OPENCC_HOMEPAGE = "https://github.com/BYVoid/OpenCC"

UNICODE_UNIHAN_URL = "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip"
UNICODE_HOMEPAGE = "https://www.unicode.org/ucd/"
THUOCL_ZIP_URL = "https://github.com/thunlp/THUOCL/archive/refs/heads/master.zip"
THUOCL_HOMEPAGE = "https://github.com/thunlp/THUOCL"
JIEBA_DICT_URL = "https://raw.githubusercontent.com/fxsjy/jieba/master/jieba/dict.txt"
JIEBA_HOMEPAGE = "https://github.com/fxsjy/jieba"
ZHWIKI_TITLES_URL = "https://dumps.wikimedia.org/zhwiki/latest/zhwiki-latest-all-titles-in-ns0.gz"
ZHWIKI_HOMEPAGE = "https://dumps.wikimedia.org/zhwiki/latest/"
ZHWIKTIONARY_TITLES_URL = (
    "https://dumps.wikimedia.org/zhwiktionary/latest/"
    "zhwiktionary-latest-all-titles-in-ns0.gz"
)
ZHWIKTIONARY_HOMEPAGE = "https://dumps.wikimedia.org/zhwiktionary/latest/"
CURATED_DAILY_PHRASES_URL = "repo://manifests/curated_daily_phrases.tsv"
CURATED_DAILY_SUPPLEMENT_PHRASES_URL = "repo://manifests/curated_daily_supplement_phrases.tsv"
CURATED_DAILY_PHRASES_HOMEPAGE = "https://github.com/shenmin/cassotis-lexicon"
VERTICAL_LAYERS_MANIFEST_DEFAULT = "manifests/vertical_layers.public.json"
WIKIMEDIA_PAGEVIEWS_TOP_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/zh.wikipedia/all-access"
WIKIMEDIA_PAGEVIEWS_TOP_HOMEPAGE = "https://wikitech.wikimedia.org/wiki/Analytics/AQS/Pageviews"
MESH_DESCRIPTOR_XML_URL = f"https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc{dt.date.today().year}.xml"
MESH_HOMEPAGE = "https://www.nlm.nih.gov/mesh/meshhome.html"
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIDATA_HOMEPAGE = "https://www.wikidata.org/wiki/Wikidata:Main_Page"
DEFAULT_PINYIN_OVERRIDES = "manifests/pinyin_overrides.tsv"
DEFAULT_PERMISSIVE_OVERRIDES = "manifests/pinyin_overrides.clean_permissive.tsv"
DEFAULT_HTTP_USER_AGENT = "cassotis-lexicon/1.0 (+https://github.com/shenmin/cassotis-lexicon)"
COMPUTING_VERTICAL_FILTER_KEYWORDS = (
    "程序",
    "代码",
    "源码",
    "编译",
    "解释",
    "变量",
    "函数",
    "字段",
    "类型",
    "结构",
    "构造",
    "命令",
    "配置",
    "封装",
    "实例",
    "递归",
    "线程",
    "协程",
    "并发",
    "异步",
    "回调",
    "事件",
    "内存",
    "缓存",
    "环境",
    "虚拟",
    "容器",
    "镜像",
    "网关",
    "协议",
    "中间件",
    "数据库",
    "索引",
    "主键",
    "外键",
    "查询",
    "事务",
    "序列",
    "插件",
    "扩展",
    "驱动",
    "调试",
    "断点",
    "测试",
    "回归",
    "集成",
    "单元",
    "部署",
    "持续",
    "版本",
    "依赖",
    "开发者",
    "类名",
    "父类",
    "子类",
    "对象",
    "接口",
    "组件",
    "服务端",
    "客户端",
    "应用程序",
    "数据结构",
    "数据类型",
    "命令行",
    "生命周期",
    "成员变量",
    "头文件",
    "构造函数",
    "环境变量",
    "配置文件",
    "包管理",
    "负载",
    "垃圾回收",
)
MEDICAL_MESH_TREE_PREFIXES = ("A", "C", "D", "E", "F", "G", "N")
MEDICAL_SHORT_TERM_HINTS = (
    "癌", "病", "症", "炎", "瘤", "菌", "毒", "药", "藥", "疗", "療", "诊", "診",
    "术", "術", "血", "肝", "肺", "肾", "腎", "胃", "胆", "膽", "胰", "腺", "脉",
    "脈", "痛", "热", "熱", "寒", "液", "針", "针", "酸", "素", "酶", "醇", "胺",
    "糖", "尿", "疫", "苗", "咳", "喘", "泻", "瀉", "疹", "疮", "瘡", "瘫", "癱",
    "栓", "醉", "麻", "痰", "疡", "疣", "癣", "癬", "膜", "骨", "脑", "腦", "心",
)
LOW_PRIORITY_MEDICAL_PROCEDURE_TERMS = {
    "堕胎",
    "墮胎",
}
VerticalEntry = Tuple[str, str, float, str, str, str]
WIKIDATA_MEDICAL_MESH_QUERY = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?term ?mesh WHERE {
  {
    ?item wdt:P486 ?mesh ;
          rdfs:label ?label .
    FILTER(LANG(?label) = "zh")
    BIND(STR(?label) AS ?term)
  }
  UNION
  {
    ?item wdt:P486 ?mesh ;
          skos:altLabel ?alt .
    FILTER(LANG(?alt) = "zh")
    BIND(STR(?alt) AS ?term)
  }
  __MESH_PREFIX_FILTER__
}
"""
COMPUTING_VERTICAL_FILTER_EXACT = {
    "字符串",
    "数组",
    "初始化",
    "字段",
    "控件",
    "文件名",
    "递归",
    "多线程",
    "迭代",
    "数组",
    "接口",
    "指针",
    "节点",
    "线程",
    "进程",
    "编程",
    "编码",
    "解码",
    "算法",
    "脚本",
    "组件",
    "模块",
    "插件",
    "框架",
    "内核",
    "终端",
    "日志",
    "异常",
    "调试",
    "部署",
    "容器",
    "镜像",
    "缓存",
    "索引",
    "事务",
    "数据库",
    "协议",
    "网关",
    "控件",
    "实例化",
}
GAMING_LEXICAL_FILTER_EXACT = {
    "开黑",
    "联机",
    "副本",
    "团本",
    "关卡",
    "存档",
    "读档",
    "主机",
    "掌机",
    "手柄",
    "手游",
    "端游",
    "页游",
    "氪金",
    "抽卡",
    "卡池",
    "保底",
    "掉落",
    "暴击",
    "冷却",
    "血条",
    "蓝条",
    "回蓝",
    "回魔",
    "成就",
    "奖杯",
    "攻略",
    "排位",
    "段位",
    "上分",
    "补刀",
    "打野",
    "射手",
    "辅助",
    "中单",
    "上单",
    "下路",
    "团战",
    "出装",
    "符文",
    "天赋",
    "肉鸽",
    "类魂",
    "周目",
    "刷图",
    "跑图",
    "开荒",
}
GAMING_LEXICAL_FILTER_KEYWORDS = (
    "游戏",
    "玩家",
    "联机",
    "副本",
    "关卡",
    "存档",
    "读档",
    "开黑",
    "电竞",
    "排位",
    "段位",
    "上分",
    "补刀",
    "打野",
    "射手",
    "辅助",
    "中单",
    "上单",
    "下路",
    "团战",
    "出装",
    "符文",
    "天赋",
    "氪金",
    "抽卡",
    "卡池",
    "保底",
    "掉落",
    "暴击",
    "冷却",
    "血条",
    "蓝条",
    "回蓝",
    "回魔",
    "成就",
    "奖杯",
    "攻略",
    "主机",
    "掌机",
    "手柄",
    "手游",
    "端游",
    "页游",
    "开放世界",
    "沙盒",
    "像素风",
    "肉鸽",
    "类魂",
    "平台跳跃",
    "动作冒险",
    "动作游戏",
    "冒险游戏",
    "角色扮演",
    "回合制",
    "即时战略",
    "模拟经营",
    "生存建造",
    "独立游戏",
    "游戏引擎",
    "游戏主机",
    "游戏平台",
    "游戏类型",
)
GODOT_GAMEDEV_FILTER_EXACT = {
    "节点",
    "场景",
    "信号",
    "脚本",
    "资源",
    "视口",
    "相机",
    "网格",
    "骨骼",
    "粒子",
    "材质",
    "着色器",
    "输入映射",
    "动画树",
    "动画播放器",
    "补间动画",
    "碰撞体",
    "碰撞层",
    "碰撞掩码",
    "物理材质",
    "瓦片地图",
    "导航网格",
    "导航代理",
    "角色身体",
    "刚体",
    "静态体",
    "软体",
    "区域",
    "状态机",
}
GODOT_GAMEDEV_FILTER_KEYWORDS = (
    "节点",
    "场景",
    "动画",
    "碰撞",
    "导航",
    "瓦片",
    "信号",
    "脚本",
    "输入",
    "物理",
    "材质",
    "渲染",
    "着色器",
    "骨骼",
    "网格",
    "补间",
    "视口",
    "粒子",
    "相机",
    "角色身体",
    "状态机",
    "资源",
)
GODOT_GAMEDEV_BLOCKED_PREFIXES = (
    "为",
    "从",
    "使用",
    "如何",
    "为什么",
    "与你",
    "与",
    "在",
    "将",
    "让",
    "创建",
    "导出",
    "优化",
    "你的",
    "什么是",
    "何时",
    "启用",
    "禁用",
    "切换",
    "下载",
    "安装",
    "配置",
    "运行",
    "编写",
    "构建",
    "转换",
    "获取",
    "伪造",
)
GODOT_GAMEDEV_BLOCKED_SUFFIXES = (
    "说明",
    "概览",
    "教程",
    "指南",
    "步骤",
    "示例",
    "实例",
    "方案",
    "属性",
    "方法",
    "问题",
    "选项",
    "性能",
    "知识",
    "基础",
    "标签",
    "参数",
    "预览",
)
DAILY_CHAT_SEED_PREFIXES = (
    "不",
    "没",
    "别",
    "这",
    "那",
    "哪",
    "怎",
    "为",
    "有",
    "无",
    "可",
    "能",
    "会",
    "要",
    "想",
    "该",
    "真",
    "挺",
    "太",
    "好",
    "先",
    "再",
    "还",
    "也",
    "就",
    "才",
    "又",
    "都",
    "老",
    "总",
)
DAILY_CHAT_SEED_SUFFIXES = (
    "吗",
    "呢",
    "吧",
    "呀",
    "啊",
    "嘛",
    "哦",
    "呗",
    "啦",
    "喽",
    "哟",
    "了",
    "着",
    "过",
    "是",
    "说",
    "看",
    "来",
    "去",
)
DAILY_CHAT_SEED_CHARS = set("的得地就也还才又都把被给跟让像向对从为在将这那哪怎啥谁您你我他她它咱吗呢吧呀啊嘛哦呗啦了着过说看来去")
DAILY_CHAT_SEED_CHARS.update(("將",))
DAILY_CHAT_SEED_CHARS.update(("\u6539", "\u6210"))
DAILY_ASPECT_SUFFIX_CHARS = set("\u4e86\u7740\u8fc7")
CURATED_PRODUCTIVE_STATE_PREFIX_CHARS = set("\u5df2\u6ca1\u6c92\u672a")
DERIVED_PREFIX_BLOCKED_TAIL_CHARS = set(
    "\u800c\u4e4b\u6240\u4e0e\u8207\u53ca\u548c\u6216\u5c06\u5c07"
    "\u88ab\u628a\u7684\u5730\u5f97"
)
STRONG_TWO_CHAR_DAILY_HEAD_CHARS = set(
    "\u4e0d\u6ca1\u522b\u8fd9\u90a3\u54ea\u600e\u5565\u8c01\u60a8\u4f60\u6211\u4ed6\u5979\u5b83\u54b1"
    "\u6709\u65e0\u53ef\u80fd\u4f1a\u8981\u60f3\u8be5\u771f\u633a\u592a\u597d\u5148\u518d\u8fd8\u4e5f"
    "\u5c31\u624d\u53c8\u90fd\u8001\u603b\u6539"
)
STRONG_TWO_CHAR_DAILY_TAIL_CHARS = set(
    "\u5417\u5462\u5427\u5440\u554a\u561b\u54e6\u5457\u5566\u4e86\u7740\u8fc7"
    "\u662f\u7684\u5f97\u6765\u53bb\u770b\u8bf4\u505a\u641e\u5f04\u95ee\u67e5\u542c\u8bd5\u6539"
    "\u7ed9\u8981\u4f1a\u80fd\u884c\u597d\u5bf9\u9519\u5fd9\u7d2f\u723d\u75bc\u75db\u6210"
)
LOW_SIGNAL_FRAGMENT_HEAD_CHARS = set(
    "\u6765\u4f86\u53bb\u770b\u8bf4\u8aaa\u505a\u641e\u5f04\u542c\u807d\u95ee\u554f\u8bd5\u8a66\u60f3"
    "\u8981\u80fd\u4f1a\u6703\u7ed9\u7d66\u5e2e\u53eb\u627e\u7b49\u8ba9\u8b93\u5e26\u5e36\u966a"
)
LOW_SIGNAL_FRAGMENT_TAIL_SUFFIXES = (
    "\u5f97",
)
DAILY_NUMBER_WORD_CHARS = set(
    "\u4e00\u4e8c\u4e24\u5169\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d"
    "\u5341\u767e\u5343\u4e07\u842c\u4ebf\u5104"
)
DAILY_NUMBER_WORD_UNIT_CHARS = set(
    "\u5341\u767e\u5343\u4e07\u842c\u4ebf\u5104"
)
CURATED_DAILY_NUMBER_WEIGHT_CAP = 700
CURATED_DAILY_COUNT_MEASURE_WEIGHT_CAP = 420
CURATED_DAILY_HOUSING_COUNT_MEASURE_WEIGHT_CAP = 420
CURATED_DAILY_VISIBILITY_WEIGHT_CAP_SHORT = 700
CURATED_DAILY_VISIBILITY_WEIGHT_CAP_LONG = 800
CURATED_DAILY_SUPPLEMENT_WEIGHT_CAP = 280
CURATED_DAILY_SUPPLEMENT_NUMBER_WEIGHT_CAP = 520
CURATED_DAILY_ASPECT_VISIBILITY_CAP = 760
CURATED_DAILY_POST_RANK_EXACT_USAGE_MAX = -1.99
CURATED_DAILY_POST_RANK_ZERO_WEIGHT_USAGE_MAX = -2.0
CURATED_DAILY_POST_RANK_FIXED_WEIGHT_USAGE_BASE = -3.0
CURATED_DAILY_EXACT_ZERO_MODE = "exact_zero"
CURATED_DAILY_EXACT_RANK_MODE = "exact_rank"
CURATED_DAILY_NO_CONTAINS_MODE = "no_contains"
CURATED_DAILY_EXACT_RANK_NO_CONTAINS_MODE = "exact_rank_no_contains"


def _curated_daily_supplement_weight_cap(usage_score: float, text: str) -> int:
    """Cap low-frequency exact supplements without letting visibility imply priority."""
    # Negative usage is a build-only marker handled by the post-rank injector.
    if usage_score < 0.0:
        return 0
    bounded_usage = max(0.0, min(1.0, usage_score))
    if _is_pure_daily_number_word(text):
        return CURATED_DAILY_SUPPLEMENT_NUMBER_WEIGHT_CAP

    # Ultra-low scores are for useful exact-match words that should remain
    # inputable but should not become attractive long-sentence path chunks.
    if bounded_usage <= 0.0:
        return 1
    if bounded_usage < 0.10:
        return 8 + int(round(bounded_usage * 240.0))

    return CURATED_DAILY_SUPPLEMENT_WEIGHT_CAP


def _partition_curated_daily_post_rank_exact_entries(
    entries: List[Tuple[str, str, float, str]],
) -> Tuple[
    List[Tuple[str, str, float, str]],
    List[Tuple[str, str, float, str]],
]:
    """Keep exact-only visibility rows out of global ranking calculations."""
    regular_entries: List[Tuple[str, str, float, str]] = []
    post_rank_entries: List[Tuple[str, str, float, str]] = []
    for entry in entries:
        if entry[2] <= CURATED_DAILY_POST_RANK_EXACT_USAGE_MAX:
            post_rank_entries.append(entry)
        else:
            regular_entries.append(entry)
    return regular_entries, post_rank_entries


def _inject_curated_daily_post_rank_exact_entries(
    sc_map: Dict[Tuple[str, str], int],
    tc_map: Dict[Tuple[str, str], int],
    entries: List[Tuple[str, str, float, str]],
) -> Dict[str, int]:
    """Add exact-only rows after every ranking and path-prior stage."""
    stats = {
        "curated_daily_post_rank_exact_rows": len(entries),
        "curated_daily_post_rank_exact_sc_added": 0,
        "curated_daily_post_rank_exact_tc_added": 0,
        "curated_daily_post_rank_exact_sc_forced_zero": 0,
        "curated_daily_post_rank_exact_tc_forced_zero": 0,
        "curated_daily_post_rank_exact_sc_forced_rank": 0,
        "curated_daily_post_rank_exact_tc_forced_rank": 0,
        "curated_daily_post_rank_exact_invalid_pinyin": 0,
    }
    for sc_word, tc_word, usage_score, explicit_pinyin in entries:
        pinyin = _normalize_pinyin(explicit_pinyin)
        if not pinyin:
            stats["curated_daily_post_rank_exact_invalid_pinyin"] += 1
            continue

        # Keep the legacy -2.0 zero-weight and -1.99 visibility sentinels
        # intact. Values below -3 encode a fixed post-rank weight, allowing an
        # exact candidate to rank naturally without entering path statistics.
        if usage_score <= CURATED_DAILY_POST_RANK_FIXED_WEIGHT_USAGE_BASE:
            exact_weight = max(
                1,
                min(
                    1000,
                    int(
                        round(
                            (
                                -usage_score
                                + CURATED_DAILY_POST_RANK_FIXED_WEIGHT_USAGE_BASE
                            )
                            * 1000.0
                        )
                    ),
                ),
            )
        elif usage_score <= CURATED_DAILY_POST_RANK_ZERO_WEIGHT_USAGE_MAX:
            exact_weight = 0
        else:
            exact_weight = 1

        sc_key = (pinyin, sc_word)
        if sc_key not in sc_map:
            sc_map[sc_key] = exact_weight
            stats["curated_daily_post_rank_exact_sc_added"] += 1
        elif usage_score <= CURATED_DAILY_POST_RANK_FIXED_WEIGHT_USAGE_BASE:
            if sc_map[sc_key] != exact_weight:
                stats["curated_daily_post_rank_exact_sc_forced_rank"] += 1
            sc_map[sc_key] = exact_weight
        elif usage_score <= CURATED_DAILY_POST_RANK_ZERO_WEIGHT_USAGE_MAX:
            if sc_map[sc_key] != exact_weight:
                stats["curated_daily_post_rank_exact_sc_forced_zero"] += 1
            sc_map[sc_key] = exact_weight

        tc_text = tc_word or sc_word
        tc_key = (pinyin, tc_text)
        if tc_key not in tc_map:
            tc_map[tc_key] = exact_weight
            stats["curated_daily_post_rank_exact_tc_added"] += 1
        elif usage_score <= CURATED_DAILY_POST_RANK_FIXED_WEIGHT_USAGE_BASE:
            if tc_map[tc_key] != exact_weight:
                stats["curated_daily_post_rank_exact_tc_forced_rank"] += 1
            tc_map[tc_key] = exact_weight
        elif usage_score <= CURATED_DAILY_POST_RANK_ZERO_WEIGHT_USAGE_MAX:
            if tc_map[tc_key] != exact_weight:
                stats["curated_daily_post_rank_exact_tc_forced_zero"] += 1
            tc_map[tc_key] = exact_weight
    return stats

# Quantity-classifier snippets are useful exact matches, but they are not
# necessarily more common than same-pinyin lexical words. Keep them visible
# without giving them the full daily/chat priority floor.
DAILY_COUNT_MEASURE_CHARS = set("把本部对栋副幅根幢件轮盘匹批片篇瓶扇双台条桶页项只爿间間套房厅廳卫衛室厨廚种種")
DAILY_HOUSING_COUNT_MEASURE_CHARS = set("间間套房厅廳卫衛室厨廚")
DAILY_COUNT_PREFIX_CHARS = set("一二两三四五六七八九十几每")
DAILY_TRADITIONAL_COUNT_PREFIX_CHARS = set("兩幾")
# Fiction entities and public/historical people names are supplemental named
# entities and should not inherit everyday-word priors. Product/platform proper
# nouns have their own conservative cap: exact matches should stay visible, but
# the brand/proper-noun layer should not reinforce them like daily words.
NAMED_ENTITY_VERTICAL_LAYERS = {"fiction_entities", "people_names"}
LOW_PRIORITY_VERTICAL_ENTITY_SOURCE_PREFIXES = (
    "wikidata-video-game",
)

CEDICT_LINE_RE = re.compile(r"^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.*)/$")
CJK_RE = re.compile("[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002A6DF]")
CJK_FULL_RE = re.compile(
    "^[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002A6DF]+$"
)
CJK_WINDOWS_FULL_RE = re.compile("^[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+$")
PINYIN_RE = re.compile(r"^[a-z]+$")
EXPLICIT_PINYIN_RE = re.compile(r"^[a-z]+(?:'[a-z]+)*$")
UNIHAN_SOURCE_HANYU_EXTRA = 1
UNIHAN_SOURCE_MANDARIN = 2
UNIHAN_SOURCE_PINLU = 3
UNIHAN_HANYU_EXTRA_WEIGHT_CAP = 160
COMMON_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦马苗凤花方俞任袁柳鲍史唐费廉岑薛"
    "雷贺倪汤滕殷罗毕郝邬安常乐于傅皮卞齐康伍余元顾孟平黄和穆萧尹姚邵湛汪"
    "祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路"
    "娄危江童颜郭梅盛林钟徐邱骆高夏蔡田樊胡凌霍虞万柯卢莫房解应宗丁宣贲邓"
    "郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴"
    "糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘斜厉戎"
    "祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔"
    "阴郁胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀"
    "郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿"
    "满弘匡国文寇广禄阙东殴殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空"
    "曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公"
)
COMMON_COMPOUND_SURNAMES = {
    "欧阳",
    "司马",
    "上官",
    "诸葛",
    "夏侯",
    "东方",
    "皇甫",
    "尉迟",
    "公孙",
    "慕容",
    "司徒",
    "司空",
    "令狐",
    "宇文",
    "长孙",
    "独孤",
    "南宫",
}

LOW_SIGNAL_PLACE_SUFFIXES = (
    "\u5e02",
    "\u53bf",
    "\u533a",
    "\u9547",
    "\u6751",
    "\u4e61",
    "\u5dde",
    "\u90e1",
    "\u5821",
    "\u6e7e",
    "\u5cad",
    "\u5c9b",
    "\u6c5f",
    "\u6cb3",
    "\u6e56",
    "\u5c71",
    "\u6865",
    "\u7ad9",
    "\u8def",
    "\u8857",
)

LOW_SIGNAL_LITERARY_CHARS = set(
    "\u516e\u77e3\u7109\u6b24\u54c9\u4e4e\u5b70\u76cd\u532a\u6bcb\u5f17\u5c82"
    "\u76d6\u4e43\u9042\u65af\u5176\u82e5\u592b"
)

LOW_SIGNAL_LITERARY_SUFFIXES = (
    "\u4e4b",
    "\u4e4e",
    "\u7109",
    "\u77e3",
    "\u6b24",
    "\u54c9",
    "\u8033",
)

LOW_SIGNAL_WRITTEN_TAIL_SUFFIXES = (
    "\u8005",
    "\u4e5f",
    "\u7109",
    "\u77e3",
    "\u54c9",
    "\u8033",
    "\u4e4e",
    "\u516e",
)

LOW_SIGNAL_WRITTEN_TAIL_HEADS = set(
    "\u5176\u4e8e\u4e43\u65af\u4ee5\u56e0\u6545\u8bfa\u65bc\u4e8c\u82e5\u592b\u51e1\u76d6\u9042\u83ab\u5f17\u672a\u5179\u8bf8"
)

# Some explicit TC<->SC single-character variant relations are not safe to
# apply as a global char-for-char rewrite. These pairs remain shared for at
# least one side in modern usage, so script filtering must be relaxed.
#
# Mapping value:
#   (keep_trad_in_sc, keep_simp_in_tc)
#
# The list below is intentionally audited and conservative. It is derived from
# CEDICT/OpenCC evidence, but excludes noisy mixed-script entries such as
# 夥/伙 and 摺/折 that should not be surfaced in modern simplified output.
SHARED_SCRIPT_VARIANT_BEHAVIOR: Dict[Tuple[str, str], Tuple[bool, bool]] = {
    ("乾", "干"): (True, True),
    ("徵", "征"): (True, True),
    ("瞭", "了"): (True, True),
    ("著", "着"): (True, False),
    ("藉", "借"): (True, True),
    ("覆", "复"): (True, False),
    ("阪", "坂"): (True, True),
    ("纔", "才"): (False, True),
}

# Audited single-character reading overrides. Keep this hook available, but
# prefer algorithmic phrase-support calibration before adding explicit entries.
SINGLE_CHAR_READING_DROP_OVERRIDES: Set[Tuple[str, str]] = {
    # `哦/e` exists as a marginal colloquial reading, but standalone `e` input
    # should not surface it as a single-character candidate at all.
    ("哦", "e"),
}
SINGLE_CHAR_READING_DELTA_OVERRIDES: Dict[Tuple[str, str], int] = {
    # Keep U+5594 visible under its wo reading without competing with everyday wo.
    ("\u5594", "wo"): 160,
    # Keep U+54E6 as the dominant everyday standalone o reading.
    ("\u54e6", "o"): 360,
    # Keep common standalone function/action targets visible ahead of rarer
    # same-pinyin characters without changing phrase dictionary weights.
    ("\u8fc7", "guo"): 80,
    ("\u904e", "guo"): 60,
    ("\u9609", "yan"): 160,
    ("\u95b9", "yan"): 100,
    # `是/shi` is the dominant standalone IME target for shi in both SC and TC.
    ("是", "shi"): 90,
    # Keep 阮 visible as a common surname and standalone lexical target without
    # overriding 软 as the dominant everyday ruan reading.
    ("阮", "ruan"): 320,
    # Keep 朊 visible for medical contexts after vertical medical terms are
    # isolated from single-character support derivation.
    ("朊", "ruan"): 220,
    # Keep 爿 visible for standalone lookup under its modern pan reading.
    ("爿", "pan"): 120,
    # `难/難` is the everyday standalone target for nan; geographic/name
    # support can keep 南 visible, but should not outrank the common adjective.
    ("难", "nan"): 180,
    ("難", "nan"): 180,
    # `付/fu` is a common standalone action target (payment, delivery, handing
    # over). Broad compound evidence understates that standalone usefulness.
    ("付", "fu"): 140,
    # Keep the common function-word reading above same-pinyin content roots.
    ("与", "yu"): 100,
    ("與", "yu"): 100,
    # `图/圖` is the everyday standalone target for tu more often than `土`.
    ("\u56fe", "tu"): 320,
    ("\u5716", "tu"): 280,
}
SINGLE_CHAR_ADDED_READING_WEIGHT_CAP = 280

# Audited pronunciation aliases whose lexical weight should not depend on the
# selected standard reading. Apply these only after filtering and ranking so an
# alias cannot revive a rejected term or influence another pinyin bucket.
LEADING_TEXT_PINYIN_ALIAS_RULES: Tuple[Tuple[str, str, str], ...] = (
    ("谁", "shei", "shui"),
    ("谁", "shui", "shei"),
    ("誰", "shei", "shui"),
    ("誰", "shui", "shei"),
)
SINGLE_CHAR_RELATIVE_ORDER_OVERRIDES: Tuple[
    Tuple[Tuple[str, str], Tuple[str, str], int], ...
] = (
    # Prefer everyday standalone "图/圖" over "土" for tu.
    (("tu", "图"), ("tu", "土"), 16),
    (("tu", "圖"), ("tu", "土"), 16),
    # Simplified-source conversion overstates 简 relative to the much more
    # common standalone verb 见. Keep the correction local to SC output.
    (("jian", "见"), ("jian", "简"), 16),
    # 咯 is the everyday sentence-final particle for lo; keep it ahead of the
    # uncommon variant 囖. Its other secondary readings should remain visible.
    (("lo", "咯"), ("lo", "囖"), 16),
    (("ka", "咯"), ("ka", "佧"), 16),
    (("luo", "咯"), ("luo", "箩"), 16),
    (("luo", "咯"), ("luo", "籮"), 16),
)

MULTI_CHAR_TERM_DROP_OVERRIDES: Set[str] = {
    # Legacy orthography no longer preferred in modern IME usage.
    "补钉",
    "補釘",
    # Context-specific connector phrase; too sentence-like for lexicon output.
    "\u968f\u5373\u518d\u6b21",
    "\u96a8\u5373\u518d\u6b21",
    # Closed particle pairs are handled by exact IME rules instead of lexicon
    # entries, otherwise AB+tail composition can recursively create odd forms.
    "\u7684\u5417",
    "\u7684\u55ce",
    # Removed from curated daily: sentence fragments mined from narrow context
    # should not re-enter generated dictionaries through external title seeds.
    "不便表现",
    "不便表現",
    "不得不考虑",
    "不得不考慮",
    "不再使用",
    "程序员沟通",
    "程序員溝通",
    "吹了会儿",
    "吹了會兒",
    "吹了会儿风",
    "吹了會兒風",
    "得到应答",
    "得到應答",
    "得到了应答",
    "得到了應答",
    "更有效地",
    "关于是否",
    "關於是否",
    "归因结果",
    "歸因結果",
    "很快得到",
    "角度去看",
    "极度不悦",
    "極度不悅",
    "技术斗争",
    "技術鬥爭",
    "技术声誉",
    "技術聲譽",
    "开发进程",
    "開發進程",
    "客户群里",
    "客戶群裡",
    "刻意放慢",
    "快速盘算",
    "快速盤算",
    "来电关心",
    "來電關心",
    "人的提议",
    "人的提議",
    "商业范畴",
    "商業範疇",
    "稍微缓解",
    "稍微緩解",
    "深感担忧",
    "深感擔憂",
    "外部租用",
    "完全信任",
    "现在需要",
    "現在需要",
    "行为目标",
    "行為目標",
    "心里暗自",
    "心裡暗自",
    "心里充满",
    "心裡充滿",
    "一种做法",
    "一種做法",
    "邮件转给",
    "郵件轉給",
    "昨日状况",
    "昨日狀況",
    # Low-signal CEDICT noise; the standard everyday target is 花费/花費.
    "华废",
    "華廢",
}

MULTI_CHAR_TERM_DROP_SUBSTRINGS: Set[str] = {
    # Deprecated or erroneous orthographic variants. Drop compounds containing
    # these fragments as well; keep the standard forms `片段` and `模板`.
    "片断",
    "片斷",
    "模版",
    "模闆",
}


def _is_explicit_multi_char_drop_text(text: str) -> bool:
    if len(text) <= 1:
        return False
    if text in MULTI_CHAR_TERM_DROP_OVERRIDES:
        return True
    return any(fragment in text for fragment in MULTI_CHAR_TERM_DROP_SUBSTRINGS)

COPYLEFT_LICENSE_TOKENS = (
    "by-sa",
    "gpl",
    "lgpl",
    "agpl",
    "gfdl",
    "copyleft",
)

QUERY_PATH_FILE_SEPARATOR = "|"

PROFILE_DEFAULTS: Dict[str, Dict[str, object]] = {
    "external_cedict": {
        "parser": "cedict",
        "sources": [
            {
                "id": "cc-cedict",
                "name": "CC-CEDICT",
                "download_url": CEDICT_DEFAULT_URL,
                "homepage": CEDICT_HOMEPAGE,
                "license": "CC BY-SA 4.0",
                "risk_level": "medium",
                "redistribution_class": "copyleft_sharealike",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Parsed to pinyin<TAB>text<TAB>weight format.",
            },
            {
                "id": "unicode-unihan-readings",
                "name": "Unicode Unihan_Readings",
                "download_url": UNICODE_UNIHAN_URL,
                "homepage": UNICODE_HOMEPAGE,
                "license": "Unicode-3.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Character-level Mandarin readings for curated daily phrase pinyin generation.",
            },
            {
                "id": "project-curated-daily-phrases",
                "name": "Cassotis curated daily/chat phrases",
                "download_url": CURATED_DAILY_PHRASES_URL,
                "homepage": CURATED_DAILY_PHRASES_HOMEPAGE,
                "license": "Repository license (project-authored)",
                "risk_level": "low",
                "redistribution_class": "project_authored",
                "attribution_required": False,
                "raw_committed": True,
                "notes": "Project-maintained daily/chat phrase whitelist layered on top of CEDICT.",
            },
            {
                "id": "project-curated-daily-supplement-phrases",
                "name": "Cassotis low-frequency daily supplements",
                "download_url": CURATED_DAILY_SUPPLEMENT_PHRASES_URL,
                "homepage": CURATED_DAILY_PHRASES_HOMEPAGE,
                "license": "Repository license (project-authored)",
                "risk_level": "low",
                "redistribution_class": "project_authored",
                "attribution_required": False,
                "raw_committed": True,
                "notes": "Project-maintained exact-match supplements that should remain visible without inheriting daily/chat preferred-term weight.",
            },
        ],
    },
    "external_broad": {
        "parser": "cedict_thuocl_jieba_opencc_unihan_wiki",
        "sources": [
            {
                "id": "cc-cedict",
                "name": "CC-CEDICT",
                "download_url": CEDICT_DEFAULT_URL,
                "homepage": CEDICT_HOMEPAGE,
                "license": "CC BY-SA 4.0",
                "risk_level": "medium",
                "redistribution_class": "copyleft_sharealike",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Core dictionary entries with word-level pinyin.",
            },
            {
                "id": "thuocl",
                "name": "THUOCL (Tsinghua Open Chinese Lexicon)",
                "download_url": THUOCL_ZIP_URL,
                "homepage": THUOCL_HOMEPAGE,
                "license": "THUOCL custom open terms",
                "risk_level": "medium",
                "redistribution_class": "attribution_required",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Domain/common words with DF statistics, used for broad coverage.",
            },
            {
                "id": "opencc-stphrases",
                "name": "OpenCC STPhrases",
                "download_url": OPENCC_STPHRASES_URL,
                "homepage": OPENCC_HOMEPAGE,
                "license": "Apache-2.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "SC->TC phrase mapping for broad-profile TC expansion.",
            },
            {
                "id": "jieba-dict",
                "name": "jieba dict.txt",
                "download_url": JIEBA_DICT_URL,
                "homepage": JIEBA_HOMEPAGE,
                "license": "MIT",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Word-frequency dictionary used as ranking signal.",
            },
            {
                "id": "unicode-unihan-readings",
                "name": "Unicode Unihan_Readings",
                "download_url": UNICODE_UNIHAN_URL,
                "homepage": UNICODE_HOMEPAGE,
                "license": "Unicode-3.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Character-level Mandarin readings for pinyin fallback.",
            },
            {
                "id": "zhwiktionary-titles-ns0",
                "name": "Wiktionary zh titles (ns0)",
                "download_url": ZHWIKTIONARY_TITLES_URL,
                "homepage": ZHWIKTIONARY_HOMEPAGE,
                "license": "CC BY-SA 4.0",
                "risk_level": "medium",
                "redistribution_class": "copyleft_sharealike",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Daily/colloquial lexical entries used as direct seed for modern chat phrasing.",
            },
            {
                "id": "project-curated-daily-phrases",
                "name": "Cassotis curated daily/chat phrases",
                "download_url": CURATED_DAILY_PHRASES_URL,
                "homepage": CURATED_DAILY_PHRASES_HOMEPAGE,
                "license": "Repository license (project-authored)",
                "risk_level": "low",
                "redistribution_class": "project_authored",
                "attribution_required": False,
                "raw_committed": True,
                "notes": "Project-maintained high-value daily/chat phrase whitelist for IME-friendly everyday input.",
            },
            {
                "id": "project-curated-daily-supplement-phrases",
                "name": "Cassotis low-frequency daily supplements",
                "download_url": CURATED_DAILY_SUPPLEMENT_PHRASES_URL,
                "homepage": CURATED_DAILY_PHRASES_HOMEPAGE,
                "license": "Repository license (project-authored)",
                "risk_level": "low",
                "redistribution_class": "project_authored",
                "attribution_required": False,
                "raw_committed": True,
                "notes": "Project-maintained exact-match supplements for useful but lower-frequency daily-adjacent terms; isolated from daily/chat preferred-term ranking.",
            },
            {
                "id": "zhwiki-titles-ns0",
                "name": "Wikipedia zh titles (ns0)",
                "download_url": ZHWIKI_TITLES_URL,
                "homepage": ZHWIKI_HOMEPAGE,
                "license": "CC BY-SA 4.0",
                "risk_level": "medium",
                "redistribution_class": "copyleft_sharealike",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Used as broad coverage and ranking signal for common named terms.",
            },
            {
                "id": "wikimedia-pageviews-top",
                "name": "Wikimedia Pageviews Top (zh.wikipedia)",
                "download_url": WIKIMEDIA_PAGEVIEWS_TOP_URL,
                "homepage": WIKIMEDIA_PAGEVIEWS_TOP_HOMEPAGE,
                "license": "CC BY-SA 4.0",
                "risk_level": "medium",
                "redistribution_class": "copyleft_sharealike",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Monthly top pageviews are aggregated as real-world usage heat signal.",
            },
        ],
    },
    "clean_permissive": {
        "parser": "opencc_unihan",
        "sources": [
            {
                "id": "opencc-stphrases",
                "name": "OpenCC STPhrases",
                "download_url": OPENCC_STPHRASES_URL,
                "homepage": OPENCC_HOMEPAGE,
                "license": "Apache-2.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Simplified/Traditional phrase mapping source.",
            },
            {
                "id": "unicode-unihan-readings",
                "name": "Unicode Unihan_Readings",
                "download_url": UNICODE_UNIHAN_URL,
                "homepage": UNICODE_HOMEPAGE,
                "license": "Unicode-3.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Character-level Mandarin readings for pinyin generation.",
            },
        ],
    },
    "unihan_single": {
        "parser": "unihan_only",
        "sources": [
            {
                "id": "opencc-stphrases",
                "name": "OpenCC STPhrases",
                "download_url": OPENCC_STPHRASES_URL,
                "homepage": OPENCC_HOMEPAGE,
                "license": "Apache-2.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Used for script split hints (SC/TC) in Unihan-only generation.",
            },
            {
                "id": "unicode-unihan-readings",
                "name": "Unicode Unihan_Readings",
                "download_url": UNICODE_UNIHAN_URL,
                "homepage": UNICODE_HOMEPAGE,
                "license": "Unicode-3.0",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Single-character Mandarin readings with frequency/rank metadata.",
            },
            {
                "id": "jieba-dict",
                "name": "jieba dict.txt",
                "download_url": JIEBA_DICT_URL,
                "homepage": JIEBA_HOMEPAGE,
                "license": "MIT",
                "risk_level": "low",
                "redistribution_class": "permissive",
                "attribution_required": True,
                "raw_committed": False,
                "notes": "Single-character lexical frequency signal used to keep standalone IME ordering from being dominated by compound-root support.",
            },
        ],
    },
}


def _parse_bool(text: str) -> bool:
    value = text.strip().lower()
    if value in {"true", "1", "yes", "y"}:
        return True
    if value in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean text: {text}")


def _to_yaml_bool(value: bool) -> str:
    return "true" if value else "false"


def _yaml_single_quote(value: object) -> str:
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", "\\n")
    return "'" + text.replace("'", "''") + "'"


def _load_vertical_layer_sources(
    manifest_path: pathlib.Path,
) -> Tuple[List[Dict[str, object]], Dict[str, int]]:
    stats = {
        "vertical_layers_manifest_present": 0,
        "vertical_layers_declared": 0,
        "vertical_layers_active": 0,
        "vertical_layer_sources_total": 0,
        "vertical_layer_sources_loaded": 0,
        "vertical_layer_sources_skipped_inactive": 0,
        "vertical_layer_sources_skipped_unsupported": 0,
    }
    if not manifest_path.exists():
        return [], stats
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    stats["vertical_layers_manifest_present"] = 1

    loaded_sources: List[Dict[str, object]] = []
    for layer in data.get("layers", []):
        if not isinstance(layer, dict):
            continue
        stats["vertical_layers_declared"] += 1
        layer_id = str(layer.get("id", "")).strip()
        if not layer_id:
            continue
        layer_status = str(layer.get("status", "active")).strip().lower()
        if layer_status != "active":
            continue
        stats["vertical_layers_active"] += 1
        layer_title = str(layer.get("title", layer_id)).strip() or layer_id
        layer_notes = str(layer.get("notes", "")).strip()
        for source in layer.get("sources", []):
            if not isinstance(source, dict):
                continue
            stats["vertical_layer_sources_total"] += 1
            source_status = str(source.get("status", "active")).strip().lower()
            if source_status != "active":
                stats["vertical_layer_sources_skipped_inactive"] += 1
                continue
            source_type = str(source.get("type", "repo_tsv")).strip().lower()
            if source_type not in {
                "repo_tsv",
                "thuocl_zip_member",
                "mesh_descriptor_catalog",
                "wikidata_mesh_query",
                "wikidata_term_query",
                "sparql_term_query",
                "payload_titles_filter",
                "godot_searchindex_titles",
            }:
                stats["vertical_layer_sources_skipped_unsupported"] += 1
                continue

            source_id = str(source.get("id", "")).strip()
            source_name = str(source.get("name", "")).strip()
            download_url = str(source.get("download_url", "")).strip()
            if not source_id or not source_name or not download_url:
                continue

            default_usage_score = source.get("default_usage_score", 0.72)
            try:
                default_usage_score = float(default_usage_score)
            except (TypeError, ValueError):
                default_usage_score = 0.72

            loaded_sources.append(
                {
                    "id": source_id,
                    "name": source_name,
                    "download_url": download_url,
                    "homepage": str(source.get("homepage", CURATED_DAILY_PHRASES_HOMEPAGE)).strip()
                    or CURATED_DAILY_PHRASES_HOMEPAGE,
                    "license": str(source.get("license", "Repository license (project-authored)")).strip()
                    or "Repository license (project-authored)",
                    "risk_level": str(source.get("risk_level", "low")).strip() or "low",
                    "redistribution_class": str(source.get("redistribution_class", "project_authored")).strip()
                    or "project_authored",
                    "attribution_required": bool(source.get("attribution_required", False)),
                    "raw_committed": bool(source.get("raw_committed", True)),
                    "notes": str(source.get("notes", layer_notes)).strip() or layer_notes,
                    "vertical_layer_id": layer_id,
                    "vertical_layer_title": layer_title,
                    "vertical_source_type": source_type,
                    "vertical_default_usage_score": min(1.0, max(0.0, default_usage_score)),
                    "vertical_payload_source_id": str(source.get("payload_source_id", "")).strip(),
                    "vertical_member_name": str(source.get("member_name", "")).strip(),
                    "vertical_filter_id": str(source.get("filter_id", "")).strip(),
                    "vertical_cache_file": str(source.get("cache_file", "")).strip(),
                    "vertical_query": str(source.get("query", "")).strip(),
                    "vertical_mesh_source_id": str(source.get("mesh_source_id", "")).strip(),
                    "vertical_mesh_tree_prefixes": str(source.get("mesh_tree_prefixes", "")).strip(),
                    "vertical_max_hanzi": int(source.get("max_hanzi", 8) or 8),
                }
            )
            stats["vertical_layer_sources_loaded"] += 1

    return loaded_sources, stats


def _normalize_pinyin_token(token: str) -> str:
    value = token.strip().lower()
    value = value.replace("u:", "v").replace("v:", "v")
    for ch in ("ü", "ǖ", "ǘ", "ǚ", "ǜ"):
        value = value.replace(ch, "v")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[1-5]", "", value)
    value = re.sub(r"[^a-zv]", "", value)
    return value


def _normalize_pinyin(raw: str) -> str:
    tokens = raw.strip().split()
    normalized: List[str] = []
    for token in tokens:
        value = _normalize_pinyin_token(token)
        if value:
            normalized.append(value)

    if not normalized:
        return ""

    merged = "".join(normalized)
    if not PINYIN_RE.fullmatch(merged):
        return ""
    return merged


def _normalize_explicit_pinyin(raw: str) -> str:
    """Normalize a manifest override without discarding explicit boundaries."""
    value = raw.strip().lower()
    value = value.replace("\u2018", "'").replace("\u2019", "'").replace("\u02bc", "'")
    raw_parts = value.split("'")
    if not raw_parts or any(not part.strip() for part in raw_parts):
        return ""

    normalized_parts = [_normalize_pinyin(part) for part in raw_parts]
    if any(not part for part in normalized_parts):
        return ""
    normalized = "'".join(normalized_parts)
    if not EXPLICIT_PINYIN_RE.fullmatch(normalized):
        return ""
    return normalized


def _normalize_compact_pinyin_key(raw: str) -> str:
    value = raw.strip().lower()
    value = value.replace("’", "'").replace("'", "")
    value = re.sub(r"\s+", "", value)
    return value


# Keep this compact-prefix parser aligned with nc_pinyin_parser.pas. Transition
# completions are keyed by what the runtime parser sees, so a prefix that would
# be split along different syllable boundaries must be rejected offline.
_RUNTIME_PINYIN_INITIALS = (
    "zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l", "g",
    "k", "h", "j", "q", "x", "r", "z", "c", "s", "y", "w",
)
_RUNTIME_PINYIN_FINALS = (
    "iang", "iong", "uang", "uai", "uan", "iao", "ian", "ing", "ang",
    "eng", "ong", "ai", "an", "ao", "ei", "en", "er", "ou", "ia",
    "ie", "in", "iu", "ua", "ui", "un", "uo", "ve", "van", "vn",
    "ue", "a", "e", "i", "o", "u", "v",
)
_RUNTIME_PINYIN_FINALS_NO_INITIAL = (
    "ang", "eng", "ai", "an", "ao", "ei", "en", "er", "ou", "a", "e",
    "o", "r",
)


def _runtime_initial_final_compatible(initial: str, final: str) -> bool:
    if final == "er":
        return False
    if initial in {"b", "p", "m", "f", "w"} and len(final) > 1 and final[0] == "u":
        return False
    if initial == "y" and final not in {
        "a", "an", "ang", "ao", "e", "i", "in", "ing", "o", "ong", "ou",
        "u", "ue", "uan", "un",
    }:
        return False
    if initial == "w" and final not in {
        "a", "ai", "an", "ang", "ei", "en", "eng", "o", "u",
    }:
        return False
    if initial in {"j", "q", "x"} and final in {"ua", "uai", "uang", "ui", "uo"}:
        return False
    if initial in {"zh", "ch", "sh", "r", "z", "c", "s"} and final in {
        "ia", "in", "ing", "iu", "ie", "ian", "iang", "iao", "iong", "ue",
        "ve", "van", "vn",
    }:
        return False
    if initial in {"b", "p", "m", "f", "d", "t", "g", "k", "h"} and final in {
        "iang", "iong",
    }:
        return False
    return True


def _runtime_parse_compact_pinyin(raw: str) -> List[str]:
    """Mirror TncPinyinParser's deterministic best compact segmentation."""

    text = raw.strip().lower()
    if not text:
        return []
    memo: Dict[int, Tuple[int, int, str] | None] = {}

    def no_initial_penalty(final: str, start: int) -> int:
        if start <= 0 or text[start - 1] == "'":
            return 0
        if final in {"a", "e", "o"}:
            return 160
        if final == "er":
            return 100
        if final == "r":
            return 1200 if start > 0 and text[start - 1] == "e" else 80
        return 20

    def solve(start: int) -> int:
        if start >= len(text):
            return 0
        if start in memo:
            value = memo[start]
            return value[0] if value is not None else -(10**9)
        if text[start] == "'":
            score = solve(start + 1)
            memo[start] = (score, start + 1, "")
            return score

        best_score = -(10**9)
        best_next = start + 1
        best_text = text[start]
        for initial in _RUNTIME_PINYIN_INITIALS:
            if not text.startswith(initial, start):
                continue
            final_start = start + len(initial)
            for final in _RUNTIME_PINYIN_FINALS:
                if (
                    _runtime_initial_final_compatible(initial, final)
                    and text.startswith(final, final_start)
                ):
                    token = initial + final
                    next_index = start + len(token)
                    score = solve(next_index) + len(token) * len(token) * 10
                    if score > best_score:
                        best_score, best_next, best_text = score, next_index, token

        for final in _RUNTIME_PINYIN_FINALS_NO_INITIAL:
            if not text.startswith(final, start):
                continue
            next_index = start + len(final)
            score = (
                solve(next_index)
                + len(final) * len(final) * 10
                - no_initial_penalty(final, start)
            )
            if score > best_score:
                best_score, best_next, best_text = score, next_index, final

        fallback_score = solve(start + 1) - 1000
        if fallback_score > best_score:
            best_score, best_next, best_text = fallback_score, start + 1, text[start]
        memo[start] = (best_score, best_next, best_text)
        return best_score

    solve(0)
    result: List[str] = []
    cursor = 0
    while cursor < len(text):
        if text[cursor] == "'":
            cursor += 1
            continue
        value = memo.get(cursor)
        if value is None or value[1] <= cursor or not value[2]:
            result.append(text[cursor])
            cursor += 1
            continue
        result.append(value[2])
        cursor = value[1]
    return result


def _unihan_reading_score_vector(
    ch: str,
    pinyin: str,
    unihan_map: Dict[str, str],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
) -> Tuple[int, int, int, int, int, int]:
    source_rank = unihan_source_rank_map.get((ch, pinyin), 0)
    pinlu_count = max(0, unihan_pinlu_detail_map.get((ch, pinyin), 0))
    default_bonus = 1 if source_rank >= UNIHAN_SOURCE_MANDARIN and pinyin == unihan_map.get(ch, "") else 0
    return (
        1 if source_rank >= UNIHAN_SOURCE_MANDARIN else 0,
        source_rank,
        1 if pinlu_count > 0 else 0,
        pinlu_count,
        1 if len(pinyin) > 1 else 0,
        default_bonus,
    )


def _candidate_unihan_readings_for_char(
    ch: str,
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
) -> List[str]:
    readings = {value for value in unihan_readings_map.get(ch, set()) if value}
    default_pinyin = unihan_map.get(ch, "")
    if default_pinyin:
        readings.add(default_pinyin)
    if not readings:
        return []

    best_source_rank = max(unihan_source_rank_map.get((ch, value), 0) for value in readings)
    if best_source_rank >= UNIHAN_SOURCE_MANDARIN:
        readings = {
            value
            for value in readings
            if unihan_source_rank_map.get((ch, value), 0) >= UNIHAN_SOURCE_MANDARIN
        }

    return sorted(
        readings,
        key=lambda value: (
            _unihan_reading_score_vector(
                ch,
                value,
                unihan_map,
                unihan_source_rank_map,
                unihan_pinlu_detail_map,
            ),
            value,
        ),
        reverse=True,
    )


def _best_unihan_pinyin_syllables(
    text: str,
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
) -> List[str] | None:
    syllables: List[str] = []
    for ch in text:
        if not CJK_RE.match(ch):
            return None
        readings = _candidate_unihan_readings_for_char(
            ch,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not readings:
            return None
        syllables.append(readings[0])
    return syllables


def _split_compact_pinyin_by_unihan(
    text: str,
    compact_pinyin: str,
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
) -> List[str] | None:
    compact = _normalize_compact_pinyin_key(compact_pinyin)
    if not compact or _cjk_len(text) <= 0:
        return None

    chars = [ch for ch in text]
    reading_candidates: List[List[str]] = []
    for ch in chars:
        readings = _candidate_unihan_readings_for_char(
            ch,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not readings:
            return None
        reading_candidates.append(readings)

    score_cache: Dict[Tuple[str, str], Tuple[int, int, int, int, int, int]] = {}

    def score_vector(ch: str, pinyin: str) -> Tuple[int, int, int, int, int, int]:
        key = (ch, pinyin)
        value = score_cache.get(key)
        if value is None:
            value = _unihan_reading_score_vector(
                ch,
                pinyin,
                unihan_map,
                unihan_source_rank_map,
                unihan_pinlu_detail_map,
            )
            score_cache[key] = value
        return value

    memo: Dict[Tuple[int, int], Tuple[List[str], Tuple[int, int, int, int, int, int]] | None] = {}

    def dfs(char_index: int, offset: int) -> Tuple[List[str], Tuple[int, int, int, int, int, int]] | None:
        key = (char_index, offset)
        if key in memo:
            return memo[key]
        if char_index >= len(chars):
            memo[key] = ([], (0, 0, 0, 0, 0, 0)) if offset == len(compact) else None
            return memo[key]

        best: Tuple[List[str], Tuple[int, int, int, int, int, int]] | None = None
        for reading in reading_candidates[char_index]:
            if not compact.startswith(reading, offset):
                continue
            tail = dfs(char_index + 1, offset + len(reading))
            if tail is None:
                continue
            tail_syllables, tail_score = tail
            local_score = score_vector(chars[char_index], reading)
            combined_score = tuple(local_score[i] + tail_score[i] for i in range(len(local_score)))
            combined_syllables = [reading] + tail_syllables
            if best is None or combined_score > best[1]:
                best = (combined_syllables, combined_score)

        memo[key] = best
        return best

    result = dfs(0, 0)
    if result is None:
        return None
    return result[0]


def _format_canonical_pinyin_syllables(syllables: List[str]) -> str:
    if not syllables:
        return ""
    parts = [syllables[0]]
    for syllable in syllables[1:]:
        if syllable and syllable[0] in {"a", "e", "o"}:
            parts.append("'" + syllable)
        else:
            parts.append(syllable)
    return "".join(parts)


def _canonicalize_output_pinyin(
    compact_pinyin: str,
    text: str,
    unihan_map: Dict[str, str] | None,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
) -> str:
    compact = _normalize_compact_pinyin_key(compact_pinyin)
    if not compact:
        return ""
    if (
        _cjk_len(text) <= 1
        or not unihan_map
        or not unihan_readings_map
        or not unihan_source_rank_map
        or not unihan_pinlu_detail_map
    ):
        return compact

    syllables = _split_compact_pinyin_by_unihan(
        text,
        compact,
        unihan_map,
        unihan_readings_map,
        unihan_source_rank_map,
        unihan_pinlu_detail_map,
    )
    if not syllables or "".join(syllables) != compact:
        return compact
    return _format_canonical_pinyin_syllables(syllables)


def _cjk_len(text: str) -> int:
    return len(CJK_RE.findall(text))


def _split_text_units(text: str) -> List[str]:
    return [ch for ch in text if ch]


def _is_windows_renderable_cjk_text(text: str) -> bool:
    return bool(CJK_WINDOWS_FULL_RE.fullmatch(text))


def _matches_vertical_filter(text: str, filter_id: str) -> bool:
    filter_id = filter_id.strip().lower()
    if not filter_id:
        return True
    if filter_id == "computing_heuristic":
        if text in COMPUTING_VERTICAL_FILTER_EXACT:
            return True
        return any(keyword in text for keyword in COMPUTING_VERTICAL_FILTER_KEYWORDS)
    if filter_id == "gaming_lexical_heuristic":
        if text in GAMING_LEXICAL_FILTER_EXACT:
            return True
        return any(keyword in text for keyword in GAMING_LEXICAL_FILTER_KEYWORDS)
    if filter_id == "game_dev_lexical_heuristic":
        if text in GODOT_GAMEDEV_FILTER_EXACT:
            return True
        return any(keyword in text for keyword in GODOT_GAMEDEV_FILTER_KEYWORDS)
    if filter_id == "godot_gamedev_heuristic":
        compact = text.strip().replace(" ", "").replace("_", "")
        if compact in GODOT_GAMEDEV_FILTER_EXACT:
            return True
        if not any(keyword in compact for keyword in GODOT_GAMEDEV_FILTER_KEYWORDS):
            return False
        if compact.startswith(GODOT_GAMEDEV_BLOCKED_PREFIXES):
            return False
        if compact.endswith(GODOT_GAMEDEV_BLOCKED_SUFFIXES):
            return False
        return 2 <= _cjk_len(compact) <= 10
    if filter_id == "idioms_allusions_heuristic":
        text_len = _cjk_len(text)
        if text_len < 4 or text_len > 10:
            return False
        return CJK_FULL_RE.fullmatch(text) is not None
    return True


def _resolve_optional_repo_path(
    repo_root: pathlib.Path,
    relative_path: str,
) -> pathlib.Path | None:
    relative_path = relative_path.strip()
    if not relative_path:
        return None
    relative = pathlib.PurePosixPath(relative_path.replace("\\", "/"))
    return repo_root.joinpath(*relative.parts)


def _build_vertical_source_request_url(source: Dict[str, object]) -> str:
    source_url = str(source.get("download_url", "")).strip()
    source_type = str(source.get("vertical_source_type", "repo_tsv")).strip().lower()
    if source_type not in {"wikidata_mesh_query", "wikidata_term_query", "sparql_term_query"}:
        return source_url

    parsed = urllib.parse.urlparse(source_url)
    existing = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered = [(key, value) for key, value in existing if key.lower() not in {"query", "format"}]
    filtered.append(("format", "json"))
    rebuilt = parsed._replace(query=urllib.parse.urlencode(filtered))
    return urllib.parse.urlunparse(rebuilt)


def _download_wikidata_sparql_bytes(url: str, query: str) -> bytes:
    post_data = urllib.parse.urlencode({"query": query}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=post_data,
        headers={
            "User-Agent": DEFAULT_HTTP_USER_AGENT,
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        },
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return response.read()
        except Exception as exc:
            last_error = exc
            if attempt >= 2:
                raise
            time.sleep(1.0 + attempt * 1.5)
    if last_error is not None:
        raise last_error
    raise RuntimeError("unreachable")


def _iter_wikidata_mesh_prefix_queries(query: str) -> Iterator[str]:
    if "__MESH_PREFIX_FILTER__" not in query:
        yield query
        return
    for suffix in range(10):
        prefix_filter = f'FILTER(STRSTARTS(?mesh, "D0{suffix}"))'
        yield query.replace("__MESH_PREFIX_FILTER__", prefix_filter)


def _download_wikidata_mesh_query_payload(url: str, query: str) -> bytes:
    combined_bindings: List[Dict[str, object]] = []
    vars_list: List[str] = ["term", "mesh"]
    for chunk_query in _iter_wikidata_mesh_prefix_queries(query):
        chunk_payload = _download_wikidata_sparql_bytes(url, chunk_query)
        chunk_text = chunk_payload.decode("utf-8", errors="ignore").strip()
        chunk_data = json.loads(chunk_text)
        head_vars = chunk_data.get("head", {}).get("vars")
        if isinstance(head_vars, list) and head_vars:
            vars_list = [str(value) for value in head_vars]
        results = chunk_data.get("results", {}).get("bindings", [])
        if isinstance(results, list):
            combined_bindings.extend(results)
    combined_payload = {
        "head": {"vars": vars_list},
        "results": {"bindings": combined_bindings},
    }
    return json.dumps(combined_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _download_wikidata_term_query_payload(url: str, query: str) -> bytes:
    return _download_wikidata_sparql_bytes(url, query)


def _download_sparql_term_query_payload(url: str, query: str) -> bytes:
    return _download_wikidata_sparql_bytes(url, query)


def _is_valid_wikidata_sparql_payload(payload: bytes) -> bool:
    stripped = payload.lstrip()
    if not stripped:
        return False
    if stripped.startswith(b"{"):
        try:
            data = json.loads(stripped.decode("utf-8", errors="ignore"))
        except json.JSONDecodeError:
            return False
        results = data.get("results", {})
        return isinstance(results, dict) and isinstance(results.get("bindings"), list)
    if stripped.startswith(b"<"):
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return False
        return root.tag.endswith("sparql")
    return False


def _prefetch_vertical_source_payloads(
    vertical_sources: List[Dict[str, object]],
    repo_root: pathlib.Path,
) -> Dict[str, bytes]:
    payloads: Dict[str, bytes] = {}
    for source in vertical_sources:
        source_type = str(source.get("vertical_source_type", "repo_tsv")).strip().lower()
        if source_type == "thuocl_zip_member":
            continue
        source_id = str(source.get("id", "")).strip()
        if not source_id:
            continue
        cache_file = _resolve_optional_repo_path(repo_root, str(source.get("vertical_cache_file", "")))
        if source_type == "wikidata_mesh_query":
            if cache_file and cache_file.exists():
                cached_payload = cache_file.read_bytes()
                if _is_valid_wikidata_sparql_payload(cached_payload):
                    payloads[source_id] = cached_payload
                    continue
            url = _build_vertical_source_request_url(source)
            query = str(source.get("vertical_query", "")).strip()
            payload = _download_wikidata_mesh_query_payload(url, query)
            if cache_file:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(payload)
            payloads[source_id] = payload
            continue
        if source_type == "wikidata_term_query":
            if cache_file and cache_file.exists():
                cached_payload = cache_file.read_bytes()
                if _is_valid_wikidata_sparql_payload(cached_payload):
                    payloads[source_id] = cached_payload
                    continue
            url = _build_vertical_source_request_url(source)
            query = str(source.get("vertical_query", "")).strip()
            payload = _download_wikidata_term_query_payload(url, query)
            if cache_file:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(payload)
            payloads[source_id] = payload
            continue
        if source_type == "sparql_term_query":
            if cache_file and cache_file.exists():
                cached_payload = cache_file.read_bytes()
                if _is_valid_wikidata_sparql_payload(cached_payload):
                    payloads[source_id] = cached_payload
                    continue
            url = _build_vertical_source_request_url(source)
            query = str(source.get("vertical_query", "")).strip()
            payload = _download_sparql_term_query_payload(url, query)
            if cache_file:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(payload)
            payloads[source_id] = payload
            continue
        url = _build_vertical_source_request_url(source)
        payloads[source_id] = _read_source_bytes(url, cache_file, repo_root=repo_root)
    return payloads


def _parse_mesh_descriptor_allowed_ids(
    payload: bytes,
    *,
    allowed_prefixes: Tuple[str, ...] = MEDICAL_MESH_TREE_PREFIXES,
) -> Tuple[Set[str], Dict[str, int]]:
    stats = {
        "vertical_mesh_descriptors_total": 0,
        "vertical_mesh_descriptors_medical": 0,
        "vertical_mesh_descriptors_nonmedical": 0,
    }
    allowed_ids: Set[str] = set()
    prefix_set = tuple(prefix.strip().upper() for prefix in allowed_prefixes if prefix.strip())
    stream = io.BytesIO(payload)
    for _event, elem in ET.iterparse(stream, events=("end",)):
        if not elem.tag.endswith("DescriptorRecord"):
            continue
        stats["vertical_mesh_descriptors_total"] += 1
        descriptor_ui = ""
        tree_numbers: List[str] = []
        for child in elem.iter():
            if child.tag.endswith("DescriptorUI"):
                descriptor_ui = (child.text or "").strip().upper()
            elif child.tag.endswith("TreeNumber"):
                value = (child.text or "").strip().upper()
                if value:
                    tree_numbers.append(value)
        if descriptor_ui and any(number.startswith(prefix_set) for number in tree_numbers):
            allowed_ids.add(descriptor_ui)
            stats["vertical_mesh_descriptors_medical"] += 1
        else:
            stats["vertical_mesh_descriptors_nonmedical"] += 1
        elem.clear()
    return allowed_ids, stats


def _parse_wikidata_bindings(payload: bytes) -> List[Tuple[str, str]]:
    stripped = payload.lstrip()
    results: List[Tuple[str, str]] = []
    if stripped.startswith(b"{"):
        data = json.loads(stripped.decode("utf-8", errors="ignore"))
        for item in data.get("results", {}).get("bindings", []):
            if not isinstance(item, dict):
                continue
            term = str(item.get("term", {}).get("value", "")).strip()
            mesh_id = str(item.get("mesh", {}).get("value", "")).strip().upper()
            if term and mesh_id:
                results.append((term, mesh_id))
        return results

    root = ET.fromstring(payload)
    ns = {"sr": "http://www.w3.org/2005/sparql-results#"}
    for result in root.findall(".//sr:result", ns):
        term = ""
        mesh_id = ""
        for binding in result.findall("sr:binding", ns):
            name = binding.get("name", "")
            literal = binding.find("sr:literal", ns)
            value = (literal.text or "").strip() if literal is not None else ""
            if name == "term":
                term = value
            elif name == "mesh":
                mesh_id = value.upper()
        if term and mesh_id:
            results.append((term, mesh_id))
    return results


def _parse_wikidata_term_bindings(payload: bytes) -> List[str]:
    stripped = payload.lstrip()
    results: List[str] = []
    if stripped.startswith(b"{"):
        data = json.loads(stripped.decode("utf-8", errors="ignore"))
        for item in data.get("results", {}).get("bindings", []):
            if not isinstance(item, dict):
                continue
            term = str(item.get("term", {}).get("value", "")).strip()
            if term:
                results.append(term)
        return results

    root = ET.fromstring(payload)
    ns = {"sr": "http://www.w3.org/2005/sparql-results#"}
    for result in root.findall(".//sr:result", ns):
        for binding in result.findall("sr:binding", ns):
            name = binding.get("name", "")
            if name != "term":
                continue
            literal = binding.find("sr:literal", ns)
            value = (literal.text or "").strip() if literal is not None else ""
            if value:
                results.append(value)
    return results


def _build_opencc_variant_context(
    opencc_payload: bytes | None,
) -> Tuple[
    List[Tuple[str, str]],
    Dict[str, Set[str]],
    Dict[str, Set[str]],
    Dict[str, str],
    Dict[str, str],
]:
    opencc_entries: List[Tuple[str, str]] = []
    opencc_sc_to_tc: Dict[str, Set[str]] = {}
    opencc_tc_to_sc: Dict[str, Set[str]] = {}
    trad_to_simp_char_map: Dict[str, str] = {}
    simp_to_trad_char_map: Dict[str, str] = {}
    if not opencc_payload:
        return (
            opencc_entries,
            opencc_sc_to_tc,
            opencc_tc_to_sc,
            trad_to_simp_char_map,
            simp_to_trad_char_map,
        )

    opencc_entries, _ = _parse_opencc_entries(_decode_text(opencc_payload), 1)
    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    opencc_tc_to_sc = _build_opencc_tc_to_sc_map(opencc_entries)
    trad_to_simp_char_map, simp_to_trad_char_map, _sc_chars, _tc_chars = _build_char_variant_hints(
        opencc_tc_to_sc,
        opencc_entries,
    )
    return (
        opencc_entries,
        opencc_sc_to_tc,
        opencc_tc_to_sc,
        trad_to_simp_char_map,
        simp_to_trad_char_map,
    )


def _map_vertical_term_to_sc_tc(
    term: str,
    opencc_sc_to_tc: Dict[str, Set[str]],
    opencc_tc_to_sc: Dict[str, Set[str]],
    trad_to_simp_char_map: Dict[str, str],
    simp_to_trad_char_map: Dict[str, str],
) -> Tuple[str, str]:
    sc_candidate = term
    tc_candidate = term
    mapped_sc_words = opencc_tc_to_sc.get(term, set())
    mapped_tc_words = opencc_sc_to_tc.get(term, set())
    if mapped_sc_words:
        sc_candidate = sorted(mapped_sc_words)[0]
        tc_candidate = term
    elif mapped_tc_words:
        sc_candidate = term
        tc_candidate = sorted(mapped_tc_words)[0]
    elif trad_to_simp_char_map:
        sc_candidate = _convert_text_with_char_map(term, trad_to_simp_char_map)
        tc_candidate = _convert_sc_text_to_tc_with_phrase_hints(
            sc_candidate,
            opencc_sc_to_tc,
            simp_to_trad_char_map,
        )
    return sc_candidate, tc_candidate


def _parse_wikidata_term_query_entries(
    payload: bytes,
    opencc_payload: bytes | None,
    min_hanzi: int,
    default_usage_score: float,
    filter_id: str,
    max_hanzi: int,
) -> Tuple[List[Tuple[str, str, float, str]], Dict[str, int]]:
    stats = {
        "vertical_wikidata_term_rows": 0,
        "vertical_wikidata_term_kept": 0,
        "vertical_wikidata_term_skipped_non_cjk": 0,
        "vertical_wikidata_term_skipped_short": 0,
        "vertical_wikidata_term_skipped_long": 0,
        "vertical_wikidata_term_skipped_filter": 0,
        "vertical_wikidata_term_skipped_duplicate": 0,
    }
    (
        _opencc_entries,
        opencc_sc_to_tc,
        opencc_tc_to_sc,
        trad_to_simp_char_map,
        simp_to_trad_char_map,
    ) = _build_opencc_variant_context(opencc_payload)
    default_usage_score = min(1.0, max(0.0, default_usage_score))
    entries: List[Tuple[str, str, float, str]] = []
    seen_pairs: Set[Tuple[str, str]] = set()
    for term in _parse_wikidata_term_bindings(payload):
        stats["vertical_wikidata_term_rows"] += 1
        normalized, reason = _normalize_wiki_title_with_reason(
            term,
            min_hanzi=min_hanzi,
            max_hanzi=max_hanzi,
        )
        if not normalized:
            if reason == "non_cjk":
                stats["vertical_wikidata_term_skipped_non_cjk"] += 1
            elif reason == "short":
                stats["vertical_wikidata_term_skipped_short"] += 1
            elif reason == "long":
                stats["vertical_wikidata_term_skipped_long"] += 1
            else:
                stats["vertical_wikidata_term_skipped_non_cjk"] += 1
            continue
        if filter_id and not _matches_vertical_filter(normalized, filter_id):
            stats["vertical_wikidata_term_skipped_filter"] += 1
            continue
        sc_candidate, tc_candidate = _map_vertical_term_to_sc_tc(
            normalized,
            opencc_sc_to_tc,
            opencc_tc_to_sc,
            trad_to_simp_char_map,
            simp_to_trad_char_map,
        )
        pair_key = (sc_candidate, tc_candidate)
        if pair_key in seen_pairs:
            stats["vertical_wikidata_term_skipped_duplicate"] += 1
            continue
        seen_pairs.add(pair_key)
        entries.append((sc_candidate, tc_candidate, default_usage_score, ""))
        stats["vertical_wikidata_term_kept"] += 1
    return entries, stats


def _parse_payload_titles_filter_entries(
    payload: bytes,
    opencc_payload: bytes | None,
    min_hanzi: int,
    default_usage_score: float,
    filter_id: str,
    max_hanzi: int,
) -> Tuple[List[Tuple[str, str, float, str]], Dict[str, int]]:
    titles, wiki_stats = _parse_wiki_titles_entries(
        payload,
        min_hanzi=min_hanzi,
        max_hanzi=max_hanzi,
    )
    stats: Dict[str, int] = {
        "vertical_payload_titles_candidates": len(titles),
        "vertical_payload_titles_kept": 0,
        "vertical_payload_titles_skipped_filter": 0,
        "vertical_payload_titles_skipped_duplicate": 0,
    }
    for key, value in wiki_stats.items():
        stats[key] = stats.get(key, 0) + value

    (
        _opencc_entries,
        opencc_sc_to_tc,
        opencc_tc_to_sc,
        trad_to_simp_char_map,
        simp_to_trad_char_map,
    ) = _build_opencc_variant_context(opencc_payload)
    default_usage_score = min(1.0, max(0.0, default_usage_score))
    entries: List[Tuple[str, str, float, str]] = []
    seen_pairs: Set[Tuple[str, str]] = set()
    for title in sorted(titles):
        if filter_id and not _matches_vertical_filter(title, filter_id):
            stats["vertical_payload_titles_skipped_filter"] += 1
            continue
        sc_candidate, tc_candidate = _map_vertical_term_to_sc_tc(
            title,
            opencc_sc_to_tc,
            opencc_tc_to_sc,
            trad_to_simp_char_map,
            simp_to_trad_char_map,
        )
        pair_key = (sc_candidate, tc_candidate)
        if pair_key in seen_pairs:
            stats["vertical_payload_titles_skipped_duplicate"] += 1
            continue
        seen_pairs.add(pair_key)
        entries.append((sc_candidate, tc_candidate, default_usage_score, ""))
        stats["vertical_payload_titles_kept"] += 1
    return entries, stats


def _parse_godot_searchindex_entries(
    payload: bytes,
    opencc_payload: bytes | None,
    min_hanzi: int,
    default_usage_score: float,
    filter_id: str,
    max_hanzi: int,
) -> Tuple[List[Tuple[str, str, float, str]], Dict[str, int]]:
    stats = {
        "vertical_godot_titles_total": 0,
        "vertical_godot_titles_kept": 0,
        "vertical_godot_titles_skipped_empty": 0,
        "vertical_godot_titles_skipped_colon": 0,
        "vertical_godot_titles_skipped_non_cjk": 0,
        "vertical_godot_titles_skipped_short": 0,
        "vertical_godot_titles_skipped_long": 0,
        "vertical_godot_titles_skipped_filter": 0,
        "vertical_godot_titles_skipped_duplicate": 0,
        "vertical_godot_titles_invalid_format": 0,
        "vertical_godot_titles_invalid_json": 0,
    }
    text = _decode_text(payload).strip()
    if not text.startswith("Search.setIndex("):
        stats["vertical_godot_titles_invalid_format"] += 1
        return [], stats
    json_text = text[len("Search.setIndex("):].strip()
    if json_text.endswith(";"):
        json_text = json_text[:-1].strip()
    if json_text.endswith(")"):
        json_text = json_text[:-1].strip()
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        stats["vertical_godot_titles_invalid_json"] += 1
        return [], stats
    alltitles = data.get("alltitles", {})
    if not isinstance(alltitles, dict):
        stats["vertical_godot_titles_invalid_format"] += 1
        return [], stats

    (
        _opencc_entries,
        opencc_sc_to_tc,
        opencc_tc_to_sc,
        trad_to_simp_char_map,
        simp_to_trad_char_map,
    ) = _build_opencc_variant_context(opencc_payload)
    default_usage_score = min(1.0, max(0.0, default_usage_score))
    entries: List[Tuple[str, str, float, str]] = []
    seen_pairs: Set[Tuple[str, str]] = set()
    for raw_title in alltitles.keys():
        stats["vertical_godot_titles_total"] += 1
        normalized, reason = _normalize_wiki_title_with_reason(
            str(raw_title),
            min_hanzi=min_hanzi,
            max_hanzi=max_hanzi,
        )
        if not normalized:
            if reason == "empty":
                stats["vertical_godot_titles_skipped_empty"] += 1
            elif reason == "colon":
                stats["vertical_godot_titles_skipped_colon"] += 1
            elif reason == "non_cjk":
                stats["vertical_godot_titles_skipped_non_cjk"] += 1
            elif reason == "short":
                stats["vertical_godot_titles_skipped_short"] += 1
            elif reason == "long":
                stats["vertical_godot_titles_skipped_long"] += 1
            else:
                stats["vertical_godot_titles_skipped_non_cjk"] += 1
            continue
        if filter_id and not _matches_vertical_filter(normalized, filter_id):
            stats["vertical_godot_titles_skipped_filter"] += 1
            continue
        sc_candidate, tc_candidate = _map_vertical_term_to_sc_tc(
            normalized,
            opencc_sc_to_tc,
            opencc_tc_to_sc,
            trad_to_simp_char_map,
            simp_to_trad_char_map,
        )
        pair_key = (sc_candidate, tc_candidate)
        if pair_key in seen_pairs:
            stats["vertical_godot_titles_skipped_duplicate"] += 1
            continue
        seen_pairs.add(pair_key)
        entries.append((sc_candidate, tc_candidate, default_usage_score, ""))
        stats["vertical_godot_titles_kept"] += 1
    return entries, stats


def _parse_wikidata_mesh_query_entries(
    payload: bytes,
    mesh_payload: bytes | None,
    opencc_payload: bytes | None,
    min_hanzi: int,
    default_usage_score: float,
    mesh_tree_prefixes: Tuple[str, ...],
) -> Tuple[List[Tuple[str, str, float, str]], Dict[str, int]]:
    stats = {
        "vertical_wikidata_rows": 0,
        "vertical_wikidata_kept": 0,
        "vertical_wikidata_skipped_nonmedical_mesh": 0,
        "vertical_wikidata_skipped_non_cjk": 0,
        "vertical_wikidata_skipped_short": 0,
        "vertical_wikidata_skipped_duplicate": 0,
        "vertical_wikidata_missing_mesh_payload": 0,
    }
    if mesh_payload is None:
        stats["vertical_wikidata_missing_mesh_payload"] += 1
        return [], stats

    allowed_mesh_ids, mesh_stats = _parse_mesh_descriptor_allowed_ids(
        mesh_payload,
        allowed_prefixes=mesh_tree_prefixes,
    )
    for key, value in mesh_stats.items():
        stats[key] = stats.get(key, 0) + value

    opencc_entries: List[Tuple[str, str]] = []
    opencc_sc_to_tc: Dict[str, Set[str]] = {}
    opencc_tc_to_sc: Dict[str, Set[str]] = {}
    trad_to_simp_char_map: Dict[str, str] = {}
    simp_to_trad_char_map: Dict[str, str] = {}
    if opencc_payload:
        opencc_entries, _ = _parse_opencc_entries(_decode_text(opencc_payload), 1)
        opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
        opencc_tc_to_sc = _build_opencc_tc_to_sc_map(opencc_entries)
        trad_to_simp_char_map, simp_to_trad_char_map, _sc_chars, _tc_chars = _build_char_variant_hints(
            opencc_tc_to_sc,
            opencc_entries,
        )

    default_usage_score = min(1.0, max(0.0, default_usage_score))
    entries: List[Tuple[str, str, float, str]] = []
    seen_pairs: Set[Tuple[str, str]] = set()
    for term, mesh_id in _parse_wikidata_bindings(payload):
        stats["vertical_wikidata_rows"] += 1
        if mesh_id not in allowed_mesh_ids:
            stats["vertical_wikidata_skipped_nonmedical_mesh"] += 1
            continue
        if not CJK_FULL_RE.fullmatch(term):
            stats["vertical_wikidata_skipped_non_cjk"] += 1
            continue
        if _cjk_len(term) < min_hanzi:
            stats["vertical_wikidata_skipped_short"] += 1
            continue

        sc_candidate = term
        tc_candidate = term
        mapped_sc_words = opencc_tc_to_sc.get(term, set())
        mapped_tc_words = opencc_sc_to_tc.get(term, set())
        if mapped_sc_words:
            sc_candidate = sorted(mapped_sc_words)[0]
            tc_candidate = term
        elif mapped_tc_words:
            sc_candidate = term
            tc_candidate = sorted(mapped_tc_words)[0]
        elif trad_to_simp_char_map:
            sc_candidate = _convert_text_with_char_map(term, trad_to_simp_char_map)
            tc_candidate = _convert_sc_text_to_tc_with_phrase_hints(
                sc_candidate,
                opencc_sc_to_tc,
                simp_to_trad_char_map,
            )
        pair_key = (sc_candidate, tc_candidate)
        if pair_key in seen_pairs:
            stats["vertical_wikidata_skipped_duplicate"] += 1
            continue
        seen_pairs.add(pair_key)
        entries.append((sc_candidate, tc_candidate, default_usage_score, ""))
        stats["vertical_wikidata_kept"] += 1
    return entries, stats


def _is_medical_specific_term(text: str) -> bool:
    if not text or not CJK_FULL_RE.fullmatch(text):
        return False
    return any(token in text for token in MEDICAL_SHORT_TERM_HINTS)


def _wrap_vertical_entries(
    entries: List[Tuple[str, str, float, str]],
    source: Dict[str, object],
) -> List[VerticalEntry]:
    layer_id = str(source.get("vertical_layer_id", "")).strip()
    source_id = str(source.get("id", "")).strip()
    return [
        (sc_word, tc_word, usage_score, explicit_pinyin, layer_id, source_id)
        for sc_word, tc_word, usage_score, explicit_pinyin in entries
    ]


def _build_vertical_explicit_pinyin_override_map(
    entries: List[VerticalEntry],
) -> Dict[Tuple[str, str], str]:
    overrides: Dict[Tuple[str, str], str] = {}
    for sc_word, _tc_word, _usage_score, explicit_pinyin, layer_id, _source_id in entries:
        if not explicit_pinyin:
            continue
        key = (layer_id, sc_word)
        if key not in overrides:
            overrides[key] = explicit_pinyin
    return overrides


def _build_explicit_term_pinyin_override_map(
    entries: List[VerticalEntry],
) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    for sc_word, tc_word, _usage_score, explicit_pinyin, _layer_id, _source_id in entries:
        if not explicit_pinyin:
            continue
        if sc_word and sc_word not in overrides:
            overrides[sc_word] = explicit_pinyin
        if tc_word and tc_word not in overrides:
            overrides[tc_word] = explicit_pinyin
    return overrides


def _build_curated_daily_explicit_pinyin_override_map(
    entries: List[Tuple[str, str, float, str]],
) -> Dict[str, str]:
    pinyins_by_text: Dict[str, Set[str]] = {}
    for sc_word, tc_word, _usage_score, explicit_pinyin in entries:
        if not explicit_pinyin:
            continue
        if sc_word:
            pinyins_by_text.setdefault(sc_word, set()).add(explicit_pinyin)
        if tc_word:
            pinyins_by_text.setdefault(tc_word, set()).add(explicit_pinyin)

    overrides: Dict[str, str] = {}
    for text, pinyins in pinyins_by_text.items():
        if len(pinyins) == 1:
            overrides[text] = next(iter(pinyins))
    return overrides


def _build_curated_daily_explicit_pinyin_key_set(
    entries: List[Tuple[str, str, float, str]],
) -> Set[Tuple[str, str]]:
    keys: Set[Tuple[str, str]] = set()
    for sc_word, tc_word, _usage_score, explicit_pinyin in entries:
        if not explicit_pinyin:
            continue
        if sc_word:
            keys.add((explicit_pinyin, sc_word))
        if tc_word:
            keys.add((explicit_pinyin, tc_word))
    return keys


def _build_vertical_explicit_pinyin_key_set(
    entries: List[VerticalEntry],
) -> Set[Tuple[str, str]]:
    keys: Set[Tuple[str, str]] = set()
    for sc_word, tc_word, _usage_score, explicit_pinyin, _layer_id, _source_id in entries:
        if not explicit_pinyin or "'" not in explicit_pinyin:
            continue
        if sc_word:
            keys.add((explicit_pinyin, sc_word))
        if tc_word:
            keys.add((explicit_pinyin, tc_word))
    return keys


def _compute_medicine_vertical_penalty(text: str, source_id: str) -> int:
    text_len = _cjk_len(text)
    if text_len <= 2:
        base_penalty = 140
    elif text_len == 3:
        base_penalty = 92
    elif text_len == 4:
        base_penalty = 58
    elif text_len == 5:
        base_penalty = 30
    else:
        base_penalty = 14

    if source_id == "project-curated-vertical-medicine":
        if text_len <= 2:
            relief = 112
        elif text_len <= 4:
            relief = 48
        else:
            relief = 8
    elif source_id == "wikidata-medical-mesh-zh":
        relief = 22 if text_len <= 4 else 6
    else:
        relief = 0

    return max(0, base_penalty - relief)


def _cap_medicine_vertical_weight(weight: int, text: str, source_id: str) -> int:
    """Keep medical vertical terms discoverable without daily-word priority."""
    text_len = _cjk_len(text)
    source = source_id.strip().lower()

    if source == "project-curated-vertical-medicine":
        if text_len <= 2:
            cap = 460
        elif text_len == 3:
            cap = 520
        elif text_len == 4:
            cap = 590
        elif text_len == 5:
            cap = 660
        else:
            cap = 720
    elif source == "wikidata-medical-mesh-zh":
        if text_len <= 2:
            cap = 430
        elif text_len == 3:
            cap = 500
        elif text_len == 4:
            cap = 570
        elif text_len == 5:
            cap = 640
        else:
            cap = 700
    else:
        if text_len <= 2:
            cap = 400
        elif text_len == 3:
            cap = 470
        elif text_len == 4:
            cap = 540
        elif text_len == 5:
            cap = 610
        else:
            cap = 680

    return min(weight, cap)


def _cap_generic_vertical_weight(weight: int, text: str, layer_id: str, source_id: str) -> int:
    """Keep imported vertical short terms visible without letting them dominate daily exact input."""
    text_len = _cjk_len(text)
    if text_len <= 0:
        return weight

    source = source_id.strip().lower()
    if layer_id in NAMED_ENTITY_VERTICAL_LAYERS:
        # Names and fiction entities should stay selectable for exact input, but
        # short names are visibility signals rather than broad frequency signals.
        # Keep them below ordinary daily/common words in the same pinyin bucket.
        if text_len <= 2:
            cap = 620
        elif text_len == 3:
            cap = 700
        else:
            cap = 760
        return min(weight, cap)
    if layer_id == "proper_nouns":
        if text_len <= 2:
            cap = 1000
        elif text_len == 3:
            cap = 780
        elif text_len == 4:
            cap = 720
        elif text_len == 5:
            cap = 700
        else:
            cap = 700
        return min(weight, cap)
    if layer_id == "architecture_entities":
        if text_len <= 2:
            cap = 420
        elif text_len == 3:
            cap = 520
        elif text_len == 4:
            cap = 600
        else:
            cap = 660
        return min(weight, cap)
    if layer_id == "gaming" and source.startswith(LOW_PRIORITY_VERTICAL_ENTITY_SOURCE_PREFIXES):
        if text_len <= 2:
            cap = 360
        elif text_len == 3:
            cap = 460
        elif text_len == 4:
            cap = 560
        elif text_len == 5:
            cap = 640
        else:
            cap = 720
        return min(weight, cap)
    if layer_id == "architecture_terms":
        if source == "project-curated-vertical-architecture-terms":
            if text_len <= 2:
                cap = 420
            elif text_len == 3:
                cap = 620
            elif text_len == 4:
                cap = 680
            else:
                cap = 760
        else:
            if text_len <= 2:
                # Externally imported short architecture labels are useful as
                # exact candidates, but should not outrank broad daily/common
                # homophones such as qiangzhi=强制. Project-curated architecture
                # terms keep the higher cap above.
                cap = 260
            elif text_len == 3:
                cap = 600
            elif text_len == 4:
                cap = 680
            else:
                cap = 760
        return min(weight, cap)

    return weight


def _cap_project_vertical_exact_weights(
    mapping: Dict[Tuple[str, str], int],
    vertical_entries: List[VerticalEntry],
    *,
    use_traditional: bool,
    stats_prefix: str,
) -> Dict[str, int]:
    """Apply vertical-layer caps after all restore/merge passes."""
    stats = {
        f"{stats_prefix}_project_vertical_exact_rows": 0,
        f"{stats_prefix}_project_vertical_exact_capped": 0,
    }
    if not mapping or not vertical_entries:
        return stats

    for sc_word, tc_word, _usage_score, explicit_pinyin, layer_id, source_id in vertical_entries:
        text = tc_word if use_traditional and tc_word else sc_word
        if not text or not explicit_pinyin:
            continue
        source = source_id.strip().lower()
        if not source.startswith("project-curated"):
            continue

        key = (explicit_pinyin, text)
        weight = mapping.get(key)
        if weight is None:
            continue

        stats[f"{stats_prefix}_project_vertical_exact_rows"] += 1
        if layer_id == "medicine":
            capped = _cap_medicine_vertical_weight(weight, text, source_id)
        else:
            capped = _cap_generic_vertical_weight(weight, text, layer_id, source_id)
        if capped < weight:
            mapping[key] = capped
            stats[f"{stats_prefix}_project_vertical_exact_capped"] += 1

    return stats


def _restore_project_proper_noun_exact_floor(
    mapping: Dict[Tuple[str, str], int],
    vertical_entries: List[VerticalEntry],
    *,
    use_traditional: bool,
    stats_prefix: str,
) -> Dict[str, int]:
    """Keep curated proper nouns exact-visible after generic low-signal filters."""
    stats = {
        f"{stats_prefix}_project_proper_exact_floor_rows": 0,
        f"{stats_prefix}_project_proper_exact_floor_restored": 0,
    }
    if not mapping or not vertical_entries:
        return stats

    for sc_word, tc_word, _usage_score, explicit_pinyin, layer_id, source_id in vertical_entries:
        if layer_id != "proper_nouns" or source_id != "project-curated-proper-nouns":
            continue
        text = tc_word if use_traditional and tc_word else sc_word
        if not text or not explicit_pinyin:
            continue

        key = (explicit_pinyin, text)
        weight = mapping.get(key)
        if weight is None:
            continue

        text_len = _cjk_len(text)
        if text_len <= 2:
            floor = 360
        elif text_len == 3:
            floor = 420
        else:
            floor = 480
        floor = _cap_generic_vertical_weight(floor, text, layer_id, source_id)

        stats[f"{stats_prefix}_project_proper_exact_floor_rows"] += 1
        if weight < floor:
            mapping[key] = floor
            stats[f"{stats_prefix}_project_proper_exact_floor_restored"] += 1

    return stats


def _cap_medical_specific_term_weights(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    curated_daily_terms: Set[str],
    stats_prefix: str,
) -> Dict[str, int]:
    """Cap medical-domain fragments that enter through generic sources."""
    stats = {
        f"{stats_prefix}_medical_specific_capped": 0,
        f"{stats_prefix}_low_priority_medical_procedure_capped": 0,
    }
    if not mapping:
        return stats

    for key, weight in list(mapping.items()):
        _pinyin, text = key
        text_len = _cjk_len(text)
        if text_len < 2 or text_len > 4:
            continue
        if text in curated_daily_terms:
            continue
        if text in LOW_PRIORITY_MEDICAL_PROCEDURE_TERMS:
            if weight > 80:
                mapping[key] = 80
                stats[f"{stats_prefix}_medical_specific_capped"] += 1
                stats[f"{stats_prefix}_low_priority_medical_procedure_capped"] += 1
            continue
        if not _is_medical_specific_term(text):
            continue

        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        if usage_score >= 0.52 or pageview_score >= 0.16:
            continue

        if text_len <= 2:
            cap = 440
        elif text_len == 3:
            cap = 510
        else:
            cap = 580

        if source_hits >= 3 or jieba_direct_score >= 0.50:
            cap += 30
        if weight > cap:
            mapping[key] = cap
            stats[f"{stats_prefix}_medical_specific_capped"] += 1

    return stats


def _cap_low_signal_short_term_weights(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    term_semantic_bonus_map: Dict[Tuple[str, str], int] | None,
    protected_terms: Set[str],
    stats_prefix: str,
) -> Dict[str, int]:
    """Keep low-evidence short dictionary/wiki terms discoverable but non-dominant."""
    stats = {
        f"{stats_prefix}_low_signal_short_capped": 0,
    }
    if not mapping:
        return stats
    term_semantic_bonus_map = term_semantic_bonus_map or {}

    for key, weight in list(mapping.items()):
        pinyin, text = key
        text_len = _cjk_len(text)
        if text_len < 2 or text_len > 3:
            continue
        if text in protected_terms or _is_pure_daily_number_word(text):
            continue

        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pos_tag = jieba_pos_map.get(text, "")

        if source_hits > 2:
            continue
        if usage_score >= 0.16 or jieba_direct_score >= 0.08 or pageview_score >= 0.03:
            continue
        if _is_conversational_pos(pos_tag):
            continue
        if term_semantic_bonus_map.get((pinyin, text), 0) >= 120:
            continue

        cap = 560 if text_len <= 2 else 620
        if weight > cap:
            mapping[key] = cap
            stats[f"{stats_prefix}_low_signal_short_capped"] += 1

    return stats


def _build_longer_prefix_term_support_index(
    mapping: Dict[Tuple[str, str], int],
    *,
    min_prefix_len: int = 2,
    max_prefix_len: int = 3,
    min_support_weight: int = 520,
) -> Dict[str, List[Tuple[str, str, int]]]:
    support_index: Dict[str, List[Tuple[str, str, int]]] = {}
    if not mapping:
        return support_index

    for (pinyin, text), weight in mapping.items():
        text_len = _cjk_len(text)
        if (
            weight < min_support_weight
            or text_len <= min_prefix_len
            or not CJK_FULL_RE.fullmatch(text)
        ):
            continue

        max_len = min(max_prefix_len, text_len - 1)
        for prefix_len in range(min_prefix_len, max_len + 1):
            prefix_text = text[:prefix_len]
            support_index.setdefault(prefix_text, []).append((pinyin, text, weight))

    return support_index


def _has_longer_prefix_term_support(
    pinyin: str,
    text: str,
    support_index: Dict[str, List[Tuple[str, str, int]]],
) -> bool:
    for support_pinyin, support_text, support_weight in support_index.get(text, []):
        if support_text == text:
            continue
        if (
            support_pinyin.startswith(pinyin)
            and len(support_pinyin) > len(pinyin)
            and support_weight >= 520
        ):
            return True
    return False


def _longer_prefix_term_support_stats(
    pinyin: str,
    text: str,
    support_index: Dict[str, List[Tuple[str, str, int]]],
    *,
    min_support_weight: int = 520,
) -> Tuple[int, int]:
    support_count = 0
    support_total = 0
    for support_pinyin, support_text, support_weight in support_index.get(text, []):
        if support_text == text:
            continue
        if (
            support_pinyin.startswith(pinyin)
            and len(support_pinyin) > len(pinyin)
            and support_weight >= min_support_weight
        ):
            support_count += 1
            support_total += support_weight
    return support_count, support_total


def _cap_low_independent_prefix_fragment_weights(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    wiki_titles: Set[str],
    wiki_augmented_terms: Set[str] | None,
    protected_terms: Set[str],
    stats_prefix: str,
) -> Dict[str, int]:
    """Cap weak short terms that mostly exist as prefixes of longer terms.

    Formal long terms should remain strong exact entries (for example 核试验),
    while their low-independent-signal prefixes (for example 核试) stay visible
    but should not dominate common exact alternatives.
    """
    stats = {
        f"{stats_prefix}_low_independent_prefix_fragments_capped": 0,
    }
    if not mapping:
        return stats

    support_index = _build_longer_prefix_term_support_index(mapping)
    if not support_index:
        return stats

    for key, weight in list(mapping.items()):
        pinyin, text = key
        text_len = _cjk_len(text)
        if text_len < 2 or text_len > 3:
            continue
        if text in protected_terms or _is_pure_daily_number_word(text):
            continue
        if not _has_longer_prefix_term_support(pinyin, text, support_index):
            continue

        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pos_tag = jieba_pos_map.get(text, "")
        weak_nominal_verb_fragment = (
            pos_tag.startswith("vn")
            and jieba_direct_score < 0.14
            and pageview_score < 0.06
            and source_hits <= 4
        )
        weak_function_prefix_fragment = (
            pos_tag.startswith(("d", "p", "c"))
            and jieba_direct_score < 0.04
            and pageview_score < 0.04
            and source_hits <= 2
        )
        has_strong_wiki_signal = (
            (
                text in (wiki_augmented_terms or set())
                and (pageview_score >= 0.08 or source_hits >= 5)
            )
            or (text in wiki_titles and pageview_score >= 0.08)
        )
        if (
            (usage_score >= 0.32 and not weak_nominal_verb_fragment)
            or jieba_direct_score >= 0.18
            or pageview_score >= 0.08
            or source_hits >= 5
            or has_strong_wiki_signal
        ):
            continue

        very_low_signal_fragment = (
            usage_score < 0.14
            and jieba_direct_score < 0.06
            and pageview_score < 0.025
            and source_hits <= 2
            and not _is_conversational_pos(pos_tag)
        )
        if not (
            weak_nominal_verb_fragment
            or weak_function_prefix_fragment
            or very_low_signal_fragment
        ):
            continue

        cap = 480 if text_len <= 2 else 540
        if source_hits >= 3:
            cap += 20
        if weight > cap:
            mapping[key] = cap
            stats[f"{stats_prefix}_low_independent_prefix_fragments_capped"] += 1

    return stats


def _cap_low_signal_reduplicated_term_weights(
    mapping: Dict[Tuple[str, str], int],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    protected_terms: Set[str],
    stats_prefix: str,
) -> Dict[str, int]:
    """Prevent low-evidence AA reduplications from dominating exact buckets."""
    stats = {
        f"{stats_prefix}_low_signal_redup_capped": 0,
    }
    if not mapping:
        return stats

    for key, weight in list(mapping.items()):
        _pinyin, text = key
        if _cjk_len(text) != 2 or len(text) != 2 or text[0] != text[1]:
            continue
        if text in protected_terms or _is_pure_daily_number_word(text):
            continue

        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        if pageview_score >= 0.08 or jieba_direct_score >= 0.18:
            continue
        if source_hits >= 4 and jieba_direct_score >= 0.08:
            continue

        cap = 560
        if weight > cap:
            mapping[key] = cap
            stats[f"{stats_prefix}_low_signal_redup_capped"] += 1

    return stats


def _compute_generic_vertical_penalty(
    text: str,
    layer_id: str,
    source_id: str,
) -> int:
    text_len = _cjk_len(text)
    if layer_id == "computing":
        if text_len <= 2:
            base_penalty = 210
        elif text_len == 3:
            base_penalty = 132
        elif text_len == 4:
            base_penalty = 72
        elif text_len == 5:
            base_penalty = 34
        else:
            base_penalty = 14
        if source_id == "project-curated-vertical-computing":
            relief = 28 if text_len <= 4 else 8
        else:
            relief = 0
    elif layer_id == "game_dev":
        if text_len <= 2:
            base_penalty = 228
        elif text_len == 3:
            base_penalty = 148
        elif text_len == 4:
            base_penalty = 86
        elif text_len == 5:
            base_penalty = 44
        else:
            base_penalty = 18
        if source_id == "project-curated-vertical-game-dev":
            relief = 24 if text_len <= 4 else 8
        elif source_id == "godot-zh-searchindex-titles":
            relief = 16 if text_len <= 4 else 6
        else:
            relief = 8 if text_len <= 4 else 4
    elif layer_id == "gaming":
        if text_len <= 2:
            base_penalty = 118
        elif text_len == 3:
            base_penalty = 70
        elif text_len == 4:
            base_penalty = 38
        elif text_len == 5:
            base_penalty = 18
        else:
            base_penalty = 8
        if source_id == "project-curated-vertical-gaming":
            relief = 22 if text_len <= 4 else 6
        elif source_id.startswith("wikidata-video-game"):
            relief = 16 if text_len <= 4 else 5
        else:
            relief = 10 if text_len <= 4 else 4
    elif layer_id == "architecture_terms":
        if text_len <= 2:
            base_penalty = 154
        elif text_len == 3:
            base_penalty = 96
        elif text_len == 4:
            base_penalty = 52
        elif text_len == 5:
            base_penalty = 24
        else:
            base_penalty = 10
        if source_id == "project-curated-vertical-architecture-terms":
            relief = 18 if text_len <= 4 else 6
        elif source_id.startswith("getty-aat-"):
            relief = 12 if text_len <= 4 else 4
        else:
            relief = 8 if text_len <= 4 else 3
    elif layer_id == "architecture_entities":
        if text_len <= 2:
            base_penalty = 132
        elif text_len == 3:
            base_penalty = 82
        elif text_len == 4:
            base_penalty = 46
        elif text_len == 5:
            base_penalty = 22
        else:
            base_penalty = 10
        if source_id == "project-curated-vertical-architecture-entities":
            relief = 18 if text_len <= 4 else 6
        else:
            relief = 6 if text_len <= 4 else 3
    elif layer_id == "place_names":
        if text_len <= 2:
            base_penalty = 230
        elif text_len == 3:
            base_penalty = 150
        elif text_len == 4:
            base_penalty = 90
        elif text_len == 5:
            base_penalty = 48
        else:
            base_penalty = 22
        if source_id == "project-curated-vertical-place-names":
            relief = 22 if text_len <= 2 else 12 if text_len <= 4 else 6
        else:
            relief = 0
    elif layer_id == "idioms_allusions":
        if text_len <= 3:
            base_penalty = 220
        elif text_len == 4:
            base_penalty = 92
        elif text_len <= 6:
            base_penalty = 58
        else:
            base_penalty = 34
        if source_id == "project-curated-vertical-idioms-allusions":
            relief = 24 if text_len <= 4 else 10
        elif source_id == "thuocl-chengyu-vertical":
            relief = 12 if text_len <= 4 else 6
        else:
            relief = 0
    elif layer_id in NAMED_ENTITY_VERTICAL_LAYERS:
        if text_len <= 2:
            base_penalty = 260
        elif text_len == 3:
            base_penalty = 170
        elif text_len == 4:
            base_penalty = 108
        elif text_len == 5:
            base_penalty = 60
        else:
            base_penalty = 28
        relief = 0
    elif layer_id == "proper_nouns":
        if text_len <= 2:
            base_penalty = 170
        elif text_len == 3:
            base_penalty = 118
        elif text_len == 4:
            base_penalty = 76
        elif text_len == 5:
            base_penalty = 46
        else:
            base_penalty = 24
        relief = 0
    else:
        if text_len <= 2:
            base_penalty = 96
        elif text_len == 3:
            base_penalty = 54
        elif text_len == 4:
            base_penalty = 28
        elif text_len == 5:
            base_penalty = 14
        else:
            base_penalty = 6
        relief = 12 if text_len <= 4 else 4

    return max(0, base_penalty - relief)


def _is_named_entity_vertical_layer(layer_id: str) -> bool:
    return layer_id in NAMED_ENTITY_VERTICAL_LAYERS


def _cap_named_entity_vertical_usage_score(usage_score: float, text_len: int) -> float:
    """Keep supplementary names visible without making them daily-word priors."""
    bounded = min(1.0, max(0.0, usage_score))
    if text_len <= 2:
        return min(bounded, 0.34)
    if text_len == 3:
        return min(bounded, 0.42)
    if text_len == 4:
        return min(bounded, 0.50)
    if text_len == 5:
        return min(bounded, 0.56)
    return min(bounded, 0.62)


def _cap_proper_noun_vertical_usage_score(usage_score: float, text_len: int) -> float:
    """Keep brands/proper nouns exact-searchable without turning them into daily priors."""
    bounded = min(1.0, max(0.0, usage_score))
    if bounded >= 0.90:
        if text_len <= 2:
            return bounded
        if text_len <= 4:
            return min(bounded, 0.86)
        return min(bounded, 0.68)
    if bounded >= 0.82:
        if text_len <= 2:
            return min(bounded, 0.58)
        if text_len <= 4:
            return min(bounded, 0.52)
        return min(bounded, 0.48)
    if text_len <= 2:
        return min(bounded, 0.30)
    if text_len == 3:
        return min(bounded, 0.38)
    if text_len == 4:
        return min(bounded, 0.46)
    if text_len == 5:
        return min(bounded, 0.52)
    return min(bounded, 0.58)


def _cap_place_vertical_usage_score(
    usage_score: float,
    text_len: int,
    source_id: str = "",
) -> float:
    """Keep place names discoverable without letting obscure places outrank daily words."""
    bounded = min(1.0, max(0.0, usage_score))
    source = source_id.strip().lower()

    if source == "project-curated-vertical-place-names":
        if text_len <= 2:
            return min(bounded, 0.62)
        if text_len <= 4:
            return min(bounded, 0.56)
        return min(bounded, 0.48)

    if source in {
        "project-curated-vertical-country-region-names",
        "project-curated-vertical-major-city-names",
    }:
        if text_len <= 2:
            return min(bounded, 0.52)
        if text_len <= 4:
            return min(bounded, 0.46)
        return min(bounded, 0.40)

    if source.startswith("wikidata-"):
        if text_len <= 2:
            return min(bounded, 0.22)
        if text_len == 3:
            return min(bounded, 0.26)
        if text_len == 4:
            return min(bounded, 0.30)
        return min(bounded, 0.28)

    if text_len <= 2:
        return min(bounded, 0.30)
    if text_len == 3:
        return min(bounded, 0.34)
    if text_len == 4:
        return min(bounded, 0.36)
    return min(bounded, 0.34)


def _cap_medicine_vertical_usage_score(
    usage_score: float,
    text_len: int,
    source_id: str = "",
) -> float:
    """Medical terms are exact-searchable vertical terms, not daily priors."""
    bounded = min(1.0, max(0.0, usage_score))
    source = source_id.strip().lower()

    if source == "project-curated-vertical-medicine":
        if text_len <= 2:
            return min(bounded, 0.48)
        if text_len == 3:
            return min(bounded, 0.54)
        if text_len == 4:
            return min(bounded, 0.58)
        return min(bounded, 0.62)

    if source == "wikidata-medical-mesh-zh":
        if text_len <= 2:
            return min(bounded, 0.34)
        if text_len == 3:
            return min(bounded, 0.40)
        if text_len == 4:
            return min(bounded, 0.46)
        return min(bounded, 0.52)

    if text_len <= 2:
        return min(bounded, 0.28)
    if text_len == 3:
        return min(bounded, 0.34)
    if text_len == 4:
        return min(bounded, 0.40)
    return min(bounded, 0.46)


def _vertical_ranking_usage_score(
    text: str,
    layer_id: str,
    usage_score: float,
    *,
    source_id: str = "",
    supported_named_entity: bool = False,
) -> float:
    source = source_id.strip().lower()
    bounded = min(1.0, max(0.0, usage_score))
    text_len = _cjk_len(text)
    if layer_id == "gaming" and source.startswith(LOW_PRIORITY_VERTICAL_ENTITY_SOURCE_PREFIXES):
        if text_len <= 2:
            return min(bounded, 0.16)
        if text_len == 3:
            return min(bounded, 0.22)
        if text_len == 4:
            return min(bounded, 0.28)
        return min(bounded, 0.34)
    if layer_id == "proper_nouns":
        return _cap_proper_noun_vertical_usage_score(usage_score, text_len)
    if _is_named_entity_vertical_layer(layer_id) and not supported_named_entity:
        return _cap_named_entity_vertical_usage_score(usage_score, text_len)
    if layer_id == "medicine":
        return _cap_medicine_vertical_usage_score(usage_score, text_len, source_id)
    if layer_id == "place_names":
        return _cap_place_vertical_usage_score(usage_score, text_len, source_id)
    if layer_id == "idioms_allusions":
        if text_len <= 3:
            return min(bounded, 0.50)
        if text_len == 4:
            return min(bounded, 0.72)
        if text_len <= 6:
            return min(bounded, 0.64)
        return min(bounded, 0.58)
    return bounded


def _build_existing_prefix_support_map(
    mapping: Dict[Tuple[str, str], int],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    *,
    min_weight: int = 520,
    max_prefix_len: int = 4,
) -> Dict[Tuple[str, str], int]:
    support: Dict[Tuple[str, str], int] = {}
    if not mapping:
        return support

    for (pinyin, text), weight in mapping.items():
        text_len = _cjk_len(text)
        if weight < min_weight or text_len < 3 or not CJK_FULL_RE.fullmatch(text):
            continue
        syllables = _split_compact_pinyin_by_unihan(
            text,
            pinyin,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not syllables or len(syllables) < text_len:
            continue
        for prefix_len in range(2, min(max_prefix_len, text_len - 1) + 1):
            prefix_text = text[:prefix_len]
            prefix_pinyin = _normalize_compact_pinyin_key("".join(syllables[:prefix_len]))
            if not prefix_pinyin:
                continue
            key = (prefix_pinyin, prefix_text)
            support[key] = max(support.get(key, 0), weight)

    return support


def _compute_civic_neutral_usage_score(usage_score: float, text_len: int) -> float:
    if text_len <= 2:
        return min(usage_score, 0.12)
    if text_len == 3:
        return min(usage_score, 0.18)
    if text_len == 4:
        return min(usage_score, 0.26)
    if text_len == 5:
        return min(usage_score, 0.34)
    return min(usage_score, 0.42)


def _apply_neutral_civic_weights(
    mapping: Dict[Tuple[str, str], int],
    civic_terms: Set[str],
    usage_score_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    stats_prefix: str,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    stats = {
        f"{stats_prefix}_rows_considered": 0,
        f"{stats_prefix}_rows_reduced": 0,
        f"{stats_prefix}_weight_delta_total": 0,
    }
    if not mapping or not civic_terms:
        return mapping, stats

    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    adjusted: Dict[Tuple[str, str], int] = {}
    for key, weight in mapping.items():
        _pinyin, text = key
        if text not in civic_terms or _cjk_len(text) < 2:
            adjusted[key] = weight
            continue

        stats[f"{stats_prefix}_rows_considered"] += 1
        text_len = _cjk_len(text)
        neutral_usage_score = _compute_civic_neutral_usage_score(
            usage_score_map.get(text, 0.0),
            text_len,
        )
        neutral_weight = _compute_weight_with_signals(
            text,
            usage_score=neutral_usage_score,
            source_hits=0,
            pageview_score=0.0,
            wiki_hit=False,
            core_entry=False,
            jieba_direct_score=jieba_direct_signal_map.get(text, 0.0),
            pos_tag=jieba_pos_map.get(text, ""),
            char_score=_compute_text_single_char_prior(text, char_prior),
        )
        neutral_penalty = _compute_civic_neutral_usage_score(0.0, text_len)
        if text_len <= 2:
            neutral_penalty = 74
        elif text_len == 3:
            neutral_penalty = 32
        elif text_len == 4:
            neutral_penalty = 6
        elif text_len == 5:
            neutral_penalty = 0
        else:
            neutral_penalty = 0
        if neutral_penalty > 0:
            neutral_weight = max(1, neutral_weight - neutral_penalty)
        new_weight = min(weight, neutral_weight)
        adjusted[key] = new_weight
        if new_weight < weight:
            stats[f"{stats_prefix}_rows_reduced"] += 1
            stats[f"{stats_prefix}_weight_delta_total"] += weight - new_weight

    return adjusted, stats


def _apply_explicit_term_pinyin_overrides(
    mapping: Dict[Tuple[str, str], int],
    overrides: Dict[str, str],
    stat_prefix: str,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    stats = {
        f"{stat_prefix}_terms_total": len(mapping),
        f"{stat_prefix}_terms_rekeyed": 0,
        f"{stat_prefix}_terms_merged": 0,
    }
    if (not mapping) or (not overrides):
        return mapping, stats

    remapped: Dict[Tuple[str, str], int] = {}
    for (pinyin, text), weight in mapping.items():
        target_pinyin = overrides.get(text, pinyin)
        if target_pinyin != pinyin:
            stats[f"{stat_prefix}_terms_rekeyed"] += 1
        key = (target_pinyin, text)
        existing = remapped.get(key)
        if existing is not None:
            stats[f"{stat_prefix}_terms_merged"] += 1
            if weight > existing:
                remapped[key] = weight
        else:
            remapped[key] = weight
    return remapped, stats


def _apply_word_pinyin_overrides(
    mapping: Dict[Tuple[str, str], int],
    overrides: Dict[str, str],
    stat_prefix: str,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    if (not mapping) or (not overrides):
        return _apply_explicit_term_pinyin_overrides(mapping, overrides, stat_prefix)

    single_char_overrides = {
        text: pinyin
        for text, pinyin in overrides.items()
        if _cjk_len(text) == 1
    }
    multi_char_overrides = {
        text: pinyin
        for text, pinyin in overrides.items()
        if _cjk_len(text) != 1
    }

    remapped, stats = _apply_explicit_term_pinyin_overrides(
        mapping,
        multi_char_overrides,
        stat_prefix,
    )
    stats[f"{stat_prefix}_single_char_readings_added"] = 0
    if not single_char_overrides:
        return remapped, stats

    best_text_weight: Dict[str, int] = {}
    for (_pinyin, text), weight in remapped.items():
        if text not in single_char_overrides:
            continue
        best_text_weight[text] = max(best_text_weight.get(text, 0), weight)

    for text, pinyin in single_char_overrides.items():
        weight = best_text_weight.get(text, 0)
        if weight <= 0:
            continue
        key = (pinyin, text)
        if key in remapped:
            continue
        # An explicitly restored secondary reading must stay selectable without
        # inheriting the dominant reading's standalone rank.
        remapped[key] = min(weight, SINGLE_CHAR_ADDED_READING_WEIGHT_CAP)
        stats[f"{stat_prefix}_single_char_readings_added"] += 1

    return remapped, stats


def _expand_leading_text_pinyin_aliases(
    mapping: Dict[Tuple[str, str], int],
    stats_prefix: str,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    expanded = dict(mapping)
    stats = {
        f"{stats_prefix}_pinyin_alias_rows_considered": 0,
        f"{stats_prefix}_pinyin_alias_rows_added": 0,
        f"{stats_prefix}_pinyin_alias_rows_equalized": 0,
    }

    for (pinyin, text), weight in mapping.items():
        for text_prefix, source_prefix, target_prefix in LEADING_TEXT_PINYIN_ALIAS_RULES:
            if not text.startswith(text_prefix) or not pinyin.startswith(source_prefix):
                continue

            stats[f"{stats_prefix}_pinyin_alias_rows_considered"] += 1
            alias_pinyin = target_prefix + pinyin[len(source_prefix):]
            alias_key = (alias_pinyin, text)
            alias_weight = expanded.get(alias_key)
            if alias_weight is None:
                expanded[alias_key] = weight
                stats[f"{stats_prefix}_pinyin_alias_rows_added"] += 1
                continue

            shared_weight = max(weight, alias_weight)
            source_key = (pinyin, text)
            if expanded[source_key] != shared_weight or expanded[alias_key] != shared_weight:
                expanded[source_key] = shared_weight
                expanded[alias_key] = shared_weight
                stats[f"{stats_prefix}_pinyin_alias_rows_equalized"] += 1

    return expanded, stats


def _collect_preferred_unihan_readings(
    ch: str,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_mandarin_map: Dict[str, str] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
) -> List[str]:
    if (
        not unihan_readings_map
        or not unihan_source_rank_map
        or not unihan_mandarin_map
        or not unihan_pinlu_detail_map
    ):
        return []

    pinyin_set = unihan_readings_map.get(ch, set())
    if not pinyin_set:
        mandarin = unihan_mandarin_map.get(ch, "")
        return [mandarin] if mandarin else []

    mandarin = unihan_mandarin_map.get(ch, "")
    preferred: Set[str] = set()
    for pinyin in pinyin_set:
        if (
            pinyin == mandarin
            or unihan_pinlu_detail_map.get((ch, pinyin), 0) > 0
            or unihan_source_rank_map.get((ch, pinyin), 0) >= UNIHAN_SOURCE_MANDARIN
        ):
            preferred.add(pinyin)

    if mandarin:
        preferred.add(mandarin)

    if not preferred:
        preferred.update(
            _select_unihan_output_readings(
                ch,
                pinyin_set,
                unihan_source_rank_map,
                unihan_mandarin_map,
                unihan_pinlu_detail_map,
            )
        )

    return sorted(
        preferred,
        key=lambda pinyin: (
            1 if pinyin == mandarin else 0,
            unihan_pinlu_detail_map.get((ch, pinyin), 0),
            unihan_source_rank_map.get((ch, pinyin), 0),
            len(pinyin),
            pinyin,
        ),
        reverse=True,
    )


def _has_constituent_pinyin_alignment_mismatch(
    text: str,
    pinyin: str,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_mandarin_map: Dict[str, str] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
) -> bool:
    if not PINYIN_RE.fullmatch(pinyin):
        return False

    units = _split_text_units(text)
    if len(units) < 2 or len(units) > 4:
        return False
    if len(pinyin) < len(units):
        return False

    unit_readings: List[List[str]] = []
    for ch in units:
        readings = _collect_preferred_unihan_readings(
            ch,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_mandarin_map,
            unihan_pinlu_detail_map,
        )
        if not readings:
            return False
        unit_readings.append(readings)

    memo: Dict[Tuple[int, int], bool] = {}

    def can_align(unit_idx: int, offset: int) -> bool:
        key = (unit_idx, offset)
        if key in memo:
            return memo[key]
        if unit_idx >= len(unit_readings):
            result = offset == len(pinyin)
            memo[key] = result
            return result

        if offset >= len(pinyin):
            memo[key] = False
            return False

        result = False
        for reading in unit_readings[unit_idx]:
            if pinyin.startswith(reading, offset) and can_align(
                unit_idx + 1, offset + len(reading)
            ):
                result = True
                break

        memo[key] = result
        return result

    return not can_align(0, 0)


def _collect_unihan_phrase_pinyin_variants(
    text: str,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_mandarin_map: Dict[str, str] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    max_variants: int = 24,
) -> List[str]:
    units = _split_text_units(text)
    if not units or len(units) > 5:
        return []

    variants: List[str] = [""]
    for ch in units:
        readings = _collect_preferred_unihan_readings(
            ch,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_mandarin_map,
            unihan_pinlu_detail_map,
        )
        if not readings:
            return []
        readings = readings[:4]

        next_variants: List[str] = []
        for prefix in variants:
            for reading in readings:
                merged = prefix + reading
                if PINYIN_RE.fullmatch(merged):
                    next_variants.append(merged)
                if len(next_variants) >= max_variants:
                    break
            if len(next_variants) >= max_variants:
                break

        if not next_variants:
            return []
        variants = next_variants

    return variants


def _derive_prefix_pinyin_candidates_from_longer_terms(
    text: str,
    pinyin_index: Dict[str, Set[str]],
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_mandarin_map: Dict[str, str] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
) -> Set[str]:
    variants = _collect_unihan_phrase_pinyin_variants(
        text,
        unihan_readings_map,
        unihan_source_rank_map,
        unihan_mandarin_map,
        unihan_pinlu_detail_map,
    )
    if not variants:
        return set()

    candidates: Set[str] = set()
    text_len = _cjk_len(text)
    for longer_text, longer_pinyins in pinyin_index.items():
        if not longer_text.startswith(text) or _cjk_len(longer_text) <= text_len:
            continue
        for variant in variants:
            for longer_pinyin in longer_pinyins:
                if longer_pinyin.startswith(variant):
                    candidates.add(variant)
                    break
    return candidates


def _compute_weight(text: str) -> int:
    # Stable seed mapping: longer CJK terms get slightly larger base weight.
    length = _cjk_len(text)
    if length <= 0:
        return 0
    return min(1000, 180 + min(length, 8) * 40)


def _compute_weight_with_signals(
    text: str,
    usage_score: float = 0.0,
    source_hits: int = 0,
    pageview_score: float = 0.0,
    wiki_hit: bool = False,
    core_entry: bool = False,
    jieba_direct_score: float = 0.0,
    pos_tag: str = "",
    char_score: float = 0.0,
) -> int:
    """
    Weight model for broad profile.

    Signals:
    - cjk length (base readability/usefulness prior)
    - aggregated cross-source usage score (strong ranking signal)
    - cross-source agreement count
    - pageview popularity score
    - wiki title hit (named/common term prior)
    - core entry bonus (keep core dictionary terms generally ahead)
    - POS / term-class shaping (daily words vs. named entities / rare tails)
    - single-character commonness prior
    """
    def _compute_term_class_bias() -> float:
        bias = 0.0
        looks_like_person_name = _looks_like_low_signal_person_name(
            text,
            usage_score=bounded_usage,
            source_hits=source_hits,
            pageview_score=bounded_pageviews,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_hit,
            pos_tag=pos_tag,
        )
        looks_like_place_name = _looks_like_low_signal_place_name(
            text,
            usage_score=bounded_usage,
            source_hits=source_hits,
            pageview_score=bounded_pageviews,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_hit,
            pos_tag=pos_tag,
        )
        looks_like_literary_term = _looks_like_low_signal_literary_term(
            text,
            usage_score=bounded_usage,
            source_hits=source_hits,
            pageview_score=bounded_pageviews,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_hit,
            pos_tag=pos_tag,
            char_score=char_score,
        )

        if length == 1:
            if char_score >= 0.94:
                bias += 0.44
            elif char_score >= 0.84:
                bias += 0.30
            elif char_score >= 0.74:
                bias += 0.16
            elif (
                char_score <= 0.06
                and bounded_usage < 0.04
                and jieba_direct_score < 0.03
                and source_hits <= 1
                and bounded_pageviews < 0.02
            ):
                bias -= 0.48
            elif (
                char_score <= 0.12
                and bounded_usage < 0.06
                and jieba_direct_score < 0.05
                and source_hits <= 1
                and bounded_pageviews < 0.03
            ):
                bias -= 0.28

        if _is_named_entity_pos(pos_tag):
            if source_hits <= 1 and bounded_pageviews < 0.08 and jieba_direct_score < 0.10:
                bias -= 0.34 if length <= 3 else 0.22
            elif source_hits <= 2 and bounded_pageviews < 0.18 and jieba_direct_score < 0.16:
                bias -= 0.16
            elif (
                length <= 3
                and source_hits <= 1
                and bounded_pageviews < 0.04
                and bounded_usage < 0.20
                and jieba_direct_score < 0.10
            ):
                bias -= 0.10
            if looks_like_place_name:
                bias -= 0.18 if length <= 3 else 0.12
        elif looks_like_person_name:
            if length <= 3:
                bias -= 0.34
            else:
                bias -= 0.22
        elif looks_like_place_name:
            if length <= 3:
                bias -= 0.30
            else:
                bias -= 0.18
        elif looks_like_literary_term:
            if length <= 2:
                bias -= 0.28
            else:
                bias -= 0.18
        elif _is_conversational_pos(pos_tag):
            if (
                length <= 2
                and pos_tag.startswith(("d", "r", "p", "u", "c"))
                and (
                    bounded_usage >= 0.05
                    or jieba_direct_score >= 0.06
                    or source_hits >= 2
                )
            ):
                bias += 0.32
            elif length <= 4 and (bounded_usage >= 0.05 or jieba_direct_score >= 0.08):
                bias += 0.22
            elif length <= 4:
                bias += 0.10
        elif _is_noun_pos(pos_tag):
            if length <= 2 and (
                bounded_usage >= 0.14
                or jieba_direct_score >= 0.14
                or source_hits >= 2
                or char_score >= 0.70
            ):
                bias += 0.14
            elif length <= 2 and (
                bounded_usage >= 0.08
                or jieba_direct_score >= 0.08
                or char_score >= 0.58
            ):
                bias += 0.08
            elif length <= 3 and (bounded_usage >= 0.12 or jieba_direct_score >= 0.12 or source_hits >= 2):
                bias += 0.10
            elif length <= 4 and bounded_usage >= 0.06 and jieba_direct_score >= 0.06:
                bias += 0.06

        if length <= 3 and not _is_named_entity_pos(pos_tag):
            if bounded_usage >= 0.22 or jieba_direct_score >= 0.20:
                bias += 0.10
            elif length <= 2 and char_score >= 0.62 and (
                bounded_usage >= 0.08 or jieba_direct_score >= 0.08 or source_hits >= 2
            ):
                bias += 0.06

        if (
            length <= 4
            and bounded_usage < 0.03
            and jieba_direct_score < 0.03
            and source_hits <= 0
            and bounded_pageviews <= 0.0
            and char_score < 0.10
            and not wiki_hit
        ):
            bias -= 0.22

        if (
            length <= 2
            and bounded_usage < 0.06
            and jieba_direct_score < 0.06
            and source_hits <= 1
            and bounded_pageviews < 0.02
            and char_score < 0.18
            and not wiki_hit
        ):
            bias -= 0.12

        if length <= 2 and char_score >= 0.74 and not _is_named_entity_pos(pos_tag):
            bias += 0.10

        return max(-0.65, min(0.52, bias))

    length = max(1, _cjk_len(text))
    base = 120 + min(length, 8) * 30
    bounded_usage = min(1.0, max(0.0, usage_score))
    bounded_pageviews = min(1.0, max(0.0, pageview_score))
    usage_bonus = int(round(520.0 * math.sqrt(bounded_usage)))
    consensus_bonus = 0
    if source_hits >= 2:
        consensus_bonus = 24 + 14 * min(source_hits - 2, 4)
    pageview_bonus = int(round(92.0 * math.sqrt(bounded_pageviews))) if bounded_pageviews > 0 else 0
    wiki_bonus = 20 if wiki_hit else 0
    core_bonus = 18 if core_entry else 0
    phrase_bonus = int(
        round(
            _compute_common_phrase_confidence(
                text,
                usage_score=bounded_usage,
                source_hits=source_hits,
                pageview_score=bounded_pageviews,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_hit,
                pos_tag=pos_tag,
                char_score=char_score,
            )
            * 220.0
        )
    )
    class_bonus = int(round(_compute_term_class_bias() * 180.0))
    # Keep a global cap for compatibility with downstream consumers.
    # The current formula generally peaks below 1000 for realistic inputs.
    return min(
        1000,
        max(
            1,
            base
            + usage_bonus
            + consensus_bonus
            + pageview_bonus
            + wiki_bonus
            + core_bonus
            + phrase_bonus
            + class_bonus,
        ),
    )


def _build_single_char_weight_prior(mapping: Dict[Tuple[str, str], int]) -> Dict[str, float]:
    """
    Build a normalized single-character prior from current weights.
    This gives common characters a stronger prior than rare ones.
    """
    raw: Dict[str, int] = {}
    for (_pinyin, text), weight in mapping.items():
        if _cjk_len(text) != 1:
            continue
        if not CJK_FULL_RE.fullmatch(text):
            continue
        previous = raw.get(text, 0)
        if weight > previous:
            raw[text] = weight

    if not raw:
        return {}

    min_weight = min(raw.values())
    max_weight = max(raw.values())
    if max_weight <= min_weight:
        return {ch: 0.5 for ch in raw.keys()}

    spread = float(max_weight - min_weight)
    return {ch: (weight - min_weight) / spread for ch, weight in raw.items()}


def _build_mapping_char_frequency_prior(
    mapping: Dict[Tuple[str, str], int],
) -> Dict[str, float]:
    """
    Build a coarse character prior from all current terms.

    This is weaker than external frequency sources, but it gives cedict-only
    builds a useful fallback: common characters that participate in many
    productive compounds should outrank rare characters that only appear in a
    handful of literary or archaic entries.
    """
    raw: Dict[str, float] = {}
    for (_pinyin, text), weight in mapping.items():
        text_len = _cjk_len(text)
        if text_len <= 0:
            continue
        term_weight = min(420.0, float(weight))
        if text_len == 1:
            term_factor = 1.30
        elif text_len == 2:
            term_factor = 1.00
        elif text_len <= 4:
            term_factor = 0.62
        else:
            term_factor = 0.34
        contribution = term_weight * term_factor
        for ch in text:
            if not CJK_FULL_RE.fullmatch(ch):
                continue
            raw[ch] = raw.get(ch, 0.0) + contribution

    if not raw:
        return {}

    max_log = 0.0
    for value in raw.values():
        if value <= 0.0:
            continue
        log_value = math.log1p(value)
        if log_value > max_log:
            max_log = log_value
    if max_log <= 0.0:
        return {}

    prior: Dict[str, float] = {}
    for ch, value in raw.items():
        ratio = min(1.0, max(0.0, math.log1p(value) / max_log))
        prior[ch] = ratio**1.35
    return prior


def _compute_text_single_char_prior(text: str, char_prior: Dict[str, float]) -> float:
    if not text:
        return 0.0

    total = 0.0
    count = 0
    for ch in text:
        if not CJK_FULL_RE.fullmatch(ch):
            continue
        total += char_prior.get(ch, 0.0)
        count += 1

    if count <= 0:
        return 0.0
    return total / float(count)


def _normalize_jieba_pos_tag(tag: str) -> str:
    value = tag.strip().lower()
    if not value:
        return ""
    value = re.sub(r"[^a-z]", "", value)
    return value


def _compute_jieba_pos_bias(pos_tag: str, text_len: int) -> float:
    """
    Estimate IME-priority bias from jieba POS tags.

    The goal is to slightly prefer daily input词类 (verb/adverb/adj/pronoun)
    and slightly damp proper-name heavy categories in short homophone buckets.
    """
    if not pos_tag:
        return 0.0

    length = max(1, text_len)
    if length <= 2:
        length_scale = 1.0
    elif length <= 4:
        length_scale = 0.55
    else:
        length_scale = 0.30

    # Named-entity categories are often over-represented in web/wiki sources.
    if pos_tag.startswith(("nr", "ns", "nt", "nz", "nw")):
        return -0.36 * length_scale

    # Conversationally frequent classes: verb/adverb/adj/pronoun/preposition.
    if pos_tag.startswith(("v", "d", "a", "r", "p", "u", "c")):
        return 0.24 * length_scale

    # Generic noun categories stay neutral.
    if pos_tag.startswith("n"):
        return 0.0

    # Light positive prior for uncategorized non-noun tags.
    return 0.08 * length_scale


def _is_conversational_pos(pos_tag: str) -> bool:
    return pos_tag.startswith(("v", "d", "a", "r", "p", "u", "c"))


def _is_noun_pos(pos_tag: str) -> bool:
    return pos_tag.startswith("n")


def _is_named_entity_pos(pos_tag: str) -> bool:
    return pos_tag.startswith(("nr", "ns", "nt", "nz", "nw"))


def _looks_like_low_signal_person_name(
    text: str,
    usage_score: float,
    source_hits: int,
    pageview_score: float,
    jieba_direct_score: float,
    wiki_support: bool,
    pos_tag: str = "",
) -> bool:
    text_len = _cjk_len(text)
    if text_len < 2 or text_len > 4:
        return False
    if not CJK_WINDOWS_FULL_RE.fullmatch(text):
        return False
    if wiki_support:
        return False
    if (
        usage_score >= 0.03
        or jieba_direct_score >= 0.03
        or source_hits >= 2
        or pageview_score >= 0.03
    ):
        return False
    if pos_tag and not _is_named_entity_pos(pos_tag):
        return False

    if text[:2] in COMMON_COMPOUND_SURNAMES:
        return text_len >= 3
    return text[0] in COMMON_SURNAMES


def _looks_like_low_signal_place_name(
    text: str,
    usage_score: float,
    source_hits: int,
    pageview_score: float,
    jieba_direct_score: float,
    wiki_support: bool,
    pos_tag: str = "",
) -> bool:
    text_len = _cjk_len(text)
    if text_len < 2 or text_len > 5:
        return False
    if not CJK_WINDOWS_FULL_RE.fullmatch(text):
        return False
    if wiki_support:
        return False
    if (
        usage_score >= 0.04
        or jieba_direct_score >= 0.04
        or source_hits >= 2
        or pageview_score >= 0.03
    ):
        return False

    if pos_tag.startswith("ns"):
        return True
    if pos_tag and not _is_named_entity_pos(pos_tag):
        return False

    return text.endswith(LOW_SIGNAL_PLACE_SUFFIXES)


def _looks_like_low_signal_literary_term(
    text: str,
    usage_score: float,
    source_hits: int,
    pageview_score: float,
    jieba_direct_score: float,
    wiki_support: bool,
    pos_tag: str = "",
    char_score: float = 0.0,
) -> bool:
    text_len = _cjk_len(text)
    if text_len < 2 or text_len > 4:
        return False
    if not CJK_WINDOWS_FULL_RE.fullmatch(text):
        return False
    if wiki_support:
        return False
    if _is_named_entity_pos(pos_tag):
        return False
    if (
        usage_score >= 0.06
        or jieba_direct_score >= 0.06
        or source_hits >= 2
        or pageview_score >= 0.03
    ):
        return False
    if char_score >= 0.72:
        return False

    if any(ch in LOW_SIGNAL_LITERARY_CHARS for ch in text):
        return True

    return text.endswith(LOW_SIGNAL_LITERARY_SUFFIXES) and any(
        ch in LOW_SIGNAL_LITERARY_CHARS for ch in text[:-1]
    )


def _looks_like_low_signal_written_tail_term(
    text: str,
    usage_score: float,
    source_hits: int,
    pageview_score: float,
    jieba_direct_score: float,
    wiki_support: bool,
    pos_tag: str = "",
    char_score: float = 0.0,
) -> bool:
    text_len = _cjk_len(text)
    if text_len < 2 or text_len > 4:
        return False
    if not CJK_WINDOWS_FULL_RE.fullmatch(text):
        return False
    if wiki_support:
        return False
    if _is_named_entity_pos(pos_tag):
        return False
    if (
        usage_score >= 0.08
        or jieba_direct_score >= 0.08
        or source_hits >= 2
        or pageview_score >= 0.04
    ):
        return False
    if char_score >= 0.68:
        return False
    if not text.endswith(LOW_SIGNAL_WRITTEN_TAIL_SUFFIXES):
        return False

    head = text[:-1]
    return any(
        (ch in LOW_SIGNAL_LITERARY_CHARS) or (ch in LOW_SIGNAL_WRITTEN_TAIL_HEADS)
        for ch in head
    )


def _looks_like_low_signal_fragment_term(
    text: str,
    usage_score: float,
    source_hits: int,
    pageview_score: float,
    jieba_direct_score: float,
    wiki_support: bool,
    pos_tag: str = "",
) -> bool:
    text_len = _cjk_len(text)
    if text_len != 2:
        return False
    if not CJK_WINDOWS_FULL_RE.fullmatch(text):
        return False
    if _is_named_entity_pos(pos_tag):
        return False
    if text[0] not in LOW_SIGNAL_FRAGMENT_HEAD_CHARS:
        return False
    if text[1] not in LOW_SIGNAL_FRAGMENT_TAIL_SUFFIXES:
        return False
    return True


def _compute_low_signal_inflated_short_term_penalty(
    text: str,
    usage_score: float,
    source_hits: int,
    pageview_score: float,
    jieba_direct_score: float,
    wiki_support: bool,
    pos_tag: str = "",
    char_score: float = 0.0,
    min_char_prior: float = 0.0,
) -> int:
    text_len = _cjk_len(text)
    if text_len != 2:
        return 0
    if not CJK_WINDOWS_FULL_RE.fullmatch(text):
        return 0
    if wiki_support:
        return 0
    if _is_named_entity_pos(pos_tag) or _is_conversational_pos(pos_tag):
        return 0
    if (
        usage_score >= 0.12
        or jieba_direct_score >= 0.10
        or source_hits >= 2
        or pageview_score >= 0.03
    ):
        return 0
    if min_char_prior >= 0.18:
        return 0
    if char_score < 0.34:
        return 0

    inflation_gap = char_score - min_char_prior
    if inflation_gap < 0.18:
        return 0

    rarity_component = min(1.0, max(0.0, (0.18 - min_char_prior) / 0.18))
    gap_component = min(1.0, max(0.0, (inflation_gap - 0.18) / 0.24))
    return 72 + int(round(rarity_component * 92.0 + gap_component * 68.0))


def _compute_low_signal_modernity_risk(
    text: str,
    usage_score: float,
    source_hits: int,
    pageview_score: float,
    jieba_direct_score: float,
    wiki_support: bool,
    pos_tag: str = "",
    char_score: float = 0.0,
    min_char_prior: float = 0.0,
    looks_like_person_name: bool = False,
    looks_like_place_name: bool = False,
    looks_like_literary_term: bool = False,
    looks_like_written_tail_term: bool = False,
) -> int:
    text_len = _cjk_len(text)
    if text_len <= 0 or text_len > 3:
        return 0
    if not CJK_WINDOWS_FULL_RE.fullmatch(text):
        return 0
    if wiki_support:
        return 0

    risk = 0
    if usage_score < 0.02:
        risk += 112
    elif usage_score < 0.05:
        risk += 68
    elif usage_score < 0.08:
        risk += 24

    if jieba_direct_score < 0.02:
        risk += 96
    elif jieba_direct_score < 0.05:
        risk += 52
    elif jieba_direct_score < 0.08:
        risk += 20

    if source_hits <= 0:
        risk += 38
    elif source_hits == 1:
        risk += 16

    if pageview_score < 0.01:
        risk += 22
    elif pageview_score < 0.03:
        risk += 10

    if text_len <= 2 and char_score < 0.20:
        risk += 34
    if min_char_prior < 0.08:
        risk += 34
    elif min_char_prior < 0.14:
        risk += 16

    if _is_named_entity_pos(pos_tag) and source_hits <= 1 and pageview_score < 0.03:
        risk += 34
    if (
        text_len <= 2
        and _is_named_entity_pos(pos_tag)
        and usage_score < 0.10
        and jieba_direct_score < 0.06
        and source_hits <= 1
        and pageview_score < 0.03
        and char_score < 0.38
    ):
        risk += 32
    if (
        text_len <= 2
        and source_hits <= 1
        and pageview_score < 0.015
        and usage_score < 0.025
        and jieba_direct_score < 0.025
        and char_score < 0.24
    ):
        risk += 26
    if looks_like_person_name or looks_like_place_name:
        risk += 78
        if text_len <= 2 and char_score < 0.32 and min_char_prior < 0.12:
            risk += 18
        if (
            text_len <= 2
            and usage_score < 0.035
            and jieba_direct_score < 0.03
            and pageview_score < 0.015
            and source_hits <= 1
        ):
            risk += 28
    if looks_like_literary_term:
        risk += 48
    if looks_like_written_tail_term:
        risk += 60
        if text_len == 3 and usage_score < 0.05 and jieba_direct_score < 0.05:
            risk += 34
        if (
            text_len == 3
            and usage_score < 0.08
            and jieba_direct_score < 0.06
            and source_hits <= 1
            and pageview_score < 0.03
            and char_score < 0.34
        ):
            risk += 22
    if (
        text_len == 2
        and (looks_like_written_tail_term or looks_like_literary_term)
        and usage_score < 0.04
        and jieba_direct_score < 0.04
        and pageview_score < 0.02
        and source_hits <= 1
        and char_score < 0.30
    ):
        risk += 24
    if (
        text_len == 3
        and source_hits <= 1
        and not wiki_support
        and pageview_score < 0.015
        and usage_score < 0.025
        and jieba_direct_score < 0.025
        and char_score < 0.30
        and (looks_like_written_tail_term or looks_like_literary_term)
    ):
        risk += 20
    if text_len <= 2 and source_hits <= 1 and not wiki_support:
        if usage_score < 0.04 and jieba_direct_score < 0.04:
            risk += 44
        elif usage_score < 0.08 and jieba_direct_score < 0.06:
            risk += 20

        if (_is_noun_pos(pos_tag) or _is_conversational_pos(pos_tag)) and char_score < 0.28:
            risk += 22
        elif char_score < 0.22:
            risk += 14
        if (
            usage_score < 0.03
            and jieba_direct_score < 0.03
            and pageview_score < 0.02
            and char_score < 0.26
        ):
            risk += 30
        if (
            (_is_noun_pos(pos_tag) or _is_conversational_pos(pos_tag))
            and char_score < 0.18
            and min_char_prior < 0.10
        ):
            risk += 18
        if (
            (_is_noun_pos(pos_tag) or _is_conversational_pos(pos_tag))
            and usage_score < 0.025
            and jieba_direct_score < 0.025
            and pageview_score < 0.015
            and char_score < 0.24
            and min_char_prior < 0.12
        ):
            risk += 16
    if (
        text_len == 3
        and usage_score < 0.03
        and jieba_direct_score < 0.03
        and source_hits <= 1
        and not wiki_support
    ):
        risk += 18

    return risk


def _compute_min_char_prior(text: str, char_prior: Dict[str, float]) -> float:
    min_char_prior = 1.0
    has_cjk_char = False
    for ch in text:
        if not CJK_FULL_RE.fullmatch(ch):
            continue
        has_cjk_char = True
        value = min(1.0, max(0.0, char_prior.get(ch, 0.0)))
        if value < min_char_prior:
            min_char_prior = value
    if not has_cjk_char:
        return 0.0
    return min_char_prior


def _has_effective_wiki_support(
    text: str,
    wiki_titles: Set[str],
    pageview_score: float,
    source_hits: int,
    wiki_augmented_terms: Set[str] | None = None,
) -> bool:
    wiki_augmented_terms = wiki_augmented_terms or set()
    if text in wiki_augmented_terms:
        return True
    if text not in wiki_titles:
        return False
    # Full zhwiki title dump includes a large long tail. Treat wiki as an
    # effective positive signal only when real popularity or multi-source
    # consensus exists.
    return pageview_score >= 0.08 or source_hits >= 2


def _normalize_ascii_wiki_title_candidate(raw_title: str) -> str:
    title = raw_title.strip()
    if not title:
        return ""
    normalized = title.replace("_", "").replace(" ", "").strip().lower()
    if not normalized:
        return ""
    if not re.fullmatch(r"[a-z]{2,32}", normalized):
        return ""
    return normalized


def _collect_wiki_pinyin_alias_titles(
    payload: bytes,
    valid_pinyin_keys: Set[str],
) -> Dict[str, Set[str]]:
    candidates: Dict[str, Set[str]] = {}
    text = _decode_text(payload)
    for raw_line in text.splitlines():
        title = raw_line.strip()
        if not title:
            continue
        normalized = _normalize_ascii_wiki_title_candidate(title)
        if not normalized or normalized not in valid_pinyin_keys:
            continue
        candidates.setdefault(normalized, set()).add(title)
    return candidates


def _load_wiki_redirect_alias_map(
    repo_root: pathlib.Path,
    alias_titles_by_pinyin: Dict[str, Set[str]],
    min_hanzi: int,
    max_hanzi: int = 8,
    batch_size: int = 50,
) -> Dict[str, Set[str]]:
    if not alias_titles_by_pinyin:
        return {}

    cache_path = repo_root / "data" / "cache" / "wiki_redirect_aliases.json"
    cache: Dict[str, List[str]] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    raw_titles = sorted({title for titles in alias_titles_by_pinyin.values() for title in titles})
    missing_titles = [title for title in raw_titles if title not in cache]
    resolved_updates: Dict[str, List[str]] = {}

    for start_idx in range(0, len(missing_titles), batch_size):
        batch = missing_titles[start_idx : start_idx + batch_size]
        params = urllib.parse.urlencode(
            {
                "action": "query",
                "format": "json",
                "redirects": "1",
                "titles": "|".join(batch),
            }
        )
        request = urllib.request.Request(
            f"https://zh.wikipedia.org/w/api.php?{params}",
            headers={"User-Agent": DEFAULT_HTTP_USER_AGENT},
        )
        batch_cache = {title: [] for title in batch}
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))

        for redirect in payload.get("query", {}).get("redirects", []):
            from_title = str(redirect.get("from", ""))
            to_title = _normalize_wiki_title(
                str(redirect.get("to", "")),
                min_hanzi=min_hanzi,
                max_hanzi=max_hanzi,
            )
            if not from_title or not to_title:
                continue
            batch_cache.setdefault(from_title, [])
            if to_title not in batch_cache[from_title]:
                batch_cache[from_title].append(to_title)

        resolved_updates.update(batch_cache)

    if resolved_updates:
        cache.update(resolved_updates)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    alias_map: Dict[str, Set[str]] = {}
    for pinyin, raw_titles_for_pinyin in alias_titles_by_pinyin.items():
        targets: Set[str] = set()
        for raw_title in raw_titles_for_pinyin:
            for target in cache.get(raw_title, []):
                if _cjk_len(target) >= min_hanzi:
                    targets.add(target)
        if targets:
            alias_map[pinyin] = targets
    return alias_map


def _compute_wiki_alias_support_signal(
    text: str,
    wiki_titles: Set[str],
) -> Tuple[float, int, float]:
    """
    Convert zhwiki Latin redirect aliases into a modest modern-usage prior.

    These terms often miss THUOCL/jieba direct coverage, but a stable Latin
    alias redirecting to a CJK title is still a useful popularity signal for
    modern products/brands/common concepts. Keep the boost bounded so obscure
    alias-only terms do not swamp stronger lexicon-backed words.
    """
    text_len = _cjk_len(text)
    if text_len <= 0:
        return 0.0, 0, 0.0

    if text_len <= 2:
        usage_score = 0.46
        pageview_score = 0.12
    elif text_len <= 4:
        usage_score = 0.30
        pageview_score = 0.08
    else:
        usage_score = 0.18
        pageview_score = 0.04

    source_hits = 1
    if text in wiki_titles:
        usage_score += 0.08 if text_len <= 2 else 0.05
        pageview_score += 0.04 if text_len <= 2 else 0.02
        source_hits = 2 if text_len <= 2 else 1

    return (
        min(1.0, max(0.0, usage_score)),
        max(0, source_hits),
        min(1.0, max(0.0, pageview_score)),
    )


def _has_meaningful_direct_support_for_wiki_alias(
    text: str,
    usage_score: float,
    source_hits: int,
    pageview_score: float,
    jieba_direct_score: float,
    char_score: float,
    wiki_titles: Set[str],
) -> bool:
    """
    Only keep ASCII wiki redirect aliases when the CJK target already has
    meaningful independent support.

    This blocks cases like Latin taxon names whose ASCII spelling happens to
    look like a valid pinyin key (for example "Lema" -> "lema"), while
    preserving common products/brands/concepts such as "知乎/微信/百度" that
    already show up in real usage or pageview signals.
    """
    text_len = _cjk_len(text)
    if text_len <= 0:
        return False

    bounded_usage = min(1.0, max(0.0, usage_score))
    bounded_pageviews = min(1.0, max(0.0, pageview_score))
    bounded_jieba = min(1.0, max(0.0, jieba_direct_score))
    bounded_char = min(1.0, max(0.0, char_score))

    if source_hits >= 2:
        return True

    def _looks_like_specialized_alias_target() -> bool:
        if text.endswith(("属", "疗法", "治疗法")):
            return True
        if text_len >= 5 and text.endswith(
            ("亚科", "总科", "亚目", "亚纲", "亚族", "学派", "学说")
        ):
            return True
        return False

    if _looks_like_specialized_alias_target():
        return (
            source_hits >= 2
            or bounded_usage >= 0.10
            or bounded_jieba >= 0.08
            or bounded_pageviews >= 0.06
        )

    if text_len <= 4:
        return True

    if bounded_usage >= 0.14 or bounded_jieba >= 0.10 or bounded_pageviews >= 0.08:
        return True
    if text in wiki_titles and (
        bounded_usage >= 0.10 or bounded_jieba >= 0.08 or bounded_pageviews >= 0.06
    ):
        return True
    return False


def _wiki_alias_target_matches_pinyin(
    alias_pinyin: str,
    text: str,
    pinyin_index: Dict[str, Set[str]],
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_mandarin_map: Dict[str, str] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
) -> bool:
    """
    Keep ASCII wiki redirect aliases only when the alias itself is a valid
    pinyin for the redirected CJK target.
    """
    normalized_alias = _normalize_pinyin(alias_pinyin)
    if not normalized_alias or not text:
        return False

    direct_pinyins = pinyin_index.get(text, set())
    if normalized_alias in direct_pinyins:
        return True

    derived_variants = _collect_unihan_phrase_pinyin_variants(
        text,
        unihan_readings_map,
        unihan_source_rank_map,
        unihan_mandarin_map,
        unihan_pinlu_detail_map,
    )
    return normalized_alias in derived_variants


def _compute_effective_pos_bias(
    pos_tag: str,
    text_len: int,
    usage_score: float,
    jieba_direct_score: float,
    source_hits: int,
    pageview_score: float,
    char_score: float,
) -> float:
    """
    Scale POS bias by signal confidence.

    jieba POS can mislabel common words (for example tagging regular words as 'nr').
    Use multi-signal confidence so POS is a tiebreaker, not a hard override.
    """
    base_bias = _compute_jieba_pos_bias(pos_tag, text_len)
    if abs(base_bias) <= 1e-9:
        return 0.0

    confidence = max(
        0.0,
        min(1.0, usage_score),
        min(1.0, jieba_direct_score),
        min(1.0, pageview_score * 1.3),
    )

    if source_hits >= 2:
        confidence = max(confidence, 0.42)
    elif source_hits == 1:
        confidence = max(confidence, 0.24)

    if text_len <= 2:
        confidence = max(confidence, min(1.0, char_score * 0.45))

    # Keep a small floor to preserve deterministic ordering, while avoiding over-penalization.
    confidence = min(1.0, max(0.08, confidence))
    return base_bias * confidence


def _compute_common_phrase_confidence(
    text: str,
    usage_score: float,
    source_hits: int,
    pageview_score: float,
    jieba_direct_score: float,
    wiki_support: bool,
    pos_tag: str,
    char_score: float,
) -> float:
    """
    Estimate cold-start confidence for common multi-syllable phrases.

    The goal is to help 3-6 character daily phrases surface earlier without
    turning wiki/pageview bursts into generic phrase boosts.
    """
    text_len = _cjk_len(text)
    if text_len < 3 or text_len > 6:
        return 0.0

    bounded_usage = min(1.0, max(0.0, usage_score))
    bounded_pageviews = min(1.0, max(0.0, pageview_score))
    bounded_jieba = min(1.0, max(0.0, jieba_direct_score))
    normalized_hits = min(1.0, max(0.0, float(source_hits) / 3.0))

    looks_like_person_name = _looks_like_low_signal_person_name(
        text,
        usage_score=bounded_usage,
        source_hits=source_hits,
        pageview_score=bounded_pageviews,
        jieba_direct_score=bounded_jieba,
        wiki_support=wiki_support,
        pos_tag=pos_tag,
    )
    looks_like_place_name = _looks_like_low_signal_place_name(
        text,
        usage_score=bounded_usage,
        source_hits=source_hits,
        pageview_score=bounded_pageviews,
        jieba_direct_score=bounded_jieba,
        wiki_support=wiki_support,
        pos_tag=pos_tag,
    )
    looks_like_literary_term = _looks_like_low_signal_literary_term(
        text,
        usage_score=bounded_usage,
        source_hits=source_hits,
        pageview_score=bounded_pageviews,
        jieba_direct_score=bounded_jieba,
        wiki_support=wiki_support,
        pos_tag=pos_tag,
        char_score=char_score,
    )
    if looks_like_person_name or looks_like_place_name or looks_like_literary_term:
        return 0.0
    if _is_named_entity_pos(pos_tag) and source_hits < 3 and bounded_jieba < 0.18:
        return 0.0

    confidence = (
        bounded_usage * 0.34
        + bounded_jieba * 0.46
        + bounded_pageviews * 0.12
        + normalized_hits * 0.20
    )

    if _is_conversational_pos(pos_tag):
        confidence += 0.12 if text_len <= 4 else 0.08
    elif _is_noun_pos(pos_tag):
        confidence += 0.08 if text_len <= 4 else 0.04

    if text_len == 3 and char_score >= 0.52:
        confidence += 0.04
    elif text_len <= 5 and char_score >= 0.46:
        confidence += 0.02

    if bounded_jieba >= 0.18 and source_hits >= 2:
        confidence += 0.12
    elif bounded_jieba >= 0.12 and bounded_usage >= 0.12:
        confidence += 0.08
    elif bounded_jieba >= 0.08 and source_hits >= 2:
        confidence += 0.04

    if bounded_pageviews >= 0.20 and bounded_jieba < 0.05 and source_hits <= 1:
        confidence -= 0.10
    if bounded_usage < 0.04 and bounded_jieba < 0.04:
        confidence *= 0.40
    if text_len >= 5 and bounded_jieba < 0.06 and source_hits <= 1:
        confidence *= 0.65

    return min(1.0, max(0.0, confidence))


def _is_daily_number_word_candidate(
    text: str,
    text_len: int,
    usage_score: float,
    source_hits: int,
    pos_tag: str,
) -> bool:
    if text_len < 2 or text_len > 4:
        return False
    if _is_named_entity_pos(pos_tag):
        return False
    if not _is_pure_daily_number_word(text):
        return False

    bounded_usage = min(1.0, max(0.0, usage_score))
    return bounded_usage >= 0.84 or source_hits >= 4


def _is_short_everyday_term_candidate(
    text: str,
    text_len: int,
    usage_score: float,
    source_hits: int,
    pageview_score: float,
    jieba_direct_score: float,
    pos_tag: str,
    char_score: float,
) -> bool:
    """
    Identify 2-character high-frequency everyday terms that should behave
    like daily phrases in homophone buckets even without wiki-augmentation.

    The key gap this covers is short functional / localizer / conversational
    terms such as "还是" or "里面": they are common input targets, but they
    are often absent from the explicit daily seed layers, so requiring
    wiki-augmented membership is too strict.
    """
    if text_len != 2:
        return False
    if _is_named_entity_pos(pos_tag):
        return False

    bounded_usage = min(1.0, max(0.0, usage_score))
    bounded_pageviews = min(1.0, max(0.0, pageview_score))
    bounded_jieba = min(1.0, max(0.0, jieba_direct_score))

    if (
        bounded_usage < 0.08
        and bounded_jieba < 0.08
        and source_hits < 2
        and bounded_pageviews < 0.04
    ):
        return False

    if pos_tag.startswith(("d", "r", "p", "u", "c", "f", "s", "t")):
        return char_score >= 0.40 or bounded_usage >= 0.10 or bounded_jieba >= 0.10

    if pos_tag.startswith(("v", "a")):
        if (
            pos_tag.startswith("vn")
            and bounded_jieba < 0.12
            and bounded_pageviews < 0.04
            and source_hits <= 3
        ):
            return False
        return (
            bounded_usage >= 0.12
            or bounded_jieba >= 0.12
            or (bounded_usage >= 0.08 and bounded_jieba >= 0.08)
            or (
                source_hits >= 2
                and (bounded_usage >= 0.08 or bounded_jieba >= 0.08)
            )
        )

    if _is_noun_pos(pos_tag):
        if source_hits >= 2:
            return (
                bounded_jieba >= 0.12
                or (bounded_usage >= 0.14 and bounded_jieba >= 0.08)
                or (bounded_usage >= 0.08 and bounded_jieba >= 0.08)
                or (
                    bounded_pageviews >= 0.10
                    and (bounded_usage >= 0.08 or bounded_jieba >= 0.08)
                )
                or (
                    bounded_usage >= 0.18
                    and bounded_jieba >= 0.06
                    and char_score >= 0.62
                )
            )

        if bounded_pageviews >= 0.18:
            return (
                bounded_jieba >= 0.16
                or bounded_usage >= 0.14
                or (char_score >= 0.70 and bounded_jieba >= 0.12)
            )

        return (
            bounded_jieba >= 0.46
            or (bounded_jieba >= 0.38 and char_score >= 0.70)
            or (bounded_jieba >= 0.30 and char_score >= 0.80)
        )

    return False


def _is_daily_phrase_candidate(
    text: str,
    text_len: int,
    usage_score: float,
    source_hits: int,
    pageview_score: float,
    jieba_direct_score: float,
    wiki_support: bool,
    pos_tag: str,
    char_score: float,
    wiki_augmented_terms: Set[str] | None,
    preferred_terms: Set[str] | None = None,
) -> bool:
    if _is_daily_number_word_candidate(
        text,
        text_len=text_len,
        usage_score=usage_score,
        source_hits=source_hits,
        pos_tag=pos_tag,
    ):
        return True

    if _is_short_everyday_term_candidate(
        text,
        text_len=text_len,
        usage_score=usage_score,
        source_hits=source_hits,
        pageview_score=pageview_score,
        jieba_direct_score=jieba_direct_score,
        pos_tag=pos_tag,
        char_score=char_score,
    ):
        return True

    preferred_terms = preferred_terms or set()
    if text in preferred_terms and usage_score >= 0.90:
        return True

    wiki_augmented_terms = wiki_augmented_terms or set()
    if text not in wiki_augmented_terms:
        return False
    if _is_named_entity_pos(pos_tag):
        return False
    if text_len < 2 or text_len > 4:
        return False

    if text_len <= 2:
        # Two-character augmented terms have a long noisy tail of domain nouns
        # and historical labels (for example "海事", "维新", "简易"). Treat them
        # as daily-phrase candidates only when they are explicit preferred terms
        # or when short-term POS/signal heuristics already classified them above.
        return False

    bounded_usage = min(1.0, max(0.0, usage_score))
    bounded_pageviews = min(1.0, max(0.0, pageview_score))
    bounded_jieba = min(1.0, max(0.0, jieba_direct_score))

    if text_len <= 2:
        return _is_conversational_pos(pos_tag) or (
            char_score >= 0.42
            and (
                bounded_usage >= 0.08
                or bounded_jieba >= 0.08
                or source_hits >= 2
                or bounded_pageviews >= 0.06
                or wiki_support
            )
        )

    phrase_confidence = _compute_common_phrase_confidence(
        text,
        usage_score=bounded_usage,
        source_hits=source_hits,
        pageview_score=bounded_pageviews,
        jieba_direct_score=bounded_jieba,
        wiki_support=wiki_support,
        pos_tag=pos_tag,
        char_score=char_score,
    )
    return (
        _is_conversational_pos(pos_tag)
        or phrase_confidence >= 0.18
        or (
            bounded_usage >= 0.10
            and (
                bounded_jieba >= 0.08
                or source_hits >= 2
                or bounded_pageviews >= 0.08
                or wiki_support
            )
        )
    )


def _build_effective_char_prior(
    mapping: Dict[Tuple[str, str], int],
    char_frequency_prior: Dict[str, float] | None,
) -> Dict[str, float]:
    char_frequency_prior = char_frequency_prior or {}
    mapping_char_prior = _build_single_char_weight_prior(mapping)
    mapping_frequency_prior = _build_mapping_char_frequency_prior(mapping)
    if not char_frequency_prior:
        if not mapping_char_prior:
            return mapping_frequency_prior
        if not mapping_frequency_prior:
            return mapping_char_prior

        char_prior: Dict[str, float] = {}
        for ch in set(mapping_char_prior.keys()) | set(mapping_frequency_prior.keys()):
            char_prior[ch] = (
                0.34 * mapping_char_prior.get(ch, 0.0)
                + 0.66 * mapping_frequency_prior.get(ch, 0.0)
            )
        return char_prior

    char_prior: Dict[str, float] = {}
    for ch in (
        set(mapping_char_prior.keys())
        | set(mapping_frequency_prior.keys())
        | set(char_frequency_prior.keys())
    ):
        char_prior[ch] = (
            0.12 * mapping_char_prior.get(ch, 0.0)
            + 0.16 * mapping_frequency_prior.get(ch, 0.0)
            + 0.72 * char_frequency_prior.get(ch, 0.0)
        )
    return char_prior


def _build_edge_family_support_for_terms(
    mapping: Dict[Tuple[str, str], int],
) -> Dict[Tuple[str, str], float]:
    """
    Build conservative family support for short terms from longer terms that
    contain them at the edge with aligned compact pinyin.

    This is intentionally weaker than broad-profile usage signals, but it gives
    cedict-only buckets a useful fallback so rare variants do not stay tied with
    mainstream forms simply because they share the same base length weight.
    """
    variants_by_text: Dict[str, List[str]] = {}
    for pinyin, text in mapping.keys():
        text_len = _cjk_len(text)
        if text_len < 2 or text_len > 4:
            continue
        bucket = variants_by_text.setdefault(text, [])
        if pinyin not in bucket:
            bucket.append(pinyin)

    if not variants_by_text:
        return {}

    family_support: Dict[Tuple[str, str], float] = {}
    for (term_pinyin, term_text), weight in mapping.items():
        term_len = _cjk_len(term_text)
        if term_len <= 2:
            continue

        term_support = min(420.0, float(weight))
        max_sub_len = min(4, term_len - 1)
        seen_keys: Set[Tuple[str, str]] = set()
        for sub_len in range(2, max_sub_len + 1):
            prefix_text = term_text[:sub_len]
            for sub_pinyin in variants_by_text.get(prefix_text, []):
                key = (sub_pinyin, prefix_text)
                if key in seen_keys:
                    continue
                if term_pinyin.startswith(sub_pinyin):
                    family_support[key] = family_support.get(key, 0.0) + term_support
                    seen_keys.add(key)

            suffix_text = term_text[-sub_len:]
            for sub_pinyin in variants_by_text.get(suffix_text, []):
                key = (sub_pinyin, suffix_text)
                if key in seen_keys:
                    continue
                if term_pinyin.endswith(sub_pinyin):
                    family_support[key] = family_support.get(key, 0.0) + term_support
                    seen_keys.add(key)

    return family_support


def _rerank_multi_pronunciation_terms(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float] | None,
    stats_prefix: str,
) -> Dict[str, int]:
    """
    Re-rank same-text multi-pronunciation entries using family support.

    Usage/pageview signals are mostly text-level, so rare alternate readings of
    a very common word can incorrectly inherit the mainstream word's weight.
    Use longer terms that contain the same text as a conservative proxy for
    which reading is actually productive in modern usage.
    """
    stats = {
        f"{stats_prefix}_multi_pronunciation_terms": 0,
        f"{stats_prefix}_multi_pronunciation_damped": 0,
        f"{stats_prefix}_multi_pronunciation_penalty_total": 0,
    }
    if not mapping:
        return stats

    jieba_direct_signal_map = jieba_direct_signal_map or {}

    ambiguous_terms: Dict[str, List[Tuple[str, int]]] = {}
    ambiguous_by_len: Dict[int, Set[str]] = {}
    for (pinyin, text), weight in mapping.items():
        text_len = _cjk_len(text)
        if text_len < 2 or text_len > 4:
            continue
        ambiguous_terms.setdefault(text, []).append((pinyin, weight))

    ambiguous_terms = {
        text: items for text, items in ambiguous_terms.items() if len(items) >= 2
    }
    if not ambiguous_terms:
        return stats

    for text in ambiguous_terms.keys():
        ambiguous_by_len.setdefault(_cjk_len(text), set()).add(text)

    family_support: Dict[str, Dict[str, float]] = {
        text: {pinyin: 0.0 for pinyin, _weight in items}
        for text, items in ambiguous_terms.items()
    }

    def _matches_variant(
        term_pinyin: str,
        sub_pinyin: str,
        start_index: int,
        sub_len: int,
        term_len: int,
    ) -> bool:
        if not sub_pinyin or sub_pinyin not in term_pinyin:
            return False
        if start_index == 0:
            return term_pinyin.startswith(sub_pinyin)
        if start_index + sub_len == term_len:
            return term_pinyin.endswith(sub_pinyin)
        # Internal compact-pinyin substring matches are too noisy here: character
        # offsets are not syllable offsets, so a raw `in` check can spuriously
        # boost the wrong pronunciation family. Keep family support conservative
        # and only trust prefix/suffix matches that stay aligned to the term edge.
        return False

    for (term_pinyin, term_text), weight in mapping.items():
        term_len = _cjk_len(term_text)
        if term_len <= 2:
            continue

        usage_score = min(1.0, max(0.0, usage_score_map.get(term_text, 0.0)))
        source_hits = max(0, source_hits_map.get(term_text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(term_text, 0.0)))
        jieba_direct_score = min(
            1.0, max(0.0, jieba_direct_signal_map.get(term_text, 0.0))
        )
        term_support = min(420.0, float(weight)) + (
            usage_score * 180.0
            + jieba_direct_score * 180.0
            + pageview_score * 64.0
            + min(source_hits, 4) * 24.0
        )

        max_sub_len = min(4, term_len - 1)
        seen_subtexts: Set[str] = set()
        for sub_len in range(2, max_sub_len + 1):
            candidates = ambiguous_by_len.get(sub_len, set())
            if not candidates:
                continue
            for start_idx in range(0, term_len - sub_len + 1):
                subtext = term_text[start_idx : start_idx + sub_len]
                if subtext not in candidates or subtext in seen_subtexts:
                    continue
                seen_subtexts.add(subtext)

                edge_factor = 1.0
                if start_idx != 0 and start_idx + sub_len != term_len:
                    edge_factor = 0.72

                for sub_pinyin, _variant_weight in ambiguous_terms[subtext]:
                    if not _matches_variant(
                        term_pinyin,
                        sub_pinyin,
                        start_idx,
                        sub_len,
                        term_len,
                    ):
                        continue
                    family_support[subtext][sub_pinyin] += term_support * edge_factor

    for text, items in ambiguous_terms.items():
        supports: List[Tuple[float, str, int]] = []
        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        own_signal_support = (
            usage_score * 120.0
            + jieba_direct_score * 120.0
            + pageview_score * 40.0
            + min(source_hits, 4) * 18.0
        )

        for pinyin, weight in items:
            support = float(weight) + own_signal_support + family_support[text].get(
                pinyin, 0.0
            )
            supports.append((support, pinyin, weight))

        supports.sort(key=lambda item: (-item[0], item[1]))
        if len(supports) < 2:
            continue

        best_support, best_pinyin, best_weight = supports[0]
        second_support = supports[1][0]
        if best_support < 520.0:
            continue
        strong_primary_reading = best_weight >= 900 and any(
            variant_weight >= 420 for _support, _pinyin, variant_weight in supports[1:]
        )
        if best_support < second_support * 1.35 and not strong_primary_reading:
            continue

        stats[f"{stats_prefix}_multi_pronunciation_terms"] += 1
        best_family_support = family_support[text].get(best_pinyin, 0.0)
        gap = best_support - second_support
        for support, pinyin, weight in supports[1:]:
            penalty = 36 + int(gap // 4)
            if support <= best_support * 0.70:
                penalty += 40
            if support <= best_support * 0.55:
                penalty += 56
            if usage_score >= 0.20 and source_hits >= 2 and support <= best_support * 0.82:
                penalty += 120
            if own_signal_support >= 110.0 and support <= best_support * 0.72:
                penalty += 72
            if family_support[text].get(pinyin, 0.0) <= best_family_support * 0.35:
                penalty += 56
            if family_support[text].get(pinyin, 0.0) <= best_family_support * 0.22:
                penalty += 72
            if strong_primary_reading and weight > 360:
                penalty = max(penalty, weight - 360)
            penalty = min(min(460, max(280, int(weight * 0.55))), penalty)
            if penalty <= 0:
                continue

            key = (pinyin, text)
            new_weight = max(1, weight - penalty)
            if new_weight >= weight:
                continue
            mapping[key] = new_weight
            stats[f"{stats_prefix}_multi_pronunciation_damped"] += 1
            stats[f"{stats_prefix}_multi_pronunciation_penalty_total"] += penalty

    return stats


def _propagate_tc_multi_pronunciation_preference_from_sc(
    sc_map: Dict[Tuple[str, str], int],
    tc_map: Dict[Tuple[str, str], int],
    tc_to_sc_map: Dict[str, Set[str]] | None,
    stats_prefix: str,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_multi_pronunciation_sc_guided_terms": 0,
        f"{stats_prefix}_multi_pronunciation_sc_guided_damped": 0,
        f"{stats_prefix}_multi_pronunciation_sc_guided_penalty_total": 0,
    }
    if not sc_map or not tc_map or not tc_to_sc_map:
        return stats

    sc_variants_by_text: Dict[str, Dict[str, int]] = {}
    for (pinyin, text), weight in sc_map.items():
        if _cjk_len(text) < 2:
            continue
        sc_variants_by_text.setdefault(text, {})[pinyin] = weight
    sc_variants_by_text = {
        text: variants
        for text, variants in sc_variants_by_text.items()
        if len(variants) >= 2
    }
    if not sc_variants_by_text:
        return stats

    tc_variants_by_text: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in tc_map.items():
        if _cjk_len(text) < 2:
            continue
        tc_variants_by_text.setdefault(text, []).append((pinyin, weight))

    for tc_text, tc_items in tc_variants_by_text.items():
        if len(tc_items) < 2:
            continue
        candidate_sc_texts: Set[str] = set()
        if tc_text in sc_variants_by_text:
            candidate_sc_texts.add(tc_text)
        candidate_sc_texts.update(tc_to_sc_map.get(tc_text, set()))
        if not candidate_sc_texts:
            continue

        sc_variants: Dict[str, int] = {}
        for sc_text in candidate_sc_texts:
            variants = sc_variants_by_text.get(sc_text)
            if not variants:
                continue
            for pinyin, weight in variants.items():
                current = sc_variants.get(pinyin, 0)
                if weight > current:
                    sc_variants[pinyin] = weight
        if len(sc_variants) < 2:
            continue

        best_sc_weight = max(sc_variants.values())
        if best_sc_weight <= 0:
            continue

        stats[f"{stats_prefix}_multi_pronunciation_sc_guided_terms"] += 1
        for pinyin, tc_weight in tc_items:
            sc_weight = sc_variants.get(pinyin, 0)
            if sc_weight <= 0 or sc_weight >= best_sc_weight:
                continue
            ratio_gap = 1.0 - min(1.0, float(sc_weight) / float(best_sc_weight))
            if ratio_gap < 0.24:
                continue

            penalty = 64 + int(round(ratio_gap * 240.0))
            if sc_weight <= best_sc_weight * 0.75 and tc_weight >= best_sc_weight * 0.70:
                penalty += 28
            penalty = min(260, penalty)
            key = (pinyin, tc_text)
            new_weight = max(1, tc_weight - penalty)
            if new_weight >= tc_weight:
                continue
            tc_map[key] = new_weight
            stats[f"{stats_prefix}_multi_pronunciation_sc_guided_damped"] += 1
            stats[f"{stats_prefix}_multi_pronunciation_sc_guided_penalty_total"] += penalty

    return stats


def _propagate_tc_homophone_preference_from_sc(
    sc_map: Dict[Tuple[str, str], int],
    tc_map: Dict[Tuple[str, str], int],
    tc_to_sc_map: Dict[str, Set[str]] | None,
    stats_prefix: str,
    *,
    min_boost_gap: int = 56,
    force_sc_leader_order: bool = False,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_homophone_sc_guided_buckets": 0,
        f"{stats_prefix}_homophone_sc_guided_boosted": 0,
        f"{stats_prefix}_homophone_sc_guided_damped": 0,
        f"{stats_prefix}_homophone_sc_guided_boost_total": 0,
        f"{stats_prefix}_homophone_sc_guided_penalty_total": 0,
    }
    if not sc_map or not tc_map or not tc_to_sc_map:
        return stats

    sc_buckets: Dict[str, Dict[str, int]] = {}
    for (pinyin, text), weight in sc_map.items():
        if weight <= 0 or _cjk_len(text) < 2:
            continue
        sc_buckets.setdefault(pinyin, {})[text] = max(
            weight, sc_buckets.get(pinyin, {}).get(text, 0)
        )

    tc_buckets: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in tc_map.items():
        if weight <= 0 or _cjk_len(text) < 2:
            continue
        tc_buckets.setdefault(pinyin, []).append((text, weight))

    for pinyin, tc_items in tc_buckets.items():
        if len(tc_items) < 2:
            continue
        sc_bucket = sc_buckets.get(pinyin)
        if not sc_bucket:
            continue

        aligned_items: List[Tuple[str, int, int, str]] = []
        best_sc_weight = 0
        best_tc_weight = 0
        for tc_text, tc_weight in tc_items:
            candidate_sc_texts: Set[str] = set()
            if tc_text in sc_bucket:
                candidate_sc_texts.add(tc_text)
            candidate_sc_texts.update(tc_to_sc_map.get(tc_text, set()))

            sc_weight = 0
            best_sc_text_for_tc = ""
            for sc_text in candidate_sc_texts:
                candidate_weight = sc_bucket.get(sc_text, 0)
                if candidate_weight > sc_weight:
                    sc_weight = candidate_weight
                    best_sc_text_for_tc = sc_text
            if sc_weight <= 0:
                continue

            aligned_items.append((tc_text, tc_weight, sc_weight, best_sc_text_for_tc))
            best_sc_weight = max(best_sc_weight, sc_weight)
            best_tc_weight = max(best_tc_weight, tc_weight)

        if len(aligned_items) < 2 or best_sc_weight <= 0 or best_tc_weight <= 0:
            continue

        stats[f"{stats_prefix}_homophone_sc_guided_buckets"] += 1
        for tc_text, tc_weight, sc_weight, best_sc_text_for_tc in aligned_items:
            sc_ratio = min(1.0, max(0.0, float(sc_weight) / float(best_sc_weight)))
            target_weight = max(1, int(round(best_tc_weight * sc_ratio)))
            gap = target_weight - tc_weight
            key = (pinyin, tc_text)

            same_sc_higher_tc_variant = any(
                other_tc_text != tc_text
                and other_sc_text == best_sc_text_for_tc
                and other_tc_weight > tc_weight
                for other_tc_text, other_tc_weight, _other_sc_weight, other_sc_text in aligned_items
            )
            force_leader_for_item = (
                force_sc_leader_order
                and sc_ratio >= 0.99
                and gap > 0
                and bool(best_sc_text_for_tc)
                and not same_sc_higher_tc_variant
            )
            should_boost = gap >= min_boost_gap or (
                force_leader_for_item
            )
            if should_boost:
                if sc_ratio >= 0.99:
                    boost_factor = 0.68
                elif sc_ratio >= 0.95:
                    boost_factor = 0.55
                else:
                    boost_factor = 0.42
                boost = min(220, max(24, int(round(gap * boost_factor))))
                new_weight = tc_weight + boost
                if force_leader_for_item:
                    new_weight = max(new_weight, min(1000, best_tc_weight + 1))
                if new_weight > tc_weight:
                    tc_map[key] = new_weight
                    stats[f"{stats_prefix}_homophone_sc_guided_boosted"] += 1
                    stats[f"{stats_prefix}_homophone_sc_guided_boost_total"] += boost
            elif gap <= -72 and sc_ratio <= 0.92:
                penalty_factor = 0.34 if sc_ratio <= 0.84 else 0.26
                penalty = min(180, max(20, int(round(abs(gap) * penalty_factor))))
                new_weight = max(1, tc_weight - penalty)
                if new_weight < tc_weight:
                    tc_map[key] = new_weight
                    stats[f"{stats_prefix}_homophone_sc_guided_damped"] += 1
                    stats[f"{stats_prefix}_homophone_sc_guided_penalty_total"] += penalty

    return stats


def _rerank_homophone_buckets(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    wiki_augmented_terms: Set[str] | None,
    jieba_direct_signal_map: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    char_frequency_prior: Dict[str, float] | None,
    term_style_penalty_map: Dict[Tuple[str, str], int] | None,
    term_semantic_bonus_map: Dict[Tuple[str, str], int] | None,
    preferred_terms: Set[str] | None,
    stats_prefix: str,
    weak_leader_terms: Set[str] | None = None,
) -> Dict[str, int]:
    """
    Re-rank entries within each same-pinyin bucket to suppress rare/noisy
    homophone candidates and promote commonly used terms.

    The score mixes:
    - term usage/pageview/source-hit signals
    - normalized single-character prior from the same mapping
    - a small original-weight prior for stability
    """
    c_max_delta = 320
    c_sparse_penalty = 132
    c_weak_signal_penalty = 78
    c_named_entity_penalty = 108
    c_literary_penalty = 86
    c_rare_form_penalty = 168

    stats = {
        f"{stats_prefix}_homophone_buckets": 0,
        f"{stats_prefix}_homophone_entries_adjusted": 0,
        f"{stats_prefix}_homophone_entries_boosted": 0,
        f"{stats_prefix}_homophone_entries_damped": 0,
        f"{stats_prefix}_homophone_dominant_common_boosted": 0,
        f"{stats_prefix}_homophone_dominant_common_damped": 0,
        f"{stats_prefix}_homophone_sparse_penalized": 0,
        f"{stats_prefix}_homophone_literary_penalized": 0,
        f"{stats_prefix}_homophone_written_tail_penalized": 0,
        f"{stats_prefix}_homophone_rare_form_penalized": 0,
        f"{stats_prefix}_homophone_inflated_short_penalized": 0,
        f"{stats_prefix}_homophone_modernity_risk_penalized": 0,
        f"{stats_prefix}_homophone_daily_phrase_boosted": 0,
        f"{stats_prefix}_homophone_daily_phrase_damped": 0,
        f"{stats_prefix}_homophone_daily_number_boosted": 0,
        f"{stats_prefix}_homophone_rare_char_short_damped": 0,
        f"{stats_prefix}_homophone_short_everyday_boosted": 0,
        f"{stats_prefix}_homophone_short_everyday_non_daily_damped": 0,
        f"{stats_prefix}_homophone_short_everyday_weak_noun_damped": 0,
        f"{stats_prefix}_homophone_conversational_family_noun_damped": 0,
        f"{stats_prefix}_homophone_short_popular_wiki_boosted": 0,
        f"{stats_prefix}_homophone_short_popular_named_bucket_damped": 0,
        f"{stats_prefix}_homophone_daily_phrase_short_non_daily_damped": 0,
        f"{stats_prefix}_homophone_preferred_term_boosted": 0,
        f"{stats_prefix}_homophone_preferred_term_damped": 0,
        f"{stats_prefix}_homophone_supplement_exact_protected": 0,
        f"{stats_prefix}_homophone_supplement_exact_competitor_capped": 0,
        f"{stats_prefix}_homophone_short_family_noun_damped": 0,
        f"{stats_prefix}_homophone_semantic_daily_boosted": 0,
    }
    if not mapping:
        return stats
    has_robust_usage = bool(
        usage_score_map or source_hits_map or pageviews_signal_map or wiki_titles
    )

    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    term_style_penalty_map = term_style_penalty_map or {}
    term_semantic_bonus_map = term_semantic_bonus_map or {}
    preferred_terms = preferred_terms or set()
    weak_leader_terms = weak_leader_terms or set()
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    edge_family_support = _build_edge_family_support_for_terms(mapping)
    buckets: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        buckets.setdefault(pinyin, []).append((text, weight))

    for pinyin, items in buckets.items():
        if len(items) < 2:
            continue
        stats[f"{stats_prefix}_homophone_buckets"] += 1

        raw_scores: Dict[str, float] = {}
        common_signal_scores: Dict[str, float] = {}
        bucket_has_strong_term = False
        bucket_has_family_term = False
        bucket_has_conversational_short_term = False
        bucket_has_daily_phrase_term = False
        bucket_has_daily_number_term = False
        bucket_has_short_everyday_term = False
        bucket_has_preferred_term = False
        bucket_has_supplement_exact_term = False
        bucket_supplement_exact_weight = 0
        bucket_supplement_exact_signal = -1.0
        bucket_has_short_popular_named_term = False
        bucket_has_chat_prefixed_short_term = False
        bucket_dominant_common_text = ""
        bucket_dominant_common_signal = -1.0
        bucket_dominant_common_runner_up = -1.0
        bucket_direct_leader_text = ""
        bucket_direct_leader_score = -1.0
        bucket_direct_runner_up = -1.0
        bucket_direct_leader_usage = 0.0
        bucket_direct_leader_jieba = 0.0
        bucket_direct_leader_source_hits = 0
        bucket_direct_leader_pageview = 0.0
        bucket_direct_leader_pos = ""
        strong_short_head_terms: Set[str] = set()
        for text, _weight in items:
            text_len = _cjk_len(text)
            count_measure_support = _is_daily_count_measure_phrase(text)
            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            source_hits = max(0, source_hits_map.get(text, 0))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            family_support_score = min(
                1.0,
                max(0.0, edge_family_support.get((pinyin, text), 0.0) / 900.0),
            )
            wiki_support = _has_effective_wiki_support(
                text,
                wiki_titles,
                pageview_score=pageview_score,
                source_hits=source_hits,
                wiki_augmented_terms=wiki_augmented_terms,
            )
            wiki_hit = 1.0 if wiki_support else 0.0
            jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            char_score = _compute_text_single_char_prior(text, char_prior)
            pos_tag = jieba_pos_map.get(text, "")
            semantic_bonus = term_semantic_bonus_map.get((pinyin, text), 0)
            supplement_exact_support = (
                text in weak_leader_terms
                and 2 <= text_len <= 4
                and not count_measure_support
                and not _is_pure_daily_number_word(text)
                and (
                    usage_score >= 0.18
                    or source_hits >= 1
                    or jieba_direct_score >= 0.08
                )
            )
            semantic_daily_support = (
                text_len <= 3
                and semantic_bonus >= 120
                and not _is_named_entity_pos(pos_tag)
            )
            if text_len <= 3 and not _is_named_entity_pos(pos_tag):
                direct_common_score = (
                    jieba_direct_score
                    + usage_score * 0.35
                    + min(source_hits, 3) * 0.035
                    + pageview_score * 0.12
                )
                if supplement_exact_support:
                    direct_common_score += min(
                        0.40,
                        0.18 + usage_score * 0.35 + min(source_hits, 2) * 0.03,
                    )
                if direct_common_score > bucket_direct_leader_score:
                    bucket_direct_runner_up = bucket_direct_leader_score
                    bucket_direct_leader_score = direct_common_score
                    bucket_direct_leader_text = text
                    bucket_direct_leader_usage = usage_score
                    bucket_direct_leader_jieba = jieba_direct_score
                    bucket_direct_leader_source_hits = source_hits
                    bucket_direct_leader_pageview = pageview_score
                    bucket_direct_leader_pos = pos_tag
                elif direct_common_score > bucket_direct_runner_up:
                    bucket_direct_runner_up = direct_common_score
            if (
                text_len <= 2
                and (
                    usage_score >= 0.10
                    or jieba_direct_score >= 0.06
                    or source_hits >= 2
                    or pageview_score >= 0.10
                    or wiki_hit > 0.0
                )
            ):
                strong_short_head_terms.add(text)
            if (not has_robust_usage) and family_support_score >= 0.20:
                bucket_has_family_term = True
            short_everyday_support = _is_short_everyday_term_candidate(
                text,
                text_len=text_len,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                pos_tag=pos_tag,
                char_score=char_score,
            )
            if short_everyday_support:
                bucket_has_short_everyday_term = True
            if (
                text_len <= 2
                and text
                and text[0] in DAILY_CHAT_SEED_PREFIXES
                and (
                    _is_conversational_pos(pos_tag)
                    or usage_score >= 0.08
                    or jieba_direct_score >= 0.06
                    or source_hits >= 1
                )
            ):
                bucket_has_chat_prefixed_short_term = True
            if semantic_daily_support:
                bucket_has_short_everyday_term = True
                bucket_has_daily_phrase_term = True
            if supplement_exact_support:
                bucket_has_daily_phrase_term = True
                bucket_has_short_everyday_term = True
                bucket_has_supplement_exact_term = True
                supplement_signal = (
                    usage_score * 0.42
                    + jieba_direct_score * 0.36
                    + min(1.0, source_hits / 4.0) * 0.12
                )
                if supplement_signal > bucket_supplement_exact_signal:
                    bucket_supplement_exact_signal = supplement_signal
                    bucket_supplement_exact_weight = max(
                        bucket_supplement_exact_weight,
                        min(max(1, min(1000, int(weight))), CURATED_DAILY_SUPPLEMENT_WEIGHT_CAP),
                    )
            if (not count_measure_support) and _is_daily_phrase_candidate(
                text,
                text_len=text_len,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
                char_score=char_score,
                wiki_augmented_terms=wiki_augmented_terms,
                preferred_terms=preferred_terms,
            ):
                bucket_has_daily_phrase_term = True
            if _is_daily_number_word_candidate(
                text,
                text_len=text_len,
                usage_score=usage_score,
                source_hits=source_hits,
                pos_tag=pos_tag,
            ):
                bucket_has_daily_number_term = True
            if text in preferred_terms and usage_score >= 0.90 and not count_measure_support:
                bucket_has_preferred_term = True
            if (
                text_len <= 2
                and _is_named_entity_pos(pos_tag)
                and (wiki_hit > 0.0 or pageview_score >= 0.12)
                and (
                    usage_score >= 0.18
                    or jieba_direct_score >= 0.10
                    or source_hits >= 2
                )
            ):
                bucket_has_short_popular_named_term = True
        bucket_direct_leader_margin = max(
            0.0,
            bucket_direct_leader_score - max(0.0, bucket_direct_runner_up),
        )
        bucket_direct_leader_active = (
            bool(bucket_direct_leader_text)
            and bucket_direct_leader_jieba >= 0.18
            and bucket_direct_leader_margin >= 0.16
            and (
                bucket_direct_leader_usage >= 0.08
                or bucket_direct_leader_jieba >= 0.30
                or bucket_direct_leader_source_hits >= 1
                or bucket_direct_leader_pageview >= 0.04
            )
            and not (
                bucket_has_chat_prefixed_short_term
                and _is_noun_pos(bucket_direct_leader_pos)
                and bucket_direct_leader_jieba < 0.75
            )
        )
        for text, weight in items:
            text_len = _cjk_len(text)
            count_measure_support = _is_daily_count_measure_phrase(text)
            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            source_hits = max(0, source_hits_map.get(text, 0))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            wiki_hit = 1.0 if _has_effective_wiki_support(
                text,
                wiki_titles,
                pageview_score=pageview_score,
                source_hits=source_hits,
                wiki_augmented_terms=wiki_augmented_terms,
            ) else 0.0
            jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            family_support_score = min(
                1.0,
                max(0.0, edge_family_support.get((pinyin, text), 0.0) / 900.0),
            )
            char_score = _compute_text_single_char_prior(text, char_prior)
            pos_tag = jieba_pos_map.get(text, "")
            semantic_bonus = term_semantic_bonus_map.get((pinyin, text), 0)
            supplement_exact_support = (
                text in weak_leader_terms
                and 2 <= text_len <= 4
                and not count_measure_support
                and not _is_pure_daily_number_word(text)
                and (
                    usage_score >= 0.18
                    or source_hits >= 1
                    or jieba_direct_score >= 0.08
                )
            )
            semantic_daily_support = (
                text_len <= 3
                and semantic_bonus >= 120
                and not _is_named_entity_pos(pos_tag)
            )
            daily_phrase_support = _is_daily_phrase_candidate(
                text,
                text_len=text_len,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_hit > 0.0,
                pos_tag=pos_tag,
                char_score=char_score,
                wiki_augmented_terms=wiki_augmented_terms,
                preferred_terms=preferred_terms,
            )
            if semantic_daily_support:
                daily_phrase_support = True
            if supplement_exact_support:
                daily_phrase_support = True
            if count_measure_support:
                daily_phrase_support = False
            short_everyday_support = _is_short_everyday_term_candidate(
                text,
                text_len=text_len,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                pos_tag=pos_tag,
                char_score=char_score,
            )
            if semantic_daily_support and text_len <= 2:
                short_everyday_support = True
            if supplement_exact_support and text_len <= 2:
                short_everyday_support = True
            if count_measure_support:
                short_everyday_support = False
            daily_number_support = _is_daily_number_word_candidate(
                text,
                text_len=text_len,
                usage_score=usage_score,
                source_hits=source_hits,
                pos_tag=pos_tag,
            )
            if count_measure_support:
                daily_number_support = False
            pos_bias = _compute_effective_pos_bias(
                pos_tag=pos_tag,
                text_len=text_len,
                usage_score=usage_score,
                jieba_direct_score=jieba_direct_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                char_score=char_score,
            )
            min_char_prior = _compute_min_char_prior(text, char_prior)
            if text_len == 1:
                char_weight = 220.0
            elif text_len == 2:
                # For multi-character exact words, term-level frequency should
                # dominate character-level priors. A high-prior character pair
                # is evidence that a word is plausible, not that it is more
                # common than a better-supported same-pinyin word.
                char_weight = 160.0
            elif text_len <= 4:
                char_weight = 72.0
            else:
                char_weight = 28.0
            conversational_short_supported = (
                text_len <= 2
                and _is_conversational_pos(pos_tag)
                and (
                    daily_phrase_support
                    or short_everyday_support
                    or semantic_daily_support
                    or usage_score >= 0.08
                    or jieba_direct_score >= 0.06
                    or source_hits >= 2
                    or pageview_score >= 0.05
                    or wiki_hit > 0.0
                )
            )
            if conversational_short_supported:
                bucket_has_conversational_short_term = True
            if (
                usage_score >= 0.28
                or jieba_direct_score >= 0.42
                or source_hits >= 2
                or pageview_score >= 0.22
                or wiki_hit > 0.0
                or (pos_bias >= 0.08 and jieba_direct_score >= 0.16)
            ):
                bucket_has_strong_term = True

            common_signal = 0.0
            if text_len <= 3 and not _is_named_entity_pos(pos_tag):
                common_signal = (
                    usage_score * 320.0
                    + jieba_direct_score * 360.0
                    + pageview_score * 120.0
                    + min(source_hits, 4) * 34.0
                    + wiki_hit * 26.0
                    + family_support_score * (148.0 if not has_robust_usage else 96.0)
                    + max(0.0, pos_bias) * 160.0
                    + float(semantic_bonus) * 0.90
                )
                if text_len <= 2:
                    common_signal += char_score * 60.0
                    if _is_conversational_pos(pos_tag):
                        if conversational_short_supported:
                            common_signal += 68.0
                        else:
                            # POS tags are noisy for short homophones. Keep a
                            # weak verb/function-word hint, but do not let a
                            # low-evidence POS label outweigh direct usage.
                            common_signal += 18.0
                        if conversational_short_supported and text and text[0] in ("不", "没", "无", "非", "未"):
                            common_signal += 46.0
                    elif (
                        _is_noun_pos(pos_tag)
                        and usage_score < 0.20
                        and jieba_direct_score < 0.18
                        and source_hits < 3
                    ):
                        common_signal -= 18.0
                elif _is_conversational_pos(pos_tag):
                    common_signal += 28.0
                elif char_score >= 0.50:
                    common_signal += 16.0
                if daily_phrase_support:
                    common_signal += 96.0 if text_len <= 2 else 40.0
                    if _is_conversational_pos(pos_tag):
                        common_signal += 36.0 if text_len <= 2 else 16.0
                if daily_number_support:
                    common_signal += 84.0 if text_len <= 2 else 52.0
            common_signal_scores[text] = common_signal
            if common_signal > bucket_dominant_common_signal:
                bucket_dominant_common_runner_up = bucket_dominant_common_signal
                bucket_dominant_common_signal = common_signal
                bucket_dominant_common_text = text
            elif common_signal > bucket_dominant_common_runner_up:
                bucket_dominant_common_runner_up = common_signal

            raw_scores[text] = (
                usage_score * 220.0
                + jieba_direct_score * 220.0
                + min(source_hits, 4) * 22.0
                + pageview_score * 40.0
                + wiki_hit * 12.0
                + family_support_score * (104.0 if not has_robust_usage else 76.0)
                + char_score * char_weight
                + pos_bias * 190.0
                + float(semantic_bonus) * 0.55
                + (weight / 1000.0) * 14.0
                + (76.0 if (daily_phrase_support and text_len <= 2) else 24.0 if daily_phrase_support else 0.0)
                + (36.0 if (daily_number_support and text_len <= 2) else 22.0 if daily_number_support else 0.0)
                - float(
                    _compute_style_ranking_penalty(
                        term_style_penalty_map.get((pinyin, text), 0)
                    )
                )
            )
            if text_len >= 4 and pageview_score < 0.18:
                contains_strong_head = any(
                    shorter != text
                    and (text.startswith(shorter) or text.endswith(shorter))
                    and (_cjk_len(text) - _cjk_len(shorter) >= 2)
                    for shorter in strong_short_head_terms
                )
                if contains_strong_head:
                    raw_scores[text] -= 64.0

        raw_values = list(raw_scores.values())
        min_raw = min(raw_values)
        max_raw = max(raw_values)
        spread = max_raw - min_raw
        if spread <= 1e-6:
            continue

        spread_factor = min(1.0, spread / 240.0)
        bucket_dominant_common_margin = 0.0
        if bucket_dominant_common_text:
            bucket_dominant_common_margin = max(
                0.0, bucket_dominant_common_signal - max(0.0, bucket_dominant_common_runner_up)
            )
            dominant_usage_score = min(
                1.0, max(0.0, usage_score_map.get(bucket_dominant_common_text, 0.0))
            )
            dominant_source_hits = max(0, source_hits_map.get(bucket_dominant_common_text, 0))
            dominant_pageview_score = min(
                1.0, max(0.0, pageviews_signal_map.get(bucket_dominant_common_text, 0.0))
            )
            dominant_jieba_direct_score = min(
                1.0,
                max(0.0, jieba_direct_signal_map.get(bucket_dominant_common_text, 0.0)),
            )
            dominant_wiki_support = _has_effective_wiki_support(
                bucket_dominant_common_text,
                wiki_titles,
                pageview_score=dominant_pageview_score,
                source_hits=dominant_source_hits,
                wiki_augmented_terms=wiki_augmented_terms,
            )
            if (
                bucket_dominant_common_margin < 42.0
                or (
                    dominant_usage_score < 0.08
                    and dominant_jieba_direct_score < 0.08
                    and dominant_source_hits < 2
                    and dominant_pageview_score < 0.05
                    and not dominant_wiki_support
                )
            ):
                bucket_dominant_common_text = ""
                bucket_dominant_common_margin = 0.0

        for text, weight in items:
            text_len = _cjk_len(text)
            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            source_hits = max(0, source_hits_map.get(text, 0))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            family_support_score = min(
                1.0,
                max(0.0, edge_family_support.get((pinyin, text), 0.0) / 900.0),
            )
            pos_tag = jieba_pos_map.get(text, "")
            semantic_bonus = term_semantic_bonus_map.get((pinyin, text), 0)
            supplement_exact_support = (
                text in weak_leader_terms
                and 2 <= text_len <= 4
                and not _is_pure_daily_number_word(text)
                and (
                    usage_score >= 0.18
                    or source_hits >= 1
                    or jieba_direct_score >= 0.08
                )
            )
            semantic_daily_support = (
                text_len <= 3
                and semantic_bonus >= 120
                and not _is_named_entity_pos(pos_tag)
            )
            wiki_support = _has_effective_wiki_support(
                text,
                wiki_titles,
                pageview_score=pageview_score,
                source_hits=source_hits,
                wiki_augmented_terms=wiki_augmented_terms,
            )
            looks_like_person_name = _looks_like_low_signal_person_name(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
            )
            looks_like_place_name = _looks_like_low_signal_place_name(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
            )
            char_score = _compute_text_single_char_prior(text, char_prior)
            min_char_prior = _compute_min_char_prior(text, char_prior)
            daily_phrase_support = _is_daily_phrase_candidate(
                text,
                text_len=text_len,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
                char_score=char_score,
                wiki_augmented_terms=wiki_augmented_terms,
                preferred_terms=preferred_terms,
            )
            if semantic_daily_support:
                daily_phrase_support = True
            if supplement_exact_support:
                daily_phrase_support = True
            short_everyday_support = _is_short_everyday_term_candidate(
                text,
                text_len=text_len,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                pos_tag=pos_tag,
                char_score=char_score,
            )
            if semantic_daily_support and text_len <= 2:
                short_everyday_support = True
            if supplement_exact_support and text_len <= 2:
                short_everyday_support = True
            daily_number_support = _is_daily_number_word_candidate(
                text,
                text_len=text_len,
                usage_score=usage_score,
                source_hits=source_hits,
                pos_tag=pos_tag,
            )
            looks_like_literary_term = _looks_like_low_signal_literary_term(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
                char_score=char_score,
            )
            looks_like_written_tail_term = _looks_like_low_signal_written_tail_term(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
                char_score=char_score,
            )
            pos_bias = _compute_effective_pos_bias(
                pos_tag=pos_tag,
                text_len=text_len,
                usage_score=usage_score,
                jieba_direct_score=jieba_direct_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                char_score=char_score,
            )
            normalized = (raw_scores[text] - min_raw) / spread
            delta_cap = c_max_delta
            if not has_robust_usage:
                delta_cap = min(delta_cap, 96)
            if bucket_dominant_common_text:
                delta_cap += min(140, int(round(bucket_dominant_common_margin * 0.60)))
            delta = int(round((normalized - 0.5) * (2 * delta_cap) * spread_factor))
            post_cap_bonus = 0

            if bucket_direct_leader_active:
                if text == bucket_direct_leader_text:
                    direct_leader_boost = min(
                        150,
                        42 + int(round(bucket_direct_leader_margin * 260.0)),
                    )
                    delta += direct_leader_boost
                    post_cap_bonus += min(
                        72,
                        20 + int(round(bucket_direct_leader_margin * 180.0)),
                    )
                elif (
                    text_len <= 3
                    and not wiki_support
                    and not _is_named_entity_pos(pos_tag)
                    and jieba_direct_score + 0.18 < bucket_direct_leader_jieba
                    and usage_score <= bucket_direct_leader_usage + 0.05
                    and pageview_score <= bucket_direct_leader_pageview + 0.08
                    and source_hits <= bucket_direct_leader_source_hits + 1
                ):
                    direct_leader_damp = min(
                        118,
                        26 + int(round(bucket_direct_leader_margin * 220.0)),
                    )
                    delta -= direct_leader_damp
                    post_cap_bonus -= min(
                        72,
                        18 + int(round(bucket_direct_leader_margin * 160.0)),
                    )

            if text == bucket_dominant_common_text:
                dominant_common_boost = min(
                    168,
                    28 + int(round(bucket_dominant_common_margin * 0.75)),
                )
                if text_len <= 2:
                    dominant_common_boost += 22
                if (
                    usage_score >= 0.18
                    or jieba_direct_score >= 0.18
                    or pageview_score >= 0.10
                    or source_hits >= 2
                    or wiki_support
                ):
                    dominant_common_boost += 18
                delta += dominant_common_boost
                if (
                    text_len <= 2
                    and daily_phrase_support
                    and bucket_dominant_common_margin >= 96.0
                ):
                    post_cap_bonus += 44
                    if short_everyday_support:
                        post_cap_bonus += 40 + min(
                            24, int(round(jieba_direct_score * 42.0))
                        )
                stats[f"{stats_prefix}_homophone_dominant_common_boosted"] += 1
            elif (
                bucket_dominant_common_text
                and text_len <= 3
                and not wiki_support
                and common_signal_scores.get(text, 0.0) + 44.0 < bucket_dominant_common_signal
                and usage_score < 0.14
                and jieba_direct_score < 0.12
                and source_hits <= 1
                and pageview_score < 0.05
            ):
                dominant_common_damp = min(
                    118,
                    20 + int(round(bucket_dominant_common_margin * 0.55)),
                )
                delta -= dominant_common_damp
                stats[f"{stats_prefix}_homophone_dominant_common_damped"] += 1

            if (
                bucket_has_strong_term
                and usage_score < 0.05
                and jieba_direct_score < 0.04
                and source_hits <= 0
                and pageview_score <= 0.0
                and not wiki_support
            ):
                delta -= c_sparse_penalty
                stats[f"{stats_prefix}_homophone_sparse_penalized"] += 1
            elif (
                bucket_has_strong_term
                and usage_score < 0.10
                and jieba_direct_score < 0.10
                and source_hits <= 1
                and pageview_score <= 0.02
                and not wiki_support
            ):
                delta -= c_weak_signal_penalty

            if (
                bucket_has_strong_term
                and text_len <= 3
                and usage_score < 0.08
                and jieba_direct_score < 0.02
                and source_hits <= 1
                and pageview_score <= 0.01
                and not wiki_support
                and min_char_prior < 0.16
            ):
                delta -= c_rare_form_penalty
                stats[f"{stats_prefix}_homophone_rare_form_penalized"] += 1

            if (
                bucket_has_strong_term
                and text_len == 2
                and not daily_phrase_support
                and not short_everyday_support
                and not semantic_daily_support
                and not _is_named_entity_pos(pos_tag)
                and usage_score < 0.20
                and jieba_direct_score < 0.18
                and source_hits <= 2
                and pageview_score < 0.06
                and not wiki_support
                and min_char_prior < 0.12
                and char_score < 0.62
                and (
                    common_signal_scores.get(text, 0.0) + 80.0
                    < bucket_dominant_common_signal
                )
            ):
                # A common head character can make a rare two-character term look
                # deceptively strong. In an exact homophone bucket, keep such
                # entries visible but below the better supported daily term.
                delta -= 112
                stats[f"{stats_prefix}_homophone_rare_char_short_damped"] += 1

            inflated_short_penalty = _compute_low_signal_inflated_short_term_penalty(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
                char_score=char_score,
                min_char_prior=min_char_prior,
            )
            if inflated_short_penalty > 0:
                delta -= inflated_short_penalty
                stats[f"{stats_prefix}_homophone_inflated_short_penalized"] += 1

            modernity_risk = _compute_low_signal_modernity_risk(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
                char_score=char_score,
                min_char_prior=min_char_prior,
                looks_like_person_name=looks_like_person_name,
                looks_like_place_name=looks_like_place_name,
                looks_like_literary_term=looks_like_literary_term,
                looks_like_written_tail_term=looks_like_written_tail_term,
            )
            if (
                bucket_has_strong_term
                and modernity_risk >= 150
                and usage_score < 0.18
                and jieba_direct_score < 0.14
                and source_hits <= 1
                and pageview_score < 0.04
                and not wiki_support
            ):
                delta -= min(132, 28 + modernity_risk // 3)
                stats[f"{stats_prefix}_homophone_modernity_risk_penalized"] += 1
            elif (
                bucket_has_strong_term
                and text_len <= 2
                and modernity_risk >= 120
                and usage_score < 0.12
                and jieba_direct_score < 0.08
                and source_hits <= 1
                and pageview_score < 0.03
                and not wiki_support
            ):
                delta -= min(86, 18 + modernity_risk // 4)
                stats[f"{stats_prefix}_homophone_modernity_risk_penalized"] += 1

            style_penalty = term_style_penalty_map.get((pinyin, text), 0)
            if style_penalty > 0:
                delta -= _compute_style_ranking_penalty(style_penalty)

            if (
                bucket_has_strong_term
                and text_len <= 2
                and pos_bias <= -0.12
                and usage_score < 0.30
                and jieba_direct_score < 0.32
                and source_hits <= 1
            ):
                delta -= c_named_entity_penalty
            elif (
                bucket_has_strong_term
                and text_len <= 3
                and _is_named_entity_pos(pos_tag)
                and source_hits <= 2
                and pageview_score < 0.08
                and jieba_direct_score < 0.10
                and usage_score < 0.48
            ):
                # Suppress low-traffic short names/places in homophone buckets.
                delta -= 96
            if looks_like_place_name:
                delta -= 84
            elif looks_like_literary_term:
                delta -= c_literary_penalty
                stats[f"{stats_prefix}_homophone_literary_penalized"] += 1
            elif looks_like_written_tail_term:
                delta -= 68
                stats[f"{stats_prefix}_homophone_written_tail_penalized"] += 1
            elif (
                bucket_has_strong_term
                and text_len <= 2
                and pos_bias >= 0.10
                and (usage_score >= 0.10 or jieba_direct_score >= 0.14 or char_score >= 0.62)
            ):
                delta += 34
            elif (
                bucket_has_strong_term
                and text_len <= 2
                and not _is_named_entity_pos(pos_tag)
                and char_score >= 0.56
                and (usage_score >= 0.08 or jieba_direct_score >= 0.10 or source_hits >= 2)
            ):
                delta += 30

            if (
                bucket_has_strong_term
                and text_len <= 3
                and pos_bias <= -0.20
                and usage_score < 0.18
                and jieba_direct_score < 0.12
                and source_hits <= 1
                and pageview_score <= 0.04
                and not wiki_support
            ):
                delta -= 42

            if (
                bucket_has_strong_term
                and count_measure_support
                and usage_score < 0.16
                and jieba_direct_score < 0.18
                and pageview_score < 0.05
            ):
                delta -= 96

            if (
                bucket_has_strong_term
                and text_len <= 2
                and not _is_named_entity_pos(pos_tag)
                and _is_conversational_pos(pos_tag)
                and char_score >= 0.38
                and (usage_score >= 0.06 or jieba_direct_score >= 0.08 or source_hits >= 2)
            ):
                # Favor short modern verb/adj/functional terms over literary or
                # low-signal homophones when the bucket already has a strong term.
                delta += 28
            elif (
                bucket_has_strong_term
                and text_len <= 2
                and _is_noun_pos(pos_tag)
                and not _is_named_entity_pos(pos_tag)
                and char_score < 0.46
                and usage_score < 0.10
                and jieba_direct_score < 0.08
                and source_hits <= 1
                and pageview_score <= 0.02
                and not wiki_support
            ):
                delta -= 24

            if (
                not has_robust_usage
                and bucket_has_family_term
                and text_len <= 3
                and family_support_score < 0.10
                and char_score < 0.58
            ):
                delta -= 36

            if (
                not has_robust_usage
                and text_len <= 3
                and family_support_score >= 0.34
            ):
                delta += 34

            if bucket_has_daily_phrase_term:
                if daily_phrase_support:
                    if text_len <= 2:
                        delta += 76 if _is_conversational_pos(pos_tag) else 58
                    else:
                        delta += 28 if _is_conversational_pos(pos_tag) else 18
                    if short_everyday_support:
                        short_everyday_boost = (
                            128 if _is_conversational_pos(pos_tag) else 96
                        )
                        short_everyday_boost += min(
                            64, int(round(jieba_direct_score * 96.0))
                        )
                        delta += short_everyday_boost
                        stats[f"{stats_prefix}_homophone_short_everyday_boosted"] += 1
                    stats[f"{stats_prefix}_homophone_daily_phrase_boosted"] += 1
                elif (
                    text_len <= 3
                    and not _is_named_entity_pos(pos_tag)
                    and not wiki_support
                    and usage_score < 0.10
                    and jieba_direct_score < 0.10
                    and source_hits <= 1
                    and pageview_score < 0.04
                    and not _is_conversational_pos(pos_tag)
                ):
                    delta -= 24 if text_len <= 2 else 16
                    stats[f"{stats_prefix}_homophone_daily_phrase_damped"] += 1
                elif (
                    text_len <= 2
                    and not _is_named_entity_pos(pos_tag)
                    and not _is_conversational_pos(pos_tag)
                    and not wiki_support
                    and source_hits <= 1
                    and usage_score < 0.18
                    and jieba_direct_score < 0.14
                    and pageview_score < 0.10
                ):
                    delta -= 96
                    stats[f"{stats_prefix}_homophone_daily_phrase_short_non_daily_damped"] += 1

            if (
                bucket_has_short_everyday_term
                and not short_everyday_support
                and text_len <= 2
                and _is_noun_pos(pos_tag)
                and not _is_named_entity_pos(pos_tag)
                and not daily_phrase_support
                and usage_score < 0.30
                and jieba_direct_score < 0.12
                and source_hits <= 3
                and pageview_score < 0.10
            ):
                delta -= 84
                stats[f"{stats_prefix}_homophone_short_everyday_non_daily_damped"] += 1

            if (
                bucket_has_short_everyday_term
                and text_len <= 2
                and _is_noun_pos(pos_tag)
                and not _is_named_entity_pos(pos_tag)
                and not daily_phrase_support
                and not short_everyday_support
                and family_support_score >= 0.24
                and usage_score < 0.22
                and jieba_direct_score < 0.18
                and pageview_score < 0.12
                and not wiki_support
            ):
                delta -= 72
                stats[
                    f"{stats_prefix}_homophone_short_everyday_non_daily_damped"
                ] += 1

            if (
                bucket_has_short_everyday_term
                and text_len <= 2
                and _is_noun_pos(pos_tag)
                and not _is_named_entity_pos(pos_tag)
                and not daily_phrase_support
                and not short_everyday_support
                and family_support_score >= 0.18
                and usage_score < 0.24
                and jieba_direct_score < 0.20
                and pageview_score < 0.12
                and not wiki_support
            ):
                # Edge-family support mostly says "this is a valid domain head"
                # (for example medical/technical terms), not that it is a
                # high-priority daily input target. In a same-pinyin bucket with
                # an everyday short term, keep such nouns below broadly supported
                # conversational/verb candidates unless they have their own
                # broad frequency evidence.
                delta -= 72
                stats[f"{stats_prefix}_homophone_short_family_noun_damped"] += 1

            if (
                bucket_has_short_everyday_term
                and text_len <= 2
                and _is_noun_pos(pos_tag)
                and not _is_named_entity_pos(pos_tag)
                and not daily_phrase_support
                and not short_everyday_support
                and usage_score < 0.22
                and jieba_direct_score < 0.18
                and pageview_score < 0.16
                and (
                    common_signal_scores.get(text, 0.0) + 72.0 < bucket_dominant_common_signal
                    or family_support_score >= 0.18
                    or char_score < 0.58
                    or (source_hits <= 2 and not wiki_support)
                )
            ):
                # Family/prefix support says "valid term", not "daily default".
                # In buckets that already contain a well-supported short everyday
                # candidate, keep low-direct-evidence short nouns discoverable
                # without letting them crowd common functional words.
                delta -= 168
                stats[f"{stats_prefix}_homophone_short_everyday_weak_noun_damped"] += 1

            if (
                text_len <= 2
                and wiki_support
                and pageview_score >= 0.12
                and usage_score >= 0.30
            ):
                delta += 160
                stats[f"{stats_prefix}_homophone_short_popular_wiki_boosted"] += 1

            if (
                bucket_has_short_popular_named_term
                and text_len <= 2
                and not _is_named_entity_pos(pos_tag)
                and not daily_phrase_support
                and not short_everyday_support
                and usage_score < 0.24
                and jieba_direct_score < 0.16
                and pageview_score < 0.08
                and family_support_score < 0.48
            ):
                delta -= 76
                stats[
                    f"{stats_prefix}_homophone_short_popular_named_bucket_damped"
                ] += 1

            if bucket_has_daily_number_term and daily_number_support:
                delta += 28 if text_len <= 2 else 18
                stats[f"{stats_prefix}_homophone_daily_number_boosted"] += 1

            if semantic_daily_support:
                delta += min(220, 72 + semantic_bonus)
                post_cap_bonus += min(120, semantic_bonus // 2)
                stats[f"{stats_prefix}_homophone_semantic_daily_boosted"] += 1

            if bucket_has_preferred_term:
                if text in preferred_terms and usage_score >= 0.90:
                    delta += 24 if text_len <= 2 else 14
                    stats[f"{stats_prefix}_homophone_preferred_term_boosted"] += 1
                elif text_len <= 3:
                    # Curated daily terms are an explicit product preference.
                    # In the same homophone bucket, short non-curated terms
                    # should yield unless they are also manually promoted.
                    delta -= 96 if text_len <= 2 else 44
                    stats[f"{stats_prefix}_homophone_preferred_term_damped"] += 1

            supplement_competitor_cap = 0
            if (
                bucket_has_supplement_exact_term
                and not supplement_exact_support
                and text_len <= 3
                and bucket_supplement_exact_weight > 0
                and pos_tag.startswith("t")
                and wiki_support
                and pageview_score >= 0.12
                and usage_score >= 0.20
                and jieba_direct_score < 0.35
            ):
                # A pageview-heavy historical/time-label term is a valid exact
                # entry, but it should not be boosted above an explicitly
                # curated daily supplement in the same homophone bucket.
                supplement_competitor_cap = max(1, bucket_supplement_exact_weight - 24)

            if bucket_has_conversational_short_term and text_len <= 2:
                # Keep conversational preference as a mild tiebreaker only.
                # The old ±300~400 forcing was too aggressive and could demote
                # common nouns (for example "世界") below rare conversational forms.
                if _is_conversational_pos(pos_tag):
                    if usage_score >= 0.10 or jieba_direct_score >= 0.14 or source_hits >= 2:
                        delta += 48
                    elif usage_score >= 0.04 or jieba_direct_score >= 0.06:
                        delta += 24
                elif _is_noun_pos(pos_tag):
                    if (
                        usage_score < 0.06
                        and jieba_direct_score < 0.08
                        and source_hits <= 1
                        and pageview_score <= 0.02
                        and not wiki_support
                    ):
                        delta -= 44
                    elif (
                        usage_score < 0.28
                        and jieba_direct_score < 0.65
                        and source_hits <= 1
                        and pageview_score <= 0.02
                        and not wiki_support
                    ):
                        delta -= 56
                    elif (
                        usage_score < 0.16
                        and jieba_direct_score < 0.20
                        and source_hits <= 2
                        and pageview_score < 0.10
                        and not (
                            char_score >= 0.76
                            and (usage_score >= 0.10 or jieba_direct_score >= 0.12)
                        )
                    ):
                        delta -= 36
                    elif (
                        char_score >= 0.58
                        and (usage_score >= 0.08 or jieba_direct_score >= 0.10 or source_hits >= 2)
                    ):
                        delta += 20

            if (
                bucket_has_conversational_short_term
                and text_len <= 2
                and _is_noun_pos(pos_tag)
                and not _is_named_entity_pos(pos_tag)
                and family_support_score >= 0.42
                and jieba_direct_score < 0.12
                and usage_score < 0.30
                and pageview_score < 0.05
            ):
                # Phrase-family support often marks domain heads as valid
                # (medical/technical nouns), but it should not make them the
                # default over a same-pinyin conversational/function word.
                post_cap_bonus -= 300
                stats[f"{stats_prefix}_homophone_conversational_family_noun_damped"] += 1

            if text_len == 1:
                audited_reading_delta = SINGLE_CHAR_READING_DELTA_OVERRIDES.get((text, pinyin), 0)
                if audited_reading_delta < 0:
                    # Keep audited rare-reading penalties alive after homophone
                    # reranking, so later conversational boosts cannot undo
                    # earlier single-character reading correction.
                    delta += int(round(audited_reading_delta * 0.55))

            if (
                text_len <= 2
                and _is_conversational_pos(pos_tag)
                and text
                and text[0] in ("不", "没", "无", "非", "未")
                and (usage_score >= 0.12 or jieba_direct_score >= 0.10 or char_score >= 0.75)
            ):
                delta += 90

            if bucket_has_strong_term:
                if jieba_direct_score >= 0.70 and usage_score >= 0.16:
                    delta += 32
                elif jieba_direct_score >= 0.50 and usage_score >= 0.12:
                    delta += 16

            if delta > delta_cap:
                delta = delta_cap
            elif delta < -delta_cap:
                delta = -delta_cap
            delta += post_cap_bonus

            new_weight = max(1, min(1000, weight + delta))
            if supplement_exact_support:
                supplement_floor = min(
                    max(1, min(1000, int(weight))),
                    CURATED_DAILY_SUPPLEMENT_WEIGHT_CAP,
                )
                if new_weight < supplement_floor:
                    new_weight = supplement_floor
                    stats[f"{stats_prefix}_homophone_supplement_exact_protected"] += 1
            elif supplement_competitor_cap > 0 and new_weight > supplement_competitor_cap:
                new_weight = supplement_competitor_cap
                stats[
                    f"{stats_prefix}_homophone_supplement_exact_competitor_capped"
                ] += 1
            if delta == 0 and new_weight == weight:
                continue
            if new_weight == weight:
                continue

            mapping[(pinyin, text)] = new_weight
            stats[f"{stats_prefix}_homophone_entries_adjusted"] += 1
            if new_weight > weight:
                stats[f"{stats_prefix}_homophone_entries_boosted"] += 1
            else:
                stats[f"{stats_prefix}_homophone_entries_damped"] += 1

    return stats


def _promote_negated_predicate_homophone_terms(
    mapping: Dict[Tuple[str, str], int],
    term_semantic_bonus_map: Dict[Tuple[str, str], int] | None,
    stats_prefix: str,
) -> Dict[str, int]:
    """Prefer high-confidence negated predicate words over same-pinyin nouns.

    Words such as "不行" are daily predicates, while same-pinyin terms such as
    "步行" are valid but less likely as the default exact bucket target. The
    semantic gate comes from CEDICT definitions, so this stays a class rule
    rather than an item-specific exception.
    """
    stats = {
        f"{stats_prefix}_negated_predicate_buckets": 0,
        f"{stats_prefix}_negated_predicate_promoted": 0,
        f"{stats_prefix}_negated_predicate_competitors_capped": 0,
    }
    if not mapping:
        return stats

    term_semantic_bonus_map = term_semantic_bonus_map or {}
    buckets: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        buckets.setdefault(pinyin, []).append((text, weight))

    def is_negated_predicate(key: Tuple[str, str]) -> bool:
        _pinyin, text = key
        return (
            _cjk_len(text) == 2
            and text.startswith(("不", "没", "無", "无", "非", "未"))
            and term_semantic_bonus_map.get(key, 0) >= 300
        )

    for pinyin, items in buckets.items():
        if len(items) < 2:
            continue
        protected = [
            (text, weight)
            for text, weight in items
            if is_negated_predicate((pinyin, text))
        ]
        if not protected:
            continue

        best_competitor_weight = max(
            (weight for text, weight in items if not is_negated_predicate((pinyin, text))),
            default=0,
        )
        target_weight = min(1000, max(880, best_competitor_weight + 72))
        competitor_cap = max(620, target_weight - 160)
        touched = False

        for text, weight in protected:
            key = (pinyin, text)
            if weight < target_weight:
                mapping[key] = target_weight
                stats[f"{stats_prefix}_negated_predicate_promoted"] += 1
                touched = True

        for text, weight in items:
            key = (pinyin, text)
            if is_negated_predicate(key):
                continue
            if weight > competitor_cap:
                mapping[key] = competitor_cap
                stats[f"{stats_prefix}_negated_predicate_competitors_capped"] += 1
                touched = True

        if touched:
            stats[f"{stats_prefix}_negated_predicate_buckets"] += 1

    return stats


def _cap_short_domain_terms_against_direct_common(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    wiki_augmented_terms: Set[str] | None,
    jieba_direct_signal_map: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    char_frequency_prior: Dict[str, float] | None,
    preferred_terms: Set[str] | None,
    stats_prefix: str,
    weak_leader_terms: Set[str] | None = None,
) -> Dict[str, int]:
    """Keep wiki/family-supported short domain nouns below direct common terms.

    Wiki titles and edge-family support are good visibility signals, but they
    are not enough evidence that a short term should become the default in an
    exact homophone bucket. This pass caps those terms after the general
    homophone reranker so they stay selectable without crowding common words.
    """
    stats = {
        f"{stats_prefix}_short_domain_buckets": 0,
        f"{stats_prefix}_short_domain_capped": 0,
    }
    if not mapping:
        return stats

    wiki_augmented_terms = wiki_augmented_terms or set()
    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    preferred_terms = preferred_terms or set()
    weak_leader_terms = weak_leader_terms or set()
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    edge_family_support = _build_edge_family_support_for_terms(mapping)

    buckets: Dict[str, List[Tuple[str, int]]] = {}
    for key, weight in mapping.items():
        pinyin, text = key
        buckets.setdefault(pinyin, []).append((text, weight))

    for pinyin, items in buckets.items():
        if len(items) < 2:
            continue

        metrics: Dict[str, Tuple[float, float, float, int, float, float, str, bool]] = {}
        leader_text = ""
        leader_signal = -1.0
        leader_runner_up = -1.0
        for text, _weight in items:
            if text in weak_leader_terms:
                continue
            text_len = _cjk_len(text)
            if text_len <= 0 or text_len > 3:
                continue
            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            source_hits = max(0, source_hits_map.get(text, 0))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            jieba_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            char_score = _compute_text_single_char_prior(text, char_prior)
            family_score = min(
                1.0,
                max(0.0, edge_family_support.get((pinyin, text), 0.0) / 900.0),
            )
            pos_tag = jieba_pos_map.get(text, "")
            wiki_support = _has_effective_wiki_support(
                text,
                wiki_titles,
                pageview_score=pageview_score,
                source_hits=source_hits,
                wiki_augmented_terms=wiki_augmented_terms,
            )
            direct_signal = (
                jieba_score * 0.68
                + usage_score * 0.18
                + pageview_score * 0.04
                + min(source_hits, 3) * 0.012
                + char_score * 0.04
            )
            if _is_conversational_pos(pos_tag):
                direct_signal += 0.08
            elif _is_noun_pos(pos_tag):
                direct_signal += 0.015
            if char_score >= 0.64:
                direct_signal += 0.015
            if _is_named_entity_pos(pos_tag):
                direct_signal *= 0.72

            metrics[text] = (
                direct_signal,
                usage_score,
                jieba_score,
                source_hits,
                pageview_score,
                family_score,
                pos_tag,
                wiki_support,
            )
            if direct_signal > leader_signal:
                leader_runner_up = leader_signal
                leader_signal = direct_signal
                leader_text = text
            elif direct_signal > leader_runner_up:
                leader_runner_up = direct_signal

        if not leader_text:
            continue
        leader_margin = leader_signal - max(0.0, leader_runner_up)
        if leader_signal < 0.12 or leader_margin < 0.035:
            continue
        leader_weight = mapping.get((pinyin, leader_text), 0)
        if leader_weight <= 0:
            continue

        bucket_touched = False
        for text, weight in items:
            if text == leader_text or text in preferred_terms or text in weak_leader_terms:
                continue
            text_len = _cjk_len(text)
            if text_len < 2 or text_len > 3:
                continue
            metric = metrics.get(text)
            if metric is None:
                continue
            (
                direct_signal,
                usage_score,
                jieba_score,
                source_hits,
                pageview_score,
                family_score,
                pos_tag,
                wiki_support,
            ) = metric
            if _is_conversational_pos(pos_tag) or _is_named_entity_pos(pos_tag):
                continue
            has_visibility_only_signal = (
                wiki_support
                or family_score >= 0.18
                or (source_hits >= 2 and usage_score < 0.12 and jieba_score < 0.12)
            )
            has_strong_direct_signal = (
                jieba_score >= 0.22
                or (usage_score >= 0.24 and jieba_score >= 0.08)
                or (pageview_score >= 0.18 and jieba_score >= 0.12)
                or (source_hits >= 4 and jieba_score >= 0.10)
            )
            if not has_visibility_only_signal or has_strong_direct_signal:
                continue
            if direct_signal + 0.045 >= leader_signal:
                continue
            if weight <= leader_weight - 48:
                continue

            cap_margin = 64 + min(160, int(round((leader_signal - direct_signal) * 360.0)))
            cap = max(1, leader_weight - cap_margin)
            if weight > cap:
                mapping[(pinyin, text)] = cap
                stats[f"{stats_prefix}_short_domain_capped"] += 1
                bucket_touched = True

        if bucket_touched:
            stats[f"{stats_prefix}_short_domain_buckets"] += 1

    return stats


def _cap_low_signal_competitors_against_direct_leaders(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    preferred_terms: Set[str],
    weak_leader_terms: Set[str],
    stats_prefix: str,
    bucket_pinyin_map: Dict[Tuple[str, str], str] | None = None,
    term_semantic_bonus_map: Dict[Tuple[str, str], int] | None = None,
    term_style_penalty_map: Dict[Tuple[str, str], int] | None = None,
) -> Dict[str, int]:
    """Keep low-signal exact competitors below stronger same-pinyin direct terms."""
    stats = {
        f"{stats_prefix}_low_signal_competitors_capped": 0,
        f"{stats_prefix}_low_signal_competitor_buckets": 0,
    }
    if not mapping:
        return stats

    support_index = _build_longer_prefix_term_support_index(mapping)
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    bucket_pinyin_map = bucket_pinyin_map or {}
    term_semantic_bonus_map = term_semantic_bonus_map or {}
    term_style_penalty_map = term_style_penalty_map or {}
    semantic_bonus_by_text: Dict[str, int] = {}
    for (_pinyin, text), bonus in term_semantic_bonus_map.items():
        if bonus <= 0:
            continue
        previous = semantic_bonus_by_text.get(text, 0)
        if bonus > previous:
            semantic_bonus_by_text[text] = bonus
    buckets: Dict[str, List[Tuple[str, int]]] = {}
    for pinyin, text in mapping.keys():
        bucket_pinyin = bucket_pinyin_map.get((pinyin, text), pinyin)
        if not bucket_pinyin:
            continue
        buckets.setdefault(bucket_pinyin, []).append((text, mapping[(pinyin, text)]))

    def signal_parts(text: str) -> Tuple[float, int, float, float, str, float, bool, bool]:
        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pos_tag = jieba_pos_map.get(text, "")
        char_score = _compute_text_single_char_prior(text, char_prior)
        text_len = _cjk_len(text)
        short_everyday = _is_short_everyday_term_candidate(
            text,
            text_len=text_len,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_score,
            pos_tag=pos_tag,
            char_score=char_score,
        )
        preferred_daily = (
            text in preferred_terms
            and text not in weak_leader_terms
            and usage_score >= 0.50
        )
        return (
            usage_score,
            source_hits,
            pageview_score,
            jieba_score,
            pos_tag,
            char_score,
            short_everyday,
            preferred_daily,
        )

    def direct_signal(text: str) -> float:
        (
            usage_score,
            source_hits,
            pageview_score,
            jieba_score,
            _pos_tag,
            _char_score,
            short_everyday,
            preferred_daily,
        ) = signal_parts(text)
        signal = (
            usage_score * 0.42
            + jieba_score * 0.36
            + pageview_score * 0.14
            + min(1.0, source_hits / 6.0) * 0.08
        )
        if short_everyday:
            signal += 0.16
        if preferred_daily:
            signal += 0.18
        semantic_bonus = semantic_bonus_by_text.get(text, 0)
        if semantic_bonus >= 120:
            signal += min(0.18, semantic_bonus / 1200.0)
        return min(1.0, signal)

    for pinyin, items in buckets.items():
        direct_items: List[Tuple[str, int, float]] = []
        for text, weight in items:
            text_len = _cjk_len(text)
            if (
                text_len < 2
                or text_len > 4
                or _is_pure_daily_number_word(text)
                or text in weak_leader_terms
            ):
                continue

            (
                usage_score,
                source_hits,
                _pageview_score,
                jieba_score,
                pos_tag,
                _char_score,
                _short_everyday,
                _preferred_daily,
            ) = signal_parts(text)
            # Styled CEDICT senses (variants, dialect/literary terms, geographic
            # proper names) are visibility signals. They should stay selectable
            # but must not become "direct leaders" that suppress ordinary exact
            # homophones such as 亮光 below 两广.
            if term_style_penalty_map.get((pinyin, text), 0) >= 80:
                continue
            # Jieba occasionally marks ordinary words as place/name POS. Keep
            # the named-entity guard for weak direct evidence, but do not block
            # clearly frequent words from becoming the bucket's direct leader.
            if _is_named_entity_pos(pos_tag) and not (
                usage_score >= 0.16
                or jieba_score >= 0.18
                or (usage_score >= 0.12 and source_hits >= 2)
            ):
                continue

            direct_items.append((text, weight, direct_signal(text)))
        direct_items = [
            (text, weight, signal)
            for text, weight, signal in direct_items
            if signal >= 0.12
        ]
        if not direct_items:
            continue

        leader_text, leader_weight, leader_signal = max(
            direct_items, key=lambda item: (item[2], item[1])
        )
        if leader_weight < 300 or leader_signal < 0.12:
            continue

        (
            leader_usage_score,
            leader_source_hits,
            leader_pageview_score,
            leader_jieba_score,
            leader_pos_tag,
            _leader_char_score,
            leader_short_everyday,
            leader_preferred_daily,
        ) = signal_parts(leader_text)
        leader_is_daily_like = (
            leader_short_everyday
            or leader_preferred_daily
            or semantic_bonus_by_text.get(leader_text, 0) >= 120
            or (
                _is_conversational_pos(leader_pos_tag)
                and (
                    leader_jieba_score >= 0.18
                    or leader_usage_score >= 0.16
                    or leader_source_hits >= 2
                    or leader_pageview_score >= 0.08
                )
            )
        )

        bucket_touched = False
        for text, weight in items:
            text_len = _cjk_len(text)
            if (
                text == leader_text
                or text_len < 2
                or text_len > 3
                or _is_pure_daily_number_word(text)
                or text in weak_leader_terms
            ):
                continue
            if text_len == 2 and len(text) == 2 and text[0] == text[1]:
                continue
            if weight <= leader_weight - 64:
                continue

            (
                usage_score,
                source_hits,
                pageview_score,
                jieba_score,
                pos_tag,
                _char_score,
                short_everyday,
                preferred_daily,
            ) = signal_parts(text)
            if (
                _is_conversational_pos(pos_tag)
                and (jieba_score >= 0.14 or pageview_score >= 0.08 or source_hits >= 4)
            ):
                continue
            if preferred_daily:
                continue
            if semantic_bonus_by_text.get(text, 0) >= 120:
                continue
            short_everyday_yields_to_daily_leader = (
                short_everyday
                and leader_is_daily_like
                and _is_noun_pos(pos_tag)
                and not _is_conversational_pos(pos_tag)
                and source_hits <= 3
                and pageview_score < 0.12
                and jieba_score + 0.08 < leader_jieba_score
                and usage_score <= leader_usage_score + 0.08
            )
            effective_short_everyday = short_everyday and not short_everyday_yields_to_daily_leader
            if effective_short_everyday and (
                jieba_score >= 0.12
                or pageview_score >= 0.08
                or (usage_score >= 0.18 and source_hits >= 4)
            ):
                continue

            signal = direct_signal(text)
            support_count, support_total = _longer_prefix_term_support_stats(
                pinyin,
                text,
                support_index,
            )
            prefix_fragment = support_count > 0
            productive_action_root = (
                pos_tag.startswith("v")
                and source_hits >= 2
                and support_count >= 12
                and support_total >= 12 * 620
                and jieba_score >= 0.08
            )
            if productive_action_root:
                continue
            strong_independent_signal = (
                usage_score >= 0.30
                or jieba_score >= 0.24
                or pageview_score >= 0.10
                or (
                    source_hits >= 4
                    and (
                        usage_score >= 0.20
                        or jieba_score >= 0.12
                        or pageview_score >= 0.06
                    )
                )
            )
            if _is_named_entity_pos(pos_tag) and strong_independent_signal:
                continue
            if strong_independent_signal:
                continue
            comparable_direct_signal = signal >= max(0.12, leader_signal * 0.82)
            low_independent_signal = (
                usage_score < 0.18
                and jieba_score < 0.16
                and pageview_score < 0.08
                and source_hits <= 2
            )
            weaker_than_leader = signal + 0.10 < leader_signal
            moderate_non_daily_competitor = (
                leader_is_daily_like
                and not effective_short_everyday
                and not preferred_daily
                and not _is_conversational_pos(pos_tag)
                and text_len <= 3
                and source_hits <= 3
                and pageview_score < 0.12
                and jieba_score + 0.08 < leader_jieba_score
                and usage_score <= leader_usage_score + 0.06
                and signal + 0.03 < leader_signal
            )
            if comparable_direct_signal and not prefix_fragment and not moderate_non_daily_competitor:
                continue
            if not (
                low_independent_signal
                or prefix_fragment
                or weaker_than_leader
                or moderate_non_daily_competitor
            ):
                continue

            weak_prefix_fragment = (
                prefix_fragment
                and jieba_score < 0.08
                and pageview_score < 0.04
                and source_hits <= 3
            )
            cap_margin = (
                180
                if low_independent_signal or weak_prefix_fragment
                else 96
                if prefix_fragment or moderate_non_daily_competitor
                else 72
            )
            cap = max(1, leader_weight - cap_margin)
            if low_independent_signal:
                cap = min(cap, 640)
            if weight > cap:
                mapping[(pinyin, text)] = cap
                stats[f"{stats_prefix}_low_signal_competitors_capped"] += 1
                bucket_touched = True

        if bucket_touched:
            stats[f"{stats_prefix}_low_signal_competitor_buckets"] += 1

    return stats


def _cap_short_exact_homophones_by_direct_signal(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float] | None,
    preferred_terms: Set[str],
    weak_leader_terms: Set[str],
    stats_prefix: str,
    bucket_pinyin_map: Dict[Tuple[str, str], str] | None = None,
    term_style_penalty_map: Dict[Tuple[str, str], int] | None = None,
    term_semantic_bonus_map: Dict[Tuple[str, str], int] | None = None,
) -> Dict[str, int]:
    """Keep short exact homophones ordered by direct usage evidence.

    Character priors and longer-compound support make a word valid and visible,
    but they are weak evidence for default exact ranking.  For two-character
    homophones, prefer candidates with stronger direct usage/jieba/pageview/source
    evidence and cap weaker candidates that were inflated mostly by visibility
    signals.
    """
    stats = {
        f"{stats_prefix}_short_exact_direct_signal_buckets": 0,
        f"{stats_prefix}_short_exact_direct_signal_capped": 0,
        f"{stats_prefix}_short_exact_direct_evidence_dominated_capped": 0,
        f"{stats_prefix}_short_exact_direct_signal_restored": 0,
    }
    if not mapping:
        return stats

    bucket_pinyin_map = bucket_pinyin_map or {}
    term_style_penalty_map = term_style_penalty_map or {}
    term_semantic_bonus_map = term_semantic_bonus_map or {}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    support_index = _build_longer_prefix_term_support_index(mapping)

    buckets: Dict[str, List[Tuple[str, str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        bucket_pinyin = bucket_pinyin_map.get((pinyin, text), pinyin)
        if not bucket_pinyin:
            continue
        buckets.setdefault(bucket_pinyin, []).append((pinyin, text, weight))

    def parts(pinyin: str, text: str) -> Tuple[float, float, float, int, str, float, int, int, float, int]:
        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        jieba_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pos_tag = jieba_pos_map.get(text, "")
        char_score = _compute_text_single_char_prior(text, char_prior)
        style_penalty = term_style_penalty_map.get((pinyin, text), 0)
        semantic_bonus = term_semantic_bonus_map.get((pinyin, text), 0)
        support_count, _support_total = _longer_prefix_term_support_stats(
            pinyin,
            text,
            support_index,
            min_support_weight=360,
        )
        direct_signal = (
            usage_score * 0.44
            + jieba_score * 0.38
            + pageview_score * 0.12
            + min(1.0, source_hits / 6.0) * 0.06
            + char_score * 0.025
        )
        if _is_conversational_pos(pos_tag):
            direct_signal += 0.015
        elif _is_noun_pos(pos_tag) and (usage_score >= 0.10 or jieba_score >= 0.10):
            direct_signal += 0.010
        if style_penalty > 0:
            direct_signal -= min(0.18, style_penalty / 1000.0)
        if semantic_bonus > 0:
            semantic_cap = 0.20
            if (
                _is_noun_pos(pos_tag)
                and semantic_bonus <= 240
                and usage_score < 0.16
                and jieba_score < 0.12
                and pageview_score < 0.06
                and source_hits <= 1
            ):
                # CEDICT "daily concrete object" clues are visibility hints for
                # noun entries.  They should not let a low-direct-signal object
                # noun outrank a same-pinyin term with stronger usage evidence.
                semantic_cap = 0.04
            direct_signal += min(semantic_cap, semantic_bonus / 1200.0)
        return (
            max(0.0, min(1.0, direct_signal)),
            usage_score,
            jieba_score,
            source_hits,
            pos_tag,
            pageview_score,
            style_penalty,
            support_count,
            char_score,
            semantic_bonus,
        )

    for bucket_pinyin, items in buckets.items():
        if len(items) < 2:
            continue

        enriched: List[
            Tuple[
                str,
                str,
                int,
                Tuple[float, float, float, int, str, float, int, int, float, int],
            ]
        ] = []
        for pinyin, text, weight in items:
            if _cjk_len(text) != 2 or _is_pure_daily_number_word(text):
                continue
            enriched.append((pinyin, text, weight, parts(pinyin, text)))
        if len(enriched) < 2:
            continue

        # Earlier semantic/family passes can over-promote a valid but less
        # common homophone, or suppress the direct-frequency leader to a
        # visibility-only weight. Only repair low-confidence buckets, and only
        # from independent aggregate-usage and Jieba evidence; established
        # high-confidence winners must not be reshuffled here.
        direct_evidence_candidates = [
            item
            for item in enriched
            if item[1] not in weak_leader_terms
            and item[3][6] < 120
            and not _is_named_entity_pos(item[3][4])
        ]
        if len(direct_evidence_candidates) >= 2:
            bucket_peak_weight = max(item[2] for item in enriched)
            direct_evidence_candidates.sort(
                key=lambda item: (
                    item[3][1]
                    + item[3][2]
                    + item[3][5]
                    + min(1.0, item[3][3] / 6.0),
                    item[2],
                ),
                reverse=True,
            )
            evidence_leader = direct_evidence_candidates[0]
            evidence_runner_up = direct_evidence_candidates[1]
            evidence_leader_total = (
                evidence_leader[3][1]
                + evidence_leader[3][2]
                + evidence_leader[3][5]
                + min(1.0, evidence_leader[3][3] / 6.0)
            )
            evidence_runner_up_total = (
                evidence_runner_up[3][1]
                + evidence_runner_up[3][2]
                + evidence_runner_up[3][5]
                + min(1.0, evidence_runner_up[3][3] / 6.0)
            )
            evidence_margin = evidence_leader_total - evidence_runner_up_total
            evidence_leader_pinyin = evidence_leader[0]
            evidence_leader_text = evidence_leader[1]
            evidence_leader_weight = evidence_leader[2]
            evidence_leader_usage = evidence_leader[3][1]
            evidence_leader_jieba = evidence_leader[3][2]
            evidence_runner_up_usage = evidence_runner_up[3][1]
            evidence_runner_up_jieba = evidence_runner_up[3][2]
            protected_competitor = any(
                text != evidence_leader_text
                and text in preferred_terms
                and weight >= evidence_leader_weight
                for _pinyin, text, weight, item_parts in enriched
            )
            if (
                not protected_competitor
                and bucket_peak_weight <= 640
                and evidence_leader_total >= 0.28
                and evidence_margin >= 0.045
                and evidence_leader_usage >= evidence_runner_up_usage + 0.015
                and evidence_leader_jieba >= evidence_runner_up_jieba + 0.010
            ):
                strongest_competitor_weight = max(
                    weight
                    for _pinyin, text, weight, _item_parts in enriched
                    if text != evidence_leader_text
                )
                restore_margin = 32 + min(
                    48,
                    int(round((evidence_margin - 0.045) * 220.0)),
                )
                restored_weight = min(
                    1000,
                    max(
                        evidence_leader_weight,
                        strongest_competitor_weight + restore_margin,
                    ),
                )
                if restored_weight > evidence_leader_weight:
                    mapping[(evidence_leader_pinyin, evidence_leader_text)] = restored_weight
                    stats[f"{stats_prefix}_short_exact_direct_signal_restored"] += 1
                    enriched = [
                        (
                            pinyin,
                            text,
                            mapping.get((pinyin, text), weight),
                            item_parts,
                        )
                        for pinyin, text, weight, item_parts in enriched
                    ]

        leaders = [
            item
            for item in enriched
            if item[3][0] >= 0.16
            and item[3][6] < 120
            and not _is_named_entity_pos(item[3][4])
        ]
        if not leaders:
            continue

        leader = max(leaders, key=lambda item: (item[3][0], item[2]))
        leader_pinyin, leader_text, leader_weight, leader_parts = leader
        leader_signal, leader_usage, leader_jieba, leader_hits, _leader_pos, leader_page, _leader_style, _leader_support, _leader_char, leader_semantic = leader_parts
        leader_direct_total = leader_usage + leader_jieba + leader_page + min(1.0, leader_hits / 6.0)
        if leader_weight < 240 or leader_direct_total < 0.24:
            continue

        touched = False
        for pinyin, text, weight, item_parts in enriched:
            if text == leader_text:
                continue
            if (
                text in weak_leader_terms
                or (
                    text in preferred_terms
                    and item_parts[1] >= 0.50
                )
            ):
                continue

            signal, usage_score, jieba_score, source_hits, pos_tag, pageview_score, style_penalty, support_count, _char_score, semantic_bonus = item_parts
            if style_penalty >= 180:
                signal_margin = 0.030
            else:
                signal_margin = 0.055
            direct_total = usage_score + jieba_score + pageview_score + min(1.0, source_hits / 6.0)
            direct_gap = leader_direct_total - direct_total
            visibility_inflated = (
                support_count >= 2
                and direct_total + 0.10 < leader_direct_total
            )
            weak_direct_competitor = (
                direct_gap >= 0.10
                and (
                    usage_score < leader_usage + 0.03
                    and jieba_score < leader_jieba + 0.03
                )
            )
            semantic_daily_leader = (
                leader_semantic >= 180
                and leader_semantic >= semantic_bonus + 120
                and leader_signal >= signal + signal_margin
                and direct_total <= leader_direct_total + 0.18
            )
            direct_evidence_dominated = (
                leader_signal >= signal + signal_margin
                and direct_gap >= 0.12
                and direct_total <= leader_direct_total + 0.04
                and usage_score <= leader_usage + 0.03
                and jieba_score <= leader_jieba + 0.03
                and pageview_score <= leader_page + 0.05
                and source_hits <= leader_hits + 1
                and semantic_bonus <= leader_semantic + 300
                and style_penalty < 120
                and not _is_named_entity_pos(pos_tag)
                and not _is_conversational_pos(pos_tag)
            )
            weak_direct_against_common_leader = (
                leader_signal >= signal + max(0.040, signal_margin - 0.010)
                and leader_direct_total >= 0.36
                and direct_total + 0.16 <= leader_direct_total
                and usage_score <= leader_usage + 0.03
                and jieba_score <= leader_jieba + 0.03
                and pageview_score <= leader_page + 0.05
                and source_hits <= leader_hits + 1
                and style_penalty < 160
                and not _is_named_entity_pos(pos_tag)
                and not _is_conversational_pos(pos_tag)
            )
            if not (
                leader_signal >= signal + signal_margin
                and (
                    visibility_inflated
                    or weak_direct_competitor
                    or semantic_daily_leader
                    or direct_evidence_dominated
                    or weak_direct_against_common_leader
                    or style_penalty >= 80
                )
            ):
                continue
            if (
                _is_conversational_pos(pos_tag)
                and source_hits >= 3
                and jieba_score >= 0.18
                and leader_signal < signal + 0.12
            ):
                continue

            cap_margin = 36 + min(132, int(round((leader_signal - signal) * 260.0)))
            if visibility_inflated:
                cap_margin += 28
            if direct_evidence_dominated:
                cap_margin += 28
            if weak_direct_against_common_leader:
                cap_margin += 36
            cap = max(1, leader_weight - cap_margin)
            if weight <= cap:
                continue

            mapping[(pinyin, text)] = cap
            stats[f"{stats_prefix}_short_exact_direct_signal_capped"] += 1
            if direct_evidence_dominated:
                stats[f"{stats_prefix}_short_exact_direct_evidence_dominated_capped"] += 1
            touched = True

        if touched:
            stats[f"{stats_prefix}_short_exact_direct_signal_buckets"] += 1

    return stats


def _promote_short_exact_homophones_by_pairwise_direct_signal(
    mapping: Dict[Tuple[str, str], int],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    preferred_terms: Set[str],
    weak_leader_terms: Set[str],
    stats_prefix: str,
    bucket_pinyin_map: Dict[Tuple[str, str], str] | None = None,
    term_style_penalty_map: Dict[Tuple[str, str], int] | None = None,
    thuocl_corroborated_signal_map: Dict[str, float] | None = None,
) -> Dict[str, int]:
    """Repair small final two-character inversions without lowering candidates.

    This pass deliberately runs after every existing weight rule. It promotes
    only terms backed by strict direct-frequency dominance, or by independently
    corroborated THUOCL evidence, so earlier ranking decisions cannot react to
    the new floor and indirectly suppress another candidate.
    """
    stats = {
        f"{stats_prefix}_short_exact_pairwise_buckets": 0,
        f"{stats_prefix}_short_exact_pairwise_rebalanced": 0,
    }
    if not mapping:
        return stats

    bucket_pinyin_map = bucket_pinyin_map or {}
    term_style_penalty_map = term_style_penalty_map or {}
    thuocl_corroborated_signal_map = thuocl_corroborated_signal_map or {}
    buckets: Dict[str, List[Tuple[str, str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        if _cjk_len(text) != 2 or _is_pure_daily_number_word(text):
            continue
        bucket_pinyin = bucket_pinyin_map.get((pinyin, text), pinyin)
        if not bucket_pinyin:
            continue
        buckets.setdefault(bucket_pinyin, []).append((pinyin, text, weight))

    for items in buckets.values():
        if len(items) < 2:
            continue

        required_floors: Dict[Tuple[str, str], int] = {}
        for strong_pinyin, strong_text, strong_weight in items:
            strong_jieba = min(
                1.0,
                max(0.0, jieba_direct_signal_map.get(strong_text, 0.0)),
            )
            strong_pos = jieba_pos_map.get(strong_text, "")
            strong_style = term_style_penalty_map.get(
                (strong_pinyin, strong_text),
                0,
            )
            if strong_style >= 120 or _is_named_entity_pos(strong_pos):
                continue
            strong_thuocl = thuocl_corroborated_signal_map.get(strong_text, 0.0)

            for _weak_pinyin, weak_text, weak_weight in items:
                if strong_text == weak_text:
                    continue
                weak_jieba = min(
                    1.0,
                    max(0.0, jieba_direct_signal_map.get(weak_text, 0.0)),
                )
                weak_pos = jieba_pos_map.get(weak_text, "")
                weak_style = term_style_penalty_map.get(
                    (_weak_pinyin, weak_text),
                    0,
                )
                if weak_style >= 120 or _is_named_entity_pos(weak_pos):
                    continue
                if weak_text in preferred_terms or weak_weight >= 900:
                    continue

                inversion = weak_weight + 12 - strong_weight
                if inversion <= 0:
                    continue

                weak_thuocl = thuocl_corroborated_signal_map.get(weak_text, 0.0)
                large_jieba_dominance = (
                    inversion <= 92
                    and strong_jieba >= 0.12
                    and strong_jieba >= weak_jieba + 0.08
                    and strong_jieba >= max(0.01, weak_jieba) * 8.0
                )
                small_jieba_dominance = (
                    inversion <= 48
                    and strong_jieba >= 0.055
                    and strong_jieba >= weak_jieba + 0.015
                    and strong_jieba >= max(0.01, weak_jieba) * 1.40
                )
                corroborated_thuocl_dominance = (
                    inversion <= 24
                    and strong_thuocl >= 0.65
                    and strong_thuocl >= weak_thuocl + 0.45
                    and strong_jieba >= 0.12
                    and strong_jieba + 0.012 >= weak_jieba
                )
                if not (
                    large_jieba_dominance
                    or small_jieba_dominance
                    or corroborated_thuocl_dominance
                ):
                    continue
                if (
                    weak_text in weak_leader_terms
                    and not (weak_jieba > 0.0 and large_jieba_dominance)
                ):
                    continue

                margin = 12
                if large_jieba_dominance:
                    margin += min(12, int(round(min(0.24, strong_jieba) * 50.0)))
                strong_key = (strong_pinyin, strong_text)
                required_floors[strong_key] = max(
                    required_floors.get(strong_key, strong_weight),
                    min(1000, weak_weight + margin),
                )

        changed_keys = set()
        for key, floor in required_floors.items():
            current = mapping.get(key, 0)
            if floor <= current:
                continue
            mapping[key] = floor
            changed_keys.add(key)
        if changed_keys:
            stats[f"{stats_prefix}_short_exact_pairwise_buckets"] += 1
            stats[f"{stats_prefix}_short_exact_pairwise_rebalanced"] += len(changed_keys)

    return stats


def _cap_weak_exact_homophones_against_curated_daily_leaders(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    preferred_terms: Set[str],
    weak_leader_terms: Set[str],
    stats_prefix: str,
    bucket_pinyin_map: Dict[Tuple[str, str], str] | None = None,
    term_style_penalty_map: Dict[Tuple[str, str], int] | None = None,
    term_semantic_bonus_map: Dict[Tuple[str, str], int] | None = None,
) -> Dict[str, int]:
    """Keep weak exact homophones below explicit curated daily exact terms.

    Curated daily terms are human frequency anchors. Domain terms, fragments
    backed mainly by longer compounds, and style-marked entries should remain
    visible, but should not outrank these anchors in the same pinyin bucket.
    """
    stats = {
        f"{stats_prefix}_curated_exact_leader_buckets": 0,
        f"{stats_prefix}_curated_exact_leader_capped": 0,
    }
    if not mapping or not preferred_terms:
        return stats

    bucket_pinyin_map = bucket_pinyin_map or {}
    term_style_penalty_map = term_style_penalty_map or {}
    term_semantic_bonus_map = term_semantic_bonus_map or {}
    support_index = _build_longer_prefix_term_support_index(mapping)

    buckets: Dict[str, List[Tuple[str, str, int]]] = {}
    for key, weight in mapping.items():
        pinyin, text = key
        bucket_pinyin = bucket_pinyin_map.get(key, pinyin)
        if not bucket_pinyin:
            continue
        buckets.setdefault(bucket_pinyin, []).append((pinyin, text, weight))

    def direct_parts(pinyin: str, text: str) -> Tuple[float, float, float, int, str, int, int, int]:
        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        jieba_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pos_tag = jieba_pos_map.get(text, "")
        style_penalty = term_style_penalty_map.get((pinyin, text), 0)
        semantic_bonus = term_semantic_bonus_map.get((pinyin, text), 0)
        support_count, _support_total = _longer_prefix_term_support_stats(
            pinyin,
            text,
            support_index,
            min_support_weight=360,
        )
        return (
            usage_score,
            jieba_score,
            pageview_score,
            source_hits,
            pos_tag,
            style_penalty,
            support_count,
            semantic_bonus,
        )

    for bucket_pinyin, items in buckets.items():
        leaders: List[Tuple[str, str, int, Tuple[float, float, float, int, str, int, int, int]]] = []
        for pinyin, text, weight in items:
            text_len = _cjk_len(text)
            if text_len < 2 or text_len > 4:
                continue
            if text not in preferred_terms or text in weak_leader_terms:
                continue
            text_parts = direct_parts(pinyin, text)
            if text_parts[0] < 0.50:
                continue
            leaders.append((pinyin, text, weight, text_parts))
        if not leaders:
            continue

        leader_pinyin, leader_text, leader_weight, leader_parts = max(
            leaders,
            key=lambda item: (
                item[2],
                item[3][0] + item[3][1] + item[3][2] + min(1.0, item[3][3] / 6.0),
            ),
        )
        preferred_min_weight = min(item[2] for item in leaders)
        if leader_weight < 520:
            continue
        (
            leader_usage,
            leader_jieba,
            leader_page,
            leader_hits,
            _leader_pos,
            _leader_style,
            _leader_support,
            _leader_semantic,
        ) = leader_parts
        leader_direct_total = leader_usage + leader_jieba + leader_page + min(1.0, leader_hits / 6.0)

        bucket_touched = False
        for pinyin, text, weight in items:
            if text == leader_text:
                continue
            text_len = _cjk_len(text)
            if text_len < 2 or text_len > 3 or _is_pure_daily_number_word(text):
                continue
            if (
                text in preferred_terms
                and text not in weak_leader_terms
                and direct_parts(pinyin, text)[0] >= 0.50
            ):
                continue
            if weight <= leader_weight - 72:
                continue

            (
                usage_score,
                jieba_score,
                pageview_score,
                source_hits,
                pos_tag,
                style_penalty,
                support_count,
                semantic_bonus,
            ) = direct_parts(pinyin, text)
            direct_total = usage_score + jieba_score + pageview_score + min(1.0, source_hits / 6.0)

            strong_independent = (
                usage_score >= 0.34
                or jieba_score >= 0.28
                or pageview_score >= 0.16
                or (
                    source_hits >= 5
                    and (usage_score >= 0.18 or jieba_score >= 0.14 or pageview_score >= 0.08)
                )
                or semantic_bonus >= 220
            )
            weak_signal = (
                usage_score < 0.20
                and jieba_score < 0.18
                and pageview_score < 0.10
                and source_hits <= 3
            )
            domain_or_visibility_only = (
                _is_medical_specific_term(text)
                or style_penalty >= 80
                or support_count > 0
                or (_is_named_entity_pos(pos_tag) and direct_total + 0.08 < leader_direct_total)
            )
            if strong_independent and not domain_or_visibility_only:
                continue
            if not (
                weak_signal
                or domain_or_visibility_only
                or direct_total + 0.12 < leader_direct_total
            ):
                continue

            cap_margin = 112
            if _is_medical_specific_term(text) or style_penalty >= 120:
                cap_margin = 180
            elif support_count > 0 or weak_signal:
                cap_margin = 144
            cap = max(1, leader_weight - cap_margin)
            if weak_signal:
                cap = min(cap, 760)
            if _is_medical_specific_term(text):
                cap = min(cap, 640)
            if preferred_min_weight >= 520:
                cap = min(cap, max(1, preferred_min_weight - 24))
            if weight <= cap:
                continue

            mapping[(pinyin, text)] = cap
            stats[f"{stats_prefix}_curated_exact_leader_capped"] += 1
            bucket_touched = True

        if bucket_touched:
            stats[f"{stats_prefix}_curated_exact_leader_buckets"] += 1

    return stats


def _boost_high_productivity_short_roots(
    mapping: Dict[Tuple[str, str], int],
    source_hits_map: Dict[str, int],
    jieba_pos_map: Dict[str, str],
    stats_prefix: str,
) -> Dict[str, int]:
    """Promote short independent roots backed by many aligned longer terms.

    This handles terms such as two-character technical roots that appear in
    many high-confidence compounds. The threshold is intentionally high so a
    short fragment backed by only one or a few longer formal terms stays low.
    """
    stats = {
        f"{stats_prefix}_productive_short_roots_boosted": 0,
        f"{stats_prefix}_productive_short_roots_delta_total": 0,
    }
    if not mapping:
        return stats

    candidates_by_text: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        text_len = _cjk_len(text)
        if text_len < 2 or text_len > 3:
            continue
        if _is_pure_daily_number_word(text) or not CJK_FULL_RE.fullmatch(text):
            continue
        if _is_named_entity_pos(jieba_pos_map.get(text, "")):
            continue
        candidates_by_text.setdefault(text, []).append((pinyin, weight))

    support: Dict[Tuple[str, str], List[int]] = {}
    for (term_pinyin, term_text), term_weight in mapping.items():
        term_len = _cjk_len(term_text)
        if term_len <= 2 or term_weight < 600 or not CJK_FULL_RE.fullmatch(term_text):
            continue
        term_pos_tag = jieba_pos_map.get(term_text, "")
        if _is_named_entity_pos(term_pos_tag):
            continue

        for root_len in range(2, min(3, term_len - 1) + 1):
            prefix_text = term_text[:root_len]
            for root_pinyin, _root_weight in candidates_by_text.get(prefix_text, []):
                if term_pinyin.startswith(root_pinyin) and len(term_pinyin) > len(root_pinyin):
                    support.setdefault((root_pinyin, prefix_text), []).append(term_weight)

            suffix_text = term_text[-root_len:]
            for root_pinyin, _root_weight in candidates_by_text.get(suffix_text, []):
                if term_pinyin.endswith(root_pinyin) and len(term_pinyin) > len(root_pinyin):
                    support.setdefault((root_pinyin, suffix_text), []).append(term_weight)

    for key, weights in support.items():
        current = mapping.get(key, 0)
        if current <= 0:
            continue

        pinyin, text = key
        text_len = _cjk_len(text)
        support_count = len(weights)
        support_total = sum(weights)
        min_count = 12 if text_len == 2 else 16
        if support_count < min_count or support_total < min_count * 620:
            continue

        source_hits = max(0, source_hits_map.get(text, 0))
        base_target = 560 + min(160, (support_count - min_count) * 6)
        if source_hits >= 2:
            base_target += min(80, (source_hits - 1) * 16)
        else:
            base_target = min(base_target, 660)
        target = min(780, max(current, base_target))
        if target <= current:
            continue

        mapping[(pinyin, text)] = target
        stats[f"{stats_prefix}_productive_short_roots_boosted"] += 1
        stats[f"{stats_prefix}_productive_short_roots_delta_total"] += target - current

    return stats


def _reinforce_productive_suffix_exact_terms(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    stats_prefix: str,
) -> Dict[str, int]:
    """Lift complete short terms backed by several aligned longer suffix terms.

    A short term that appears as the exact suffix of multiple high-confidence
    longer terms is often an independent target, not a low-value fragment
    (for example, "X优先级" supports standalone "优先级").  Keep the threshold
    high enough so single fixed-expression tails do not inherit the full
    longer-term weight.
    """
    stats = {
        f"{stats_prefix}_productive_suffix_exact_terms_boosted": 0,
        f"{stats_prefix}_productive_suffix_exact_terms_delta_total": 0,
    }
    if not mapping:
        return stats

    candidates_by_text: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        text_len = _cjk_len(text)
        if text_len < 2 or text_len > 4:
            continue
        if _is_pure_daily_number_word(text) or not CJK_FULL_RE.fullmatch(text):
            continue
        if _is_named_entity_pos(jieba_pos_map.get(text, "")):
            continue
        candidates_by_text.setdefault(text, []).append((pinyin, weight))

    support: Dict[Tuple[str, str], List[int]] = {}
    for (term_pinyin, term_text), term_weight in mapping.items():
        term_len = _cjk_len(term_text)
        if term_len <= 3 or term_weight < 560 or not CJK_FULL_RE.fullmatch(term_text):
            continue
        if _is_named_entity_pos(jieba_pos_map.get(term_text, "")):
            continue

        for suffix_len in range(3, min(4, term_len - 1) + 1):
            suffix_text = term_text[-suffix_len:]
            for suffix_pinyin, _suffix_weight in candidates_by_text.get(suffix_text, []):
                if term_pinyin.endswith(suffix_pinyin) and len(term_pinyin) > len(suffix_pinyin):
                    support.setdefault((suffix_pinyin, suffix_text), []).append(term_weight)

    for key, weights in support.items():
        current = mapping.get(key, 0)
        if current <= 0:
            continue

        pinyin, text = key
        text_len = _cjk_len(text)
        support_count = len(weights)
        support_total = sum(weights)
        min_count = 3 if text_len == 3 else 4
        if support_count < min_count or support_total < min_count * 600:
            continue

        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        direct_signal = usage_score + jieba_score + pageview_score + min(1.0, source_hits / 6.0)

        # Without any direct support, suffix inheritance should remain a
        # visibility floor, not an aggressive promotion.
        base_target = 600 + min(150, (support_count - min_count) * 28)
        if direct_signal >= 0.18 or source_hits >= 1 or pageview_score >= 0.04:
            base_target += 60
        else:
            base_target = min(base_target, 660)

        target = min(820, max(current, base_target))
        if target <= current:
            continue

        mapping[key] = target
        inherited_usage = min(0.54, 0.34 + min(0.18, support_count * 0.04))
        usage_score_map[text] = max(usage_score, inherited_usage)
        source_hits_map[text] = max(source_hits, min(5, 3 + support_count // 3))
        stats[f"{stats_prefix}_productive_suffix_exact_terms_boosted"] += 1
        stats[f"{stats_prefix}_productive_suffix_exact_terms_delta_total"] += target - current

    return stats


def _filter_low_signal_rare_entries(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    wiki_augmented_terms: Set[str] | None,
    jieba_direct_signal_map: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    char_frequency_prior: Dict[str, float] | None,
    term_style_penalty_map: Dict[Tuple[str, str], int] | None,
    stats_prefix: str,
) -> Dict[str, int]:
    """
    Remove extremely low-signal rare forms when the same pinyin bucket already
    has stronger mainstream candidates.
    """
    stats = {
        f"{stats_prefix}_low_signal_rare_buckets": 0,
        f"{stats_prefix}_low_signal_rare_removed": 0,
        f"{stats_prefix}_low_signal_named_removed": 0,
        f"{stats_prefix}_low_signal_literary_removed": 0,
        f"{stats_prefix}_low_signal_written_removed": 0,
        f"{stats_prefix}_low_signal_fragment_removed": 0,
    }
    if not mapping:
        return stats
    if (
        not usage_score_map
        and not source_hits_map
        and not pageviews_signal_map
        and not wiki_titles
    ):
        return stats

    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    term_style_penalty_map = term_style_penalty_map or {}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)

    buckets: Dict[str, List[str]] = {}
    for (pinyin, text) in mapping.keys():
        buckets.setdefault(pinyin, []).append(text)

    for pinyin, texts in buckets.items():
        if len(texts) < 2:
            continue

        bucket_has_strong = False
        for text in texts:
            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            source_hits = max(0, source_hits_map.get(text, 0))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            if (
                usage_score >= 0.12
                or jieba_direct_score >= 0.08
                or source_hits >= 2
                or pageview_score >= 0.08
                or _has_effective_wiki_support(
                    text,
                    wiki_titles,
                    pageview_score=pageview_score,
                    source_hits=source_hits,
                    wiki_augmented_terms=wiki_augmented_terms,
                )
            ):
                bucket_has_strong = True
                break
        if not bucket_has_strong:
            continue
        stats[f"{stats_prefix}_low_signal_rare_buckets"] += 1

        to_drop: List[Tuple[str, str]] = []
        for text in texts:
            text_len = _cjk_len(text)
            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            source_hits = max(0, source_hits_map.get(text, 0))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            pos_tag = jieba_pos_map.get(text, "")
            wiki_support = _has_effective_wiki_support(
                text,
                wiki_titles,
                pageview_score=pageview_score,
                source_hits=source_hits,
                wiki_augmented_terms=wiki_augmented_terms,
            )
            looks_like_person_name = _looks_like_low_signal_person_name(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
            )
            looks_like_place_name = _looks_like_low_signal_place_name(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
            )

            min_char_prior = _compute_min_char_prior(text, char_prior)

            char_score = _compute_text_single_char_prior(text, char_prior)
            looks_like_literary_term = _looks_like_low_signal_literary_term(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
                char_score=char_score,
            )
            looks_like_written_tail_term = _looks_like_low_signal_written_tail_term(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
                char_score=char_score,
            )
            looks_like_fragment_term = _looks_like_low_signal_fragment_term(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
            )
            inflated_short_penalty = _compute_low_signal_inflated_short_term_penalty(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
                char_score=char_score,
                min_char_prior=min_char_prior,
            )
            if looks_like_fragment_term:
                to_drop.append((pinyin, text))
                stats[f"{stats_prefix}_low_signal_fragment_removed"] += 1
                continue
            # Protect common modern 2-char words even when cross-source signals
            # are incomplete (notably in TC conversion paths).
            if text_len <= 2 and char_score >= 0.58:
                continue
            if (
                text_len <= 2
                and not _is_named_entity_pos(pos_tag)
                and (
                    (
                        _is_conversational_pos(pos_tag)
                        and char_score >= 0.36
                        and (usage_score >= 0.05 or jieba_direct_score >= 0.07 or source_hits >= 2)
                    )
                    or (
                        _is_noun_pos(pos_tag)
                        and char_score >= 0.48
                        and (usage_score >= 0.06 or jieba_direct_score >= 0.08 or source_hits >= 2)
                    )
                )
            ):
                continue

            if (
                usage_score < 0.10
                and jieba_direct_score < 0.04
                and source_hits <= 1
                and pageview_score <= 0.02
                and not wiki_support
                and min_char_prior < 0.08
            ):
                to_drop.append((pinyin, text))
                continue

            if (
                _is_named_entity_pos(pos_tag)
                and usage_score < 0.38
                and jieba_direct_score < 0.12
                and source_hits <= 2
                and pageview_score < 0.08
                and not wiki_support
            ):
                to_drop.append((pinyin, text))
                stats[f"{stats_prefix}_low_signal_named_removed"] += 1
                continue

            if looks_like_person_name or looks_like_place_name:
                to_drop.append((pinyin, text))
                stats[f"{stats_prefix}_low_signal_named_removed"] += 1
                continue

            if looks_like_literary_term:
                to_drop.append((pinyin, text))
                stats[f"{stats_prefix}_low_signal_literary_removed"] += 1
                continue

            if looks_like_written_tail_term:
                to_drop.append((pinyin, text))
                stats[f"{stats_prefix}_low_signal_written_removed"] += 1
                continue

            style_penalty = term_style_penalty_map.get((pinyin, text), 0)
            if style_penalty >= 160 and usage_score < 0.12 and jieba_direct_score < 0.10:
                to_drop.append((pinyin, text))
                stats[f"{stats_prefix}_low_signal_written_removed"] += 1
                continue

            if inflated_short_penalty >= 112:
                to_drop.append((pinyin, text))
                stats[f"{stats_prefix}_low_signal_written_removed"] += 1

        for key in to_drop:
            if key in mapping:
                del mapping[key]
                stats[f"{stats_prefix}_low_signal_rare_removed"] += 1

    return stats


def _filter_global_tail_entries(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    wiki_augmented_terms: Set[str] | None,
    jieba_direct_signal_map: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    char_frequency_prior: Dict[str, float] | None,
    term_style_penalty_map: Dict[Tuple[str, str], int] | None,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_mandarin_map: Dict[str, str] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    stats_prefix: str,
) -> Dict[str, int]:
    """
    Global tail trimming (independent of homophone buckets).

    This catches low-signal singleton entries that bucket-based filtering
    cannot see, especially weak named entities and rare-form leftovers.
    """
    stats = {
        f"{stats_prefix}_global_tail_removed": 0,
        f"{stats_prefix}_global_tail_named_removed": 0,
        f"{stats_prefix}_global_tail_literary_removed": 0,
        f"{stats_prefix}_global_tail_written_removed": 0,
        f"{stats_prefix}_global_tail_fragment_removed": 0,
        f"{stats_prefix}_global_tail_rare_char_removed": 0,
        f"{stats_prefix}_global_tail_modernity_risk_removed": 0,
        f"{stats_prefix}_global_tail_constituent_mismatch_removed": 0,
    }
    if not mapping:
        return stats
    if (
        not usage_score_map
        and not source_hits_map
        and not pageviews_signal_map
        and not wiki_titles
    ):
        return stats

    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    term_style_penalty_map = term_style_penalty_map or {}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    to_drop: List[Tuple[str, str]] = []
    bucket_counts: Dict[str, int] = {}
    for pinyin, _text in mapping.keys():
        bucket_counts[pinyin] = bucket_counts.get(pinyin, 0) + 1
    remaining_bucket_counts: Dict[str, int] = dict(bucket_counts)
    bucket_keepers: Dict[str, Tuple[str, str]] = {}
    bucket_keeper_scores: Dict[str, Tuple[float, float, float, float, float, float, int, str]] = {}

    def build_bucket_keeper_score(entry_key: Tuple[str, str]) -> Tuple[float, float, float, float, float, float, int, str]:
        _entry_pinyin, entry_text = entry_key
        entry_usage_score = min(1.0, max(0.0, usage_score_map.get(entry_text, 0.0)))
        entry_source_hits = float(max(0, source_hits_map.get(entry_text, 0)))
        entry_pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(entry_text, 0.0)))
        entry_jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(entry_text, 0.0)))
        entry_char_score = _compute_text_single_char_prior(entry_text, char_prior)
        entry_min_char_prior = _compute_min_char_prior(entry_text, char_prior)
        entry_pos_tag = jieba_pos_map.get(entry_text, "")
        entry_wiki_support = _has_effective_wiki_support(
            entry_text,
            wiki_titles,
            pageview_score=entry_pageview_score,
            source_hits=int(entry_source_hits),
            wiki_augmented_terms=wiki_augmented_terms,
        )
        entry_inflated_short_penalty = _compute_low_signal_inflated_short_term_penalty(
            entry_text,
            usage_score=entry_usage_score,
            source_hits=int(entry_source_hits),
            pageview_score=entry_pageview_score,
            jieba_direct_score=entry_jieba_direct_score,
            wiki_support=entry_wiki_support,
            pos_tag=entry_pos_tag,
            char_score=entry_char_score,
            min_char_prior=entry_min_char_prior,
        )
        return (
            float(mapping.get(entry_key, 0) - entry_inflated_short_penalty),
            entry_usage_score,
            entry_jieba_direct_score,
            entry_pageview_score,
            entry_source_hits,
            entry_char_score,
            -_cjk_len(entry_text),
            entry_text,
        )

    # When trimming a low-signal tail, preserve the strongest remaining
    # candidate in each pinyin bucket instead of whichever entry happens to be
    # visited last in dict order.
    for key in mapping.keys():
        entry_pinyin, _entry_text = key
        keeper_score = build_bucket_keeper_score(key)
        if (
            entry_pinyin not in bucket_keeper_scores
            or keeper_score > bucket_keeper_scores[entry_pinyin]
        ):
            bucket_keeper_scores[entry_pinyin] = keeper_score
            bucket_keepers[entry_pinyin] = key

    def schedule_drop(entry_key: Tuple[str, str]) -> bool:
        entry_pinyin, _ = entry_key
        if bucket_keepers.get(entry_pinyin) == entry_key:
            return False
        remaining = remaining_bucket_counts.get(entry_pinyin, 0)
        if remaining <= 1:
            return False
        to_drop.append(entry_key)
        remaining_bucket_counts[entry_pinyin] = remaining - 1
        return True

    def force_drop(entry_key: Tuple[str, str]) -> bool:
        if entry_key in to_drop:
            return False
        entry_pinyin, _ = entry_key
        to_drop.append(entry_key)
        remaining = remaining_bucket_counts.get(entry_pinyin, 0)
        if remaining > 0:
            remaining_bucket_counts[entry_pinyin] = remaining - 1
        return True

    for key in list(mapping.keys()):
        pinyin, text = key
        text_len = _cjk_len(text)
        if text_len < 2:
            continue

        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pos_tag = jieba_pos_map.get(text, "")
        wiki_support = _has_effective_wiki_support(
            text,
            wiki_titles,
            pageview_score=pageview_score,
            source_hits=source_hits,
            wiki_augmented_terms=wiki_augmented_terms,
        )
        looks_like_person_name = _looks_like_low_signal_person_name(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_support,
            pos_tag=pos_tag,
        )
        looks_like_place_name = _looks_like_low_signal_place_name(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_support,
            pos_tag=pos_tag,
        )

        min_char_prior = _compute_min_char_prior(text, char_prior)

        char_score = _compute_text_single_char_prior(text, char_prior)
        looks_like_literary_term = _looks_like_low_signal_literary_term(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_support,
            pos_tag=pos_tag,
            char_score=char_score,
        )
        looks_like_written_tail_term = _looks_like_low_signal_written_tail_term(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_support,
            pos_tag=pos_tag,
            char_score=char_score,
        )
        looks_like_fragment_term = _looks_like_low_signal_fragment_term(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_support,
            pos_tag=pos_tag,
        )
        inflated_short_penalty = _compute_low_signal_inflated_short_term_penalty(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_support,
            pos_tag=pos_tag,
            char_score=char_score,
            min_char_prior=min_char_prior,
        )
        modernity_risk = _compute_low_signal_modernity_risk(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_support,
            pos_tag=pos_tag,
            char_score=char_score,
            min_char_prior=min_char_prior,
            looks_like_person_name=looks_like_person_name,
            looks_like_place_name=looks_like_place_name,
            looks_like_literary_term=looks_like_literary_term,
            looks_like_written_tail_term=looks_like_written_tail_term,
        )
        constituent_alignment_mismatch = _has_constituent_pinyin_alignment_mismatch(
            text,
            pinyin,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_mandarin_map,
            unihan_pinlu_detail_map,
        )
        style_penalty = term_style_penalty_map.get(key, 0)
        if (
            constituent_alignment_mismatch
            and usage_score < 0.08
            and jieba_direct_score < 0.06
            and source_hits <= 1
            and pageview_score < 0.03
            and not wiki_support
        ):
            if force_drop(key):
                stats[f"{stats_prefix}_global_tail_constituent_mismatch_removed"] += 1
            continue
        if style_penalty >= 160 and usage_score < 0.12 and jieba_direct_score < 0.10:
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_written_removed"] += 1
            continue
        if (
            text_len <= 2
            and mapping.get(key, 0) >= 380
            and char_score >= 0.58
            and usage_score >= 0.04
            and source_hits >= 1
            and not _is_named_entity_pos(pos_tag)
            and _is_conversational_pos(pos_tag)
        ):
            # A short CEDICT-derived modern verb with moderate direct evidence
            # should stay selectable even if it is not a default candidate.
            # Global tail trimming is for noise removal, not for deleting valid
            # exact words after homophone reranking has already lowered them.
            continue
        if (
            inflated_short_penalty >= 112
            and usage_score < 0.06
            and jieba_direct_score < 0.02
            and source_hits <= 1
            and pageview_score <= 0.01
            and not wiki_support
        ):
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_written_removed"] += 1
            continue
        if (
            modernity_risk >= 230
            and usage_score < 0.06
            and jieba_direct_score < 0.04
            and source_hits <= 1
            and pageview_score < 0.03
            and not wiki_support
        ):
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_modernity_risk_removed"] += 1
            continue
        if (
            text_len == 3
            and looks_like_written_tail_term
            and modernity_risk >= 250
            and usage_score < 0.08
            and jieba_direct_score < 0.06
            and source_hits <= 1
            and pageview_score < 0.03
            and not wiki_support
        ):
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_written_removed"] += 1
            continue
        if (
            bucket_counts.get(pinyin, 0) >= 3
            and text_len <= 2
            and modernity_risk >= 170
            and usage_score < 0.10
            and jieba_direct_score < 0.08
            and source_hits <= 1
            and pageview_score < 0.03
            and not wiki_support
        ):
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_modernity_risk_removed"] += 1
            continue
        if looks_like_fragment_term:
            if force_drop(key):
                stats[f"{stats_prefix}_global_tail_fragment_removed"] += 1
            continue

        # Keep at least one candidate per pinyin bucket to avoid hard holes.
        if bucket_counts.get(pinyin, 0) < 2:
            continue

        # Protect common modern 2-char words even when TC-side signal mapping
        # misses some entries.
        if text_len <= 2 and char_score >= 0.58:
            continue
        if (
            text_len <= 2
            and not _is_named_entity_pos(pos_tag)
            and (
                (
                    _is_conversational_pos(pos_tag)
                    and char_score >= 0.36
                    and (usage_score >= 0.05 or jieba_direct_score >= 0.07 or source_hits >= 2)
                )
                or (
                    _is_noun_pos(pos_tag)
                    and char_score >= 0.48
                    and (usage_score >= 0.06 or jieba_direct_score >= 0.08 or source_hits >= 2)
                )
            )
        ):
            continue

        if (
            _is_named_entity_pos(pos_tag)
            and text_len <= 4
            and not wiki_support
            and source_hits <= 2
            and pageview_score < 0.10
            and jieba_direct_score < 0.14
            and usage_score < 0.38
        ):
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_named_removed"] += 1
            continue

        if looks_like_person_name or looks_like_place_name:
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_named_removed"] += 1
            continue

        if looks_like_literary_term:
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_literary_removed"] += 1
            continue

        if looks_like_written_tail_term:
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_written_removed"] += 1
            continue

        if inflated_short_penalty >= 112:
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_written_removed"] += 1
            continue

        if (
            text_len <= 4
            and usage_score < 0.06
            and jieba_direct_score < 0.02
            and source_hits <= 1
            and pageview_score <= 0.01
            and not wiki_support
            and min_char_prior < 0.04
        ):
            if schedule_drop(key):
                stats[f"{stats_prefix}_global_tail_rare_char_removed"] += 1
            continue

    for key in to_drop:
        if key in mapping:
            del mapping[key]
            stats[f"{stats_prefix}_global_tail_removed"] += 1

    return stats


def _collect_suspicious_high_weight_entries(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    wiki_augmented_terms: Set[str] | None,
    jieba_direct_signal_map: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    char_frequency_prior: Dict[str, float] | None,
    limit: int = 25,
) -> List[Dict[str, object]]:
    if not mapping:
        return []

    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    suspicious: List[Dict[str, object]] = []

    for (pinyin, text), weight in mapping.items():
        text_len = _cjk_len(text)
        if text_len <= 0 or text_len > 3 or weight < 420:
            continue

        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pos_tag = jieba_pos_map.get(text, "")
        char_score = _compute_text_single_char_prior(text, char_prior)
        wiki_support = _has_effective_wiki_support(
            text,
            wiki_titles,
            pageview_score=pageview_score,
            source_hits=source_hits,
            wiki_augmented_terms=wiki_augmented_terms,
        )
        looks_like_person_name = _looks_like_low_signal_person_name(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_support,
            pos_tag=pos_tag,
        )
        looks_like_place_name = _looks_like_low_signal_place_name(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_support,
            pos_tag=pos_tag,
        )
        looks_like_literary_term = _looks_like_low_signal_literary_term(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_support,
            pos_tag=pos_tag,
            char_score=char_score,
        )
        looks_like_written_tail_term = _looks_like_low_signal_written_tail_term(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_support,
            pos_tag=pos_tag,
            char_score=char_score,
        )
        modernity_risk = _compute_low_signal_modernity_risk(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=wiki_support,
            pos_tag=pos_tag,
            char_score=char_score,
            min_char_prior=_compute_min_char_prior(text, char_prior),
            looks_like_person_name=looks_like_person_name,
            looks_like_place_name=looks_like_place_name,
            looks_like_literary_term=looks_like_literary_term,
            looks_like_written_tail_term=looks_like_written_tail_term,
        )

        reasons: List[str] = []
        if (
            _is_named_entity_pos(pos_tag)
            and source_hits <= 2
            and pageview_score < 0.10
            and jieba_direct_score < 0.14
            and usage_score < 0.38
            and not wiki_support
        ):
            reasons.append("low-signal-named")
        if looks_like_person_name:
            reasons.append("likely-person-name")
        if looks_like_place_name:
            reasons.append("likely-place-name")
        if looks_like_literary_term:
            reasons.append("likely-literary")
        if looks_like_written_tail_term:
            reasons.append("written-tail")
        if (
            text_len <= 2
            and char_score < 0.20
            and usage_score < 0.08
            and jieba_direct_score < 0.08
            and source_hits <= 1
            and pageview_score < 0.02
            and not wiki_support
        ):
            reasons.append("rare-char")
        if (
            usage_score < 0.04
            and jieba_direct_score < 0.04
            and source_hits <= 1
            and pageview_score < 0.02
            and not wiki_support
        ):
            reasons.append("weak-usage")
        if modernity_risk >= 180:
            reasons.append("high-modernity-risk")

        if not reasons:
            continue

        risk_score = weight - int(
            round(
                usage_score * 220.0
                + jieba_direct_score * 220.0
                + pageview_score * 80.0
                + source_hits * 28.0
                + char_score * 140.0
                + (40.0 if wiki_support else 0.0)
            )
        )
        risk_score += modernity_risk // 2
        suspicious.append(
            {
                "pinyin": pinyin,
                "text": text,
                "weight": weight,
                "usage": usage_score,
                "jieba": jieba_direct_score,
                "pageviews": pageview_score,
                "source_hits": source_hits,
                "char_score": char_score,
                "modernity_risk": modernity_risk,
                "pos": pos_tag or "-",
                "reasons": ",".join(reasons),
                "risk_score": risk_score,
            }
        )

    suspicious.sort(
        key=lambda item: (
            int(item["risk_score"]),
            int(item["weight"]),
            -_cjk_len(str(item["text"])),
            str(item["text"]),
        ),
        reverse=True,
    )
    return suspicious[:limit]


def _download_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": DEFAULT_HTTP_USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _read_source_bytes(
    url: str,
    cache_file: pathlib.Path | None,
    repo_root: pathlib.Path | None = None,
) -> bytes:
    if url.startswith("repo://"):
        if repo_root is None:
            raise ValueError(f"repo:// source requires repo_root: {url}")
        relative = pathlib.PurePosixPath(url[len("repo://") :].lstrip("/"))
        resolved = repo_root.joinpath(*relative.parts)
        return resolved.read_bytes()

    if cache_file and cache_file.exists():
        return cache_file.read_bytes()

    payload = _download_bytes(url)
    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(payload)
    return payload


def _decode_text(payload: bytes) -> str:
    if payload.startswith(b"\x1f\x8b"):
        payload = gzip.decompress(payload)
    return payload.decode("utf-8", errors="ignore")


def _compute_cedict_style_penalty(defs: str) -> int:
    defs_lower = defs.strip().lower()
    if not defs_lower:
        return 0

    senses = [sense.strip() for sense in defs_lower.split("/") if sense.strip()]
    if not senses:
        senses = [defs_lower]

    dialect_senses = 0
    literary_senses = 0
    variant_senses = 0
    geopolitical_state_senses = 0
    geographic_place_senses = 0
    plain_senses = 0

    for sense in senses:
        is_dialect = "dialect" in sense
        is_literary = (
            ("literary" in sense)
            or ("classical" in sense)
            or ("archaic" in sense)
        )
        # CC-CEDICT also uses definitions such as
        # "used for X (in Taiwan)" for regional alternative spellings.  These
        # should stay visible, but should not outrank the mainstream exact term
        # in a homophone bucket.
        is_regional_used_for = sense.startswith("used for ") and "taiwan" in sense
        is_variant = sense.startswith(("variant of ", "old variant of ", "see also ")) or is_regional_used_for
        # CEDICT definitions such as "Yue state" describe historical/geographic
        # proper terms, not the everyday abstract sense "state/condition".
        is_geopolitical_state = (
            "generic term for states" in sense
            or re.search(r"(?<![a-z])(?:[a-z]+ )+state(?![a-z])", sense) is not None
        )
        is_geographic_place = (
            re.search(
                r"(?<![a-z])(?:province|provinces|region|regions|"
                r"autonomous region|municipality|prefecture|city|island|"
                r"mountain|river|lake|bay|strait|sea) (?:of|in)(?![a-z])",
                sense,
            )
            is not None
            or re.search(
                r"(?<![a-z])(?:capital|part) of [a-z][a-z -]+(?![a-z])",
                sense,
            )
            is not None
        )
        if is_dialect:
            dialect_senses += 1
        if is_literary:
            literary_senses += 1
        if is_variant:
            variant_senses += 1
        if is_geopolitical_state:
            geopolitical_state_senses += 1
        if is_geographic_place:
            geographic_place_senses += 1
        if (
            (not is_dialect)
            and (not is_literary)
            and (not is_variant)
            and (not is_geopolitical_state)
            and (not is_geographic_place)
        ):
            plain_senses += 1

    total_senses = max(1, len(senses))
    dialect_ratio = dialect_senses / total_senses
    literary_ratio = literary_senses / total_senses

    if variant_senses > 0:
        if plain_senses <= 0:
            return 180
        if any(
            sense.startswith("used for ") and "taiwan" in sense
            for sense in senses
        ):
            return 96
        if variant_senses * 2 >= total_senses:
            return 120
        return 64

    if dialect_senses > 0:
        if plain_senses <= 0:
            return 220 if dialect_ratio >= 0.5 else 180
        if dialect_ratio >= 0.5:
            return 120
        return 64

    if literary_senses > 0:
        if plain_senses <= 0:
            return 140 if literary_ratio >= 0.5 else 108
        if literary_ratio >= 0.5:
            return 72
        return 28

    if geopolitical_state_senses > 0:
        if plain_senses <= 0:
            return 120
        if geopolitical_state_senses * 2 >= total_senses:
            return 80
        return 40

    if geographic_place_senses > 0:
        if plain_senses <= 0:
            return 120
        if geographic_place_senses * 2 >= total_senses:
            return 80
        return 40

    return 0


def _compute_cedict_ime_seed_adjustment(text: str, defs: str) -> int:
    defs_lower = defs.strip().lower()
    if not defs_lower:
        return 0

    senses = [sense.strip() for sense in defs_lower.split("/") if sense.strip()]
    if not senses:
        senses = [defs_lower]

    total_senses = max(1, len(senses))
    variant_senses = 0
    place_senses = 0
    verb_senses = 0
    function_senses = 0
    article_noun_senses = 0
    text_len = _cjk_len(text)

    function_clues = (
        "due to",
        "owing to",
        "because of",
        "because",
        "thanks to",
        "as a result of",
        "since",
    )
    place_clues = (
        "county in ",
        "district in ",
        "town in ",
        "township in ",
        "village in ",
        "county of ",
        "province of ",
        "provinces of ",
        "region of ",
        "region in ",
        "autonomous region",
        "municipality in ",
        "municipality of ",
        "prefecture in ",
        "prefecture of ",
        "city in ",
        "city of ",
        "island in ",
        "island of ",
        "mountain in ",
        "mountain of ",
        "river in ",
        "river of ",
        "lake in ",
        "lake of ",
        "bay in ",
        "bay of ",
        "strait in ",
        "strait of ",
        "place name",
    )

    for sense in senses:
        if sense.startswith(("variant of ", "old variant of ", "see also ")) or (
            sense.startswith("used for ") and "taiwan" in sense
        ):
            variant_senses += 1
        if any(clue in sense for clue in place_clues):
            place_senses += 1
        if sense.startswith("to "):
            verb_senses += 1
        if sense.startswith(("a ", "an ", "the ")):
            article_noun_senses += 1
        if any(clue in sense for clue in function_clues):
            function_senses += 1

    if variant_senses == total_senses:
        return -72

    adjustment = 0
    if place_senses * 2 >= total_senses:
        adjustment -= 34
    if function_senses > 0:
        adjustment += 80
    elif verb_senses > 0:
        adjustment += 22
        if text_len == 2:
            adjustment += 48
        elif text_len == 3:
            adjustment += 24
    elif article_noun_senses == total_senses:
        adjustment -= 44
    elif article_noun_senses > 0:
        adjustment -= 22

    return adjustment


def _compute_cedict_daily_semantic_bonus(text: str, defs: str) -> int:
    defs_lower = defs.strip().lower()
    text_len = _cjk_len(text)
    if text_len < 2 or text_len > 3 or not defs_lower:
        return 0

    senses = [sense.strip() for sense in defs_lower.split("/") if sense.strip()]
    if not senses:
        senses = [defs_lower]

    total_senses = max(1, len(senses))
    variant_senses = 0
    place_senses = 0
    comparison_senses = 0
    daily_abstract_senses = 0
    daily_concrete_senses = 0
    daily_action_senses = 0
    negative_predicate_senses = 0
    function_senses = 0
    paired_expression_function_senses = 0

    comparison_clues = (
        "compare",
        "comparison",
        "compared with",
        "compared to",
        "by comparison",
        "in comparison",
        "greater than",
        "bigger than",
        "larger than",
        "more than",
        "less than",
        "smaller than",
        "lower than",
        "equal to",
        "not equal to",
        "at least",
        "at most",
        "no less than",
        "no more than",
    )
    daily_abstract_clues = (
        "usefulness",
        "useful",
        "purpose",
        "reason",
        "method",
        "means",
        "approach",
        "basis",
        "condition",
        "situation",
        "state",
        "case",
        "example",
        "period",
        "location",
        "part",
        "portion",
        "piece",
        "section",
        "component",
        "ingredient",
        "constituent",
        "position",
        "posture",
        "pose",
        "stance",
        "suitable",
        "fitting",
        "appropriate",
        "proper",
        "apt",
        "adequate",
        "sufficient",
        "abundant",
        "reality",
        "practice",
        "practical",
        "realistic",
        "actual",
        "expect",
        "anticipate",
        "incorrect",
        "wrong",
        "amiss",
        "abnormal",
        "myopia",
        "shortsighted",
        "nearsighted",
        "hyperopia",
        "farsighted",
        "astigmatism",
    )
    daily_action_clues = (
        "show",
        "display",
        "demonstrate",
        "jump",
        "leap",
        "bound",
        "skip",
    )
    daily_concrete_clues = (
        "clothes",
        "clothing",
        "garment",
        "shirt",
        "coat",
        "jacket",
        "pants",
        "trousers",
        "shoes",
        "socks",
        "hat",
        "food",
        "meal",
        "rice",
        "vegetable",
        "meat",
        "chicken",
        "water",
        "tea",
        "coffee",
        "milk",
        "cup",
        "bowl",
        "plate",
        "chopsticks",
        "table",
        "chair",
        "bed",
        "door",
        "window",
        "road",
        "street",
        "car",
        "phone",
        "computer",
    )
    daily_negative_predicate_clues = (
        "won't do",
        "will not do",
        "would not do",
        "be out of the question",
        "out of the question",
        "be no good",
        "no good",
        "not work",
        "doesn't work",
        "do not work",
        "not be capable",
        "not capable",
        "unable to",
        "cannot",
    )
    daily_function_adverb_clues = (
        "obviously",
        "plainly",
        "undoubtedly",
        "definitely",
    )
    function_clues = (
        "due to",
        "owing to",
        "because of",
        "because",
        "thanks to",
        "as a result of",
        "since",
        "rather than",
        "instead of",
        "according to",
        "with regard to",
        "in order to",
    )
    place_clues = (
        "county in ",
        "district in ",
        "town in ",
        "township in ",
        "village in ",
        "county of ",
        "province of ",
        "provinces of ",
        "region of ",
        "region in ",
        "autonomous region",
        "municipality in ",
        "municipality of ",
        "prefecture in ",
        "prefecture of ",
        "city in ",
        "city of ",
        "island in ",
        "island of ",
        "mountain in ",
        "mountain of ",
        "river in ",
        "river of ",
        "lake in ",
        "lake of ",
        "bay in ",
        "bay of ",
        "strait in ",
        "strait of ",
        "place name",
    )

    def has_clue(sense: str, clue: str) -> bool:
        clue = clue.strip().lower()
        if not clue:
            return False
        # Avoid false positives such as matching "state" inside "statement".
        return re.search(rf"(?<![a-z]){re.escape(clue)}(?![a-z])", sense) is not None

    def is_verb_like_sense(sense: str) -> bool:
        return sense.startswith(("to ", "to be ", "to become ", "to get "))

    for sense in senses:
        if sense.startswith(("variant of ", "old variant of ", "see also ")):
            variant_senses += 1
        if any(has_clue(sense, clue) for clue in place_clues):
            place_senses += 1
        if any(has_clue(sense, clue) for clue in comparison_clues):
            comparison_senses += 1
        if any(has_clue(sense, clue) for clue in daily_abstract_clues):
            daily_abstract_senses += 1
        if any(has_clue(sense, clue) for clue in daily_action_clues):
            daily_action_senses += 1
        if (not is_verb_like_sense(sense)) and any(
            has_clue(sense, clue) for clue in daily_concrete_clues
        ):
            daily_concrete_senses += 1
        if (
            text.startswith(("不", "没", "無", "无", "非", "未"))
            and any(has_clue(sense, clue) for clue in daily_negative_predicate_clues)
        ):
            negative_predicate_senses += 1
        if any(has_clue(sense, clue) for clue in daily_function_adverb_clues):
            function_senses += 1
        if any(has_clue(sense, clue) for clue in function_clues) and not has_clue(
            sense, "according to reason"
        ):
            function_senses += 1
            if "used in expression" in sense or "used in expressions" in sense:
                paired_expression_function_senses += 1

    if variant_senses == total_senses or place_senses * 2 >= total_senses:
        return 0

    if negative_predicate_senses > 0:
        return 320 if text_len == 2 else 200
    if comparison_senses > 0:
        return 260 if text_len == 2 else 180
    if function_senses > 0 and paired_expression_function_senses * 2 < function_senses:
        return 230 if text_len == 2 else 160
    if daily_concrete_senses > 0:
        return 240 if text_len == 2 else 150
    if daily_abstract_senses > 0:
        return 220 if text_len == 2 else 140
    if daily_action_senses > 0:
        return 240 if text_len == 2 else 150

    return 0


def _compute_style_ranking_penalty(style_penalty: int) -> int:
    if style_penalty >= 200:
        return 120
    if style_penalty >= 140:
        return 72
    if style_penalty >= 80:
        return 36
    if style_penalty >= 40:
        return 16
    return 0


def _parse_cedict_entries(
    source_text: str,
    min_hanzi: int,
) -> Tuple[
    Dict[Tuple[str, str], int],
    Dict[Tuple[str, str], int],
    Dict[str, int],
    Dict[Tuple[str, str], int],
    Dict[Tuple[str, str], int],
]:
    sc: Dict[Tuple[str, str], int] = {}
    tc: Dict[Tuple[str, str], int] = {}
    term_style_penalty_map: Dict[Tuple[str, str], int] = {}
    term_style_plain_keys: Set[Tuple[str, str]] = set()
    term_semantic_bonus_map: Dict[Tuple[str, str], int] = {}
    stats = {
        "total_lines": 0,
        "parsed_lines": 0,
        "invalid_format": 0,
        "invalid_pinyin": 0,
        "filtered_short": 0,
    }

    for raw_line in source_text.splitlines():
        stats["total_lines"] += 1
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = CEDICT_LINE_RE.match(line)
        if not match:
            stats["invalid_format"] += 1
            continue

        trad, simp, pinyin_raw, defs = match.groups()
        pinyin = _normalize_pinyin(pinyin_raw)
        if not pinyin:
            stats["invalid_pinyin"] += 1
            continue

        stats["parsed_lines"] += 1
        style_penalty = _compute_cedict_style_penalty(defs)
        semantic_bonus = _compute_cedict_daily_semantic_bonus(simp, defs)

        for text, bucket in ((simp, sc), (trad, tc)):
            if _cjk_len(text) < min_hanzi:
                stats["filtered_short"] += 1
                continue
            key = (pinyin, text)
            weight = _compute_weight(text) + _compute_cedict_ime_seed_adjustment(text, defs)
            if weight < 1:
                weight = 1
            elif weight > 1000:
                weight = 1000
            previous = bucket.get(key, 0)
            if weight > previous:
                bucket[key] = weight
            if style_penalty <= 0:
                term_style_plain_keys.add(key)
            elif key not in term_style_plain_keys and style_penalty > term_style_penalty_map.get(key, 0):
                term_style_penalty_map[key] = style_penalty
            if semantic_bonus > term_semantic_bonus_map.get(key, 0):
                term_semantic_bonus_map[key] = semantic_bonus

    for key in term_style_plain_keys:
        term_style_penalty_map.pop(key, None)

    return sc, tc, stats, term_style_penalty_map, term_semantic_bonus_map


def _parse_opencc_entries(source_text: str, min_hanzi: int) -> Tuple[List[Tuple[str, str]], Dict[str, int]]:
    entries: List[Tuple[str, str]] = []
    stats = {
        "total_lines": 0,
        "parsed_lines": 0,
        "invalid_format": 0,
        "filtered_short": 0,
    }

    for raw_line in source_text.splitlines():
        stats["total_lines"] += 1
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) < 1:
            stats["invalid_format"] += 1
            continue

        sc = parts[0].strip()
        tc = parts[1].strip() if len(parts) >= 2 else sc
        if not sc:
            stats["invalid_format"] += 1
            continue

        if (_cjk_len(sc) < min_hanzi) and (_cjk_len(tc) < min_hanzi):
            stats["filtered_short"] += 1
            continue

        entries.append((sc, tc))
        stats["parsed_lines"] += 1

    return entries, stats


def _parse_thuocl_entries(
    payload: bytes,
) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]:
    stats = {
        "thuocl_total_files": 0,
        "thuocl_total_lines": 0,
        "thuocl_parsed_lines": 0,
        "thuocl_invalid_format": 0,
    }
    entries_max_df: Dict[str, int] = {}
    entries_coverage: Dict[str, int] = {}

    if not payload.startswith(b"PK"):
        stats["thuocl_invalid_format"] += 1
        return entries_max_df, entries_coverage, stats

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        file_names = [
            name
            for name in zf.namelist()
            if name.endswith(".txt") and "/data/THUOCL_" in name
        ]
        stats["thuocl_total_files"] = len(file_names)

        for name in file_names:
            text = zf.read(name).decode("utf-8", errors="ignore")
            file_seen: Set[str] = set()
            for raw_line in text.splitlines():
                stats["thuocl_total_lines"] += 1
                line = raw_line.strip()
                if not line:
                    continue
                matched = re.match(r"^(.+?)\s+(\d+)\s*$", line)
                if not matched:
                    stats["thuocl_invalid_format"] += 1
                    continue

                word = matched.group(1).strip()
                try:
                    df_value = int(matched.group(2))
                except ValueError:
                    stats["thuocl_invalid_format"] += 1
                    continue

                if not word:
                    stats["thuocl_invalid_format"] += 1
                    continue

                previous = entries_max_df.get(word, 0)
                if df_value > previous:
                    entries_max_df[word] = df_value
                if word not in file_seen:
                    entries_coverage[word] = entries_coverage.get(word, 0) + 1
                    file_seen.add(word)
                stats["thuocl_parsed_lines"] += 1

    stats["thuocl_unique_terms"] = len(entries_max_df)
    return entries_max_df, entries_coverage, stats


def _normalize_wiki_title_with_reason(
    raw_title: str,
    min_hanzi: int,
    max_hanzi: int = 8,
) -> Tuple[str, str]:
    title = raw_title.strip()
    if not title:
        return "", "empty"

    title = title.replace("_", "").replace(" ", "").strip()
    # Remove trailing disambiguation suffixes: (xxx) / （xxx）
    title = re.sub(r"[\uFF08(][^\uFF08\uFF09()]{0,24}[\uFF09)]$", "", title).strip()
    if not title:
        return "", "empty"
    if (":" in title) or ("\uFF1A" in title):
        return "", "colon"
    if not CJK_FULL_RE.fullmatch(title):
        return "", "non_cjk"

    hanzi_len = _cjk_len(title)
    if hanzi_len < min_hanzi:
        return "", "short"
    if hanzi_len > max_hanzi:
        return "", "long"
    return title, ""


def _normalize_wiki_title(raw_title: str, min_hanzi: int, max_hanzi: int = 8) -> str:
    normalized, _reason = _normalize_wiki_title_with_reason(
        raw_title,
        min_hanzi=min_hanzi,
        max_hanzi=max_hanzi,
    )
    return normalized


def _parse_wiki_titles_entries(
    payload: bytes,
    min_hanzi: int,
    max_hanzi: int = 8,
) -> Tuple[Set[str], Dict[str, int]]:
    stats = {
        "wiki_total_lines": 0,
        "wiki_kept_titles": 0,
        "wiki_skipped_empty": 0,
        "wiki_skipped_colon": 0,
        "wiki_skipped_non_cjk": 0,
        "wiki_skipped_short": 0,
        "wiki_skipped_long": 0,
        "wiki_deduplicated": 0,
    }
    titles: Set[str] = set()
    text = _decode_text(payload)

    for raw_line in text.splitlines():
        stats["wiki_total_lines"] += 1
        normalized, reason = _normalize_wiki_title_with_reason(
            raw_line,
            min_hanzi=min_hanzi,
            max_hanzi=max_hanzi,
        )
        if not normalized:
            if reason == "empty":
                stats["wiki_skipped_empty"] += 1
            elif reason == "colon":
                stats["wiki_skipped_colon"] += 1
            elif reason == "non_cjk":
                stats["wiki_skipped_non_cjk"] += 1
            elif reason == "short":
                stats["wiki_skipped_short"] += 1
            elif reason == "long":
                stats["wiki_skipped_long"] += 1
            else:
                stats["wiki_skipped_empty"] += 1
            continue

        before = len(titles)
        titles.add(normalized)
        if len(titles) == before:
            stats["wiki_deduplicated"] += 1
        else:
            stats["wiki_kept_titles"] += 1

    return titles, stats


def _build_text_best_weight_map(
    mapping: Dict[Tuple[str, str], int],
) -> Dict[str, int]:
    text_best_weight: Dict[str, int] = {}
    for (_pinyin, text), weight in mapping.items():
        current = text_best_weight.get(text, 0)
        if weight > current:
            text_best_weight[text] = weight
    return text_best_weight


def _build_text_prefix_support_from_best_weight(
    text_best_weight: Dict[str, int],
    min_prefix_len: int = 2,
    max_prefix_len: int = 6,
) -> Tuple[Dict[str, int], Dict[str, float]]:
    term_count_map: Dict[str, int] = {}
    support_sum_map: Dict[str, float] = {}
    for text, weight in text_best_weight.items():
        if not CJK_FULL_RE.fullmatch(text):
            continue
        text_len = _cjk_len(text)
        if text_len <= min_prefix_len:
            continue
        for prefix_len in range(min_prefix_len, min(max_prefix_len, text_len - 1) + 1):
            prefix = text[:prefix_len]
            term_count_map[prefix] = term_count_map.get(prefix, 0) + 1
            support_sum_map[prefix] = support_sum_map.get(prefix, 0.0) + float(weight)
    return term_count_map, support_sum_map


def _looks_like_daily_chat_seed(text: str) -> bool:
    if not text:
        return False
    if text.startswith(DAILY_CHAT_SEED_PREFIXES):
        return True
    if text.endswith(DAILY_CHAT_SEED_SUFFIXES):
        return True
    for ch in text:
        if ch in DAILY_CHAT_SEED_CHARS:
            return True
    return False


def _is_unsafe_derived_prefix_text(text: str) -> bool:
    if _cjk_len(text) < 2 or not CJK_FULL_RE.fullmatch(text):
        return True
    return text[-1] in DERIVED_PREFIX_BLOCKED_TAIL_CHARS


def _looks_like_strong_two_char_daily_seed(text: str) -> bool:
    if _cjk_len(text) != 2:
        return False
    if not CJK_FULL_RE.fullmatch(text):
        return False
    head = text[0]
    tail = text[1]
    return head in STRONG_TWO_CHAR_DAILY_HEAD_CHARS and tail in STRONG_TWO_CHAR_DAILY_TAIL_CHARS


def _build_wiktionary_daily_seed_signal_map(
    titles: Set[str],
    char_frequency_prior: Dict[str, float],
) -> Tuple[Dict[str, float], Dict[str, int]]:
    """
    Convert zh.wiktionary titles into a restrained daily/chat lexical seed.

    We intentionally focus on 2-5 character CJK entries with strong constituent
    character priors, so this source boosts colloquial and everyday phrasing
    without flooding the lexicon with the full long-tail dictionary inventory.
    """
    stats = {
        "wiktionary_titles_total": len(titles),
        "wiktionary_titles_kept": 0,
        "wiktionary_titles_derived_prefixes": 0,
        "wiktionary_titles_skipped_length": 0,
        "wiktionary_titles_skipped_non_chat": 0,
        "wiktionary_titles_skipped_two_char_weak_daily": 0,
        "wiktionary_titles_skipped_char_prior": 0,
    }
    usage_score_map: Dict[str, float] = {}

    if not titles:
        return usage_score_map, stats

    for text in sorted(titles):
        text_len = _cjk_len(text)
        if text_len < 2 or text_len > 5:
            stats["wiktionary_titles_skipped_length"] += 1
            continue
        if not _looks_like_daily_chat_seed(text):
            stats["wiktionary_titles_skipped_non_chat"] += 1
            continue
        if text_len == 2 and not _looks_like_strong_two_char_daily_seed(text):
            stats["wiktionary_titles_skipped_two_char_weak_daily"] += 1
            continue

        char_score = _compute_text_single_char_prior(text, char_frequency_prior)
        min_char_prior = _compute_min_char_prior(text, char_frequency_prior)

        keep = False
        usage_score = 0.0
        if text_len == 2:
            if char_score >= 0.34 and min_char_prior >= 0.10:
                keep = True
                usage_score = 0.54 if char_score >= 0.60 else 0.48
        elif text_len == 3:
            if char_score >= 0.28 and min_char_prior >= 0.08:
                keep = True
                usage_score = 0.42 if char_score >= 0.46 else 0.34
        elif text_len == 4:
            if char_score >= 0.24 and min_char_prior >= 0.06:
                keep = True
                usage_score = 0.32 if char_score >= 0.40 else 0.26
        else:
            if char_score >= 0.30 and min_char_prior >= 0.08:
                keep = True
                usage_score = 0.24 if char_score >= 0.42 else 0.18

        if not keep:
            stats["wiktionary_titles_skipped_char_prior"] += 1
            continue

        usage_score_map[text] = usage_score
        stats["wiktionary_titles_kept"] += 1

        for prefix_len in range(2, min(4, text_len - 1) + 1):
            prefix = text[:prefix_len]
            if _is_unsafe_derived_prefix_text(prefix):
                continue
            if not _looks_like_daily_chat_seed(prefix):
                continue
            prefix_char_score = _compute_text_single_char_prior(prefix, char_frequency_prior)
            prefix_min_char_prior = _compute_min_char_prior(prefix, char_frequency_prior)

            if prefix_len == 2:
                if prefix_char_score < 0.22 or prefix_min_char_prior < 0.03:
                    continue
                prefix_usage = max(0.22, usage_score - 0.08)
            elif prefix_len == 3:
                if prefix_char_score < 0.18 or prefix_min_char_prior < 0.03:
                    continue
                prefix_usage = max(0.20, usage_score - 0.06)
            else:
                if prefix_char_score < 0.16 or prefix_min_char_prior < 0.03:
                    continue
                prefix_usage = max(0.18, usage_score - 0.04)

            previous = usage_score_map.get(prefix, 0.0)
            if prefix_usage > previous:
                usage_score_map[prefix] = prefix_usage
                stats["wiktionary_titles_derived_prefixes"] += 1

    return usage_score_map, stats


def _parse_curated_daily_phrase_entries(
    payload: bytes,
    min_hanzi: int,
    *,
    stats_prefix: str = "curated_daily_phrase",
) -> Tuple[List[Tuple[str, str, float, str]], Dict[str, int]]:
    stats = {
        f"{stats_prefix}_rows": 0,
        f"{stats_prefix}_kept": 0,
        f"{stats_prefix}_skipped_short": 0,
        f"{stats_prefix}_skipped_non_cjk": 0,
        f"{stats_prefix}_skipped_malformed": 0,
        f"{stats_prefix}_exact_zero": 0,
        f"{stats_prefix}_exact_rank": 0,
    }
    entries: List[Tuple[str, str, float, str]] = []
    text = _decode_text(payload)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        stats[f"{stats_prefix}_rows"] += 1
        parts = line.split("\t")
        if len(parts) < 2:
            stats[f"{stats_prefix}_skipped_malformed"] += 1
            continue
        sc_word = parts[0].strip()
        tc_word = parts[1].strip()
        try:
            usage_score = float(parts[2].strip()) if len(parts) >= 3 and parts[2].strip() else 0.82
        except ValueError:
            usage_score = 0.82
        if (not sc_word) or (not CJK_FULL_RE.fullmatch(sc_word)):
            stats[f"{stats_prefix}_skipped_non_cjk"] += 1
            continue
        if _cjk_len(sc_word) < min_hanzi:
            stats[f"{stats_prefix}_skipped_short"] += 1
            continue
        if not tc_word:
            tc_word = sc_word
        explicit_pinyin = parts[3].strip().lower() if len(parts) >= 4 else ""
        if explicit_pinyin and not PINYIN_RE.fullmatch(explicit_pinyin):
            explicit_pinyin = ""
        output_mode = parts[4].strip().lower() if len(parts) >= 5 else ""
        # Keep isolated post-rank exact markers distinct. Ordinary negative
        # usage retains its legacy visibility-only normalization. Post-rank
        # modes do not feed their rows into ranking or path statistics.
        if output_mode == CURATED_DAILY_EXACT_ZERO_MODE:
            normalized_usage_score = CURATED_DAILY_POST_RANK_ZERO_WEIGHT_USAGE_MAX
            stats[f"{stats_prefix}_exact_zero"] += 1
        elif output_mode in {
            CURATED_DAILY_EXACT_RANK_MODE,
            CURATED_DAILY_EXACT_RANK_NO_CONTAINS_MODE,
        }:
            bounded_rank = max(0.001, min(1.0, usage_score))
            normalized_usage_score = -(
                -CURATED_DAILY_POST_RANK_FIXED_WEIGHT_USAGE_BASE + bounded_rank
            )
            stats[f"{stats_prefix}_exact_rank"] += 1
        elif usage_score <= CURATED_DAILY_POST_RANK_ZERO_WEIGHT_USAGE_MAX:
            normalized_usage_score = CURATED_DAILY_POST_RANK_ZERO_WEIGHT_USAGE_MAX
        elif usage_score <= CURATED_DAILY_POST_RANK_EXACT_USAGE_MAX:
            normalized_usage_score = CURATED_DAILY_POST_RANK_EXACT_USAGE_MAX
        elif usage_score < 0.0:
            normalized_usage_score = -1.0
        else:
            normalized_usage_score = min(1.0, usage_score)
        entries.append(
            (
                sc_word,
                tc_word,
                normalized_usage_score,
                explicit_pinyin,
            )
        )
        stats[f"{stats_prefix}_kept"] += 1
    return entries, stats


def _parse_curated_contains_popularity_exclusions(
    payload: bytes,
) -> Tuple[Set[str], Set[str]]:
    """Return terms explicitly scoped out of runtime substring popularity."""
    sc_terms: Set[str] = set()
    tc_terms: Set[str] = set()
    text = _decode_text(payload)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        output_mode = parts[4].strip().lower()
        if output_mode not in {
            CURATED_DAILY_NO_CONTAINS_MODE,
            CURATED_DAILY_EXACT_RANK_NO_CONTAINS_MODE,
        }:
            continue
        sc_word = parts[0].strip()
        tc_word = parts[1].strip() or sc_word
        if sc_word and CJK_FULL_RE.fullmatch(sc_word):
            sc_terms.add(sc_word)
        if tc_word and CJK_FULL_RE.fullmatch(tc_word):
            tc_terms.add(tc_word)
    return sc_terms, tc_terms


def _parse_vertical_term_entries(
    payload: bytes,
    min_hanzi: int,
    default_usage_score: float,
) -> Tuple[List[Tuple[str, str, float, str]], Dict[str, int]]:
    stats = {
        "vertical_term_rows": 0,
        "vertical_term_kept": 0,
        "vertical_term_skipped_short": 0,
        "vertical_term_skipped_non_cjk": 0,
        "vertical_term_skipped_malformed": 0,
    }
    entries: List[Tuple[str, str, float, str]] = []
    text = _decode_text(payload)
    default_usage_score = min(1.0, max(0.0, default_usage_score))
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        stats["vertical_term_rows"] += 1
        parts = line.split("\t")
        if len(parts) < 2:
            stats["vertical_term_skipped_malformed"] += 1
            continue
        sc_word = parts[0].strip()
        tc_word = parts[1].strip()
        try:
            usage_score = (
                float(parts[2].strip())
                if len(parts) >= 3 and parts[2].strip()
                else default_usage_score
            )
        except ValueError:
            usage_score = default_usage_score
        explicit_pinyin = (
            _normalize_explicit_pinyin(parts[3].strip())
            if len(parts) >= 4 and parts[3].strip()
            else ""
        )
        if (not sc_word) or (not CJK_FULL_RE.fullmatch(sc_word)):
            stats["vertical_term_skipped_non_cjk"] += 1
            continue
        if _cjk_len(sc_word) < min_hanzi:
            stats["vertical_term_skipped_short"] += 1
            continue
        if not tc_word:
            tc_word = sc_word
        entries.append((sc_word, tc_word, min(1.0, max(0.0, usage_score)), explicit_pinyin))
        stats["vertical_term_kept"] += 1
    return entries, stats


def _parse_vertical_thuocl_member_entries(
    payload: bytes,
    member_name: str,
    min_hanzi: int,
    default_usage_score: float,
    filter_id: str,
) -> Tuple[List[Tuple[str, str, float, str]], Dict[str, int]]:
    stats = {
        "vertical_thuocl_files_matched": 0,
        "vertical_thuocl_rows": 0,
        "vertical_thuocl_kept": 0,
        "vertical_thuocl_skipped_short": 0,
        "vertical_thuocl_skipped_non_cjk": 0,
        "vertical_thuocl_skipped_filter": 0,
        "vertical_thuocl_invalid_format": 0,
        "vertical_thuocl_missing_member": 0,
    }
    entries: List[Tuple[str, str, float, str]] = []
    if not payload.startswith(b"PK"):
        stats["vertical_thuocl_invalid_format"] += 1
        return entries, stats

    member_name = member_name.strip()
    if not member_name:
        stats["vertical_thuocl_missing_member"] += 1
        return entries, stats

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        file_names = [
            name
            for name in zf.namelist()
            if fnmatch.fnmatch(pathlib.PurePosixPath(name).name, member_name)
        ]
        stats["vertical_thuocl_files_matched"] = len(file_names)
        if not file_names:
            stats["vertical_thuocl_missing_member"] += 1
            return entries, stats

        parsed_rows: List[Tuple[str, int]] = []
        max_df = 1
        seen_words: Set[str] = set()
        for name in file_names:
            text = zf.read(name).decode("utf-8", errors="ignore")
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                stats["vertical_thuocl_rows"] += 1
                matched = re.match(r"^(.+?)\s+(\d+)\s*$", line)
                if not matched:
                    stats["vertical_thuocl_invalid_format"] += 1
                    continue
                word = matched.group(1).strip()
                try:
                    df_value = int(matched.group(2))
                except ValueError:
                    stats["vertical_thuocl_invalid_format"] += 1
                    continue
                if not word or word in seen_words:
                    continue
                if not CJK_FULL_RE.fullmatch(word):
                    stats["vertical_thuocl_skipped_non_cjk"] += 1
                    continue
                if _cjk_len(word) < min_hanzi:
                    stats["vertical_thuocl_skipped_short"] += 1
                    continue
                if not _matches_vertical_filter(word, filter_id):
                    stats["vertical_thuocl_skipped_filter"] += 1
                    continue
                seen_words.add(word)
                parsed_rows.append((word, df_value))
                max_df = max(max_df, df_value)

        max_df_log = math.log1p(max_df)
        for word, df_value in parsed_rows:
            df_signal = math.log1p(df_value) / max_df_log if max_df_log > 0 else 0.0
            usage_score = min(0.86, max(default_usage_score, default_usage_score + df_signal * 0.18))
            # THUOCL members are simplified Chinese; leave TC blank so the
            # vertical import path converts it through OpenCC phrase hints.
            entries.append((word, "", usage_score, ""))
            stats["vertical_thuocl_kept"] += 1

    return entries, stats


def _iter_recent_complete_months(month_count: int) -> List[Tuple[int, int]]:
    if month_count <= 0:
        return []

    cursor = dt.date.today().replace(day=1)
    months: List[Tuple[int, int]] = []
    for _ in range(month_count):
        cursor = (cursor - dt.timedelta(days=1)).replace(day=1)
        months.append((cursor.year, cursor.month))
    return months


def _finalize_pageviews_aggregate(
    aggregate_weighted_views: Dict[str, float],
    aggregate_month_hits: Dict[str, int],
    aggregate_peak_views: Dict[str, int],
) -> Dict[str, int]:
    finalized: Dict[str, int] = {}
    for title, weighted_views in aggregate_weighted_views.items():
        if weighted_views <= 0.0:
            continue

        month_hits = max(0, aggregate_month_hits.get(title, 0))
        peak_views = max(0, aggregate_peak_views.get(title, 0))
        persistence_factor = 1.0 + min(0.32, max(0, month_hits - 1) * 0.06)
        if month_hits >= 4:
            persistence_factor += 0.04

        score = weighted_views * persistence_factor
        if peak_views > 0:
            if month_hits >= 2:
                score += peak_views * 0.05
            else:
                score += peak_views * 0.02

        finalized[title] = max(1, int(round(score)))
    return finalized


def _parse_wikimedia_pageviews_payload(
    payload: bytes,
    min_hanzi: int,
    max_rank: int,
    max_hanzi: int = 8,
) -> Tuple[Dict[str, int], Dict[str, int]]:
    stats = {
        "pageviews_articles_total": 0,
        "pageviews_articles_rank_filtered": 0,
        "pageviews_articles_title_filtered": 0,
        "pageviews_articles_kept": 0,
    }
    entries: Dict[str, int] = {}
    data = json.loads(payload.decode("utf-8", errors="ignore"))
    for item in data.get("items", []):
        for article in item.get("articles", []):
            stats["pageviews_articles_total"] += 1
            rank = int(article.get("rank", 0) or 0)
            if rank <= 0 or rank > max_rank:
                stats["pageviews_articles_rank_filtered"] += 1
                continue
            title = str(article.get("article", ""))
            normalized = _normalize_wiki_title(
                title,
                min_hanzi=min_hanzi,
                max_hanzi=max_hanzi,
            )
            if not normalized:
                stats["pageviews_articles_title_filtered"] += 1
                continue
            views = int(article.get("views", 0) or 0)
            if views <= 0:
                continue

            stats["pageviews_articles_kept"] += 1
            entries[normalized] = entries.get(normalized, 0) + views
    stats["pageviews_unique_terms"] = len(entries)
    return entries, stats


def _load_wikimedia_pageviews_entries(
    repo_root: pathlib.Path,
    source_url: str,
    min_hanzi: int,
    months: int,
    max_rank: int,
) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int], Dict[str, int]]:
    stats = {
        "pageviews_months_requested": months,
        "pageviews_months_loaded": 0,
        "pageviews_cache_hits": 0,
        "pageviews_http_fetches": 0,
        "pageviews_http_failures": 0,
        "pageviews_articles_total": 0,
        "pageviews_articles_rank_filtered": 0,
        "pageviews_articles_title_filtered": 0,
        "pageviews_articles_kept": 0,
    }
    aggregate_weighted_views: Dict[str, float] = {}
    aggregate_month_hits: Dict[str, int] = {}
    aggregate_peak_views: Dict[str, int] = {}
    cache_dir = repo_root / "data" / "cache" / "wikimedia_pageviews"
    base_url = source_url.rstrip("/")
    persistent_terms_2plus = 0
    persistent_terms_4plus = 0

    recent_months = _iter_recent_complete_months(months)
    for month_index, (year, month) in enumerate(recent_months):
        cache_file = cache_dir / f"zhwiki_top_{year:04d}{month:02d}.json"
        payload: bytes
        if cache_file.exists():
            payload = cache_file.read_bytes()
            stats["pageviews_cache_hits"] += 1
        else:
            try:
                month_url = f"{base_url}/{year:04d}/{month:02d}/all-days"
                request = urllib.request.Request(
                    month_url,
                    headers={"User-Agent": DEFAULT_HTTP_USER_AGENT},
                )
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = response.read()
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(payload)
                stats["pageviews_http_fetches"] += 1
            except Exception:
                stats["pageviews_http_failures"] += 1
                continue

        month_entries, month_stats = _parse_wikimedia_pageviews_payload(
            payload,
            min_hanzi=min_hanzi,
            max_rank=max_rank,
        )
        if month_entries:
            stats["pageviews_months_loaded"] += 1
        for key in (
            "pageviews_articles_total",
            "pageviews_articles_rank_filtered",
            "pageviews_articles_title_filtered",
            "pageviews_articles_kept",
        ):
            stats[key] += int(month_stats.get(key, 0))
        recency_weight = 0.88 ** month_index
        for title, views in month_entries.items():
            aggregate_weighted_views[title] = aggregate_weighted_views.get(title, 0.0) + (
                float(views) * recency_weight
            )
            aggregate_month_hits[title] = aggregate_month_hits.get(title, 0) + 1
            aggregate_peak_views[title] = max(aggregate_peak_views.get(title, 0), views)

    aggregate = _finalize_pageviews_aggregate(
        aggregate_weighted_views,
        aggregate_month_hits,
        aggregate_peak_views,
    )
    for count in aggregate_month_hits.values():
        if count >= 2:
            persistent_terms_2plus += 1
        if count >= 4:
            persistent_terms_4plus += 1
    stats["pageviews_unique_terms"] = len(aggregate)
    stats["pageviews_persistent_terms_2plus"] = persistent_terms_2plus
    stats["pageviews_persistent_terms_4plus"] = persistent_terms_4plus
    if months > 0 and stats["pageviews_months_loaded"] == 0:
        raise ValueError(
            "failed to load Wikimedia pageviews data for all requested months; "
            "check network connectivity or reduce --pageviews-months"
        )
    return aggregate, stats, aggregate_month_hits, aggregate_peak_views


def _parse_jieba_frequency_entries(
    payload: bytes,
    min_hanzi: int,
) -> Tuple[Dict[str, int], Dict[str, str], Dict[str, int]]:
    stats = {
        "jieba_total_lines": 0,
        "jieba_parsed_lines": 0,
        "jieba_invalid_format": 0,
        "jieba_filtered_non_cjk": 0,
        "jieba_filtered_short": 0,
    }
    entries: Dict[str, int] = {}
    pos_tags: Dict[str, str] = {}
    text = _decode_text(payload)

    for raw_line in text.splitlines():
        stats["jieba_total_lines"] += 1
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            stats["jieba_invalid_format"] += 1
            continue

        word = parts[0].strip()
        if not CJK_FULL_RE.fullmatch(word):
            stats["jieba_filtered_non_cjk"] += 1
            continue
        if _cjk_len(word) < min_hanzi:
            stats["jieba_filtered_short"] += 1
            continue

        try:
            freq = int(parts[1].strip())
        except ValueError:
            stats["jieba_invalid_format"] += 1
            continue

        if freq <= 0:
            continue

        previous = entries.get(word, 0)
        if freq > previous:
            entries[word] = freq
        if len(parts) >= 3:
            pos_tag = _normalize_jieba_pos_tag(parts[2])
            if pos_tag and (word not in pos_tags or freq >= previous):
                pos_tags[word] = pos_tag
        stats["jieba_parsed_lines"] += 1

    stats["jieba_unique_terms"] = len(entries)
    stats["jieba_pos_terms"] = len(pos_tags)
    return entries, pos_tags, stats


def _read_unihan_readings_text(payload: bytes) -> str:
    if not payload.startswith(b"PK"):
        return ""

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        target_name = ""
        for name in zf.namelist():
            if name.endswith("Unihan_Readings.txt"):
                target_name = name
                break
        if not target_name:
            return ""
        return zf.read(target_name).decode("utf-8", errors="ignore")


def _add_unihan_reading(
    readings_map: Dict[str, Set[str]],
    source_rank_map: Dict[Tuple[str, str], int],
    ch: str,
    pinyin: str,
    source_rank: int,
) -> None:
    if not pinyin:
        return
    readings_map.setdefault(ch, set()).add(pinyin)
    key = (ch, pinyin)
    previous = source_rank_map.get(key, 0)
    if source_rank > previous:
        source_rank_map[key] = source_rank


def _parse_unihan_pinlu_token(token: str) -> Tuple[str, int]:
    value = token.strip()
    if not value:
        return "", 0

    left = value.find("(")
    right = value.find(")")
    if left > 0 and right > left:
        pinyin_raw = value[:left]
        try:
            count = int(value[left + 1 : right])
        except ValueError:
            count = 0
    else:
        pinyin_raw = value
        count = 0

    return _normalize_pinyin_token(pinyin_raw), count


def _load_unihan_readings_detail(
    payload: bytes,
) -> Tuple[
    Dict[str, str],
    Dict[str, Set[str]],
    Dict[Tuple[str, str], int],
    Dict[str, int],
    Dict[Tuple[str, str], int],
]:
    mandarin_map: Dict[str, str] = {}
    readings_map: Dict[str, Set[str]] = {}
    source_rank_map: Dict[Tuple[str, str], int] = {}
    pinlu_map: Dict[str, int] = {}
    pinlu_detail_map: Dict[Tuple[str, str], int] = {}
    text = _read_unihan_readings_text(payload)
    if not text:
        return mandarin_map, readings_map, source_rank_map, pinlu_map, pinlu_detail_map

    pinlu_seen_chars: Set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) < 3:
            continue
        codepoint, field_name, value = parts[0], parts[1], parts[2]
        if field_name not in {"kMandarin", "kHanyuPinyin", "kHanyuPinlu"}:
            continue
        if not codepoint.startswith("U+"):
            continue

        try:
            ch = chr(int(codepoint[2:], 16))
        except ValueError:
            continue
        if not _is_windows_renderable_cjk_text(ch):
            continue

        if field_name == "kMandarin":
            if ch in pinlu_seen_chars:
                continue
            for part in value.split():
                normalized = _normalize_pinyin_token(part)
                if not normalized:
                    continue
                _add_unihan_reading(
                    readings_map,
                    source_rank_map,
                    ch,
                    normalized,
                    UNIHAN_SOURCE_MANDARIN,
                )
                if ch not in mandarin_map:
                    mandarin_map[ch] = normalized
            continue

        if field_name == "kHanyuPinyin":
            for part in value.replace(";", " ").split():
                rest = part.rsplit(":", 1)[-1]
                if not rest:
                    continue
                for pinyin_raw in rest.split(","):
                    normalized = _normalize_pinyin_token(pinyin_raw)
                    if not normalized:
                        continue
                    _add_unihan_reading(
                        readings_map,
                        source_rank_map,
                        ch,
                        normalized,
                        UNIHAN_SOURCE_HANYU_EXTRA,
                    )
                    if ch not in mandarin_map:
                        mandarin_map[ch] = normalized
            continue

        pinlu_seen_chars.add(ch)
        for part in value.split():
            normalized, pinlu_count = _parse_unihan_pinlu_token(part)
            if not normalized:
                continue
            _add_unihan_reading(
                readings_map,
                source_rank_map,
                ch,
                normalized,
                UNIHAN_SOURCE_PINLU,
            )
            if ch not in mandarin_map:
                mandarin_map[ch] = normalized
            if pinlu_count > 0:
                previous = pinlu_map.get(ch, 0)
                if pinlu_count > previous:
                    pinlu_map[ch] = pinlu_count
                detail_key = (ch, normalized)
                previous_detail = pinlu_detail_map.get(detail_key, 0)
                if pinlu_count > previous_detail:
                    pinlu_detail_map[detail_key] = pinlu_count

    # Modern pinyin input treats "en" as the primary spelling for this
    # interjection even when Unihan happens to list another reading first.
    _add_unihan_reading(
        readings_map,
        source_rank_map,
        "嗯",
        "en",
        UNIHAN_SOURCE_PINLU,
    )
    mandarin_map["嗯"] = "en"

    for override_char, override_pinyin, min_detail in (
        ("\u5e62", "zhuang", 1),  # 幢
        ("\u723f", "pan", 12),    # 爿
        ("\u723f", "qiang", 8),   # 爿
        ("\u719f", "shou", 1),    # 熟
        ("\u98a4", "zhan", 1),    # 颤
        ("\u85cf", "zang", 1),    # 藏
        ("\u5265", "bao", 1),     # 剥
        ("\u54ea", "nei", 1),     # 哪
        ("\u5594", "wo", 1),      # 喔
        ("\u54af", "lo", 1),      # 咯（句末语气词）
        ("\u54af", "ka", 1),      # 咯（咯血等）
        ("\u54af", "luo", 1),     # 咯（咯血等）
    ):
        _add_unihan_reading(
            readings_map,
            source_rank_map,
            override_char,
            override_pinyin,
            UNIHAN_SOURCE_PINLU,
        )
        if pinlu_detail_map.get((override_char, override_pinyin), 0) < min_detail:
            pinlu_detail_map[(override_char, override_pinyin)] = min_detail

    return mandarin_map, readings_map, source_rank_map, pinlu_map, pinlu_detail_map


def _load_unihan_mandarin_map(payload: bytes) -> Dict[str, str]:
    mandarin_map, _readings_map, _source_rank_map, _pinlu_map, _pinlu_detail_map = _load_unihan_readings_detail(
        payload
    )
    return mandarin_map


def _select_unihan_output_readings(
    ch: str,
    pinyin_set: Set[str],
    source_rank_map: Dict[Tuple[str, str], int],
    mandarin_map: Dict[str, str],
    pinlu_detail_map: Dict[Tuple[str, str], int],
) -> List[str]:
    def reading_sort_key(pinyin: str) -> Tuple[int, int, int, str]:
        return (
            1 if pinyin == mandarin_map.get(ch, "") else 0,
            pinlu_detail_map.get((ch, pinyin), 0),
            source_rank_map.get((ch, pinyin), 0),
            pinyin,
        )

    if not pinyin_set:
        return []

    # Only inject mainstream single-character readings into final dictionaries.
    # Keep Mandarin / Pinlu-backed readings first; HanyuPinyin extras are used
    # only as a last-resort fallback to preserve minimal coverage.
    preferred = sorted(
        [pinyin for pinyin in pinyin_set if source_rank_map.get((ch, pinyin), 0) >= UNIHAN_SOURCE_MANDARIN],
        key=reading_sort_key,
        reverse=True,
    )
    if preferred:
        return preferred

    mandarin = mandarin_map.get(ch, "")
    if mandarin and mandarin in pinyin_set:
        return [mandarin]

    highest_rank = max(source_rank_map.get((ch, pinyin), 0) for pinyin in pinyin_set)
    fallback = sorted(
        (pinyin for pinyin in pinyin_set if source_rank_map.get((ch, pinyin), 0) == highest_rank),
        key=reading_sort_key,
        reverse=True,
    )
    if not fallback:
        return []
    return [fallback[0]]


def _parse_unihan_pinlu_count(value: str) -> int:
    max_count = 0
    for matched in re.finditer(r"\((\d+)\)", value):
        try:
            count = int(matched.group(1))
        except ValueError:
            continue
        if count > max_count:
            max_count = count
    return max_count


def _load_unihan_pinlu_map(payload: bytes) -> Dict[str, int]:
    _mandarin_map, _readings_map, _source_rank_map, pinlu_map, _pinlu_detail_map = _load_unihan_readings_detail(
        payload
    )
    return pinlu_map


def _adjust_unihan_weight_for_reading(
    weight: int,
    ch: str,
    pinyin: str,
    source_rank: int,
    mandarin_map: Dict[str, str],
    pinlu_detail_map: Dict[Tuple[str, str], int],
    max_pinlu_freq: int,
) -> int:
    adjusted = _adjust_unihan_weight_for_source(weight, source_rank)
    reading_pinlu = pinlu_detail_map.get((ch, pinyin), 0)
    is_primary = mandarin_map.get(ch, "") == pinyin

    if max_pinlu_freq > 0:
        if reading_pinlu <= 0:
            if not is_primary:
                adjusted -= 110
        else:
            ratio = reading_pinlu / max_pinlu_freq
            if ratio < 0.05:
                adjusted -= 128
            elif ratio < 0.15:
                adjusted -= 92
            elif ratio < 0.40:
                adjusted -= 56
            elif ratio < 0.75:
                adjusted -= 24

            if (not is_primary) and (reading_pinlu * 6 < max_pinlu_freq):
                adjusted -= 36
            if (not is_primary) and (reading_pinlu > 0):
                dominance_ratio = max_pinlu_freq / reading_pinlu
                if max_pinlu_freq >= 240 and dominance_ratio >= 10.0:
                    adjusted -= 20
                if max_pinlu_freq >= 600 and dominance_ratio >= 16.0:
                    adjusted -= 20
                if max_pinlu_freq >= 1000 and dominance_ratio >= 20.0:
                    adjusted -= 24
            if is_primary:
                adjusted += 8
    elif not is_primary:
        adjusted -= 48

    if adjusted < 70:
        return 70
    if adjusted > 620:
        return 620
    return adjusted


def _compute_unihan_single_char_reading_delta(
    ch: str,
    pinyin: str,
    readings_map: Dict[str, Set[str]] | None,
    mandarin_map: Dict[str, str] | None,
    pinlu_map: Dict[str, int] | None,
    pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    phrase_term_count_map: Dict[Tuple[str, str], int] | None = None,
    phrase_support_sum_map: Dict[Tuple[str, str], float] | None = None,
    leading_term_count_map: Dict[Tuple[str, str], int] | None = None,
    leading_support_sum_map: Dict[Tuple[str, str], float] | None = None,
) -> int:
    if (ch, pinyin) in SINGLE_CHAR_READING_DELTA_OVERRIDES:
        return SINGLE_CHAR_READING_DELTA_OVERRIDES[(ch, pinyin)]

    readings_map = readings_map or {}
    mandarin_map = mandarin_map or {}
    pinlu_map = pinlu_map or {}
    pinlu_detail_map = pinlu_detail_map or {}
    phrase_term_count_map = phrase_term_count_map or {}
    phrase_support_sum_map = phrase_support_sum_map or {}
    leading_term_count_map = leading_term_count_map or {}
    leading_support_sum_map = leading_support_sum_map or {}

    if not ch or _cjk_len(ch) != 1 or not pinyin:
        return 0

    if len(readings_map.get(ch, set())) < 2:
        return 0

    max_pinlu_freq = max(0, pinlu_map.get(ch, 0))
    reading_pinlu = max(0, pinlu_detail_map.get((ch, pinyin), 0))
    is_primary = mandarin_map.get(ch, "") == pinyin
    phrase_term_count = max(0, phrase_term_count_map.get((ch, pinyin), 0))
    phrase_support = max(0.0, phrase_support_sum_map.get((ch, pinyin), 0.0))
    leading_term_count = max(0, leading_term_count_map.get((ch, pinyin), 0))
    leading_support = max(0.0, leading_support_sum_map.get((ch, pinyin), 0.0))
    leading_ratio = leading_support / max(1.0, phrase_support) if phrase_support > 0.0 else 0.0
    best_phrase_reading = ""
    best_phrase_term_count = 0
    best_phrase_support = 0.0
    second_phrase_term_count = 0
    second_phrase_support = 0.0
    for reading in readings_map.get(ch, set()):
        current_term_count = max(0, phrase_term_count_map.get((ch, reading), 0))
        current_support = max(0.0, phrase_support_sum_map.get((ch, reading), 0.0))
        if (current_support > best_phrase_support) or (
            current_support == best_phrase_support and current_term_count > best_phrase_term_count
        ):
            second_phrase_term_count = best_phrase_term_count
            second_phrase_support = best_phrase_support
            best_phrase_reading = reading
            best_phrase_term_count = current_term_count
            best_phrase_support = current_support
        elif (current_support > second_phrase_support) or (
            current_support == second_phrase_support and current_term_count > second_phrase_term_count
        ):
            second_phrase_term_count = current_term_count
            second_phrase_support = current_support

    phrase_preferred_reading = ""
    if max_pinlu_freq > 0:
        phrase_preferred_threshold_ok = (
            best_phrase_support >= 320.0
            and best_phrase_term_count >= 4
            and (
                best_phrase_support >= max(220.0, second_phrase_support * 1.6)
                or best_phrase_term_count >= max(4, second_phrase_term_count + 4)
            )
        )
    else:
        phrase_preferred_threshold_ok = (
            best_phrase_support >= 120.0
            and best_phrase_term_count >= 3
            and (
                second_phrase_support <= 0.0
                or (
                    best_phrase_support >= second_phrase_support * 1.05
                    and best_phrase_term_count >= second_phrase_term_count + 2
                )
                or best_phrase_support >= second_phrase_support + 36.0
            )
        )

    if best_phrase_reading and phrase_preferred_threshold_ok:
        phrase_preferred_reading = best_phrase_reading

    if phrase_preferred_reading:
        if max_pinlu_freq <= 0:
            if pinyin == phrase_preferred_reading:
                return 180 if not is_primary else 40
            if phrase_support <= 0.0 or phrase_term_count <= 0:
                return -140
            return -96

        if pinyin == phrase_preferred_reading:
            return 260 if not is_primary else 40

        # A secondary reading can still be independently common even when
        # another pronunciation has broader aggregate phrase coverage.
        reading_ratio = reading_pinlu / max(1, max_pinlu_freq)
        established_secondary_reading = (
            not is_primary
            and reading_pinlu >= 40
            and reading_pinlu <= 100
            and reading_ratio >= 0.12
            and phrase_term_count >= 24
            and phrase_support >= 1800.0
            and leading_term_count >= 10
            and leading_support >= 700.0
            and leading_ratio >= 0.60
        )
        if established_secondary_reading:
            if (
                phrase_term_count >= 30
                and phrase_support >= 3000.0
                and leading_term_count >= 12
                and leading_support >= 1000.0
            ):
                return 96
            return 64

        if phrase_support <= 0.0 or phrase_term_count <= 0:
            return -220

        phrase_ratio = phrase_support / max(1.0, best_phrase_support)
        if is_primary:
            if (
                leading_support >= 900.0
                or (leading_ratio >= 0.45 and leading_term_count >= 6)
                or (reading_pinlu >= 3000 and leading_term_count >= 10)
            ):
                if phrase_ratio >= 0.60:
                    return -36
                return -72
            if phrase_ratio < 0.55:
                return -380
            if phrase_ratio < 0.70:
                return -280
            return -180
        if phrase_ratio < 0.55:
            return -180
        return -96

    if max_pinlu_freq <= 0:
        return 0 if is_primary else -42

    delta = 0

    if is_primary:
        return delta

    if reading_pinlu <= 0:
        return delta - 180

    ratio = reading_pinlu / max_pinlu_freq
    dominance_ratio = max_pinlu_freq / max(1, reading_pinlu)
    if ratio < 0.05:
        delta -= 180
    elif ratio < 0.12:
        delta -= 148
    elif ratio < 0.25:
        delta -= 112
    elif ratio < 0.50:
        delta -= 72
    elif ratio < 0.75:
        delta -= 36

    if dominance_ratio >= 8.0:
        delta -= 20
    if dominance_ratio >= 16.0:
        delta -= 20

    return delta


def _load_unihan_dictlike_maps(
    payload: bytes,
) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]:
    freq_map: Dict[str, int] = {}
    grade_map: Dict[str, int] = {}
    core_map: Dict[str, int] = {}
    if not payload.startswith(b"PK"):
        return freq_map, grade_map, core_map

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        target_name = ""
        for name in zf.namelist():
            if name.endswith("Unihan_DictionaryLikeData.txt"):
                target_name = name
                break
        if not target_name:
            return freq_map, grade_map, core_map

        text = zf.read(target_name).decode("utf-8", errors="ignore")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        codepoint, field_name, value = parts[0], parts[1], parts[2]
        if not codepoint.startswith("U+"):
            continue

        try:
            ch = chr(int(codepoint[2:], 16))
        except ValueError:
            continue
        if not _is_windows_renderable_cjk_text(ch):
            continue

        if field_name == "kFrequency":
            try:
                freq = int(value.strip())
            except ValueError:
                continue
            if freq > 0:
                freq_map[ch] = freq
        elif field_name == "kGradeLevel":
            try:
                grade = int(value.strip())
            except ValueError:
                continue
            if grade > 0:
                grade_map[ch] = grade
        elif field_name == "kUnihanCore2020":
            coverage = 0
            for ch_value in value:
                if ("A" <= ch_value <= "Z") or ("a" <= ch_value <= "z"):
                    coverage += 1
            if coverage > 0:
                core_map[ch] = coverage

    return freq_map, grade_map, core_map


def _load_unihan_simplified_variant_map(payload: bytes) -> Dict[str, str]:
    variant_map: Dict[str, str] = {}
    if not payload.startswith(b"PK"):
        return variant_map

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        target_name = ""
        for name in zf.namelist():
            if name.endswith("Unihan_Variants.txt"):
                target_name = name
                break
        if not target_name:
            return variant_map
        text = zf.read(target_name).decode("utf-8", errors="ignore")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        codepoint, field_name, value = parts[0], parts[1], parts[2]
        if field_name != "kSimplifiedVariant":
            continue
        if not codepoint.startswith("U+"):
            continue

        try:
            trad_ch = chr(int(codepoint[2:], 16))
        except ValueError:
            continue
        if not _is_windows_renderable_cjk_text(trad_ch):
            continue

        simp_ch = ""
        for token in value.split():
            token = token.strip()
            if not token.startswith("U+"):
                continue
            try:
                candidate = chr(int(token[2:], 16))
            except ValueError:
                continue
            if not _is_windows_renderable_cjk_text(candidate):
                continue
            # Prefer an actual variant target instead of same-character echo.
            if candidate == trad_ch:
                continue
            simp_ch = candidate
            break
        if not simp_ch:
            continue

        if trad_ch not in variant_map:
            variant_map[trad_ch] = simp_ch

    return variant_map


def _load_unihan_traditional_variant_map(payload: bytes) -> Dict[str, str]:
    variant_map: Dict[str, str] = {}
    if not payload.startswith(b"PK"):
        return variant_map

    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        target_name = ""
        for name in zf.namelist():
            if name.endswith("Unihan_Variants.txt"):
                target_name = name
                break
        if not target_name:
            return variant_map
        text = zf.read(target_name).decode("utf-8", errors="ignore")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        codepoint, field_name, value = parts[0], parts[1], parts[2]
        if field_name != "kTraditionalVariant":
            continue
        if not codepoint.startswith("U+"):
            continue

        try:
            simp_ch = chr(int(codepoint[2:], 16))
        except ValueError:
            continue
        if not _is_windows_renderable_cjk_text(simp_ch):
            continue

        trad_ch = ""
        for token in value.split():
            token = token.strip()
            if not token.startswith("U+"):
                continue
            try:
                candidate = chr(int(token[2:], 16))
            except ValueError:
                continue
            if not _is_windows_renderable_cjk_text(candidate):
                continue
            # Prefer an actual variant target instead of same-character echo.
            if candidate == simp_ch:
                continue
            trad_ch = candidate
            break
        if not trad_ch:
            continue

        if simp_ch not in variant_map:
            variant_map[simp_ch] = trad_ch

    return variant_map


def _unihan_weight_from_frequency(freq: int) -> int:
    if freq == 1:
        return 118
    if freq == 2:
        return 86
    if freq == 3:
        return 60
    if freq == 4:
        return 38
    if freq == 5:
        return 22
    return 0


def _unihan_weight_from_pinlu(freq: int) -> int:
    if freq <= 0:
        return 0
    ratio = min(1.0, math.log1p(freq) / math.log1p(30000.0))
    return 32 + int(round(ratio * 328))


def _unihan_weight_from_grade(grade: int) -> int:
    if grade == 1:
        return 52
    if grade == 2:
        return 42
    if grade == 3:
        return 34
    if grade == 4:
        return 26
    if grade == 5:
        return 18
    if grade == 6:
        return 12
    return 0


def _unihan_weight_from_core(coverage: int) -> int:
    if coverage <= 0:
        return 0
    capped = min(coverage, 7)
    return 5 + capped * 4


def _compute_unihan_single_char_weight(
    freq: int,
    pinlu_freq: int,
    grade_level: int,
    core_coverage: int,
) -> int:
    weight = 56
    if pinlu_freq > 0:
        weight += _unihan_weight_from_pinlu(pinlu_freq)
    else:
        # Keep non-pinlu characters available with conservative baseline.
        weight += 8
    if freq > 0:
        weight += _unihan_weight_from_frequency(freq)
    if grade_level > 0:
        grade_bonus = _unihan_weight_from_grade(grade_level)
        if pinlu_freq > 0:
            grade_bonus = grade_bonus // 3
        weight += grade_bonus
    if core_coverage > 0:
        core_bonus = _unihan_weight_from_core(core_coverage)
        if pinlu_freq > 0:
            core_bonus = core_bonus // 2
        weight += core_bonus

    if weight < 56:
        return 56
    if weight > 540:
        return 540
    return weight


def _load_char_family_support_from_generated_dict(
    path: pathlib.Path | None,
    exclude_texts: Set[str] | None = None,
) -> Tuple[Dict[str, int], Dict[str, float]]:
    term_count_map: Dict[str, int] = {}
    support_sum_map: Dict[str, float] = {}
    if path is None or (not path.exists()):
        return term_count_map, support_sum_map

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) not in {3, 4}:
                continue

            text = parts[1].strip()
            if _cjk_len(text) < 2 or not CJK_FULL_RE.fullmatch(text):
                continue
            if exclude_texts and text in exclude_texts:
                continue
            if _is_productive_suffix_support_phrase(text):
                continue

            try:
                weight = int(parts[2].strip())
            except ValueError:
                continue

            unique_chars: Set[str] = set()
            for ch in _split_text_units(text):
                if _cjk_len(ch) != 1 or not CJK_FULL_RE.fullmatch(ch):
                    continue
                unique_chars.add(ch)
            if not unique_chars:
                continue

            support = max(12.0, min(220.0, float(weight) * 0.16))
            text_len = _cjk_len(text)
            if text_len >= 4:
                support *= 0.82
            if text_len >= 6:
                support *= 0.72

            for ch in unique_chars:
                term_count_map[ch] = term_count_map.get(ch, 0) + 1
                support_sum_map[ch] = support_sum_map.get(ch, 0.0) + support

    return term_count_map, support_sum_map


PRODUCTIVE_SUFFIX_SUPPORT_CHARS = frozenset(
    {
        "\u4e86",  # le/liao
        "\u7740",  # zhe
        "\u7684",  # de
        "\u5f97",  # de/dei
        "\u5427",  # ba
        "\u5417",  # ma
        "\u5566",  # la
        "\u554a",  # a
    }
)


def _is_productive_suffix_support_phrase(text: str) -> bool:
    units = _split_text_units(text)
    return len(units) == 2 and units[1] in PRODUCTIVE_SUFFIX_SUPPORT_CHARS


def _collect_unihan_constituent_reading_alignments(
    text: str,
    pinyin: str,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_mandarin_map: Dict[str, str] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    max_alignments: int = 16,
) -> List[Tuple[str, ...]]:
    if not PINYIN_RE.fullmatch(pinyin):
        return []

    units = _split_text_units(text)
    if len(units) < 2 or len(units) > 8:
        return []
    if len(pinyin) < len(units):
        return []

    unit_readings: List[List[str]] = []
    for ch in units:
        readings = _collect_preferred_unihan_readings(
            ch,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_mandarin_map,
            unihan_pinlu_detail_map,
        )
        if not readings:
            return []
        unit_readings.append(readings[:4])

    alignments: List[Tuple[str, ...]] = []
    current: List[str] = []

    def walk(unit_idx: int, offset: int) -> None:
        if len(alignments) >= max_alignments:
            return
        if unit_idx >= len(unit_readings):
            if offset == len(pinyin):
                alignments.append(tuple(current))
            return
        if offset >= len(pinyin):
            return

        for reading in unit_readings[unit_idx]:
            if not pinyin.startswith(reading, offset):
                continue
            current.append(reading)
            walk(unit_idx + 1, offset + len(reading))
            current.pop()
            if len(alignments) >= max_alignments:
                return

    walk(0, 0)
    return alignments


def _looks_like_single_pinyin_syllable(value: str) -> bool:
    if not PINYIN_RE.fullmatch(value):
        return False
    if len(value) < 1 or len(value) > 6:
        return False
    if not any(ch in value for ch in "aeiouv"):
        return False
    return True


def _collect_unihan_single_gap_reading_candidates(
    text: str,
    pinyin: str,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_mandarin_map: Dict[str, str] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    max_alignments: int = 64,
) -> List[Tuple[str, str]]:
    if not PINYIN_RE.fullmatch(pinyin):
        return []

    units = _split_text_units(text)
    if len(units) < 2 or len(units) > 8:
        return []
    if len(pinyin) < len(units):
        return []

    unihan_readings_map = unihan_readings_map or {}
    unit_readings: List[List[str]] = []
    for ch in units:
        readings = _collect_preferred_unihan_readings(
            ch,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_mandarin_map,
            unihan_pinlu_detail_map,
        )
        unit_readings.append(readings[:4])

    candidates: List[Tuple[str, str]] = []
    seen_candidates: Set[Tuple[str, str]] = set()
    for gap_idx, gap_char in enumerate(units):
        if not gap_char or _cjk_len(gap_char) != 1:
            continue
        if not unihan_readings_map.get(gap_char):
            continue
        if any(not readings for idx, readings in enumerate(unit_readings) if idx != gap_idx):
            continue

        alignments: List[Tuple[str, ...]] = []
        current: List[str] = []
        truncated = False

        def walk(unit_idx: int, offset: int) -> None:
            nonlocal truncated
            if truncated:
                return
            if len(alignments) >= max_alignments:
                truncated = True
                return
            if unit_idx >= len(units):
                if offset == len(pinyin):
                    alignments.append(tuple(current))
                return
            if offset >= len(pinyin):
                return

            if unit_idx == gap_idx:
                remaining_units = len(units) - unit_idx - 1
                max_end = min(len(pinyin) - remaining_units, offset + 6)
                for end in range(offset + 1, max_end + 1):
                    inferred = pinyin[offset:end]
                    if not _looks_like_single_pinyin_syllable(inferred):
                        continue
                    current.append(inferred)
                    walk(unit_idx + 1, end)
                    current.pop()
                    if truncated:
                        return
                return

            for reading in unit_readings[unit_idx]:
                if not pinyin.startswith(reading, offset):
                    continue
                current.append(reading)
                walk(unit_idx + 1, offset + len(reading))
                current.pop()
                if truncated:
                    return

        walk(0, 0)
        if truncated or not alignments:
            continue

        gap_readings = {alignment[gap_idx] for alignment in alignments}
        if len(gap_readings) != 1:
            continue
        inferred = next(iter(gap_readings))

        pair = (gap_char, inferred)
        if pair in seen_candidates:
            continue
        seen_candidates.add(pair)
        candidates.append(pair)

    return candidates


def _load_char_reading_support_from_generated_dict(
    path: pathlib.Path | None,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_mandarin_map: Dict[str, str] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    exclude_texts: Set[str] | None = None,
) -> Tuple[Dict[Tuple[str, str], int], Dict[Tuple[str, str], float]]:
    term_count_map: Dict[Tuple[str, str], int] = {}
    support_sum_map: Dict[Tuple[str, str], float] = {}
    if path is None or (not path.exists()):
        return term_count_map, support_sum_map

    unihan_readings_map = unihan_readings_map or {}
    if not unihan_readings_map:
        return term_count_map, support_sum_map

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) not in {3, 4}:
                continue

            pinyin = parts[0].strip()
            text = parts[1].strip()
            if _cjk_len(text) < 2 or not CJK_FULL_RE.fullmatch(text):
                continue
            if exclude_texts and text in exclude_texts:
                continue
            if _is_productive_suffix_support_phrase(text):
                continue

            units = _split_text_units(text)
            if not any(len(unihan_readings_map.get(ch, set())) >= 2 for ch in units):
                continue

            try:
                weight = int(parts[2].strip())
            except ValueError:
                continue

            alignments = _collect_unihan_constituent_reading_alignments(
                text,
                pinyin,
                unihan_readings_map,
                unihan_source_rank_map,
                unihan_mandarin_map,
                unihan_pinlu_detail_map,
            )
            if not alignments:
                continue

            support = max(12.0, min(220.0, float(weight) * 0.16))
            text_len = _cjk_len(text)
            if text_len >= 4:
                support *= 0.82
            if text_len >= 6:
                support *= 0.72

            seen_pairs: Set[Tuple[str, str]] = set()
            for idx, ch in enumerate(units):
                if len(unihan_readings_map.get(ch, set())) < 2:
                    continue
                aligned_readings = {alignment[idx] for alignment in alignments}
                if len(aligned_readings) != 1:
                    continue
                reading = next(iter(aligned_readings))
                pair = (ch, reading)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                term_count_map[pair] = term_count_map.get(pair, 0) + 1
                support_sum_map[pair] = support_sum_map.get(pair, 0.0) + support

    return term_count_map, support_sum_map


def _load_char_inferred_reading_support_from_generated_dict(
    path: pathlib.Path | None,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_mandarin_map: Dict[str, str] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    exclude_texts: Set[str] | None = None,
) -> Tuple[Dict[Tuple[str, str], int], Dict[Tuple[str, str], float]]:
    term_count_map: Dict[Tuple[str, str], int] = {}
    support_sum_map: Dict[Tuple[str, str], float] = {}
    if path is None or (not path.exists()):
        return term_count_map, support_sum_map

    unihan_readings_map = unihan_readings_map or {}
    if not unihan_readings_map:
        return term_count_map, support_sum_map

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) not in {3, 4}:
                continue

            pinyin = parts[0].strip()
            text = parts[1].strip()
            if _cjk_len(text) < 2 or not CJK_FULL_RE.fullmatch(text):
                continue
            if exclude_texts and text in exclude_texts:
                continue
            if _is_productive_suffix_support_phrase(text):
                continue

            try:
                weight = int(parts[2].strip())
            except ValueError:
                continue

            candidates = _collect_unihan_single_gap_reading_candidates(
                text,
                pinyin,
                unihan_readings_map,
                unihan_source_rank_map,
                unihan_mandarin_map,
                unihan_pinlu_detail_map,
            )
            if not candidates:
                continue

            support = max(12.0, min(220.0, float(weight) * 0.16))
            text_len = _cjk_len(text)
            if text_len >= 4:
                support *= 0.82
            if text_len >= 6:
                support *= 0.72

            seen_pairs: Set[Tuple[str, str]] = set()
            for pair in candidates:
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                term_count_map[pair] = term_count_map.get(pair, 0) + 1
                support_sum_map[pair] = support_sum_map.get(pair, 0.0) + support

    return term_count_map, support_sum_map


def _load_char_leading_reading_support_from_generated_dict(
    path: pathlib.Path | None,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_mandarin_map: Dict[str, str] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    exclude_texts: Set[str] | None = None,
) -> Tuple[Dict[Tuple[str, str], int], Dict[Tuple[str, str], float]]:
    term_count_map: Dict[Tuple[str, str], int] = {}
    support_sum_map: Dict[Tuple[str, str], float] = {}
    if path is None or (not path.exists()):
        return term_count_map, support_sum_map

    unihan_readings_map = unihan_readings_map or {}
    if not unihan_readings_map:
        return term_count_map, support_sum_map

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) not in {3, 4}:
                continue

            pinyin = parts[0].strip()
            text = parts[1].strip()
            if _cjk_len(text) < 2 or not CJK_FULL_RE.fullmatch(text):
                continue
            if exclude_texts and text in exclude_texts:
                continue
            if _is_productive_suffix_support_phrase(text):
                continue

            first_char = text[0]
            if len(unihan_readings_map.get(first_char, set())) < 1:
                continue

            try:
                weight = int(parts[2].strip())
            except ValueError:
                continue

            alignments = _collect_unihan_constituent_reading_alignments(
                text,
                pinyin,
                unihan_readings_map,
                unihan_source_rank_map,
                unihan_mandarin_map,
                unihan_pinlu_detail_map,
            )
            if not alignments:
                continue

            first_readings = {alignment[0] for alignment in alignments}
            if len(first_readings) != 1:
                continue
            first_reading = next(iter(first_readings))

            support = max(12.0, min(220.0, float(weight) * 0.16))
            text_len = _cjk_len(text)
            if text_len >= 4:
                support *= 0.82
            if text_len >= 6:
                support *= 0.72

            pair = (first_char, first_reading)
            term_count_map[pair] = term_count_map.get(pair, 0) + 1
            support_sum_map[pair] = support_sum_map.get(pair, 0.0) + support

    return term_count_map, support_sum_map


def _compute_unihan_family_support_bonus(
    ch: str,
    *,
    term_count_map: Dict[str, int] | None,
    support_sum_map: Dict[str, float] | None,
    base_weight: int,
) -> int:
    term_count = 0 if not term_count_map else term_count_map.get(ch, 0)
    support_sum = 0.0 if not support_sum_map else support_sum_map.get(ch, 0.0)
    if term_count < 2 and support_sum < 80.0:
        return 0

    count_bonus = min(72, int(round(math.log1p(term_count) * 16.0)))
    if term_count >= 3:
        count_bonus += 6
    if term_count >= 8:
        count_bonus += 8
    if base_weight <= 90 and term_count >= 3:
        count_bonus += 14
    if base_weight <= 90 and term_count >= 8:
        count_bonus += 10

    support_bonus = min(48, int(round(math.sqrt(max(0.0, support_sum)) * 1.4)))
    bonus = count_bonus + support_bonus

    if base_weight >= 220:
        bonus = int(round(bonus * 0.35))
    elif base_weight >= 150:
        bonus = int(round(bonus * 0.55))
    elif base_weight >= 100:
        bonus = int(round(bonus * 0.75))

    return max(0, min(110, bonus))


def _compute_phrase_inferred_single_char_reading_weight(
    base_weight: int,
    term_count: int,
    support_sum: float,
) -> int:
    count_bonus = min(70, int(round(math.log1p(max(0, term_count)) * 22.0)))
    support_bonus = min(90, int(round(math.sqrt(max(0.0, support_sum)) * 4.0)))
    weight = base_weight - 28 + count_bonus + support_bonus
    return max(90, min(620, weight))


def _is_strong_phrase_inferred_single_char_reading(
    term_count: int,
    support_sum: float,
    source_rank: int,
) -> bool:
    if source_rank > 0 and term_count >= 8 and support_sum >= 520.0:
        return True
    if source_rank > 0 and term_count >= 12 and support_sum >= 360.0:
        return True
    if source_rank <= 0 and term_count >= 12 and support_sum >= 760.0:
        return True
    return False


def _adjust_unihan_weight_for_source(weight: int, source_rank: int) -> int:
    adjusted = weight
    if source_rank >= UNIHAN_SOURCE_PINLU:
        adjusted += 18
    elif source_rank == UNIHAN_SOURCE_MANDARIN:
        adjusted += 6
    else:
        adjusted -= 92

    if source_rank <= UNIHAN_SOURCE_HANYU_EXTRA:
        adjusted = min(adjusted, UNIHAN_HANYU_EXTRA_WEIGHT_CAP)

    if adjusted < 70:
        return 70
    if adjusted > 620:
        return 620
    return adjusted


def _load_pinyin_overrides(path: pathlib.Path) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    content = path.read_text(encoding="utf-8")
    for line_no, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            raise ValueError(
                f"invalid override format at {path}:{line_no}, expected text<TAB>pinyin"
            )

        text = parts[0].strip()
        if _cjk_len(text) <= 0:
            raise ValueError(
                f"invalid override text at {path}:{line_no}, expected CJK text: '{text}'"
            )

        pinyin = _normalize_explicit_pinyin(parts[1])
        if not pinyin:
            raise ValueError(
                f"invalid override pinyin at {path}:{line_no}: '{parts[1]}'"
            )

        previous = overrides.get(text, "")
        if previous and previous != pinyin:
            raise ValueError(
                f"conflicting override at {path}:{line_no} for '{text}': '{previous}' vs '{pinyin}'"
            )
        overrides[text] = pinyin

    return overrides


def _pinyin_from_unihan(
    text: str,
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]] | None = None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None = None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None = None,
) -> str:
    syllables: List[str] = []
    if (
        _cjk_len(text) > 1
        and unihan_readings_map is not None
        and unihan_source_rank_map is not None
        and unihan_pinlu_detail_map is not None
    ):
        derived = _best_unihan_pinyin_syllables(
            text,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if derived is None:
            return ""
        syllables = derived
    else:
        for ch in text:
            if not CJK_RE.match(ch):
                return ""
            py = unihan_map.get(ch, "")
            if not py:
                return ""
            syllables.append(py)

    merged = "".join(syllables)
    if not PINYIN_RE.fullmatch(merged):
        return ""
    return merged


def _build_from_opencc_unihan(
    opencc_text: str,
    unihan_payload: bytes,
    min_hanzi: int,
    overrides: Dict[str, str],
) -> Tuple[Dict[Tuple[str, str], int], Dict[Tuple[str, str], int], Dict[str, int]]:
    sc: Dict[Tuple[str, str], int] = {}
    tc: Dict[Tuple[str, str], int] = {}
    opencc_entries, stats = _parse_opencc_entries(opencc_text, min_hanzi)
    sc_terms = {sc_word for sc_word, _tc_word in opencc_entries}
    tc_terms = {tc_word for _sc_word, tc_word in opencc_entries}
    (
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_map,
        unihan_pinlu_detail_map,
    ) = _load_unihan_readings_detail(unihan_payload)
    unihan_freq_map, unihan_grade_map, unihan_core_map = _load_unihan_dictlike_maps(unihan_payload)
    stats["unihan_map_size"] = len(unihan_map)
    stats["unihan_readings_chars"] = len(unihan_readings_map)
    stats["unihan_readings_pairs"] = sum(len(values) for values in unihan_readings_map.values())
    stats["unihan_pinlu_size"] = len(unihan_pinlu_map)
    stats["unihan_frequency_size"] = len(unihan_freq_map)
    stats["unihan_grade_size"] = len(unihan_grade_map)
    stats["unihan_core_size"] = len(unihan_core_map)
    stats["invalid_pinyin"] = 0
    stats["override_entries"] = len(overrides)
    stats["override_hits"] = 0
    stats["fallback_hits"] = 0
    stats["override_injected"] = 0
    stats["unihan_single_char_injected_sc"] = 0
    stats["unihan_single_char_injected_tc"] = 0

    for sc_word, tc_word in opencc_entries:
        for text, bucket in ((sc_word, sc), (tc_word, tc)):
            if _cjk_len(text) < min_hanzi:
                continue
            pinyin = overrides.get(text, "")
            if pinyin:
                stats["override_hits"] += 1
            else:
                pinyin = _pinyin_from_unihan(
                    text,
                    unihan_map,
                    unihan_readings_map,
                    unihan_reading_source_map,
                    unihan_pinlu_detail_map,
                )
                if pinyin:
                    stats["fallback_hits"] += 1
            if not pinyin:
                stats["invalid_pinyin"] += 1
                continue

            key = (pinyin, text)
            weight = _compute_weight(text)
            previous = bucket.get(key, 0)
            if weight > previous:
                bucket[key] = weight

    # Ensure override entries are included even when source phrase lists do not contain them.
    for text, pinyin in overrides.items():
        if _cjk_len(text) < min_hanzi:
            continue
        key = (pinyin, text)
        # Explicit overrides should be easier to surface in top candidates.
        weight = min(1000, _compute_weight(text) + 80)
        if (text in sc_terms) and (text not in tc_terms):
            target_buckets = (sc,)
        elif (text in tc_terms) and (text not in sc_terms):
            target_buckets = (tc,)
        elif (text in sc_terms) and (text in tc_terms):
            target_buckets = (sc,)
        else:
            target_buckets = (sc, tc)

        for bucket in target_buckets:
            previous = bucket.get(key, 0)
            if weight > previous:
                bucket[key] = weight
                stats["override_injected"] += 1

    # Inject Unihan single-character entries when min_hanzi allows them.
    # This keeps single-char ranking logic centralized in lexicon pipeline.
    if min_hanzi <= 1:
        for ch, pinyin_set in unihan_readings_map.items():
            if _cjk_len(ch) != 1:
                continue
            if not pinyin_set:
                continue
            base_weight = _compute_unihan_single_char_weight(
                freq=unihan_freq_map.get(ch, 0),
                pinlu_freq=unihan_pinlu_map.get(ch, 0),
                grade_level=unihan_grade_map.get(ch, 0),
                core_coverage=unihan_core_map.get(ch, 0),
            )

            # Keep script buckets separated when OpenCC mapping is explicit.
            if (ch in sc_terms) and (ch not in tc_terms):
                target_buckets = (sc,)
            elif (ch in tc_terms) and (ch not in sc_terms):
                target_buckets = (tc,)
            else:
                target_buckets = (sc, tc)

            output_pinyin_set = _select_unihan_output_readings(
                ch,
                pinyin_set,
                unihan_reading_source_map,
                unihan_map,
                unihan_pinlu_detail_map,
            )
            for pinyin in output_pinyin_set:
                key = (pinyin, ch)
                source_rank = unihan_reading_source_map.get((ch, pinyin), UNIHAN_SOURCE_MANDARIN)
                output_weight = _adjust_unihan_weight_for_reading(
                    base_weight,
                    ch,
                    pinyin,
                    source_rank,
                    unihan_map,
                    unihan_pinlu_detail_map,
                    unihan_pinlu_map.get(ch, 0),
                )

                for bucket in target_buckets:
                    previous = bucket.get(key, 0)
                    if output_weight > previous:
                        bucket[key] = output_weight
                        if bucket is sc:
                            stats["unihan_single_char_injected_sc"] += 1
                        else:
                            stats["unihan_single_char_injected_tc"] += 1

    return sc, tc, stats


def _build_from_unihan_only(
    unihan_payload: bytes,
    min_hanzi: int,
    overrides: Dict[str, str],
    trad_to_simp_char_map: Dict[str, str],
    simp_to_trad_char_map: Dict[str, str],
    sc_chars: Set[str],
    tc_chars: Set[str],
    sc_family_term_count_map: Dict[str, int] | None = None,
    sc_family_support_sum_map: Dict[str, float] | None = None,
    tc_family_term_count_map: Dict[str, int] | None = None,
    tc_family_support_sum_map: Dict[str, float] | None = None,
    sc_inferred_reading_term_count_map: Dict[Tuple[str, str], int] | None = None,
    sc_inferred_reading_support_sum_map: Dict[Tuple[str, str], float] | None = None,
    tc_inferred_reading_term_count_map: Dict[Tuple[str, str], int] | None = None,
    tc_inferred_reading_support_sum_map: Dict[Tuple[str, str], float] | None = None,
) -> Tuple[Dict[Tuple[str, str], int], Dict[Tuple[str, str], int], Dict[str, int]]:
    sc: Dict[Tuple[str, str], int] = {}
    tc: Dict[Tuple[str, str], int] = {}
    (
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_map,
        unihan_pinlu_detail_map,
    ) = _load_unihan_readings_detail(unihan_payload)
    unihan_freq_map, unihan_grade_map, unihan_core_map = _load_unihan_dictlike_maps(unihan_payload)

    stats: Dict[str, int] = {
        "unihan_map_size": len(unihan_readings_map),
        "unihan_readings_chars": len(unihan_readings_map),
        "unihan_readings_pairs": sum(len(values) for values in unihan_readings_map.values()),
        "unihan_pinlu_size": len(unihan_pinlu_map),
        "unihan_frequency_size": len(unihan_freq_map),
        "unihan_grade_size": len(unihan_grade_map),
        "unihan_core_size": len(unihan_core_map),
        "override_entries": len(overrides),
        "override_hits": 0,
        "override_injected": 0,
        "unihan_single_char_injected_sc": 0,
        "unihan_single_char_injected_tc": 0,
        "unihan_tc_only_chars": 0,
        "unihan_sc_only_chars": 0,
        "unihan_family_support_boosted_sc": 0,
        "unihan_family_support_boosted_tc": 0,
        "unihan_phrase_inferred_reading_injected_sc": 0,
        "unihan_phrase_inferred_reading_injected_tc": 0,
    }

    tc_only_chars = tc_chars.difference(sc_chars)
    sc_only_chars = sc_chars.difference(tc_chars)

    if min_hanzi <= 1:
        for ch, pinyin_set in unihan_readings_map.items():
            if _cjk_len(ch) != 1:
                continue
            if not pinyin_set:
                continue

            base_weight = _compute_unihan_single_char_weight(
                freq=unihan_freq_map.get(ch, 0),
                pinlu_freq=unihan_pinlu_map.get(ch, 0),
                grade_level=unihan_grade_map.get(ch, 0),
                core_coverage=unihan_core_map.get(ch, 0),
            )
            sc_base_weight = min(
                620,
                base_weight
                + _compute_unihan_family_support_bonus(
                    ch,
                    term_count_map=sc_family_term_count_map,
                    support_sum_map=sc_family_support_sum_map,
                    base_weight=base_weight,
                ),
            )
            tc_base_weight = min(
                620,
                base_weight
                + _compute_unihan_family_support_bonus(
                    ch,
                    term_count_map=tc_family_term_count_map,
                    support_sum_map=tc_family_support_sum_map,
                    base_weight=base_weight,
                ),
            )
            if sc_base_weight > base_weight:
                stats["unihan_family_support_boosted_sc"] += 1
            if tc_base_weight > base_weight:
                stats["unihan_family_support_boosted_tc"] += 1

            output_pinyin_set = _select_unihan_output_readings(
                ch,
                pinyin_set,
                unihan_reading_source_map,
                unihan_map,
                unihan_pinlu_detail_map,
            )
            for pinyin in output_pinyin_set:
                source_rank = unihan_reading_source_map.get((ch, pinyin), UNIHAN_SOURCE_MANDARIN)
                sc_output_weight = _adjust_unihan_weight_for_reading(
                    sc_base_weight,
                    ch,
                    pinyin,
                    source_rank,
                    unihan_map,
                    unihan_pinlu_detail_map,
                    unihan_pinlu_map.get(ch, 0),
                )
                tc_output_weight = _adjust_unihan_weight_for_reading(
                    tc_base_weight,
                    ch,
                    pinyin,
                    source_rank,
                    unihan_map,
                    unihan_pinlu_detail_map,
                    unihan_pinlu_map.get(ch, 0),
                )
                key = (pinyin, ch)
                if ch in tc_only_chars:
                    previous_tc = tc.get(key, 0)
                    if tc_output_weight > previous_tc:
                        tc[key] = tc_output_weight
                        stats["unihan_single_char_injected_tc"] += 1
                        stats["unihan_tc_only_chars"] += 1
                elif ch in sc_only_chars:
                    previous_sc = sc.get(key, 0)
                    if sc_output_weight > previous_sc:
                        sc[key] = sc_output_weight
                        stats["unihan_single_char_injected_sc"] += 1
                        stats["unihan_sc_only_chars"] += 1
                else:
                    previous_sc = sc.get(key, 0)
                    if sc_output_weight > previous_sc:
                        sc[key] = sc_output_weight
                        stats["unihan_single_char_injected_sc"] += 1

                    previous_tc = tc.get(key, 0)
                    if tc_output_weight > previous_tc:
                        tc[key] = tc_output_weight
                        stats["unihan_single_char_injected_tc"] += 1

    def inject_phrase_inferred_readings(
        bucket: Dict[Tuple[str, str], int],
        term_count_map: Dict[Tuple[str, str], int] | None,
        support_sum_map: Dict[Tuple[str, str], float] | None,
        skip_chars: Set[str],
        stats_key: str,
    ) -> None:
        if min_hanzi > 1 or not term_count_map:
            return

        support_sum_map = support_sum_map or {}
        for ch, pinyin in sorted(term_count_map.keys()):
            if ch in skip_chars:
                continue
            if _cjk_len(ch) != 1 or not _is_windows_renderable_cjk_text(ch):
                continue
            if (ch, pinyin) in SINGLE_CHAR_READING_DROP_OVERRIDES:
                continue
            key = (pinyin, ch)
            if key in bucket:
                continue

            term_count = max(0, term_count_map.get((ch, pinyin), 0))
            support_sum = max(0.0, support_sum_map.get((ch, pinyin), 0.0))
            source_rank = unihan_reading_source_map.get((ch, pinyin), 0)
            if not _is_strong_phrase_inferred_single_char_reading(
                term_count,
                support_sum,
                source_rank,
            ):
                continue

            base_weight = _compute_unihan_single_char_weight(
                freq=unihan_freq_map.get(ch, 0),
                pinlu_freq=unihan_pinlu_map.get(ch, 0),
                grade_level=unihan_grade_map.get(ch, 0),
                core_coverage=unihan_core_map.get(ch, 0),
            )
            output_weight = _compute_phrase_inferred_single_char_reading_weight(
                base_weight,
                term_count,
                support_sum,
            )
            bucket[key] = output_weight
            stats[stats_key] += 1

    inject_phrase_inferred_readings(
        sc,
        sc_inferred_reading_term_count_map,
        sc_inferred_reading_support_sum_map,
        tc_only_chars,
        "unihan_phrase_inferred_reading_injected_sc",
    )
    inject_phrase_inferred_readings(
        tc,
        tc_inferred_reading_term_count_map,
        tc_inferred_reading_support_sum_map,
        sc_only_chars,
        "unihan_phrase_inferred_reading_injected_tc",
    )

    for text, pinyin in overrides.items():
        if _cjk_len(text) != 1:
            continue
        if min_hanzi > 1:
            continue

        base_weight = _compute_unihan_single_char_weight(
            freq=unihan_freq_map.get(text, 0),
            pinlu_freq=unihan_pinlu_map.get(text, 0),
            grade_level=unihan_grade_map.get(text, 0),
            core_coverage=unihan_core_map.get(text, 0),
        )
        key = (pinyin, text)
        output_weight = min(700, base_weight + 70)

        if text in tc_only_chars:
            previous_tc = tc.get(key, 0)
            if output_weight > previous_tc:
                tc[key] = output_weight
                stats["override_injected"] += 1
        elif text in sc_only_chars:
            previous_sc = sc.get(key, 0)
            if output_weight > previous_sc:
                sc[key] = output_weight
                stats["override_injected"] += 1
        else:
            previous_sc = sc.get(key, 0)
            if output_weight > previous_sc:
                sc[key] = output_weight
                stats["override_injected"] += 1

            previous_tc = tc.get(key, 0)
            if output_weight > previous_tc:
                tc[key] = output_weight
                stats["override_injected"] += 1

        stats["override_hits"] += 1

    if trad_to_simp_char_map:
        sc, normalize_stats = _normalize_sc_mapping_with_char_map(
            sc, trad_to_simp_char_map, simp_to_trad_char_map
        )
        stats.update(normalize_stats)
    if simp_to_trad_char_map:
        tc, normalize_stats = _normalize_tc_mapping_with_char_map(
            tc,
            simp_to_trad_char_map,
            trad_to_simp_char_map,
        )
        stats.update(normalize_stats)

    sc, sc_script_stats = _filter_sc_mapping_with_script_hints(sc, sc_chars, tc_chars)
    stats.update(sc_script_stats)
    tc, tc_script_stats = _filter_tc_mapping_with_script_hints(tc, sc_chars, tc_chars)
    stats.update(tc_script_stats)

    return sc, tc, stats


def _build_text_pinyin_index(
    sc: Dict[Tuple[str, str], int],
    tc: Dict[Tuple[str, str], int],
) -> Dict[str, Set[str]]:
    index: Dict[str, Set[str]] = {}

    for pinyin, text in sc.keys():
        index.setdefault(text, set()).add(pinyin)
    for pinyin, text in tc.keys():
        index.setdefault(text, set()).add(pinyin)

    return index


def _build_opencc_sc_to_tc_map(opencc_entries: List[Tuple[str, str]]) -> Dict[str, Set[str]]:
    mapping: Dict[str, Set[str]] = {}
    for sc_word, tc_word in opencc_entries:
        if not sc_word or not tc_word:
            continue
        mapping.setdefault(sc_word, set()).add(tc_word)
    return mapping


def _build_opencc_tc_to_sc_map(opencc_entries: List[Tuple[str, str]]) -> Dict[str, Set[str]]:
    mapping: Dict[str, Set[str]] = {}
    for sc_word, tc_word in opencc_entries:
        if not sc_word or not tc_word:
            continue
        mapping.setdefault(tc_word, set()).add(sc_word)
    return mapping


def _build_cedict_tc_to_sc_map(source_text: str, min_hanzi: int) -> Dict[str, Set[str]]:
    mapping: Dict[str, Set[str]] = {}
    for raw_line in source_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        matched = CEDICT_LINE_RE.match(line)
        if not matched:
            continue
        trad, simp, _pinyin_raw, _defs = matched.groups()
        if _cjk_len(trad) < min_hanzi or _cjk_len(simp) < min_hanzi:
            continue
        if trad == simp:
            continue
        mapping.setdefault(trad, set()).add(simp)
    return mapping


def _merge_tc_to_sc_maps(*maps: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    merged: Dict[str, Set[str]] = {}
    for mapping in maps:
        for tc_word, sc_words in mapping.items():
            if not sc_words:
                continue
            bucket = merged.setdefault(tc_word, set())
            bucket.update(sc_words)
    return merged


def _build_char_variant_hints(
    tc_to_sc_map: Dict[str, Set[str]],
    opencc_entries: List[Tuple[str, str]],
) -> Tuple[Dict[str, str], Dict[str, str], Set[str], Set[str]]:
    # Build char-level hints from known word-level SC/TC alignments.
    # Used for:
    # 1) script split in unihan_single generation
    # 2) SC-side cleanup in broad profile.
    pair_counts: Dict[Tuple[str, str], int] = {}
    tc_identity_counts: Dict[str, int] = {}
    sc_identity_counts: Dict[str, int] = {}
    sc_chars: Set[str] = set()
    tc_chars: Set[str] = set()

    def add_pair(tc_word: str, sc_word: str) -> None:
        if len(tc_word) != len(sc_word):
            return
        for tc_ch, sc_ch in zip(tc_word, sc_word):
            if not CJK_FULL_RE.fullmatch(tc_ch):
                continue
            if not CJK_FULL_RE.fullmatch(sc_ch):
                continue
            tc_chars.add(tc_ch)
            sc_chars.add(sc_ch)
            if tc_ch == sc_ch:
                tc_identity_counts[tc_ch] = tc_identity_counts.get(tc_ch, 0) + 1
                sc_identity_counts[sc_ch] = sc_identity_counts.get(sc_ch, 0) + 1
                continue
            key = (tc_ch, sc_ch)
            pair_counts[key] = pair_counts.get(key, 0) + 1

    for sc_word, tc_word in opencc_entries:
        add_pair(tc_word, sc_word)
    for tc_word, sc_words in tc_to_sc_map.items():
        for sc_word in sc_words:
            add_pair(tc_word, sc_word)

    trad_to_simp: Dict[str, str] = {}
    per_tc: Dict[str, List[Tuple[int, str]]] = {}
    for (tc_ch, sc_ch), count in pair_counts.items():
        per_tc.setdefault(tc_ch, []).append((count, sc_ch))
    for tc_ch, candidates in per_tc.items():
        candidates.sort(key=lambda item: (-item[0], item[1]))
        best_count, best_sc = candidates[0]
        second_count = candidates[1][0] if len(candidates) > 1 else 0
        same_count = tc_identity_counts.get(tc_ch, 0)
        # Avoid overfitting lexicalized phrase-level replacements (for example 待->呆 in 待著->呆着).
        # Only keep a TC->SC char hint when evidence is strong enough.
        if best_count < 2:
            continue
        if best_count <= same_count:
            continue
        if best_count <= second_count:
            continue
        trad_to_simp[tc_ch] = best_sc

    simp_to_trad: Dict[str, str] = {}
    per_sc: Dict[str, List[Tuple[int, str]]] = {}
    for (tc_ch, sc_ch), count in pair_counts.items():
        per_sc.setdefault(sc_ch, []).append((count, tc_ch))
    for sc_ch, candidates in per_sc.items():
        candidates.sort(key=lambda item: (-item[0], item[1]))
        best_count, best_tc = candidates[0]
        second_count = candidates[1][0] if len(candidates) > 1 else 0
        same_count = sc_identity_counts.get(sc_ch, 0)
        if best_count < 2:
            continue
        if best_count <= same_count:
            continue
        if best_count <= second_count:
            continue
        simp_to_trad[sc_ch] = best_tc

    return trad_to_simp, simp_to_trad, sc_chars, tc_chars


def _build_tc_shared_identity_chars(
    tc_to_sc_map: Dict[str, Set[str]],
    opencc_entries: List[Tuple[str, str]],
    min_identity_count: int = 20,
) -> Set[str]:
    """Find simplified-looking chars that are also common in TC text.

    Unihan exposes pairs such as 閤/合, 麵/面, 製/制 and 齣/出 as variants.
    They are useful for SC normalization, but forcing the simplified-looking
    member to the rare traditional variant globally breaks ordinary TC words
    such as 合適, 同意, 反向代理 and 台州.  OpenCC identity alignments provide a
    broad signal for chars that should remain legal in TC output.
    """
    identity_counts: Dict[str, int] = {}

    def add_pair(tc_word: str, sc_word: str) -> None:
        if len(tc_word) != len(sc_word):
            return
        for tc_ch, sc_ch in zip(tc_word, sc_word):
            if not CJK_FULL_RE.fullmatch(tc_ch):
                continue
            if not CJK_FULL_RE.fullmatch(sc_ch):
                continue
            if tc_ch == sc_ch:
                identity_counts[sc_ch] = identity_counts.get(sc_ch, 0) + 1

    for sc_word, tc_word in opencc_entries:
        add_pair(tc_word, sc_word)
    for tc_word, sc_words in tc_to_sc_map.items():
        for sc_word in sc_words:
            add_pair(tc_word, sc_word)

    return {
        ch
        for ch, count in identity_counts.items()
        if count >= min_identity_count
    }


def _apply_explicit_script_pair(
    trad_ch: str,
    simp_ch: str,
    trad_to_simp_char_map: Dict[str, str],
    simp_to_trad_char_map: Dict[str, str],
    sc_chars: Set[str],
    tc_chars: Set[str],
    tc_shared_identity_chars: Set[str] | None = None,
) -> None:
    if (
        trad_ch == simp_ch
        or not CJK_FULL_RE.fullmatch(trad_ch)
        or not CJK_FULL_RE.fullmatch(simp_ch)
    ):
        return

    shared_behavior = SHARED_SCRIPT_VARIANT_BEHAVIOR.get((trad_ch, simp_ch))
    if shared_behavior is not None:
        keep_trad_in_sc, keep_simp_in_tc = shared_behavior

        # Do not apply global char-for-char rewrites for audited shared pairs.
        trad_to_simp_char_map.pop(trad_ch, None)
        simp_to_trad_char_map.pop(simp_ch, None)
        trad_to_simp_char_map.pop(simp_ch, None)
        simp_to_trad_char_map.pop(trad_ch, None)

        sc_chars.add(simp_ch)
        tc_chars.add(trad_ch)
        if keep_trad_in_sc:
            sc_chars.add(trad_ch)
        else:
            sc_chars.discard(trad_ch)
        if keep_simp_in_tc:
            tc_chars.add(simp_ch)
        else:
            tc_chars.discard(simp_ch)
        return

    if tc_shared_identity_chars and simp_ch in tc_shared_identity_chars:
        # Keep SC cleanup for the traditional variant, but do not globally
        # rewrite the shared form away from TC output.
        trad_to_simp_char_map[trad_ch] = simp_ch
        simp_to_trad_char_map.pop(simp_ch, None)
        trad_to_simp_char_map.pop(simp_ch, None)
        simp_to_trad_char_map.pop(trad_ch, None)

        sc_chars.add(simp_ch)
        sc_chars.discard(trad_ch)
        tc_chars.add(trad_ch)
        tc_chars.add(simp_ch)
        return

    # Treat explicit Unihan/OpenCC single-character variant relations as
    # authoritative. They should override noisy phrase-level hints that may
    # otherwise let traditional chars leak into SC buckets (and vice versa).
    trad_to_simp_char_map[trad_ch] = simp_ch
    simp_to_trad_char_map[simp_ch] = trad_ch

    trad_to_simp_char_map.pop(simp_ch, None)
    simp_to_trad_char_map.pop(trad_ch, None)

    sc_chars.add(simp_ch)
    sc_chars.discard(trad_ch)
    tc_chars.add(trad_ch)
    tc_chars.discard(simp_ch)


def _normalize_sc_mapping_with_char_map(
    mapping: Dict[Tuple[str, str], int],
    trad_to_simp_char_map: Dict[str, str],
    simp_to_trad_char_map: Dict[str, str] | None = None,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    simp_to_trad_char_map = simp_to_trad_char_map or {}
    if not trad_to_simp_char_map:
        return mapping, {
            "sc_char_normalized_converted_entries": 0,
            "sc_char_normalized_total_entries": len(mapping),
            "sc_char_normalized_blocked_reverse_entries": 0,
        }

    normalized: Dict[Tuple[str, str], int] = {}
    converted_entries = 0
    blocked_reverse_entries = 0

    for (pinyin, text), weight in mapping.items():
        converted_chars: List[str] = []
        changed = False
        for ch in text:
            replacement = trad_to_simp_char_map.get(ch, ch)
            # Guardrail: do not rewrite a known simplified form into a
            # traditional/variant form (for example 么 -> 幺).
            if replacement != ch and ch in simp_to_trad_char_map:
                replacement = ch
                blocked_reverse_entries += 1
            if replacement != ch:
                changed = True
            converted_chars.append(replacement)
        output_text = "".join(converted_chars)
        if changed:
            converted_entries += 1

        key = (pinyin, output_text)
        previous = normalized.get(key, 0)
        if weight > previous:
            normalized[key] = weight

    stats = {
        "sc_char_normalized_converted_entries": converted_entries,
        "sc_char_normalized_total_entries": len(normalized),
        "sc_char_normalized_blocked_reverse_entries": blocked_reverse_entries,
    }
    return normalized, stats


def _filter_sc_mapping_with_script_hints(
    mapping: Dict[Tuple[str, str], int],
    sc_chars: Set[str],
    tc_chars: Set[str],
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    filtered: Dict[Tuple[str, str], int] = {}
    dropped_entries = 0
    tc_only_chars = tc_chars.difference(sc_chars)

    if not tc_only_chars:
        return mapping, {
            "sc_script_filtered_entries": 0,
            "sc_script_filtered_total_entries": len(mapping),
        }

    for key, weight in mapping.items():
        _pinyin, text = key
        drop = False
        for ch in text:
            if ch in tc_only_chars:
                drop = True
                break
        if drop:
            dropped_entries += 1
            continue
        filtered[key] = weight

    stats = {
        "sc_script_filtered_entries": dropped_entries,
        "sc_script_filtered_total_entries": len(filtered),
    }
    return filtered, stats


def _normalize_tc_mapping_with_char_map(
    mapping: Dict[Tuple[str, str], int],
    simp_to_trad_char_map: Dict[str, str],
    trad_to_simp_char_map: Dict[str, str] | None = None,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    trad_to_simp_char_map = trad_to_simp_char_map or {}
    if not simp_to_trad_char_map:
        return mapping, {
            "tc_char_normalized_converted_entries": 0,
            "tc_char_normalized_total_entries": len(mapping),
            "tc_char_normalized_blocked_reverse_entries": 0,
        }

    normalized: Dict[Tuple[str, str], int] = {}
    converted_entries = 0
    blocked_reverse_entries = 0

    for (pinyin, text), weight in mapping.items():
        converted_chars: List[str] = []
        changed = False
        for ch in text:
            replacement = simp_to_trad_char_map.get(ch, ch)
            # Guardrail symmetric to SC normalization: do not rewrite a known
            # traditional form into another simplified/variant form. Noisy
            # phrase-level hints can otherwise turn exact TC entries such as
            # 合適 into a mixed-script/non-preferred form.
            if replacement != ch and ch in trad_to_simp_char_map:
                replacement = ch
                blocked_reverse_entries += 1
            if replacement != ch:
                changed = True
            converted_chars.append(replacement)
        output_text = "".join(converted_chars)
        if changed:
            converted_entries += 1

        key = (pinyin, output_text)
        previous = normalized.get(key, 0)
        if weight > previous:
            normalized[key] = weight

    stats = {
        "tc_char_normalized_converted_entries": converted_entries,
        "tc_char_normalized_total_entries": len(normalized),
        "tc_char_normalized_blocked_reverse_entries": blocked_reverse_entries,
    }
    return normalized, stats


def _convert_text_with_char_map(
    text: str,
    char_map: Dict[str, str],
) -> str:
    if not char_map:
        return text
    return "".join(char_map.get(ch, ch) for ch in text)


def _choose_tc_phrase_candidate(
    sc_text: str,
    candidates: Set[str],
    simp_to_trad_char_map: Dict[str, str],
) -> str:
    if not candidates:
        return ""

    ordered = sorted(candidates)
    char_converted = _convert_text_with_char_map(sc_text, simp_to_trad_char_map)
    if char_converted in candidates:
        return char_converted

    def score(candidate: str) -> Tuple[int, int, int, int, str]:
        expected_matches = sum(
            1
            for left, right in zip(candidate, char_converted)
            if left == right
        )
        changed_from_source = sum(
            1
            for left, right in zip(candidate, sc_text)
            if left != right
        )
        same_as_source_penalty = 1 if candidate == sc_text and char_converted != sc_text else 0
        length_match = 1 if len(candidate) == len(sc_text) else 0
        return (
            -same_as_source_penalty,
            length_match,
            expected_matches,
            changed_from_source,
            candidate,
        )

    return max(ordered, key=score)


def _convert_sc_text_to_tc_with_phrase_hints(
    text: str,
    opencc_sc_to_tc_map: Dict[str, Set[str]],
    simp_to_trad_char_map: Dict[str, str],
) -> str:
    if not text:
        return text
    if text in opencc_sc_to_tc_map:
        return _choose_tc_phrase_candidate(
            text,
            opencc_sc_to_tc_map[text],
            simp_to_trad_char_map,
        )

    output: List[str] = []
    index = 0
    text_len = len(text)
    while index < text_len:
        matched = ""
        max_span = min(8, text_len - index)
        for span in range(max_span, 1, -1):
            fragment = text[index : index + span]
            candidates = opencc_sc_to_tc_map.get(fragment, set())
            if not candidates:
                continue
            matched = _choose_tc_phrase_candidate(
                fragment,
                candidates,
                simp_to_trad_char_map,
            )
            index += span
            output.append(matched)
            break
        if matched:
            continue
        output.append(simp_to_trad_char_map.get(text[index], text[index]))
        index += 1

    return "".join(output)


def _backfill_tc_mapping_from_sc_with_char_map(
    sc_mapping: Dict[Tuple[str, str], int],
    tc_mapping: Dict[Tuple[str, str], int],
    simp_to_trad_char_map: Dict[str, str],
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    if not simp_to_trad_char_map:
        return tc_mapping, {
            "tc_backfill_from_sc_added": 0,
            "tc_backfill_from_sc_boosted": 0,
            "tc_backfill_from_sc_total": len(tc_mapping),
        }

    normalized = dict(tc_mapping)
    added = 0
    boosted = 0
    for (pinyin, sc_text), weight in sc_mapping.items():
        tc_text = _convert_text_with_char_map(sc_text, simp_to_trad_char_map)
        key = (pinyin, tc_text)
        previous = normalized.get(key)
        if previous is None:
            normalized[key] = weight
            added += 1
        elif weight > previous:
            normalized[key] = weight
            boosted += 1

    stats = {
        "tc_backfill_from_sc_added": added,
        "tc_backfill_from_sc_boosted": boosted,
        "tc_backfill_from_sc_total": len(normalized),
    }
    return normalized, stats


def _merge_tc_simplified_terms_into_existing_traditional_targets(
    mapping: Dict[Tuple[str, str], int],
    sc_terms: Set[str],
    simp_to_trad_char_map: Dict[str, str],
    stats_prefix: str,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    if not mapping or not sc_terms or not simp_to_trad_char_map:
        return mapping, {
            f"{stats_prefix}_simplified_variant_rows_merged": 0,
            f"{stats_prefix}_simplified_variant_targets_boosted": 0,
        }

    normalized = dict(mapping)
    merged = 0
    boosted = 0
    for key, weight in list(mapping.items()):
        pinyin, text = key
        if text not in sc_terms:
            continue
        converted = _convert_text_with_char_map(text, simp_to_trad_char_map)
        if converted == text:
            continue
        target_key = (pinyin, converted)
        if target_key not in normalized:
            continue
        if normalized[target_key] < weight:
            normalized[target_key] = weight
            boosted += 1
        if key in normalized:
            del normalized[key]
            merged += 1

    stats = {
        f"{stats_prefix}_simplified_variant_rows_merged": merged,
        f"{stats_prefix}_simplified_variant_targets_boosted": boosted,
    }
    return normalized, stats


def _merge_tc_converted_variants_into_preferred_targets(
    mapping: Dict[Tuple[str, str], int],
    preferred_tc_by_sc: Dict[str, str],
    simp_to_trad_char_map: Dict[str, str],
    stats_prefix: str,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    if not mapping or not preferred_tc_by_sc or not simp_to_trad_char_map:
        return mapping, {
            f"{stats_prefix}_converted_variant_rows_merged": 0,
            f"{stats_prefix}_converted_variant_targets_boosted": 0,
        }

    converted_to_preferred: Dict[str, Set[str]] = {}
    for sc_text, preferred_tc in preferred_tc_by_sc.items():
        if not sc_text or not preferred_tc:
            continue
        converted = _convert_text_with_char_map(sc_text, simp_to_trad_char_map)
        if not converted or converted == preferred_tc:
            continue
        converted_to_preferred.setdefault(converted, set()).add(preferred_tc)

    if not converted_to_preferred:
        return mapping, {
            f"{stats_prefix}_converted_variant_rows_merged": 0,
            f"{stats_prefix}_converted_variant_targets_boosted": 0,
        }

    normalized = dict(mapping)
    merged = 0
    boosted = 0
    for key, weight in list(mapping.items()):
        pinyin, text = key
        preferred_candidates = converted_to_preferred.get(text)
        if not preferred_candidates:
            continue

        target_key = None
        for preferred_tc in sorted(preferred_candidates):
            candidate_key = (pinyin, preferred_tc)
            if candidate_key in normalized:
                target_key = candidate_key
                break
        if target_key is None:
            continue

        if normalized[target_key] < weight:
            normalized[target_key] = weight
            boosted += 1
        if key in normalized:
            del normalized[key]
            merged += 1

    stats = {
        f"{stats_prefix}_converted_variant_rows_merged": merged,
        f"{stats_prefix}_converted_variant_targets_boosted": boosted,
    }
    return normalized, stats


def _filter_tc_mapping_with_script_hints(
    mapping: Dict[Tuple[str, str], int],
    sc_chars: Set[str],
    tc_chars: Set[str],
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    filtered: Dict[Tuple[str, str], int] = {}
    dropped_entries = 0
    sc_only_chars = sc_chars.difference(tc_chars)

    if not sc_only_chars:
        return mapping, {
            "tc_script_filtered_entries": 0,
            "tc_script_filtered_total_entries": len(mapping),
        }

    for key, weight in mapping.items():
        _pinyin, text = key
        drop = False
        for ch in text:
            if ch in sc_only_chars:
                drop = True
                break
        if drop:
            dropped_entries += 1
            continue
        filtered[key] = weight

    stats = {
        "tc_script_filtered_entries": dropped_entries,
        "tc_script_filtered_total_entries": len(filtered),
    }
    return filtered, stats


def _normalize_pageviews_entries_to_sc(
    pageviews_entries: Dict[str, int],
    tc_to_sc_map: Dict[str, Set[str]],
) -> Dict[str, int]:
    normalized: Dict[str, int] = {}
    for word, views in pageviews_entries.items():
        if views <= 0:
            continue
        mapped_sc = tc_to_sc_map.get(word, set())
        if mapped_sc:
            for sc_word in mapped_sc:
                normalized[sc_word] = normalized.get(sc_word, 0) + views
        else:
            normalized[word] = normalized.get(word, 0) + views
    return normalized


def _normalize_metric_map_to_sc(
    metric_map: Dict[str, int],
    tc_to_sc_map: Dict[str, Set[str]],
) -> Dict[str, int]:
    normalized: Dict[str, int] = {}
    for word, value in metric_map.items():
        if value <= 0:
            continue
        mapped_sc = tc_to_sc_map.get(word, set())
        if mapped_sc:
            for sc_word in mapped_sc:
                normalized[sc_word] = max(normalized.get(sc_word, 0), value)
        else:
            normalized[word] = max(normalized.get(word, 0), value)
    return normalized


def _normalize_sc_mapping_with_opencc(
    sc_map: Dict[Tuple[str, str], int],
    tc_to_sc_map: Dict[str, Set[str]],
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    normalized: Dict[Tuple[str, str], int] = {}
    converted_entries = 0

    for (pinyin, text), weight in sc_map.items():
        mapped_sc = tc_to_sc_map.get(text, set())
        if mapped_sc:
            converted_entries += 1
            targets = mapped_sc
        else:
            targets = {text}

        for target in targets:
            key = (pinyin, target)
            previous = normalized.get(key, 0)
            if weight > previous:
                normalized[key] = weight

    stats = {
        "sc_normalized_converted_entries": converted_entries,
        "sc_normalized_total_entries": len(normalized),
    }
    return normalized, stats


def _build_thuocl_frequency_map(
    max_df_map: Dict[str, int],
    coverage_map: Dict[str, int],
) -> Dict[str, int]:
    normalized: Dict[str, int] = {}
    for word, max_df in max_df_map.items():
        if max_df <= 0:
            continue
        coverage = max(1, coverage_map.get(word, 1))
        # Keep only cross-list terms to suppress domain-specific tails.
        if coverage < 2:
            continue
        # Reward broader cross-list consensus.
        coverage_factor = 0.62 + 0.14 * min(coverage, 5)
        normalized[word] = max(1, int(round(max_df * coverage_factor)))
    return normalized


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    ratio = min(1.0, max(0.0, percentile / 100.0))
    index = int(math.ceil(ratio * len(ordered))) - 1
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def _build_normalized_signal_map(
    source_frequency_map: Dict[str, int],
    percentile: float = 99.0,
) -> Dict[str, float]:
    values: List[float] = []
    for freq in source_frequency_map.values():
        if freq > 0:
            values.append(math.log1p(freq))
    cap = _percentile(values, percentile)
    if cap <= 0:
        return {}

    normalized: Dict[str, float] = {}
    for word, freq in source_frequency_map.items():
        if freq <= 0:
            continue
        score = math.log1p(freq) / cap
        normalized[word] = min(1.0, max(0.0, score))
    return normalized


def _build_pageviews_burst_signal_map(
    aggregate_entries: Dict[str, int],
    month_hits_map: Dict[str, int],
    peak_views_map: Dict[str, int],
) -> Dict[str, float]:
    burst_signal: Dict[str, float] = {}
    for word, total_views in aggregate_entries.items():
        if total_views <= 0:
            continue
        month_hits = max(1, month_hits_map.get(word, 0))
        peak_views = max(0, peak_views_map.get(word, 0))
        if peak_views <= 0:
            continue

        average_views = max(1.0, float(total_views) / float(month_hits))
        concentration = float(peak_views) / average_views
        burst = min(1.0, max(0.0, (concentration - 1.15) / 2.75))
        if month_hits >= 4:
            burst *= 0.22
        elif month_hits >= 3:
            burst *= 0.45
        elif month_hits == 2:
            burst *= 0.72

        if burst > 0.0:
            burst_signal[word] = burst
    return burst_signal


def _build_direct_frequency_signal_map(
    source_frequency_map: Dict[str, int],
    power: float = 3.0,
) -> Dict[str, float]:
    """
    Build a strict frequency signal from raw counts.

    This keeps very frequent daily terms clearly separated from low-frequency
    tails inside same-pinyin buckets.
    """
    max_log = 0.0
    for freq in source_frequency_map.values():
        if freq <= 0:
            continue
        value = math.log1p(freq)
        if value > max_log:
            max_log = value

    if max_log <= 0.0:
        return {}

    shaped_power = max(1.0, float(power))
    normalized: Dict[str, float] = {}
    for word, freq in source_frequency_map.items():
        if freq <= 0:
            continue
        ratio = min(1.0, max(0.0, math.log1p(freq) / max_log))
        normalized[word] = ratio**shaped_power
    return normalized


def _build_thuocl_jieba_corroborated_signal_map(
    thuocl_max_df_map: Dict[str, int],
    thuocl_coverage_map: Dict[str, int],
    jieba_direct_signal_map: Dict[str, float],
) -> Dict[str, float]:
    """Keep strong single-list THUOCL evidence only when Jieba corroborates it.

    The regular THUOCL signal intentionally requires cross-list coverage so
    domain tails cannot influence general ranking. That conservative filter
    also drops genuinely common terms which occur in one THUOCL list. Retain a
    separate, short-word-only signal for the subset independently supported by
    a strong Jieba frequency; it is never used to add entries or globally
    rescore the dictionary.
    """
    raw_signal_map = _build_normalized_signal_map(thuocl_max_df_map)
    corroborated: Dict[str, float] = {}
    for word, signal in raw_signal_map.items():
        if thuocl_coverage_map.get(word, 0) != 1:
            continue
        if signal < 0.55:
            continue
        if jieba_direct_signal_map.get(word, 0.0) < 0.14:
            continue
        corroborated[word] = signal
    return corroborated


def _build_char_frequency_prior(
    source_frequency_map: Dict[str, int],
    power: float = 1.6,
) -> Dict[str, float]:
    """
    Build a character-level prior from lexical frequencies.

    This helps same-pinyin short-word ordering (e.g. 不对 vs 部队) reflect
    common character usage, while still remaining data-driven.
    """
    char_raw: Dict[str, int] = {}
    for word, freq in source_frequency_map.items():
        if freq <= 0:
            continue
        for ch in word:
            if not CJK_FULL_RE.fullmatch(ch):
                continue
            char_raw[ch] = char_raw.get(ch, 0) + freq

    if not char_raw:
        return {}

    max_log = 0.0
    for value in char_raw.values():
        if value <= 0:
            continue
        log_value = math.log1p(value)
        if log_value > max_log:
            max_log = log_value
    if max_log <= 0.0:
        return {}

    shaped_power = max(1.0, float(power))
    prior: Dict[str, float] = {}
    for ch, value in char_raw.items():
        ratio = min(1.0, max(0.0, math.log1p(value) / max_log))
        prior[ch] = ratio**shaped_power
    return prior


def _build_usage_signal_map(
    thuocl_signal_map: Dict[str, float],
    jieba_signal_map: Dict[str, float],
    pageviews_signal_map: Dict[str, float],
    pageviews_persistence_signal_map: Dict[str, float] | None = None,
    pageviews_burst_signal_map: Dict[str, float] | None = None,
    jieba_pos_map: Dict[str, str] | None = None,
    jieba_direct_signal_map: Dict[str, float] | None = None,
) -> Tuple[Dict[str, float], Dict[str, int]]:
    # Source weights reflect relative robustness of the signals:
    # THUOCL consensus DF, jieba lexical frequency, and Wikipedia usage heat.
    source_weights = {
        "thuocl": 0.46,
        "jieba": 0.31,
        "pageviews": 0.23,
    }
    consensus_step = 0.12

    usage_score_map: Dict[str, float] = {}
    source_hits_map: Dict[str, int] = {}
    pageviews_persistence_signal_map = pageviews_persistence_signal_map or {}
    pageviews_burst_signal_map = pageviews_burst_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    jieba_direct_signal_map = jieba_direct_signal_map or {}

    all_terms = set(thuocl_signal_map.keys())
    all_terms.update(jieba_signal_map.keys())
    all_terms.update(pageviews_signal_map.keys())
    for term in all_terms:
        thuocl_score = thuocl_signal_map.get(term, 0.0)
        jieba_score = jieba_signal_map.get(term, 0.0)
        pageviews_score = pageviews_signal_map.get(term, 0.0)
        pageviews_persistence = pageviews_persistence_signal_map.get(term, 0.0)
        pageviews_burst = pageviews_burst_signal_map.get(term, 0.0)
        effective_pageviews_score = min(
            1.0,
            max(
                0.0,
                pageviews_score * 0.72
                + pageviews_persistence * 0.28
                - pageviews_burst * 0.14,
            ),
        )
        thuocl_hit = thuocl_score >= 0.10
        jieba_hit = jieba_score >= 0.06
        pageviews_hit = effective_pageviews_score >= 0.05
        source_hits = int(thuocl_hit) + int(jieba_hit) + int(pageviews_hit)
        if source_hits <= 0:
            continue

        score = (
            source_weights["thuocl"] * thuocl_score
            + source_weights["jieba"] * jieba_score
            + source_weights["pageviews"] * effective_pageviews_score
        )
        if source_hits > 1:
            score += consensus_step * (source_hits - 1)

        # Source-consensus shaping:
        # single-source words tend to include noisy transliterations/domain terms,
        # while robust daily vocabulary is usually supported by multiple signals.
        if source_hits == 1:
            if pageviews_hit and (not thuocl_hit) and (not jieba_hit):
                # Wiki top-only words are often named entities.
                score *= 0.55
            elif jieba_hit and (not thuocl_hit) and (not pageviews_hit):
                # Jieba-only terms include many low-priority lexicon tails.
                score *= 0.72
            else:
                # THUOCL-only still keeps better trust than other single-source terms.
                score *= 0.82
        elif source_hits == 2:
            score *= 0.88
        else:
            score *= 1.00

        if (pageviews_burst >= 0.40) and (pageviews_persistence < 0.16) and (source_hits <= 1):
            score *= 0.72
        elif (pageviews_burst >= 0.26) and (pageviews_persistence < 0.20) and (source_hits <= 1):
            score *= 0.84
        elif (pageviews_persistence >= 0.42) and (source_hits >= 2):
            score *= 1.05
        elif (pageviews_persistence >= 0.30) and (jieba_score >= 0.08):
            score *= 1.03

        pos_tag = jieba_pos_map.get(term, "")
        if _is_named_entity_pos(pos_tag):
            jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(term, 0.0)))
            looks_like_person_name = _looks_like_low_signal_person_name(
                term,
                usage_score=score,
                source_hits=source_hits,
                pageview_score=effective_pageviews_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=effective_pageviews_score >= 0.08 or source_hits >= 2,
                pos_tag=pos_tag,
            )
            looks_like_place_name = _looks_like_low_signal_place_name(
                term,
                usage_score=score,
                source_hits=source_hits,
                pageview_score=effective_pageviews_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=effective_pageviews_score >= 0.08 or source_hits >= 2,
                pos_tag=pos_tag,
            )
            short_ambiguous_named_entity = (
                _cjk_len(term) <= 2
                and (not looks_like_person_name)
                and (not looks_like_place_name)
                and effective_pageviews_score < 0.20
                and source_hits <= 1
            )
            # Named entities are useful, but web/wiki popularity alone can
            # over-promote proper nouns for IME general typing.
            # Use strict direct-frequency gates to keep only high-utility names
            # near the top by default.
            if jieba_direct_score < 0.02:
                score *= 0.52 if short_ambiguous_named_entity else 0.22
            elif jieba_direct_score < 0.05:
                score *= 0.64 if short_ambiguous_named_entity else 0.32
            elif jieba_direct_score < 0.10:
                score *= 0.76 if short_ambiguous_named_entity else 0.46
            elif jieba_direct_score < 0.18:
                score *= 0.88 if short_ambiguous_named_entity else 0.62
            else:
                score *= 0.94 if short_ambiguous_named_entity else 0.80

            if (
                effective_pageviews_score >= 0.30
                and source_hits >= 2
                and jieba_direct_score >= 0.12
            ):
                score *= 1.08
            elif (
                effective_pageviews_score >= 0.20
                and source_hits >= 2
                and jieba_direct_score >= 0.08
            ):
                score *= 1.00
            else:
                score *= 0.96

        usage_score_map[term] = min(1.0, max(0.0, score))
        source_hits_map[term] = source_hits

    return usage_score_map, source_hits_map


def _build_tc_signal_map(
    source_signal_map: Dict[str, float],
    tc_to_sc_map: Dict[str, Set[str]],
) -> Dict[str, float]:
    tc_signal: Dict[str, float] = {}

    for sc_word, signal in source_signal_map.items():
        if signal <= 0.0:
            continue
        previous_sc = tc_signal.get(sc_word, 0.0)
        if signal > previous_sc:
            tc_signal[sc_word] = signal

    for tc_word, sc_words in tc_to_sc_map.items():
        best = tc_signal.get(tc_word, 0.0)
        for sc_word in sc_words:
            signal = source_signal_map.get(sc_word, 0.0)
            if signal > best:
                best = signal
        if best > 0.0:
            tc_signal[tc_word] = best

    return tc_signal


def _build_tc_signal_map_with_char_fallback(
    source_signal_map: Dict[str, float],
    tc_to_sc_map: Dict[str, Set[str]],
    trad_to_simp_char_map: Dict[str, str],
    tc_terms: Set[str],
) -> Tuple[Dict[str, float], int]:
    """Map strict SC signals to TC terms missing from phrase-level maps.

    OpenCC and CEDICT phrase mappings do not cover every productive modern
    phrase. For final same-pinyin correction only, fall back to conservative
    character-level TC->SC conversion so terms such as 聞到 can reuse the
    direct corpus signal for 闻到 without changing global TC rescoring.
    """
    tc_signal = _build_tc_signal_map(source_signal_map, tc_to_sc_map)
    fallback_count = 0
    if not source_signal_map or not trad_to_simp_char_map or not tc_terms:
        return tc_signal, fallback_count

    for tc_term in tc_terms:
        sc_term = "".join(trad_to_simp_char_map.get(ch, ch) for ch in tc_term)
        if sc_term == tc_term:
            continue
        signal = source_signal_map.get(sc_term, 0.0)
        if signal <= tc_signal.get(tc_term, 0.0):
            continue
        tc_signal[tc_term] = signal
        fallback_count += 1

    return tc_signal, fallback_count


def _build_tc_source_hits_map(
    source_hits_map: Dict[str, int],
    tc_to_sc_map: Dict[str, Set[str]],
) -> Dict[str, int]:
    tc_hits: Dict[str, int] = {}

    for sc_word, hits in source_hits_map.items():
        if hits <= 0:
            continue
        previous_sc = tc_hits.get(sc_word, 0)
        if hits > previous_sc:
            tc_hits[sc_word] = hits

    for tc_word, sc_words in tc_to_sc_map.items():
        best = tc_hits.get(tc_word, 0)
        for sc_word in sc_words:
            hits = source_hits_map.get(sc_word, 0)
            if hits > best:
                best = hits
        if best > 0:
            tc_hits[tc_word] = best

    return tc_hits


def _build_tc_pos_map(
    source_pos_map: Dict[str, str],
    tc_to_sc_map: Dict[str, Set[str]],
) -> Dict[str, str]:
    tc_pos: Dict[str, str] = {}

    for sc_word, pos_tag in source_pos_map.items():
        if not pos_tag:
            continue
        if sc_word not in tc_pos:
            tc_pos[sc_word] = pos_tag

    for tc_word, sc_words in tc_to_sc_map.items():
        best_tag = tc_pos.get(tc_word, "")
        for sc_word in sc_words:
            pos_tag = source_pos_map.get(sc_word, "")
            if not pos_tag:
                continue
            if not best_tag or len(pos_tag) > len(best_tag):
                best_tag = pos_tag
        if best_tag:
            tc_pos[tc_word] = best_tag

    return tc_pos


def _rescore_mapping_with_signals(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    jieba_direct_signal_map: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    char_frequency_prior: Dict[str, float] | None,
    term_style_penalty_map: Dict[Tuple[str, str], int] | None,
    term_semantic_bonus_map: Dict[Tuple[str, str], int] | None,
    unihan_map: Dict[str, str] | None,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_pinlu_map: Dict[str, int] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    core_entry: bool,
    stats_prefix: str,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_rescored": 0,
        f"{stats_prefix}_usage_hits": 0,
        f"{stats_prefix}_multi_source_hits": 0,
        f"{stats_prefix}_pageviews_hits": 0,
        f"{stats_prefix}_wiki_hits": 0,
        f"{stats_prefix}_named_entity_penalized": 0,
        f"{stats_prefix}_single_char_adjusted": 0,
        f"{stats_prefix}_single_char_reading_adjusted": 0,
        f"{stats_prefix}_semantic_bonus_applied": 0,
    }
    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    term_style_penalty_map = term_style_penalty_map or {}
    term_semantic_bonus_map = term_semantic_bonus_map or {}
    unihan_map = unihan_map or {}
    unihan_readings_map = unihan_readings_map or {}
    unihan_pinlu_map = unihan_pinlu_map or {}
    unihan_pinlu_detail_map = unihan_pinlu_detail_map or {}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    for key in list(mapping.keys()):
        _pinyin, text = key
        usage_score = usage_score_map.get(text, 0.0)
        source_hits = source_hits_map.get(text, 0)
        pageviews_score = pageviews_signal_map.get(text, 0.0)
        wiki_hit = _has_effective_wiki_support(
            text,
            wiki_titles,
            pageview_score=pageviews_score,
            source_hits=source_hits,
        )
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pos_tag = jieba_pos_map.get(text, "")
        char_score = _compute_text_single_char_prior(text, char_prior)
        weight = _compute_weight_with_signals(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageviews_score,
            wiki_hit=wiki_hit,
            core_entry=core_entry,
            jieba_direct_score=jieba_direct_score,
            pos_tag=pos_tag,
            char_score=char_score,
        )
        text_len = _cjk_len(text)
        if text_len == 1:
            if char_score >= 0.88:
                weight = min(1000, weight + 180)
                stats[f"{stats_prefix}_single_char_adjusted"] += 1
            elif char_score >= 0.76:
                weight = min(1000, weight + 110)
                stats[f"{stats_prefix}_single_char_adjusted"] += 1
            elif (
                char_score <= 0.06
                and usage_score < 0.03
                and jieba_direct_score < 0.03
                and source_hits <= 1
                and pageviews_score < 0.02
            ):
                weight = max(1, weight - 240)
                stats[f"{stats_prefix}_single_char_adjusted"] += 1
            elif (
                char_score <= 0.12
                and usage_score < 0.05
                and jieba_direct_score < 0.05
                and source_hits <= 1
                and pageviews_score < 0.03
            ):
                weight = max(1, weight - 140)
                stats[f"{stats_prefix}_single_char_adjusted"] += 1
            reading_adjust = _compute_unihan_single_char_reading_delta(
                ch=text,
                pinyin=_pinyin,
                readings_map=unihan_readings_map,
                mandarin_map=unihan_map,
                pinlu_map=unihan_pinlu_map,
                pinlu_detail_map=unihan_pinlu_detail_map,
            )
            if reading_adjust != 0:
                weight = max(1, min(1000, weight + reading_adjust))
                stats[f"{stats_prefix}_single_char_reading_adjusted"] += 1
        if _is_named_entity_pos(pos_tag):
            if source_hits <= 2 and pageviews_score < 0.08 and jieba_direct_score < 0.12:
                penalty = 68 if text_len <= 2 else (44 if text_len <= 4 else 28)
                weight = max(1, weight - penalty)
                stats[f"{stats_prefix}_named_entity_penalized"] += 1

        style_penalty = term_style_penalty_map.get(key, 0)
        if style_penalty > 0:
            weight = max(1, weight - style_penalty)

        semantic_bonus = term_semantic_bonus_map.get(key, 0)
        if semantic_bonus > 0:
            weight = min(1000, weight + semantic_bonus)
            stats[f"{stats_prefix}_semantic_bonus_applied"] += 1

        if mapping[key] != weight:
            stats[f"{stats_prefix}_rescored"] += 1
            mapping[key] = weight
        if usage_score > 0.0:
            stats[f"{stats_prefix}_usage_hits"] += 1
        if source_hits > 1:
            stats[f"{stats_prefix}_multi_source_hits"] += 1
        if pageviews_score > 0.0:
            stats[f"{stats_prefix}_pageviews_hits"] += 1
        if wiki_hit:
            stats[f"{stats_prefix}_wiki_hits"] += 1

    return stats


def _adjust_single_char_reading_preferences(
    mapping: Dict[Tuple[str, str], int],
    unihan_map: Dict[str, str] | None,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_pinlu_map: Dict[str, int] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    phrase_term_count_map: Dict[Tuple[str, str], int] | None,
    phrase_support_sum_map: Dict[Tuple[str, str], float] | None,
    leading_term_count_map: Dict[Tuple[str, str], int] | None,
    leading_support_sum_map: Dict[Tuple[str, str], float] | None,
    stats_prefix: str,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_single_char_reading_preference_adjusted": 0,
        f"{stats_prefix}_single_char_reading_preference_delta_total": 0,
        f"{stats_prefix}_single_char_reading_removed": 0,
    }
    if not mapping:
        return stats

    unihan_map = unihan_map or {}
    unihan_readings_map = unihan_readings_map or {}
    unihan_pinlu_map = unihan_pinlu_map or {}
    unihan_pinlu_detail_map = unihan_pinlu_detail_map or {}
    phrase_term_count_map = phrase_term_count_map or {}
    phrase_support_sum_map = phrase_support_sum_map or {}
    leading_term_count_map = leading_term_count_map or {}
    leading_support_sum_map = leading_support_sum_map or {}

    for key in list(mapping.keys()):
        pinyin, text = key
        if _cjk_len(text) != 1:
            continue

        if (text, pinyin) in SINGLE_CHAR_READING_DROP_OVERRIDES:
            del mapping[key]
            stats[f"{stats_prefix}_single_char_reading_removed"] += 1
            continue

        delta = _compute_unihan_single_char_reading_delta(
            ch=text,
            pinyin=pinyin,
            readings_map=unihan_readings_map,
            mandarin_map=unihan_map,
            pinlu_map=unihan_pinlu_map,
            pinlu_detail_map=unihan_pinlu_detail_map,
            phrase_term_count_map=phrase_term_count_map,
            phrase_support_sum_map=phrase_support_sum_map,
            leading_term_count_map=leading_term_count_map,
            leading_support_sum_map=leading_support_sum_map,
        )
        if delta == 0:
            continue

        current = mapping[key]
        adjusted = max(1, min(1000, current + delta))
        if adjusted == current:
            continue

        mapping[key] = adjusted
        stats[f"{stats_prefix}_single_char_reading_preference_adjusted"] += 1
        stats[f"{stats_prefix}_single_char_reading_preference_delta_total"] += (
            adjusted - current
        )

    return stats


def _adjust_single_char_leading_preferences(
    mapping: Dict[Tuple[str, str], int],
    leading_term_count_map: Dict[Tuple[str, str], int] | None,
    leading_support_sum_map: Dict[Tuple[str, str], float] | None,
    family_term_count_map: Dict[str, int] | None,
    family_support_sum_map: Dict[str, float] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    stats_prefix: str,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_single_char_leading_adjusted": 0,
        f"{stats_prefix}_single_char_leading_delta_total": 0,
    }
    if not mapping:
        return stats

    leading_term_count_map = leading_term_count_map or {}
    leading_support_sum_map = leading_support_sum_map or {}
    family_term_count_map = family_term_count_map or {}
    family_support_sum_map = family_support_sum_map or {}
    unihan_pinlu_detail_map = unihan_pinlu_detail_map or {}

    buckets: Dict[str, List[Tuple[str, int]]] = {}
    for key, weight in mapping.items():
        pinyin, text = key
        if _cjk_len(text) != 1:
            continue
        buckets.setdefault(pinyin, []).append((text, weight))

    for pinyin, items in buckets.items():
        if len(items) < 2:
            continue

        bucket_best_leading_support = 0.0
        for text, _weight in items:
            bucket_best_leading_support = max(
                bucket_best_leading_support,
                leading_support_sum_map.get((text, pinyin), 0.0),
            )
        if bucket_best_leading_support < 120.0:
            continue

        for text, current in items:
            pair = (text, pinyin)
            leading_support = max(0.0, leading_support_sum_map.get(pair, 0.0))
            leading_term_count = max(0, leading_term_count_map.get(pair, 0))
            family_support = max(0.0, family_support_sum_map.get(text, 0.0))
            family_term_count = max(0, family_term_count_map.get(text, 0))
            reading_pinlu = max(0, unihan_pinlu_detail_map.get(pair, 0))
            leading_ratio = (
                leading_support / family_support if family_support > 0.0 else 0.0
            )
            meaningful_leading_presence = (
                leading_support >= 260.0 and leading_term_count >= 3
            )
            strong_leading_presence = (
                leading_support >= 520.0 and leading_term_count >= 6
            )
            high_pinlu_mainstream_competitor = False
            for other_text, _other_weight in items:
                if other_text == text:
                    continue
                other_pinlu = max(0, unihan_pinlu_detail_map.get((other_text, pinyin), 0))
                if (
                    other_pinlu >= 500
                    and other_pinlu >= max(reading_pinlu * 2.5, reading_pinlu + 400)
                ):
                    high_pinlu_mainstream_competitor = True
                    break

            delta = 0
            if (
                leading_support >= 3000.0
                and leading_term_count >= 24
                and leading_ratio >= 0.55
                and not high_pinlu_mainstream_competitor
            ):
                # Strong compound-head evidence is a better IME prior than
                # raw standalone frequency for many action/common characters.
                delta += 132
            elif (
                leading_support >= 10000.0
                and leading_term_count >= 80
                and leading_ratio >= 0.30
            ):
                delta += 96
            elif (
                bucket_best_leading_support >= 8000.0
                and leading_support >= bucket_best_leading_support * 0.82
                and leading_support >= 8000.0
                and leading_term_count >= 20
                and leading_ratio >= 0.32
            ):
                # A character can be common as a compound head even when its
                # standalone corpus count is modest. Use same-reading compound
                # evidence instead of enumerating such characters one by one.
                delta += 132 if leading_ratio >= 0.55 else 96
            elif (
                reading_pinlu >= 3000
                and leading_support >= 1200.0
                and leading_ratio >= 0.70
            ):
                delta += 120
            elif (
                reading_pinlu >= 1000
                and bucket_best_leading_support >= 1600.0
                and leading_support >= bucket_best_leading_support * 0.88
                and leading_support >= 1800.0
                and leading_term_count >= 8
                and leading_ratio >= 0.38
            ):
                # A lower Unihan Pinlu standalone count should not bury a
                # character that dominates same-pinyin compound heads in
                # everyday lexicon evidence. This keeps single-character
                # ordering aligned with modern IME usage without per-character
                # overrides.
                delta += 164
            elif (
                reading_pinlu >= 1000
                and bucket_best_leading_support >= 1200.0
                and leading_support >= bucket_best_leading_support * 0.72
                and leading_support >= 1200.0
                and leading_term_count >= 6
                and leading_ratio >= 0.34
            ):
                delta += 76
            elif (
                reading_pinlu >= 3000
                and leading_support >= 1500.0
                and leading_ratio >= 0.20
            ):
                delta += 72
            elif (
                reading_pinlu >= 1000
                and leading_support >= 800.0
                and leading_ratio >= 0.45
            ):
                delta += 60
            elif (
                reading_pinlu >= 3000
                and leading_support >= 1500.0
                and leading_ratio >= 0.20
            ):
                delta += 48
            elif (
                reading_pinlu >= 150
                and leading_support >= 1500.0
                and leading_ratio >= 0.45
            ):
                delta += 24

            # Some high-frequency standalone characters are common even when
            # they do not dominate as the first character of compounds.
            # Give them a modest absolute-leading-support boost so characters
            # like "是/里/还" are not buried behind less common homophones.
            if reading_pinlu >= 6000 and strong_leading_presence:
                delta += 72
            elif reading_pinlu >= 3000 and meaningful_leading_presence:
                delta += 36

            if bucket_best_leading_support >= 800.0 and reading_pinlu >= 3000:
                if leading_support >= bucket_best_leading_support * 0.88:
                    delta += 36
                elif leading_support >= bucket_best_leading_support * 0.60:
                    delta += 12

            if (
                reading_pinlu >= 3000
                and family_support >= 10000.0
                and family_term_count >= 24
                and leading_ratio < 0.18
            ):
                if not meaningful_leading_presence:
                    delta -= 180
                elif not strong_leading_presence:
                    delta -= 60
            elif (
                reading_pinlu >= 3000
                and family_support >= 6000.0
                and family_term_count >= 12
                and leading_ratio < 0.22
            ):
                if not meaningful_leading_presence:
                    delta -= 120
                elif leading_support < 360.0 or leading_term_count < 4:
                    delta -= 36

            if text in DAILY_CHAT_SEED_CHARS:
                # Single-character IME usage is not the same as raw character
                # frequency inside compounds. Keep common standalone/action
                # characters competitive without per-reading overrides.
                delta += 132 if current < 760 else 48

            if delta == 0:
                continue

            adjusted = max(1, min(1000, current + delta))
            if adjusted == current:
                continue

            mapping[(pinyin, text)] = adjusted
            stats[f"{stats_prefix}_single_char_leading_adjusted"] += 1
            stats[f"{stats_prefix}_single_char_leading_delta_total"] += (
                adjusted - current
            )

    return stats


def _rebalance_single_char_homophones_by_leading_support(
    mapping: Dict[Tuple[str, str], int],
    leading_term_count_map: Dict[Tuple[str, str], int] | None,
    leading_support_sum_map: Dict[Tuple[str, str], float] | None,
    family_support_sum_map: Dict[str, float] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    stats_prefix: str,
    single_char_frequency_map: Dict[str, float] | None = None,
) -> Dict[str, int]:
    """Prefer modern compound-head evidence over raw Unihan frequency for single chars.

    Unihan Pinlu is useful, but for IME single-character ordering it can
    over-favor literary/written characters.  When a same-pinyin character is
    clearly more productive as the first character of modern lexicon words,
    keep weaker compound-head competitors below it.  This is intentionally
    bucket-local and data-driven; no character-specific overrides are used.
    """
    stats = {
        f"{stats_prefix}_single_char_leading_rebalanced": 0,
        f"{stats_prefix}_single_char_leading_rebalanced_buckets": 0,
    }
    if not mapping:
        return stats

    leading_term_count_map = leading_term_count_map or {}
    leading_support_sum_map = leading_support_sum_map or {}
    family_support_sum_map = family_support_sum_map or {}
    unihan_pinlu_detail_map = unihan_pinlu_detail_map or {}
    single_char_frequency_map = single_char_frequency_map or {}

    buckets: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        if _cjk_len(text) != 1:
            continue
        buckets.setdefault(pinyin, []).append((text, weight))

    for pinyin, items in buckets.items():
        if len(items) < 2:
            continue

        records: List[Dict[str, float | int | str]] = []
        for text, weight in items:
            pair = (text, pinyin)
            leading_support = max(0.0, leading_support_sum_map.get(pair, 0.0))
            leading_count = max(0, leading_term_count_map.get(pair, 0))
            family_support = max(0.0, family_support_sum_map.get(text, 0.0))
            leading_ratio = leading_support / family_support if family_support > 0.0 else 0.0
            records.append(
                {
                    "text": text,
                    "weight": weight,
                    "leading_support": leading_support,
                    "leading_count": leading_count,
                    "leading_ratio": leading_ratio,
                    "pinlu": max(0, unihan_pinlu_detail_map.get(pair, 0)),
                    "standalone_frequency": max(
                        0.0, single_char_frequency_map.get(text, 0.0)
                    ),
                }
            )

        eligible = [
            record
            for record in records
            if float(record["leading_support"]) >= 1200.0
            and int(record["leading_count"]) >= 6
            and float(record["leading_ratio"]) >= 0.24
            and int(record["pinlu"]) >= 1000
        ]
        if not eligible:
            continue

        leader = max(
            eligible,
            key=lambda item: (
                float(item["leading_support"]),
                int(item["leading_count"]),
                float(item["leading_ratio"]),
                int(item["pinlu"]),
            ),
        )
        leader_text = str(leader["text"])
        leader_weight = int(leader["weight"])
        leader_support = float(leader["leading_support"])
        leader_count = int(leader["leading_count"])
        leader_ratio = float(leader["leading_ratio"])
        leader_pinlu = int(leader["pinlu"])
        leader_frequency = float(leader["standalone_frequency"])

        bucket_touched = False
        for record in records:
            text = str(record["text"])
            if text == leader_text:
                continue

            weight = int(record["weight"])
            leading_support = float(record["leading_support"])
            leading_count = int(record["leading_count"])
            leading_ratio = float(record["leading_ratio"])
            pinlu = int(record["pinlu"])
            standalone_frequency = float(record["standalone_frequency"])

            leader_independent_usage_dominant = (
                leader_frequency
                >= max(standalone_frequency * 5.0, standalone_frequency + 30000.0)
                and leader_pinlu >= max(pinlu * 1.25, pinlu + 240)
                and leader_support >= max(1200.0, leading_support * 0.70)
            )

            clear_leading_advantage = (
                leader_support >= max(leading_support * 1.35, leading_support + 900.0)
                or (
                    leader_ratio >= max(leading_ratio * 1.75, leading_ratio + 0.16)
                    and leader_support >= leading_support + 600.0
                )
                or (leader_count >= leading_count + 28 and leader_support >= leading_support + 600.0)
                or leader_independent_usage_dominant
            )
            if not clear_leading_advantage:
                continue

            # Do not overturn an overwhelmingly stronger standalone reading.
            if pinlu > max(leader_pinlu * 3.2, leader_pinlu + 4200):
                continue

            # Absolute compound-head support can grow when a batch of related
            # words is added.  Do not let a broader root suppress a candidate
            # whose support is more concentrated in the same-pinyin head role.
            if (
                not leader_independent_usage_dominant
                and leading_ratio >= leader_ratio + 0.08
                and leading_support >= leader_support * 0.42
            ):
                continue

            if (
                not leader_independent_usage_dominant
                and leading_ratio >= leader_ratio * 0.72
                and leading_support >= leader_support * 0.82
            ):
                continue

            cap = max(1, leader_weight - 24)
            if weight <= cap:
                continue

            mapping[(pinyin, text)] = cap
            stats[f"{stats_prefix}_single_char_leading_rebalanced"] += 1
            bucket_touched = True

        if bucket_touched:
            stats[f"{stats_prefix}_single_char_leading_rebalanced_buckets"] += 1

    return stats


def _promote_single_char_homophones_by_head_productivity(
    mapping: Dict[Tuple[str, str], int],
    leading_term_count_map: Dict[Tuple[str, str], int] | None,
    leading_support_sum_map: Dict[Tuple[str, str], float] | None,
    family_support_sum_map: Dict[str, float] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    stats_prefix: str,
    single_char_frequency_map: Dict[str, float] | None = None,
    single_char_pos_map: Dict[str, str] | None = None,
) -> Dict[str, int]:
    """Lift productive same-pinyin word-head characters above broad root noise.

    Some single characters inherit high weight from many related compounds, but
    are weaker as a modern IME word-head choice.  In the same pinyin bucket, a
    character with strong leading ratio and enough absolute support should not
    be buried behind a broader but less head-productive root.  This is a
    bucket-local signal rule, not a per-character override.
    """
    stats = {
        f"{stats_prefix}_single_char_head_productive_promoted": 0,
        f"{stats_prefix}_single_char_head_productive_buckets": 0,
        f"{stats_prefix}_single_char_input_signal_promoted": 0,
        f"{stats_prefix}_single_char_input_signal_buckets": 0,
        f"{stats_prefix}_single_char_concentrated_head_restored": 0,
        f"{stats_prefix}_single_char_concentrated_head_buckets": 0,
    }
    if not mapping:
        return stats

    leading_term_count_map = leading_term_count_map or {}
    leading_support_sum_map = leading_support_sum_map or {}
    family_support_sum_map = family_support_sum_map or {}
    unihan_pinlu_detail_map = unihan_pinlu_detail_map or {}
    single_char_frequency_map = single_char_frequency_map or {}
    single_char_pos_map = single_char_pos_map or {}

    def input_pos_bonus(pos_tag: str) -> int:
        if pos_tag in {"a", "ad", "an"}:
            return 160
        if pos_tag in {"v", "vd", "vn"}:
            return 150
        if pos_tag in {"d", "r", "p", "c"}:
            return 120
        if pos_tag in {"q", "m"}:
            return 80
        if pos_tag in {"ns", "nr", "nt", "nz"}:
            return -120
        if pos_tag in {"t", "tg"}:
            return -110
        if pos_tag == "zg":
            # General morpheme tags include common standalone IME targets such
            # as "选".  Do not penalize them like temporal/location tags; the
            # bucket-local frequency and Pinlu signals decide whether they rise.
            return -12
        if pos_tag == "n":
            return -36
        return 0

    buckets: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        if _cjk_len(text) != 1:
            continue
        buckets.setdefault(pinyin, []).append((text, weight))

    for pinyin, items in buckets.items():
        if len(items) < 2:
            continue

        records: List[Dict[str, float | int | str]] = []
        for text, weight in items:
            pair = (text, pinyin)
            family_support = max(0.0, family_support_sum_map.get(text, 0.0))
            leading_support = max(0.0, leading_support_sum_map.get(pair, 0.0))
            records.append(
                {
                    "text": text,
                    "weight": weight,
                    "pinlu": max(0, unihan_pinlu_detail_map.get(pair, 0)),
                    "family": family_support,
                    "leading": leading_support,
                    "leading_count": max(0, leading_term_count_map.get(pair, 0)),
                    "leading_ratio": leading_support / family_support
                    if family_support > 0.0
                    else 0.0,
                    "standalone_frequency": max(
                        0.0, single_char_frequency_map.get(text, 0.0)
                    ),
                    "pos": single_char_pos_map.get(text, ""),
                }
            )

        bucket_touched = False
        for record in records:
            text = str(record["text"])
            weight = int(record["weight"])
            pinlu = int(record["pinlu"])
            standalone_frequency = float(record["standalone_frequency"])
            leading = float(record["leading"])
            leading_count = int(record["leading_count"])
            leading_ratio = float(record["leading_ratio"])

            if weight < 240:
                continue
            if pinlu < 80:
                continue
            if leading < 4200.0 or leading_count < 18 or leading_ratio < 0.52:
                continue

            target = weight
            for competitor in records:
                competitor_text = str(competitor["text"])
                if competitor_text == text:
                    continue
                competitor_weight = int(competitor["weight"])
                if competitor_weight <= target:
                    continue

                competitor_pinlu = int(competitor["pinlu"])
                competitor_frequency = float(competitor["standalone_frequency"])
                competitor_leading = float(competitor["leading"])
                competitor_count = int(competitor["leading_count"])
                competitor_ratio = float(competitor["leading_ratio"])

                if competitor_ratio >= leading_ratio - 0.12:
                    continue
                if (
                    competitor_frequency
                    >= max(standalone_frequency * 5.0, standalone_frequency + 30000.0)
                    and competitor_pinlu >= max(pinlu * 1.25, pinlu + 240)
                ):
                    # Productive compound heads must not overtake a character
                    # with overwhelmingly stronger independent usage evidence.
                    continue
                if leading < max(competitor_leading * 0.50, 3600.0):
                    continue
                if leading_count < max(12, int(round(competitor_count * 0.45))):
                    continue
                # Keep genuinely dominant standalone readings stable.
                if competitor_pinlu > max(pinlu * 6, pinlu + 1800):
                    continue

                target = max(target, min(760, competitor_weight + 8))

            if target <= weight:
                continue

            mapping[(pinyin, text)] = target
            stats[f"{stats_prefix}_single_char_head_productive_promoted"] += 1
            bucket_touched = True

        if bucket_touched:
            stats[f"{stats_prefix}_single_char_head_productive_buckets"] += 1

        signal_touched = False
        max_bucket_weight = max(int(record["weight"]) for record in records)
        for record in records:
            text = str(record["text"])
            weight = int(mapping.get((pinyin, text), int(record["weight"])))
            pinlu = int(record["pinlu"])
            standalone_frequency = float(record["standalone_frequency"])
            leading = float(record["leading"])
            leading_count = int(record["leading_count"])
            leading_ratio = float(record["leading_ratio"])
            pos_tag = str(record["pos"])

            if weight >= max_bucket_weight:
                continue
            if pinlu <= 0 and standalone_frequency <= 0.0:
                continue

            head_bonus = 0
            if leading >= 3600.0 and leading_count >= 18 and leading_ratio >= 0.50:
                head_bonus = 80
            elif leading >= 1800.0 and leading_count >= 10 and leading_ratio >= 0.44:
                head_bonus = 40

            signal = (
                math.log1p(max(0, pinlu)) * 88.0
                + math.log1p(max(0.0, standalone_frequency)) * 30.0
                + float(input_pos_bonus(pos_tag))
                + float(head_bonus)
            )

            better_than_all_heavier = True
            for competitor in records:
                competitor_text = str(competitor["text"])
                if competitor_text == text:
                    continue
                competitor_weight = int(
                    mapping.get((pinyin, competitor_text), int(competitor["weight"]))
                )
                if competitor_weight <= weight:
                    continue

                competitor_pinlu = int(competitor["pinlu"])
                competitor_frequency = float(competitor["standalone_frequency"])
                competitor_leading = float(competitor["leading"])
                competitor_count = int(competitor["leading_count"])
                competitor_ratio = float(competitor["leading_ratio"])
                competitor_pos = str(competitor["pos"])
                competitor_head_bonus = 0
                if (
                    competitor_leading >= 3600.0
                    and competitor_count >= 18
                    and competitor_ratio >= 0.50
                ):
                    competitor_head_bonus = 80
                elif (
                    competitor_leading >= 1800.0
                    and competitor_count >= 10
                    and competitor_ratio >= 0.44
                ):
                    competitor_head_bonus = 40
                competitor_signal = (
                    math.log1p(max(0, competitor_pinlu)) * 88.0
                    + math.log1p(max(0.0, competitor_frequency)) * 30.0
                    + float(input_pos_bonus(competitor_pos))
                    + float(competitor_head_bonus)
                )

                if (
                    competitor_frequency
                    >= max(standalone_frequency * 5.0, standalone_frequency + 30000.0)
                    and competitor_pinlu >= max(pinlu * 1.25, pinlu + 240)
                ):
                    better_than_all_heavier = False
                    break

                if (
                    competitor_pinlu >= max(pinlu * 3.8, pinlu + 420)
                    and competitor_frequency >= max(
                        standalone_frequency * 1.28,
                        standalone_frequency + 1200.0,
                    )
                ):
                    better_than_all_heavier = False
                    break
                candidate_pinlu_frequency_dominant = (
                    pinlu >= max(competitor_pinlu * 3.5, competitor_pinlu + 420)
                    and standalone_frequency
                    >= max(competitor_frequency * 1.25, competitor_frequency + 1200.0)
                )
                if candidate_pinlu_frequency_dominant:
                    if signal + 96.0 < competitor_signal:
                        better_than_all_heavier = False
                        break
                    continue
                if signal < competitor_signal + 72.0:
                    better_than_all_heavier = False
                    break

            if not better_than_all_heavier:
                continue

            target = min(780, max_bucket_weight + 8)
            if target <= weight:
                continue

            mapping[(pinyin, text)] = target
            stats[f"{stats_prefix}_single_char_input_signal_promoted"] += 1
            signal_touched = True

        if signal_touched:
            stats[f"{stats_prefix}_single_char_input_signal_buckets"] += 1

        restore_touched = False
        current_leader = max(
            records,
            key=lambda item: int(mapping.get((pinyin, str(item["text"])), int(item["weight"]))),
        )
        leader_text = str(current_leader["text"])
        leader_weight = int(
            mapping.get((pinyin, leader_text), int(current_leader["weight"]))
        )
        leader_leading = float(current_leader["leading"])
        leader_ratio = float(current_leader["leading_ratio"])
        for record in records:
            text = str(record["text"])
            if text == leader_text:
                continue

            weight = int(mapping.get((pinyin, text), int(record["weight"])))
            if weight >= leader_weight - 32:
                continue

            pinlu = int(record["pinlu"])
            leading = float(record["leading"])
            leading_count = int(record["leading_count"])
            leading_ratio = float(record["leading_ratio"])
            if pinlu < 80:
                continue
            if leading < 3600.0 or leading_count < 18 or leading_ratio < 0.50:
                continue
            if leading_ratio < leader_ratio + 0.02:
                continue
            if leader_leading > 0.0 and leading < leader_leading * 0.42:
                continue

            target = max(weight, min(780, leader_weight - 8))
            if target <= weight:
                continue

            mapping[(pinyin, text)] = target
            stats[f"{stats_prefix}_single_char_concentrated_head_restored"] += 1
            restore_touched = True

        if restore_touched:
            stats[f"{stats_prefix}_single_char_concentrated_head_buckets"] += 1

    return stats


def _enforce_single_char_relative_order_overrides(
    mapping: Dict[Tuple[str, str], int],
    stats_prefix: str,
) -> Dict[str, int]:
    """Apply final audited ordering for rare single-character tie failures."""
    stats = {f"{stats_prefix}_single_char_relative_order_adjusted": 0}
    for preferred_key, competitor_key, margin in SINGLE_CHAR_RELATIVE_ORDER_OVERRIDES:
        if preferred_key not in mapping or competitor_key not in mapping:
            continue
        preferred_weight = mapping[preferred_key]
        competitor_weight = mapping[competitor_key]
        target_weight = min(1000, competitor_weight + margin)
        if preferred_weight >= target_weight:
            continue
        mapping[preferred_key] = target_weight
        stats[f"{stats_prefix}_single_char_relative_order_adjusted"] += 1
    return stats


def _dampen_compound_root_inflated_single_chars(
    mapping: Dict[Tuple[str, str], int],
    leading_support_sum_map: Dict[Tuple[str, str], float] | None,
    family_support_sum_map: Dict[str, float] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    single_char_frequency_map: Dict[str, float] | None,
    stats_prefix: str,
) -> Dict[str, int]:
    """Keep compound-root evidence from dominating standalone single-char order.

    Family/leading support is useful for keeping productive characters visible,
    but it is not the same as standalone IME usefulness.  In a same-pinyin
    bucket, a content root that is inflated mostly by many compounds should not
    outrank a comparable standalone-frequency competitor whose support is not
    compound-heavy.  The rule is bucket-local and signal-based; it does not name
    individual characters.
    """
    stats = {
        f"{stats_prefix}_single_char_compound_root_capped": 0,
        f"{stats_prefix}_single_char_compound_root_buckets": 0,
    }
    if not mapping:
        return stats

    leading_support_sum_map = leading_support_sum_map or {}
    family_support_sum_map = family_support_sum_map or {}
    unihan_pinlu_detail_map = unihan_pinlu_detail_map or {}
    single_char_frequency_map = single_char_frequency_map or {}

    buckets: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        if _cjk_len(text) != 1:
            continue
        buckets.setdefault(pinyin, []).append((text, weight))

    for pinyin, items in buckets.items():
        if len(items) < 2:
            continue

        records: List[Dict[str, float | int | str]] = []
        for text, weight in items:
            pair = (text, pinyin)
            records.append(
                {
                    "text": text,
                    "weight": weight,
                    "pinlu": max(0, unihan_pinlu_detail_map.get(pair, 0)),
                    "standalone_frequency": max(0.0, single_char_frequency_map.get(text, 0.0)),
                    "family": max(0.0, family_support_sum_map.get(text, 0.0)),
                    "leading": max(0.0, leading_support_sum_map.get(pair, 0.0)),
                }
            )

        bucket_touched = False
        for record in records:
            text = str(record["text"])
            weight = int(record["weight"])
            pinlu = int(record["pinlu"])
            standalone_frequency = float(record["standalone_frequency"])
            family = float(record["family"])
            leading = float(record["leading"])

            if text in DAILY_CHAT_SEED_CHARS:
                continue
            if text in DAILY_NUMBER_WORD_CHARS:
                continue
            if weight < 460:
                continue
            if family < 12000.0 and leading < 3600.0:
                continue
            if pinlu <= 0:
                continue
            if standalone_frequency <= 0.0:
                continue

            best_competitor: Dict[str, float | int | str] | None = None
            for competitor in records:
                competitor_text = str(competitor["text"])
                if competitor_text == text:
                    continue

                competitor_weight = int(competitor["weight"])
                competitor_pinlu = int(competitor["pinlu"])
                competitor_standalone_frequency = float(competitor["standalone_frequency"])
                competitor_family = float(competitor["family"])
                competitor_leading = float(competitor["leading"])
                if competitor_weight < 360 or competitor_pinlu <= 0:
                    continue
                if competitor_standalone_frequency < max(
                    standalone_frequency * 8.0,
                    standalone_frequency + 30000.0,
                ):
                    continue
                if competitor_pinlu < max(480, int(round(pinlu * 0.45))):
                    continue
                if competitor_family > max(2600.0, family * 0.35):
                    continue
                if leading > 0.0 and competitor_leading > max(900.0, leading * 0.35):
                    continue

                if best_competitor is None:
                    best_competitor = competitor
                    continue
                if (
                    competitor_weight,
                    int(round(competitor_standalone_frequency)),
                    competitor_pinlu,
                    -int(round(competitor_family)),
                ) > (
                    int(best_competitor["weight"]),
                    int(round(float(best_competitor["standalone_frequency"]))),
                    int(best_competitor["pinlu"]),
                    -int(round(float(best_competitor["family"]))),
                ):
                    best_competitor = competitor

            if best_competitor is None:
                continue

            cap = max(1, int(best_competitor["weight"]) - 8)
            if weight <= cap:
                continue

            mapping[(pinyin, text)] = cap
            stats[f"{stats_prefix}_single_char_compound_root_capped"] += 1
            bucket_touched = True

        if bucket_touched:
            stats[f"{stats_prefix}_single_char_compound_root_buckets"] += 1

    return stats


def _restore_common_polyphonic_reading_visibility(
    mapping: Dict[Tuple[str, str], int],
    competing_single_char_map: Dict[Tuple[str, str], int] | None,
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_mandarin_map: Dict[str, str] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    phrase_term_count_map: Dict[Tuple[str, str], int] | None,
    phrase_support_sum_map: Dict[Tuple[str, str], float] | None,
    visibility_phrase_term_count_map: Dict[Tuple[str, str], int] | None,
    visibility_phrase_support_sum_map: Dict[Tuple[str, str], float] | None,
    inferred_phrase_term_count_map: Dict[Tuple[str, str], int] | None,
    inferred_phrase_support_sum_map: Dict[Tuple[str, str], float] | None,
    visibility_inferred_phrase_term_count_map: Dict[Tuple[str, str], int] | None,
    visibility_inferred_phrase_support_sum_map: Dict[Tuple[str, str], float] | None,
    family_term_count_map: Dict[str, int] | None,
    visibility_family_term_count_map: Dict[str, int] | None,
    single_char_frequency_map: Dict[str, float] | None,
    single_char_pos_map: Dict[str, str] | None,
    explicit_pinyin_overrides: Dict[str, str] | None,
    stats_prefix: str,
    visible_rank: int = 9,
    common_char_min_frequency: float = 150.0,
) -> Dict[str, int]:
    """Keep valid readings of common polyphonic characters visibly ranked.

    A cold reading can be rare while its character remains familiar to users.
    Treat the character's standalone frequency and modern phrase alignments as
    separate signals, and also honor audited single-character reading aliases.
    High-confidence readings use the first page, while weaker evidence is
    limited to the second or third page. The final adjustment is bucket-local
    and runs after global calibration.
    """
    stats = {
        f"{stats_prefix}_common_polyphonic_readings_eligible": 0,
        f"{stats_prefix}_common_polyphonic_readings_explicit": 0,
        f"{stats_prefix}_common_polyphonic_readings_direct": 0,
        f"{stats_prefix}_common_polyphonic_readings_modern_primary": 0,
        f"{stats_prefix}_common_polyphonic_readings_sparse_pinlu": 0,
        f"{stats_prefix}_common_polyphonic_readings_corpus_pinlu": 0,
        f"{stats_prefix}_common_polyphonic_readings_inferred": 0,
        f"{stats_prefix}_common_polyphonic_readings_first_page": 0,
        f"{stats_prefix}_common_polyphonic_readings_second_page": 0,
        f"{stats_prefix}_common_polyphonic_readings_third_page": 0,
        f"{stats_prefix}_common_polyphonic_readings_visibility_overflow": 0,
        f"{stats_prefix}_common_polyphonic_readings_restored": 0,
        f"{stats_prefix}_common_polyphonic_reading_buckets": 0,
        f"{stats_prefix}_common_polyphonic_readings_unresolved": 0,
    }
    if not mapping or visible_rank <= 0:
        return stats

    competing_single_char_map = competing_single_char_map or {}
    unihan_readings_map = unihan_readings_map or {}
    unihan_mandarin_map = unihan_mandarin_map or {}
    unihan_pinlu_detail_map = unihan_pinlu_detail_map or {}
    phrase_term_count_map = phrase_term_count_map or {}
    phrase_support_sum_map = phrase_support_sum_map or {}
    visibility_phrase_term_count_map = visibility_phrase_term_count_map or {}
    visibility_phrase_support_sum_map = visibility_phrase_support_sum_map or {}
    inferred_phrase_term_count_map = inferred_phrase_term_count_map or {}
    inferred_phrase_support_sum_map = inferred_phrase_support_sum_map or {}
    visibility_inferred_phrase_term_count_map = (
        visibility_inferred_phrase_term_count_map or {}
    )
    visibility_inferred_phrase_support_sum_map = (
        visibility_inferred_phrase_support_sum_map or {}
    )
    family_term_count_map = family_term_count_map or {}
    visibility_family_term_count_map = visibility_family_term_count_map or {}
    single_char_frequency_map = single_char_frequency_map or {}
    single_char_pos_map = single_char_pos_map or {}
    explicit_pinyin_overrides = explicit_pinyin_overrides or {}

    bucket_maps: Dict[str, Dict[str, int]] = {}
    for source_map in (competing_single_char_map, mapping):
        for (pinyin, text), weight in source_map.items():
            if _cjk_len(text) != 1:
                continue
            bucket = bucket_maps.setdefault(pinyin, {})
            bucket[text] = max(bucket.get(text, 0), weight)

    for pinyin, bucket in bucket_maps.items():
        items = list(bucket.items())
        if len(items) <= visible_rank:
            continue

        ordered = sorted(items, key=lambda item: (-item[1], item[0]))
        eligible: List[Tuple[int, str, int, float, int, float, int]] = []
        for rank_index, (text, current_weight) in enumerate(ordered):
            if (pinyin, text) not in mapping:
                continue
            pair = (text, pinyin)
            readings = unihan_readings_map.get(text, set())
            if len(readings) < 2 or unihan_mandarin_map.get(text, "") == pinyin:
                continue
            if single_char_frequency_map.get(text, 0.0) < common_char_min_frequency:
                continue

            phrase_term_count = max(0, phrase_term_count_map.get(pair, 0))
            phrase_support = max(0.0, phrase_support_sum_map.get(pair, 0.0))
            visibility_phrase_term_count = max(
                phrase_term_count, visibility_phrase_term_count_map.get(pair, 0)
            )
            visibility_phrase_support = max(
                phrase_support, visibility_phrase_support_sum_map.get(pair, 0.0)
            )
            inferred_phrase_term_count = max(
                0, inferred_phrase_term_count_map.get(pair, 0)
            )
            inferred_phrase_support = max(
                0.0, inferred_phrase_support_sum_map.get(pair, 0.0)
            )
            visibility_inferred_phrase_term_count = max(
                inferred_phrase_term_count,
                visibility_inferred_phrase_term_count_map.get(pair, 0),
            )
            visibility_inferred_phrase_support = max(
                inferred_phrase_support,
                visibility_inferred_phrase_support_sum_map.get(pair, 0.0),
            )
            family_term_count = max(
                0,
                family_term_count_map.get(text, 0),
                visibility_family_term_count_map.get(text, 0),
            )
            standalone_frequency = max(
                0.0, single_char_frequency_map.get(text, 0.0)
            )
            primary_pinyin = unihan_mandarin_map.get(text, "")
            primary_phrase_term_count = max(
                0, phrase_term_count_map.get((text, primary_pinyin), 0)
            )
            primary_phrase_support = max(
                0.0, phrase_support_sum_map.get((text, primary_pinyin), 0.0)
            )
            visibility_primary_phrase_term_count = max(
                primary_phrase_term_count,
                visibility_phrase_term_count_map.get((text, primary_pinyin), 0),
            )
            visibility_primary_phrase_support = max(
                primary_phrase_support,
                visibility_phrase_support_sum_map.get((text, primary_pinyin), 0.0),
            )
            pos_tag = single_char_pos_map.get(text, "")
            reading_pinlu = max(0, unihan_pinlu_detail_map.get(pair, 0))
            explicitly_audited = explicit_pinyin_overrides.get(text, "") == pinyin
            has_modern_phrase_support = (
                reading_pinlu > 0
                and phrase_term_count >= 2
                and phrase_support >= 48.0
            )
            has_strong_phrase_support = (
                phrase_term_count >= 4 and phrase_support >= 240.0
            )
            has_sparse_pinlu_support = (
                reading_pinlu > 0
                and standalone_frequency >= 3000.0
                and phrase_term_count >= 1
                and phrase_support >= 32.0
            )
            has_corpus_pinlu_support = (
                reading_pinlu >= 8
                and standalone_frequency >= 1000.0
            )
            has_filtered_inferred_modern_phrase_support = (
                (
                    standalone_frequency >= 250.0
                    and family_term_count_map.get(text, 0) >= 5
                    and inferred_phrase_term_count >= 2
                    and inferred_phrase_support >= 96.0
                )
                or (
                    family_term_count_map.get(text, 0) >= 10
                    and inferred_phrase_term_count >= 4
                    and inferred_phrase_support >= 160.0
                )
            )
            has_inferred_modern_phrase_support = (
                (
                    standalone_frequency >= 250.0
                    and family_term_count >= 5
                    and visibility_inferred_phrase_term_count >= 2
                    and visibility_inferred_phrase_support >= 96.0
                )
                or (
                    family_term_count >= 10
                    and visibility_inferred_phrase_term_count >= 4
                    and visibility_inferred_phrase_support >= 160.0
                )
            )
            has_sparse_inferred_modern_phrase_support = (
                standalone_frequency >= 500.0
                and family_term_count >= 5
                and visibility_inferred_phrase_term_count >= 1
                and visibility_inferred_phrase_support >= 12.0
            )
            has_modern_primary_correction = (
                visibility_phrase_term_count >= 2
                and visibility_phrase_support >= 36.0
                and visibility_primary_phrase_term_count == 0
                and visibility_primary_phrase_support <= 0.0
                and (
                    (
                        standalone_frequency >= 300.0
                        and pos_tag not in {"nr", "nrt", "ns", "nz"}
                    )
                    or (standalone_frequency >= 150.0 and pos_tag == "o")
                )
            )
            has_filtered_modern_primary_correction = (
                phrase_term_count >= 2
                and phrase_support >= 36.0
                and primary_phrase_term_count == 0
                and primary_phrase_support <= 0.0
            )
            if not (
                explicitly_audited
                or has_modern_phrase_support
                or has_strong_phrase_support
                or has_sparse_pinlu_support
                or has_corpus_pinlu_support
                or has_inferred_modern_phrase_support
                or has_sparse_inferred_modern_phrase_support
                or has_modern_primary_correction
            ):
                continue

            if explicitly_audited:
                evidence_priority = 4
            elif has_modern_phrase_support or has_strong_phrase_support:
                evidence_priority = 3
            elif has_sparse_pinlu_support:
                evidence_priority = 2
            elif has_corpus_pinlu_support:
                evidence_priority = 2
            elif has_modern_primary_correction:
                evidence_priority = 2
            else:
                evidence_priority = 1
            evidence_support = max(
                phrase_support,
                visibility_inferred_phrase_support,
            )
            isolated_layer_only = (
                (
                    has_modern_primary_correction
                    and not has_filtered_modern_primary_correction
                )
                or (
                    has_inferred_modern_phrase_support
                    and not has_filtered_inferred_modern_phrase_support
                )
                or (
                    has_sparse_inferred_modern_phrase_support
                    and not has_filtered_inferred_modern_phrase_support
                )
            ) and not (
                explicitly_audited
                or has_modern_phrase_support
                or has_strong_phrase_support
                or has_sparse_pinlu_support
                or has_corpus_pinlu_support
            )
            if isolated_layer_only:
                # Evidence from an isolated layer validates the reading, but
                # must not by itself consume a first-page slot.
                desired_rank = visible_rank * 3
                stats[f"{stats_prefix}_common_polyphonic_readings_third_page"] += 1
            elif has_corpus_pinlu_support and not (
                explicitly_audited
                or has_modern_phrase_support
                or has_strong_phrase_support
                or has_sparse_pinlu_support
                or has_filtered_inferred_modern_phrase_support
                or has_filtered_modern_primary_correction
            ):
                # kHanyuPinlu is independent corpus evidence. Very common
                # characters receive first-page visibility; less common ones
                # stay on page two so a cold reading cannot crowd out the
                # primary readings of that syllable.
                if standalone_frequency >= 10000.0:
                    desired_rank = visible_rank
                    stats[f"{stats_prefix}_common_polyphonic_readings_first_page"] += 1
                else:
                    desired_rank = visible_rank * 2
                    stats[f"{stats_prefix}_common_polyphonic_readings_second_page"] += 1
            elif explicitly_audited or standalone_frequency >= 1000.0:
                desired_rank = visible_rank
                stats[f"{stats_prefix}_common_polyphonic_readings_first_page"] += 1
            elif standalone_frequency >= 500.0:
                desired_rank = visible_rank * 2
                stats[f"{stats_prefix}_common_polyphonic_readings_second_page"] += 1
            else:
                desired_rank = visible_rank * 3
                stats[f"{stats_prefix}_common_polyphonic_readings_third_page"] += 1
            eligible.append(
                (
                    rank_index,
                    text,
                    current_weight,
                    standalone_frequency,
                    evidence_priority,
                    evidence_support,
                    desired_rank,
                )
            )
            if explicitly_audited:
                stats[f"{stats_prefix}_common_polyphonic_readings_explicit"] += 1
            elif has_modern_phrase_support or has_strong_phrase_support:
                stats[f"{stats_prefix}_common_polyphonic_readings_direct"] += 1
            elif has_sparse_pinlu_support:
                stats[f"{stats_prefix}_common_polyphonic_readings_sparse_pinlu"] += 1
            elif has_corpus_pinlu_support:
                stats[f"{stats_prefix}_common_polyphonic_readings_corpus_pinlu"] += 1
            elif has_modern_primary_correction:
                stats[f"{stats_prefix}_common_polyphonic_readings_modern_primary"] += 1
            else:
                stats[f"{stats_prefix}_common_polyphonic_readings_inferred"] += 1

        stats[f"{stats_prefix}_common_polyphonic_readings_eligible"] += len(eligible)
        adjusted_texts: Set[str] = set()
        protected_deadlines: Dict[str, int] = {}
        for rank_limit in sorted({item[6] for item in eligible}, reverse=True):
            protected = [item for item in eligible if item[6] <= rank_limit]
            effective_limit = min(rank_limit, len(items))
            if len(protected) > effective_limit:
                stats[
                    f"{stats_prefix}_common_polyphonic_readings_visibility_overflow"
                ] += len(protected) - effective_limit
                protected = sorted(
                    protected,
                    key=lambda item: (
                        -item[3],
                        -item[4],
                        -item[5],
                        -item[2],
                        item[1],
                    ),
                )[:effective_limit]
            for item in protected:
                protected_deadlines[item[1]] = min(
                    rank_limit, protected_deadlines.get(item[1], rank_limit)
                )

            current_ordered = sorted(
                (
                    (
                        text,
                        max(
                            mapping.get((pinyin, text), 0),
                            competing_single_char_map.get((pinyin, text), 0),
                        ),
                    )
                    for text, _weight in items
                ),
                key=lambda item: (-item[1], item[0]),
            )
            current_ranks = {
                text: idx for idx, (text, _weight) in enumerate(current_ordered, 1)
            }
            if all(
                current_ranks.get(item[1], effective_limit + 1) <= effective_limit
                for item in protected
            ):
                continue

            cutoff_index = max(0, effective_limit - len(protected))
            target_weight = min(1000, current_ordered[cutoff_index][1] + 1)
            for (
                _rank_index,
                text,
                _weight,
                _frequency,
                _priority,
                _support,
                _desired_rank,
            ) in protected:
                current_weight = max(
                    mapping.get((pinyin, text), 0),
                    competing_single_char_map.get((pinyin, text), 0),
                )
                if current_weight >= target_weight:
                    continue
                mapping[(pinyin, text)] = target_weight
                adjusted_texts.add(text)

        stats[f"{stats_prefix}_common_polyphonic_readings_restored"] += len(
            adjusted_texts
        )
        updated = sorted(
            (
                (
                    text,
                    max(
                        mapping.get((pinyin, text), 0),
                        competing_single_char_map.get((pinyin, text), 0),
                    ),
                )
                for text, _weight in items
            ),
            key=lambda item: (-item[1], item[0]),
        )
        updated_ranks = {text: idx for idx, (text, _weight) in enumerate(updated, 1)}
        unresolved = sum(
            1
            for text, rank_limit in protected_deadlines.items()
            if updated_ranks.get(text, rank_limit + 1) > rank_limit
        )
        stats[f"{stats_prefix}_common_polyphonic_readings_unresolved"] += unresolved
        if adjusted_texts:
            stats[f"{stats_prefix}_common_polyphonic_reading_buckets"] += 1

    return stats


def _augment_with_frequency_lexicon(
    sc: Dict[Tuple[str, str], int],
    tc: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    tc_usage_score_map: Dict[str, float],
    tc_source_hits_map: Dict[str, int],
    tc_pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    opencc_entries: List[Tuple[str, str]],
    tc_to_sc_map: Dict[str, Set[str]],
    simp_to_trad_char_map: Dict[str, str],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    wiki_titles: Set[str],
    wiki_pinyin_alias_map: Dict[str, Set[str]],
    lexical_seed_terms: Set[str],
    min_hanzi: int,
) -> Tuple[Dict[str, int], Set[str], Set[str], Set[str], Set[str]]:
    stats = {
        "freqlex_terms_total": 0,
        "freqlex_terms_added_sc": 0,
        "freqlex_terms_boosted_sc": 0,
        "freqlex_terms_added_tc": 0,
        "freqlex_terms_boosted_tc": 0,
        "freqlex_skipped_short": 0,
        "freqlex_skipped_non_cjk": 0,
        "freqlex_skipped_no_pinyin": 0,
        "freqlex_skipped_weak_fallback": 0,
        "freqlex_existing_pinyin_hits": 0,
        "freqlex_prefix_seed_pinyin_hits": 0,
        "freqlex_unihan_fallback_hits": 0,
        "freqlex_opencc_tc_hits": 0,
        "freqlex_wiki_alias_added_sc": 0,
        "freqlex_wiki_alias_added_tc": 0,
        "freqlex_wiki_alias_skipped_pinyin_mismatch": 0,
    }

    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    pinyin_index = _build_text_pinyin_index(sc, tc)
    tc_existing_texts = {text for _pinyin, text in tc.keys()}
    char_prior = _build_effective_char_prior(sc, char_frequency_prior)
    wiki_alias_sc_terms: Set[str] = set()
    wiki_alias_tc_terms: Set[str] = set()
    lexical_seed_sc_terms: Set[str] = set()
    lexical_seed_tc_terms: Set[str] = set()

    for word, usage_score in usage_score_map.items():
        stats["freqlex_terms_total"] += 1
        lexical_seeded = word in lexical_seed_terms

        if not CJK_FULL_RE.fullmatch(word):
            stats["freqlex_skipped_non_cjk"] += 1
            continue
        if _cjk_len(word) < min_hanzi:
            stats["freqlex_skipped_short"] += 1
            continue

        pinyin_candidates = sorted(pinyin_index.get(word, set()))
        if pinyin_candidates:
            stats["freqlex_existing_pinyin_hits"] += 1
        else:
            if lexical_seeded:
                derived_candidates = sorted(
                    _derive_prefix_pinyin_candidates_from_longer_terms(
                        word,
                        pinyin_index,
                        unihan_readings_map,
                        unihan_source_rank_map,
                        unihan_map,
                        unihan_pinlu_detail_map,
                    )
                )
                if derived_candidates:
                    pinyin_candidates = derived_candidates
                    stats["freqlex_prefix_seed_pinyin_hits"] += 1

        if not pinyin_candidates:
            fallback = _pinyin_from_unihan(
                word,
                unihan_map,
                unihan_readings_map,
                unihan_source_rank_map,
                unihan_pinlu_detail_map,
            )
            if not fallback:
                stats["freqlex_skipped_no_pinyin"] += 1
                continue
            source_hits = source_hits_map.get(word, 0)
            pageview_score = pageviews_signal_map.get(word, 0.0)
            # Unihan fallback can generate many low-value pseudo-words.
            # Keep only strongly supported terms when no curated pinyin source exists.
            hanzi_len = _cjk_len(word)
            if hanzi_len <= 2:
                allow_fallback = (
                    usage_score >= 0.42
                    or source_hits >= 2
                    or pageview_score >= 0.15
                    or (lexical_seeded and usage_score >= 0.34)
                )
            elif hanzi_len <= 4:
                allow_fallback = (
                    usage_score >= 0.20
                    or source_hits >= 2
                    or pageview_score >= 0.10
                    or (lexical_seeded and usage_score >= 0.18)
                )
            else:
                allow_fallback = (
                    usage_score >= 0.12
                    or source_hits >= 1
                    or pageview_score >= 0.06
                    or (lexical_seeded and usage_score >= 0.16)
                )
            if not allow_fallback:
                stats["freqlex_skipped_weak_fallback"] += 1
                continue
            pinyin_candidates = [fallback]
            stats["freqlex_unihan_fallback_hits"] += 1

        source_hits = source_hits_map.get(word, 0)
        pageview_score = pageviews_signal_map.get(word, 0.0)
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(word, 0.0)))
        pos_tag = jieba_pos_map.get(word, "")
        char_score = _compute_text_single_char_prior(word, char_prior)
        weight = _compute_weight_with_signals(
            word,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            wiki_hit=lexical_seeded
            or _has_effective_wiki_support(
                word,
                wiki_titles,
                pageview_score=pageview_score,
                source_hits=source_hits,
            ),
            core_entry=False,
            jieba_direct_score=jieba_direct_score,
            pos_tag=pos_tag,
            char_score=char_score,
        )
        sc_words = tc_to_sc_map.get(word, set())
        if not sc_words:
            sc_words = {word}
        added_sc = False
        boosted_sc = False
        for sc_word in sc_words:
            if _cjk_len(sc_word) < min_hanzi:
                continue
            for pinyin in pinyin_candidates:
                key = (pinyin, sc_word)
                existing_weight = sc.get(key)
                if lexical_seeded and existing_weight is not None:
                    lexical_seed_sc_terms.add(sc_word)
                if existing_weight is None:
                    sc[key] = weight
                    added_sc = True
                    if lexical_seeded:
                        lexical_seed_sc_terms.add(sc_word)
                elif weight > existing_weight:
                    sc[key] = weight
                    boosted_sc = True
                    if lexical_seeded:
                        lexical_seed_sc_terms.add(sc_word)
        if added_sc:
            stats["freqlex_terms_added_sc"] += 1
        if boosted_sc:
            stats["freqlex_terms_boosted_sc"] += 1

        tc_words = opencc_sc_to_tc.get(word, set())
        if tc_words:
            stats["freqlex_opencc_tc_hits"] += 1
        elif word in tc_existing_texts:
            tc_words = {word}
        else:
            converted_word = _convert_sc_text_to_tc_with_phrase_hints(
                word,
                opencc_sc_to_tc,
                simp_to_trad_char_map,
            )
            if converted_word != word:
                tc_words = {converted_word}

        added_tc = False
        boosted_tc = False
        for tc_word in tc_words:
            if _cjk_len(tc_word) < min_hanzi:
                continue
            tc_char_score = _compute_text_single_char_prior(tc_word, char_prior)
            tc_weight = _compute_weight_with_signals(
                tc_word,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                wiki_hit=lexical_seeded
                or _has_effective_wiki_support(
                    tc_word,
                    wiki_titles,
                    pageview_score=pageview_score,
                    source_hits=source_hits,
                ),
                core_entry=False,
                jieba_direct_score=jieba_direct_score,
                pos_tag=pos_tag,
                char_score=tc_char_score,
            )
            for pinyin in pinyin_candidates:
                key = (pinyin, tc_word)
                existing_weight = tc.get(key)
                if lexical_seeded and existing_weight is not None:
                    lexical_seed_tc_terms.add(tc_word)
                if existing_weight is None:
                    tc[key] = tc_weight
                    added_tc = True
                    if lexical_seeded:
                        lexical_seed_tc_terms.add(tc_word)
                elif tc_weight > existing_weight:
                    tc[key] = tc_weight
                    boosted_tc = True
                    if lexical_seeded:
                        lexical_seed_tc_terms.add(tc_word)
        if added_tc:
            stats["freqlex_terms_added_tc"] += 1
        if boosted_tc:
            stats["freqlex_terms_boosted_tc"] += 1

    for pinyin, wiki_words in wiki_pinyin_alias_map.items():
        for word in sorted(wiki_words):
            if not CJK_FULL_RE.fullmatch(word):
                continue
            text_len = _cjk_len(word)
            if text_len < min_hanzi or text_len > 8:
                continue

            if not _wiki_alias_target_matches_pinyin(
                pinyin,
                word,
                pinyin_index,
                unihan_readings_map,
                unihan_source_rank_map,
                unihan_map,
                unihan_pinlu_detail_map,
            ):
                stats["freqlex_wiki_alias_skipped_pinyin_mismatch"] += 1
                continue

            synthetic_usage_score, synthetic_source_hits, synthetic_pageview_score = (
                _compute_wiki_alias_support_signal(word, wiki_titles)
            )
            pos_tag = jieba_pos_map.get(word, "")
            char_score = _compute_text_single_char_prior(word, char_prior)
            weight = _compute_weight_with_signals(
                word,
                usage_score=synthetic_usage_score,
                source_hits=synthetic_source_hits,
                pageview_score=synthetic_pageview_score,
                wiki_hit=True,
                core_entry=False,
                jieba_direct_score=0.0,
                pos_tag=pos_tag,
                char_score=char_score,
            )

            sc_words = tc_to_sc_map.get(word, set())
            if not sc_words:
                sc_words = {word}
            added_sc = False
            for sc_word in sc_words:
                if _cjk_len(sc_word) < min_hanzi:
                    continue
                usage_score_map[sc_word] = max(
                    synthetic_usage_score,
                    usage_score_map.get(sc_word, 0.0),
                )
                source_hits_map[sc_word] = max(
                    synthetic_source_hits,
                    source_hits_map.get(sc_word, 0),
                )
                pageviews_signal_map[sc_word] = max(
                    synthetic_pageview_score,
                    pageviews_signal_map.get(sc_word, 0.0),
                )
                key = (pinyin, sc_word)
                if key in sc:
                    if weight > sc[key]:
                        sc[key] = weight
                    wiki_alias_sc_terms.add(sc_word)
                    continue
                sc[key] = weight
                added_sc = True
                wiki_alias_sc_terms.add(sc_word)
            if added_sc:
                stats["freqlex_wiki_alias_added_sc"] += 1

            tc_words = opencc_sc_to_tc.get(word, set())
            if tc_words:
                stats["freqlex_opencc_tc_hits"] += 1
            elif word in tc_existing_texts:
                tc_words = {word}
            else:
                converted_word = _convert_text_with_char_map(word, simp_to_trad_char_map)
                if converted_word != word:
                    tc_words = {converted_word}

            added_tc = False
            for tc_word in tc_words:
                if _cjk_len(tc_word) < min_hanzi:
                    continue
                tc_char_score = _compute_text_single_char_prior(tc_word, char_prior)
                tc_weight = _compute_weight_with_signals(
                    tc_word,
                    usage_score=synthetic_usage_score,
                    source_hits=synthetic_source_hits,
                    pageview_score=synthetic_pageview_score,
                    wiki_hit=True,
                    core_entry=False,
                    jieba_direct_score=0.0,
                    pos_tag=jieba_pos_map.get(tc_word, pos_tag),
                    char_score=tc_char_score,
                )
                tc_usage_score_map[tc_word] = max(
                    synthetic_usage_score,
                    tc_usage_score_map.get(tc_word, 0.0),
                )
                tc_source_hits_map[tc_word] = max(
                    synthetic_source_hits,
                    tc_source_hits_map.get(tc_word, 0),
                )
                tc_pageviews_signal_map[tc_word] = max(
                    synthetic_pageview_score,
                    tc_pageviews_signal_map.get(tc_word, 0.0),
                )
                key = (pinyin, tc_word)
                if key in tc:
                    if tc_weight > tc[key]:
                        tc[key] = tc_weight
                    wiki_alias_tc_terms.add(tc_word)
                    continue
                tc[key] = tc_weight
                added_tc = True
                wiki_alias_tc_terms.add(tc_word)
            if added_tc:
                stats["freqlex_wiki_alias_added_tc"] += 1

    return (
        stats,
        wiki_alias_sc_terms,
        wiki_alias_tc_terms,
        lexical_seed_sc_terms,
        lexical_seed_tc_terms,
    )


def _augment_with_daily_prefix_derivation(
    sc: Dict[Tuple[str, str], int],
    tc: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    opencc_entries: List[Tuple[str, str]],
    simp_to_trad_char_map: Dict[str, str],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    min_hanzi: int,
) -> Tuple[Dict[str, int], Set[str], Set[str]]:
    stats = {
        "daily_prefix_source_terms": 0,
        "daily_prefix_pinyin_hits": 0,
        "daily_prefix_added_sc": 0,
        "daily_prefix_boosted_sc": 0,
        "daily_prefix_added_tc": 0,
        "daily_prefix_boosted_tc": 0,
    }
    if not sc and not tc:
        return stats, set(), set()

    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    pinyin_index = _build_text_pinyin_index(sc, tc)
    tc_existing_texts = {text for _pinyin, text in tc.keys()}
    char_prior = _build_effective_char_prior(sc, char_frequency_prior)
    text_best_weight: Dict[str, int] = {}
    for _key, weight in sc.items():
        _pinyin, text = _key
        current = text_best_weight.get(text, 0)
        if weight > current:
            text_best_weight[text] = weight
    for _key, weight in tc.items():
        _pinyin, text = _key
        current = text_best_weight.get(text, 0)
        if weight > current:
            text_best_weight[text] = weight
    sc_terms: Set[str] = set()
    tc_terms: Set[str] = set()
    candidate_texts = sorted(
        {
            text
            for _pinyin, text in list(sc.keys()) + list(tc.keys())
            if _cjk_len(text) >= max(min_hanzi + 1, 3) and _cjk_len(text) <= 5
        }
    )

    for word in candidate_texts:
        if not _looks_like_daily_chat_seed(word):
            continue
        pos_tag = jieba_pos_map.get(word, "")
        if _is_named_entity_pos(pos_tag):
            continue

        usage_score = min(1.0, max(0.0, usage_score_map.get(word, 0.0)))
        source_hits = max(0, source_hits_map.get(word, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(word, 0.0)))
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(word, 0.0)))
        existing_weight = text_best_weight.get(word, 0)
        if (
            usage_score < 0.18
            and jieba_direct_score < 0.10
            and source_hits < 2
            and pageview_score < 0.06
            and existing_weight < 240
        ):
            continue

        stats["daily_prefix_source_terms"] += 1
        word_len = _cjk_len(word)
        for prefix_len in range(2, min(4, word_len - 1) + 1):
            prefix = word[:prefix_len]
            if _is_unsafe_derived_prefix_text(prefix):
                continue
            if not _looks_like_daily_chat_seed(prefix):
                continue
            prefix_char_score = _compute_text_single_char_prior(prefix, char_prior)
            prefix_min_char_prior = _compute_min_char_prior(prefix, char_prior)
            prefix_usage_direct = min(1.0, max(0.0, usage_score_map.get(prefix, 0.0)))
            prefix_source_hits_direct = max(0, source_hits_map.get(prefix, 0))
            prefix_pageview_direct = min(
                1.0,
                max(0.0, pageviews_signal_map.get(prefix, 0.0)),
            )
            prefix_jieba_direct = min(
                1.0,
                max(0.0, jieba_direct_signal_map.get(prefix, 0.0)),
            )
            existing_prefix_weight = text_best_weight.get(prefix, 0)
            if prefix_len == 2:
                if prefix_char_score < 0.14 or prefix_min_char_prior < 0.01:
                    continue
                prefix_usage = max(0.22, usage_score - 0.10)
            elif prefix_len == 3:
                if prefix_char_score < 0.10 or prefix_min_char_prior < 0.01:
                    continue
                prefix_usage = max(0.20, usage_score - 0.08)
            else:
                if prefix_char_score < 0.08 or prefix_min_char_prior < 0.01:
                    continue
                prefix_usage = max(0.18, usage_score - 0.06)

            # Keep daily-chat prefix derivation conservative: the prefix must
            # have some direct evidence of its own instead of inheriting the
            # full strength of a longer phrase wholesale.
            if (
                prefix_usage_direct < 0.08
                and prefix_jieba_direct < 0.05
                and prefix_source_hits_direct < 1
                and prefix_pageview_direct < 0.02
                and existing_prefix_weight < 320
            ):
                continue

            pinyin_candidates = sorted(
                _derive_prefix_pinyin_candidates_from_longer_terms(
                    prefix,
                    pinyin_index,
                    unihan_readings_map,
                    unihan_source_rank_map,
                    unihan_map,
                    unihan_pinlu_detail_map,
                )
            )
            if not pinyin_candidates:
                continue
            stats["daily_prefix_pinyin_hits"] += 1

            blended_usage = max(prefix_usage_direct, min(prefix_usage, prefix_usage_direct + 0.10))
            blended_pageview = max(
                prefix_pageview_direct,
                min(pageview_score * 0.40, prefix_pageview_direct + 0.04),
            )
            blended_source_hits = max(
                prefix_source_hits_direct,
                min(max(1, source_hits), prefix_source_hits_direct + 1),
            )
            blended_jieba_direct = max(
                prefix_jieba_direct,
                min(max(jieba_direct_score, prefix_usage * 0.50), prefix_jieba_direct + 0.10),
            )

            weight = _compute_weight_with_signals(
                prefix,
                usage_score=blended_usage,
                source_hits=blended_source_hits,
                pageview_score=blended_pageview,
                wiki_hit=True,
                core_entry=False,
                jieba_direct_score=blended_jieba_direct,
                pos_tag=pos_tag,
                char_score=prefix_char_score,
            )
            # A prefix derived from a longer daily phrase is supporting
            # evidence, not an explicit curated entry. If it keeps the same
            # ceiling as the source phrase, incomplete input such as "dianl"
            # can prefer a derived prefix ("店里") over a stronger complete
            # conversational phrase ("点了"). Keep derived prefixes visible
            # while leaving room for direct dictionary/user evidence.
            if prefix_len == 2:
                weight = min(weight, 760)
            elif prefix_len == 3:
                weight = min(weight, 860)
            else:
                weight = min(weight, 920)

            sc_words = {prefix}
            added_sc = False
            boosted_sc = False
            for sc_word in sc_words:
                if _cjk_len(sc_word) < min_hanzi:
                    continue
                for pinyin in pinyin_candidates:
                    key = (pinyin, sc_word)
                    existing_weight = sc.get(key)
                    if existing_weight is None:
                        sc[key] = weight
                        added_sc = True
                        sc_terms.add(sc_word)
                    elif weight > existing_weight:
                        sc[key] = weight
                        boosted_sc = True
                        sc_terms.add(sc_word)
            if added_sc:
                stats["daily_prefix_added_sc"] += 1
            if boosted_sc:
                stats["daily_prefix_boosted_sc"] += 1

            tc_words = opencc_sc_to_tc.get(prefix, set())
            if not tc_words:
                if prefix in tc_existing_texts:
                    tc_words = {prefix}
                else:
                    converted = _convert_sc_text_to_tc_with_phrase_hints(
                        prefix,
                        opencc_sc_to_tc,
                        simp_to_trad_char_map,
                    )
                    if converted != prefix:
                        tc_words = {converted}

            added_tc = False
            boosted_tc = False
            for tc_word in tc_words:
                if _cjk_len(tc_word) < min_hanzi:
                    continue
                tc_char_score = _compute_text_single_char_prior(tc_word, char_prior)
                tc_weight = _compute_weight_with_signals(
                    tc_word,
                    usage_score=blended_usage,
                    source_hits=blended_source_hits,
                    pageview_score=blended_pageview,
                    wiki_hit=True,
                    core_entry=False,
                    jieba_direct_score=blended_jieba_direct,
                    pos_tag=pos_tag,
                    char_score=tc_char_score,
                )
                if prefix_len == 2:
                    tc_weight = min(tc_weight, 760)
                elif prefix_len == 3:
                    tc_weight = min(tc_weight, 860)
                else:
                    tc_weight = min(tc_weight, 920)
                for pinyin in pinyin_candidates:
                    key = (pinyin, tc_word)
                    existing_weight = tc.get(key)
                    if existing_weight is None:
                        tc[key] = tc_weight
                        added_tc = True
                        tc_terms.add(tc_word)
                    elif tc_weight > existing_weight:
                        tc[key] = tc_weight
                        boosted_tc = True
                        tc_terms.add(tc_word)
            if added_tc:
                stats["daily_prefix_added_tc"] += 1
            if boosted_tc:
                stats["daily_prefix_boosted_tc"] += 1

    return stats, sc_terms, tc_terms


def _finalize_curated_daily_weight(
    weight: int,
    usage_score: float,
    is_number_word: bool,
    low_frequency: bool = False,
    text: str = "",
) -> int:
    if low_frequency and usage_score < 0.0:
        return 0
    bounded_usage = max(0.0, min(1.0, usage_score))
    if low_frequency:
        if is_number_word:
            number_floor = 400 + int(round(bounded_usage * 120.0))
            return min(
                _curated_daily_supplement_weight_cap(usage_score, text),
                max(weight, number_floor),
            )
        if bounded_usage < 0.10:
            supplement_floor = 1 + int(round(bounded_usage * 120.0))
        else:
            supplement_floor = 220 + int(round(bounded_usage * 80.0))
        return min(
            _curated_daily_supplement_weight_cap(usage_score, text),
            max(weight, supplement_floor),
        )

    if not is_number_word:
        if _is_daily_count_measure_phrase(text):
            count_floor = 440 + int(round(bounded_usage * 120.0))
            count_cap = (
                CURATED_DAILY_HOUSING_COUNT_MEASURE_WEIGHT_CAP
                if _is_daily_housing_count_measure_phrase(text)
                else CURATED_DAILY_COUNT_MEASURE_WEIGHT_CAP
            )
            return min(count_cap, max(weight, count_floor))

        # Daily curated entries serve two different purposes:
        # - high-confidence everyday words should be strong defaults;
        # - useful exact-match supplements should stay visible without
        #   overpowering more common same-pinyin words.
        # A single 1200+ floor for both groups makes entries such as "起始"
        # outrank broader daily words such as "其实". Keep the boost tiered by
        # usage score and never cap independent evidence from other sources.
        if bounded_usage >= 0.90:
            daily_floor = 1000 + int(round((bounded_usage - 0.90) * 900.0))
            return max(weight, daily_floor)

        if bounded_usage < 0.50:
            # Some curated daily entries are useful exact candidates but should
            # sit below stronger same-pinyin common words.  Let explicit low
            # usage scores express that without moving the word to the very
            # low-frequency supplement layer.
            visibility_floor = 420 + int(round(bounded_usage * 400.0))
        else:
            visibility_floor = 540 + int(round(bounded_usage * 300.0))
        visibility_cap = (
            CURATED_DAILY_VISIBILITY_WEIGHT_CAP_SHORT
            if _cjk_len(text) <= 2
            else CURATED_DAILY_VISIBILITY_WEIGHT_CAP_LONG
        )
        return min(visibility_cap, max(weight, visibility_floor))

    # Number words are useful daily entries, but should not be as dominant as
    # conversational words/phrases. Keep them strong enough to surface while
    # leaving room for non-numeric homophones and user learning.
    number_cap = CURATED_DAILY_NUMBER_WEIGHT_CAP
    number_floor = min(
        number_cap,
        840 + int(round(bounded_usage * 110.0)),
    )
    return min(number_cap, max(weight, number_floor))


def _is_daily_count_measure_phrase(text: str) -> bool:
    if not text or CJK_FULL_RE.fullmatch(text) is None:
        return False

    rest = ""
    if text.startswith("每一"):
        rest = text[2:]
    elif text.startswith("每"):
        rest = text[1:]
    elif text[0] in DAILY_COUNT_PREFIX_CHARS:
        rest = text[1:]
    elif (
        text[0] in DAILY_TRADITIONAL_COUNT_PREFIX_CHARS
        and len(text) > 1
        and text[1] == "本"
    ):
        rest = text[1:]

    if not rest:
        return False
    if rest[0] not in DAILY_COUNT_MEASURE_CHARS:
        return False
    if rest[0] == "本":
        return len(rest) == 1 or (len(rest) == 2 and rest[1] in {"书", "書"})
    return True


def _is_daily_housing_count_measure_phrase(text: str) -> bool:
    if not _is_daily_count_measure_phrase(text):
        return False
    if text.startswith("每一"):
        rest = text[2:]
    elif text.startswith("每"):
        rest = text[1:]
    else:
        rest = text[1:]
    return bool(rest) and rest[0] in DAILY_HOUSING_COUNT_MEASURE_CHARS


def _is_pure_daily_number_word(text: str) -> bool:
    if text.startswith("\u7b2c") and len(text) > 1:
        text = text[1:]
    return (
        bool(text)
        and CJK_FULL_RE.fullmatch(text) is not None
        and all(ch in DAILY_NUMBER_WORD_CHARS for ch in text)
        and any(ch in DAILY_NUMBER_WORD_UNIT_CHARS for ch in text)
    )


def _cap_curated_daily_number_weights(
    mapping: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    *,
    use_traditional: bool,
    stats_prefix: str,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_curated_daily_number_cap_terms": 0,
        f"{stats_prefix}_curated_daily_number_cap_rows": 0,
    }
    if not mapping or not curated_entries:
        return stats

    number_terms: Set[str] = set()
    for sc_word, tc_word, _usage_score, _explicit_pinyin in curated_entries:
        text = tc_word if use_traditional and tc_word else sc_word
        if _is_pure_daily_number_word(text) or _is_daily_count_measure_phrase(text):
            number_terms.add(text)

    stats[f"{stats_prefix}_curated_daily_number_cap_terms"] = len(number_terms)
    if not number_terms:
        return stats

    for key, weight in list(mapping.items()):
        _pinyin, text = key
        if text not in number_terms:
            continue
        cap = (
            CURATED_DAILY_HOUSING_COUNT_MEASURE_WEIGHT_CAP
            if _is_daily_housing_count_measure_phrase(text)
            else CURATED_DAILY_COUNT_MEASURE_WEIGHT_CAP
            if _is_daily_count_measure_phrase(text)
            else CURATED_DAILY_NUMBER_WEIGHT_CAP
        )
        if weight <= cap:
            continue
        mapping[key] = cap
        stats[f"{stats_prefix}_curated_daily_number_cap_rows"] += 1

    return stats


def _is_curated_aspect_visibility_term(text: str, usage_score: float) -> bool:
    return (
        _cjk_len(text) == 2
        and len(text) == 2
        and text[-1] in DAILY_ASPECT_SUFFIX_CHARS
        and usage_score < 0.90
    )


def _cap_curated_daily_aspect_visibility_weights(
    mapping: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    *,
    use_traditional: bool,
    stats_prefix: str,
) -> Dict[str, int]:
    """Keep weak verb-aspect daily supplements visible but behind strong words.

    Entries such as "笑过" are valid exact candidates, but they are productive
    verb-aspect forms rather than corpus-frequency evidence. When the same
    pinyin bucket contains a stronger independent word (for example "效果"),
    the aspect form should not become the default solely because it is curated.
    """
    stats = {
        f"{stats_prefix}_curated_daily_aspect_cap_terms": 0,
        f"{stats_prefix}_curated_daily_aspect_cap_rows": 0,
    }
    if not mapping or not curated_entries:
        return stats

    aspect_terms: Dict[str, float] = {}
    for sc_word, tc_word, usage_score, _explicit_pinyin in curated_entries:
        text = tc_word if use_traditional and tc_word else sc_word
        if _is_curated_aspect_visibility_term(text, usage_score):
            aspect_terms[text] = max(aspect_terms.get(text, 0.0), usage_score)
    if not aspect_terms:
        return stats

    buckets: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        buckets.setdefault(pinyin, []).append((text, weight))

    capped_terms: Set[str] = set()

    def direct_signal(text: str) -> float:
        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pos_tag = jieba_pos_map.get(text, "")
        signal = (
            usage_score * 0.44
            + jieba_score * 0.40
            + pageview_score * 0.10
            + min(1.0, source_hits / 5.0) * 0.06
        )
        if _is_conversational_pos(pos_tag):
            signal += 0.04
        elif _is_named_entity_pos(pos_tag):
            signal *= 0.70
        return min(1.0, signal)

    for pinyin, items in buckets.items():
        aspects = [
            (text, weight, aspect_terms[text])
            for text, weight in items
            if text in aspect_terms
        ]
        if not aspects:
            continue
        leaders = [
            (text, weight, direct_signal(text))
            for text, weight in items
            if text not in aspect_terms
            and _cjk_len(text) >= 2
            and _cjk_len(text) <= 4
        ]
        leaders = [
            item for item in leaders
            if item[1] >= 520 and item[2] >= 0.16
        ]
        if leaders:
            leader_text, leader_weight, leader_signal = max(
                leaders,
                key=lambda item: (item[2], item[1]),
            )
            del leader_text, leader_signal
            cap = min(CURATED_DAILY_ASPECT_VISIBILITY_CAP, max(520, leader_weight - 64))
            for text, weight, usage_score in aspects:
                if usage_score >= 0.80:
                    continue
                if weight <= cap:
                    continue
                mapping[(pinyin, text)] = cap
                capped_terms.add(text)
                stats[f"{stats_prefix}_curated_daily_aspect_cap_rows"] += 1

        if len(aspects) >= 2:
            best_usage = max(usage_score for _text, _weight, usage_score in aspects)
            best_weight = max(
                mapping.get((pinyin, text), weight)
                for text, weight, usage_score in aspects
                if usage_score + 0.015 >= best_usage
            )
            for text, weight, usage_score in aspects:
                if usage_score + 0.015 >= best_usage:
                    continue
                current_weight = mapping.get((pinyin, text), weight)
                usage_gap = best_usage - usage_score
                cap_margin = 32 + int(round(usage_gap * 240.0))
                cap = max(420, min(CURATED_DAILY_ASPECT_VISIBILITY_CAP, best_weight - cap_margin))
                if current_weight <= cap:
                    continue
                mapping[(pinyin, text)] = cap
                capped_terms.add(text)
                stats[f"{stats_prefix}_curated_daily_aspect_cap_rows"] += 1

    stats[f"{stats_prefix}_curated_daily_aspect_cap_terms"] = len(capped_terms)
    return stats


def _is_curated_productive_state_visibility_term(text: str, usage_score: float) -> bool:
    """Return whether a curated entry is a productive state phrase.

    Short phrases such as "已签" or "没气" are useful exact candidates, but
    their manifest score mostly encodes product visibility, not broad corpus
    frequency. They should remain selectable without outranking stronger
    independent same-pinyin words such as "以前" or "煤气".
    """
    if (
        _cjk_len(text) < 2
        or _cjk_len(text) > 3
        or len(text) < 2
        or text[0] not in CURATED_PRODUCTIVE_STATE_PREFIX_CHARS
    ):
        return False

    # "没/沒" also forms strong everyday words ("没变", "没钱"). Only treat
    # lower-confidence entries as visibility supplements; otherwise a weak
    # dictionary competitor such as "霉变" can incorrectly become the default.
    if text[0] in ("\u6ca1", "\u6c92"):
        return usage_score < 0.85

    return usage_score <= 0.92


def _cap_curated_productive_visibility_against_direct_leaders(
    mapping: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    *,
    use_traditional: bool,
    stats_prefix: str,
    bucket_pinyin_map: Dict[Tuple[str, str], str] | None = None,
) -> Dict[str, int]:
    """Keep productive curated supplements visible but behind common exact words.

    This is the reverse of the curated-daily leader guard: manually curated
    productive forms and pure number words are valid candidates, but if a same
    pinyin bucket contains an independent word with direct frequency evidence,
    the productive supplement should not become the default just because the
    manifest gave it a visibility boost.
    """
    stats = {
        f"{stats_prefix}_curated_productive_visibility_cap_terms": 0,
        f"{stats_prefix}_curated_productive_visibility_cap_rows": 0,
    }
    if not mapping or not curated_entries:
        return stats

    bucket_pinyin_map = bucket_pinyin_map or {}
    candidate_terms: Dict[str, float] = {}
    number_terms: Set[str] = set()
    for sc_word, tc_word, usage_score, _explicit_pinyin in curated_entries:
        text = tc_word if use_traditional and tc_word else sc_word
        effective_usage = max(usage_score, usage_score_map.get(text, 0.0))
        if _is_curated_productive_state_visibility_term(text, effective_usage):
            candidate_terms[text] = effective_usage
        elif _is_pure_daily_number_word(text):
            candidate_terms[text] = effective_usage
            number_terms.add(text)
    if not candidate_terms:
        return stats

    buckets: Dict[str, List[Tuple[str, str, int]]] = {}
    for key, weight in mapping.items():
        pinyin, text = key
        bucket_pinyin = bucket_pinyin_map.get(key, pinyin)
        if not bucket_pinyin:
            continue
        buckets.setdefault(bucket_pinyin, []).append((pinyin, text, weight))

    def direct_signal(text: str) -> float:
        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        jieba_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pos_tag = jieba_pos_map.get(text, "")
        signal = (
            usage_score * 0.36
            + jieba_score * 0.42
            + pageview_score * 0.12
            + min(1.0, source_hits / 5.0) * 0.10
        )
        if _is_conversational_pos(pos_tag):
            signal += 0.04
        elif _is_noun_pos(pos_tag):
            signal += 0.02
        elif _is_named_entity_pos(pos_tag):
            signal *= 0.70
        return max(0.0, min(1.0, signal))

    capped_terms: Set[str] = set()
    for _bucket_pinyin, items in buckets.items():
        productive_items = [
            (pinyin, text, weight)
            for pinyin, text, weight in items
            if text in candidate_terms
        ]
        if not productive_items:
            continue

        leader_items: List[Tuple[str, int, float]] = []
        for _pinyin, text, weight in items:
            if text in candidate_terms:
                continue
            text_len = _cjk_len(text)
            if text_len < 2 or text_len > 4:
                continue
            if _is_pure_daily_number_word(text):
                continue
            signal = direct_signal(text)
            if weight < 180 or signal < 0.045:
                continue
            if weight < 240 and signal < 0.10:
                continue
            leader_items.append((text, weight, signal))
        if not leader_items:
            continue

        leader_text, leader_weight, leader_signal = max(
            leader_items,
            key=lambda item: (item[2], item[1]),
        )
        if leader_weight < 180 or leader_signal < 0.045:
            continue

        for pinyin, text, weight in productive_items:
            candidate_signal = direct_signal(text)
            candidate_usage = candidate_terms.get(text, 0.0)
            if (
                text not in number_terms
                and candidate_usage >= 0.94
                and candidate_signal + 0.03 >= leader_signal
            ):
                continue

            cap_margin = 36 if text in number_terms else 48
            cap = max(1, leader_weight - cap_margin)
            if text in number_terms:
                cap = min(cap, CURATED_DAILY_SUPPLEMENT_NUMBER_WEIGHT_CAP - 48)
            if weight <= cap:
                continue

            mapping[(pinyin, text)] = cap
            capped_terms.add(text)
            stats[f"{stats_prefix}_curated_productive_visibility_cap_rows"] += 1

    stats[f"{stats_prefix}_curated_productive_visibility_cap_terms"] = len(capped_terms)
    return stats


def _cap_styled_exact_competitors(
    mapping: Dict[Tuple[str, str], int],
    term_style_penalty_map: Dict[Tuple[str, str], int] | None,
    usage_score_map: Dict[str, float],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    *,
    stats_prefix: str,
) -> Dict[str, int]:
    """Apply a final homophone cap for CEDICT-styled variants/proper terms."""
    stats = {
        f"{stats_prefix}_styled_competitor_cap_rows": 0,
        f"{stats_prefix}_styled_competitor_cap_buckets": 0,
    }
    if not mapping or not term_style_penalty_map:
        return stats

    buckets: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        buckets.setdefault(pinyin, []).append((text, weight))

    def direct_signal(text: str) -> float:
        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        return usage_score * 0.45 + jieba_score * 0.45 + pageview_score * 0.10

    for pinyin, items in buckets.items():
        best_unstyled_weight = max(
            (
                weight
                for text, weight in items
                if term_style_penalty_map.get((pinyin, text), 0) <= 0
            ),
            default=0,
        )
        if best_unstyled_weight <= 0:
            continue

        touched = False
        for text, weight in items:
            style_penalty = term_style_penalty_map.get((pinyin, text), 0)
            if style_penalty <= 0:
                continue

            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            jieba_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            low_signal_geo_state = (
                style_penalty >= 100
                and _cjk_len(text) <= 3
                and text.endswith(("\u56fd", "\u570b"))
                and usage_score < 0.08
                and jieba_score < 0.08
                and pageview_score < 0.08
            )

            if low_signal_geo_state:
                cap = min(420, max(1, best_unstyled_weight - 96))
            elif style_penalty >= 140:
                cap = max(1, best_unstyled_weight - 140)
            elif style_penalty >= 80 and direct_signal(text) < 0.16:
                cap = max(1, best_unstyled_weight - 96)
            else:
                continue

            if weight <= cap:
                continue
            mapping[(pinyin, text)] = cap
            stats[f"{stats_prefix}_styled_competitor_cap_rows"] += 1
            touched = True

        if touched:
            stats[f"{stats_prefix}_styled_competitor_cap_buckets"] += 1

    return stats


def _enforce_final_normative_homophone_order(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float] | None,
    term_style_penalty_map: Dict[Tuple[str, str], int] | None,
    term_semantic_bonus_map: Dict[Tuple[str, str], int] | None,
    stats_prefix: str,
    bucket_pinyin_map: Dict[Tuple[str, str], str] | None = None,
    protected_terms: Set[str] | None = None,
) -> Dict[str, int]:
    """Final homophone ordering guard for exact candidates.

    Some source signals are visibility signals rather than rank-priority
    signals: CEDICT "variant of" forms, semantic-definition bonuses, and short
    prefixes mainly supported by longer fixed expressions. Keep these entries
    selectable, but do not let them outrank stronger mainstream same-pinyin
    exact words after later rescoring/boost stages have run.
    """
    stats = {
        f"{stats_prefix}_normative_homophone_rows_capped": 0,
        f"{stats_prefix}_normative_homophone_buckets": 0,
        f"{stats_prefix}_normative_variant_rows_capped": 0,
        f"{stats_prefix}_normative_semantic_rows_capped": 0,
        f"{stats_prefix}_normative_prefix_rows_capped": 0,
    }
    if not mapping:
        return stats

    term_style_penalty_map = term_style_penalty_map or {}
    term_semantic_bonus_map = term_semantic_bonus_map or {}
    bucket_pinyin_map = bucket_pinyin_map or {}
    protected_terms = protected_terms or set()
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    support_index = _build_longer_prefix_term_support_index(
        mapping,
        min_support_weight=360,
    )

    buckets: Dict[str, List[Tuple[str, str, int]]] = {}
    for key, weight in mapping.items():
        pinyin, text = key
        bucket_pinyin = bucket_pinyin_map.get(key, pinyin)
        if not bucket_pinyin:
            continue
        buckets.setdefault(bucket_pinyin, []).append((pinyin, text, weight))

    def parts(pinyin: str, text: str) -> Tuple[float, int, float, float, str, float, int, int, int, float]:
        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pos_tag = jieba_pos_map.get(text, "")
        char_score = _compute_text_single_char_prior(text, char_prior)
        style_penalty = term_style_penalty_map.get((pinyin, text), 0)
        semantic_bonus = term_semantic_bonus_map.get((pinyin, text), 0)
        support_count, support_total = _longer_prefix_term_support_stats(
            pinyin,
            text,
            support_index,
            min_support_weight=360,
        )
        text_len = _cjk_len(text)
        productive_support_threshold = 4 if text_len <= 2 else 8
        # Mainstream signal deliberately excludes CEDICT semantic bonuses and
        # final weight, because those can encode "visible but not frequent".
        #
        # Long-term support is a visibility signal for productive roots, not
        # direct evidence that the short root itself is the best exact
        # homophone.  Otherwise entries such as "复合" can be inflated by many
        # compounds and outrank a more common direct word like "符合".
        source_signal = min(1.0, source_hits / 5.0) * 0.08
        if (
            support_count >= productive_support_threshold
            and support_total >= support_count * 360
            and usage_score < 0.34
            and jieba_score < 0.30
            and pageview_score < 0.14
        ):
            source_signal *= 0.35
        mainstream_signal = (
            usage_score * 0.38
            + jieba_score * 0.36
            + pageview_score * 0.14
            + source_signal
            + char_score * 0.04
        )
        if _is_conversational_pos(pos_tag):
            mainstream_signal += 0.04
        elif _is_noun_pos(pos_tag) and (usage_score >= 0.08 or jieba_score >= 0.08):
            mainstream_signal += 0.02
        if style_penalty > 0:
            mainstream_signal -= min(0.22, style_penalty / 900.0)
        return (
            usage_score,
            source_hits,
            pageview_score,
            jieba_score,
            pos_tag,
            char_score,
            style_penalty,
            semantic_bonus,
            support_count,
            max(0.0, min(1.0, mainstream_signal)),
        )

    for bucket_pinyin, items in buckets.items():
        if len(items) < 2:
            continue

        enriched = []
        for pinyin, text, weight in items:
            text_len = _cjk_len(text)
            if text_len < 2 or text_len > 4:
                continue
            enriched.append((pinyin, text, weight, parts(pinyin, text)))
        if len(enriched) < 2:
            continue

        mainstream_candidates = [
            item
            for item in enriched
            if item[3][6] <= 0  # style_penalty
            and item[3][9] >= 0.075  # mainstream_signal
            and not _is_pure_daily_number_word(item[1])
        ]
        if not mainstream_candidates:
            continue

        touched = False

        min_normative_leader_weight = 240

        def best_mainstream_except(text: str) -> Tuple[str, str, int, Tuple[float, int, float, float, str, float, int, int, int, float]] | None:
            candidates = [
                item
                for item in mainstream_candidates
                if item[1] != text
                # A candidate already suppressed to visibility-only weight is
                # not a valid ranking leader for capping another exact word.
                and item[2] >= min_normative_leader_weight
            ]
            if not candidates:
                return None
            return max(candidates, key=lambda item: (item[3][9], item[2]))

        for pinyin, text, weight, item_parts in enriched:
            if text in protected_terms:
                continue
            (
                usage_score,
                source_hits,
                pageview_score,
                jieba_score,
                pos_tag,
                _char_score,
                style_penalty,
                semantic_bonus,
                support_count,
                mainstream_signal,
            ) = item_parts
            text_len = _cjk_len(text)
            if text_len < 2 or text_len > 3:
                continue

            leader = best_mainstream_except(text)
            if leader is None:
                continue
            _leader_pinyin, leader_text, leader_weight, leader_parts = leader
            leader_signal = leader_parts[9]

            cap_kind = ""
            cap_margin = 0
            if style_penalty >= 80:
                # "variant of X" and similar styled forms are useful exact
                # candidates, but the unstyled form should remain ahead.
                if leader_weight <= 0:
                    continue
                cap_kind = "variant"
                cap_margin = 96 if style_penalty < 140 else 140
            else:
                low_independent_signal = (
                    usage_score < 0.12
                    and jieba_score < 0.10
                    and pageview_score < 0.06
                    and source_hits <= 2
                )
                semantic_visibility_only = (
                    semantic_bonus >= 160
                    and low_independent_signal
                    and leader_signal >= mainstream_signal + 0.035
                )
                productive_prefix_visibility = (
                    support_count >= (4 if text_len <= 2 else 8)
                    and leader_signal >= mainstream_signal - 0.005
                    and not (
                        usage_score >= 0.36
                        and jieba_score >= 0.30
                        and pageview_score >= 0.12
                    )
                    and (
                        leader_parts[0] + leader_parts[3] + leader_parts[2]
                        >= usage_score + jieba_score + pageview_score - 0.02
                    )
                )
                direct_evidence_weaker_than_leader = (
                    support_count >= 1
                    and leader_signal >= mainstream_signal - 0.030
                    and (
                        leader_parts[0] + leader_parts[3] + leader_parts[2]
                        >= usage_score + jieba_score + pageview_score + 0.10
                    )
                    and not (
                        usage_score >= 0.34
                        or jieba_score >= 0.30
                        or pageview_score >= 0.14
                        or (
                            source_hits >= 5
                            and (usage_score >= 0.18 or jieba_score >= 0.14)
                        )
                    )
                )
                prefix_visibility_only = (
                    support_count >= 1
                    and (low_independent_signal or productive_prefix_visibility)
                    and leader_signal >= mainstream_signal + 0.04
                    and not (
                        pos_tag.startswith("v")
                        and source_hits >= 2
                        and jieba_score >= 0.08
                        and support_count >= 12
                    )
                )
                if semantic_visibility_only:
                    cap_kind = "semantic"
                    cap_margin = 120
                elif productive_prefix_visibility:
                    cap_kind = "prefix"
                    cap_margin = 80
                elif direct_evidence_weaker_than_leader:
                    cap_kind = "prefix"
                    cap_margin = 96
                elif prefix_visibility_only:
                    cap_kind = "prefix"
                    cap_margin = 112
                else:
                    continue

            cap = max(1, leader_weight - cap_margin)
            if weight <= cap:
                continue

            mapping[(pinyin, text)] = cap
            stats[f"{stats_prefix}_normative_homophone_rows_capped"] += 1
            if cap_kind == "variant":
                stats[f"{stats_prefix}_normative_variant_rows_capped"] += 1
            elif cap_kind == "semantic":
                stats[f"{stats_prefix}_normative_semantic_rows_capped"] += 1
            elif cap_kind == "prefix":
                stats[f"{stats_prefix}_normative_prefix_rows_capped"] += 1
            touched = True

        if touched:
            stats[f"{stats_prefix}_normative_homophone_buckets"] += 1

    return stats


def _cap_curated_daily_supplement_exact_weights(
    mapping: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    opencc_entries: List[Tuple[str, str]],
    simp_to_trad_char_map: Dict[str, str],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
    *,
    use_traditional: bool,
    stats_prefix: str,
    min_hanzi: int,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_curated_daily_supplement_exact_cap_terms": 0,
        f"{stats_prefix}_curated_daily_supplement_exact_cap_rows": 0,
    }
    if not mapping or not curated_entries:
        return stats

    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    existing_texts = {text for _pinyin, text in mapping.keys()}
    capped_terms: Set[str] = set()

    for sc_word, tc_word, usage_score, explicit_pinyin in curated_entries:
        if _cjk_len(sc_word) < min_hanzi:
            continue

        pinyin = explicit_pinyin or _pinyin_from_unihan(
            sc_word,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not pinyin:
            continue

        text = sc_word
        if use_traditional:
            text = tc_word
            if not text:
                tc_words = opencc_sc_to_tc.get(sc_word, set())
                if tc_words:
                    text = _choose_tc_phrase_candidate(
                        sc_word,
                        tc_words,
                        simp_to_trad_char_map,
                    )
                elif sc_word in existing_texts:
                    text = sc_word
                else:
                    text = _convert_sc_text_to_tc_with_phrase_hints(
                        sc_word,
                        opencc_sc_to_tc,
                        simp_to_trad_char_map,
                    )

        if _cjk_len(text) < min_hanzi:
            continue

        key = (pinyin, text)
        weight = mapping.get(key)
        cap = _curated_daily_supplement_weight_cap(usage_score, text)
        if weight is None or weight <= cap:
            continue

        mapping[key] = cap
        capped_terms.add(text)
        stats[f"{stats_prefix}_curated_daily_supplement_exact_cap_rows"] += 1

    stats[f"{stats_prefix}_curated_daily_supplement_exact_cap_terms"] = len(capped_terms)
    return stats


def _cap_low_signal_competitors_against_curated_supplement_terms(
    mapping: Dict[Tuple[str, str], int],
    supplement_terms: Set[str],
    protected_terms: Set[str],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float] | None,
    wiki_titles: Set[str],
    wiki_augmented_terms: Set[str] | None,
    stats_prefix: str,
    bucket_pinyin_map: Dict[Tuple[str, str], str] | None = None,
) -> Dict[str, int]:
    """Keep obscure same-pinyin competitors below curated low-frequency supplements.

    Curated daily supplements intentionally have a low cap so they remain
    selectable without crowding common words.  A derived/rare entry in the same
    pinyin bucket should not keep an inherited high weight above that explicit
    supplement when it has no direct usage evidence.  Entries below the
    low-frequency scoring threshold are visibility-only and must not become
    anchors that suppress established exact words.
    """
    stats = {
        f"{stats_prefix}_supplement_low_signal_competitor_buckets": 0,
        f"{stats_prefix}_supplement_low_signal_competitors_capped": 0,
    }
    if not mapping or not supplement_terms:
        return stats

    protected_terms = protected_terms or set()
    wiki_augmented_terms = wiki_augmented_terms or set()
    bucket_pinyin_map = bucket_pinyin_map or {}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    buckets: Dict[str, List[Tuple[str, str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        bucket_pinyin = bucket_pinyin_map.get((pinyin, text), pinyin)
        if not bucket_pinyin:
            continue
        buckets.setdefault(bucket_pinyin, []).append((pinyin, text, weight))
        if "'" in bucket_pinyin:
            compact_bucket = bucket_pinyin.replace("'", "")
            if (
                compact_bucket
                and compact_bucket != bucket_pinyin
                and PINYIN_RE.fullmatch(compact_bucket)
            ):
                buckets.setdefault(compact_bucket, []).append((pinyin, text, weight))

    capped_keys: Set[Tuple[str, str]] = set()
    for _bucket_pinyin, items in buckets.items():
        supplement_weights = [
            weight
            for _pinyin, text, weight in items
            if (
                text in supplement_terms
                and 2 <= _cjk_len(text) <= 4
                and usage_score_map.get(text, 0.0) >= 0.10
            )
        ]
        if not supplement_weights:
            continue

        supplement_weight = min(
            CURATED_DAILY_SUPPLEMENT_WEIGHT_CAP,
            max(supplement_weights),
        )
        if supplement_weight <= 0:
            continue
        cap = max(1, supplement_weight - 24)
        bucket_touched = False

        for pinyin, text, weight in items:
            text_len = _cjk_len(text)
            if (
                text in protected_terms
                or text_len < 2
                or text_len > 3
                or _is_pure_daily_number_word(text)
                or weight <= cap
            ):
                continue

            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            source_hits = max(0, source_hits_map.get(text, 0))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            jieba_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            pos_tag = jieba_pos_map.get(text, "")
            char_score = _compute_text_single_char_prior(text, char_prior)
            min_char_prior = _compute_min_char_prior(text, char_prior)
            wiki_support = _has_effective_wiki_support(
                text,
                wiki_titles,
                pageview_score=pageview_score,
                source_hits=source_hits,
                wiki_augmented_terms=wiki_augmented_terms,
            )
            rare_title_visibility_only = (
                usage_score < 0.45
                and jieba_score < 0.04
                and source_hits <= 4
                and min_char_prior < 0.08
                and char_score < 0.45
            )
            has_independent_signal = (
                not rare_title_visibility_only
                and (
                    usage_score >= 0.18
                    or jieba_score >= 0.12
                    or pageview_score >= 0.08
                    or source_hits >= 2
                    or (wiki_support and (pageview_score >= 0.04 or source_hits >= 1))
                )
            )
            if has_independent_signal:
                continue
            if _is_named_entity_pos(pos_tag) and (wiki_support or pageview_score >= 0.03):
                continue
            if min_char_prior >= 0.10 or char_score >= 0.42:
                continue

            key = (pinyin, text)
            mapping[key] = cap
            if key not in capped_keys:
                stats[f"{stats_prefix}_supplement_low_signal_competitors_capped"] += 1
                capped_keys.add(key)
            bucket_touched = True

        if bucket_touched:
            stats[f"{stats_prefix}_supplement_low_signal_competitor_buckets"] += 1

    return stats


def _restore_strong_curated_daily_exact_weights(
    mapping: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    opencc_entries: List[Tuple[str, str]],
    simp_to_trad_char_map: Dict[str, str],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
    *,
    use_traditional: bool,
    stats_prefix: str,
    min_hanzi: int,
) -> Dict[str, int]:
    """Keep explicitly high-confidence daily entries from being over-capped.

    Later homophone and low-signal passes may lower exact entries to keep
    visibility-only supplements from crowding common words.  Entries manually
    marked as strong daily words (usage >= 0.90) are different: they are human
    frequency anchors and should not end below same-pinyin variants.
    """
    stats = {
        f"{stats_prefix}_strong_curated_daily_exact_restored": 0,
        f"{stats_prefix}_strong_curated_daily_exact_added": 0,
    }
    if not mapping or not curated_entries:
        return stats

    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    existing_texts = {text for _pinyin, text in mapping.keys()}

    for sc_word, tc_word, usage_score, explicit_pinyin in curated_entries:
        if usage_score < 0.90 or _cjk_len(sc_word) < min_hanzi:
            continue
        source_text = tc_word if use_traditional and tc_word else sc_word
        if _is_curated_productive_state_visibility_term(source_text, usage_score):
            continue

        pinyin = explicit_pinyin or _pinyin_from_unihan(
            sc_word,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not pinyin:
            continue

        text = sc_word
        if use_traditional:
            text = tc_word
            if not text:
                tc_words = opencc_sc_to_tc.get(sc_word, set())
                if tc_words:
                    text = _choose_tc_phrase_candidate(
                        sc_word,
                        tc_words,
                        simp_to_trad_char_map,
                    )
                elif sc_word in existing_texts:
                    text = sc_word
                else:
                    text = _convert_sc_text_to_tc_with_phrase_hints(
                        sc_word,
                        opencc_sc_to_tc,
                        simp_to_trad_char_map,
                    )

        if _cjk_len(text) < min_hanzi:
            continue
        if _is_pure_daily_number_word(text) or _is_daily_count_measure_phrase(text):
            continue

        key = (pinyin, text)
        target = _finalize_curated_daily_weight(
            1,
            usage_score=usage_score,
            is_number_word=False,
            low_frequency=False,
            text=text,
        )
        current = mapping.get(key)
        if current is None:
            continue
        if current < target:
            mapping[key] = target
            stats[f"{stats_prefix}_strong_curated_daily_exact_restored"] += 1

    return stats


def _reinforce_curated_daily_existing_prefixes(
    mapping: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
    *,
    use_traditional: bool,
    stats_prefix: str,
    min_hanzi: int,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_curated_daily_prefix_terms_considered": 0,
        f"{stats_prefix}_curated_daily_prefix_reinforced": 0,
    }
    if not mapping or not curated_entries:
        return stats

    existing_texts = {text for _pinyin, text in mapping.keys()}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)

    def prefix_floor(prefix_len: int, inherited_usage: float) -> int:
        usage = min(1.0, max(0.0, inherited_usage))
        if prefix_len <= 2:
            return min(980, 760 + int(round(usage * 220.0)))
        if prefix_len == 3:
            return min(960, 720 + int(round(usage * 210.0)))
        return min(960, 720 + int(round(usage * 190.0)))

    for sc_word, tc_word, usage_score, explicit_pinyin in curated_entries:
        source_text = tc_word if use_traditional and tc_word else sc_word
        source_len = _cjk_len(source_text)
        if source_len < 3:
            continue

        pinyin = explicit_pinyin or _pinyin_from_unihan(
            sc_word,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not pinyin:
            continue

        syllables = _split_compact_pinyin_by_unihan(
            sc_word,
            pinyin,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not syllables or len(syllables) < source_len:
            continue

        for prefix_len in range(max(2, min_hanzi), min(4, source_len - 1) + 1):
            prefix = source_text[:prefix_len]
            if prefix not in existing_texts:
                continue
            if not CJK_FULL_RE.fullmatch(prefix):
                continue
            if _is_named_entity_pos(jieba_pos_map.get(prefix, "")):
                continue

            # A high-confidence 3-character daily phrase often carries a
            # productive 2-character everyday prefix (e.g. 新房子 -> 新房).
            # The prefix must already exist in the dictionary; this only
            # restores a reasonable weight instead of synthesizing new words.
            near_complete_daily_prefix = (
                prefix_len == 2
                and source_len == 3
                and min(1.0, max(0.0, usage_score)) >= 0.82
            )
            curated_prefix_support = (
                min(1.0, max(0.0, usage_score)) >= 0.88
                or near_complete_daily_prefix
            )
            prefix_char_score = _compute_text_single_char_prior(prefix, char_prior)
            prefix_min_char_prior = _compute_min_char_prior(prefix, char_prior)
            if (
                not curated_prefix_support
                and (prefix_char_score < 0.08 or prefix_min_char_prior < 0.01)
            ):
                continue

            prefix_pinyin = _normalize_compact_pinyin_key("".join(syllables[:prefix_len]))
            if not prefix_pinyin:
                continue

            key = (prefix_pinyin, prefix)
            existing_weight = mapping.get(key)
            if existing_weight is None:
                continue

            stats[f"{stats_prefix}_curated_daily_prefix_terms_considered"] += 1
            direct_usage = min(1.0, max(0.0, usage_score_map.get(prefix, 0.0)))
            direct_hits = source_hits_map.get(prefix, 0)
            if direct_usage < 0.18 and direct_hits < 2 and not curated_prefix_support:
                continue
            inherited_usage = max(
                direct_usage,
                min(0.70, max(0.18, min(1.0, max(0.0, usage_score)) - 0.16)),
            )
            floor_weight = prefix_floor(prefix_len, inherited_usage)
            if existing_weight < floor_weight:
                mapping[key] = floor_weight
                stats[f"{stats_prefix}_curated_daily_prefix_reinforced"] += 1
            # Later homophone capping passes use usage/source maps, not just the
            # current weight. Preserve the evidence that an existing short word
            # is a productive prefix of a high-confidence daily phrase.
            if curated_prefix_support:
                usage_score_map[prefix] = max(direct_usage, min(0.42, inherited_usage))
                source_hits_map[prefix] = max(direct_hits, 2)

    return stats


def _reinforce_curated_daily_existing_suffixes(
    mapping: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
    *,
    use_traditional: bool,
    stats_prefix: str,
    min_hanzi: int,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_curated_daily_suffix_terms_considered": 0,
        f"{stats_prefix}_curated_daily_suffix_reinforced": 0,
    }
    if not mapping or not curated_entries:
        return stats

    existing_texts = {text for _pinyin, text in mapping.keys()}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)

    def suffix_floor(suffix_len: int, inherited_usage: float) -> int:
        usage = min(1.0, max(0.0, inherited_usage))
        if suffix_len <= 2:
            return min(920, 700 + int(round(usage * 210.0)))
        if suffix_len == 3:
            return min(930, 700 + int(round(usage * 190.0)))
        return min(940, 710 + int(round(usage * 170.0)))

    for sc_word, tc_word, usage_score, explicit_pinyin in curated_entries:
        source_text = tc_word if use_traditional and tc_word else sc_word
        source_len = _cjk_len(source_text)
        if source_len < 3:
            continue

        pinyin = explicit_pinyin or _pinyin_from_unihan(
            sc_word,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not pinyin:
            continue

        syllables = _split_compact_pinyin_by_unihan(
            sc_word,
            pinyin,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not syllables or len(syllables) < source_len:
            continue

        for suffix_len in range(max(2, min_hanzi), min(4, source_len - 1) + 1):
            suffix = source_text[-suffix_len:]
            if suffix not in existing_texts:
                continue
            if not CJK_FULL_RE.fullmatch(suffix):
                continue
            if _is_named_entity_pos(jieba_pos_map.get(suffix, "")):
                continue

            curated_suffix_support = min(1.0, max(0.0, usage_score)) >= 0.88
            suffix_char_score = _compute_text_single_char_prior(suffix, char_prior)
            suffix_min_char_prior = _compute_min_char_prior(suffix, char_prior)
            if (
                not curated_suffix_support
                and (suffix_char_score < 0.12 or suffix_min_char_prior < 0.02)
            ):
                continue

            suffix_pinyin = _normalize_compact_pinyin_key("".join(syllables[-suffix_len:]))
            if not suffix_pinyin:
                continue

            key = (suffix_pinyin, suffix)
            existing_weight = mapping.get(key)
            if existing_weight is None:
                continue

            stats[f"{stats_prefix}_curated_daily_suffix_terms_considered"] += 1
            direct_usage = min(1.0, max(0.0, usage_score_map.get(suffix, 0.0)))
            direct_hits = source_hits_map.get(suffix, 0)
            if direct_usage < 0.18 and direct_hits < 2 and not curated_suffix_support:
                continue
            inherited_usage = max(
                direct_usage,
                min(0.64, max(0.16, min(1.0, max(0.0, usage_score)) - 0.18)),
            )
            floor_weight = suffix_floor(suffix_len, inherited_usage)
            if existing_weight < floor_weight:
                mapping[key] = floor_weight
                stats[f"{stats_prefix}_curated_daily_suffix_reinforced"] += 1
            if curated_suffix_support:
                usage_score_map[suffix] = max(direct_usage, min(0.38, inherited_usage))
                source_hits_map[suffix] = max(direct_hits, 2)

    return stats


def _cap_curated_daily_de_complement_pair_weights(
    mapping: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    *,
    use_traditional: bool,
    stats_prefix: str,
) -> Dict[str, int]:
    """Prefer standalone V+的 over matching standalone V+得 pairs.

    Two-character V+得 forms are valid exact candidates, but they normally need
    a following complement such as "做得好". When the same curated V+的 phrase
    exists in the same pinyin bucket, keep V+得 visible without making it the
    default standalone exact match.
    """
    stats = {
        f"{stats_prefix}_curated_daily_de_pair_cap_terms": 0,
        f"{stats_prefix}_curated_daily_de_pair_cap_rows": 0,
    }
    if not mapping or not curated_entries:
        return stats

    curated_terms: Set[str] = set()
    for sc_word, tc_word, _usage_score, _explicit_pinyin in curated_entries:
        text = tc_word if use_traditional and tc_word else sc_word
        if text:
            curated_terms.add(text)

    capped_terms: Set[str] = set()
    for key, weight in list(mapping.items()):
        pinyin, text = key
        if (
            _cjk_len(text) != 2
            or len(text) != 2
            or not text.endswith("\u5f97")
            or text not in curated_terms
        ):
            continue

        de_text = text[:-1] + "\u7684"
        if de_text not in curated_terms:
            continue

        de_weight = mapping.get((pinyin, de_text))
        if de_weight is None or de_weight <= 1:
            continue

        cap = max(1, de_weight - 24)
        if weight <= cap:
            continue

        mapping[key] = cap
        capped_terms.add(text)
        stats[f"{stats_prefix}_curated_daily_de_pair_cap_rows"] += 1

    stats[f"{stats_prefix}_curated_daily_de_pair_cap_terms"] = len(capped_terms)
    return stats


def _cap_curated_daily_visibility_exact_weights(
    mapping: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    opencc_entries: List[Tuple[str, str]],
    simp_to_trad_char_map: Dict[str, str],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
    *,
    use_traditional: bool,
    stats_prefix: str,
    min_hanzi: int,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_curated_daily_visibility_cap_terms": 0,
        f"{stats_prefix}_curated_daily_visibility_cap_rows": 0,
    }
    if not mapping or not curated_entries:
        return stats

    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    existing_texts = {text for _pinyin, text in mapping.keys()}
    capped_terms: Set[str] = set()

    for sc_word, tc_word, usage_score, explicit_pinyin in curated_entries:
        if usage_score >= 0.90 or _cjk_len(sc_word) < min_hanzi:
            continue

        pinyin = explicit_pinyin or _pinyin_from_unihan(
            sc_word,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not pinyin:
            continue

        text = sc_word
        if use_traditional:
            text = tc_word
            if not text:
                tc_words = opencc_sc_to_tc.get(sc_word, set())
                if tc_words:
                    text = _choose_tc_phrase_candidate(
                        sc_word,
                        tc_words,
                        simp_to_trad_char_map,
                    )
                elif sc_word in existing_texts:
                    text = sc_word
                else:
                    text = _convert_sc_text_to_tc_with_phrase_hints(
                        sc_word,
                        opencc_sc_to_tc,
                        simp_to_trad_char_map,
                    )

        text_len = _cjk_len(text)
        if text_len < min_hanzi:
            continue
        if _is_pure_daily_number_word(text) or _is_daily_count_measure_phrase(text):
            continue

        key = (pinyin, text)
        weight = mapping.get(key)
        cap = (
            CURATED_DAILY_VISIBILITY_WEIGHT_CAP_SHORT
            if text_len <= 2
            else CURATED_DAILY_VISIBILITY_WEIGHT_CAP_LONG
        )
        if weight is None or weight <= cap:
            continue

        mapping[key] = cap
        capped_terms.add(text)
        stats[f"{stats_prefix}_curated_daily_visibility_cap_rows"] += 1

    stats[f"{stats_prefix}_curated_daily_visibility_cap_terms"] = len(capped_terms)
    return stats


def _cap_curated_daily_prefix_competitors(
    mapping: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    usage_score_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
    *,
    use_traditional: bool,
    stats_prefix: str,
    min_hanzi: int,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_curated_daily_prefix_competitors_capped": 0,
        f"{stats_prefix}_curated_daily_prefix_competitor_rows": 0,
    }
    if not mapping or not curated_entries:
        return stats

    by_pinyin: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        by_pinyin.setdefault(pinyin, []).append((text, weight))

    protected_exact_keys: Set[Tuple[str, str]] = set()
    protected_exact_texts: Set[str] = set()
    for sc_word, tc_word, _usage_score, explicit_pinyin in curated_entries:
        protected_text = tc_word if use_traditional and tc_word else sc_word
        if _cjk_len(protected_text) < min_hanzi:
            continue
        protected_texts = [protected_text]
        if not use_traditional and tc_word and tc_word == sc_word:
            protected_texts.append(sc_word)
        protected_pinyin = explicit_pinyin or _pinyin_from_unihan(
            sc_word,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        for item_text in protected_texts:
            protected_exact_texts.add(item_text)
            if protected_pinyin:
                protected_exact_keys.add((protected_pinyin, item_text))

    existing_texts = {text for _pinyin, text in mapping.keys()}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)

    def prefix_floor(prefix_len: int, inherited_usage: float) -> int:
        usage = min(1.0, max(0.0, inherited_usage))
        if prefix_len <= 2:
            return min(900, 650 + int(round(usage * 240.0)))
        if prefix_len == 3:
            return min(920, 660 + int(round(usage * 220.0)))
        return min(940, 680 + int(round(usage * 200.0)))

    for sc_word, tc_word, usage_score, explicit_pinyin in curated_entries:
        source_text = tc_word if use_traditional and tc_word else sc_word
        source_len = _cjk_len(source_text)
        if source_len < 3:
            continue

        pinyin = explicit_pinyin or _pinyin_from_unihan(
            sc_word,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not pinyin:
            continue

        syllables = _split_compact_pinyin_by_unihan(
            sc_word,
            pinyin,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not syllables or len(syllables) < source_len:
            continue

        for prefix_len in range(max(2, min_hanzi), min(4, source_len - 1) + 1):
            prefix = source_text[:prefix_len]
            if prefix not in existing_texts:
                continue
            if not CJK_FULL_RE.fullmatch(prefix):
                continue
            if _is_named_entity_pos(jieba_pos_map.get(prefix, "")):
                continue

            prefix_char_score = _compute_text_single_char_prior(prefix, char_prior)
            prefix_min_char_prior = _compute_min_char_prior(prefix, char_prior)
            if prefix_char_score < 0.08 or prefix_min_char_prior < 0.01:
                continue

            prefix_pinyin = _normalize_compact_pinyin_key("".join(syllables[:prefix_len]))
            if not prefix_pinyin:
                continue

            key = (prefix_pinyin, prefix)
            prefix_weight = mapping.get(key)
            if prefix_weight is None:
                continue

            direct_usage = min(1.0, max(0.0, usage_score_map.get(prefix, 0.0)))
            if direct_usage < 0.08:
                continue
            inherited_usage = max(
                direct_usage,
                min(0.62, max(0.18, min(1.0, max(0.0, usage_score)) - 0.18)),
            )
            if prefix_weight < prefix_floor(prefix_len, inherited_usage) - 8:
                continue

            competitor_cap = max(1, min(prefix_weight - 420, 760))
            if competitor_cap <= 0:
                continue

            for competitor_text, competitor_weight in by_pinyin.get(prefix_pinyin, []):
                if competitor_text == prefix:
                    continue
                if (prefix_pinyin, competitor_text) in protected_exact_keys:
                    continue
                if competitor_text in protected_exact_texts:
                    continue
                if competitor_weight <= competitor_cap:
                    continue
                if not CJK_FULL_RE.fullmatch(competitor_text):
                    continue
                if _is_named_entity_pos(jieba_pos_map.get(competitor_text, "")):
                    continue
                mapping[(prefix_pinyin, competitor_text)] = competitor_cap
                stats[f"{stats_prefix}_curated_daily_prefix_competitors_capped"] += 1

            stats[f"{stats_prefix}_curated_daily_prefix_competitor_rows"] += 1

    return stats


def _augment_with_curated_daily_phrases(
    sc: Dict[Tuple[str, str], int],
    tc: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    tc_usage_score_map: Dict[str, float],
    tc_source_hits_map: Dict[str, int],
    jieba_direct_signal_map: Dict[str, float],
    tc_jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    tc_jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    tc_char_frequency_prior: Dict[str, float],
    opencc_entries: List[Tuple[str, str]],
    simp_to_trad_char_map: Dict[str, str],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
    min_hanzi: int,
    *,
    stats_prefix: str = "curated_daily",
    low_frequency: bool = False,
) -> Tuple[Dict[str, int], Set[str], Set[str]]:
    def stat(name: str) -> str:
        return f"{stats_prefix}_{name}"

    stats = {
        stat("terms_total"): 0,
        stat("terms_added_sc"): 0,
        stat("terms_boosted_sc"): 0,
        stat("terms_capped_sc"): 0,
        stat("terms_added_tc"): 0,
        stat("terms_boosted_tc"): 0,
        stat("terms_capped_tc"): 0,
        stat("number_terms_boosted_sc"): 0,
        stat("number_terms_boosted_tc"): 0,
        stat("terms_skipped_short"): 0,
        stat("terms_skipped_no_pinyin"): 0,
    }
    sc_terms: Set[str] = set()
    tc_terms: Set[str] = set()
    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    tc_existing_texts = {text for _pinyin, text in tc.keys()}
    sc_char_prior = _build_effective_char_prior(sc, char_frequency_prior)
    tc_char_prior = _build_effective_char_prior(tc, tc_char_frequency_prior)

    for sc_word, tc_word, usage_score, explicit_pinyin in curated_entries:
        stats[stat("terms_total")] += 1
        if _cjk_len(sc_word) < min_hanzi:
            stats[stat("terms_skipped_short")] += 1
            continue

        pinyin = explicit_pinyin or _pinyin_from_unihan(
            sc_word,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not pinyin:
            stats[stat("terms_skipped_no_pinyin")] += 1
            continue

        signal_usage_score = usage_score
        if not low_frequency and usage_score < 0.90:
            # Scores below the strong daily threshold are exact-visibility
            # supplements, not real corpus-frequency evidence. Feeding their
            # full curated score back into the homophone/common-word model
            # makes valid-but-less-common words crowd out broader daily words.
            signal_usage_score = min(usage_score, 0.10)
        source_hits = 2 if low_frequency else 4 if usage_score >= 0.90 else 1
        usage_score_map[sc_word] = max(usage_score_map.get(sc_word, 0.0), signal_usage_score)
        source_hits_map[sc_word] = max(source_hits_map.get(sc_word, 0), source_hits)

        sc_jieba_direct = max(
            jieba_direct_signal_map.get(sc_word, 0.0),
            min(0.26, signal_usage_score * 0.32),
        )
        sc_pos_tag = jieba_pos_map.get(sc_word, "")
        sc_char_score = _compute_text_single_char_prior(sc_word, sc_char_prior)
        sc_daily_number_support = _is_daily_number_word_candidate(
            sc_word,
            text_len=_cjk_len(sc_word),
            usage_score=usage_score,
            source_hits=source_hits,
            pos_tag=sc_pos_tag,
        )
        sc_weight = _compute_weight_with_signals(
            sc_word,
            usage_score=signal_usage_score,
            source_hits=source_hits,
            pageview_score=0.0,
            wiki_hit=usage_score >= 0.90,
            core_entry=False,
            jieba_direct_score=sc_jieba_direct,
            pos_tag=sc_pos_tag,
            char_score=sc_char_score,
        )
        if sc_daily_number_support:
            sc_weight = min(1000, sc_weight + (40 if _cjk_len(sc_word) <= 2 else 26))
            stats[stat("number_terms_boosted_sc")] += 1
        sc_weight = _finalize_curated_daily_weight(
            sc_weight,
            usage_score=usage_score,
            is_number_word=sc_daily_number_support,
            low_frequency=low_frequency,
            text=sc_word,
        )
        sc_key = (pinyin, sc_word)
        existing_sc_weight = sc.get(sc_key)
        if existing_sc_weight is None:
            sc[sc_key] = sc_weight
            stats[stat("terms_added_sc")] += 1
            sc_terms.add(sc_word)
        elif low_frequency and existing_sc_weight > sc_weight:
            sc[sc_key] = sc_weight
            stats[stat("terms_capped_sc")] += 1
            sc_terms.add(sc_word)
        elif sc_weight > existing_sc_weight:
            sc[sc_key] = sc_weight
            stats[stat("terms_boosted_sc")] += 1
            sc_terms.add(sc_word)
        else:
            sc_terms.add(sc_word)

        tc_candidate = tc_word
        if not tc_candidate:
            tc_words = opencc_sc_to_tc.get(sc_word, set())
            if tc_words:
                tc_candidate = _choose_tc_phrase_candidate(
                    sc_word,
                    tc_words,
                    simp_to_trad_char_map,
                )
            elif sc_word in tc_existing_texts:
                tc_candidate = sc_word
            else:
                tc_candidate = _convert_sc_text_to_tc_with_phrase_hints(
                    sc_word,
                    opencc_sc_to_tc,
                    simp_to_trad_char_map,
                )
        if _cjk_len(tc_candidate) < min_hanzi:
            continue

        tc_usage_score_map[tc_candidate] = max(tc_usage_score_map.get(tc_candidate, 0.0), signal_usage_score)
        tc_source_hits_map[tc_candidate] = max(tc_source_hits_map.get(tc_candidate, 0), source_hits)

        tc_jieba_direct = max(
            tc_jieba_direct_signal_map.get(tc_candidate, 0.0),
            min(0.26, signal_usage_score * 0.32),
        )
        tc_pos_tag = tc_jieba_pos_map.get(tc_candidate, sc_pos_tag)
        tc_char_score = _compute_text_single_char_prior(tc_candidate, tc_char_prior)
        tc_daily_number_support = _is_daily_number_word_candidate(
            tc_candidate,
            text_len=_cjk_len(tc_candidate),
            usage_score=usage_score,
            source_hits=source_hits,
            pos_tag=tc_pos_tag,
        )
        tc_weight = _compute_weight_with_signals(
            tc_candidate,
            usage_score=signal_usage_score,
            source_hits=source_hits,
            pageview_score=0.0,
            wiki_hit=usage_score >= 0.90,
            core_entry=False,
            jieba_direct_score=tc_jieba_direct,
            pos_tag=tc_pos_tag,
            char_score=tc_char_score,
        )
        if tc_daily_number_support:
            tc_weight = min(1000, tc_weight + (40 if _cjk_len(tc_candidate) <= 2 else 26))
            stats[stat("number_terms_boosted_tc")] += 1
        tc_weight = _finalize_curated_daily_weight(
            tc_weight,
            usage_score=usage_score,
            is_number_word=tc_daily_number_support,
            low_frequency=low_frequency,
            text=tc_candidate,
        )
        tc_key = (pinyin, tc_candidate)
        existing_tc_weight = tc.get(tc_key)
        if existing_tc_weight is None:
            tc[tc_key] = tc_weight
            stats[stat("terms_added_tc")] += 1
            tc_terms.add(tc_candidate)
        elif low_frequency and existing_tc_weight > tc_weight:
            tc[tc_key] = tc_weight
            stats[stat("terms_capped_tc")] += 1
            tc_terms.add(tc_candidate)
        elif tc_weight > existing_tc_weight:
            tc[tc_key] = tc_weight
            stats[stat("terms_boosted_tc")] += 1
            tc_terms.add(tc_candidate)
        else:
            tc_terms.add(tc_candidate)

    return stats, sc_terms, tc_terms


def _reinforce_curated_daily_tc_phrases(
    tc: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    tc_usage_score_map: Dict[str, float],
    tc_source_hits_map: Dict[str, int],
    tc_jieba_direct_signal_map: Dict[str, float],
    tc_jieba_pos_map: Dict[str, str],
    tc_char_frequency_prior: Dict[str, float],
    opencc_entries: List[Tuple[str, str]],
    simp_to_trad_char_map: Dict[str, str],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
    min_hanzi: int,
    *,
    stats_prefix: str = "curated_daily_exact_tc",
    low_frequency: bool = False,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_reinforced": 0,
        f"{stats_prefix}_added": 0,
    }
    if not tc or not curated_entries:
        return stats

    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    tc_existing_texts = {text for _pinyin, text in tc.keys()}
    tc_char_prior = _build_effective_char_prior(tc, tc_char_frequency_prior)

    for sc_word, tc_word, usage_score, explicit_pinyin in curated_entries:
        if _cjk_len(sc_word) < min_hanzi:
            continue

        pinyin = explicit_pinyin or _pinyin_from_unihan(
            sc_word,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not pinyin:
            continue

        tc_candidate = tc_word
        if not tc_candidate:
            tc_words = opencc_sc_to_tc.get(sc_word, set())
            if tc_words:
                tc_candidate = _choose_tc_phrase_candidate(
                    sc_word,
                    tc_words,
                    simp_to_trad_char_map,
                )
            elif sc_word in tc_existing_texts:
                tc_candidate = sc_word
            else:
                tc_candidate = _convert_sc_text_to_tc_with_phrase_hints(
                    sc_word,
                    opencc_sc_to_tc,
                    simp_to_trad_char_map,
                )
        if _cjk_len(tc_candidate) < min_hanzi:
            continue

        entry_usage_score = usage_score
        signal_usage_score = entry_usage_score
        if not low_frequency and entry_usage_score < 0.90:
            signal_usage_score = min(entry_usage_score, 0.10)
        source_hits = max(
            2 if low_frequency else 4 if entry_usage_score >= 0.90 else 1,
            tc_source_hits_map.get(tc_candidate, 0),
        )
        signal_usage_score = max(signal_usage_score, tc_usage_score_map.get(tc_candidate, 0.0))
        tc_jieba_direct = max(
            tc_jieba_direct_signal_map.get(tc_candidate, 0.0),
            min(0.26, signal_usage_score * 0.32),
        )
        tc_pos_tag = tc_jieba_pos_map.get(tc_candidate, "")
        tc_char_score = _compute_text_single_char_prior(tc_candidate, tc_char_prior)
        tc_daily_number_support = _is_daily_number_word_candidate(
            tc_candidate,
            text_len=_cjk_len(tc_candidate),
            usage_score=entry_usage_score,
            source_hits=source_hits,
            pos_tag=tc_pos_tag,
        )
        tc_weight = _compute_weight_with_signals(
            tc_candidate,
            usage_score=signal_usage_score,
            source_hits=source_hits,
            pageview_score=0.0,
            wiki_hit=entry_usage_score >= 0.90,
            core_entry=False,
            jieba_direct_score=tc_jieba_direct,
            pos_tag=tc_pos_tag,
            char_score=tc_char_score,
        )
        if tc_daily_number_support:
            tc_weight = min(1000, tc_weight + (40 if _cjk_len(tc_candidate) <= 2 else 26))
        tc_weight = _finalize_curated_daily_weight(
            tc_weight,
            usage_score=entry_usage_score,
            is_number_word=tc_daily_number_support,
            low_frequency=low_frequency,
            text=tc_candidate,
        )

        tc_key = (pinyin, tc_candidate)
        existing_tc_weight = tc.get(tc_key)
        if existing_tc_weight is None:
            tc[tc_key] = tc_weight
            stats[f"{stats_prefix}_added"] += 1
        elif tc_weight > existing_tc_weight:
            tc[tc_key] = tc_weight
            stats[f"{stats_prefix}_reinforced"] += 1

    return stats


def _reinforce_curated_daily_sc_phrases(
    sc: Dict[Tuple[str, str], int],
    curated_entries: List[Tuple[str, str, float, str]],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
    min_hanzi: int,
    *,
    stats_prefix: str = "curated_daily_exact_sc",
    low_frequency: bool = False,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_reinforced": 0,
        f"{stats_prefix}_added": 0,
    }
    if not sc or not curated_entries:
        return stats

    sc_char_prior = _build_effective_char_prior(sc, char_frequency_prior)

    for sc_word, _tc_word, usage_score, explicit_pinyin in curated_entries:
        if _cjk_len(sc_word) < min_hanzi:
            continue

        pinyin = explicit_pinyin or _pinyin_from_unihan(
            sc_word,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not pinyin:
            continue

        entry_usage_score = usage_score
        signal_usage_score = entry_usage_score
        if not low_frequency and entry_usage_score < 0.90:
            signal_usage_score = min(entry_usage_score, 0.10)
        source_hits = max(
            2 if low_frequency else 4 if entry_usage_score >= 0.90 else 1,
            source_hits_map.get(sc_word, 0),
        )
        signal_usage_score = max(signal_usage_score, usage_score_map.get(sc_word, 0.0))
        sc_jieba_direct = max(
            jieba_direct_signal_map.get(sc_word, 0.0),
            min(0.26, signal_usage_score * 0.32),
        )
        sc_pos_tag = jieba_pos_map.get(sc_word, "")
        sc_char_score = _compute_text_single_char_prior(sc_word, sc_char_prior)
        sc_daily_number_support = _is_daily_number_word_candidate(
            sc_word,
            text_len=_cjk_len(sc_word),
            usage_score=entry_usage_score,
            source_hits=source_hits,
            pos_tag=sc_pos_tag,
        )
        sc_weight = _compute_weight_with_signals(
            sc_word,
            usage_score=signal_usage_score,
            source_hits=source_hits,
            pageview_score=0.0,
            wiki_hit=entry_usage_score >= 0.90,
            core_entry=False,
            jieba_direct_score=sc_jieba_direct,
            pos_tag=sc_pos_tag,
            char_score=sc_char_score,
        )
        if sc_daily_number_support:
            sc_weight = min(1000, sc_weight + (40 if _cjk_len(sc_word) <= 2 else 26))
        sc_weight = _finalize_curated_daily_weight(
            sc_weight,
            usage_score=entry_usage_score,
            is_number_word=sc_daily_number_support,
            low_frequency=low_frequency,
            text=sc_word,
        )

        sc_key = (pinyin, sc_word)
        existing_sc_weight = sc.get(sc_key)
        if existing_sc_weight is None:
            sc[sc_key] = sc_weight
            stats[f"{stats_prefix}_added"] += 1
        elif sc_weight > existing_sc_weight:
            sc[sc_key] = sc_weight
            stats[f"{stats_prefix}_reinforced"] += 1

    return stats


def _reinforce_vertical_tc_terms(
    tc: Dict[Tuple[str, str], int],
    vertical_entries: List[VerticalEntry],
    tc_usage_score_map: Dict[str, float],
    tc_source_hits_map: Dict[str, int],
    tc_jieba_direct_signal_map: Dict[str, float],
    tc_jieba_pos_map: Dict[str, str],
    tc_char_frequency_prior: Dict[str, float],
    opencc_entries: List[Tuple[str, str]],
    simp_to_trad_char_map: Dict[str, str],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
    min_hanzi: int,
) -> Dict[str, int]:
    stats = {
        "vertical_exact_tc_reinforced": 0,
        "vertical_exact_tc_added": 0,
        "vertical_medicine_penalized_tc": 0,
        "vertical_medicine_penalty_tc_total": 0,
        "vertical_medicine_capped_tc": 0,
    }
    if not tc or not vertical_entries:
        return stats

    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    tc_existing_texts = {text for _pinyin, text in tc.keys()}
    tc_char_prior = _build_effective_char_prior(tc, tc_char_frequency_prior)
    explicit_pinyin_overrides = _build_vertical_explicit_pinyin_override_map(vertical_entries)
    tc_prefix_support = _build_existing_prefix_support_map(
        tc,
        unihan_map,
        unihan_readings_map,
        unihan_source_rank_map,
        unihan_pinlu_detail_map,
    )

    for sc_word, tc_word, usage_score, explicit_pinyin, layer_id, source_id in vertical_entries:
        if _cjk_len(sc_word) < min_hanzi:
            continue

        pinyin = (
            explicit_pinyin
            or explicit_pinyin_overrides.get((layer_id, sc_word), "")
            or _pinyin_from_unihan(
                sc_word,
                unihan_map,
                unihan_readings_map,
                unihan_source_rank_map,
                unihan_pinlu_detail_map,
            )
        )
        if not pinyin:
            continue

        tc_candidate = tc_word
        if not tc_candidate:
            tc_words = opencc_sc_to_tc.get(sc_word, set())
            if tc_words:
                tc_candidate = _choose_tc_phrase_candidate(
                    sc_word,
                    tc_words,
                    simp_to_trad_char_map,
                )
            elif sc_word in tc_existing_texts:
                tc_candidate = sc_word
            else:
                tc_candidate = _convert_sc_text_to_tc_with_phrase_hints(
                    sc_word,
                    opencc_sc_to_tc,
                    simp_to_trad_char_map,
                )
        if _cjk_len(tc_candidate) < min_hanzi:
            continue
        allow_curated_short_medical = (
            layer_id == "medicine"
            and source_id == "project-curated-vertical-medicine"
            and bool(explicit_pinyin)
        )
        if (
            layer_id == "medicine"
            and _cjk_len(tc_candidate) <= 2
            and not (_is_medical_specific_term(tc_candidate) or allow_curated_short_medical)
        ):
            continue
        tc_key = (pinyin, tc_candidate)
        existing_tc_weight = tc.get(tc_key)
        is_named_entity_layer = _is_named_entity_vertical_layer(layer_id)
        supported_named_entity = is_named_entity_layer and (
            (existing_tc_weight is not None and existing_tc_weight >= 700)
            or tc_prefix_support.get(tc_key, 0) >= 620
        )

        if layer_id == "medicine":
            if allow_curated_short_medical:
                base_source_hits = 3
                extra_bonus = 18 if _cjk_len(tc_candidate) <= 2 else (8 if _cjk_len(tc_candidate) <= 4 else 4)
                allow_existing_boost = True
            else:
                base_source_hits = 2 if source_id == "wikidata-medical-mesh-zh" else 1
                extra_bonus = 0 if _cjk_len(tc_candidate) <= 4 else 4
                allow_existing_boost = _cjk_len(tc_candidate) >= 4 or _is_medical_specific_term(tc_candidate)
        elif layer_id == "computing":
            base_source_hits = (
                2 if source_id == "project-curated-vertical-computing" and _cjk_len(tc_candidate) >= 4 else 1
            )
            extra_bonus = 0 if _cjk_len(tc_candidate) <= 4 else 4
            allow_existing_boost = (
                source_id == "project-curated-vertical-computing" and _cjk_len(tc_candidate) >= 4
            )
        elif layer_id == "idioms_allusions":
            curated_idiom = source_id == "project-curated-vertical-idioms-allusions"
            base_source_hits = 2 if curated_idiom and _cjk_len(tc_candidate) <= 6 else 1
            extra_bonus = 4 if curated_idiom and _cjk_len(tc_candidate) <= 4 else (2 if curated_idiom else 0)
            allow_existing_boost = curated_idiom
        elif layer_id == "proper_nouns":
            high_common_proper_noun = (
                source_id == "project-curated-proper-nouns"
                and usage_score >= 0.90
                and _cjk_len(tc_candidate) <= 4
            )
            base_source_hits = 3 if high_common_proper_noun else 1
            extra_bonus = (18 if _cjk_len(tc_candidate) <= 4 else 2) if high_common_proper_noun else (
                0 if _cjk_len(tc_candidate) <= 4 else 2
            )
            allow_existing_boost = high_common_proper_noun
        elif layer_id == "gaming" and source_id.strip().lower().startswith(LOW_PRIORITY_VERTICAL_ENTITY_SOURCE_PREFIXES):
            base_source_hits = 1
            extra_bonus = 0 if _cjk_len(tc_candidate) <= 4 else 2
            allow_existing_boost = False
        elif is_named_entity_layer:
            base_source_hits = 2 if supported_named_entity else 1
            extra_bonus = (8 if _cjk_len(tc_candidate) <= 4 else 4) if supported_named_entity else (
                0 if _cjk_len(tc_candidate) <= 4 else 2
            )
            allow_existing_boost = supported_named_entity
        else:
            base_source_hits = 3
            extra_bonus = 18 if _cjk_len(tc_candidate) <= 4 else 10
            allow_existing_boost = True

        source_hits = max(base_source_hits, tc_source_hits_map.get(tc_candidate, 0))
        usage_score = max(
            _vertical_ranking_usage_score(
                tc_candidate,
                layer_id,
                usage_score,
                source_id=source_id,
                supported_named_entity=supported_named_entity,
            ),
            tc_usage_score_map.get(tc_candidate, 0.0),
        )
        tc_jieba_direct = max(
            tc_jieba_direct_signal_map.get(tc_candidate, 0.0),
            min(0.18, usage_score * 0.18),
        )
        tc_pos_tag = tc_jieba_pos_map.get(tc_candidate, "")
        tc_char_score = _compute_text_single_char_prior(tc_candidate, tc_char_prior)
        tc_weight = _compute_weight_with_signals(
            tc_candidate,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=0.0,
            wiki_hit=True,
            core_entry=False,
            jieba_direct_score=tc_jieba_direct,
            pos_tag=tc_pos_tag,
            char_score=tc_char_score,
        )
        tc_weight = min(1000, tc_weight + extra_bonus)
        if layer_id == "medicine":
            penalty = _compute_medicine_vertical_penalty(tc_candidate, source_id)
            if penalty > 0:
                tc_weight = max(1, tc_weight - penalty)
                stats["vertical_medicine_penalized_tc"] += 1
                stats["vertical_medicine_penalty_tc_total"] += penalty
            capped_weight = _cap_medicine_vertical_weight(tc_weight, tc_candidate, source_id)
            if capped_weight < tc_weight:
                tc_weight = capped_weight
                stats["vertical_medicine_capped_tc"] += 1
        elif not supported_named_entity:
            penalty = _compute_generic_vertical_penalty(tc_candidate, layer_id, source_id)
            if penalty > 0:
                tc_weight = max(1, tc_weight - penalty)
            tc_weight = _cap_generic_vertical_weight(tc_weight, tc_candidate, layer_id, source_id)

        if existing_tc_weight is None:
            tc[tc_key] = tc_weight
            stats["vertical_exact_tc_added"] += 1
        elif allow_existing_boost and tc_weight > existing_tc_weight:
            tc[tc_key] = tc_weight
            stats["vertical_exact_tc_reinforced"] += 1

    return stats


def _augment_with_admin_place_short_aliases(
    sc: Dict[Tuple[str, str], int],
    tc: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    tc_usage_score_map: Dict[str, float],
    tc_source_hits_map: Dict[str, int],
    tc_pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    tc_jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    tc_jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    tc_char_frequency_prior: Dict[str, float],
    opencc_entries: List[Tuple[str, str]],
    simp_to_trad_char_map: Dict[str, str],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    min_hanzi: int,
) -> Tuple[Dict[str, int], Set[str], Set[str]]:
    stats = {
        "admin_place_alias_source_terms": 0,
        "admin_place_alias_skipped_short": 0,
        "admin_place_alias_skipped_existing": 0,
        "admin_place_alias_skipped_no_pinyin": 0,
        "admin_place_alias_added_sc": 0,
        "admin_place_alias_boosted_sc": 0,
        "admin_place_alias_added_tc": 0,
        "admin_place_alias_boosted_tc": 0,
    }
    sc_terms: Set[str] = set()
    tc_terms: Set[str] = set()
    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    pinyin_index = _build_text_pinyin_index(sc, tc)
    sc_existing_texts = {text for _pinyin, text in sc.keys()}
    tc_existing_texts = {text for _pinyin, text in tc.keys()}
    sc_char_prior = _build_effective_char_prior(sc, char_frequency_prior)
    tc_char_prior = _build_effective_char_prior(tc, tc_char_frequency_prior)
    sc_parent_terms = sorted(
        {
            text
            for _pinyin, text in sc.keys()
            if text.endswith("市") and _cjk_len(text) >= max(min_hanzi + 1, 3)
        }
    )

    def _derive_alias_pinyin_candidates(parent_text: str, alias_text: str) -> List[str]:
        candidates: Set[str] = set()
        for parent_pinyin in pinyin_index.get(parent_text, set()):
            normalized_parent = _normalize_pinyin(parent_pinyin)
            if normalized_parent.endswith("shi") and len(normalized_parent) > 3:
                candidates.add(normalized_parent[:-3])

        if not candidates:
            fallback = _pinyin_from_unihan(
                alias_text,
                unihan_map,
                unihan_readings_map,
                unihan_source_rank_map,
                unihan_pinlu_detail_map,
            )
            if fallback:
                candidates.add(fallback)

        return sorted(candidate for candidate in candidates if candidate)

    for sc_parent in sc_parent_terms:
        stats["admin_place_alias_source_terms"] += 1
        sc_alias = sc_parent[:-1]
        if not CJK_FULL_RE.fullmatch(sc_alias) or _cjk_len(sc_alias) < min_hanzi:
            stats["admin_place_alias_skipped_short"] += 1
            continue
        if sc_alias in sc_existing_texts:
            stats["admin_place_alias_skipped_existing"] += 1
            continue

        pinyin_candidates = _derive_alias_pinyin_candidates(sc_parent, sc_alias)
        if not pinyin_candidates:
            stats["admin_place_alias_skipped_no_pinyin"] += 1
            continue

        parent_usage = min(1.0, max(0.0, usage_score_map.get(sc_parent, 0.0)))
        parent_source_hits = max(0, source_hits_map.get(sc_parent, 0))
        parent_pageview = min(1.0, max(0.0, pageviews_signal_map.get(sc_parent, 0.0)))
        parent_jieba_direct = min(
            1.0, max(0.0, jieba_direct_signal_map.get(sc_parent, 0.0))
        )
        sc_usage = max(
            usage_score_map.get(sc_alias, 0.0),
            min(0.18, max(parent_usage * 0.45, 0.08)),
        )
        sc_source_hits = max(
            source_hits_map.get(sc_alias, 0),
            min(max(parent_source_hits, 1), 2),
        )
        sc_pageview = max(
            pageviews_signal_map.get(sc_alias, 0.0),
            min(parent_pageview * 0.35, 0.06),
        )
        sc_jieba_direct = max(
            jieba_direct_signal_map.get(sc_alias, 0.0),
            min(0.04, max(parent_jieba_direct * 0.25, sc_usage * 0.12)),
        )
        sc_pos_tag = jieba_pos_map.get(sc_parent, "ns") or "ns"
        sc_char_score = _compute_text_single_char_prior(sc_alias, sc_char_prior)
        sc_weight = _compute_weight_with_signals(
            sc_alias,
            usage_score=sc_usage,
            source_hits=sc_source_hits,
            pageview_score=sc_pageview,
            wiki_hit=False,
            core_entry=False,
            jieba_direct_score=sc_jieba_direct,
            pos_tag=sc_pos_tag,
            char_score=sc_char_score,
        )
        sc_weight = min(sc_weight, 320)
        usage_score_map[sc_alias] = max(usage_score_map.get(sc_alias, 0.0), sc_usage)
        source_hits_map[sc_alias] = max(source_hits_map.get(sc_alias, 0), sc_source_hits)
        pageviews_signal_map[sc_alias] = max(
            pageviews_signal_map.get(sc_alias, 0.0), sc_pageview
        )

        added_sc = False
        boosted_sc = False
        for pinyin in pinyin_candidates:
            sc_key = (pinyin, sc_alias)
            existing_sc_weight = sc.get(sc_key)
            if existing_sc_weight is None:
                sc[sc_key] = sc_weight
                added_sc = True
                sc_terms.add(sc_alias)
            elif sc_weight > existing_sc_weight:
                sc[sc_key] = sc_weight
                boosted_sc = True
                sc_terms.add(sc_alias)
        if added_sc:
            stats["admin_place_alias_added_sc"] += 1
        if boosted_sc:
            stats["admin_place_alias_boosted_sc"] += 1

        tc_candidates = opencc_sc_to_tc.get(sc_alias, set())
        if not tc_candidates:
            converted = _convert_sc_text_to_tc_with_phrase_hints(
                sc_alias,
                opencc_sc_to_tc,
                simp_to_trad_char_map,
            )
            if converted != sc_alias or sc_alias in tc_existing_texts:
                tc_candidates = {converted}

        added_tc = False
        boosted_tc = False
        for tc_alias in tc_candidates:
            if not CJK_FULL_RE.fullmatch(tc_alias) or _cjk_len(tc_alias) < min_hanzi:
                continue
            if tc_alias in tc_existing_texts:
                continue

            tc_usage = max(tc_usage_score_map.get(tc_alias, 0.0), sc_usage)
            tc_source_hits = max(tc_source_hits_map.get(tc_alias, 0), sc_source_hits)
            tc_pageview = max(tc_pageviews_signal_map.get(tc_alias, 0.0), sc_pageview)
            tc_jieba_direct = max(
                tc_jieba_direct_signal_map.get(tc_alias, 0.0), sc_jieba_direct
            )
            tc_pos_tag = tc_jieba_pos_map.get(tc_alias, sc_pos_tag) or sc_pos_tag
            tc_char_score = _compute_text_single_char_prior(tc_alias, tc_char_prior)
            tc_weight = _compute_weight_with_signals(
                tc_alias,
                usage_score=tc_usage,
                source_hits=tc_source_hits,
                pageview_score=tc_pageview,
                wiki_hit=False,
                core_entry=False,
                jieba_direct_score=tc_jieba_direct,
                pos_tag=tc_pos_tag,
                char_score=tc_char_score,
            )
            tc_weight = min(tc_weight, 320)
            tc_usage_score_map[tc_alias] = max(tc_usage_score_map.get(tc_alias, 0.0), tc_usage)
            tc_source_hits_map[tc_alias] = max(tc_source_hits_map.get(tc_alias, 0), tc_source_hits)
            tc_pageviews_signal_map[tc_alias] = max(
                tc_pageviews_signal_map.get(tc_alias, 0.0), tc_pageview
            )
            for pinyin in pinyin_candidates:
                tc_key = (pinyin, tc_alias)
                existing_tc_weight = tc.get(tc_key)
                if existing_tc_weight is None:
                    tc[tc_key] = tc_weight
                    added_tc = True
                    tc_terms.add(tc_alias)
                elif tc_weight > existing_tc_weight:
                    tc[tc_key] = tc_weight
                    boosted_tc = True
                    tc_terms.add(tc_alias)
        if added_tc:
            stats["admin_place_alias_added_tc"] += 1
        if boosted_tc:
            stats["admin_place_alias_boosted_tc"] += 1

    return stats, sc_terms, tc_terms


def _augment_with_vertical_terms(
    sc: Dict[Tuple[str, str], int],
    tc: Dict[Tuple[str, str], int],
    vertical_entries: List[VerticalEntry],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    tc_usage_score_map: Dict[str, float],
    tc_source_hits_map: Dict[str, int],
    jieba_direct_signal_map: Dict[str, float],
    tc_jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    tc_jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    tc_char_frequency_prior: Dict[str, float],
    opencc_entries: List[Tuple[str, str]],
    simp_to_trad_char_map: Dict[str, str],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
    min_hanzi: int,
) -> Tuple[Dict[str, int], Set[str], Set[str]]:
    stats = {
        "vertical_terms_total": 0,
        "vertical_terms_added_sc": 0,
        "vertical_terms_boosted_sc": 0,
        "vertical_terms_added_tc": 0,
        "vertical_terms_boosted_tc": 0,
        "vertical_terms_skipped_short": 0,
        "vertical_terms_skipped_no_pinyin": 0,
        "vertical_medicine_penalized_sc": 0,
        "vertical_medicine_penalty_sc_total": 0,
        "vertical_medicine_capped_sc": 0,
        "vertical_generic_capped_sc": 0,
        "vertical_medicine_penalized_tc": 0,
        "vertical_medicine_penalty_tc_total": 0,
        "vertical_medicine_capped_tc": 0,
        "vertical_generic_capped_tc": 0,
    }
    sc_terms: Set[str] = set()
    tc_terms: Set[str] = set()
    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    tc_existing_texts = {text for _pinyin, text in tc.keys()}
    sc_char_prior = _build_effective_char_prior(sc, char_frequency_prior)
    tc_char_prior = _build_effective_char_prior(tc, tc_char_frequency_prior)
    explicit_pinyin_overrides = _build_vertical_explicit_pinyin_override_map(vertical_entries)
    sc_prefix_support = _build_existing_prefix_support_map(
        sc,
        unihan_map,
        unihan_readings_map,
        unihan_source_rank_map,
        unihan_pinlu_detail_map,
    )
    tc_prefix_support = _build_existing_prefix_support_map(
        tc,
        unihan_map,
        unihan_readings_map,
        unihan_source_rank_map,
        unihan_pinlu_detail_map,
    )

    for sc_word, tc_word, usage_score, explicit_pinyin, layer_id, source_id in vertical_entries:
        stats["vertical_terms_total"] += 1
        if _cjk_len(sc_word) < min_hanzi:
            stats["vertical_terms_skipped_short"] += 1
            continue

        allow_curated_short_medical = (
            layer_id == "medicine"
            and source_id == "project-curated-vertical-medicine"
            and bool(explicit_pinyin)
        )
        if (
            layer_id == "medicine"
            and _cjk_len(sc_word) <= 2
            and not (_is_medical_specific_term(sc_word) or allow_curated_short_medical)
        ):
            stats["vertical_terms_skipped_short"] += 1
            continue
        if (
            layer_id == "architecture_entities"
            and source_id != "project-curated-vertical-architecture-entities"
            and _cjk_len(sc_word) <= 3
        ):
            stats["vertical_terms_skipped_short"] += 1
            continue

        pinyin = (
            explicit_pinyin
            or explicit_pinyin_overrides.get((layer_id, sc_word), "")
            or _pinyin_from_unihan(
                sc_word,
                unihan_map,
                unihan_readings_map,
                unihan_source_rank_map,
                unihan_pinlu_detail_map,
            )
        )
        if not pinyin:
            stats["vertical_terms_skipped_no_pinyin"] += 1
            continue

        sc_key = (pinyin, sc_word)
        existing_sc_weight = sc.get(sc_key)
        is_named_entity_layer = _is_named_entity_vertical_layer(layer_id)
        sc_supported_named_entity = is_named_entity_layer and (
            (existing_sc_weight is not None and existing_sc_weight >= 700)
            or sc_prefix_support.get(sc_key, 0) >= 620
        )

        if layer_id == "medicine":
            if allow_curated_short_medical:
                source_hits = 3
                short_bonus = 18 if _cjk_len(sc_word) <= 2 else 0
                long_bonus = 8 if _cjk_len(sc_word) <= 4 else 4
                allow_existing_boost = True
            else:
                source_hits = 2 if source_id == "wikidata-medical-mesh-zh" else 1
                short_bonus = 0
                long_bonus = 4
                allow_existing_boost = _cjk_len(sc_word) >= 4 or _is_medical_specific_term(sc_word)
        elif layer_id == "computing":
            source_hits = 2 if source_id == "project-curated-vertical-computing" and _cjk_len(sc_word) >= 4 else 1
            short_bonus = 0
            long_bonus = 4
            allow_existing_boost = (
                source_id == "project-curated-vertical-computing" and _cjk_len(sc_word) >= 4
            )
        elif layer_id == "architecture_terms":
            source_hits = 1
            short_bonus = 0
            long_bonus = 4
            allow_existing_boost = (
                source_id == "project-curated-vertical-architecture-terms"
                and _cjk_len(sc_word) >= 4
            )
        elif layer_id == "architecture_entities":
            source_hits = 1
            short_bonus = 0
            long_bonus = 2
            allow_existing_boost = (
                source_id == "project-curated-vertical-architecture-entities"
                and _cjk_len(sc_word) >= 5
            )
        elif layer_id == "place_names":
            curated_common_place = (
                source_id == "project-curated-vertical-place-names"
                and usage_score >= 0.82
            )
            source_hits = 2 if curated_common_place else 1
            short_bonus = 4 if curated_common_place and _cjk_len(sc_word) <= 4 else 0
            long_bonus = 2 if curated_common_place else 0
            allow_existing_boost = curated_common_place
        elif layer_id == "idioms_allusions":
            curated_idiom = source_id == "project-curated-vertical-idioms-allusions"
            source_hits = 2 if curated_idiom and _cjk_len(sc_word) <= 6 else 1
            short_bonus = 4 if curated_idiom and _cjk_len(sc_word) <= 4 else 0
            long_bonus = 2 if curated_idiom else 0
            allow_existing_boost = curated_idiom
        elif layer_id == "proper_nouns":
            high_common_proper_noun = (
                source_id == "project-curated-proper-nouns"
                and usage_score >= 0.90
                and _cjk_len(sc_word) <= 4
            )
            source_hits = 3 if high_common_proper_noun else 1
            short_bonus = 18 if high_common_proper_noun else 0
            long_bonus = 2
            allow_existing_boost = high_common_proper_noun
        elif layer_id == "gaming" and source_id.strip().lower().startswith(LOW_PRIORITY_VERTICAL_ENTITY_SOURCE_PREFIXES):
            source_hits = 1
            short_bonus = 0
            long_bonus = 2
            allow_existing_boost = False
        elif is_named_entity_layer:
            source_hits = 2 if sc_supported_named_entity else 1
            short_bonus = 8 if sc_supported_named_entity else 0
            long_bonus = 4 if sc_supported_named_entity else 2
            allow_existing_boost = sc_supported_named_entity
        else:
            source_hits = 3
            short_bonus = 18
            long_bonus = 10
            allow_existing_boost = True
        sc_ranking_usage_score = _vertical_ranking_usage_score(
            sc_word,
            layer_id,
            usage_score,
            source_id=source_id,
            supported_named_entity=sc_supported_named_entity,
        )
        usage_score_map[sc_word] = max(usage_score_map.get(sc_word, 0.0), sc_ranking_usage_score)
        source_hits_map[sc_word] = max(source_hits_map.get(sc_word, 0), source_hits)

        sc_jieba_direct = max(
            jieba_direct_signal_map.get(sc_word, 0.0),
            min(0.18, sc_ranking_usage_score * 0.18),
        )
        sc_pos_tag = jieba_pos_map.get(sc_word, "")
        sc_char_score = _compute_text_single_char_prior(sc_word, sc_char_prior)
        sc_weight = _compute_weight_with_signals(
            sc_word,
            usage_score=sc_ranking_usage_score,
            source_hits=source_hits,
            pageview_score=0.0,
            wiki_hit=False,
            core_entry=False,
            jieba_direct_score=sc_jieba_direct,
            pos_tag=sc_pos_tag,
            char_score=sc_char_score,
        )
        sc_weight = min(1000, sc_weight + (short_bonus if _cjk_len(sc_word) <= 4 else long_bonus))
        if layer_id == "medicine":
            penalty = _compute_medicine_vertical_penalty(sc_word, source_id)
            if penalty > 0:
                sc_weight = max(1, sc_weight - penalty)
                stats["vertical_medicine_penalized_sc"] += 1
                stats["vertical_medicine_penalty_sc_total"] += penalty
            capped_weight = _cap_medicine_vertical_weight(sc_weight, sc_word, source_id)
            if capped_weight < sc_weight:
                sc_weight = capped_weight
                stats["vertical_medicine_capped_sc"] += 1
        elif not sc_supported_named_entity:
            penalty = _compute_generic_vertical_penalty(sc_word, layer_id, source_id)
            if penalty > 0:
                sc_weight = max(1, sc_weight - penalty)
            capped_weight = _cap_generic_vertical_weight(sc_weight, sc_word, layer_id, source_id)
            if capped_weight < sc_weight:
                sc_weight = capped_weight
                stats["vertical_generic_capped_sc"] += 1
        if existing_sc_weight is None:
            sc[sc_key] = sc_weight
            stats["vertical_terms_added_sc"] += 1
            sc_terms.add(sc_word)
        elif allow_existing_boost and sc_weight > existing_sc_weight:
            sc[sc_key] = sc_weight
            stats["vertical_terms_boosted_sc"] += 1
            sc_terms.add(sc_word)
        else:
            sc_terms.add(sc_word)

        tc_candidate = tc_word
        if not tc_candidate:
            tc_words = opencc_sc_to_tc.get(sc_word, set())
            if tc_words:
                tc_candidate = _choose_tc_phrase_candidate(
                    sc_word,
                    tc_words,
                    simp_to_trad_char_map,
                )
            elif sc_word in tc_existing_texts:
                tc_candidate = sc_word
            else:
                tc_candidate = _convert_sc_text_to_tc_with_phrase_hints(
                    sc_word,
                    opencc_sc_to_tc,
                    simp_to_trad_char_map,
                )
        if _cjk_len(tc_candidate) < min_hanzi:
            continue

        tc_key = (pinyin, tc_candidate)
        existing_tc_weight = tc.get(tc_key)
        tc_supported_named_entity = is_named_entity_layer and (
            (existing_tc_weight is not None and existing_tc_weight >= 700)
            or tc_prefix_support.get(tc_key, 0) >= 620
        )
        tc_source_hits = (
            max(source_hits, 2)
            if tc_supported_named_entity
            else source_hits
        )
        tc_short_bonus = (
            max(short_bonus, 8)
            if tc_supported_named_entity and _cjk_len(tc_candidate) <= 4
            else short_bonus
        )
        tc_long_bonus = max(long_bonus, 4) if tc_supported_named_entity else long_bonus
        tc_allow_existing_boost = (
            tc_supported_named_entity if is_named_entity_layer else allow_existing_boost
        )
        tc_ranking_usage_score = _vertical_ranking_usage_score(
            tc_candidate,
            layer_id,
            usage_score,
            source_id=source_id,
            supported_named_entity=tc_supported_named_entity,
        )
        tc_usage_score_map[tc_candidate] = max(tc_usage_score_map.get(tc_candidate, 0.0), tc_ranking_usage_score)
        tc_source_hits_map[tc_candidate] = max(tc_source_hits_map.get(tc_candidate, 0), tc_source_hits)

        tc_jieba_direct = max(
            tc_jieba_direct_signal_map.get(tc_candidate, 0.0),
            min(0.18, tc_ranking_usage_score * 0.18),
        )
        tc_pos_tag = tc_jieba_pos_map.get(tc_candidate, sc_pos_tag)
        tc_char_score = _compute_text_single_char_prior(tc_candidate, tc_char_prior)
        tc_weight = _compute_weight_with_signals(
            tc_candidate,
            usage_score=tc_ranking_usage_score,
            source_hits=tc_source_hits,
            pageview_score=0.0,
            wiki_hit=False,
            core_entry=False,
            jieba_direct_score=tc_jieba_direct,
            pos_tag=tc_pos_tag,
            char_score=tc_char_score,
        )
        tc_weight = min(1000, tc_weight + (tc_short_bonus if _cjk_len(tc_candidate) <= 4 else tc_long_bonus))
        if layer_id == "medicine":
            penalty = _compute_medicine_vertical_penalty(tc_candidate, source_id)
            if penalty > 0:
                tc_weight = max(1, tc_weight - penalty)
                stats["vertical_medicine_penalized_tc"] += 1
                stats["vertical_medicine_penalty_tc_total"] += penalty
            capped_weight = _cap_medicine_vertical_weight(tc_weight, tc_candidate, source_id)
            if capped_weight < tc_weight:
                tc_weight = capped_weight
                stats["vertical_medicine_capped_tc"] += 1
        elif not tc_supported_named_entity:
            penalty = _compute_generic_vertical_penalty(tc_candidate, layer_id, source_id)
            if penalty > 0:
                tc_weight = max(1, tc_weight - penalty)
            capped_weight = _cap_generic_vertical_weight(tc_weight, tc_candidate, layer_id, source_id)
            if capped_weight < tc_weight:
                tc_weight = capped_weight
                stats["vertical_generic_capped_tc"] += 1
        if existing_tc_weight is None:
            tc[tc_key] = tc_weight
            stats["vertical_terms_added_tc"] += 1
            tc_terms.add(tc_candidate)
        elif tc_allow_existing_boost and tc_weight > existing_tc_weight:
            tc[tc_key] = tc_weight
            stats["vertical_terms_boosted_tc"] += 1
            tc_terms.add(tc_candidate)
        else:
            tc_terms.add(tc_candidate)

    return stats, sc_terms, tc_terms


def _augment_with_wiki_proper_noun_titles(
    sc: Dict[Tuple[str, str], int],
    tc: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    tc_usage_score_map: Dict[str, float],
    tc_source_hits_map: Dict[str, int],
    tc_pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    tc_jieba_direct_signal_map: Dict[str, float],
    jieba_pos_map: Dict[str, str],
    tc_jieba_pos_map: Dict[str, str],
    char_frequency_prior: Dict[str, float],
    tc_char_frequency_prior: Dict[str, float],
    opencc_entries: List[Tuple[str, str]],
    tc_to_sc_map: Dict[str, Set[str]],
    simp_to_trad_char_map: Dict[str, str],
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]] | None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    wiki_titles: Set[str],
    min_hanzi: int,
) -> Tuple[Dict[str, int], Set[str], Set[str]]:
    stats = {
        "wiki_proper_titles_total": 0,
        "wiki_proper_titles_candidates_sc": 0,
        "wiki_proper_titles_skipped_daily_like": 0,
        "wiki_proper_titles_skipped_weak_signal": 0,
        "wiki_proper_titles_skipped_no_pinyin": 0,
        "wiki_proper_titles_pageview_backed": 0,
        "wiki_proper_titles_prefix_backed": 0,
        "wiki_proper_titles_added_sc": 0,
        "wiki_proper_titles_boosted_sc": 0,
        "wiki_proper_titles_added_tc": 0,
        "wiki_proper_titles_boosted_tc": 0,
    }
    if not wiki_titles:
        return stats, set(), set()

    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    pinyin_index = _build_text_pinyin_index(sc, tc)
    tc_existing_texts = {text for _pinyin, text in tc.keys()}
    sc_char_prior = _build_effective_char_prior(sc, char_frequency_prior)
    tc_char_prior = _build_effective_char_prior(tc, tc_char_frequency_prior)
    sc_text_best_weight = _build_text_best_weight_map(sc)
    tc_text_best_weight = _build_text_best_weight_map(tc)
    sc_prefix_term_count_map, sc_prefix_support_sum_map = _build_text_prefix_support_from_best_weight(
        sc_text_best_weight
    )
    tc_prefix_term_count_map, tc_prefix_support_sum_map = _build_text_prefix_support_from_best_weight(
        tc_text_best_weight
    )

    sc_candidates: Set[str] = set()
    for title in wiki_titles:
        stats["wiki_proper_titles_total"] += 1
        if _looks_like_daily_chat_seed(title):
            stats["wiki_proper_titles_skipped_daily_like"] += 1
            continue
        if not CJK_FULL_RE.fullmatch(title):
            continue
        title_len = _cjk_len(title)
        if title_len < min_hanzi or title_len > 6:
            continue
        sc_words = tc_to_sc_map.get(title, set())
        if sc_words:
            sc_candidates.update(sc_words)
        else:
            sc_candidates.add(title)

    sc_terms: Set[str] = set()
    tc_terms: Set[str] = set()

    for sc_word in sorted(sc_candidates):
        if not CJK_FULL_RE.fullmatch(sc_word):
            continue
        if _looks_like_daily_chat_seed(sc_word):
            continue
        text_len = _cjk_len(sc_word)
        if text_len < min_hanzi or text_len > 6:
            continue

        stats["wiki_proper_titles_candidates_sc"] += 1
        direct_usage = min(1.0, max(0.0, usage_score_map.get(sc_word, 0.0)))
        direct_source_hits = max(0, source_hits_map.get(sc_word, 0))
        direct_pageview = min(1.0, max(0.0, pageviews_signal_map.get(sc_word, 0.0)))
        direct_jieba = min(1.0, max(0.0, jieba_direct_signal_map.get(sc_word, 0.0)))
        pos_tag = jieba_pos_map.get(sc_word, "")
        char_score = _compute_text_single_char_prior(sc_word, sc_char_prior)
        min_char_prior = _compute_min_char_prior(sc_word, sc_char_prior)
        prefix_term_count = max(0, sc_prefix_term_count_map.get(sc_word, 0))
        prefix_support = max(0.0, sc_prefix_support_sum_map.get(sc_word, 0.0))

        pageview_backed = direct_pageview >= 0.08
        source_backed = direct_source_hits >= 2
        prefix_backed = (
            text_len <= 4
            and (
                (prefix_term_count >= 1 and prefix_support >= 320.0)
                or (prefix_term_count >= 2 and prefix_support >= 220.0)
            )
        )
        if text_len == 2:
            has_admissible_support = pageview_backed or source_backed or (
                prefix_backed and (direct_jieba >= 0.06 or direct_usage >= 0.06)
            )
        else:
            has_admissible_support = pageview_backed or source_backed or prefix_backed
        if not has_admissible_support:
            stats["wiki_proper_titles_skipped_weak_signal"] += 1
            continue

        if text_len == 2:
            if char_score < 0.06 and min_char_prior < 0.01 and not (pageview_backed or source_backed):
                stats["wiki_proper_titles_skipped_weak_signal"] += 1
                continue
        elif text_len == 3:
            if char_score < 0.05 and min_char_prior < 0.008 and not (pageview_backed or source_backed):
                stats["wiki_proper_titles_skipped_weak_signal"] += 1
                continue
        elif char_score < 0.04 and min_char_prior < 0.006 and not pageview_backed:
            stats["wiki_proper_titles_skipped_weak_signal"] += 1
            continue

        pinyin_candidates = sorted(pinyin_index.get(sc_word, set()))
        if not pinyin_candidates:
            pinyin_candidates = sorted(
                _derive_prefix_pinyin_candidates_from_longer_terms(
                    sc_word,
                    pinyin_index,
                    unihan_readings_map,
                    unihan_source_rank_map,
                    unihan_map,
                    unihan_pinlu_detail_map,
                )
            )
        if not pinyin_candidates:
            fallback = _pinyin_from_unihan(
                sc_word,
                unihan_map,
                unihan_readings_map,
                unihan_source_rank_map,
                unihan_pinlu_detail_map,
            )
            if fallback and (pageview_backed or source_backed or prefix_support >= 420.0):
                pinyin_candidates = [fallback]
        if not pinyin_candidates:
            stats["wiki_proper_titles_skipped_no_pinyin"] += 1
            continue

        synthetic_usage = direct_usage
        if pageview_backed:
            if direct_pageview >= 0.16:
                synthetic_usage = max(synthetic_usage, 0.32)
            elif direct_pageview >= 0.12:
                synthetic_usage = max(synthetic_usage, 0.28)
            else:
                synthetic_usage = max(synthetic_usage, 0.24)
            stats["wiki_proper_titles_pageview_backed"] += 1
        elif prefix_backed:
            if prefix_support >= 700.0 or prefix_term_count >= 2:
                synthetic_usage = max(synthetic_usage, 0.24)
            else:
                synthetic_usage = max(synthetic_usage, 0.20)
            stats["wiki_proper_titles_prefix_backed"] += 1
        else:
            synthetic_usage = max(synthetic_usage, 0.22)

        synthetic_source_hits = direct_source_hits
        if pageview_backed and direct_pageview >= 0.16:
            synthetic_source_hits = max(synthetic_source_hits, 3)
        elif prefix_backed and (prefix_support >= 700.0 or prefix_term_count >= 2):
            synthetic_source_hits = max(synthetic_source_hits, 3)
        elif pageview_backed or source_backed or prefix_backed:
            synthetic_source_hits = max(synthetic_source_hits, 2)

        synthetic_jieba_direct = max(
            direct_jieba,
            min(0.16, synthetic_usage * 0.36),
        )
        weight = _compute_weight_with_signals(
            sc_word,
            usage_score=synthetic_usage,
            source_hits=synthetic_source_hits,
            pageview_score=direct_pageview,
            wiki_hit=True,
            core_entry=False,
            jieba_direct_score=synthetic_jieba_direct,
            pos_tag=pos_tag,
            char_score=char_score,
        )

        usage_score_map[sc_word] = max(usage_score_map.get(sc_word, 0.0), synthetic_usage)
        source_hits_map[sc_word] = max(source_hits_map.get(sc_word, 0), synthetic_source_hits)
        pageviews_signal_map[sc_word] = max(pageviews_signal_map.get(sc_word, 0.0), direct_pageview)

        added_sc = False
        boosted_sc = False
        for pinyin in pinyin_candidates:
            key = (pinyin, sc_word)
            existing_sc_weight = sc.get(key)
            if existing_sc_weight is None:
                sc[key] = weight
                added_sc = True
                sc_terms.add(sc_word)
            elif weight > existing_sc_weight:
                sc[key] = weight
                boosted_sc = True
                sc_terms.add(sc_word)
            else:
                sc_terms.add(sc_word)
        if added_sc:
            stats["wiki_proper_titles_added_sc"] += 1
        if boosted_sc:
            stats["wiki_proper_titles_boosted_sc"] += 1

        tc_words = opencc_sc_to_tc.get(sc_word, set())
        if not tc_words:
            if sc_word in tc_existing_texts:
                tc_words = {sc_word}
            else:
                converted = _convert_sc_text_to_tc_with_phrase_hints(
                    sc_word,
                    opencc_sc_to_tc,
                    simp_to_trad_char_map,
                )
                if converted != sc_word:
                    tc_words = {converted}

        added_tc = False
        boosted_tc = False
        for tc_word in tc_words:
            if _cjk_len(tc_word) < min_hanzi or _cjk_len(tc_word) > 6:
                continue
            tc_char_score = _compute_text_single_char_prior(tc_word, tc_char_prior)
            tc_direct_pageview = min(1.0, max(0.0, tc_pageviews_signal_map.get(tc_word, direct_pageview)))
            tc_direct_jieba = min(
                1.0,
                max(0.0, tc_jieba_direct_signal_map.get(tc_word, synthetic_jieba_direct)),
            )
            tc_pos_tag = tc_jieba_pos_map.get(tc_word, pos_tag)
            tc_prefix_term_count = max(0, tc_prefix_term_count_map.get(tc_word, prefix_term_count))
            tc_prefix_support = max(0.0, tc_prefix_support_sum_map.get(tc_word, prefix_support))
            tc_source_hits = max(tc_source_hits_map.get(tc_word, 0), synthetic_source_hits)
            if tc_prefix_support >= 700.0 or tc_prefix_term_count >= 2:
                tc_source_hits = max(tc_source_hits, 3)
            tc_weight = _compute_weight_with_signals(
                tc_word,
                usage_score=synthetic_usage,
                source_hits=tc_source_hits,
                pageview_score=tc_direct_pageview,
                wiki_hit=True,
                core_entry=False,
                jieba_direct_score=tc_direct_jieba,
                pos_tag=tc_pos_tag,
                char_score=tc_char_score,
            )
            tc_usage_score_map[tc_word] = max(tc_usage_score_map.get(tc_word, 0.0), synthetic_usage)
            tc_source_hits_map[tc_word] = max(tc_source_hits_map.get(tc_word, 0), tc_source_hits)
            tc_pageviews_signal_map[tc_word] = max(tc_pageviews_signal_map.get(tc_word, 0.0), tc_direct_pageview)
            for pinyin in pinyin_candidates:
                key = (pinyin, tc_word)
                existing_tc_weight = tc.get(key)
                if existing_tc_weight is None:
                    tc[key] = tc_weight
                    added_tc = True
                    tc_terms.add(tc_word)
                elif tc_weight > existing_tc_weight:
                    tc[key] = tc_weight
                    boosted_tc = True
                    tc_terms.add(tc_word)
                else:
                    tc_terms.add(tc_word)
        if added_tc:
            stats["wiki_proper_titles_added_tc"] += 1
        if boosted_tc:
            stats["wiki_proper_titles_boosted_tc"] += 1

    return stats, sc_terms, tc_terms


def _apply_limit(
    mapping: Dict[Tuple[str, str], int],
    max_entries: int,
) -> Dict[Tuple[str, str], int]:
    if max_entries <= 0 or len(mapping) <= max_entries:
        return mapping

    items = sorted(
        mapping.items(),
        key=lambda kv: (-kv[1], kv[0][0], kv[0][1]),
    )[:max_entries]
    return dict(items)


def _drop_explicit_multi_char_terms(
    mapping: Dict[Tuple[str, str], int],
    drop_terms: Set[str],
) -> Tuple[Dict[Tuple[str, str], int], int]:
    if not drop_terms:
        return mapping, 0

    filtered: Dict[Tuple[str, str], int] = {}
    dropped = 0
    for key, weight in mapping.items():
        _pinyin, text = key
        if len(text) > 1 and (
            text in drop_terms
            or any(fragment in text for fragment in MULTI_CHAR_TERM_DROP_SUBSTRINGS)
        ):
            dropped += 1
            continue
        filtered[key] = weight
    return filtered, dropped


def _filter_windows_unrenderable_entries(
    mapping: Dict[Tuple[str, str], int],
) -> Tuple[Dict[Tuple[str, str], int], int]:
    filtered: Dict[Tuple[str, str], int] = {}
    dropped = 0
    for key, weight in mapping.items():
        _pinyin, text = key
        if not _is_windows_renderable_cjk_text(text):
            dropped += 1
            continue
        filtered[key] = weight
    return filtered, dropped


def _write_dict(
    path: pathlib.Path,
    mapping: Dict[Tuple[str, str], int],
    preferred_terms: Set[str] | None = None,
    low_priority_output_terms: Set[str] | None = None,
    post_low_priority_output_terms: Set[str] | None = None,
    preserve_pinyin_keys: Set[Tuple[str, str]] | None = None,
    unihan_map: Dict[str, str] | None = None,
    unihan_readings_map: Dict[str, Set[str]] | None = None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None = None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None = None,
    contains_popularity_excluded_terms: Set[str] | None = None,
) -> None:
    preferred_terms = preferred_terms or set()
    low_priority_output_terms = low_priority_output_terms or set()
    post_low_priority_output_terms = post_low_priority_output_terms or set()
    preserve_pinyin_keys = preserve_pinyin_keys or set()
    contains_popularity_excluded_terms = contains_popularity_excluded_terms or set()
    valid_single_syllables: Set[str] = set()
    if unihan_readings_map:
        for readings in unihan_readings_map.values():
            valid_single_syllables.update(readings)

    def should_emit_compact_apostrophe_alias(output_pinyin: str, text: str) -> bool:
        if "'" not in output_pinyin:
            return False
        if _cjk_len(text) > 4:
            return False
        compact = output_pinyin.replace("'", "")
        if not compact or compact == output_pinyin:
            return False
        if not PINYIN_RE.fullmatch(compact):
            return False
        # Do not alias forms like ji'e -> jie or xi'an -> xian; those compact
        # strings are valid standalone syllables and would pollute exact lookup.
        return compact not in valid_single_syllables

    output_rows: Dict[Tuple[str, str], int] = {}
    path.parent.mkdir(parents=True, exist_ok=True)
    for (pinyin, text), weight in mapping.items():
        if (pinyin, text) in preserve_pinyin_keys:
            output_pinyin = pinyin
        else:
            output_pinyin = _canonicalize_output_pinyin(
                pinyin,
                text,
                unihan_map,
                unihan_readings_map,
                unihan_source_rank_map,
                unihan_pinlu_detail_map,
            )
        if not output_pinyin:
            continue
        output_pinyin = output_pinyin.replace("\ufeff", "").strip()
        text = text.replace("\ufeff", "").strip()
        if not output_pinyin or not text:
            continue
        key = (output_pinyin, text)
        output_rows[key] = max(output_rows.get(key, 0), weight)
        if should_emit_compact_apostrophe_alias(output_pinyin, text):
            alias_key = (output_pinyin.replace("'", ""), text)
            output_rows[alias_key] = max(output_rows.get(alias_key, 0), weight)

    def output_sort_key(item: Tuple[Tuple[str, str], int]) -> Tuple[object, ...]:
        (output_pinyin, text), weight = item
        return (
            1
            if text in low_priority_output_terms
            or text in post_low_priority_output_terms
            else 0,
            1 if text in post_low_priority_output_terms else 0,
            output_pinyin,
            -weight,
            0 if text in preferred_terms else 1,
            text,
        )

    # dict_base IDs follow import order and dict_jianpin references those IDs.
    # Preserve surviving rows in their previous order so an additive vocabulary
    # update cannot renumber every later entry and perturb otherwise tied query
    # results. New rows remain deterministic and are appended in normal order.
    existing_keys: List[Tuple[str, str]] = []
    existing_seen: Set[Tuple[str, str]] = set()
    if path.exists():
        with path.open("r", encoding="utf-8") as existing_file:
            for raw_line in existing_file:
                parts = raw_line.rstrip("\n").split("\t")
                if len(parts) < 2:
                    continue
                existing_key = (
                    parts[0].replace("\ufeff", "").strip(),
                    parts[1].replace("\ufeff", "").strip(),
                )
                if (
                    existing_key in output_rows
                    and existing_key not in existing_seen
                ):
                    existing_keys.append(existing_key)
                    existing_seen.add(existing_key)

    new_items = sorted(
        (
            (key, weight)
            for key, weight in output_rows.items()
            if key not in existing_seen
        ),
        key=output_sort_key,
    )
    ordered_items = [
        (key, output_rows[key]) for key in existing_keys
    ] + new_items

    with path.open("w", encoding="utf-8", newline="\n") as f:
        for (output_pinyin, text), weight in ordered_items:
            scope = "\tno_contains" if text in contains_popularity_excluded_terms else ""
            f.write(f"{output_pinyin}\t{text}\t{weight}{scope}\n")


def _build_output_pinyin_bucket_map(
    mapping: Dict[Tuple[str, str], int],
    preserve_pinyin_keys: Set[Tuple[str, str]] | None = None,
    unihan_map: Dict[str, str] | None = None,
    unihan_readings_map: Dict[str, Set[str]] | None = None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None = None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None = None,
) -> Dict[Tuple[str, str], str]:
    """Return the same pinyin bucket key that _write_dict will emit."""
    preserve_pinyin_keys = preserve_pinyin_keys or set()
    bucket_map: Dict[Tuple[str, str], str] = {}
    for pinyin, text in mapping.keys():
        if (pinyin, text) in preserve_pinyin_keys:
            output_pinyin = pinyin
        else:
            output_pinyin = _canonicalize_output_pinyin(
                pinyin,
                text,
                unihan_map,
                unihan_readings_map,
                unihan_source_rank_map,
                unihan_pinlu_detail_map,
            )
        output_pinyin = output_pinyin.replace("\ufeff", "").strip()
        if output_pinyin:
            bucket_map[(pinyin, text)] = output_pinyin
    return bucket_map


def _load_existing_dict_snapshot(
    path: pathlib.Path,
) -> Dict[Tuple[str, str], int]:
    snapshot: Dict[Tuple[str, str], int] = {}
    if not path.exists():
        return snapshot
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            try:
                snapshot[(parts[0], parts[1])] = int(parts[2])
            except ValueError:
                continue
    return snapshot


def _build_snapshot_prefix_fragment_support_index(
    mapping: Dict[Tuple[str, str], int],
    previous_snapshot: Dict[Tuple[str, str], int],
) -> Dict[str, List[Tuple[str, int]]]:
    """
    Index longer terms that can explain a shorter snapshot row as a stale
    generated prefix fragment.  The index is used only as evidence while
    restoring old rows; it does not synthesize any exact dictionary entry.
    """
    combined: Dict[Tuple[str, str], int] = {}
    combined.update(previous_snapshot)
    combined.update(mapping)

    support_index: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in combined.items():
        text_len = _cjk_len(text)
        if weight <= 0 or text_len < 4 or not CJK_FULL_RE.fullmatch(text):
            continue

        for prefix_len in range(3, min(4, text_len - 1) + 1):
            prefix_text = text[:prefix_len]
            support_index.setdefault(prefix_text, []).append((pinyin, weight))

    return support_index


def _is_low_signal_snapshot_prefix_fragment(
    pinyin: str,
    text: str,
    weight: int,
    prefix_fragment_support_index: Dict[str, List[Tuple[str, int]]],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    wiki_augmented_terms: Set[str] | None,
) -> bool:
    if not _has_low_weight_longer_prefix_fragment_structure(
        pinyin,
        text,
        weight,
        prefix_fragment_support_index,
    ):
        return False

    usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
    source_hits = max(0, source_hits_map.get(text, 0))
    pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
    jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
    wiki_support = _has_effective_wiki_support(
        text,
        wiki_titles,
        pageview_score=pageview_score,
        source_hits=source_hits,
        wiki_augmented_terms=wiki_augmented_terms,
    )

    return (
        usage_score < 0.16
        and jieba_direct_score < 0.16
        and source_hits <= 2
        and pageview_score < 0.08
        and not wiki_support
    )


def _has_low_weight_longer_prefix_fragment_structure(
    pinyin: str,
    text: str,
    weight: int,
    prefix_fragment_support_index: Dict[str, List[Tuple[str, int]]],
) -> bool:
    text_len = _cjk_len(text)
    if (
        weight >= 360
        or text_len < 3
        or text_len > 4
        or not CJK_FULL_RE.fullmatch(text)
    ):
        return False

    support_entries = prefix_fragment_support_index.get(text)
    if not support_entries:
        return False

    for support_pinyin, support_weight in support_entries:
        if (
            support_pinyin.startswith(pinyin)
            and len(support_pinyin) > len(pinyin)
            and support_weight >= max(420, weight + 240)
        ):
            return True

    return False


def _filter_low_signal_prefix_fragment_entries(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float],
    wiki_titles: Set[str],
    wiki_augmented_terms: Set[str] | None,
    stats_prefix: str,
    respect_source_signal: bool = True,
) -> Dict[str, int]:
    stats = {
        f"{stats_prefix}_prefix_fragment_entries_removed": 0,
    }
    if not mapping:
        return stats

    support_index = _build_snapshot_prefix_fragment_support_index(mapping, {})
    best_bucket_weight: Dict[str, int] = {}
    for (pinyin, _text), weight in mapping.items():
        best_bucket_weight[pinyin] = max(best_bucket_weight.get(pinyin, 0), weight)

    to_drop: List[Tuple[str, str]] = []
    for (pinyin, text), weight in mapping.items():
        if best_bucket_weight.get(pinyin, 0) < max(720, weight * 3):
            continue
        if not _has_low_weight_longer_prefix_fragment_structure(
            pinyin,
            text,
            weight,
            support_index,
        ):
            continue
        if respect_source_signal and (
            not _is_low_signal_snapshot_prefix_fragment(
                pinyin,
                text,
                weight,
                support_index,
                usage_score_map,
                source_hits_map,
                pageviews_signal_map,
                jieba_direct_signal_map,
                wiki_titles,
                wiki_augmented_terms,
            )
        ):
            continue
        to_drop.append((pinyin, text))

    for key in to_drop:
        if key in mapping:
            del mapping[key]
            stats[f"{stats_prefix}_prefix_fragment_entries_removed"] += 1

    return stats


def _restore_missing_texts_from_snapshot(
    mapping: Dict[Tuple[str, str], int],
    previous_snapshot: Dict[Tuple[str, str], int],
    explicit_drop_terms: Set[str],
    stats_prefix: str,
    snapshot_restore_block_terms: Set[str] | None = None,
    usage_score_map: Dict[str, float] | None = None,
    source_hits_map: Dict[str, int] | None = None,
    pageviews_signal_map: Dict[str, float] | None = None,
    jieba_direct_signal_map: Dict[str, float] | None = None,
    jieba_pos_map: Dict[str, str] | None = None,
    char_frequency_prior: Dict[str, float] | None = None,
    wiki_titles: Set[str] | None = None,
    wiki_augmented_terms: Set[str] | None = None,
    require_current_signal: bool = False,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    snapshot_restore_block_terms = snapshot_restore_block_terms or set()
    usage_score_map = usage_score_map or {}
    source_hits_map = source_hits_map or {}
    pageviews_signal_map = pageviews_signal_map or {}
    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    wiki_titles = wiki_titles or set()
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)
    stats = {
        f"{stats_prefix}_snapshot_rows_considered": len(previous_snapshot),
        f"{stats_prefix}_snapshot_rows_restored": 0,
        f"{stats_prefix}_snapshot_texts_restored": 0,
        f"{stats_prefix}_snapshot_rows_skipped_explicit_drop": 0,
        f"{stats_prefix}_snapshot_rows_skipped_blocked_prefix": 0,
        f"{stats_prefix}_snapshot_rows_skipped_prefix_fragment": 0,
        f"{stats_prefix}_snapshot_rows_skipped_low_signal_risk": 0,
        f"{stats_prefix}_snapshot_rows_skipped_no_current_signal": 0,
    }
    if not previous_snapshot:
        return mapping, stats

    restored = dict(mapping)
    current_texts = {text for _pinyin, text in restored.keys()}
    prefix_fragment_support_index = _build_snapshot_prefix_fragment_support_index(
        mapping,
        previous_snapshot,
    )
    restored_texts: Set[str] = set()
    for key, weight in previous_snapshot.items():
        _pinyin, text = key
        if len(text) > 1 and _is_explicit_multi_char_drop_text(text):
            stats[f"{stats_prefix}_snapshot_rows_skipped_explicit_drop"] += 1
            continue
        if len(text) > 1 and text in snapshot_restore_block_terms:
            stats[f"{stats_prefix}_snapshot_rows_skipped_blocked_prefix"] += 1
            continue
        if len(text) > 1 and _is_unsafe_derived_prefix_text(text):
            usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            source_hits = max(0, source_hits_map.get(text, 0))
            pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
            jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
            if (
                usage_score < 0.08
                and jieba_direct_score < 0.05
                and source_hits <= 0
                and pageview_score < 0.02
            ):
                stats[f"{stats_prefix}_snapshot_rows_skipped_prefix_fragment"] += 1
                continue
        if text in current_texts:
            continue
        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = max(0, source_hits_map.get(text, 0))
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        wiki_support = _has_effective_wiki_support(
            text,
            wiki_titles,
            pageview_score=pageview_score,
            source_hits=source_hits,
            wiki_augmented_terms=wiki_augmented_terms,
        )
        has_current_signal = (
            len(text) <= 1
            or text in wiki_augmented_terms
            or source_hits >= 2
            or usage_score >= 0.08
            or jieba_direct_score >= 0.08
            or pageview_score >= 0.03
            or (
                source_hits >= 1
                and (
                    usage_score >= 0.04
                    or jieba_direct_score >= 0.04
                    or pageview_score >= 0.01
                )
            )
        )
        if require_current_signal and not has_current_signal:
            stats[f"{stats_prefix}_snapshot_rows_skipped_no_current_signal"] += 1
            continue
        if len(text) > 1 and _is_low_signal_snapshot_prefix_fragment(
            _pinyin,
            text,
            weight,
            prefix_fragment_support_index,
            usage_score_map,
            source_hits_map,
            pageviews_signal_map,
            jieba_direct_signal_map,
            wiki_titles,
            wiki_augmented_terms,
        ):
            stats[f"{stats_prefix}_snapshot_rows_skipped_prefix_fragment"] += 1
            continue
        if len(text) > 1 and weight >= 900:
            pos_tag = jieba_pos_map.get(text, "")
            char_score = _compute_text_single_char_prior(text, char_prior)
            modernity_risk = _compute_low_signal_modernity_risk(
                text,
                usage_score=usage_score,
                source_hits=source_hits,
                pageview_score=pageview_score,
                jieba_direct_score=jieba_direct_score,
                wiki_support=wiki_support,
                pos_tag=pos_tag,
                char_score=char_score,
                min_char_prior=_compute_min_char_prior(text, char_prior),
                looks_like_person_name=False,
                looks_like_place_name=False,
                looks_like_literary_term=False,
                looks_like_written_tail_term=False,
            )
            if (
                usage_score < 0.04
                and jieba_direct_score < 0.04
                and source_hits <= 0
                and pageview_score < 0.02
                and not wiki_support
                and modernity_risk >= 180
            ):
                stats[f"{stats_prefix}_snapshot_rows_skipped_low_signal_risk"] += 1
                continue
        restored[key] = weight
        current_texts.add(text)
        restored_texts.add(text)
        stats[f"{stats_prefix}_snapshot_rows_restored"] += 1

    stats[f"{stats_prefix}_snapshot_texts_restored"] = len(restored_texts)
    return restored, stats


def _preserve_existing_unihan_single_char_weights(
    mapping: Dict[Tuple[str, str], int],
    previous_snapshot: Dict[Tuple[str, str], int],
    stats_prefix: str,
) -> Dict[str, int]:
    """Keep mature Unihan rows stable across unrelated phrase additions.

    Phrase support can still add a missing character or reading. Reweighting an
    existing row is explicit because a small curated phrase batch must not
    reshuffle an entire same-pinyin bucket.
    """
    stats = {
        f"{stats_prefix}_existing_single_char_rows_considered": 0,
        f"{stats_prefix}_existing_single_char_weights_preserved": 0,
    }
    if not mapping or not previous_snapshot:
        return stats

    for key, previous_weight in previous_snapshot.items():
        _pinyin, text = key
        if _cjk_len(text) != 1 or key not in mapping:
            continue

        stats[f"{stats_prefix}_existing_single_char_rows_considered"] += 1
        if mapping[key] == previous_weight:
            continue

        mapping[key] = previous_weight
        stats[f"{stats_prefix}_existing_single_char_weights_preserved"] += 1

    return stats


def _build_curated_daily_prefix_restore_blocklist(
    curated_entries: List[Tuple[str, str, float, str]],
    use_traditional: bool,
) -> Set[str]:
    """
    Snapshot restore is useful for stable releases, but it must not undo a
    deliberate decision to keep only the full curated phrase. Prefixes of new
    daily phrases should survive only if the current build produces them again.
    """
    blocked: Set[str] = set()
    for sc_word, tc_word, _usage_score, _explicit_pinyin in curated_entries:
        word = tc_word if use_traditional and tc_word else sc_word
        word_len = _cjk_len(word)
        if word_len <= 2:
            continue
        for prefix_len in range(2, min(4, word_len - 1) + 1):
            prefix = word[:prefix_len]
            if CJK_FULL_RE.fullmatch(prefix) and not _is_unsafe_derived_prefix_text(prefix):
                blocked.add(prefix)
    return blocked


LM_CORPUS_SENTENCE_SPLIT_RE = re.compile(
    r"[\s\u3000\u3001\u3002\uff0c\uff01\uff1f\uff1b\uff1a,.!?;:"
    r"\uff08\uff09()\[\]\u3010\u3011\u300a\u300b"
    r"\u201c\u201d\u2018\u2019\u2026\u2014\-/\\|]+"
)

LM_CORPUS_ASCII_RE = re.compile(r"[A-Za-z0-9]")
LM_CORPUS_CJK_RUN_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002A6DF]+"
)
LM_CORPUS_CHUNK_OVERLAP = 4

LM_FUNCTION_SINGLE_CHARS: Set[str] = set(
    "的一是在我你他她它了着也都就不没很还又再才把被给让向从和或与及而并"
    "这那哪有无来去上下载里内外中前后大小游戏多"
)

# Productive one-character heads can form useful 1+2 short candidates when
# corpus evidence is independently strong. They remain subject to exact-entry,
# homophone, association, and concentrated-context guards below.
LM_PRODUCTIVE_SINGLE_PREFIX_CHARS: Set[str] = set(
    "要可不没沒别別未无無就还還再又也都只才正已将將仍会會能该該需想敢肯"
    "很更最太挺稍较較"
)

LM_PRODUCTIVE_PREDICATE_ONLY_HEADS: Set[str] = set(
    "可会會能敢肯很更最太挺稍较較"
)

# Keep rigorously validated productive 1+2 runner-ups in a distinct low band.
# This lets the dedicated selector retain a useful same-pinyin alternative
# without admitting the general population of weak runner-up paths.
LM_STRONG_PRODUCTIVE_RUNNER_UP_WEIGHT = 400
LM_STRONG_PRODUCTIVE_RUNNER_UP_MIN_DIRECT_COUNT = 7
LM_STRONG_PRODUCTIVE_RUNNER_UP_MIN_DIRECT_SOURCES = 7

# Adjacent single-character transitions are intentionally much stricter than
# productive 1+2/2+1 pairs. They are learned offline only and never expanded
# from the runtime homophone Cartesian product.
LM_STRONG_SINGLE_PAIR_MIN_COUNT = 12
LM_STRONG_SINGLE_PAIR_MIN_SOURCES = 5
LM_STRONG_SINGLE_PAIR_RUNNER_UP_MIN_COUNT = 36
LM_STRONG_SINGLE_PAIR_RUNNER_UP_MIN_SOURCES = 10


def _is_productive_predicate_pos(pos_tag: str) -> bool:
    normalized = pos_tag.strip().lower()
    return (
        normalized.startswith(("v", "a", "z"))
        or normalized in {"d", "i", "l"}
    )


def _decode_lm_corpus_file(path: pathlib.Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _iter_lm_json_record_texts(record: object) -> List[str]:
    texts: List[str] = []
    if not isinstance(record, dict):
        return texts

    messages = record.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                texts.append(content)
        return texts

    for key in ("text", "content"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            texts.append(value)
            break
    return texts


def _new_lm_corpus_stats() -> Dict[str, int]:
    return {
        "lm_corpus_files": 0,
        "lm_corpus_fragments": 0,
        "lm_corpus_accepted": 0,
        "lm_corpus_rejected_ascii_or_digit": 0,
        "lm_corpus_rejected_non_cjk": 0,
        "lm_corpus_rejected_length": 0,
        "lm_corpus_mixed_ascii_or_digit": 0,
        "lm_corpus_salvaged_mixed_fragments": 0,
        "lm_corpus_split_long_runs": 0,
        "lm_corpus_text_files": 0,
        "lm_corpus_jsonl_files": 0,
        "lm_corpus_jsonl_records": 0,
        "lm_corpus_jsonl_malformed": 0,
        "lm_corpus_jsonl_skipped_holdout_files": 0,
    }


def _stream_lm_corpus_sentences(
    corpus_dir: pathlib.Path,
    *,
    min_units: int,
    max_units: int,
    convert_text,
    stats: Dict[str, int] | None = None,
) -> Iterator[Tuple[str, str]]:
    active_stats = stats if stats is not None else _new_lm_corpus_stats()
    if not corpus_dir.exists():
        active_stats["lm_corpus_missing_dir"] = 1
        return

    def _iter_fragments(
        raw_text: str,
        source_name: str,
        seen_in_record: Set[str] | None = None,
    ) -> Iterator[Tuple[str, str]]:
        for raw_fragment in LM_CORPUS_SENTENCE_SPLIT_RE.split(raw_text):
            fragment = raw_fragment.strip()
            if not fragment:
                continue
            active_stats["lm_corpus_fragments"] += 1
            has_ascii_or_digit = LM_CORPUS_ASCII_RE.search(fragment) is not None
            if has_ascii_or_digit:
                active_stats["lm_corpus_mixed_ascii_or_digit"] += 1

            cjk_runs = LM_CORPUS_CJK_RUN_RE.findall(fragment)
            if not cjk_runs:
                if has_ascii_or_digit:
                    active_stats["lm_corpus_rejected_ascii_or_digit"] += 1
                active_stats["lm_corpus_rejected_non_cjk"] += 1
                continue
            if len(cjk_runs) != 1 or cjk_runs[0] != fragment:
                active_stats["lm_corpus_salvaged_mixed_fragments"] += 1

            for cjk_run in cjk_runs:
                run_units = _cjk_len(cjk_run)
                if run_units < min_units:
                    active_stats["lm_corpus_rejected_length"] += 1
                    continue

                if run_units <= max_units:
                    chunk_starts: Iterable[int] = (0,)
                else:
                    active_stats["lm_corpus_split_long_runs"] += 1
                    step = max(1, max_units - LM_CORPUS_CHUNK_OVERLAP)
                    chunk_starts = (
                        start
                        for start in range(0, run_units, step)
                        if run_units - start >= min_units
                    )

                for start in chunk_starts:
                    chunk = cjk_run[start : start + max_units]
                    normalized = convert_text(chunk)
                    if not normalized or not CJK_FULL_RE.fullmatch(normalized):
                        active_stats["lm_corpus_rejected_non_cjk"] += 1
                        continue
                    if seen_in_record is not None:
                        if normalized in seen_in_record:
                            continue
                        seen_in_record.add(normalized)
                    active_stats["lm_corpus_accepted"] += 1
                    yield normalized, source_name

    for path in sorted(corpus_dir.glob("*.txt")):
        active_stats["lm_corpus_files"] += 1
        active_stats["lm_corpus_text_files"] += 1
        text = _decode_lm_corpus_file(path)
        yield from _iter_fragments(text, path.name)

    holdout_names = {"dev.jsonl", "test.jsonl", "validation.jsonl"}
    for path in sorted(corpus_dir.rglob("*.jsonl")):
        if path.name.lower() in holdout_names:
            active_stats["lm_corpus_jsonl_skipped_holdout_files"] += 1
            continue
        active_stats["lm_corpus_files"] += 1
        active_stats["lm_corpus_jsonl_files"] += 1
        relative_name = path.relative_to(corpus_dir).as_posix()
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    active_stats["lm_corpus_jsonl_malformed"] += 1
                    continue
                active_stats["lm_corpus_jsonl_records"] += 1
                record_source = ""
                if isinstance(record, dict):
                    for key in ("source", "id", "doc_id"):
                        value = record.get(key)
                        if isinstance(value, str) and value.strip():
                            record_source = value.strip()
                            break
                if not record_source:
                    record_source = str(line_number)
                source_name = f"{relative_name}:{record_source}"
                seen_in_record: Set[str] = set()
                for record_text in _iter_lm_json_record_texts(record):
                    yield from _iter_fragments(
                        record_text,
                        source_name,
                        seen_in_record,
                    )


def _iter_lm_corpus_sentences(
    corpus_dir: pathlib.Path,
    *,
    min_units: int,
    max_units: int,
    convert_text,
) -> Tuple[List[Tuple[str, str]], Dict[str, int]]:
    stats = _new_lm_corpus_stats()
    sentences = list(
        _stream_lm_corpus_sentences(
            corpus_dir,
            min_units=min_units,
            max_units=max_units,
            convert_text=convert_text,
            stats=stats,
        )
    )
    return sentences, stats


def _build_lm_entry_indexes(
    mapping: Dict[Tuple[str, str], int],
    *,
    max_segment_units: int,
    single_char_readings_map: Dict[str, Set[str]] | None = None,
    single_char_default_pinyin_map: Dict[str, str] | None = None,
    single_char_source_rank_map: Dict[Tuple[str, str], int] | None = None,
    single_char_pinlu_detail_map: Dict[Tuple[str, str], int] | None = None,
    char_frequency_prior: Dict[str, float] | None = None,
) -> Tuple[Dict[str, List[Tuple[str, str, int, int, int]]], Dict[Tuple[str, str], Tuple[int, int]]]:
    entry_weight_by_key: Dict[Tuple[str, str], int] = {}
    by_pinyin: Dict[str, List[Tuple[str, int]]] = {}
    entries_by_text: Dict[str, List[Tuple[str, str, int, int, int]]] = {}
    rank_info: Dict[Tuple[str, str], Tuple[int, int]] = {}
    single_char_readings_map = single_char_readings_map or {}
    single_char_default_pinyin_map = single_char_default_pinyin_map or {}
    single_char_source_rank_map = single_char_source_rank_map or {}
    single_char_pinlu_detail_map = single_char_pinlu_detail_map or {}
    char_frequency_prior = char_frequency_prior or {}

    for (pinyin, text), weight in mapping.items():
        normalized_pinyin = _normalize_compact_pinyin_key(pinyin)
        text_units = _cjk_len(text)
        if weight <= 0 or not normalized_pinyin or text_units <= 0 or text_units > max_segment_units:
            continue
        if not CJK_FULL_RE.fullmatch(text):
            continue
        key = (normalized_pinyin, text)
        entry_weight_by_key[key] = max(entry_weight_by_key.get(key, 0), weight)

    # `dict_clean` is a word dictionary and usually does not contain all
    # single-character readings. LM training still needs single-character
    # fallback to segment corpus sentences with the same broad capability as
    # the engine. These synthetic single-character entries are used only for
    # training segmentation; transition emission still filters non-function
    # single characters.
    for ch, readings in single_char_readings_map.items():
        if _cjk_len(ch) != 1 or not CJK_FULL_RE.fullmatch(ch):
            continue
        char_prior = min(1.0, max(0.0, char_frequency_prior.get(ch, 0.0)))
        if ch in LM_FUNCTION_SINGLE_CHARS:
            synthetic_weight = max(360, int(round(420 + char_prior * 260)))
        else:
            synthetic_weight = max(96, int(round(130 + char_prior * 180)))
        ordered_readings = _candidate_unihan_readings_for_char(
            ch,
            single_char_default_pinyin_map,
            single_char_readings_map,
            single_char_source_rank_map,
            single_char_pinlu_detail_map,
        )
        if not ordered_readings:
            ordered_readings = sorted(readings)
        for reading_rank, raw_pinyin in enumerate(ordered_readings):
            pinyin = _normalize_compact_pinyin_key(raw_pinyin)
            if not pinyin:
                continue
            key = (pinyin, ch)
            reading_weight = max(1, synthetic_weight - min(96, reading_rank * 24))
            entry_weight_by_key[key] = max(
                entry_weight_by_key.get(key, 0),
                reading_weight,
            )

    for (pinyin, text), weight in entry_weight_by_key.items():
        by_pinyin.setdefault(pinyin, []).append((text, weight))

    for pinyin, items in by_pinyin.items():
        items.sort(key=lambda item: (-item[1], item[0]))
        top_weight = items[0][1]
        for rank, (text, weight) in enumerate(items, start=1):
            rank_info[(pinyin, text)] = (rank, top_weight)

    for (pinyin, text), weight in entry_weight_by_key.items():
        info = rank_info.get((pinyin, text))
        if info is None:
            continue
        exact_rank, top_weight = info
        entries_by_text.setdefault(text, []).append((pinyin, text, weight, exact_rank, top_weight))

    for text, entries in entries_by_text.items():
        entries.sort(key=lambda item: (-item[2], item[3], item[0]))
        entries_by_text[text] = entries[:4]
    return entries_by_text, rank_info


def _segment_lm_sentence(
    sentence: str,
    entries_by_text: Dict[str, List[Tuple[str, str, int, int, int]]],
    *,
    max_segment_units: int,
) -> List[Tuple[str, str, int, int, int]] | None:
    text_len = len(sentence)
    best_score: List[int] = [-10**12] * (text_len + 1)
    best_edge: List[Tuple[int, Tuple[str, str, int, int, int]] | None] = [None] * (text_len + 1)
    best_score[0] = 0

    for start in range(text_len):
        if best_score[start] <= -10**11:
            continue
        for end in range(start + 1, min(text_len, start + max_segment_units) + 1):
            text = sentence[start:end]
            entries = entries_by_text.get(text)
            if not entries:
                continue
            units = end - start
            for entry in entries[:2]:
                pinyin, _text, weight, exact_rank, top_weight = entry
                del pinyin
                score = best_score[start]
                score += min(1200, max(1, weight))
                score += units * units * 210
                if units >= 2:
                    score += 520
                if units >= 3:
                    score += 160
                if units == 1:
                    score -= 300
                if exact_rank > 1:
                    score -= min(420, (exact_rank - 1) * 55)
                if top_weight > weight:
                    score -= min(480, (top_weight - weight) // 2)
                if score > best_score[end]:
                    best_score[end] = score
                    best_edge[end] = (start, entry)

    if best_edge[text_len] is None:
        return None

    output: List[Tuple[str, str, int, int, int]] = []
    pos = text_len
    while pos > 0:
        edge = best_edge[pos]
        if edge is None:
            return None
        start, entry = edge
        output.append(entry)
        pos = start
    output.reverse()
    return output


def _segment_lm_sentence_nbest(
    sentence: str,
    entries_by_text: Dict[str, List[Tuple[str, str, int, int, int]]],
    *,
    max_segment_units: int,
    path_limit: int = 5,
    state_limit: int = 15,
    max_score_gap: int = 1100,
    confidence_temperature: float = 700.0,
) -> List[Tuple[List[Tuple[str, str, int, int, int]], float]]:
    """Return a small, confidence-weighted set of lexical segmentations.

    The ordinary segmenter intentionally keeps one deterministic path.  LM
    training needs a little more boundary diversity, but an unbounded lattice
    would multiply both memory and noisy transition counts.  This decoder
    therefore retains at most ``state_limit`` paths at every character
    boundary and emits no more than ``path_limit`` near-best paths.
    """

    text_len = len(sentence)
    states: List[
        List[Tuple[int, Tuple[Tuple[str, str, int, int, int], ...]]]
    ] = [[] for _ in range(text_len + 1)]
    states[0] = [(0, tuple())]

    def edge_score(
        entry: Tuple[str, str, int, int, int], units: int
    ) -> int:
        _pinyin, _text, weight, exact_rank, top_weight = entry
        score = min(1200, max(1, weight))
        score += units * units * 210
        if units >= 2:
            score += 520
        if units >= 3:
            score += 160
        if units == 1:
            score -= 300
        if exact_rank > 1:
            score -= min(420, (exact_rank - 1) * 55)
        if top_weight > weight:
            score -= min(480, (top_weight - weight) // 2)
        return score

    def prune(
        values: List[
            Tuple[int, Tuple[Tuple[str, str, int, int, int], ...]]
        ],
    ) -> List[Tuple[int, Tuple[Tuple[str, str, int, int, int], ...]]]:
        best_by_signature: Dict[
            Tuple[Tuple[str, str], ...],
            Tuple[int, Tuple[Tuple[str, str, int, int, int], ...]],
        ] = {}
        for score, path in values:
            signature = tuple((entry[0], entry[1]) for entry in path)
            previous = best_by_signature.get(signature)
            if previous is None or score > previous[0]:
                best_by_signature[signature] = (score, path)
        ranked = sorted(
            best_by_signature.values(),
            key=lambda item: (
                -item[0],
                tuple((entry[1], entry[0]) for entry in item[1]),
            ),
        )
        return ranked[: max(path_limit, state_limit)]

    for start in range(text_len):
        if not states[start]:
            continue
        touched_destinations: Set[int] = set()
        for end in range(
            start + 1, min(text_len, start + max_segment_units) + 1
        ):
            text = sentence[start:end]
            entries = entries_by_text.get(text)
            if not entries:
                continue
            units = end - start
            for entry in entries[:2]:
                increment = edge_score(entry, units)
                for state_score, state_path in states[start]:
                    states[end].append(
                        (state_score + increment, state_path + (entry,))
                    )
            touched_destinations.add(end)
        for destination in touched_destinations:
            if len(states[destination]) > state_limit:
                states[destination] = prune(states[destination])

    if not states[text_len]:
        return []
    ranked_final = prune(states[text_len])
    best_score = ranked_final[0][0]
    output: List[
        Tuple[List[Tuple[str, str, int, int, int]], float]
    ] = []
    for score, path in ranked_final:
        score_gap = best_score - score
        if score_gap > max_score_gap:
            continue
        confidence = math.exp(
            -max(0, score_gap) / max(1.0, confidence_temperature)
        )
        if output and confidence < 0.20:
            continue
        output.append((list(path), confidence))
        if len(output) >= path_limit:
            break
    return output


def _lm_segment_allowed(
    entry: Tuple[str, str, int, int, int],
    *,
    max_exact_rank: int,
    max_top_gap: int,
    min_single_weight: int,
    min_multi_weight: int,
) -> bool:
    _pinyin, text, weight, exact_rank, top_weight = entry
    text_len = _cjk_len(text)
    if exact_rank > max_exact_rank:
        return False
    if top_weight - weight > max_top_gap:
        return False
    if text_len <= 1:
        return text in LM_FUNCTION_SINGLE_CHARS and weight >= min_single_weight
    return weight >= min_multi_weight


def _collect_lm_transition_priors(
    sentences: Iterable[Tuple[str, str]],
    entries_by_text: Dict[str, List[Tuple[str, str, int, int, int]]],
    *,
    max_segment_units: int = 4,
    min_bigram_count: int = 5,
    min_trigram_count: int = 4,
    max_exact_rank: int = 4,
    max_top_gap: int = 360,
    min_single_weight: int = 300,
    min_multi_weight: int = 180,
    max_weight: int = 520,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    # Keep all statistics for one transition in one compact record. N-best
    # segmentation produces millions of distinct windows; separate dictionaries
    # and per-key source sets multiply Python object overhead without adding
    # information. Record fields are count, source mask, weighted lexical sum,
    # maximum exact rank, maximum multi-character rank and maximum weight gap.
    transition_stats: Dict[str, List[float | int]] = {}
    segment_counts: Dict[str, float] = {}
    current_source: str | None = None
    current_source_keys: Set[str] = set()
    spill_limit = 250_000
    total_windows = 0.0
    spill_file = tempfile.NamedTemporaryFile(
        prefix="cassotis_lm_transition_", suffix=".sqlite3", delete=False
    )
    spill_path = pathlib.Path(spill_file.name)
    spill_file.close()
    spill_db = sqlite3.connect(str(spill_path))
    spill_db.execute("PRAGMA journal_mode=OFF")
    spill_db.execute("PRAGMA synchronous=OFF")
    spill_db.execute("PRAGMA temp_store=FILE")
    spill_db.execute("PRAGMA cache_size=-131072")
    spill_db.execute(
        """
        CREATE TABLE transition_stats (
            query TEXT NOT NULL,
            path TEXT NOT NULL,
            count REAL NOT NULL,
            source_count INTEGER NOT NULL,
            weight_sum REAL NOT NULL,
            rank_max INTEGER NOT NULL,
            multi_rank_max INTEGER NOT NULL,
            gap_max INTEGER NOT NULL,
            PRIMARY KEY(query, path)
        ) WITHOUT ROWID
        """
    )
    stats: Dict[str, int] = {
        "lm_corpus_segmented": 0,
        "lm_corpus_segmentations": 0,
        "lm_corpus_unsegmented": 0,
        "lm_corpus_bigram_windows": 0,
        "lm_corpus_trigram_windows": 0,
        "lm_corpus_priors_emitted": 0,
        "lm_corpus_priors_skipped_query_rank": 0,
        "lm_corpus_priors_skipped_weak_runner_up": 0,
        "lm_corpus_priors_skipped_weak_single": 0,
        "lm_corpus_priors_skipped_ambiguous_function_bigram": 0,
    }

    def _window_allowed(window: List[Tuple[str, str, int, int, int]]) -> bool:
        if len(window) < 2:
            return False
        single_count = 0
        for entry in window:
            if not _lm_segment_allowed(
                entry,
                max_exact_rank=max_exact_rank,
                max_top_gap=max_top_gap,
                min_single_weight=min_single_weight,
                min_multi_weight=min_multi_weight,
            ):
                return False
            if _cjk_len(entry[1]) <= 1:
                single_count += 1
        if single_count >= len(window):
            return False
        if single_count > 1:
            return False
        return True

    def _window_emittable(segments: List[str]) -> bool:
        single_segments = [text for text in segments if _cjk_len(text) <= 1]
        if len(single_segments) > 1:
            return False
        return all(text in LM_FUNCTION_SINGLE_CHARS for text in single_segments)

    def _flush_transition_stats() -> None:
        if not transition_stats:
            return

        def _rows() -> Iterator[Tuple[object, ...]]:
            for packed_key, record in transition_stats.items():
                query, _separator, path = packed_key.partition("\0")
                yield (
                    query,
                    path,
                    float(record[0]),
                    int(record[1]),
                    float(record[2]),
                    int(record[3]),
                    int(record[4]),
                    int(record[5]),
                )

        spill_db.executemany(
            """
            INSERT INTO transition_stats (
                query, path, count, source_count, weight_sum,
                rank_max, multi_rank_max, gap_max
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(query, path) DO UPDATE SET
                count = count + excluded.count,
                source_count = MIN(3, source_count + excluded.source_count),
                weight_sum = weight_sum + excluded.weight_sum,
                rank_max = MAX(rank_max, excluded.rank_max),
                multi_rank_max = MAX(multi_rank_max, excluded.multi_rank_max),
                gap_max = MAX(gap_max, excluded.gap_max)
            """,
            _rows(),
        )
        spill_db.commit()
        transition_stats.clear()

    def _finish_source() -> None:
        if not current_source_keys:
            return
        for packed_key in current_source_keys:
            record = transition_stats.get(packed_key)
            if record is None:
                record = [0.0, 0, 0.0, 0, 0, 0]
                transition_stats[packed_key] = record
            record[1] = min(3, int(record[1]) + 1)
        current_source_keys.clear()
        if len(transition_stats) >= spill_limit:
            _flush_transition_stats()

    for sentence, source_name in sentences:
        if current_source is None:
            current_source = source_name
        elif source_name != current_source:
            _finish_source()
            current_source = source_name
        segmentation_paths = _segment_lm_sentence_nbest(
            sentence,
            entries_by_text,
            max_segment_units=max_segment_units,
        )
        if not segmentation_paths:
            stats["lm_corpus_unsegmented"] += 1
            continue
        stats["lm_corpus_segmented"] += 1
        stats["lm_corpus_segmentations"] += len(segmentation_paths)
        for segments, path_confidence in segmentation_paths:
            for _pinyin, text, _weight, _exact_rank, _top_weight in segments:
                segment_counts[text] = (
                    segment_counts.get(text, 0.0) + path_confidence
                )
            for start in range(len(segments)):
                for window_size in (2, 3):
                    window = segments[start : start + window_size]
                    if len(window) != window_size:
                        continue
                    if not _window_allowed(window):
                        continue
                    query = "".join(item[0] for item in window)
                    path = QUERY_PATH_FILE_SEPARATOR.join(
                        item[1] for item in window
                    )
                    packed_key = query + "\0" + path
                    record = transition_stats.get(packed_key)
                    if record is None:
                        record = [0.0, 0, 0.0, 0, 0, 0]
                        transition_stats[packed_key] = record
                    record[0] = float(record[0]) + path_confidence
                    record[2] = float(record[2]) + path_confidence * sum(
                        item[2] for item in window
                    )
                    record[3] = max(
                        int(record[3]), *(item[3] for item in window)
                    )
                    multi_ranks = [
                        item[3] for item in window if _cjk_len(item[1]) > 1
                    ]
                    if multi_ranks:
                        record[4] = max(int(record[4]), *multi_ranks)
                    record[5] = max(
                        int(record[5]),
                        *(item[4] - item[2] for item in window),
                    )
                    current_source_keys.add(packed_key)
                    total_windows += path_confidence
                    if len(transition_stats) >= spill_limit:
                        _flush_transition_stats()
                    if window_size == 2:
                        stats["lm_corpus_bigram_windows"] += 1
                    else:
                        stats["lm_corpus_trigram_windows"] += 1

    _finish_source()
    _flush_transition_stats()

    priors: Dict[Tuple[str, str], int] = {}
    total_windows = max(1.0, total_windows)

    def _emit_query_rows(query: str, rows: List[Tuple[object, ...]]) -> None:
        if not rows:
            return
        query_total_count = max(1.0, sum(float(row[2]) for row in rows))
        best_path = str(rows[0][1])
        best_count = float(rows[0][2])
        second_path = str(rows[1][1]) if len(rows) > 1 else ""
        second_count = float(rows[1][2]) if len(rows) > 1 else 0.0

        for row in rows:
            path = str(row[1])
            count = float(row[2])
            source_count = int(row[3])
            segments = path.split(QUERY_PATH_FILE_SEPARATOR)
            if not _window_emittable(segments):
                continue
            min_count = (
                min_trigram_count if len(segments) >= 3 else min_bigram_count
            )
            if count < min_count:
                continue
            if source_count < 2 and count < (min_count + 4):
                continue

            if path == best_path:
                contender_rank = 1
                competitor_count = second_count
            elif path == second_path:
                contender_rank = 2
                competitor_count = best_count
            else:
                contender_rank = 3
                competitor_count = best_count
            query_share = count / query_total_count

            # Positive-only runtime bonuses require defensible evidence inside
            # the same pinyin bucket; weak homophone paths cannot be penalized.
            if contender_rank > 2:
                stats["lm_corpus_priors_skipped_query_rank"] += 1
                continue
            if contender_rank == 2 and (
                count < (min_count + 3) or count * 100 < best_count * 45
            ):
                stats["lm_corpus_priors_skipped_weak_runner_up"] += 1
                continue

            has_function_single = any(
                _cjk_len(text) <= 1 for text in segments
            )
            if has_function_single:
                if len(segments) == 2:
                    if int(row[6]) > 1:
                        stats[
                            "lm_corpus_priors_skipped_ambiguous_function_bigram"
                        ] += 1
                        continue
                    weak_single = (
                        source_count < 2
                        or count < max(8, min_count + 3)
                        or (
                            competitor_count > 0
                            and count * 100 < competitor_count * 70
                        )
                    )
                else:
                    weak_single = (
                        count < max(10, min_count + 6)
                        or (source_count < 2 and count < 16)
                        or (
                            competitor_count > 0
                            and count * 100 < competitor_count * 85
                        )
                    )
                if weak_single:
                    stats["lm_corpus_priors_skipped_weak_single"] += 1
                    continue

            segment_product = 1.0
            for text in segments:
                segment_product *= max(1.0, segment_counts.get(text, 1.0))
            pmi = math.log2(
                (count * total_windows) / max(1.0, segment_product)
            )
            avg_weight = float(row[4]) / max(1.0, count * len(segments))
            rank_penalty = max(0, int(row[5]) - 1) * 10
            gap_penalty = min(60, max(0, int(row[7])) // 8)
            dominance = math.log2((count + 2) / (competitor_count + 2))
            score = 72
            score += int(round(math.log2(count + 1) * 30))
            score += int(round(max(-1.0, min(5.0, pmi)) * 14))
            score += int(round(min(62.0, avg_weight * 0.026)))
            score += min(36, source_count * 12)
            score += int(round(query_share * 72))
            score += int(round(max(-1.5, min(4.0, dominance)) * 30))
            if contender_rank == 2:
                score -= 24
            score -= rank_penalty + gap_penalty
            if len(segments) >= 3:
                score += 18
            priors[(query, path)] = max(96, min(max_weight, score))

    try:
        cursor = spill_db.execute(
            """
            SELECT query, path, count, source_count, weight_sum,
                   rank_max, multi_rank_max, gap_max
            FROM transition_stats
            ORDER BY query, count DESC, path
            """
        )
        current_query = ""
        query_rows: List[Tuple[object, ...]] = []
        for row in cursor:
            query = str(row[0])
            if current_query and query != current_query:
                _emit_query_rows(current_query, query_rows)
                query_rows.clear()
            current_query = query
            query_rows.append(row)
        if current_query:
            _emit_query_rows(current_query, query_rows)
    finally:
        spill_db.close()
        spill_path.unlink(missing_ok=True)

    stats["lm_corpus_priors_emitted"] = len(priors)
    return priors, stats

def _collect_short_exact_pair_transition_priors(
    sentences: Iterable[Tuple[str, str]],
    entries_by_text: Dict[str, List[Tuple[str, str, int, int, int]]],
    *,
    second_pass_sentences: Iterable[Tuple[str, str]] | None = None,
    jieba_pos_map: Dict[str, str] | None = None,
    min_count: int = 4,
    min_single_source_count: int = 12,
    max_weight: int = 520,
    completion_evidence_out: Dict[
        Tuple[str, str], Tuple[int, int, int, int, int, int, float, float, int]
    ]
    | None = None,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    """Collect conservative exact pair transitions from short corpus spans.

    The general LM transition collector intentionally limits single-character
    bigrams to function words. Short-word prediction needs a separate channel
    for lexical 1+2/2+1 pairs and stronger direct evidence for 2+2/2+3/3+2
    pairs. Both sides still have to be exact dictionary entries and corpus
    evidence must dominate alternatives with the same pinyin, so this does not
    enable arbitrary word composition at runtime.
    """

    jieba_pos_map = jieba_pos_map or {}
    pair_layouts = ((3, 1), (3, 2), (4, 2), (5, 2), (5, 3))
    transition_counts: Dict[Tuple[str, str], int] = {}
    transition_source_counts: Dict[Tuple[str, str], int] = {}
    component_counts: Dict[str, int] = {}
    transition_rank_penalty: Dict[Tuple[str, str], int] = {}
    transition_gap_penalty: Dict[Tuple[str, str], int] = {}
    transition_left_contexts: Dict[Tuple[str, str], Dict[str, int]] = {}
    transition_right_contexts: Dict[Tuple[str, str], Dict[str, int]] = {}
    transition_exact_extension_count: Dict[Tuple[str, str], int] = {}
    transition_unextended_source_counts: Dict[Tuple[str, str], int] = {}
    transition_ambiguous_alternative_count: Dict[Tuple[str, str], int] = {}
    stats: Dict[str, int] = {
        "short_exact_pair_windows": 0,
        "short_exact_pair_viable_windows": 0,
        "short_exact_pair_priors_emitted": 0,
        "short_exact_pair_skipped_count": 0,
        "short_exact_pair_skipped_source_count": 0,
        "short_exact_pair_skipped_query_rank": 0,
        "short_exact_pair_skipped_weak_runner_up": 0,
        "short_exact_pair_skipped_weak_association": 0,
        "short_exact_pair_skipped_weak_medium_evidence": 0,
        "short_exact_pair_skipped_embedded_fragment": 0,
        "short_exact_pair_skipped_exact_extension": 0,
        "short_exact_pair_skipped_observed_homophone_alternative": 0,
        "short_exact_pair_productive_prefix_windows": 0,
        "short_exact_pair_productive_prefix_emitted": 0,
        "short_exact_pair_productive_prefix_weak_skipped": 0,
        "short_exact_pair_productive_prefix_extension_bypassed": 0,
        "short_exact_pair_productive_prefix_insufficient_direct_skipped": 0,
        "short_exact_pair_productive_prefix_named_tail_skipped": 0,
        "short_exact_pair_productive_prefix_nonpredicate_tail_skipped": 0,
        "short_exact_pair_productive_prefix_strong_runner_up_emitted": 0,
    }
    for total_units, split_at in pair_layouts:
        stats[f"short_exact_pair_{split_at}_{total_units - split_at}_windows"] = 0
        stats[f"short_exact_pair_{split_at}_{total_units - split_at}_viable"] = 0

    strong_multi_terms_by_pinyin: Dict[str, Set[str]] = {}
    for entries in entries_by_text.values():
        for pinyin, text, weight, _exact_rank, _top_weight in entries:
            if _cjk_len(text) <= 1 or weight < 500:
                continue
            strong_multi_terms_by_pinyin.setdefault(pinyin, set()).add(text)
    ambiguous_multi_pinyins = {
        pinyin
        for pinyin, texts in strong_multi_terms_by_pinyin.items()
        if len(texts) >= 2
    }

    def _best_viable_entry(
        text: str,
        *,
        single: bool,
        productive_tail: bool = False,
    ) -> Tuple[str, str, int, int, int] | None:
        entries = entries_by_text.get(text)
        if not entries:
            return None
        min_weight = 200 if single else 420
        max_exact_rank = 8 if single else 2
        max_top_gap = 300 if single else (480 if productive_tail else 240)
        for entry in entries:
            _pinyin, _text, weight, exact_rank, top_weight = entry
            if weight < min_weight or (
                max_exact_rank > 0 and exact_rank > max_exact_rank
            ):
                continue
            if top_weight - weight > max_top_gap:
                continue
            return entry
        return None

    def _evidence_requirements(key: Tuple[str, str]) -> Tuple[int, int]:
        segment_lengths = [
            _cjk_len(segment)
            for segment in key[1].split(QUERY_PATH_FILE_SEPARATOR)
        ]
        if 1 in segment_lengths:
            return min_count, 3
        if max(segment_lengths, default=0) >= 3:
            return max(10, min_count), 4
        return max(8, min_count), 4

    def _has_source_support(
        key: Tuple[str, str],
        count: int,
        source_count: int,
    ) -> bool:
        required_count, required_sources = _evidence_requirements(key)
        if count < required_count:
            return False
        segment_lengths = [
            _cjk_len(segment)
            for segment in key[1].split(QUERY_PATH_FILE_SEPARATOR)
        ]
        if 1 in segment_lengths and count == 4:
            # The new medium-confidence tier must be observed in four
            # independent documents. Repeated mentions inside one source do
            # not provide enough evidence to compose a new short candidate.
            return source_count >= 4
        if source_count >= required_sources:
            return True
        if source_count == 3:
            return count >= required_count + 4
        if source_count == 2:
            return count >= required_count + 8
        return count >= max(min_single_source_count, required_count + 14)

    current_source = ""
    current_source_keys: Set[Tuple[str, str]] = set()

    def _flush_source_keys() -> None:
        for source_key in current_source_keys:
            transition_source_counts[source_key] = min(
                min_single_source_count,
                transition_source_counts.get(source_key, 0) + 1,
            )
        current_source_keys.clear()

    for sentence, source_name in sentences:
        if source_name != current_source:
            if current_source:
                _flush_source_keys()
            current_source = source_name
        if len(sentence) < 3:
            continue
        for total_units, split_at in pair_layouts:
            if len(sentence) < total_units:
                continue
            layout_name = f"{split_at}_{total_units - split_at}"
            for start in range(len(sentence) - total_units + 1):
                text = sentence[start : start + total_units]
                stats["short_exact_pair_windows"] += 1
                stats[f"short_exact_pair_{layout_name}_windows"] += 1
                # A full exact term needs no composed transition.
                if text in entries_by_text:
                    continue
                if total_units == 3 and (
                    text[0] == text[1] or text[1] == text[2]
                ):
                    continue
                left_text = text[:split_at]
                right_text = text[split_at:]
                single_text = ""
                if len(left_text) == 1:
                    single_text = left_text
                elif len(right_text) == 1:
                    single_text = right_text
                productive_single_prefix = (
                    len(left_text) == 1
                    and len(right_text) == 2
                    and left_text in LM_PRODUCTIVE_SINGLE_PREFIX_CHARS
                )
                if productive_single_prefix:
                    stats["short_exact_pair_productive_prefix_windows"] += 1
                # Function-word singles are already handled by the general LM
                # collector. Keeping this channel lexical avoids duplicating
                # tens of thousands of weak `word + de/le/yi` fragments. A
                # productive 1+2 head is admitted here only if it later passes
                # the dedicated strong-evidence gate.
                if (
                    single_text
                    and single_text in LM_FUNCTION_SINGLE_CHARS
                    and not productive_single_prefix
                ):
                    continue
                left_entry = _best_viable_entry(
                    left_text,
                    single=(len(left_text) == 1),
                )
                right_entry = _best_viable_entry(
                    right_text,
                    single=(len(right_text) == 1),
                    productive_tail=productive_single_prefix,
                )
                if left_entry is None or right_entry is None:
                    continue

                stats["short_exact_pair_viable_windows"] += 1
                stats[f"short_exact_pair_{layout_name}_viable"] += 1
                query = left_entry[0] + right_entry[0]
                path = QUERY_PATH_FILE_SEPARATOR.join((left_text, right_text))
                key = (query, path)
                transition_counts[key] = transition_counts.get(key, 0) + 1
                current_source_keys.add(key)
                component_counts[left_text] = component_counts.get(left_text, 0) + 1
                component_counts[right_text] = component_counts.get(right_text, 0) + 1
                transition_rank_penalty[key] = max(
                    transition_rank_penalty.get(key, 0),
                    max(left_entry[3] - 1, right_entry[3] - 1),
                )
                transition_gap_penalty[key] = max(
                    transition_gap_penalty.get(key, 0),
                    max(
                        left_entry[4] - left_entry[2],
                        right_entry[4] - right_entry[2],
                    ),
                )
    if current_source:
        _flush_source_keys()

    # Context histograms are needed only for transitions that pass the basic
    # count/source gates. Building them in a second streaming pass keeps peak
    # memory bounded when the corpus contains millions of distinct trigrams.
    context_keys_by_span: Dict[str, List[Tuple[int, Tuple[str, str]]]] = {}
    context_candidate_keys: Set[Tuple[str, str]] = set()
    for key, count in transition_counts.items():
        source_count = transition_source_counts.get(key, 0)
        if not _has_source_support(key, count, source_count):
            continue
        segments = key[1].split(QUERY_PATH_FILE_SEPARATOR)
        if len(segments) != 2:
            continue
        context_keys_by_span.setdefault("".join(segments), []).append(
            (len(segments[0]), key)
        )
        context_candidate_keys.add(key)

    ambiguous_keys_by_span: Dict[str, Set[Tuple[str, str]]] = {}
    for key in context_candidate_keys:
        segments = key[1].split(QUERY_PATH_FILE_SEPARATOR)
        if len(segments) != 2:
            continue
        for segment_index, segment in enumerate(segments):
            if _cjk_len(segment) <= 1:
                continue
            entry = _best_viable_entry(segment, single=False)
            if entry is None or entry[0] not in ambiguous_multi_pinyins:
                continue
            for alternative in strong_multi_terms_by_pinyin.get(entry[0], set()):
                if alternative == segment:
                    continue
                alternative_segments = list(segments)
                alternative_segments[segment_index] = alternative
                alternative_text = "".join(alternative_segments)
                ambiguous_keys_by_span.setdefault(alternative_text, set()).add(key)

    if second_pass_sentences is None:
        if isinstance(sentences, (list, tuple)):
            second_pass_sentences = sentences
        else:
            raise ValueError(
                "streamed short exact pair collection requires a second corpus pass"
            )

    context_source = ""
    context_unextended_source_keys: Set[Tuple[str, str]] = set()

    def _flush_context_unextended_source_keys() -> None:
        for source_key in context_unextended_source_keys:
            transition_unextended_source_counts[source_key] = min(
                min_single_source_count,
                transition_unextended_source_counts.get(source_key, 0) + 1,
            )
        context_unextended_source_keys.clear()

    for sentence, source_name in second_pass_sentences:
        if source_name != context_source:
            if context_source:
                _flush_context_unextended_source_keys()
            context_source = source_name
        if len(sentence) < 3:
            continue
        for total_units in (3, 4, 5):
            if len(sentence) < total_units:
                continue
            for start in range(len(sentence) - total_units + 1):
                text = sentence[start : start + total_units]
                for key in ambiguous_keys_by_span.get(text, ()):
                    transition_ambiguous_alternative_count[key] = (
                        transition_ambiguous_alternative_count.get(key, 0) + 1
                    )
                context_keys = context_keys_by_span.get(text)
                if not context_keys:
                    continue
                left_context = sentence[start - 1] if start > 0 else "^"
                right_pos = start + total_units
                right_context = (
                    sentence[right_pos] if right_pos < len(sentence) else "$"
                )
                for split_at, key in context_keys:
                    left_contexts = transition_left_contexts.setdefault(key, {})
                    right_contexts = transition_right_contexts.setdefault(key, {})
                    left_contexts[left_context] = left_contexts.get(left_context, 0) + 1
                    right_contexts[right_context] = right_contexts.get(right_context, 0) + 1
                    left_text = text[:split_at]
                    right_text = text[split_at:]
                    extends_exact = False
                    if len(left_text) == 1 and start > 0:
                        for prefix_units in range(1, min(3, start) + 1):
                            if (
                                sentence[start - prefix_units : start] + left_text
                                in entries_by_text
                            ):
                                extends_exact = True
                                break
                    elif len(right_text) == 1 and right_pos < len(sentence):
                        remaining_units = len(sentence) - right_pos
                        for suffix_units in range(1, min(3, remaining_units) + 1):
                            if (
                                right_text + sentence[right_pos : right_pos + suffix_units]
                                in entries_by_text
                            ):
                                extends_exact = True
                                break
                    if extends_exact:
                        transition_exact_extension_count[key] = (
                            transition_exact_extension_count.get(key, 0) + 1
                        )
                    else:
                        context_unextended_source_keys.add(key)
    if context_source:
        _flush_context_unextended_source_keys()

    contenders_by_query: Dict[str, List[Tuple[str, int]]] = {}
    for (query, path), count in transition_counts.items():
        contenders_by_query.setdefault(query, []).append((path, count))
    for contenders in contenders_by_query.values():
        contenders.sort(key=lambda item: (-item[1], item[0]))

    priors: Dict[Tuple[str, str], int] = {}
    total_windows = max(1, sum(transition_counts.values()))
    for key, count in transition_counts.items():
        required_count, _required_sources = _evidence_requirements(key)
        if count < required_count:
            stats["short_exact_pair_skipped_count"] += 1
            continue
        source_count = transition_source_counts.get(key, 0)
        if not _has_source_support(key, count, source_count):
            stats["short_exact_pair_skipped_source_count"] += 1
            continue
        contenders = contenders_by_query.get(key[0], [])
        contender_rank = next(
            (
                rank
                for rank, (path, _count) in enumerate(contenders, start=1)
                if path == key[1]
            ),
            len(contenders) + 1,
        )
        if contender_rank > 2:
            stats["short_exact_pair_skipped_query_rank"] += 1
            continue
        best_count = contenders[0][1] if contenders else count
        competitor_count = max(
            (
                other_count
                for other_path, other_count in contenders
                if other_path != key[1]
            ),
            default=0,
        )
        segments = key[1].split(QUERY_PATH_FILE_SEPARATOR)
        is_productive_single_prefix = (
            len(segments) == 2
            and _cjk_len(segments[0]) == 1
            and _cjk_len(segments[1]) == 2
            and segments[0] in LM_PRODUCTIVE_SINGLE_PREFIX_CHARS
        )
        potential_strong_productive_runner_up = (
            is_productive_single_prefix
            and contender_rank == 2
            and count >= max(10, required_count + 6)
            and source_count >= 8
            and count * 100 >= best_count * 5
            and transition_rank_penalty.get(key, 0) <= 1
            and transition_gap_penalty.get(key, 0) <= 480
        )
        if contender_rank == 2 and not potential_strong_productive_runner_up and (
            count < required_count + 7 or count * 100 < best_count * 80
        ):
            stats["short_exact_pair_skipped_weak_runner_up"] += 1
            continue

        segment_product = 1
        for segment in segments:
            segment_product *= max(1, component_counts.get(segment, 1))
        pmi = math.log2((count * total_windows) / max(1, segment_product))
        query_total = max(1, sum(value for _path, value in contenders))
        query_share = count / query_total
        dominance = math.log2((count + 2) / (competitor_count + 2))
        right_pos_tag = ""
        if is_productive_single_prefix:
            right_pos_tag = jieba_pos_map.get(segments[1], "")
            if _is_named_entity_pos(right_pos_tag):
                stats["short_exact_pair_productive_prefix_named_tail_skipped"] += 1
                continue
            if (
                segments[0] in LM_PRODUCTIVE_PREDICATE_ONLY_HEADS
                and not _is_productive_predicate_pos(right_pos_tag)
            ):
                stats[
                    "short_exact_pair_productive_prefix_nonpredicate_tail_skipped"
                ] += 1
                continue
            if contender_rank == 2 and not _is_productive_predicate_pos(
                right_pos_tag
            ):
                stats[
                    "short_exact_pair_productive_prefix_nonpredicate_tail_skipped"
                ] += 1
                continue
        exact_extension_count = transition_exact_extension_count.get(key, 0)
        direct_count = max(0, count - exact_extension_count)
        direct_source_count = transition_unextended_source_counts.get(key, 0)
        has_independent_direct_evidence = (
            direct_count >= 12 and direct_source_count >= 6
        )
        has_strong_runner_up_direct_evidence = (
            direct_count >= LM_STRONG_PRODUCTIVE_RUNNER_UP_MIN_DIRECT_COUNT
            and direct_source_count
            >= LM_STRONG_PRODUCTIVE_RUNNER_UP_MIN_DIRECT_SOURCES
        )
        strong_absolute_productive_evidence = (
            is_productive_single_prefix
            and count >= max(24, required_count + 12)
            and source_count >= min_single_source_count
            and contender_rank == 1
            and query_share >= 0.90
            and has_independent_direct_evidence
            and transition_rank_penalty.get(key, 0) <= 1
            and transition_gap_penalty.get(key, 0) <= 120
            and (
                competitor_count == 0
                or count * 100 >= competitor_count * 300
            )
        )
        strong_productive_prefix_evidence = (
            is_productive_single_prefix
            and count >= max(12, required_count + 5)
            and source_count >= 6
            and contender_rank == 1
            and query_share >= 0.75
            and (pmi >= 1.25 or strong_absolute_productive_evidence)
            and transition_rank_penalty.get(key, 0) <= 1
            and transition_gap_penalty.get(key, 0) <= 120
            and (
                competitor_count == 0
                or count * 100 >= competitor_count * 160
            )
        )
        strong_productive_runner_up_evidence = (
            potential_strong_productive_runner_up
            and has_strong_runner_up_direct_evidence
            and query_share >= 0.05
            and _is_productive_predicate_pos(right_pos_tag)
        )
        admitted_productive_prefix_evidence = (
            strong_productive_prefix_evidence
            or strong_productive_runner_up_evidence
        )

        left_context_peak = max(
            (
                value
                for context, value in transition_left_contexts.get(key, {}).items()
                if context != "^"
            ),
            default=0,
        )
        right_context_peak = max(
            (
                value
                for context, value in transition_right_contexts.get(key, {}).items()
                if context != "$"
            ),
            default=0,
        )
        if max(left_context_peak, right_context_peak) * 100 >= count * 80:
            stats["short_exact_pair_skipped_embedded_fragment"] += 1
            continue
        if is_productive_single_prefix and not admitted_productive_prefix_evidence:
            stats["short_exact_pair_productive_prefix_weak_skipped"] += 1
            stats["short_exact_pair_skipped_weak_association"] += 1
            continue
        if exact_extension_count * 100 >= count * 60:
            if (
                admitted_productive_prefix_evidence
                and (
                    has_independent_direct_evidence
                    or has_strong_runner_up_direct_evidence
                )
            ):
                stats["short_exact_pair_productive_prefix_extension_bypassed"] += 1
            else:
                if is_productive_single_prefix:
                    stats[
                        "short_exact_pair_productive_prefix_insufficient_direct_skipped"
                    ] += 1
                stats["short_exact_pair_skipped_exact_extension"] += 1
                continue
        strong_absolute_evidence = (
            count >= max(12, required_count + 5)
            and source_count >= 6
            and query_share >= 0.70
            and (
                competitor_count == 0
                or count * 100 >= competitor_count * 140
            )
        )
        has_single_component = any(_cjk_len(segment) == 1 for segment in segments)
        medium_single_evidence = has_single_component and count == 4
        independent_single_evidence = (
            has_single_component
            and count >= required_count
            and source_count >= 5
            and source_count * 100 >= min(count, min_single_source_count) * 80
            and query_share >= 0.75
            and (
                competitor_count == 0
                or count * 100 >= competitor_count * 160
            )
        )

        # Reject observed homophone substitutions before exposing evidence to
        # either the ordinary transition model or the stricter completion
        # index. Completion may use stronger absolute evidence than the
        # ordinary PMI gate, but it must not bypass lexical ambiguity checks.
        ambiguous_multi_count = 0
        for segment in segments:
            if _cjk_len(segment) <= 1:
                continue
            entry = _best_viable_entry(
                segment,
                single=False,
                productive_tail=(
                    is_productive_single_prefix and segment == segments[1]
                ),
            )
            if entry is not None and entry[0] in ambiguous_multi_pinyins:
                ambiguous_multi_count += 1
        if (
            ambiguous_multi_count > 0
            and transition_ambiguous_alternative_count.get(key, 0) >= 2
            and not strong_productive_runner_up_evidence
        ):
            stats["short_exact_pair_skipped_observed_homophone_alternative"] += 1
            continue

        score = 300
        score += int(round(math.log2(count + 1) * 14))
        score += min(28, source_count * 5)
        score += int(round(query_share * 28))
        score += int(round(max(-1.0, min(3.0, dominance)) * 10))
        score += int(round(max(-1.0, min(4.0, pmi)) * 6))
        score -= min(42, transition_rank_penalty.get(key, 0) * 7)
        score -= min(48, max(0, transition_gap_penalty.get(key, 0)) // 10)
        if contender_rank == 2:
            score -= 20
        minimum_effective_score = 390 if has_single_component else 350
        effective_score = max(
            minimum_effective_score,
            min(min(max_weight, 480), score),
        )

        # Completion has its own conservative gate. Preserve structurally
        # valid raw evidence here instead of making it depend on the ordinary
        # blue-candidate PMI admission below. This matters for common/common
        # pairs whose PMI is modest despite broad, direct corpus support.
        if completion_evidence_out is not None:
            completion_evidence_out[key] = (
                count,
                source_count,
                direct_count,
                direct_source_count,
                competitor_count,
                contender_rank,
                query_share,
                pmi,
                effective_score,
            )

        if (
            pmi < 0.75
            and not strong_absolute_evidence
            and not independent_single_evidence
            and not strong_productive_runner_up_evidence
        ) or (
            competitor_count > 0
            and query_share < 0.55
            and not strong_productive_runner_up_evidence
        ):
            stats["short_exact_pair_skipped_weak_association"] += 1
            continue

        if medium_single_evidence and (
            source_count < 4
            or contender_rank != 1
            or query_share < 0.75
            or pmi < 1.25
            or transition_rank_penalty.get(key, 0) > 3
            or transition_gap_penalty.get(key, 0) > 120
        ):
            stats["short_exact_pair_skipped_weak_medium_evidence"] += 1
            continue
        if medium_single_evidence:
            # Keep count=4 evidence in the lowest runtime-supported band. It
            # can recall an exact 1+2/2+1 composition without carrying the
            # same ranking strength as better-supported transitions.
            effective_score = min(399, effective_score)
        if strong_productive_runner_up_evidence:
            effective_score = LM_STRONG_PRODUCTIVE_RUNNER_UP_WEIGHT
            stats[
                "short_exact_pair_productive_prefix_strong_runner_up_emitted"
            ] += 1
        priors[key] = effective_score
        if is_productive_single_prefix:
            stats["short_exact_pair_productive_prefix_emitted"] += 1

    stats["short_exact_pair_priors_emitted"] = len(priors)
    return priors, stats


def _collect_strong_single_pair_transition_priors(
    sentences: Iterable[Tuple[str, str]],
    entries_by_text: Dict[str, List[Tuple[str, str, int, int, int]]],
    *,
    second_pass_sentences: Iterable[Tuple[str, str]] | None = None,
    exact_texts: Set[str] | None = None,
    jieba_pos_map: Dict[str, str] | None = None,
    min_count: int = LM_STRONG_SINGLE_PAIR_MIN_COUNT,
    min_source_count: int = LM_STRONG_SINGLE_PAIR_MIN_SOURCES,
    max_weight: int = 468,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    """Collect sparse corpus-backed 1+1 transitions.

    Raw adjacent characters are used only as a cheap count prefilter. Final
    evidence is collected from adjacent one-character segments in Cassotis
    dictionary-constrained DP paths, so a boundary such as ``\u5e73\u5b89|\u4e0d\u884c``
    cannot create the synthetic pair ``\u5b89|\u4e0d``. Full two-character dictionary
    entries are excluded, and both character readings must be common exact
    candidates. One (exceptionally two) paths are retained for each compact
    pinyin query.
    """

    jieba_pos_map = jieba_pos_map or {}
    known_exact_texts = set(entries_by_text)
    if exact_texts:
        known_exact_texts.update(exact_texts)
    stats: Dict[str, int] = {
        "strong_single_pair_windows": 0,
        "strong_single_pair_nonexact_windows": 0,
        "strong_single_pair_viable_windows": 0,
        "strong_single_pair_segmented_sentences": 0,
        "strong_single_pair_unsegmented_sentences": 0,
        "strong_single_pair_segmented_windows": 0,
        "strong_single_pair_segmented_viable_windows": 0,
        "strong_single_pair_preliminary": 0,
        "strong_single_pair_skipped_exact": 0,
        "strong_single_pair_skipped_uncommon_reading": 0,
        "strong_single_pair_skipped_count": 0,
        "strong_single_pair_skipped_source_count": 0,
        "strong_single_pair_skipped_named_fragment": 0,
        "strong_single_pair_skipped_concentrated_context": 0,
        "strong_single_pair_skipped_query_dominance": 0,
        "strong_single_pair_runner_up_emitted": 0,
        "strong_single_pair_priors_emitted": 0,
    }

    common_entries_by_char: Dict[
        str, List[Tuple[str, str, int, int, int]]
    ] = {}
    for text, entries in entries_by_text.items():
        if _cjk_len(text) != 1:
            continue
        viable: List[Tuple[str, str, int, int, int]] = []
        seen_pinyin: Set[str] = set()
        for entry in entries:
            pinyin, _text, weight, exact_rank, top_weight = entry
            if (
                not pinyin
                or pinyin in seen_pinyin
                or weight < 270
                or exact_rank > 6
                or top_weight - weight > 160
            ):
                continue
            viable.append(entry)
            seen_pinyin.add(pinyin)
            if len(viable) >= 2:
                break
        if viable:
            common_entries_by_char[text] = viable

    raw_pair_counts: Dict[str, int] = {}

    for sentence, _source_name in sentences:
        if len(sentence) < 2:
            continue
        for start in range(len(sentence) - 1):
            stats["strong_single_pair_windows"] += 1
            pair_text = sentence[start : start + 2]
            if pair_text in known_exact_texts:
                stats["strong_single_pair_skipped_exact"] += 1
                continue
            stats["strong_single_pair_nonexact_windows"] += 1
            if _is_named_entity_pos(jieba_pos_map.get(pair_text, "")):
                stats["strong_single_pair_skipped_named_fragment"] += 1
                continue
            left_entries = common_entries_by_char.get(pair_text[0], ())
            right_entries = common_entries_by_char.get(pair_text[1], ())
            if not left_entries or not right_entries:
                stats["strong_single_pair_skipped_uncommon_reading"] += 1
                continue

            raw_pair_counts[pair_text] = raw_pair_counts.get(pair_text, 0) + 1
            stats["strong_single_pair_viable_windows"] += 1

    preliminary_pair_texts = {
        pair_text: count
        for pair_text, count in raw_pair_counts.items()
        if count >= min_count
    }
    del raw_pair_counts
    if not preliminary_pair_texts:
        return {}, stats

    if second_pass_sentences is None:
        if isinstance(sentences, (list, tuple)):
            second_pass_sentences = sentences
        else:
            raise ValueError(
                "streamed strong single-pair collection requires a second corpus pass"
            )
    pair_counts: Dict[str, int] = {}
    transition_source_fingerprints: Dict[str, List[int]] = {}
    # [left candidate, left balance, right candidate, right balance]
    majority_states: Dict[str, List[object]] = {}
    left_component_counts: Dict[str, int] = {}
    right_component_counts: Dict[str, int] = {}

    def update_majority_candidate(
        state: List[object], candidate_idx: int, balance_idx: int, context: str
    ) -> None:
        candidate = str(state[candidate_idx])
        balance = int(state[balance_idx])
        if balance <= 0:
            state[candidate_idx] = context
            state[balance_idx] = 1
        elif candidate == context:
            state[balance_idx] = balance + 1
        else:
            state[balance_idx] = balance - 1

    for sentence, source_name in second_pass_sentences:
        if len(sentence) < 2:
            continue
        segments = _segment_lm_sentence(
            sentence,
            entries_by_text,
            max_segment_units=4,
        )
        if not segments:
            stats["strong_single_pair_unsegmented_sentences"] += 1
            continue
        stats["strong_single_pair_segmented_sentences"] += 1
        stats["strong_single_pair_segmented_windows"] += max(
            0, len(segments) - 1
        )
        source_fingerprint = hash(source_name)
        for segment_idx in range(len(segments) - 1):
            left_text = segments[segment_idx][1]
            right_text = segments[segment_idx + 1][1]
            if _cjk_len(left_text) != 1 or _cjk_len(right_text) != 1:
                continue
            left_entries = common_entries_by_char.get(left_text, ())
            right_entries = common_entries_by_char.get(right_text, ())
            if not left_entries or not right_entries:
                continue
            stats["strong_single_pair_segmented_viable_windows"] += 1
            for left_entry in left_entries:
                left_component = left_entry[0] + "\0" + left_text
                left_component_counts[left_component] = (
                    left_component_counts.get(left_component, 0) + 1
                )
            for right_entry in right_entries:
                right_component = right_entry[0] + "\0" + right_text
                right_component_counts[right_component] = (
                    right_component_counts.get(right_component, 0) + 1
                )

            pair_text = left_text + right_text
            if pair_text not in preliminary_pair_texts:
                continue
            pair_counts[pair_text] = pair_counts.get(pair_text, 0) + 1
            left_context = "^"
            if segment_idx > 0:
                left_context = segments[segment_idx - 1][1][-1]
            right_context = "$"
            if segment_idx + 2 < len(segments):
                right_context = segments[segment_idx + 2][1][0]
            source_fingerprints = transition_source_fingerprints.get(pair_text)
            if source_fingerprints is None:
                source_fingerprints = []
                transition_source_fingerprints[pair_text] = source_fingerprints
            if (
                len(source_fingerprints)
                < LM_STRONG_SINGLE_PAIR_RUNNER_UP_MIN_SOURCES
                and source_fingerprint not in source_fingerprints
            ):
                source_fingerprints.append(source_fingerprint)
            majority_state = majority_states.get(pair_text)
            if majority_state is None:
                majority_state = ["", 0, "", 0]
                majority_states[pair_text] = majority_state
            update_majority_candidate(
                majority_state, 0, 1, left_context
            )
            update_majority_candidate(
                majority_state, 2, 3, right_context
            )

    eligible_pair_counts = {
        pair_text: count
        for pair_text, count in pair_counts.items()
        if count >= min_count
    }
    stats["strong_single_pair_skipped_count"] += (
        len(preliminary_pair_texts) - len(eligible_pair_counts)
    )

    transition_metadata: Dict[
        Tuple[str, str], Tuple[int, int, str, str]
    ] = {}
    preliminary_keys: Set[Tuple[str, str]] = set()
    for pair_text in eligible_pair_counts:
        left_entries = common_entries_by_char.get(pair_text[0], ())
        right_entries = common_entries_by_char.get(pair_text[1], ())
        for left_entry in left_entries:
            for right_entry in right_entries:
                query = left_entry[0] + right_entry[0]
                path = QUERY_PATH_FILE_SEPARATOR.join(pair_text)
                key = (query, path)
                preliminary_keys.add(key)
                transition_metadata[key] = (
                    max(left_entry[3] - 1, right_entry[3] - 1),
                    max(
                        left_entry[4] - left_entry[2],
                        right_entry[4] - right_entry[2],
                    ),
                    left_entry[0] + "\0" + pair_text[0],
                    right_entry[0] + "\0" + pair_text[1],
                )
    stats["strong_single_pair_preliminary"] = len(preliminary_keys)
    if not preliminary_keys:
        return {}, stats

    qualified_by_query: Dict[
        str, List[Tuple[Tuple[str, str], int, int, float, int]]
    ] = {}
    total_windows = max(
        1, stats["strong_single_pair_segmented_viable_windows"]
    )
    for key in preliminary_keys:
        pair_text = key[1].replace(QUERY_PATH_FILE_SEPARATOR, "")
        count = eligible_pair_counts[pair_text]
        source_count = len(transition_source_fingerprints.get(pair_text, ()))
        if source_count < min_source_count:
            stats["strong_single_pair_skipped_source_count"] += 1
            continue
        rank_penalty, gap_penalty, left_component, right_component = (
            transition_metadata[key]
        )
        if (
            rank_penalty > 3
            or gap_penalty > 120
        ):
            stats["strong_single_pair_skipped_uncommon_reading"] += 1
            continue

        majority_state = majority_states[pair_text]
        left_candidate = str(majority_state[0])
        right_candidate = str(majority_state[2])
        left_peak_signal = 0
        if left_candidate != "^":
            left_peak_signal = int(majority_state[1])
        right_peak_signal = 0
        if right_candidate != "$":
            right_peak_signal = int(majority_state[3])
        # Boyer-Moore balance is a conservative fixed-context signal. An
        # actual 80% majority leaves at least a 60% balance; rejecting at that
        # point can only make this sparse generated layer more conservative.
        context_peak_signal = max(left_peak_signal, right_peak_signal)
        if context_peak_signal * 100 >= count * 60:
            stats["strong_single_pair_skipped_concentrated_context"] += 1
            continue

        component_product = max(
            1, left_component_counts.get(left_component, 1)
        ) * max(
            1, right_component_counts.get(right_component, 1)
        )
        pmi = math.log2((count * total_windows) / component_product)
        qualified_by_query.setdefault(key[0], []).append(
            (key, count, source_count, pmi, context_peak_signal)
        )

    priors: Dict[Tuple[str, str], int] = {}
    for contenders in qualified_by_query.values():
        contenders.sort(key=lambda item: (-item[1], -item[2], item[0][1]))
        query_total = sum(item[1] for item in contenders)
        top_count = contenders[0][1]
        second_count = contenders[1][1] if len(contenders) > 1 else 0
        third_count = contenders[2][1] if len(contenders) > 2 else 0
        top_key, _top_count, top_source_count, top_pmi, _top_context = (
            contenders[0]
        )
        top_share = top_count / max(1, query_total)
        normal_top_admitted = (
            top_share >= 0.58
            and (second_count == 0 or top_count * 100 >= second_count * 160)
            and (top_pmi >= 0.75 or top_count >= 24)
        )
        exceptional_runner_admitted = False
        if len(contenders) > 1:
            runner_key, runner_count, runner_source_count, runner_pmi, _ = (
                contenders[1]
            )
            exceptional_runner_admitted = (
                runner_count >= LM_STRONG_SINGLE_PAIR_RUNNER_UP_MIN_COUNT
                and runner_source_count
                >= LM_STRONG_SINGLE_PAIR_RUNNER_UP_MIN_SOURCES
                and runner_count / max(1, query_total) >= 0.30
                and runner_count * 100 >= top_count * 75
                and (third_count == 0 or runner_count >= third_count * 2)
                and transition_metadata[runner_key][0] <= 1
                and transition_metadata[runner_key][1] <= 60
                and runner_pmi >= 1.5
                and top_count >= LM_STRONG_SINGLE_PAIR_RUNNER_UP_MIN_COUNT
                and top_source_count
                >= LM_STRONG_SINGLE_PAIR_RUNNER_UP_MIN_SOURCES
                and transition_metadata[top_key][0] <= 1
                and transition_metadata[top_key][1] <= 60
                and top_pmi >= 1.5
                and (top_count + runner_count) / max(1, query_total) >= 0.85
            )
        top_admitted = normal_top_admitted or exceptional_runner_admitted

        for contender_idx, (key, count, source_count, pmi, _context_peak) in enumerate(
            contenders[:2]
        ):
            query_share = count / max(1, query_total)
            competitor_count = max(
                (item[1] for item in contenders if item[0] != key),
                default=0,
            )
            if contender_idx == 0:
                admitted = top_admitted
            else:
                admitted = top_admitted and exceptional_runner_admitted
            if not admitted:
                stats["strong_single_pair_skipped_query_dominance"] += 1
                continue

            dominance = math.log2((count + 2) / (competitor_count + 2))
            score = 382
            score += int(round(math.log2(count + 1) * 5))
            score += min(18, source_count * 2)
            score += int(round(query_share * 12))
            score += int(round(max(-1.0, min(3.0, dominance)) * 4))
            score += int(round(max(0.0, min(4.0, pmi)) * 3))
            score -= min(18, transition_metadata[key][0] * 6)
            score -= min(20, transition_metadata[key][1] // 8)
            if contender_idx == 1:
                score -= 10
                stats["strong_single_pair_runner_up_emitted"] += 1
            priors[key] = max(420, min(max_weight, score))

    stats["strong_single_pair_priors_emitted"] = len(priors)
    return priors, stats


def _build_lm_corpus_query_path_prior_map(
    mapping: Dict[Tuple[str, str], int],
    corpus_dir: pathlib.Path,
    *,
    convert_text,
    additional_exact_texts: Set[str] | None,
    single_char_readings_map: Dict[str, Set[str]] | None,
    single_char_default_pinyin_map: Dict[str, str] | None,
    single_char_source_rank_map: Dict[Tuple[str, str], int] | None,
    single_char_pinlu_detail_map: Dict[Tuple[str, str], int] | None,
    char_frequency_prior: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    stats_prefix: str,
    exact_pairs_only: bool = False,
    general_transitions_only: bool = False,
    completion_evidence_out: Dict[
        Tuple[str, str], Tuple[int, int, int, int, int, int, float, float, int]
    ]
    | None = None,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    entries_by_text, _rank_info = _build_lm_entry_indexes(
        mapping,
        max_segment_units=4,
        single_char_readings_map=single_char_readings_map,
        single_char_default_pinyin_map=single_char_default_pinyin_map,
        single_char_source_rank_map=single_char_source_rank_map,
        single_char_pinlu_detail_map=single_char_pinlu_detail_map,
        char_frequency_prior=char_frequency_prior,
    )
    exact_two_character_texts = {
        text
        for _pinyin, text in mapping
        if _cjk_len(text) == 2 and CJK_FULL_RE.fullmatch(text)
    }
    if additional_exact_texts:
        exact_two_character_texts.update(
            text
            for text in additional_exact_texts
            if _cjk_len(text) == 2 and CJK_FULL_RE.fullmatch(text)
        )
    if exact_pairs_only and general_transitions_only:
        raise ValueError(
            "exact-pairs-only and general-transitions-only are mutually exclusive"
        )
    if exact_pairs_only:
        sentence_stats = _new_lm_corpus_stats()
        sentence_stats["lm_corpus_streaming_exact_pairs_only"] = 1
        priors: Dict[Tuple[str, str], int] = {}
        prior_stats: Dict[str, int] = {}
        short_pair_priors, short_pair_stats = (
            _collect_short_exact_pair_transition_priors(
                _stream_lm_corpus_sentences(
                    corpus_dir,
                    min_units=4,
                    max_units=40,
                    convert_text=convert_text,
                    stats=sentence_stats,
                ),
                entries_by_text,
                second_pass_sentences=_stream_lm_corpus_sentences(
                    corpus_dir,
                    min_units=4,
                    max_units=40,
                    convert_text=convert_text,
                ),
                jieba_pos_map=jieba_pos_map,
                completion_evidence_out=completion_evidence_out,
            )
        )
        strong_single_pair_priors, strong_single_pair_stats = (
            _collect_strong_single_pair_transition_priors(
                _stream_lm_corpus_sentences(
                    corpus_dir,
                    min_units=4,
                    max_units=40,
                    convert_text=convert_text,
                ),
                entries_by_text,
                second_pass_sentences=_stream_lm_corpus_sentences(
                    corpus_dir,
                    min_units=4,
                    max_units=40,
                    convert_text=convert_text,
                ),
                exact_texts=exact_two_character_texts,
                jieba_pos_map=jieba_pos_map,
            )
        )
    elif general_transitions_only:
        sentence_stats = _new_lm_corpus_stats()
        sentence_stats["lm_corpus_streaming_general_transitions_only"] = 1
        priors, prior_stats = _collect_lm_transition_priors(
            _stream_lm_corpus_sentences(
                corpus_dir,
                min_units=4,
                max_units=40,
                convert_text=convert_text,
                stats=sentence_stats,
            ),
            entries_by_text,
        )
        short_pair_priors = {}
        short_pair_stats = {}
        strong_single_pair_priors = {}
        strong_single_pair_stats = {}
    else:
        # The expanded training corpus contains millions of fragments.  Keep
        # every collector streaming instead of materializing the corpus once:
        # N-best segmentation intentionally expands each accepted sentence,
        # so retaining the raw input list would otherwise dominate memory.
        sentence_stats = _new_lm_corpus_stats()
        priors, prior_stats = _collect_lm_transition_priors(
            _stream_lm_corpus_sentences(
                corpus_dir,
                min_units=4,
                max_units=40,
                convert_text=convert_text,
                stats=sentence_stats,
            ),
            entries_by_text,
        )
        short_pair_priors, short_pair_stats = (
            _collect_short_exact_pair_transition_priors(
                _stream_lm_corpus_sentences(
                    corpus_dir,
                    min_units=4,
                    max_units=40,
                    convert_text=convert_text,
                ),
                entries_by_text,
                second_pass_sentences=_stream_lm_corpus_sentences(
                    corpus_dir,
                    min_units=4,
                    max_units=40,
                    convert_text=convert_text,
                ),
                jieba_pos_map=jieba_pos_map,
                completion_evidence_out=completion_evidence_out,
            )
        )
        strong_single_pair_priors, strong_single_pair_stats = (
            _collect_strong_single_pair_transition_priors(
                _stream_lm_corpus_sentences(
                    corpus_dir,
                    min_units=4,
                    max_units=40,
                    convert_text=convert_text,
                ),
                entries_by_text,
                second_pass_sentences=_stream_lm_corpus_sentences(
                    corpus_dir,
                    min_units=4,
                    max_units=40,
                    convert_text=convert_text,
                ),
                exact_texts=exact_two_character_texts,
                jieba_pos_map=jieba_pos_map,
            )
        )
    for key, weight in short_pair_priors.items():
        priors[key] = max(priors.get(key, 0), weight)
    for key, weight in strong_single_pair_priors.items():
        priors[key] = max(priors.get(key, 0), weight)
    stats: Dict[str, int] = {}
    for key, value in sentence_stats.items():
        stats[f"{stats_prefix}_{key}"] = value
    for key, value in prior_stats.items():
        stats[f"{stats_prefix}_{key}"] = value
    for key, value in short_pair_stats.items():
        stats[f"{stats_prefix}_{key}"] = value
    for key, value in strong_single_pair_stats.items():
        stats[f"{stats_prefix}_{key}"] = value
    return priors, stats


def _select_dedicated_lm_transitions(
    base_priors: Dict[Tuple[str, str], int],
    corpus_priors: Dict[Tuple[str, str], int],
    *,
    stats_prefix: str,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    min_model_weight = 340
    runner_up_min_weight = 400
    runner_up_min_percent = 90
    candidates_by_bucket: Dict[
        Tuple[str, int], List[Tuple[Tuple[str, str], int]]
    ] = {}
    overlapping_existing = 0
    skipped_unsupported_ngram = 0
    skipped_low_weight = 0
    skipped_runner_up = 0
    selected_runner_up = 0
    selected_strong_productive_runner_up = 0
    for key, weight in corpus_priors.items():
        if key in base_priors:
            # The legacy query-path prior and the dedicated LM serve different
            # runtime stages. Keep corpus-backed transitions in the LM table
            # even when the decoder already has a prior for the same path, so
            # final-candidate reranking sees the strongest evidence as well.
            overlapping_existing += 1
        ngram_order = len(key[1].split(QUERY_PATH_FILE_SEPARATOR))
        if ngram_order not in (2, 3):
            skipped_unsupported_ngram += 1
            continue
        if weight < min_model_weight:
            skipped_low_weight += 1
            continue
        bucket = (key[0], ngram_order)
        candidates_by_bucket.setdefault(bucket, []).append((key, weight))

    selected: Dict[Tuple[str, str], int] = {}
    for bucket_candidates in candidates_by_bucket.values():
        bucket_candidates.sort(key=lambda item: (-item[1], item[0][1]))
        top_weight = bucket_candidates[0][1]
        for rank, (key, weight) in enumerate(bucket_candidates):
            if rank == 0:
                selected[key] = weight
                continue
            path_segments = key[1].split(QUERY_PATH_FILE_SEPARATOR)
            is_strong_productive_runner_up = (
                rank == 1
                and weight == LM_STRONG_PRODUCTIVE_RUNNER_UP_WEIGHT
                and len(path_segments) == 2
                and _cjk_len(path_segments[0]) == 1
                and path_segments[0] in LM_PRODUCTIVE_SINGLE_PREFIX_CHARS
                and _cjk_len(path_segments[1]) == 2
            )
            if is_strong_productive_runner_up:
                selected[key] = weight
                selected_strong_productive_runner_up += 1
                continue
            if (
                rank == 1
                and weight >= runner_up_min_weight
                and weight * 100 >= top_weight * runner_up_min_percent
            ):
                selected[key] = weight
                selected_runner_up += 1
                continue
            skipped_runner_up += 1
    return selected, {
        f"{stats_prefix}_lm_transition_rows": len(selected),
        f"{stats_prefix}_lm_transition_overlapping_existing": overlapping_existing,
        f"{stats_prefix}_lm_transition_skipped_unsupported_ngram": skipped_unsupported_ngram,
        f"{stats_prefix}_lm_transition_skipped_low_weight": skipped_low_weight,
        f"{stats_prefix}_lm_transition_skipped_runner_up": skipped_runner_up,
        f"{stats_prefix}_lm_transition_selected_runner_up": selected_runner_up,
        f"{stats_prefix}_lm_transition_selected_strong_productive_runner_up": (
            selected_strong_productive_runner_up
        ),
    }


def _build_query_path_prior_map(
    mapping: Dict[Tuple[str, str], int],
    usage_score_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    pageviews_signal_map: Dict[str, float],
    jieba_direct_signal_map: Dict[str, float] | None,
    jieba_pos_map: Dict[str, str] | None,
    char_frequency_prior: Dict[str, float] | None,
    stats_prefix: str,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    stats = {
        f"{stats_prefix}_query_path_terms_considered": 0,
        f"{stats_prefix}_query_path_terms_emitted": 0,
        f"{stats_prefix}_query_path_full_entries": 0,
        f"{stats_prefix}_query_path_prefix_entries": 0,
    }
    if not mapping:
        return {}, stats

    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    char_frequency_prior = char_frequency_prior or {}

    entries_by_text: Dict[str, List[Tuple[str, int]]] = {}
    for (pinyin, text), weight in mapping.items():
        text_len = _cjk_len(text)
        if weight <= 0 or text_len <= 0 or text_len > 6:
            continue
        entries_by_text.setdefault(text, []).append((pinyin, weight))

    for text in entries_by_text.keys():
        entries_by_text[text].sort(key=lambda item: (-item[1], len(item[0]), item[0]))

    priors: Dict[Tuple[str, str], int] = {}

    def _segment_confidence(text: str, weight: int) -> float:
        usage_score = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
        source_hits = source_hits_map.get(text, 0)
        pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(text, 0.0)))
        jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(text, 0.0)))
        pos_tag = jieba_pos_map.get(text, "")
        char_score = _compute_text_single_char_prior(text, char_frequency_prior)
        phrase_conf = _compute_common_phrase_confidence(
            text,
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=pageview_score,
            jieba_direct_score=jieba_direct_score,
            wiki_support=pageview_score >= 0.08 or source_hits >= 2,
            pos_tag=pos_tag,
            char_score=char_score,
        )
        confidence = phrase_conf
        if weight >= 620:
            confidence += 0.12
        elif weight >= 460:
            confidence += 0.06
        return min(1.0, max(0.0, confidence))

    def _score_segment(
        segment_text: str,
        segment_weight: int,
        segment_confidence: float,
        is_first: bool,
        is_last: bool,
    ) -> int:
        segment_len = _cjk_len(segment_text)
        score = max(24, int(round(segment_weight * 0.44)))
        score += int(round(segment_confidence * 220.0))
        score += segment_len * 28
        if segment_len >= 2:
            score += 34
        if segment_len >= 3 and segment_confidence >= 0.18:
            score += 26
        if segment_len == 1:
            score -= 68
            if not is_first and not is_last:
                score -= 74
            elif is_first:
                score -= 28
            elif is_last:
                score -= 22
        return score

    def _score_path(segments: List[Tuple[str, str, int]]) -> int:
        segment_count = len(segments)
        if segment_count < 2:
            return -10_000

        score = 0
        all_multi_char = True
        has_middle_single_char = False
        for idx, (segment_pinyin, segment_text, segment_weight) in enumerate(segments):
            del segment_pinyin
            segment_len = _cjk_len(segment_text)
            if segment_len <= 1:
                all_multi_char = False
                if idx > 0 and idx < segment_count - 1:
                    has_middle_single_char = True
            score += _score_segment(
                segment_text,
                segment_weight,
                _segment_confidence(segment_text, segment_weight),
                is_first=(idx == 0),
                is_last=(idx == segment_count - 1),
            )

        if segment_count == 2:
            score += 152
        elif segment_count == 3:
            score += 96
        else:
            score += 48 - ((segment_count - 3) * 52)

        if all_multi_char:
            score += 84
        if has_middle_single_char:
            score -= 120

        return score

    def _maybe_add_prior(query_pinyin: str, path_segments: List[str], weight: int) -> bool:
        if weight <= 0 or len(path_segments) < 2:
            return False
        path_text = QUERY_PATH_FILE_SEPARATOR.join(path_segments)
        key = (query_pinyin, path_text)
        previous = priors.get(key, 0)
        if weight > previous:
            priors[key] = weight
            return True
        return False

    for (full_pinyin, full_text), full_weight in mapping.items():
        text_units = _split_text_units(full_text)
        text_len = len(text_units)
        if full_weight <= 0 or text_len < 3 or text_len > 6:
            continue

        full_usage_score = min(1.0, max(0.0, usage_score_map.get(full_text, 0.0)))
        full_source_hits = source_hits_map.get(full_text, 0)
        full_pageview_score = min(1.0, max(0.0, pageviews_signal_map.get(full_text, 0.0)))
        full_jieba_direct_score = min(1.0, max(0.0, jieba_direct_signal_map.get(full_text, 0.0)))
        full_pos_tag = jieba_pos_map.get(full_text, "")
        full_char_score = _compute_text_single_char_prior(full_text, char_frequency_prior)
        full_phrase_confidence = _compute_common_phrase_confidence(
            full_text,
            usage_score=full_usage_score,
            source_hits=full_source_hits,
            pageview_score=full_pageview_score,
            jieba_direct_score=full_jieba_direct_score,
            wiki_support=full_pageview_score >= 0.08 or full_source_hits >= 2,
            pos_tag=full_pos_tag,
            char_score=full_char_score,
        )
        if (full_phrase_confidence < 0.16) and (full_weight < 560):
            continue

        stats[f"{stats_prefix}_query_path_terms_considered"] += 1
        candidate_paths: Dict[str, Tuple[int, List[Tuple[str, str, int]]]] = {}

        def _walk(
            unit_index: int,
            pinyin_index: int,
            current_segments: List[Tuple[str, str, int]],
        ) -> None:
            if len(current_segments) > 4:
                return
            if unit_index == text_len and pinyin_index == len(full_pinyin):
                if len(current_segments) >= 2:
                    path_key = QUERY_PATH_FILE_SEPARATOR.join(seg_text for _seg_pinyin, seg_text, _seg_weight in current_segments)
                    path_score = _score_path(current_segments)
                    existing = candidate_paths.get(path_key)
                    if existing is None or path_score > existing[0]:
                        candidate_paths[path_key] = (path_score, list(current_segments))
                return
            if unit_index >= text_len or pinyin_index >= len(full_pinyin):
                return

            max_end = min(text_len, unit_index + 4)
            for next_unit_index in range(unit_index + 1, max_end + 1):
                segment_text = "".join(text_units[unit_index:next_unit_index])
                for segment_pinyin, segment_weight in entries_by_text.get(segment_text, []):
                    if not full_pinyin.startswith(segment_pinyin, pinyin_index):
                        continue
                    next_pinyin_index = pinyin_index + len(segment_pinyin)
                    if next_pinyin_index > len(full_pinyin):
                        continue
                    if (next_unit_index == text_len) != (next_pinyin_index == len(full_pinyin)):
                        continue
                    current_segments.append((segment_pinyin, segment_text, segment_weight))
                    _walk(next_unit_index, next_pinyin_index, current_segments)
                    current_segments.pop()

        _walk(0, 0, [])
        if not candidate_paths:
            continue

        ranked_paths = sorted(
            candidate_paths.values(),
            key=lambda item: (
                item[0],
                -len(item[1]),
                sum(_cjk_len(seg_text) for _seg_pinyin, seg_text, _seg_weight in item[1]),
            ),
            reverse=True,
        )
        best_score, best_segments = ranked_paths[0]
        second_score = ranked_paths[1][0] if len(ranked_paths) > 1 else best_score - 180
        score_margin = best_score - second_score
        if len(ranked_paths) > 1 and score_margin < 24:
            continue

        path_weight = 76 + min(176, max(0, best_score // 6))
        path_weight += int(round(full_phrase_confidence * 170.0))
        path_weight += min(148, max(24, score_margin))
        if all(_cjk_len(seg_text) >= 2 for _seg_pinyin, seg_text, _seg_weight in best_segments):
            path_weight += 36
        path_weight = max(72, min(520, path_weight))

        best_query_pinyin = "".join(seg_pinyin for seg_pinyin, _seg_text, _seg_weight in best_segments)
        best_path_segments = [seg_text for _seg_pinyin, seg_text, _seg_weight in best_segments]
        if best_query_pinyin != full_pinyin:
            continue

        _maybe_add_prior(full_pinyin, best_path_segments, path_weight)
        stats[f"{stats_prefix}_query_path_terms_emitted"] += 1
        stats[f"{stats_prefix}_query_path_full_entries"] += 1

        prefix_query = ""
        prefix_segments: List[str] = []
        for idx, (segment_pinyin, segment_text, _segment_weight) in enumerate(best_segments):
            prefix_query += segment_pinyin
            prefix_segments.append(segment_text)
            if idx < 1 or idx >= len(best_segments) - 1:
                continue
            prefix_weight = path_weight - 44 - ((len(best_segments) - idx - 1) * 38)
            prefix_weight = max(64, min(path_weight, prefix_weight))
            if _maybe_add_prior(prefix_query, prefix_segments, prefix_weight):
                stats[f"{stats_prefix}_query_path_prefix_entries"] += 1

    return priors, stats


def _build_transition_completion_index(
    mapping: Dict[Tuple[str, str], int],
    completion_evidence: Dict[
        Tuple[str, str], Tuple[int, int, int, int, int, int, float, float, int]
    ],
    *,
    unihan_map: Dict[str, str],
    unihan_readings_map: Dict[str, Set[str]],
    unihan_source_rank_map: Dict[Tuple[str, str], int],
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int],
    stats_prefix: str,
) -> Tuple[Dict[Tuple[str, str, str, str], int], Dict[str, int]]:
    """Build a sparse, deterministic prefix-completion index.

    Runtime completion must never enumerate word combinations. This index
    contains only exact 1+2, 2+1, 2+2 and 2+3 paths that already passed the
    corpus transition collector and then pass a stricter completion gate.
    Up to six reliable alternatives are retained for each prefix so runtime
    context can resolve ambiguity without enumerating word combinations.
    """

    min_transition_score = 420
    # Ordinary short exact-pair transitions can enter the blue candidate path
    # with four independent sources. Completion is deliberately stricter, but
    # five sources still admits well-supported phrases such as `提高|很多`
    # without requiring a sixth corpus family.
    min_sources = 5
    min_direct_sources = 4
    min_direct_count = 8
    min_prefix_evidence_gap = 24
    min_prefix_count_ratio_percent = 130
    max_candidates_per_prefix = 6
    allowed_layouts = {(1, 2), (2, 1), (2, 2), (2, 3)}
    exact_keys = {
        (_normalize_compact_pinyin_key(pinyin), text)
        for (pinyin, text), weight in mapping.items()
        if weight > 0
    }
    prefix_candidates: Dict[
        str, List[Tuple[str, str, str, int, int, int]]
    ] = {}
    stats = {
        f"{stats_prefix}_transition_completion_evidence_rows": len(
            completion_evidence
        ),
        f"{stats_prefix}_transition_completion_strong_paths": 0,
        f"{stats_prefix}_transition_completion_prefix_candidates": 0,
        f"{stats_prefix}_transition_completion_rows": 0,
        f"{stats_prefix}_transition_completion_skipped_layout": 0,
        f"{stats_prefix}_transition_completion_skipped_full_exact": 0,
        f"{stats_prefix}_transition_completion_skipped_weak_evidence": 0,
        f"{stats_prefix}_transition_completion_skipped_pinyin_alignment": 0,
        f"{stats_prefix}_transition_completion_skipped_runtime_prefix_boundary": 0,
        f"{stats_prefix}_transition_completion_skipped_ambiguous_prefix": 0,
        f"{stats_prefix}_transition_completion_retained_ambiguous_prefix": 0,
    }

    for (full_pinyin, path_text), evidence_values in completion_evidence.items():
        segments = path_text.split(QUERY_PATH_FILE_SEPARATOR)
        if len(segments) != 2:
            stats[f"{stats_prefix}_transition_completion_skipped_layout"] += 1
            continue
        layout = (_cjk_len(segments[0]), _cjk_len(segments[1]))
        if layout not in allowed_layouts:
            stats[f"{stats_prefix}_transition_completion_skipped_layout"] += 1
            continue

        full_text = "".join(segments)
        normalized_full_pinyin = _normalize_compact_pinyin_key(full_pinyin)
        if (normalized_full_pinyin, full_text) in exact_keys:
            stats[f"{stats_prefix}_transition_completion_skipped_full_exact"] += 1
            continue

        (
            count,
            source_count,
            direct_count,
            direct_source_count,
            competitor_count,
            contender_rank,
            query_share,
            pmi,
            transition_score,
        ) = evidence_values
        required_count = 16 if sum(layout) >= 5 else 12
        has_strong_absolute_completion_evidence = (
            count >= max(20, required_count + 4)
            and source_count >= min_sources
            and direct_count >= max(16, required_count)
            and direct_source_count >= min_sources
            and contender_rank == 1
            and query_share >= 0.90
            and (
                competitor_count == 0
                or count * 100 >= competitor_count * 300
            )
        )
        if (
            count < required_count
            or source_count < min_sources
            or direct_count < min_direct_count
            or direct_source_count < min_direct_sources
            or contender_rank != 1
            or transition_score < min_transition_score
            or query_share < 0.70
            # PMI systematically underrates useful pairs whose two components
            # are both common (for example `提高|很多`). Counts, independent
            # sources, direct observations and prefix dominance already make
            # this gate stricter than ordinary transition admission.
            or (pmi < 0.75 and not has_strong_absolute_completion_evidence)
            or (
                competitor_count > 0
                and count * 100 < competitor_count * 160
            )
        ):
            stats[f"{stats_prefix}_transition_completion_skipped_weak_evidence"] += 1
            continue

        syllables = _split_compact_pinyin_by_unihan(
            full_text,
            normalized_full_pinyin,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if syllables is None or len(syllables) != sum(layout):
            stats[
                f"{stats_prefix}_transition_completion_skipped_pinyin_alignment"
            ] += 1
            continue

        # Preserve every syllable boundary in the payload. The runtime key is
        # still the compact typed prefix, while explicit boundaries prevent a
        # compact full spelling from being reparsed along a different path
        # (for example jin'e as ji+ne).
        canonical_full_pinyin = "'".join(syllables)

        completion_score = transition_score
        completion_score += min(88, int(round(math.log2(count + 1) * 15)))
        completion_score += min(36, source_count * 3)
        completion_score += min(24, direct_source_count * 4)
        completion_score += int(round(query_share * 24))

        total_units = len(syllables)
        first_prefix_units = max(2, total_units - 3)
        for prefix_units in range(first_prefix_units, total_units):
            typed_prefix = "".join(syllables[:prefix_units])
            if not typed_prefix:
                continue
            if _runtime_parse_compact_pinyin(typed_prefix) != syllables[:prefix_units]:
                stats[
                    f"{stats_prefix}_transition_completion_skipped_runtime_prefix_boundary"
                ] += 1
                continue
            prefix_candidates.setdefault(typed_prefix, []).append(
                (
                    canonical_full_pinyin,
                    full_text,
                    path_text,
                    completion_score,
                    count,
                    source_count,
                )
            )
            stats[
                f"{stats_prefix}_transition_completion_prefix_candidates"
            ] += 1
        stats[f"{stats_prefix}_transition_completion_strong_paths"] += 1

    output: Dict[Tuple[str, str, str, str], int] = {}
    for typed_prefix, candidates in prefix_candidates.items():
        deduplicated: Dict[
            Tuple[str, str], Tuple[str, str, str, int, int, int]
        ] = {}
        for candidate in candidates:
            key = (candidate[0], candidate[1])
            current = deduplicated.get(key)
            if current is None or (candidate[3], candidate[4], candidate[5]) > (
                current[3],
                current[4],
                current[5],
            ):
                deduplicated[key] = candidate
        ordered = sorted(
            deduplicated.values(),
            key=lambda item: (-item[3], -item[4], -item[5], item[0], item[1]),
        )
        if not ordered:
            continue
        if len(ordered) > 1:
            top = ordered[0]
            runner = ordered[1]
            if (
                top[3] - runner[3] < min_prefix_evidence_gap
                or top[4] * 100 < runner[4] * min_prefix_count_ratio_percent
            ):
                stats[
                    f"{stats_prefix}_transition_completion_retained_ambiguous_prefix"
                ] += 1
        for candidate in ordered[:max_candidates_per_prefix]:
            output[
                (typed_prefix, candidate[0], candidate[1], candidate[2])
            ] = candidate[3]

    stats[f"{stats_prefix}_transition_completion_rows"] = len(output)
    return output, stats


def _write_query_path_prior(path: pathlib.Path, mapping: Dict[Tuple[str, str], int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for (query_pinyin, path_text), weight in sorted(
            mapping.items(), key=lambda kv: (kv[0][0], kv[0][1], -kv[1])
        ):
            f.write(f"{query_pinyin}\t{path_text}\t{weight}\n")


def _write_transition_completion(
    path: pathlib.Path,
    mapping: Dict[Tuple[str, str, str, str], int],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for (typed_prefix, full_pinyin, text, path_text), evidence in sorted(
            mapping.items(),
            key=lambda item: (
                item[0][0],
                -item[1],
                item[0][1],
                item[0][2],
                item[0][3],
            ),
        ):
            f.write(
                f"{typed_prefix}\t{full_pinyin}\t{text}\t{path_text}\t{evidence}\n"
            )


def _completion_vertical_layer_kind(layer_id: str) -> int:
    """Return a compact completion-only vertical classification."""
    normalized = layer_id.strip().lower()
    if not normalized:
        return 0
    if normalized == "medicine":
        return 3
    if normalized in {"proper_nouns", "place_names"} or (
        normalized in NAMED_ENTITY_VERTICAL_LAYERS
    ):
        return 2
    return 1


def _build_completion_vertical_layer_maps(
    vertical_entries: List[VerticalEntry],
    *,
    convert_sc_to_tc: Callable[[str], str] | None = None,
) -> Tuple[Dict[str, int], Dict[str, int]]:
    sc_layers: Dict[str, int] = {}
    tc_layers: Dict[str, int] = {}
    for sc_word, tc_word, _usage, _pinyin, layer_id, _source_id in vertical_entries:
        layer_kind = _completion_vertical_layer_kind(layer_id)
        if layer_kind <= 0:
            continue
        if sc_word:
            sc_layers[sc_word] = max(sc_layers.get(sc_word, 0), layer_kind)
        tc_candidate = tc_word
        if (not tc_candidate) and convert_sc_to_tc is not None and sc_word:
            tc_candidate = convert_sc_to_tc(sc_word)
        if tc_candidate:
            tc_layers[tc_candidate] = max(
                tc_layers.get(tc_candidate, 0), layer_kind
            )
    return sc_layers, tc_layers


def _build_completion_popularity_prior(
    dictionary_path: pathlib.Path,
    *,
    usage_score_map: Dict[str, float],
    corpus_frequency_map: Dict[str, float],
    document_frequency_map: Dict[str, float],
    persistence_map: Dict[str, float],
    source_hits_map: Dict[str, int],
    vertical_layer_map: Dict[str, int],
    curated_hot_terms: Set[str],
    curated_low_terms: Set[str],
    path_score_map: Dict[str, int],
    stats_prefix: str,
) -> Tuple[Dict[Tuple[str, str], Tuple[int, int, int, int, int, int, int]], Dict[str, int]]:
    """Build a completion popularity prior without reusing dictionary weight."""

    output: Dict[Tuple[str, str], Tuple[int, int, int, int, int, int, int]] = {}
    stats = {
        f"{stats_prefix}_completion_prior_rows": 0,
        f"{stats_prefix}_completion_prior_hot_rows": 0,
        f"{stats_prefix}_completion_prior_vertical_rows": 0,
        f"{stats_prefix}_completion_prior_cold_vertical_rows": 0,
    }

    with dictionary_path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                raise ValueError(
                    f"Malformed dictionary row at {dictionary_path}:{line_number}"
                )
            pinyin = parts[0].strip()
            text = parts[1].strip()
            if not pinyin or not text:
                continue

            usage = min(1.0, max(0.0, usage_score_map.get(text, 0.0)))
            corpus = min(1.0, max(0.0, corpus_frequency_map.get(text, 0.0)))
            document = min(
                1.0, max(0.0, document_frequency_map.get(text, 0.0))
            )
            persistence = min(1.0, max(0.0, persistence_map.get(text, 0.0)))
            source_count = min(8, max(0, source_hits_map.get(text, 0)))
            layer_kind = min(3, max(0, vertical_layer_map.get(text, 0)))
            path_score = min(1000, max(0, path_score_map.get(text, 0)))

            # Completion needs a broad familiarity prior, not a copy of the
            # normal candidate weight. Shape direct corpus frequency less
            # aggressively and retain document/source consensus separately.
            corpus_component = math.sqrt(corpus)
            document_component = max(document, persistence * 0.82)
            source_component = min(1.0, float(source_count) / 3.0)
            popularity = (
                0.08
                + usage * 0.26
                + corpus_component * 0.31
                + document_component * 0.18
                + persistence * 0.07
                + source_component * 0.10
            )

            if text in curated_hot_terms:
                # Curated daily membership is useful weak evidence, but it is
                # not an independent corpus source. Only real cross-source or
                # document evidence may turn a term into a protected hot
                # completion.
                popularity += 0.06
                if source_count >= 2 or max(
                    corpus_component, document_component, persistence
                ) >= 0.10:
                    popularity = max(
                        popularity, 0.45 + min(0.10, usage * 0.10)
                    )
                layer_kind = 0
            elif text in curated_low_terms:
                popularity = max(popularity, 0.20 + min(0.20, usage * 0.20))

            vertical_penalty = 0
            if layer_kind > 0:
                base_penalty = {1: 150, 2: 240, 3: 340}[layer_kind]
                general_support = max(
                    usage * 0.85,
                    corpus_component,
                    document_component,
                    min(1.0, float(source_count) / 3.0),
                )
                # Independent general evidence can rehabilitate a vertical
                # word; a single-domain term retains most of the penalty.
                relief = min(0.90, general_support * 0.82)
                vertical_penalty = int(round(base_penalty * (1.0 - relief)))

            popularity_prior = int(round(popularity * 1000.0)) - vertical_penalty
            popularity_prior = min(1000, max(1, popularity_prior))
            corpus_score = int(round(corpus_component * 1000.0))
            document_score = int(round(document_component * 1000.0))
            value = (
                popularity_prior,
                corpus_score,
                document_score,
                source_count,
                vertical_penalty,
                layer_kind,
                path_score,
            )
            key = (pinyin, text)
            current = output.get(key)
            if current is None or value > current:
                output[key] = value

    for (
        popularity_prior,
        _corpus,
        _document,
        _sources,
        _penalty,
        layer_kind,
        _path_score,
    ) in output.values():
        if popularity_prior >= 700:
            stats[f"{stats_prefix}_completion_prior_hot_rows"] += 1
        if layer_kind > 0:
            stats[f"{stats_prefix}_completion_prior_vertical_rows"] += 1
            if popularity_prior < 300:
                stats[f"{stats_prefix}_completion_prior_cold_vertical_rows"] += 1
    stats[f"{stats_prefix}_completion_prior_rows"] = len(output)
    return output, stats


def _write_completion_popularity_prior(
    path: pathlib.Path,
    mapping: Dict[Tuple[str, str], Tuple[int, int, int, int, int, int, int]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for (pinyin, text), values in sorted(
            mapping.items(), key=lambda item: (item[0][0], -item[1][0], item[0][1])
        ):
            handle.write(
                f"{pinyin}\t{text}\t{values[0]}\t{values[1]}\t{values[2]}\t"
                f"{values[3]}\t{values[4]}\t{values[5]}\t{values[6]}\n"
            )


def _build_completion_exact_lookup(
    dictionary_path: pathlib.Path,
    completion_prior: Dict[
        Tuple[str, str], Tuple[int, int, int, int, int, int, int]
    ],
    *,
    stats_prefix: str,
    per_rank_limit: int = 8,
) -> Tuple[
    Dict[
        Tuple[str, str, str],
        Tuple[int, int, int, int, int, int, int, int, int, int],
    ],
    Dict[str, int],
]:
    """Precompute the bounded exact completion pool for every syllable prefix."""

    entries: List[Tuple[str, str, int, List[str], List[str]]] = []
    exact_keys: Set[Tuple[str, str]] = set()
    stats = {
        f"{stats_prefix}_completion_lookup_prefixes": 0,
        f"{stats_prefix}_completion_lookup_raw_rows": 0,
        f"{stats_prefix}_completion_lookup_rows": 0,
        f"{stats_prefix}_completion_lookup_anchored_rows": 0,
    }

    with dictionary_path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                raise ValueError(
                    f"Malformed dictionary row at {dictionary_path}:{line_number}"
                )
            pinyin = parts[0].strip()
            text = parts[1].strip()
            try:
                weight = int(parts[2])
            except ValueError as exc:
                raise ValueError(
                    f"Invalid dictionary weight at {dictionary_path}:{line_number}"
                ) from exc
            if not pinyin or not text or weight <= 0:
                continue
            syllables = _runtime_parse_compact_pinyin(pinyin)
            text_units = _split_text_units(text)
            # The runtime completion matcher does not expose an erhua marker
            # parsed as a standalone ``r`` syllable. Excluding it here keeps
            # the offline pool byte-for-byte equivalent to the legacy scan;
            # explicit ``er`` readings remain eligible.
            if "r" in syllables:
                continue
            if len(syllables) != len(text_units):
                continue
            compact_pinyin = _normalize_compact_pinyin_key(pinyin)
            exact_keys.add((compact_pinyin, text))
            if len(syllables) >= 3:
                entries.append((pinyin, text, weight, syllables, text_units))

    grouped: Dict[
        str,
        List[
            Tuple[
                str,
                str,
                int,
                int,
                int,
                int,
                int,
                int,
                int,
                int,
                int,
            ]
        ],
    ] = {}
    for pinyin, text, weight, syllables, text_units in entries:
        prior = completion_prior.get((pinyin, text))
        if prior is None:
            prior = completion_prior.get(
                (_normalize_compact_pinyin_key(pinyin), text),
                (0, 0, 0, 0, 0, 0, 0),
            )
        (
            popularity_prior,
            corpus_score,
            document_score,
            source_count,
            vertical_penalty,
            layer_kind,
            path_score,
        ) = prior
        for prefix_units in range(2, len(syllables)):
            typed_prefix = "".join(syllables[:prefix_units])
            prefix_text = "".join(text_units[:prefix_units])
            anchored = int((typed_prefix, prefix_text) in exact_keys)
            grouped.setdefault(typed_prefix, []).append(
                (
                    pinyin,
                    text,
                    weight,
                    popularity_prior,
                    corpus_score,
                    document_score,
                    source_count,
                    path_score,
                    vertical_penalty,
                    layer_kind,
                    anchored,
                )
            )
            stats[f"{stats_prefix}_completion_lookup_raw_rows"] += 1

    output: Dict[
        Tuple[str, str, str],
        Tuple[int, int, int, int, int, int, int, int, int, int],
    ] = {}
    for typed_prefix, candidates in grouped.items():
        deduplicated: Dict[
            Tuple[str, str],
            Tuple[str, str, int, int, int, int, int, int, int, int, int],
        ] = {}
        for candidate in candidates:
            candidate_key = (
                _normalize_compact_pinyin_key(candidate[0]),
                candidate[1],
            )
            current = deduplicated.get(candidate_key)
            if current is None or (
                candidate[2], candidate[3], candidate[10], candidate[0]
            ) > (
                current[2], current[3], current[10], current[0]
            ):
                deduplicated[candidate_key] = candidate
        candidates = list(deduplicated.values())

        def rank_key(
            candidate: Tuple[
                str, str, int, int, int, int, int, int, int, int, int
            ],
            *,
            popularity: bool,
        ) -> Tuple[int, int, str, str]:
            primary = candidate[3] if popularity else candidate[2]
            primary += 80 if candidate[10] else 0
            return (-primary, len(_split_text_units(candidate[1])), candidate[1], candidate[0])

        ranked_weight = sorted(
            candidates, key=lambda item: rank_key(item, popularity=False)
        )[:per_rank_limit]
        ranked_popularity = sorted(
            candidates, key=lambda item: rank_key(item, popularity=True)
        )[:per_rank_limit]
        selected: List[
            Tuple[str, str, int, int, int, int, int, int, int, int, int]
        ] = []
        seen: Set[Tuple[str, str]] = set()
        for candidate in ranked_weight + ranked_popularity:
            candidate_key = (
                _normalize_compact_pinyin_key(candidate[0]),
                candidate[1],
            )
            if candidate_key in seen:
                continue
            seen.add(candidate_key)
            selected.append(candidate)
        for rank_order, candidate in enumerate(selected):
            (
                full_pinyin,
                text,
                weight,
                popularity_prior,
                corpus_score,
                document_score,
                source_count,
                path_score,
                vertical_penalty,
                layer_kind,
                anchored,
            ) = candidate
            output[(typed_prefix, full_pinyin, text)] = (
                weight,
                popularity_prior,
                corpus_score,
                document_score,
                source_count,
                path_score,
                vertical_penalty,
                layer_kind,
                anchored,
                rank_order,
            )
            if anchored:
                stats[f"{stats_prefix}_completion_lookup_anchored_rows"] += 1

    stats[f"{stats_prefix}_completion_lookup_prefixes"] = len(grouped)
    stats[f"{stats_prefix}_completion_lookup_rows"] = len(output)
    return output, stats


def _write_completion_exact_lookup(
    path: pathlib.Path,
    mapping: Dict[
        Tuple[str, str, str],
        Tuple[int, int, int, int, int, int, int, int, int, int],
    ],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for (typed_prefix, full_pinyin, text), values in sorted(
            mapping.items(),
            key=lambda item: (item[0][0], item[1][9], item[0][1], item[0][2]),
        ):
            handle.write(
                f"{typed_prefix}\t{full_pinyin}\t{text}\t{values[0]}\t"
                f"{values[1]}\t{values[2]}\t{values[3]}\t{values[4]}\t"
                f"{values[5]}\t{values[6]}\t{values[7]}\t{values[8]}\t"
                f"{values[9]}\n"
            )


def _build_completion_path_score_map(
    *prior_maps: Dict[Tuple[str, str], int],
) -> Dict[str, int]:
    """Collapse corpus-trained local word paths into exact-text support."""

    output: Dict[str, int] = {}
    for priors in prior_maps:
        for (_query, path_text), weight in priors.items():
            text = path_text.replace(QUERY_PATH_FILE_SEPARATOR, "")
            if not text or QUERY_PATH_FILE_SEPARATOR not in path_text:
                continue
            output[text] = max(output.get(text, 0), int(weight))
    return output


def _filter_transition_completion_against_written_dictionary(
    mapping: Dict[Tuple[str, str, str, str], int],
    dictionary_path: pathlib.Path,
    *,
    single_char_readings_map: Dict[str, Set[str]] | None = None,
    stats_prefix: str,
) -> Tuple[Dict[Tuple[str, str, str, str], int], Dict[str, int]]:
    """Keep only completions whose two segments are exact in the final output.

    The build pipeline applies several final pinyin and visibility passes after
    transition training. Validating against the file that will actually be
    imported prevents a stale reading or a newly exact full phrase from leaking
    into the separate completion index.
    """

    exact_keys: Set[Tuple[str, str]] = set()
    pinyins_by_text: Dict[str, Set[str]] = {}
    with dictionary_path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                raise ValueError(
                    f"Malformed dictionary row at {dictionary_path}:{line_number}"
                )
            pinyin = _normalize_compact_pinyin_key(parts[0])
            text = parts[1].strip()
            try:
                weight = int(parts[2])
            except ValueError as exc:
                raise ValueError(
                    f"Invalid dictionary weight at {dictionary_path}:{line_number}"
                ) from exc
            if not pinyin or not text or weight <= 0:
                continue
            exact_keys.add((pinyin, text))
            pinyins_by_text.setdefault(text, set()).add(pinyin)

    for text, readings in (single_char_readings_map or {}).items():
        if _cjk_len(text) != 1:
            continue
        normalized_readings = {
            _normalize_compact_pinyin_key(reading)
            for reading in readings
            if _normalize_compact_pinyin_key(reading)
        }
        if normalized_readings:
            pinyins_by_text.setdefault(text, set()).update(normalized_readings)

    filtered: Dict[Tuple[str, str, str, str], int] = {}
    dropped_full_exact = 0
    dropped_component_reading = 0
    for key, evidence in mapping.items():
        typed_prefix, full_pinyin, text, path_text = key
        normalized_full_pinyin = _normalize_compact_pinyin_key(full_pinyin)
        segments = path_text.split(QUERY_PATH_FILE_SEPARATOR)
        if len(segments) != 2 or "".join(segments) != text:
            dropped_component_reading += 1
            continue
        if (normalized_full_pinyin, text) in exact_keys:
            dropped_full_exact += 1
            continue
        left_pinyins = pinyins_by_text.get(segments[0], set())
        right_pinyins = pinyins_by_text.get(segments[1], set())
        if not any(
            left_pinyin + right_pinyin == normalized_full_pinyin
            for left_pinyin in left_pinyins
            for right_pinyin in right_pinyins
        ):
            dropped_component_reading += 1
            continue
        filtered[(typed_prefix, full_pinyin, text, path_text)] = evidence

    return filtered, {
        f"{stats_prefix}_transition_completion_final_rows": len(filtered),
        f"{stats_prefix}_transition_completion_final_dropped_full_exact": (
            dropped_full_exact
        ),
        f"{stats_prefix}_transition_completion_final_dropped_component_reading": (
            dropped_component_reading
        ),
    }


def _load_query_path_prior(path: pathlib.Path | None) -> Dict[Tuple[str, str], int]:
    priors: Dict[Tuple[str, str], int] = {}
    if path is None or not path.exists():
        return priors
    with path.open("r", encoding="utf-8-sig") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                raise ValueError(f"Malformed query-path row at {path}:{line_number}")
            query_pinyin = _normalize_compact_pinyin_key(parts[0])
            path_text = parts[1].strip()
            try:
                weight = int(parts[2])
            except ValueError as exc:
                raise ValueError(
                    f"Invalid query-path weight at {path}:{line_number}"
                ) from exc
            if (
                not query_pinyin
                or len(path_text.split(QUERY_PATH_FILE_SEPARATOR)) < 2
                or weight <= 0
            ):
                raise ValueError(f"Invalid query-path row at {path}:{line_number}")
            key = (query_pinyin, path_text)
            priors[key] = max(priors.get(key, 0), weight)
    return priors


def _merge_frozen_lm_transitions(
    baseline: Dict[Tuple[str, str], int],
    trained: Dict[Tuple[str, str], int],
    *,
    stats_prefix: str,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    if not baseline:
        return dict(trained), {
            f"{stats_prefix}_lm_transition_rows": len(trained),
            f"{stats_prefix}_lm_transition_baseline_rows": 0,
            f"{stats_prefix}_lm_transition_incremental_added": len(trained),
            f"{stats_prefix}_lm_transition_frozen_reweights": 0,
        }

    merged = dict(baseline)
    incremental_added = 0
    frozen_reweights = 0
    for key, weight in trained.items():
        baseline_weight = baseline.get(key)
        if baseline_weight is not None:
            if baseline_weight != weight:
                frozen_reweights += 1
            continue
        merged[key] = weight
        incremental_added += 1
    return merged, {
        f"{stats_prefix}_lm_transition_rows": len(merged),
        f"{stats_prefix}_lm_transition_baseline_rows": len(baseline),
        f"{stats_prefix}_lm_transition_incremental_added": incremental_added,
        f"{stats_prefix}_lm_transition_frozen_reweights": frozen_reweights,
    }


def _write_manifest(path: pathlib.Path, profile: str, sources: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    lines: List[str] = [
        "version: 1",
        f'generated_at: "{generated_at}"',
        f"profile: {profile}",
        "sources:",
    ]
    for source in sources:
        lines.extend(
            [
                f"  - id: {source['id']}",
                f"    name: {source['name']}",
                f"    download_url: {source['download_url']}",
                f"    homepage: {source['homepage']}",
                f"    license: {source['license']}",
                f"    risk_level: {source['risk_level']}",
                f"    redistribution_class: {source['redistribution_class']}",
                "    attribution_required: "
                + _to_yaml_bool(bool(source["attribution_required"])),
                "    raw_committed: " + _to_yaml_bool(bool(source["raw_committed"])),
                f"    notes: {_yaml_single_quote(source['notes'])}",
            ]
        )
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _format_report_path(path: pathlib.Path) -> str:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        return str(path)


def _write_report(
    path: pathlib.Path,
    profile: str,
    sources: List[Dict[str, object]],
    output_sc: pathlib.Path,
    output_tc: pathlib.Path,
    output_query_path_sc: pathlib.Path | None,
    output_query_path_tc: pathlib.Path | None,
    output_lm_transition_sc: pathlib.Path | None,
    output_lm_transition_tc: pathlib.Path | None,
    output_transition_completion_sc: pathlib.Path | None,
    output_transition_completion_tc: pathlib.Path | None,
    stats: Dict[str, int],
    count_sc: int,
    count_tc: int,
    min_hanzi: int,
    max_entries: int,
    suspicious_sc: List[Dict[str, object]] | None = None,
) -> None:
    reason_counts: Dict[str, int] = {}
    suspicious_sc = suspicious_sc or []
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# External Build Report",
        "",
        f"- profile: {profile}",
        f"- generated_at_utc: {dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}",
        f"- min_hanzi: {min_hanzi}",
        f"- max_entries: {max_entries if max_entries > 0 else 'unlimited'}",
        "",
        "## Sources",
    ]
    for source in sources:
        lines.extend(
            [
                f"- {source['id']}: {source['name']}",
                f"  - license: {source['license']}",
                f"  - risk_level: {source['risk_level']}",
                f"  - redistribution_class: {source['redistribution_class']}",
                f"  - url: {source['download_url']}",
            ]
        )

    lines.append("")
    lines.append("## Parse stats")
    for key in sorted(stats.keys()):
        lines.append(f"- {key}: {stats[key]}")

    lines.extend(
        [
            "",
            "## Output",
            f"- sc_file: {_format_report_path(output_sc)}",
            f"- tc_file: {_format_report_path(output_tc)}",
            f"- sc_entries: {count_sc}",
            f"- tc_entries: {count_tc}",
            f"- suspicious_sc_entries: {len(suspicious_sc)}",
            "",
        ]
    )
    if output_query_path_sc is not None:
        lines.append(f"- sc_query_path_file: {_format_report_path(output_query_path_sc)}")
    if output_query_path_tc is not None:
        lines.append(f"- tc_query_path_file: {_format_report_path(output_query_path_tc)}")
    if output_lm_transition_sc is not None:
        lines.append(f"- sc_lm_transition_file: {_format_report_path(output_lm_transition_sc)}")
    if output_lm_transition_tc is not None:
        lines.append(f"- tc_lm_transition_file: {_format_report_path(output_lm_transition_tc)}")
    if output_transition_completion_sc is not None:
        lines.append(
            "- sc_transition_completion_file: "
            f"{_format_report_path(output_transition_completion_sc)}"
        )
    if output_transition_completion_tc is not None:
        lines.append(
            "- tc_transition_completion_file: "
            f"{_format_report_path(output_transition_completion_tc)}"
        )
    if any(
        path is not None
        for path in (
            output_query_path_sc,
            output_query_path_tc,
            output_lm_transition_sc,
            output_lm_transition_tc,
            output_transition_completion_sc,
            output_transition_completion_tc,
        )
    ):
        lines.append("")

    if suspicious_sc:
        for item in suspicious_sc:
            for reason in str(item.get("reasons", "")).split(","):
                reason = reason.strip()
                if not reason:
                    continue
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

        if reason_counts:
            lines.append("## Suspicious SC Reason Summary")
            lines.append("")
            for reason, count in sorted(
                reason_counts.items(),
                key=lambda item: (item[1], item[0]),
                reverse=True,
            ):
                lines.append(f"- {reason}: {count}")
            lines.append("")

        lines.append("## Suspicious High-Weight SC Entries")
        lines.append("")
        lines.append(
            "| text | pinyin | weight | risk_score | modernity_risk | usage | jieba | pageviews | source_hits | char_score | pos | reasons |"
        )
        lines.append(
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |"
        )
        for item in suspicious_sc:
            lines.append(
                "| {text} | {pinyin} | {weight} | {risk_score} | {modernity_risk} | {usage:.3f} | {jieba:.3f} |"
                " {pageviews:.3f} | {source_hits} | {char_score:.3f} | {pos} | {reasons} |".format(**item)
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _resolve_profile_config(args: argparse.Namespace) -> Dict[str, object]:
    if args.profile not in PROFILE_DEFAULTS:
        known = ", ".join(sorted(PROFILE_DEFAULTS.keys()))
        raise ValueError(f"unknown profile '{args.profile}', expected one of: {known}")

    base = PROFILE_DEFAULTS[args.profile]
    config: Dict[str, object] = {
        "parser": base["parser"],
        "sources": [dict(item) for item in base["sources"]],  # deep copy for source dicts
    }
    sources: List[Dict[str, object]] = config["sources"]  # type: ignore[assignment]
    if not sources:
        raise ValueError(f"profile '{args.profile}' has no sources configured")

    # Apply optional source overrides to primary source only.
    primary = sources[0]
    override_pairs = (
        ("download_url", args.source_url),
        ("id", args.source_id),
        ("name", args.source_name),
        ("homepage", args.source_homepage),
        ("license", args.source_license),
        ("risk_level", args.risk_level),
        ("redistribution_class", args.redistribution_class),
        ("notes", args.source_notes),
    )
    for key, value in override_pairs:
        if value:
            primary[key] = value
    if args.attribution_required:
        primary["attribution_required"] = _parse_bool(args.attribution_required)

    required_keys = (
        "id",
        "name",
        "download_url",
        "homepage",
        "license",
        "risk_level",
        "redistribution_class",
        "notes",
    )
    for source in sources:
        for key in required_keys:
            if not str(source.get(key, "")).strip():
                raise ValueError(f"profile '{args.profile}' source requires key '{key}'")

    if args.profile == "clean_permissive":
        for source in sources:
            license_lower = str(source["license"]).lower()
            if any(token in license_lower for token in COPYLEFT_LICENSE_TOKENS):
                raise ValueError(
                    "clean_permissive profile rejects copyleft/share-alike licenses; "
                    f"got '{source['license']}' in source {source['id']}"
                )
            if str(source.get("redistribution_class", "")).lower() != "permissive":
                raise ValueError(
                    "clean_permissive profile requires redistribution_class=permissive"
                )
            if str(source.get("risk_level", "")).lower() != "low":
                raise ValueError("clean_permissive profile requires risk_level=low")

    return config


def _resolve_cache_source_id(
    parser_name: str, sources: List[Dict[str, object]], explicit_source_id: str
) -> str:
    if not sources:
        raise ValueError("no sources configured for cache resolution")

    known_ids = [str(item.get("id", "")) for item in sources if str(item.get("id", "")).strip()]
    if not known_ids:
        raise ValueError("all sources are missing non-empty id")

    if explicit_source_id:
        if explicit_source_id not in known_ids:
            raise ValueError(
                f"--cache-source-id '{explicit_source_id}' not found in current profile sources: "
                + ", ".join(known_ids)
            )
        return explicit_source_id

    preferred_by_parser = {
        "cedict": "cc-cedict",
        "cedict_thuocl_jieba_opencc_unihan_wiki": "cc-cedict",
        "opencc_unihan": "opencc-stphrases",
        "unihan_only": "unicode-unihan-readings",
    }
    preferred = preferred_by_parser.get(parser_name, "")
    if preferred and preferred in known_ids:
        return preferred

    return known_ids[0]


def _require_source_payload(
    payload_map: Dict[str, bytes],
    sources: List[Dict[str, object]],
    *,
    role: str,
    source_id: str,
    download_url: str,
) -> bytes:
    source: Dict[str, object] | None = None
    for candidate in sources:
        if str(candidate.get("id", "")) == source_id:
            source = candidate
            break

    if source is None:
        for candidate in sources:
            if str(candidate.get("download_url", "")) == download_url:
                source = candidate
                break

    if source is None:
        raise ValueError(
            f"missing source payload for role '{role}' "
            f"(id='{source_id}', url='{download_url}')"
        )

    payload_key = str(source.get("id", ""))
    payload = payload_map.get(payload_key)
    if payload is None:
        raise ValueError(
            f"missing payload bytes for role '{role}' source id '{payload_key}'"
    )
    return payload


def _require_source_config(
    sources: List[Dict[str, object]],
    *,
    role: str,
    source_id: str,
    download_url: str,
) -> Dict[str, object]:
    for candidate in sources:
        if str(candidate.get("id", "")) == source_id:
            return candidate
    for candidate in sources:
        if str(candidate.get("download_url", "")) == download_url:
            return candidate
    raise ValueError(
        f"missing source config for role '{role}' (id='{source_id}', url='{download_url}')"
    )


def _load_vertical_source_entries(
    source: Dict[str, object],
    payload_map: Dict[str, bytes],
    vertical_payload_map: Dict[str, bytes],
    min_hanzi: int,
    repo_root: pathlib.Path,
) -> Tuple[List[VerticalEntry], Dict[str, int]]:
    source_type = str(source.get("vertical_source_type", "repo_tsv")).strip().lower()
    default_usage_score = float(source.get("vertical_default_usage_score", 0.72))
    if source_type == "repo_tsv":
        payload = vertical_payload_map.get(str(source.get("id", "")).strip())
        if payload is None:
            payload = _read_source_bytes(
                _build_vertical_source_request_url(source),
                _resolve_optional_repo_path(repo_root, str(source.get("vertical_cache_file", ""))),
                repo_root=repo_root,
            )
        entries, stats = _parse_vertical_term_entries(payload, min_hanzi, default_usage_score)
        return _wrap_vertical_entries(entries, source), stats
    if source_type == "thuocl_zip_member":
        payload_source_id = str(source.get("vertical_payload_source_id", "")).strip()
        stats = {
            "vertical_terms_missing_payload_source": 0,
            "vertical_terms_fallback_downloads": 0,
        }
        payload = payload_map.get(payload_source_id) if payload_source_id else None
        if payload is None:
            base_url = urllib.parse.urldefrag(str(source.get("download_url", "")).strip())[0]
            if not base_url:
                stats["vertical_terms_missing_payload_source"] += 1
                return [], stats
            payload = _read_source_bytes(base_url, None, repo_root=repo_root)
            stats["vertical_terms_fallback_downloads"] += 1
        entries, parse_stats = _parse_vertical_thuocl_member_entries(
            payload,
            str(source.get("vertical_member_name", "")),
            min_hanzi,
            default_usage_score,
            str(source.get("vertical_filter_id", "")),
        )
        return _wrap_vertical_entries(entries, source), parse_stats
    if source_type == "mesh_descriptor_catalog":
        payload = vertical_payload_map.get(str(source.get("id", "")).strip())
        if payload is None:
            return [], {"vertical_mesh_missing_payload": 1}
        _allowed_ids, stats = _parse_mesh_descriptor_allowed_ids(
            payload,
            allowed_prefixes=tuple(
                part.strip().upper()
                for part in str(source.get("vertical_mesh_tree_prefixes", "")).split(",")
                if part.strip()
            )
            or MEDICAL_MESH_TREE_PREFIXES,
        )
        return [], stats
    if source_type == "wikidata_mesh_query":
        payload = vertical_payload_map.get(str(source.get("id", "")).strip())
        mesh_source_id = str(source.get("vertical_mesh_source_id", "")).strip()
        mesh_payload = vertical_payload_map.get(mesh_source_id) if mesh_source_id else None
        opencc_payload = payload_map.get("opencc-stphrases")
        if payload is None:
            return [], {"vertical_wikidata_missing_payload": 1}
        entries, parse_stats = _parse_wikidata_mesh_query_entries(
            payload,
            mesh_payload,
            opencc_payload,
            min_hanzi,
            default_usage_score,
            tuple(
                part.strip().upper()
                for part in str(source.get("vertical_mesh_tree_prefixes", "")).split(",")
                if part.strip()
            )
            or MEDICAL_MESH_TREE_PREFIXES,
        )
        return _wrap_vertical_entries(entries, source), parse_stats
    if source_type == "wikidata_term_query":
        payload = vertical_payload_map.get(str(source.get("id", "")).strip())
        opencc_payload = payload_map.get("opencc-stphrases")
        if payload is None:
            return [], {"vertical_wikidata_term_missing_payload": 1}
        entries, parse_stats = _parse_wikidata_term_query_entries(
            payload,
            opencc_payload,
            min_hanzi,
            default_usage_score,
            str(source.get("vertical_filter_id", "")).strip(),
            max(min_hanzi, int(source.get("vertical_max_hanzi", 12) or 12)),
        )
        return _wrap_vertical_entries(entries, source), parse_stats
    if source_type == "sparql_term_query":
        payload = vertical_payload_map.get(str(source.get("id", "")).strip())
        opencc_payload = payload_map.get("opencc-stphrases")
        if payload is None:
            return [], {"vertical_sparql_term_missing_payload": 1}
        entries, parse_stats = _parse_wikidata_term_query_entries(
            payload,
            opencc_payload,
            min_hanzi,
            default_usage_score,
            str(source.get("vertical_filter_id", "")).strip(),
            max(min_hanzi, int(source.get("vertical_max_hanzi", 12) or 12)),
        )
        return _wrap_vertical_entries(entries, source), parse_stats
    if source_type == "payload_titles_filter":
        payload_source_id = str(source.get("vertical_payload_source_id", "")).strip()
        payload = vertical_payload_map.get(str(source.get("id", "")).strip())
        if payload is None and payload_source_id:
            payload = payload_map.get(payload_source_id)
        if payload is None:
            payload = _read_source_bytes(
                _build_vertical_source_request_url(source),
                _resolve_optional_repo_path(repo_root, str(source.get("vertical_cache_file", ""))),
                repo_root=repo_root,
            )
        opencc_payload = payload_map.get("opencc-stphrases")
        entries, parse_stats = _parse_payload_titles_filter_entries(
            payload,
            opencc_payload,
            min_hanzi,
            default_usage_score,
            str(source.get("vertical_filter_id", "")).strip(),
            max(min_hanzi, int(source.get("vertical_max_hanzi", 8) or 8)),
        )
        return _wrap_vertical_entries(entries, source), parse_stats
    if source_type == "godot_searchindex_titles":
        payload = vertical_payload_map.get(str(source.get("id", "")).strip())
        if payload is None:
            payload = _read_source_bytes(
                _build_vertical_source_request_url(source),
                _resolve_optional_repo_path(repo_root, str(source.get("vertical_cache_file", ""))),
                repo_root=repo_root,
            )
        opencc_payload = payload_map.get("opencc-stphrases")
        entries, parse_stats = _parse_godot_searchindex_entries(
            payload,
            opencc_payload,
            min_hanzi,
            default_usage_score,
            str(source.get("vertical_filter_id", "")).strip(),
            max(min_hanzi, int(source.get("vertical_max_hanzi", 10) or 10)),
        )
        return _wrap_vertical_entries(entries, source), parse_stats
    return [], {"vertical_terms_unsupported_source_type": 1}


def _collect_vertical_term_sets(
    entries: List[VerticalEntry]
) -> Tuple[Set[str], Set[str]]:
    sc_terms: Set[str] = set()
    tc_terms: Set[str] = set()
    for sc_text, tc_text, _usage_score, _explicit_pinyin, _layer_id, _source_id in entries:
        if _cjk_len(sc_text) >= 2 and CJK_FULL_RE.fullmatch(sc_text):
            sc_terms.add(sc_text)
        if _cjk_len(tc_text) >= 2 and CJK_FULL_RE.fullmatch(tc_text):
            tc_terms.add(tc_text)
    return sc_terms, tc_terms


def _remove_known_incorrect_jiancha_entries(
    sc_map: Dict[Tuple[str, str], int],
    tc_map: Dict[Tuple[str, str], int],
) -> Dict[str, int]:
    stats = {
        "known_incorrect_jiancha_entries_removed_sc": 0,
        "known_incorrect_jiancha_entries_removed_tc": 0,
        "known_incorrect_lexical_entries_removed_sc": 0,
        "known_incorrect_lexical_entries_removed_tc": 0,
        "script_specific_variant_capped_sc": 0,
        "script_specific_variant_removed_tc": 0,
    }
    sc_blocklist = {
        ("houjingjianchashu", "喉镜检察术"),
        ("jianchashidengdai", "监察式等待"),
        ("kunchongjiancha", "昆虫奸察"),
        ("linchuangjianchaqi", "临床监察期"),
        ("shenjingxuejiancha", "神经学检察"),
    }
    tc_blocklist = {
        ("houjingjianchashu", "喉鏡檢察術"),
        ("jianchashidengdai", "監察式等待"),
        ("kunchongjiancha", "昆蟲奸察"),
        ("linchuangjianchaqi", "臨床監察期"),
        ("shenjingxuejiancha", "神經學檢察"),
    }

    sc_lexical_blocklist = {
        ("guibao", "硅宝"),
        ("haoxiang", "好象"),
        ("jieyue", "阶越"),
        ("jieyuexingchen", "阶越星辰"),
        ("mabei", "马贝"),
        ("taoxi", "陶熙"),
    }
    tc_lexical_blocklist = {
        ("guibao", "硅寶"),
        ("haoxiang", "好象"),
        ("jieyue", "階越"),
        ("jieyuexingchen", "階越星辰"),
        ("mabei", "馬貝"),
        ("taoxi", "陶熙"),
    }
    sc_variant_caps = {
        # In simplified Chinese, standalone `象` is uncommon in modern IME use;
        # keep compound words such as `大象`/`象棋` intact, but do not let the
        # single character compete with everyday `xiang` characters such as
        # `像`/`想`/`向`.
        ("xiang", "象"): 220,
        ("xiangxiang", "想像"): 360,
        ("xiangxiangli", "想像力"): 360,
    }

    for key in sc_blocklist:
        if key in sc_map:
            del sc_map[key]
            stats["known_incorrect_jiancha_entries_removed_sc"] += 1
    for key in tc_blocklist:
        if key in tc_map:
            del tc_map[key]
            stats["known_incorrect_jiancha_entries_removed_tc"] += 1
    for key in sc_lexical_blocklist:
        if key in sc_map:
            del sc_map[key]
            stats["known_incorrect_lexical_entries_removed_sc"] += 1
    for key in tc_lexical_blocklist:
        if key in tc_map:
            del tc_map[key]
            stats["known_incorrect_lexical_entries_removed_tc"] += 1

    for key, cap in sc_variant_caps.items():
        weight = sc_map.get(key)
        if weight is not None and weight > cap:
            sc_map[key] = cap
            stats["script_specific_variant_capped_sc"] += 1
    for key in {("xiangxiang", "想象"), ("xiangxiangli", "想象力")}:
        if key in tc_map:
            del tc_map[key]
            stats["script_specific_variant_removed_tc"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build dictionary seed files from external data sources."
    )
    parser.add_argument(
        "--profile",
        default="external_broad",
        choices=sorted(PROFILE_DEFAULTS.keys()),
    )
    parser.add_argument("--source-url", default="")
    parser.add_argument("--source-id", default="")
    parser.add_argument("--source-name", default="")
    parser.add_argument("--source-homepage", default="")
    parser.add_argument("--source-license", default="")
    parser.add_argument("--risk-level", default="")
    parser.add_argument("--redistribution-class", default="")
    parser.add_argument(
        "--attribution-required",
        default="",
        help="Optional bool override for primary source: true/false.",
    )
    parser.add_argument("--source-notes", default="")
    parser.add_argument(
        "--cache-file",
        default="",
        help="Optional local cache file. Bound to --cache-source-id "
        "(or profile default source role when omitted).",
    )
    parser.add_argument(
        "--cache-source-id",
        default="",
        help="Optional source id to bind --cache-file to (for example: cc-cedict).",
    )
    parser.add_argument("--output-sc", default="data/generated/dict_clean_sc.txt")
    parser.add_argument("--output-tc", default="data/generated/dict_clean_tc.txt")
    parser.add_argument("--query-path-output-sc", default="")
    parser.add_argument("--query-path-output-tc", default="")
    parser.add_argument("--lm-transition-output-sc", default="")
    parser.add_argument("--lm-transition-output-tc", default="")
    parser.add_argument("--transition-completion-output-sc", default="")
    parser.add_argument("--transition-completion-output-tc", default="")
    parser.add_argument("--completion-prior-output-sc", default="")
    parser.add_argument("--completion-prior-output-tc", default="")
    parser.add_argument("--completion-lookup-output-sc", default="")
    parser.add_argument("--completion-lookup-output-tc", default="")
    parser.add_argument(
        "--lm-transition-base-sc",
        default="",
        help="Optional frozen simplified LM baseline. Existing transition weights are preserved.",
    )
    parser.add_argument(
        "--lm-transition-base-tc",
        default="",
        help="Optional frozen traditional LM baseline. Existing transition weights are preserved.",
    )
    parser.add_argument(
        "--query-path-lm-corpus-dir",
        default="",
        help="Optional internal plain-text corpus directory for conservative query-path transition priors.",
    )
    parser.add_argument(
        "--lm-transition-exact-pairs-only",
        action="store_true",
        help=(
            "Stream the corpus and train only exact 1+2/2+1/2+2/2+3/3+2 "
            "transition additions against the frozen LM baseline."
        ),
    )
    parser.add_argument(
        "--lm-transition-general-only",
        action="store_true",
        help=(
            "Stream the corpus and train only the general confidence-weighted "
            "word bigram/trigram transitions against the frozen LM baseline."
        ),
    )
    parser.add_argument("--support-dict-sc", default="")
    parser.add_argument("--support-dict-tc", default="")
    parser.add_argument(
        "--refresh-unihan-single-char-weights",
        action="store_true",
        help=(
            "Allow the unihan_single profile to recalculate weights of existing "
            "single-character rows. By default only new rows are learned."
        ),
    )
    parser.add_argument("--manifest", default="manifests/sources.public.yml")
    parser.add_argument("--report", default="reports/external_build_report.md")
    parser.add_argument(
        "--vertical-manifest",
        default=VERTICAL_LAYERS_MANIFEST_DEFAULT,
        help="Optional JSON manifest that defines isolated vertical terminology layers.",
    )
    parser.add_argument(
        "--pinyin-overrides",
        default=DEFAULT_PINYIN_OVERRIDES,
        help="Optional word-level pinyin override TSV: text<TAB>pinyin",
    )
    parser.add_argument("--min-hanzi", type=int, default=2)
    parser.add_argument(
        "--max-entries",
        type=int,
        default=0,
        help="Limit output entries per script. 0 means unlimited.",
    )
    parser.add_argument(
        "--pageviews-months",
        type=int,
        default=6,
        help="Number of recent complete months for Wikimedia pageviews-top aggregation.",
    )
    parser.add_argument(
        "--pageviews-max-rank",
        type=int,
        default=1000,
        help="Per-month pageviews rank cutoff (1..1000).",
    )
    args = parser.parse_args()

    repo_root = pathlib.Path(__file__).resolve().parents[1]
    output_sc = repo_root / args.output_sc
    output_tc = repo_root / args.output_tc
    output_query_path_sc = (
        repo_root / args.query_path_output_sc if args.query_path_output_sc else None
    )
    output_query_path_tc = (
        repo_root / args.query_path_output_tc if args.query_path_output_tc else None
    )
    output_lm_transition_sc = (
        repo_root / args.lm_transition_output_sc if args.lm_transition_output_sc else None
    )
    output_lm_transition_tc = (
        repo_root / args.lm_transition_output_tc if args.lm_transition_output_tc else None
    )
    output_transition_completion_sc = (
        repo_root / args.transition_completion_output_sc
        if args.transition_completion_output_sc
        else None
    )
    output_transition_completion_tc = (
        repo_root / args.transition_completion_output_tc
        if args.transition_completion_output_tc
        else None
    )
    output_completion_prior_sc = (
        repo_root / args.completion_prior_output_sc
        if args.completion_prior_output_sc
        else None
    )
    output_completion_prior_tc = (
        repo_root / args.completion_prior_output_tc
        if args.completion_prior_output_tc
        else None
    )
    output_completion_lookup_sc = (
        repo_root / args.completion_lookup_output_sc
        if args.completion_lookup_output_sc
        else None
    )
    output_completion_lookup_tc = (
        repo_root / args.completion_lookup_output_tc
        if args.completion_lookup_output_tc
        else None
    )
    lm_transition_base_sc = (
        repo_root / args.lm_transition_base_sc if args.lm_transition_base_sc else None
    )
    lm_transition_base_tc = (
        repo_root / args.lm_transition_base_tc if args.lm_transition_base_tc else None
    )
    baseline_lm_transition_sc = _load_query_path_prior(lm_transition_base_sc)
    baseline_lm_transition_tc = _load_query_path_prior(lm_transition_base_tc)
    previous_snapshot_sc = _load_existing_dict_snapshot(output_sc)
    previous_snapshot_tc = _load_existing_dict_snapshot(output_tc)
    support_dict_sc = repo_root / args.support_dict_sc if args.support_dict_sc else None
    support_dict_tc = repo_root / args.support_dict_tc if args.support_dict_tc else None
    support_single_char_sc_map = {
        key: weight
        for key, weight in (
            _load_existing_dict_snapshot(support_dict_sc)
            if support_dict_sc is not None
            else {}
        ).items()
        if _cjk_len(key[1]) == 1
    }
    support_single_char_tc_map = {
        key: weight
        for key, weight in (
            _load_existing_dict_snapshot(support_dict_tc)
            if support_dict_tc is not None
            else {}
        ).items()
        if _cjk_len(key[1]) == 1
    }
    manifest = repo_root / args.manifest
    report = repo_root / args.report
    vertical_manifest = repo_root / args.vertical_manifest if args.vertical_manifest else None
    if args.pageviews_months < 0:
        raise ValueError("--pageviews-months must be >= 0")
    if args.pageviews_max_rank <= 0:
        raise ValueError("--pageviews-max-rank must be > 0")

    profile_config = _resolve_profile_config(args)
    parser_name = str(profile_config["parser"])
    sources: List[Dict[str, object]] = profile_config["sources"]  # type: ignore[assignment]
    vertical_manifest_stats: Dict[str, int] = {}
    vertical_source_configs: List[Dict[str, object]] = []
    vertical_payload_map: Dict[str, bytes] = {}
    word_pinyin_overrides: Dict[str, str] = {}
    if args.pinyin_overrides:
        word_pinyin_overrides = _load_pinyin_overrides(repo_root / args.pinyin_overrides)
    output_unihan_map: Dict[str, str] = {}
    output_unihan_readings_map: Dict[str, Set[str]] = {}
    output_unihan_source_rank_map: Dict[Tuple[str, str], int] = {}
    output_unihan_pinlu_detail_map: Dict[Tuple[str, str], int] = {}
    if (
        vertical_manifest is not None
        and parser_name in {"cedict", "cedict_thuocl_jieba_opencc_unihan_wiki", "unihan_only"}
    ):
        vertical_source_configs, vertical_manifest_stats = _load_vertical_layer_sources(
            vertical_manifest
        )
        vertical_payload_map = _prefetch_vertical_source_payloads(vertical_source_configs, repo_root)
        if parser_name in {"cedict", "cedict_thuocl_jieba_opencc_unihan_wiki"}:
            sources.extend(
                [
                    source
                    for source in vertical_source_configs
                    if str(source.get("vertical_source_type", "repo_tsv")).strip().lower() == "repo_tsv"
                ]
            )

    payload_map: Dict[str, bytes] = {}
    usage_score_map: Dict[str, float] = {}
    source_hits_map: Dict[str, int] = {}
    jieba_direct_signal_map: Dict[str, float] = {}
    thuocl_corroborated_signal_map: Dict[str, float] = {}
    jieba_pos_map: Dict[str, str] = {}
    char_frequency_prior: Dict[str, float] = {}
    pageviews_signal_map: Dict[str, float] = {}
    pageviews_persistence_signal_map: Dict[str, float] = {}
    pageviews_burst_signal_map: Dict[str, float] = {}
    thuocl_signal_map: Dict[str, float] = {}
    wiki_titles: Set[str] = set()
    wiktionary_titles: Set[str] = set()
    wiki_alias_sc_terms: Set[str] = set()
    wiki_alias_tc_terms: Set[str] = set()
    lexical_seed_sc_terms: Set[str] = set()
    lexical_seed_tc_terms: Set[str] = set()
    wiki_proper_sc_terms: Set[str] = set()
    wiki_proper_tc_terms: Set[str] = set()
    curated_daily_sc_terms: Set[str] = set()
    curated_daily_tc_terms: Set[str] = set()
    single_char_frequency_map: Dict[str, float] = {}
    tc_single_char_frequency_map: Dict[str, float] = {}
    single_char_pos_map: Dict[str, str] = {}
    tc_single_char_pos_map: Dict[str, str] = {}
    curated_daily_entries: List[Tuple[str, str, float, str]] = []
    curated_daily_parse_stats: Dict[str, int] = {}
    curated_daily_supplement_sc_terms: Set[str] = set()
    curated_daily_supplement_tc_terms: Set[str] = set()
    curated_daily_supplement_entries: List[Tuple[str, str, float, str]] = []
    curated_daily_post_rank_exact_entries: List[Tuple[str, str, float, str]] = []
    contains_popularity_excluded_sc_terms: Set[str] = set()
    contains_popularity_excluded_tc_terms: Set[str] = set()
    curated_daily_supplement_parse_stats: Dict[str, int] = {}
    curated_usage_score_map: Dict[str, float] = {}
    curated_source_hits_map: Dict[str, int] = {}
    curated_tc_usage_score_map: Dict[str, float] = {}
    curated_tc_source_hits_map: Dict[str, int] = {}
    curated_daily_stats: Dict[str, int] = {}
    curated_daily_supplement_stats: Dict[str, int] = {}
    admin_place_alias_sc_terms: Set[str] = set()
    admin_place_alias_tc_terms: Set[str] = set()
    vertical_sc_terms: Set[str] = set()
    vertical_tc_terms: Set[str] = set()
    civic_sc_terms: Set[str] = set()
    civic_tc_terms: Set[str] = set()
    tc_usage_score_map: Dict[str, float] = {}
    tc_source_hits_map: Dict[str, int] = {}
    tc_jieba_direct_signal_map: Dict[str, float] = {}
    tc_jieba_pos_map: Dict[str, str] = {}
    tc_char_frequency_prior: Dict[str, float] = {}
    tc_pageviews_signal_map: Dict[str, float] = {}
    tc_pageviews_persistence_signal_map: Dict[str, float] = {}
    tc_pageviews_burst_signal_map: Dict[str, float] = {}
    tc_thuocl_signal_map: Dict[str, float] = {}
    vertical_entries: List[VerticalEntry] = []
    sc_family_term_count_map: Dict[str, int] = {}
    sc_family_support_sum_map: Dict[str, float] = {}
    tc_family_term_count_map: Dict[str, int] = {}
    tc_family_support_sum_map: Dict[str, float] = {}
    sc_visibility_family_term_count_map: Dict[str, int] = {}
    tc_visibility_family_term_count_map: Dict[str, int] = {}
    sc_reading_term_count_map: Dict[Tuple[str, str], int] = {}
    sc_reading_support_sum_map: Dict[Tuple[str, str], float] = {}
    tc_reading_term_count_map: Dict[Tuple[str, str], int] = {}
    tc_reading_support_sum_map: Dict[Tuple[str, str], float] = {}
    sc_visibility_reading_term_count_map: Dict[Tuple[str, str], int] = {}
    sc_visibility_reading_support_sum_map: Dict[Tuple[str, str], float] = {}
    tc_visibility_reading_term_count_map: Dict[Tuple[str, str], int] = {}
    tc_visibility_reading_support_sum_map: Dict[Tuple[str, str], float] = {}
    sc_inferred_reading_term_count_map: Dict[Tuple[str, str], int] = {}
    sc_inferred_reading_support_sum_map: Dict[Tuple[str, str], float] = {}
    tc_inferred_reading_term_count_map: Dict[Tuple[str, str], int] = {}
    tc_inferred_reading_support_sum_map: Dict[Tuple[str, str], float] = {}
    sc_visibility_inferred_reading_term_count_map: Dict[Tuple[str, str], int] = {}
    sc_visibility_inferred_reading_support_sum_map: Dict[Tuple[str, str], float] = {}
    tc_visibility_inferred_reading_term_count_map: Dict[Tuple[str, str], int] = {}
    tc_visibility_inferred_reading_support_sum_map: Dict[Tuple[str, str], float] = {}
    admin_place_alias_stats = {
        "admin_place_alias_source_terms": 0,
        "admin_place_alias_skipped_short": 0,
        "admin_place_alias_skipped_existing": 0,
        "admin_place_alias_skipped_no_pinyin": 0,
        "admin_place_alias_added_sc": 0,
        "admin_place_alias_boosted_sc": 0,
        "admin_place_alias_added_tc": 0,
        "admin_place_alias_boosted_tc": 0,
    }
    sc_leading_term_count_map: Dict[Tuple[str, str], int] = {}
    sc_leading_support_sum_map: Dict[Tuple[str, str], float] = {}
    tc_leading_term_count_map: Dict[Tuple[str, str], int] = {}
    tc_leading_support_sum_map: Dict[Tuple[str, str], float] = {}
    tc_to_sc_map: Dict[str, Set[str]] = {}
    cedict_style_penalty_map: Dict[Tuple[str, str], int] = {}
    cedict_semantic_bonus_map: Dict[Tuple[str, str], int] = {}
    unihan_map: Dict[str, str] = {}
    unihan_readings_map: Dict[str, Set[str]] = {}
    unihan_reading_source_map: Dict[Tuple[str, str], int] = {}
    unihan_pinlu_map: Dict[str, int] = {}
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] = {}
    curated_unihan_map: Dict[str, str] = {}
    curated_unihan_readings_map: Dict[str, Set[str]] = {}
    curated_unihan_source_rank_map: Dict[Tuple[str, str], int] = {}
    curated_unihan_pinlu_detail_map: Dict[Tuple[str, str], int] = {}
    primary_cache = repo_root / args.cache_file if args.cache_file else None
    cache_source_id = ""
    if primary_cache is not None:
        cache_source_id = _resolve_cache_source_id(parser_name, sources, args.cache_source_id)
    for source in sources:
        source_id = str(source["id"])
        if source_id in payload_map:
            raise ValueError(f"duplicate source id in profile '{args.profile}': {source_id}")
        if source_id == "wikimedia-pageviews-top":
            # This source is fetched via monthly API calls with dedicated local cache files.
            continue
        cache_file = primary_cache if (primary_cache is not None and source_id == cache_source_id) else None
        payload = _read_source_bytes(str(source["download_url"]), cache_file, repo_root=repo_root)
        payload_map[source_id] = payload

    if parser_name == "cedict":
        primary_source_id = str(sources[0]["id"])
        source_payload = payload_map[primary_source_id]
        source_text = _decode_text(source_payload)
        (
            sc_map,
            tc_map,
            stats,
            cedict_style_penalty_map,
            cedict_semantic_bonus_map,
        ) = _parse_cedict_entries(source_text, args.min_hanzi)
        source_ids = {str(source.get("id", "")) for source in sources}
        if (
            "project-curated-daily-phrases" in source_ids
            and "unicode-unihan-readings" in source_ids
        ):
            curated_daily_payload = _require_source_payload(
                payload_map,
                sources,
                role="project-curated-daily-phrases",
                source_id="project-curated-daily-phrases",
                download_url=CURATED_DAILY_PHRASES_URL,
            )
            unihan_payload = _require_source_payload(
                payload_map,
                sources,
                role="unicode-unihan-readings",
                source_id="unicode-unihan-readings",
                download_url=UNICODE_UNIHAN_URL,
            )
            curated_daily_entries, curated_daily_parse_stats = _parse_curated_daily_phrase_entries(
                curated_daily_payload,
                args.min_hanzi,
            )
            excluded_sc, excluded_tc = _parse_curated_contains_popularity_exclusions(
                curated_daily_payload
            )
            contains_popularity_excluded_sc_terms.update(excluded_sc)
            contains_popularity_excluded_tc_terms.update(excluded_tc)
            if "project-curated-daily-supplement-phrases" in source_ids:
                curated_daily_supplement_payload = _require_source_payload(
                    payload_map,
                    sources,
                    role="project-curated-daily-supplement-phrases",
                    source_id="project-curated-daily-supplement-phrases",
                    download_url=CURATED_DAILY_SUPPLEMENT_PHRASES_URL,
                )
                (
                    curated_daily_supplement_entries,
                    curated_daily_supplement_parse_stats,
                ) = _parse_curated_daily_phrase_entries(
                    curated_daily_supplement_payload,
                    args.min_hanzi,
                    stats_prefix="curated_daily_supplement_phrase",
                )
                excluded_sc, excluded_tc = _parse_curated_contains_popularity_exclusions(
                    curated_daily_supplement_payload
                )
                contains_popularity_excluded_sc_terms.update(excluded_sc)
                contains_popularity_excluded_tc_terms.update(excluded_tc)
                (
                    curated_daily_supplement_entries,
                    curated_daily_post_rank_exact_entries,
                ) = _partition_curated_daily_post_rank_exact_entries(
                    curated_daily_supplement_entries
                )
                curated_daily_supplement_parse_stats[
                    "curated_daily_supplement_phrase_post_rank_exact"
                ] = len(curated_daily_post_rank_exact_entries)
            (
                curated_unihan_map,
                curated_unihan_readings_map,
                curated_unihan_source_rank_map,
                _curated_unihan_pinlu_map,
                curated_unihan_pinlu_detail_map,
            ) = _load_unihan_readings_detail(unihan_payload)
            output_unihan_map = curated_unihan_map
            output_unihan_readings_map = curated_unihan_readings_map
            output_unihan_source_rank_map = curated_unihan_source_rank_map
            output_unihan_pinlu_detail_map = curated_unihan_pinlu_detail_map
            curated_usage_score_map: Dict[str, float] = {}
            curated_source_hits_map: Dict[str, int] = {}
            curated_tc_usage_score_map: Dict[str, float] = {}
            curated_tc_source_hits_map: Dict[str, int] = {}
            (
                curated_daily_stats,
                curated_daily_sc_terms,
                curated_daily_tc_terms,
            ) = _augment_with_curated_daily_phrases(
                sc_map,
                tc_map,
                curated_daily_entries,
                curated_usage_score_map,
                curated_source_hits_map,
                curated_tc_usage_score_map,
                curated_tc_source_hits_map,
                jieba_direct_signal_map,
                tc_jieba_direct_signal_map,
                jieba_pos_map,
                tc_jieba_pos_map,
                char_frequency_prior,
                tc_char_frequency_prior,
                [],
                {},
                curated_unihan_map,
                curated_unihan_readings_map,
                curated_unihan_source_rank_map,
                curated_unihan_pinlu_detail_map,
                args.min_hanzi,
            )
            if curated_daily_supplement_entries:
                (
                    curated_daily_supplement_stats,
                    curated_daily_supplement_sc_terms,
                    curated_daily_supplement_tc_terms,
                ) = _augment_with_curated_daily_phrases(
                    sc_map,
                    tc_map,
                    curated_daily_supplement_entries,
                    curated_usage_score_map,
                    curated_source_hits_map,
                    curated_tc_usage_score_map,
                    curated_tc_source_hits_map,
                    jieba_direct_signal_map,
                    tc_jieba_direct_signal_map,
                    jieba_pos_map,
                    tc_jieba_pos_map,
                    char_frequency_prior,
                    tc_char_frequency_prior,
                    [],
                    {},
                    curated_unihan_map,
                    curated_unihan_readings_map,
                    curated_unihan_source_rank_map,
                    curated_unihan_pinlu_detail_map,
                    args.min_hanzi,
                    stats_prefix="curated_daily_supplement",
                    low_frequency=True,
                )
            stats.update(curated_daily_parse_stats)
            stats.update(curated_daily_stats)
            stats.update(curated_daily_supplement_parse_stats)
            stats.update(curated_daily_supplement_stats)
        stats.update(vertical_manifest_stats)
        if vertical_source_configs:
            vertical_entries: List[Tuple[str, str, float, str]] = []
            vertical_parse_stats = {
                "vertical_term_rows": 0,
                "vertical_term_kept": 0,
                "vertical_term_skipped_short": 0,
                "vertical_term_skipped_non_cjk": 0,
                "vertical_term_skipped_malformed": 0,
                "vertical_thuocl_files_matched": 0,
                "vertical_thuocl_rows": 0,
                "vertical_thuocl_kept": 0,
                "vertical_thuocl_skipped_short": 0,
                "vertical_thuocl_skipped_non_cjk": 0,
                "vertical_thuocl_skipped_filter": 0,
                "vertical_thuocl_invalid_format": 0,
                "vertical_thuocl_missing_member": 0,
                "vertical_terms_missing_payload_source": 0,
                "vertical_terms_unsupported_source_type": 0,
                "vertical_mesh_descriptors_total": 0,
                "vertical_mesh_descriptors_medical": 0,
                "vertical_mesh_descriptors_nonmedical": 0,
                "vertical_mesh_missing_payload": 0,
                "vertical_wikidata_rows": 0,
                "vertical_wikidata_kept": 0,
                "vertical_wikidata_skipped_nonmedical_mesh": 0,
                "vertical_wikidata_skipped_non_cjk": 0,
                "vertical_wikidata_skipped_short": 0,
                "vertical_wikidata_skipped_duplicate": 0,
                "vertical_wikidata_missing_mesh_payload": 0,
                "vertical_wikidata_missing_payload": 0,
            }
            for vertical_source in vertical_source_configs:
                entries, parse_stats = _load_vertical_source_entries(
                    vertical_source,
                    payload_map,
                    vertical_payload_map,
                    args.min_hanzi,
                    repo_root,
                )
                vertical_entries.extend(entries)
                for key, value in parse_stats.items():
                    vertical_parse_stats[key] = vertical_parse_stats.get(key, 0) + value
            vertical_stats, vertical_sc_terms, vertical_tc_terms = _augment_with_vertical_terms(
                sc_map,
                tc_map,
                vertical_entries,
                usage_score_map,
                source_hits_map,
                tc_usage_score_map,
                tc_source_hits_map,
                jieba_direct_signal_map,
                tc_jieba_direct_signal_map,
                jieba_pos_map,
                tc_jieba_pos_map,
                char_frequency_prior,
                tc_char_frequency_prior,
                [],
                {},
                curated_unihan_map,
                curated_unihan_readings_map,
                curated_unihan_source_rank_map,
                curated_unihan_pinlu_detail_map,
                args.min_hanzi,
            )
            lexical_seed_sc_terms.update(vertical_sc_terms)
            lexical_seed_tc_terms.update(vertical_tc_terms)
            for sc_word, tc_word, _usage_score, _explicit_pinyin, layer_id, _source_id in vertical_entries:
                if layer_id != "civic":
                    continue
                civic_sc_terms.add(sc_word)
                civic_tc_terms.add(tc_word or sc_word)
            stats.update(vertical_parse_stats)
            stats.update(vertical_stats)
    elif parser_name == "cedict_thuocl_jieba_opencc_unihan_wiki":
        cedict_payload = _require_source_payload(
            payload_map,
            sources,
            role="cc-cedict",
            source_id="cc-cedict",
            download_url=CEDICT_DEFAULT_URL,
        )
        thuocl_payload = _require_source_payload(
            payload_map,
            sources,
            role="thuocl",
            source_id="thuocl",
            download_url=THUOCL_ZIP_URL,
        )
        opencc_payload = _require_source_payload(
            payload_map,
            sources,
            role="opencc-stphrases",
            source_id="opencc-stphrases",
            download_url=OPENCC_STPHRASES_URL,
        )
        jieba_payload = _require_source_payload(
            payload_map,
            sources,
            role="jieba-dict",
            source_id="jieba-dict",
            download_url=JIEBA_DICT_URL,
        )
        unihan_payload = _require_source_payload(
            payload_map,
            sources,
            role="unicode-unihan-readings",
            source_id="unicode-unihan-readings",
            download_url=UNICODE_UNIHAN_URL,
        )
        wiki_titles_payload = _require_source_payload(
            payload_map,
            sources,
            role="zhwiki-titles-ns0",
            source_id="zhwiki-titles-ns0",
            download_url=ZHWIKI_TITLES_URL,
        )
        wiktionary_titles_payload = _require_source_payload(
            payload_map,
            sources,
            role="zhwiktionary-titles-ns0",
            source_id="zhwiktionary-titles-ns0",
            download_url=ZHWIKTIONARY_TITLES_URL,
        )
        source_ids = {str(source.get("id", "")) for source in sources}
        curated_daily_payload = _require_source_payload(
            payload_map,
            sources,
            role="project-curated-daily-phrases",
            source_id="project-curated-daily-phrases",
            download_url=CURATED_DAILY_PHRASES_URL,
        )
        cedict_text = _decode_text(cedict_payload)
        opencc_text = _decode_text(opencc_payload)
        cedict_tc_to_sc_map = _build_cedict_tc_to_sc_map(cedict_text, args.min_hanzi)

        (
            sc_map,
            tc_map,
            cedict_stats,
            cedict_style_penalty_map,
            cedict_semantic_bonus_map,
        ) = _parse_cedict_entries(cedict_text, args.min_hanzi)
        opencc_entries, opencc_stats = _parse_opencc_entries(opencc_text, args.min_hanzi)
        opencc_tc_to_sc_map = _build_opencc_tc_to_sc_map(opencc_entries)
        tc_to_sc_map = _merge_tc_to_sc_maps(opencc_tc_to_sc_map, cedict_tc_to_sc_map)
        thuocl_max_df, thuocl_coverage, thuocl_stats = _parse_thuocl_entries(thuocl_payload)
        jieba_entries, jieba_pos_map, jieba_stats = _parse_jieba_frequency_entries(
            jieba_payload, args.min_hanzi
        )
        thuocl_entries = _build_thuocl_frequency_map(thuocl_max_df, thuocl_coverage)
        pageviews_source = _require_source_config(
            sources,
            role="wikimedia-pageviews-top",
            source_id="wikimedia-pageviews-top",
            download_url=WIKIMEDIA_PAGEVIEWS_TOP_URL,
        )
        (
            pageviews_entries,
            pageviews_stats,
            pageviews_month_hits,
            pageviews_peak_views,
        ) = _load_wikimedia_pageviews_entries(
            repo_root=repo_root,
            source_url=str(pageviews_source["download_url"]),
            min_hanzi=args.min_hanzi,
            months=args.pageviews_months,
            max_rank=args.pageviews_max_rank,
        )
        pageviews_entries_sc = _normalize_pageviews_entries_to_sc(
            pageviews_entries,
            tc_to_sc_map,
        )
        thuocl_signal_map = _build_normalized_signal_map(thuocl_entries)
        jieba_signal_map = _build_normalized_signal_map(jieba_entries)
        jieba_direct_signal_map = _build_direct_frequency_signal_map(jieba_entries)
        thuocl_corroborated_signal_map = _build_thuocl_jieba_corroborated_signal_map(
            thuocl_max_df,
            thuocl_coverage,
            jieba_direct_signal_map,
        )
        char_frequency_prior = _build_char_frequency_prior(jieba_entries)
        pageviews_signal_map = _build_normalized_signal_map(pageviews_entries_sc)
        pageviews_persistence_signal_map = _build_normalized_signal_map(
            _normalize_metric_map_to_sc(pageviews_month_hits, tc_to_sc_map),
            percentile=100.0,
        )
        pageviews_burst_signal_map = _build_pageviews_burst_signal_map(
            pageviews_entries_sc,
            _normalize_metric_map_to_sc(pageviews_month_hits, tc_to_sc_map),
            _normalize_metric_map_to_sc(pageviews_peak_views, tc_to_sc_map),
        )
        usage_score_map, source_hits_map = _build_usage_signal_map(
            thuocl_signal_map,
            jieba_signal_map,
            pageviews_signal_map,
            pageviews_persistence_signal_map=pageviews_persistence_signal_map,
            pageviews_burst_signal_map=pageviews_burst_signal_map,
            jieba_pos_map=jieba_pos_map,
            jieba_direct_signal_map=jieba_direct_signal_map,
        )
        (
            unihan_map,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_pinlu_map,
            unihan_pinlu_detail_map,
        ) = _load_unihan_readings_detail(unihan_payload)
        output_unihan_map = unihan_map
        output_unihan_readings_map = unihan_readings_map
        output_unihan_source_rank_map = unihan_reading_source_map
        output_unihan_pinlu_detail_map = unihan_pinlu_detail_map
        wiki_titles, wiki_stats = _parse_wiki_titles_entries(
            wiki_titles_payload, min_hanzi=args.min_hanzi
        )
        wiktionary_titles, wiktionary_stats = _parse_wiki_titles_entries(
            wiktionary_titles_payload,
            min_hanzi=args.min_hanzi,
        )
        wiktionary_usage_score_map, wiktionary_seed_stats = (
            _build_wiktionary_daily_seed_signal_map(
                wiktionary_titles,
                char_frequency_prior,
            )
        )
        curated_daily_entries, curated_daily_parse_stats = _parse_curated_daily_phrase_entries(
            curated_daily_payload,
            args.min_hanzi,
        )
        excluded_sc, excluded_tc = _parse_curated_contains_popularity_exclusions(
            curated_daily_payload
        )
        contains_popularity_excluded_sc_terms.update(excluded_sc)
        contains_popularity_excluded_tc_terms.update(excluded_tc)
        if "project-curated-daily-supplement-phrases" in source_ids:
            curated_daily_supplement_payload = _require_source_payload(
                payload_map,
                sources,
                role="project-curated-daily-supplement-phrases",
                source_id="project-curated-daily-supplement-phrases",
                download_url=CURATED_DAILY_SUPPLEMENT_PHRASES_URL,
            )
            (
                curated_daily_supplement_entries,
                curated_daily_supplement_parse_stats,
            ) = _parse_curated_daily_phrase_entries(
                curated_daily_supplement_payload,
                args.min_hanzi,
                stats_prefix="curated_daily_supplement_phrase",
            )
            excluded_sc, excluded_tc = _parse_curated_contains_popularity_exclusions(
                curated_daily_supplement_payload
            )
            contains_popularity_excluded_sc_terms.update(excluded_sc)
            contains_popularity_excluded_tc_terms.update(excluded_tc)
            (
                curated_daily_supplement_entries,
                curated_daily_post_rank_exact_entries,
            ) = _partition_curated_daily_post_rank_exact_entries(
                curated_daily_supplement_entries
            )
            curated_daily_supplement_parse_stats[
                "curated_daily_supplement_phrase_post_rank_exact"
            ] = len(curated_daily_post_rank_exact_entries)
        for word, score in wiktionary_usage_score_map.items():
            usage_score_map[word] = max(score, usage_score_map.get(word, 0.0))
            source_hits_map[word] = max(1, source_hits_map.get(word, 0))
        for sc_word, _tc_word, score, _explicit_pinyin in curated_daily_entries:
            usage_score_map[sc_word] = max(score, usage_score_map.get(sc_word, 0.0))
            source_hits_map[sc_word] = max(4, source_hits_map.get(sc_word, 0))
        wiki_alias_titles_by_pinyin = _collect_wiki_pinyin_alias_titles(
            wiki_titles_payload,
            {pinyin for pinyin, _text in sc_map.keys()},
        )
        wiki_pinyin_alias_map = _load_wiki_redirect_alias_map(
            repo_root,
            wiki_alias_titles_by_pinyin,
            min_hanzi=args.min_hanzi,
        )
        tc_usage_score_map = _build_tc_signal_map(usage_score_map, tc_to_sc_map)
        tc_source_hits_map = _build_tc_source_hits_map(source_hits_map, tc_to_sc_map)
        tc_jieba_direct_signal_map = _build_tc_signal_map(jieba_direct_signal_map, tc_to_sc_map)
        tc_jieba_pos_map = _build_tc_pos_map(jieba_pos_map, tc_to_sc_map)
        tc_char_frequency_prior = _build_tc_signal_map(char_frequency_prior, tc_to_sc_map)
        tc_pageviews_signal_map = _build_tc_signal_map(pageviews_signal_map, tc_to_sc_map)
        tc_thuocl_signal_map = _build_tc_signal_map(thuocl_signal_map, tc_to_sc_map)
        tc_pageviews_persistence_signal_map = _build_tc_signal_map(
            pageviews_persistence_signal_map, tc_to_sc_map
        )
        tc_pageviews_burst_signal_map = _build_tc_signal_map(
            pageviews_burst_signal_map, tc_to_sc_map
        )
        (
            trad_to_simp_char_map,
            simp_to_trad_char_map,
            sc_script_chars,
            tc_script_chars,
        ) = _build_char_variant_hints(tc_to_sc_map, opencc_entries)
        tc_shared_identity_chars = _build_tc_shared_identity_chars(
            tc_to_sc_map,
            opencc_entries,
        )
        unihan_simplified_variant_map = _load_unihan_simplified_variant_map(unihan_payload)
        for trad_ch, simp_ch in unihan_simplified_variant_map.items():
            _apply_explicit_script_pair(
                trad_ch,
                simp_ch,
                trad_to_simp_char_map,
                simp_to_trad_char_map,
                sc_script_chars,
                tc_script_chars,
                tc_shared_identity_chars,
            )
        unihan_traditional_variant_map = _load_unihan_traditional_variant_map(unihan_payload)
        for simp_ch, trad_ch in unihan_traditional_variant_map.items():
            _apply_explicit_script_pair(
                trad_ch,
                simp_ch,
                trad_to_simp_char_map,
                simp_to_trad_char_map,
                sc_script_chars,
                tc_script_chars,
                tc_shared_identity_chars,
            )
        sc_rescore_stats = _rescore_mapping_with_signals(
            sc_map,
            usage_score_map=usage_score_map,
            source_hits_map=source_hits_map,
            pageviews_signal_map=pageviews_signal_map,
            wiki_titles=wiki_titles,
            jieba_direct_signal_map=jieba_direct_signal_map,
            jieba_pos_map=jieba_pos_map,
            char_frequency_prior=char_frequency_prior,
            term_style_penalty_map=cedict_style_penalty_map,
            term_semantic_bonus_map=cedict_semantic_bonus_map,
            unihan_map=unihan_map,
            unihan_readings_map=unihan_readings_map,
            unihan_pinlu_map=unihan_pinlu_map,
            unihan_pinlu_detail_map=unihan_pinlu_detail_map,
            core_entry=True,
            stats_prefix="sc_core",
        )
        tc_rescore_stats = _rescore_mapping_with_signals(
            tc_map,
            usage_score_map=tc_usage_score_map,
            source_hits_map=tc_source_hits_map,
            pageviews_signal_map=tc_pageviews_signal_map,
            wiki_titles=wiki_titles,
            jieba_direct_signal_map=tc_jieba_direct_signal_map,
            jieba_pos_map=tc_jieba_pos_map,
            char_frequency_prior=tc_char_frequency_prior,
            term_style_penalty_map=cedict_style_penalty_map,
            term_semantic_bonus_map=cedict_semantic_bonus_map,
            unihan_map=unihan_map,
            unihan_readings_map=unihan_readings_map,
            unihan_pinlu_map=unihan_pinlu_map,
            unihan_pinlu_detail_map=unihan_pinlu_detail_map,
            core_entry=True,
            stats_prefix="tc_core",
        )
        (
            augment_stats,
            wiki_alias_sc_terms,
            wiki_alias_tc_terms,
            lexical_seed_sc_terms,
            lexical_seed_tc_terms,
        ) = _augment_with_frequency_lexicon(
            sc_map,
            tc_map,
            usage_score_map,
            source_hits_map,
            pageviews_signal_map,
            tc_usage_score_map,
            tc_source_hits_map,
            tc_pageviews_signal_map,
            jieba_direct_signal_map,
            jieba_pos_map,
            char_frequency_prior,
            opencc_entries,
            tc_to_sc_map,
            simp_to_trad_char_map,
            unihan_map,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_pinlu_detail_map,
            wiki_titles,
            wiki_pinyin_alias_map,
            set(wiktionary_usage_score_map.keys()),
            args.min_hanzi,
        )
        daily_prefix_stats = {
            "daily_prefix_source_terms": 0,
            "daily_prefix_pinyin_hits": 0,
            "daily_prefix_added_sc": 0,
            "daily_prefix_boosted_sc": 0,
            "daily_prefix_added_tc": 0,
            "daily_prefix_boosted_tc": 0,
            "daily_prefix_disabled": 1,
        }
        daily_prefix_sc_terms = set()
        daily_prefix_tc_terms = set()
        if args.min_hanzi >= 2:
            (
                wiki_proper_stats,
                wiki_proper_sc_terms,
                wiki_proper_tc_terms,
            ) = _augment_with_wiki_proper_noun_titles(
                sc_map,
                tc_map,
                usage_score_map,
                source_hits_map,
                pageviews_signal_map,
                tc_usage_score_map,
                tc_source_hits_map,
                tc_pageviews_signal_map,
                jieba_direct_signal_map,
                tc_jieba_direct_signal_map,
                jieba_pos_map,
                tc_jieba_pos_map,
                char_frequency_prior,
                tc_char_frequency_prior,
                opencc_entries,
                tc_to_sc_map,
                simp_to_trad_char_map,
                unihan_map,
                unihan_readings_map,
                unihan_reading_source_map,
                unihan_pinlu_detail_map,
                wiki_titles,
                args.min_hanzi,
            )
        else:
            wiki_proper_stats = {
                "wiki_proper_titles_total": 0,
                "wiki_proper_titles_candidates_sc": 0,
                "wiki_proper_titles_skipped_daily_like": 0,
                "wiki_proper_titles_skipped_weak_signal": 0,
                "wiki_proper_titles_skipped_no_pinyin": 0,
                "wiki_proper_titles_pageview_backed": 0,
                "wiki_proper_titles_prefix_backed": 0,
                "wiki_proper_titles_added_sc": 0,
                "wiki_proper_titles_boosted_sc": 0,
                "wiki_proper_titles_added_tc": 0,
                "wiki_proper_titles_boosted_tc": 0,
            }
        (
            curated_daily_stats,
            curated_daily_sc_terms,
            curated_daily_tc_terms,
        ) = _augment_with_curated_daily_phrases(
            sc_map,
            tc_map,
            curated_daily_entries,
            usage_score_map,
            source_hits_map,
            tc_usage_score_map,
            tc_source_hits_map,
            jieba_direct_signal_map,
            tc_jieba_direct_signal_map,
            jieba_pos_map,
            tc_jieba_pos_map,
            char_frequency_prior,
            tc_char_frequency_prior,
            opencc_entries,
            simp_to_trad_char_map,
            unihan_map,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_pinlu_detail_map,
            args.min_hanzi,
        )
        lexical_seed_sc_terms.update(curated_daily_sc_terms)
        lexical_seed_tc_terms.update(curated_daily_tc_terms)
        (
            curated_daily_supplement_stats,
            curated_daily_supplement_sc_terms,
            curated_daily_supplement_tc_terms,
        ) = _augment_with_curated_daily_phrases(
            sc_map,
            tc_map,
            curated_daily_supplement_entries,
            usage_score_map,
            source_hits_map,
            tc_usage_score_map,
            tc_source_hits_map,
            jieba_direct_signal_map,
            tc_jieba_direct_signal_map,
            jieba_pos_map,
            tc_jieba_pos_map,
            char_frequency_prior,
            tc_char_frequency_prior,
            opencc_entries,
            simp_to_trad_char_map,
            unihan_map,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_pinlu_detail_map,
            args.min_hanzi,
            stats_prefix="curated_daily_supplement",
            low_frequency=True,
        )
        vertical_parse_stats = {
            "vertical_term_rows": 0,
            "vertical_term_kept": 0,
            "vertical_term_skipped_short": 0,
            "vertical_term_skipped_non_cjk": 0,
            "vertical_term_skipped_malformed": 0,
            "vertical_thuocl_files_matched": 0,
            "vertical_thuocl_rows": 0,
            "vertical_thuocl_kept": 0,
            "vertical_thuocl_skipped_short": 0,
            "vertical_thuocl_skipped_non_cjk": 0,
            "vertical_thuocl_skipped_filter": 0,
            "vertical_thuocl_invalid_format": 0,
            "vertical_thuocl_missing_member": 0,
            "vertical_terms_missing_payload_source": 0,
            "vertical_terms_unsupported_source_type": 0,
            "vertical_mesh_descriptors_total": 0,
            "vertical_mesh_descriptors_medical": 0,
            "vertical_mesh_descriptors_nonmedical": 0,
            "vertical_mesh_missing_payload": 0,
            "vertical_wikidata_rows": 0,
            "vertical_wikidata_kept": 0,
            "vertical_wikidata_skipped_nonmedical_mesh": 0,
            "vertical_wikidata_skipped_non_cjk": 0,
            "vertical_wikidata_skipped_short": 0,
            "vertical_wikidata_skipped_duplicate": 0,
            "vertical_wikidata_missing_mesh_payload": 0,
            "vertical_wikidata_missing_payload": 0,
        }
        vertical_stats = {
            "vertical_terms_total": 0,
            "vertical_terms_added_sc": 0,
            "vertical_terms_boosted_sc": 0,
            "vertical_terms_added_tc": 0,
            "vertical_terms_boosted_tc": 0,
            "vertical_terms_skipped_short": 0,
            "vertical_terms_skipped_no_pinyin": 0,
        }
        vertical_entries: List[Tuple[str, str, float, str]] = []
        if vertical_source_configs:
            for vertical_source in vertical_source_configs:
                entries, parse_stats = _load_vertical_source_entries(
                    vertical_source,
                    payload_map,
                    vertical_payload_map,
                    args.min_hanzi,
                    repo_root,
                )
                vertical_entries.extend(entries)
                for key, value in parse_stats.items():
                    vertical_parse_stats[key] = vertical_parse_stats.get(key, 0) + value
            vertical_stats, vertical_sc_terms, vertical_tc_terms = _augment_with_vertical_terms(
                sc_map,
                tc_map,
                vertical_entries,
                usage_score_map,
                source_hits_map,
                tc_usage_score_map,
                tc_source_hits_map,
                jieba_direct_signal_map,
                tc_jieba_direct_signal_map,
                jieba_pos_map,
                tc_jieba_pos_map,
                char_frequency_prior,
                tc_char_frequency_prior,
                opencc_entries,
                simp_to_trad_char_map,
                unihan_map,
                unihan_readings_map,
                unihan_reading_source_map,
                unihan_pinlu_detail_map,
                args.min_hanzi,
            )
            lexical_seed_sc_terms.update(vertical_sc_terms)
            lexical_seed_tc_terms.update(vertical_tc_terms)
            for sc_word, tc_word, _usage_score, _explicit_pinyin, layer_id, _source_id in vertical_entries:
                if layer_id != "civic":
                    continue
                civic_sc_terms.add(sc_word)
                civic_tc_terms.add(tc_word or sc_word)
        sc_map, sc_normalize_stats = _normalize_sc_mapping_with_opencc(sc_map, tc_to_sc_map)
        sc_map, sc_char_normalize_stats = _normalize_sc_mapping_with_char_map(
            sc_map, trad_to_simp_char_map, simp_to_trad_char_map
        )
        sc_map, sc_script_filter_stats = _filter_sc_mapping_with_script_hints(
            sc_map, sc_script_chars, tc_script_chars
        )
        tc_map, tc_char_normalize_stats = _normalize_tc_mapping_with_char_map(
            tc_map,
            simp_to_trad_char_map,
            trad_to_simp_char_map,
        )
        tc_map, tc_backfill_stats = _backfill_tc_mapping_from_sc_with_char_map(
            sc_map, tc_map, simp_to_trad_char_map
        )
        tc_map, tc_script_filter_stats = _filter_tc_mapping_with_script_hints(
            tc_map, sc_script_chars, tc_script_chars
        )
        curated_daily_explicit_pinyin_overrides = _build_curated_daily_explicit_pinyin_override_map(
            curated_daily_entries + curated_daily_supplement_entries
        )
        sc_map, sc_curated_daily_pinyin_override_stats = _apply_explicit_term_pinyin_overrides(
            sc_map,
            curated_daily_explicit_pinyin_overrides,
            "sc_curated_daily_explicit_pinyin_override",
        )
        tc_map, tc_curated_daily_pinyin_override_stats = _apply_explicit_term_pinyin_overrides(
            tc_map,
            curated_daily_explicit_pinyin_overrides,
            "tc_curated_daily_explicit_pinyin_override",
        )
        explicit_term_pinyin_overrides = _build_explicit_term_pinyin_override_map(vertical_entries)
        sc_map, sc_pinyin_override_stats = _apply_explicit_term_pinyin_overrides(
            sc_map,
            explicit_term_pinyin_overrides,
            "sc_explicit_pinyin_override",
        )
        tc_map, tc_pinyin_override_stats = _apply_explicit_term_pinyin_overrides(
            tc_map,
            explicit_term_pinyin_overrides,
            "tc_explicit_pinyin_override",
        )
        vertical_tc_exact_stats = _reinforce_vertical_tc_terms(
            tc_map,
            vertical_entries,
            tc_usage_score_map,
            tc_source_hits_map,
            tc_jieba_direct_signal_map,
            tc_jieba_pos_map,
            tc_char_frequency_prior,
            opencc_entries,
            simp_to_trad_char_map,
            unihan_map,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_pinlu_detail_map,
            args.min_hanzi,
        )
        curated_daily_tc_exact_stats = _reinforce_curated_daily_tc_phrases(
            tc_map,
            curated_daily_entries,
            tc_usage_score_map,
            tc_source_hits_map,
            tc_jieba_direct_signal_map,
            tc_jieba_pos_map,
            tc_char_frequency_prior,
            opencc_entries,
            simp_to_trad_char_map,
            unihan_map,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_pinlu_detail_map,
            args.min_hanzi,
        )
        curated_daily_supplement_tc_exact_stats = _reinforce_curated_daily_tc_phrases(
            tc_map,
            curated_daily_supplement_entries,
            tc_usage_score_map,
            tc_source_hits_map,
            tc_jieba_direct_signal_map,
            tc_jieba_pos_map,
            tc_char_frequency_prior,
            opencc_entries,
            simp_to_trad_char_map,
            unihan_map,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_pinlu_detail_map,
            args.min_hanzi,
            stats_prefix="curated_daily_supplement_exact_tc",
            low_frequency=True,
        )
        curated_daily_sc_exact_stats = _reinforce_curated_daily_sc_phrases(
            sc_map,
            curated_daily_entries,
            curated_usage_score_map,
            curated_source_hits_map,
            jieba_direct_signal_map,
            jieba_pos_map,
            char_frequency_prior,
            curated_unihan_map,
            curated_unihan_readings_map,
            curated_unihan_source_rank_map,
            curated_unihan_pinlu_detail_map,
            args.min_hanzi,
        )
        curated_daily_supplement_sc_exact_stats = _reinforce_curated_daily_sc_phrases(
            sc_map,
            curated_daily_supplement_entries,
            curated_usage_score_map,
            curated_source_hits_map,
            jieba_direct_signal_map,
            jieba_pos_map,
            char_frequency_prior,
            curated_unihan_map,
            curated_unihan_readings_map,
            curated_unihan_source_rank_map,
            curated_unihan_pinlu_detail_map,
            args.min_hanzi,
            stats_prefix="curated_daily_supplement_exact_sc",
            low_frequency=True,
        )

        stats = {}
        stats.update(cedict_stats)
        stats.update(opencc_stats)
        stats.update(thuocl_stats)
        stats.update(jieba_stats)
        stats["thuocl_frequency_terms"] = len(thuocl_entries)
        stats["jieba_frequency_terms"] = len(jieba_entries)
        stats.update(pageviews_stats)
        stats["pageviews_frequency_terms"] = len(pageviews_entries)
        stats["pageviews_sc_normalized_terms"] = len(pageviews_entries_sc)
        stats["usage_score_terms"] = len(usage_score_map)
        stats["jieba_direct_score_terms"] = len(jieba_direct_signal_map)
        stats["thuocl_jieba_corroborated_terms"] = len(
            thuocl_corroborated_signal_map
        )
        stats["jieba_pos_terms"] = len(jieba_pos_map)
        stats["char_frequency_prior_terms"] = len(char_frequency_prior)
        stats["pageviews_persistence_terms"] = len(pageviews_persistence_signal_map)
        stats["pageviews_burst_terms"] = len(pageviews_burst_signal_map)
        stats.update(wiki_stats)
        stats["wiktionary_title_set_size"] = len(wiktionary_titles)
        stats.update(wiktionary_stats)
        stats.update(wiktionary_seed_stats)
        stats.update(curated_daily_parse_stats)
        stats.update(curated_daily_supplement_parse_stats)
        stats.update(sc_curated_daily_pinyin_override_stats)
        stats.update(tc_curated_daily_pinyin_override_stats)
        stats.update(sc_rescore_stats)
        stats.update(tc_rescore_stats)
        stats.update(augment_stats)
        stats.update(curated_daily_sc_exact_stats)
        stats.update(curated_daily_tc_exact_stats)
        stats.update(curated_daily_supplement_sc_exact_stats)
        stats.update(curated_daily_supplement_tc_exact_stats)
        stats.update(daily_prefix_stats)
        stats.update(wiki_proper_stats)
        stats.update(curated_daily_stats)
        stats.update(curated_daily_supplement_stats)
        stats.update(vertical_manifest_stats)
        stats.update(vertical_parse_stats)
        stats.update(vertical_stats)
        stats.update(vertical_tc_exact_stats)
        stats.update(sc_normalize_stats)
        stats.update(sc_char_normalize_stats)
        stats.update(sc_script_filter_stats)
        stats.update(sc_pinyin_override_stats)
        stats.update(tc_char_normalize_stats)
        stats.update(tc_backfill_stats)
        stats.update(tc_script_filter_stats)
        stats.update(tc_pinyin_override_stats)
        stats["unihan_map_size"] = len(unihan_map)
        stats["tc_usage_score_terms"] = len(tc_usage_score_map)
        stats["tc_jieba_direct_score_terms"] = len(tc_jieba_direct_signal_map)
        stats["tc_jieba_pos_terms"] = len(tc_jieba_pos_map)
        stats["tc_char_frequency_prior_terms"] = len(tc_char_frequency_prior)
        stats["tc_pageviews_score_terms"] = len(tc_pageviews_signal_map)
        stats["tc_pageviews_persistence_terms"] = len(tc_pageviews_persistence_signal_map)
        stats["tc_pageviews_burst_terms"] = len(tc_pageviews_burst_signal_map)
        stats["tc_to_sc_map_terms"] = len(tc_to_sc_map)
        stats["wiki_title_set_size"] = len(wiki_titles)
    elif parser_name == "opencc_unihan":
        opencc_payload = _require_source_payload(
            payload_map,
            sources,
            role="opencc-stphrases",
            source_id="opencc-stphrases",
            download_url=OPENCC_STPHRASES_URL,
        )
        unihan_payload = _require_source_payload(
            payload_map,
            sources,
            role="unicode-unihan-readings",
            source_id="unicode-unihan-readings",
            download_url=UNICODE_UNIHAN_URL,
        )
        opencc_text = _decode_text(opencc_payload)
        overrides: Dict[str, str] = {}
        if args.pinyin_overrides:
            overrides = _load_pinyin_overrides(repo_root / args.pinyin_overrides)
        sc_map, tc_map, stats = _build_from_opencc_unihan(
            opencc_text, unihan_payload, args.min_hanzi, overrides
        )
        opencc_entries_for_hints, _opencc_hint_stats = _parse_opencc_entries(opencc_text, 1)
        opencc_entries = opencc_entries_for_hints
        opencc_tc_to_sc_map = _build_opencc_tc_to_sc_map(opencc_entries_for_hints)
        (
            trad_to_simp_char_map,
            simp_to_trad_char_map,
            sc_script_chars,
            tc_script_chars,
        ) = _build_char_variant_hints(opencc_tc_to_sc_map, opencc_entries_for_hints)
        tc_shared_identity_chars = _build_tc_shared_identity_chars(
            opencc_tc_to_sc_map,
            opencc_entries_for_hints,
        )
        unihan_simplified_variant_map = _load_unihan_simplified_variant_map(unihan_payload)
        for trad_ch, simp_ch in unihan_simplified_variant_map.items():
            _apply_explicit_script_pair(
                trad_ch,
                simp_ch,
                trad_to_simp_char_map,
                simp_to_trad_char_map,
                sc_script_chars,
                tc_script_chars,
                tc_shared_identity_chars,
            )
        unihan_traditional_variant_map = _load_unihan_traditional_variant_map(unihan_payload)
        for simp_ch, trad_ch in unihan_traditional_variant_map.items():
            _apply_explicit_script_pair(
                trad_ch,
                simp_ch,
                trad_to_simp_char_map,
                simp_to_trad_char_map,
                sc_script_chars,
                tc_script_chars,
                tc_shared_identity_chars,
            )
        sc_map, sc_char_normalize_stats = _normalize_sc_mapping_with_char_map(
            sc_map, trad_to_simp_char_map, simp_to_trad_char_map
        )
        sc_map, sc_script_filter_stats = _filter_sc_mapping_with_script_hints(
            sc_map, sc_script_chars, tc_script_chars
        )
        tc_map, tc_char_normalize_stats = _normalize_tc_mapping_with_char_map(
            tc_map,
            simp_to_trad_char_map,
            trad_to_simp_char_map,
        )
        tc_map, tc_script_filter_stats = _filter_tc_mapping_with_script_hints(
            tc_map, sc_script_chars, tc_script_chars
        )
        stats.update(sc_char_normalize_stats)
        stats.update(sc_script_filter_stats)
        stats.update(tc_char_normalize_stats)
        stats.update(tc_script_filter_stats)
    elif parser_name == "unihan_only":
        opencc_payload = _require_source_payload(
            payload_map,
            sources,
            role="opencc-stphrases",
            source_id="opencc-stphrases",
            download_url=OPENCC_STPHRASES_URL,
        )
        unihan_payload = _require_source_payload(
            payload_map,
            sources,
            role="unicode-unihan-readings",
            source_id="unicode-unihan-readings",
            download_url=UNICODE_UNIHAN_URL,
        )
        opencc_text = _decode_text(opencc_payload)
        opencc_entries, opencc_stats = _parse_opencc_entries(opencc_text, 1)
        opencc_tc_to_sc_map = _build_opencc_tc_to_sc_map(opencc_entries)
        unihan_jieba_stats: Dict[str, int] = {}
        source_ids = {str(source.get("id", "")) for source in sources}
        if "jieba-dict" in source_ids:
            jieba_payload = _require_source_payload(
                payload_map,
                sources,
                role="jieba-dict",
                source_id="jieba-dict",
                download_url=JIEBA_DICT_URL,
            )
            jieba_entries, unihan_jieba_pos_map, unihan_jieba_stats = _parse_jieba_frequency_entries(
                jieba_payload,
                1,
            )
            single_char_frequency_map = {
                text: float(freq)
                for text, freq in jieba_entries.items()
                if _cjk_len(text) == 1 and CJK_FULL_RE.fullmatch(text)
            }
            single_char_pos_map = {
                text: pos_tag
                for text, pos_tag in unihan_jieba_pos_map.items()
                if _cjk_len(text) == 1 and CJK_FULL_RE.fullmatch(text)
            }
            tc_single_char_frequency_map = _build_tc_signal_map(
                single_char_frequency_map,
                opencc_tc_to_sc_map,
            )
            tc_single_char_pos_map = {
                text: pos_tag
                for text, pos_tag in _build_tc_pos_map(
                    single_char_pos_map,
                    opencc_tc_to_sc_map,
                ).items()
                if _cjk_len(text) == 1 and CJK_FULL_RE.fullmatch(text)
            }
        (
            trad_to_simp_char_map,
            simp_to_trad_char_map,
            sc_script_chars,
            tc_script_chars,
        ) = _build_char_variant_hints(opencc_tc_to_sc_map, opencc_entries)
        tc_shared_identity_chars = _build_tc_shared_identity_chars(
            opencc_tc_to_sc_map,
            opencc_entries,
        )
        unihan_simplified_variant_map = _load_unihan_simplified_variant_map(unihan_payload)
        for trad_ch, simp_ch in unihan_simplified_variant_map.items():
            _apply_explicit_script_pair(
                trad_ch,
                simp_ch,
                trad_to_simp_char_map,
                simp_to_trad_char_map,
                sc_script_chars,
                tc_script_chars,
                tc_shared_identity_chars,
            )
        unihan_traditional_variant_map = _load_unihan_traditional_variant_map(unihan_payload)
        for simp_ch, trad_ch in unihan_traditional_variant_map.items():
            _apply_explicit_script_pair(
                trad_ch,
                simp_ch,
                trad_to_simp_char_map,
                simp_to_trad_char_map,
                sc_script_chars,
                tc_script_chars,
                tc_shared_identity_chars,
            )
        if single_char_frequency_map:
            variant_frequency_terms = 0
            for trad_ch, simp_ch in trad_to_simp_char_map.items():
                if (
                    _cjk_len(trad_ch) != 1
                    or _cjk_len(simp_ch) != 1
                    or not CJK_FULL_RE.fullmatch(trad_ch)
                    or not CJK_FULL_RE.fullmatch(simp_ch)
                ):
                    continue
                signal = single_char_frequency_map.get(simp_ch, 0.0)
                if signal <= tc_single_char_frequency_map.get(trad_ch, 0.0):
                    continue
                tc_single_char_frequency_map[trad_ch] = signal
                variant_frequency_terms += 1
            unihan_jieba_stats["jieba_tc_single_char_variant_frequency_terms"] = (
                variant_frequency_terms
            )
        if single_char_pos_map:
            variant_pos_terms = 0
            for trad_ch, simp_ch in trad_to_simp_char_map.items():
                if (
                    _cjk_len(trad_ch) != 1
                    or _cjk_len(simp_ch) != 1
                    or not CJK_FULL_RE.fullmatch(trad_ch)
                    or not CJK_FULL_RE.fullmatch(simp_ch)
                ):
                    continue
                pos_tag = single_char_pos_map.get(simp_ch, "")
                if not pos_tag or tc_single_char_pos_map.get(trad_ch) == pos_tag:
                    continue
                tc_single_char_pos_map[trad_ch] = pos_tag
                variant_pos_terms += 1
            unihan_jieba_stats["jieba_tc_single_char_variant_pos_terms"] = variant_pos_terms
        overrides: Dict[str, str] = {}
        if args.pinyin_overrides:
            overrides = _load_pinyin_overrides(repo_root / args.pinyin_overrides)
        vertical_parse_stats = {
            "vertical_term_rows": 0,
            "vertical_term_kept": 0,
            "vertical_term_skipped_short": 0,
            "vertical_term_skipped_non_cjk": 0,
            "vertical_term_skipped_malformed": 0,
            "vertical_thuocl_files_matched": 0,
            "vertical_thuocl_rows": 0,
            "vertical_thuocl_kept": 0,
            "vertical_thuocl_skipped_short": 0,
            "vertical_thuocl_skipped_non_cjk": 0,
            "vertical_thuocl_skipped_filter": 0,
            "vertical_thuocl_invalid_format": 0,
            "vertical_thuocl_missing_member": 0,
            "vertical_terms_missing_payload_source": 0,
            "vertical_terms_unsupported_source_type": 0,
            "vertical_terms_fallback_downloads": 0,
            "vertical_mesh_descriptors_total": 0,
            "vertical_mesh_descriptors_medical": 0,
            "vertical_mesh_descriptors_nonmedical": 0,
            "vertical_mesh_missing_payload": 0,
            "vertical_wikidata_rows": 0,
            "vertical_wikidata_kept": 0,
            "vertical_wikidata_skipped_nonmedical_mesh": 0,
            "vertical_wikidata_skipped_non_cjk": 0,
            "vertical_wikidata_skipped_short": 0,
            "vertical_wikidata_skipped_duplicate": 0,
            "vertical_wikidata_missing_mesh_payload": 0,
            "vertical_wikidata_missing_payload": 0,
        }
        vertical_sc_support_excludes: Set[str] = set()
        vertical_tc_support_excludes: Set[str] = set()
        vertical_entries = []
        if vertical_source_configs:
            for vertical_source in vertical_source_configs:
                entries, parse_stats = _load_vertical_source_entries(
                    vertical_source,
                    payload_map,
                    vertical_payload_map,
                    args.min_hanzi,
                    repo_root,
                )
                vertical_entries.extend(entries)
                for key, value in parse_stats.items():
                    vertical_parse_stats[key] = vertical_parse_stats.get(key, 0) + value
            (
                vertical_sc_support_excludes,
                vertical_tc_support_excludes,
            ) = _collect_vertical_term_sets(vertical_entries)
        (
            unihan_map,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_pinlu_map,
            unihan_pinlu_detail_map,
        ) = _load_unihan_readings_detail(unihan_payload)
        (
            sc_family_term_count_map,
            sc_family_support_sum_map,
        ) = _load_char_family_support_from_generated_dict(
            support_dict_sc,
            exclude_texts=vertical_sc_support_excludes,
        )
        (
            tc_family_term_count_map,
            tc_family_support_sum_map,
        ) = _load_char_family_support_from_generated_dict(
            support_dict_tc,
            exclude_texts=vertical_tc_support_excludes,
        )
        (
            sc_reading_term_count_map,
            sc_reading_support_sum_map,
        ) = _load_char_reading_support_from_generated_dict(
            support_dict_sc,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_map,
            unihan_pinlu_detail_map,
            exclude_texts=vertical_sc_support_excludes,
        )
        (
            tc_reading_term_count_map,
            tc_reading_support_sum_map,
        ) = _load_char_reading_support_from_generated_dict(
            support_dict_tc,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_map,
            unihan_pinlu_detail_map,
            exclude_texts=vertical_tc_support_excludes,
        )
        if vertical_sc_support_excludes:
            (
                sc_visibility_family_term_count_map,
                _sc_visibility_family_support_sum_map,
            ) = _load_char_family_support_from_generated_dict(support_dict_sc)
            (
                sc_visibility_reading_term_count_map,
                sc_visibility_reading_support_sum_map,
            ) = _load_char_reading_support_from_generated_dict(
                support_dict_sc,
                unihan_readings_map,
                unihan_reading_source_map,
                unihan_map,
                unihan_pinlu_detail_map,
            )
            (
                sc_visibility_inferred_reading_term_count_map,
                sc_visibility_inferred_reading_support_sum_map,
            ) = _load_char_inferred_reading_support_from_generated_dict(
                support_dict_sc,
                unihan_readings_map,
                unihan_reading_source_map,
                unihan_map,
                unihan_pinlu_detail_map,
            )
        else:
            sc_visibility_family_term_count_map = dict(sc_family_term_count_map)
            sc_visibility_reading_term_count_map = dict(sc_reading_term_count_map)
            sc_visibility_reading_support_sum_map = dict(sc_reading_support_sum_map)
            sc_visibility_inferred_reading_term_count_map = dict(
                sc_inferred_reading_term_count_map
            )
            sc_visibility_inferred_reading_support_sum_map = dict(
                sc_inferred_reading_support_sum_map
            )
        if vertical_tc_support_excludes:
            (
                tc_visibility_family_term_count_map,
                _tc_visibility_family_support_sum_map,
            ) = _load_char_family_support_from_generated_dict(support_dict_tc)
            (
                tc_visibility_reading_term_count_map,
                tc_visibility_reading_support_sum_map,
            ) = _load_char_reading_support_from_generated_dict(
                support_dict_tc,
                unihan_readings_map,
                unihan_reading_source_map,
                unihan_map,
                unihan_pinlu_detail_map,
            )
            (
                tc_visibility_inferred_reading_term_count_map,
                tc_visibility_inferred_reading_support_sum_map,
            ) = _load_char_inferred_reading_support_from_generated_dict(
                support_dict_tc,
                unihan_readings_map,
                unihan_reading_source_map,
                unihan_map,
                unihan_pinlu_detail_map,
            )
        else:
            tc_visibility_family_term_count_map = dict(tc_family_term_count_map)
            tc_visibility_reading_term_count_map = dict(tc_reading_term_count_map)
            tc_visibility_reading_support_sum_map = dict(tc_reading_support_sum_map)
            tc_visibility_inferred_reading_term_count_map = dict(
                tc_inferred_reading_term_count_map
            )
            tc_visibility_inferred_reading_support_sum_map = dict(
                tc_inferred_reading_support_sum_map
            )
        (
            sc_leading_term_count_map,
            sc_leading_support_sum_map,
        ) = _load_char_leading_reading_support_from_generated_dict(
            support_dict_sc,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_map,
            unihan_pinlu_detail_map,
            exclude_texts=vertical_sc_support_excludes,
        )
        (
            tc_leading_term_count_map,
            tc_leading_support_sum_map,
        ) = _load_char_leading_reading_support_from_generated_dict(
            support_dict_tc,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_map,
            unihan_pinlu_detail_map,
            exclude_texts=vertical_tc_support_excludes,
        )
        (
            sc_inferred_reading_term_count_map,
            sc_inferred_reading_support_sum_map,
        ) = _load_char_inferred_reading_support_from_generated_dict(
            support_dict_sc,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_map,
            unihan_pinlu_detail_map,
            exclude_texts=vertical_sc_support_excludes,
        )
        (
            tc_inferred_reading_term_count_map,
            tc_inferred_reading_support_sum_map,
        ) = _load_char_inferred_reading_support_from_generated_dict(
            support_dict_tc,
            unihan_readings_map,
            unihan_reading_source_map,
            unihan_map,
            unihan_pinlu_detail_map,
            exclude_texts=vertical_tc_support_excludes,
        )
        if not vertical_sc_support_excludes:
            sc_visibility_inferred_reading_term_count_map = dict(
                sc_inferred_reading_term_count_map
            )
            sc_visibility_inferred_reading_support_sum_map = dict(
                sc_inferred_reading_support_sum_map
            )
        if not vertical_tc_support_excludes:
            tc_visibility_inferred_reading_term_count_map = dict(
                tc_inferred_reading_term_count_map
            )
            tc_visibility_inferred_reading_support_sum_map = dict(
                tc_inferred_reading_support_sum_map
            )
        sc_map, tc_map, stats = _build_from_unihan_only(
            unihan_payload,
            args.min_hanzi,
            overrides,
            trad_to_simp_char_map,
            simp_to_trad_char_map,
            sc_script_chars,
            tc_script_chars,
            sc_family_term_count_map,
            sc_family_support_sum_map,
            tc_family_term_count_map,
            tc_family_support_sum_map,
            sc_inferred_reading_term_count_map,
            sc_inferred_reading_support_sum_map,
            tc_inferred_reading_term_count_map,
            tc_inferred_reading_support_sum_map,
        )
        stats.update(opencc_stats)
        stats.update({f"unihan_{key}": value for key, value in unihan_jieba_stats.items()})
        stats["unihan_jieba_single_char_frequency_terms_sc"] = len(single_char_frequency_map)
        stats["unihan_jieba_single_char_frequency_terms_tc"] = len(tc_single_char_frequency_map)
        stats.update(vertical_manifest_stats)
        stats.update(vertical_parse_stats)
        stats["unihan_family_support_terms_sc"] = len(sc_family_term_count_map)
        stats["unihan_family_support_terms_tc"] = len(tc_family_term_count_map)
        stats["unihan_reading_support_terms_sc"] = len(sc_reading_term_count_map)
        stats["unihan_reading_support_terms_tc"] = len(tc_reading_term_count_map)
        stats["unihan_visibility_reading_support_terms_sc"] = len(
            sc_visibility_reading_term_count_map
        )
        stats["unihan_visibility_reading_support_terms_tc"] = len(
            tc_visibility_reading_term_count_map
        )
        stats["unihan_leading_support_terms_sc"] = len(sc_leading_term_count_map)
        stats["unihan_leading_support_terms_tc"] = len(tc_leading_term_count_map)
        stats["unihan_inferred_reading_support_terms_sc"] = len(sc_inferred_reading_term_count_map)
        stats["unihan_inferred_reading_support_terms_tc"] = len(tc_inferred_reading_term_count_map)
        stats["vertical_support_excluded_sc"] = len(vertical_sc_support_excludes)
        stats["vertical_support_excluded_tc"] = len(vertical_tc_support_excludes)
    else:
        raise ValueError(f"unsupported parser: {parser_name}")

    sc_map, dropped_sc_non_windows = _filter_windows_unrenderable_entries(sc_map)
    tc_map, dropped_tc_non_windows = _filter_windows_unrenderable_entries(tc_map)
    stats["sc_filtered_non_windows_cjk"] = dropped_sc_non_windows
    stats["tc_filtered_non_windows_cjk"] = dropped_tc_non_windows
    sc_single_char_reading_stats = _adjust_single_char_reading_preferences(
        sc_map,
        unihan_map=unihan_map,
        unihan_readings_map=unihan_readings_map,
        unihan_pinlu_map=unihan_pinlu_map,
        unihan_pinlu_detail_map=unihan_pinlu_detail_map,
        phrase_term_count_map=sc_reading_term_count_map,
        phrase_support_sum_map=sc_reading_support_sum_map,
        leading_term_count_map=sc_leading_term_count_map,
        leading_support_sum_map=sc_leading_support_sum_map,
        stats_prefix="sc",
    )
    stats.update(sc_single_char_reading_stats)
    sc_single_char_leading_stats = _adjust_single_char_leading_preferences(
        sc_map,
        leading_term_count_map=sc_leading_term_count_map,
        leading_support_sum_map=sc_leading_support_sum_map,
        family_term_count_map=sc_family_term_count_map,
        family_support_sum_map=sc_family_support_sum_map,
        unihan_pinlu_detail_map=unihan_pinlu_detail_map,
        stats_prefix="sc",
    )
    stats.update(sc_single_char_leading_stats)
    tc_single_char_reading_stats = _adjust_single_char_reading_preferences(
        tc_map,
        unihan_map=unihan_map,
        unihan_readings_map=unihan_readings_map,
        unihan_pinlu_map=unihan_pinlu_map,
        unihan_pinlu_detail_map=unihan_pinlu_detail_map,
        phrase_term_count_map=tc_reading_term_count_map,
        phrase_support_sum_map=tc_reading_support_sum_map,
        leading_term_count_map=tc_leading_term_count_map,
        leading_support_sum_map=tc_leading_support_sum_map,
        stats_prefix="tc",
    )
    stats.update(tc_single_char_reading_stats)
    tc_single_char_leading_stats = _adjust_single_char_leading_preferences(
        tc_map,
        leading_term_count_map=tc_leading_term_count_map,
        leading_support_sum_map=tc_leading_support_sum_map,
        family_term_count_map=tc_family_term_count_map,
        family_support_sum_map=tc_family_support_sum_map,
        unihan_pinlu_detail_map=unihan_pinlu_detail_map,
        stats_prefix="tc",
    )
    stats.update(tc_single_char_leading_stats)
    sc_augmented_terms = set(wiki_alias_sc_terms)
    sc_augmented_terms.update(lexical_seed_sc_terms)
    sc_augmented_terms.update(wiki_proper_sc_terms)
    tc_augmented_terms = set(wiki_alias_tc_terms)
    tc_augmented_terms.update(lexical_seed_tc_terms)
    tc_augmented_terms.update(wiki_proper_tc_terms)
    stats["lexical_seed_augmented_sc_terms"] = len(lexical_seed_sc_terms)
    stats["lexical_seed_augmented_tc_terms"] = len(lexical_seed_tc_terms)
    stats["wiki_proper_augmented_sc_terms"] = len(wiki_proper_sc_terms)
    stats["wiki_proper_augmented_tc_terms"] = len(wiki_proper_tc_terms)

    sc_productive_suffix_exact_stats = _reinforce_productive_suffix_exact_terms(
        sc_map,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        "sc",
    )
    tc_productive_suffix_exact_stats = _reinforce_productive_suffix_exact_terms(
        tc_map,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        "tc",
    )
    stats.update(sc_productive_suffix_exact_stats)
    stats.update(tc_productive_suffix_exact_stats)

    sc_multi_pronunciation_stats = _rerank_multi_pronunciation_terms(
        sc_map,
        usage_score_map=usage_score_map,
        source_hits_map=source_hits_map,
        pageviews_signal_map=pageviews_signal_map,
        jieba_direct_signal_map=jieba_direct_signal_map,
        stats_prefix="sc",
    )
    stats.update(sc_multi_pronunciation_stats)
    sc_homophone_stats = _rerank_homophone_buckets(
        sc_map,
        usage_score_map=usage_score_map,
        source_hits_map=source_hits_map,
        pageviews_signal_map=pageviews_signal_map,
        wiki_titles=wiki_titles,
        wiki_augmented_terms=sc_augmented_terms,
        jieba_direct_signal_map=jieba_direct_signal_map,
        jieba_pos_map=jieba_pos_map,
        char_frequency_prior=char_frequency_prior,
        term_style_penalty_map=cedict_style_penalty_map,
        term_semantic_bonus_map=cedict_semantic_bonus_map,
        preferred_terms=curated_daily_sc_terms,
        stats_prefix="sc",
        weak_leader_terms=curated_daily_supplement_sc_terms,
    )
    stats.update(sc_homophone_stats)
    sc_short_domain_cap_stats = _cap_short_domain_terms_against_direct_common(
        sc_map,
        usage_score_map=usage_score_map,
        source_hits_map=source_hits_map,
        pageviews_signal_map=pageviews_signal_map,
        wiki_titles=wiki_titles,
        wiki_augmented_terms=sc_augmented_terms,
        jieba_direct_signal_map=jieba_direct_signal_map,
        jieba_pos_map=jieba_pos_map,
        char_frequency_prior=char_frequency_prior,
        preferred_terms=curated_daily_sc_terms,
        stats_prefix="sc",
        weak_leader_terms=curated_daily_supplement_sc_terms,
    )
    stats.update(sc_short_domain_cap_stats)
    sc_low_signal_stats = _filter_low_signal_rare_entries(
        sc_map,
        usage_score_map=usage_score_map,
        source_hits_map=source_hits_map,
        pageviews_signal_map=pageviews_signal_map,
        wiki_titles=wiki_titles,
        wiki_augmented_terms=sc_augmented_terms,
        jieba_direct_signal_map=jieba_direct_signal_map,
        jieba_pos_map=jieba_pos_map,
        char_frequency_prior=char_frequency_prior,
        term_style_penalty_map=cedict_style_penalty_map,
        stats_prefix="sc",
    )
    stats.update(sc_low_signal_stats)
    sc_global_tail_stats = _filter_global_tail_entries(
        sc_map,
        usage_score_map=usage_score_map,
        source_hits_map=source_hits_map,
        pageviews_signal_map=pageviews_signal_map,
        wiki_titles=wiki_titles,
        wiki_augmented_terms=sc_augmented_terms,
        jieba_direct_signal_map=jieba_direct_signal_map,
        jieba_pos_map=jieba_pos_map,
        char_frequency_prior=char_frequency_prior,
        term_style_penalty_map=cedict_style_penalty_map,
        unihan_readings_map=unihan_readings_map,
        unihan_source_rank_map=unihan_reading_source_map,
        unihan_mandarin_map=unihan_map,
        unihan_pinlu_detail_map=unihan_pinlu_detail_map,
        stats_prefix="sc",
    )
    stats.update(sc_global_tail_stats)

    tc_multi_pronunciation_stats = _rerank_multi_pronunciation_terms(
        tc_map,
        usage_score_map=tc_usage_score_map,
        source_hits_map=tc_source_hits_map,
        pageviews_signal_map=tc_pageviews_signal_map,
        jieba_direct_signal_map=tc_jieba_direct_signal_map,
        stats_prefix="tc",
    )
    stats.update(tc_multi_pronunciation_stats)
    tc_homophone_stats = _rerank_homophone_buckets(
        tc_map,
        usage_score_map=tc_usage_score_map,
        source_hits_map=tc_source_hits_map,
        pageviews_signal_map=tc_pageviews_signal_map,
        wiki_titles=wiki_titles,
        wiki_augmented_terms=tc_augmented_terms,
        jieba_direct_signal_map=tc_jieba_direct_signal_map,
        jieba_pos_map=tc_jieba_pos_map,
        char_frequency_prior=tc_char_frequency_prior,
        term_style_penalty_map=cedict_style_penalty_map,
        term_semantic_bonus_map=cedict_semantic_bonus_map,
        preferred_terms=curated_daily_tc_terms,
        stats_prefix="tc",
        weak_leader_terms=curated_daily_supplement_tc_terms,
    )
    stats.update(tc_homophone_stats)
    tc_short_domain_cap_stats = _cap_short_domain_terms_against_direct_common(
        tc_map,
        usage_score_map=tc_usage_score_map,
        source_hits_map=tc_source_hits_map,
        pageviews_signal_map=tc_pageviews_signal_map,
        wiki_titles=wiki_titles,
        wiki_augmented_terms=tc_augmented_terms,
        jieba_direct_signal_map=tc_jieba_direct_signal_map,
        jieba_pos_map=tc_jieba_pos_map,
        char_frequency_prior=tc_char_frequency_prior,
        preferred_terms=curated_daily_tc_terms,
        stats_prefix="tc",
        weak_leader_terms=curated_daily_supplement_tc_terms,
    )
    stats.update(tc_short_domain_cap_stats)
    tc_low_signal_stats = _filter_low_signal_rare_entries(
        tc_map,
        usage_score_map=tc_usage_score_map,
        source_hits_map=tc_source_hits_map,
        pageviews_signal_map=tc_pageviews_signal_map,
        wiki_titles=wiki_titles,
        wiki_augmented_terms=tc_augmented_terms,
        jieba_direct_signal_map=tc_jieba_direct_signal_map,
        jieba_pos_map=tc_jieba_pos_map,
        char_frequency_prior=tc_char_frequency_prior,
        term_style_penalty_map=cedict_style_penalty_map,
        stats_prefix="tc",
    )
    stats.update(tc_low_signal_stats)
    tc_global_tail_stats = _filter_global_tail_entries(
        tc_map,
        usage_score_map=tc_usage_score_map,
        source_hits_map=tc_source_hits_map,
        pageviews_signal_map=tc_pageviews_signal_map,
        wiki_titles=wiki_titles,
        wiki_augmented_terms=tc_augmented_terms,
        jieba_direct_signal_map=tc_jieba_direct_signal_map,
        jieba_pos_map=tc_jieba_pos_map,
        char_frequency_prior=tc_char_frequency_prior,
        term_style_penalty_map=cedict_style_penalty_map,
        unihan_readings_map=unihan_readings_map,
        unihan_source_rank_map=unihan_reading_source_map,
        unihan_mandarin_map=unihan_map,
        unihan_pinlu_detail_map=unihan_pinlu_detail_map,
        stats_prefix="tc",
    )
    stats.update(tc_global_tail_stats)
    tc_sc_guided_multi_pronunciation_stats = _propagate_tc_multi_pronunciation_preference_from_sc(
        sc_map,
        tc_map,
        tc_to_sc_map,
        stats_prefix="tc",
    )
    stats.update(tc_sc_guided_multi_pronunciation_stats)
    tc_sc_guided_homophone_stats = _propagate_tc_homophone_preference_from_sc(
        sc_map,
        tc_map,
        tc_to_sc_map,
        stats_prefix="tc",
    )
    stats.update(tc_sc_guided_homophone_stats)

    sc_map, sc_explicit_drop_rows = _drop_explicit_multi_char_terms(
        sc_map,
        MULTI_CHAR_TERM_DROP_OVERRIDES,
    )
    tc_map, tc_explicit_drop_rows = _drop_explicit_multi_char_terms(
        tc_map,
        MULTI_CHAR_TERM_DROP_OVERRIDES,
    )
    stats["sc_explicit_multi_char_drop_rows"] = sc_explicit_drop_rows
    stats["tc_explicit_multi_char_drop_rows"] = tc_explicit_drop_rows

    sc_map = _apply_limit(sc_map, args.max_entries)
    tc_map = _apply_limit(tc_map, args.max_entries)
    sc_map, sc_civic_neutral_stats = _apply_neutral_civic_weights(
        sc_map,
        civic_sc_terms,
        usage_score_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        char_frequency_prior,
        "sc_civic_neutral",
    )
    tc_map, tc_civic_neutral_stats = _apply_neutral_civic_weights(
        tc_map,
        civic_tc_terms,
        tc_usage_score_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        tc_char_frequency_prior,
        "tc_civic_neutral",
    )
    stats.update(sc_civic_neutral_stats)
    stats.update(tc_civic_neutral_stats)
    sc_map, sc_snapshot_restore_stats = _restore_missing_texts_from_snapshot(
        sc_map,
        previous_snapshot_sc,
        MULTI_CHAR_TERM_DROP_OVERRIDES,
        "sc",
        _build_curated_daily_prefix_restore_blocklist(
            curated_daily_entries,
            use_traditional=False,
        ),
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        char_frequency_prior,
        wiki_titles,
        sc_augmented_terms,
    )
    tc_map, tc_snapshot_restore_stats = _restore_missing_texts_from_snapshot(
        tc_map,
        previous_snapshot_tc,
        MULTI_CHAR_TERM_DROP_OVERRIDES,
        "tc",
        _build_curated_daily_prefix_restore_blocklist(
            curated_daily_entries,
            use_traditional=True,
        ),
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        tc_char_frequency_prior,
        wiki_titles,
        tc_augmented_terms,
        require_current_signal=True,
    )
    stats.update(sc_snapshot_restore_stats)
    stats.update(tc_snapshot_restore_stats)
    sc_prefix_fragment_stats = _filter_low_signal_prefix_fragment_entries(
        sc_map,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        wiki_titles,
        sc_augmented_terms,
        "sc",
    )
    tc_prefix_fragment_stats = _filter_low_signal_prefix_fragment_entries(
        tc_map,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        wiki_titles,
        tc_augmented_terms,
        "tc",
    )
    stats.update(sc_prefix_fragment_stats)
    stats.update(tc_prefix_fragment_stats)
    (
        admin_place_alias_stats,
        admin_place_alias_sc_terms,
        admin_place_alias_tc_terms,
    ) = _augment_with_admin_place_short_aliases(
        sc_map,
        tc_map,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        jieba_direct_signal_map,
        tc_jieba_direct_signal_map,
        jieba_pos_map,
        tc_jieba_pos_map,
        char_frequency_prior,
        tc_char_frequency_prior,
        opencc_entries,
        simp_to_trad_char_map,
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_detail_map,
        args.min_hanzi,
    )
    stats.update(admin_place_alias_stats)
    stats["admin_place_alias_augmented_sc_terms"] = len(admin_place_alias_sc_terms)
    stats["admin_place_alias_augmented_tc_terms"] = len(admin_place_alias_tc_terms)
    curated_daily_sc_final_stats = _reinforce_curated_daily_sc_phrases(
        sc_map,
        curated_daily_entries,
        curated_usage_score_map,
        curated_source_hits_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        char_frequency_prior,
        curated_unihan_map,
        curated_unihan_readings_map,
        curated_unihan_source_rank_map,
        curated_unihan_pinlu_detail_map,
        args.min_hanzi,
    )
    curated_daily_tc_final_stats = _reinforce_curated_daily_tc_phrases(
        tc_map,
        curated_daily_entries,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        tc_char_frequency_prior,
        opencc_entries,
        simp_to_trad_char_map,
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_detail_map,
        args.min_hanzi,
    )
    stats.update(
        {
            f"final_{key}": value
            for key, value in curated_daily_sc_final_stats.items()
        }
    )
    stats.update(
        {
            f"final_{key}": value
            for key, value in curated_daily_tc_final_stats.items()
        }
    )
    sc_curated_daily_prefix_final_stats = _reinforce_curated_daily_existing_prefixes(
        sc_map,
        curated_daily_entries,
        usage_score_map,
        source_hits_map,
        jieba_pos_map,
        char_frequency_prior,
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_detail_map,
        use_traditional=False,
        stats_prefix="sc",
        min_hanzi=args.min_hanzi,
    )
    tc_curated_daily_prefix_final_stats = _reinforce_curated_daily_existing_prefixes(
        tc_map,
        curated_daily_entries,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_jieba_pos_map,
        tc_char_frequency_prior,
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_detail_map,
        use_traditional=True,
        stats_prefix="tc",
        min_hanzi=args.min_hanzi,
    )
    stats.update(sc_curated_daily_prefix_final_stats)
    stats.update(tc_curated_daily_prefix_final_stats)
    sc_curated_daily_suffix_final_stats = _reinforce_curated_daily_existing_suffixes(
        sc_map,
        curated_daily_entries,
        usage_score_map,
        source_hits_map,
        jieba_pos_map,
        char_frequency_prior,
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_detail_map,
        use_traditional=False,
        stats_prefix="sc",
        min_hanzi=args.min_hanzi,
    )
    tc_curated_daily_suffix_final_stats = _reinforce_curated_daily_existing_suffixes(
        tc_map,
        curated_daily_entries,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_jieba_pos_map,
        tc_char_frequency_prior,
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_detail_map,
        use_traditional=True,
        stats_prefix="tc",
        min_hanzi=args.min_hanzi,
    )
    stats.update(sc_curated_daily_suffix_final_stats)
    stats.update(tc_curated_daily_suffix_final_stats)
    sc_curated_daily_prefix_competitor_stats = _cap_curated_daily_prefix_competitors(
        sc_map,
        curated_daily_entries,
        usage_score_map,
        jieba_pos_map,
        char_frequency_prior,
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_detail_map,
        use_traditional=False,
        stats_prefix="sc",
        min_hanzi=args.min_hanzi,
    )
    tc_curated_daily_prefix_competitor_stats = _cap_curated_daily_prefix_competitors(
        tc_map,
        curated_daily_entries,
        tc_usage_score_map,
        tc_jieba_pos_map,
        tc_char_frequency_prior,
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_detail_map,
        use_traditional=True,
        stats_prefix="tc",
        min_hanzi=args.min_hanzi,
    )
    stats.update(sc_curated_daily_prefix_competitor_stats)
    stats.update(tc_curated_daily_prefix_competitor_stats)
    sc_curated_daily_number_cap_stats = _cap_curated_daily_number_weights(
        sc_map,
        curated_daily_entries,
        use_traditional=False,
        stats_prefix="sc",
    )
    tc_curated_daily_number_cap_stats = _cap_curated_daily_number_weights(
        tc_map,
        curated_daily_entries,
        use_traditional=True,
        stats_prefix="tc",
    )
    stats.update(sc_curated_daily_number_cap_stats)
    stats.update(tc_curated_daily_number_cap_stats)
    idiom_allusion_sc_terms = {
        sc_word
        for sc_word, _tc_word, _usage_score, _explicit_pinyin, layer_id, _source_id in vertical_entries
        if layer_id == "idioms_allusions"
    }
    tc_map, tc_idiom_variant_merge_stats = _merge_tc_simplified_terms_into_existing_traditional_targets(
        tc_map,
        idiom_allusion_sc_terms,
        simp_to_trad_char_map,
        "tc_idiom_allusion",
    )
    stats.update(tc_idiom_variant_merge_stats)
    preferred_tc_by_sc: Dict[str, str] = {}
    for sc_word, tc_word, _usage_score, _explicit_pinyin in curated_daily_entries:
        if sc_word and tc_word:
            preferred_tc_by_sc[sc_word] = tc_word
    for sc_word, tc_word, _usage_score, _explicit_pinyin in curated_daily_supplement_entries:
        if sc_word and tc_word:
            preferred_tc_by_sc.setdefault(sc_word, tc_word)
    for sc_word, tc_word, _usage_score, _explicit_pinyin, _layer_id, source_id in vertical_entries:
        if sc_word and tc_word and source_id.startswith("project-curated"):
            preferred_tc_by_sc.setdefault(sc_word, tc_word)
    tc_map, tc_project_preferred_merge_stats = _merge_tc_converted_variants_into_preferred_targets(
        tc_map,
        preferred_tc_by_sc,
        simp_to_trad_char_map,
        "tc_project_preferred",
    )
    stats.update(tc_project_preferred_merge_stats)
    sc_map, sc_word_pinyin_override_stats = _apply_word_pinyin_overrides(
        sc_map,
        word_pinyin_overrides,
        "sc_word_pinyin_override",
    )
    tc_map, tc_word_pinyin_override_stats = _apply_word_pinyin_overrides(
        tc_map,
        word_pinyin_overrides,
        "tc_word_pinyin_override",
    )
    stats.update(sc_word_pinyin_override_stats)
    stats.update(tc_word_pinyin_override_stats)
    stats["word_pinyin_override_entries"] = len(word_pinyin_overrides)
    sc_final_prefix_fragment_stats = _filter_low_signal_prefix_fragment_entries(
        sc_map,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        wiki_titles,
        sc_augmented_terms,
        "sc_final",
        respect_source_signal=False,
    )
    tc_final_prefix_fragment_stats = _filter_low_signal_prefix_fragment_entries(
        tc_map,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        wiki_titles,
        tc_augmented_terms,
        "tc_final",
        respect_source_signal=False,
    )
    stats.update(sc_final_prefix_fragment_stats)
    stats.update(tc_final_prefix_fragment_stats)
    sc_medical_specific_cap_stats = _cap_medical_specific_term_weights(
        sc_map,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        curated_daily_sc_terms,
        "sc",
    )
    tc_medical_specific_cap_stats = _cap_medical_specific_term_weights(
        tc_map,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        curated_daily_tc_terms,
        "tc",
    )
    stats.update(sc_medical_specific_cap_stats)
    stats.update(tc_medical_specific_cap_stats)
    sc_low_signal_short_cap_stats = _cap_low_signal_short_term_weights(
        sc_map,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        cedict_semantic_bonus_map,
        curated_daily_sc_terms | curated_daily_supplement_sc_terms,
        "sc",
    )
    tc_low_signal_short_cap_stats = _cap_low_signal_short_term_weights(
        tc_map,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        cedict_semantic_bonus_map,
        curated_daily_tc_terms | curated_daily_supplement_tc_terms,
        "tc",
    )
    stats.update(sc_low_signal_short_cap_stats)
    stats.update(tc_low_signal_short_cap_stats)
    sc_low_independent_prefix_cap_stats = _cap_low_independent_prefix_fragment_weights(
        sc_map,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        wiki_titles,
        sc_augmented_terms,
        curated_daily_sc_terms | curated_daily_supplement_sc_terms,
        "sc",
    )
    tc_low_independent_prefix_cap_stats = _cap_low_independent_prefix_fragment_weights(
        tc_map,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        wiki_titles,
        tc_augmented_terms,
        curated_daily_tc_terms | curated_daily_supplement_tc_terms,
        "tc",
    )
    stats.update(sc_low_independent_prefix_cap_stats)
    stats.update(tc_low_independent_prefix_cap_stats)
    sc_low_signal_redup_cap_stats = _cap_low_signal_reduplicated_term_weights(
        sc_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        curated_daily_sc_terms | curated_daily_supplement_sc_terms,
        "sc",
    )
    tc_low_signal_redup_cap_stats = _cap_low_signal_reduplicated_term_weights(
        tc_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        curated_daily_tc_terms | curated_daily_supplement_tc_terms,
        "tc",
    )
    stats.update(sc_low_signal_redup_cap_stats)
    stats.update(tc_low_signal_redup_cap_stats)

    # Snapshot restore and late augmenters can reintroduce stale rows that were
    # valid in a previous build but are no longer script-compatible after the
    # current SC/TC normalization rules. Run a final script pass so generated
    # TC output does not keep obsolete simplified variants (and vice versa).
    sc_map, sc_final_script_filter_stats = _filter_sc_mapping_with_script_hints(
        sc_map,
        sc_script_chars,
        tc_script_chars,
    )
    tc_map, tc_final_script_filter_stats = _filter_tc_mapping_with_script_hints(
        tc_map,
        sc_script_chars,
        tc_script_chars,
    )
    stats.update(
        {
            f"final_{key}": value
            for key, value in sc_final_script_filter_stats.items()
        }
    )
    stats.update(
        {
            f"final_{key}": value
            for key, value in tc_final_script_filter_stats.items()
        }
    )
    sc_negated_predicate_stats = _promote_negated_predicate_homophone_terms(
        sc_map,
        term_semantic_bonus_map=cedict_semantic_bonus_map,
        stats_prefix="sc_final",
    )
    tc_negated_predicate_stats = _promote_negated_predicate_homophone_terms(
        tc_map,
        term_semantic_bonus_map=cedict_semantic_bonus_map,
        stats_prefix="tc_final",
    )
    stats.update(sc_negated_predicate_stats)
    stats.update(tc_negated_predicate_stats)
    stats.update(_remove_known_incorrect_jiancha_entries(sc_map, tc_map))
    sc_query_path_priors: Dict[Tuple[str, str], int] = {}
    tc_query_path_priors: Dict[Tuple[str, str], int] = {}
    sc_lm_transition_priors: Dict[Tuple[str, str], int] = {}
    tc_lm_transition_priors: Dict[Tuple[str, str], int] = {}
    sc_transition_completion_index: Dict[Tuple[str, str, str, str], int] = {}
    tc_transition_completion_index: Dict[Tuple[str, str, str, str], int] = {}
    sc_transition_completion_evidence: Dict[
        Tuple[str, str], Tuple[int, int, int, int, int, int, float, float, int]
    ] = {}
    tc_transition_completion_evidence: Dict[
        Tuple[str, str], Tuple[int, int, int, int, int, int, float, float, int]
    ] = {}
    query_path_lm_corpus_dir = repo_root / args.query_path_lm_corpus_dir if args.query_path_lm_corpus_dir else None
    if (
        output_lm_transition_sc is not None
        or output_lm_transition_tc is not None
        or output_transition_completion_sc is not None
        or output_transition_completion_tc is not None
    ) and query_path_lm_corpus_dir is None:
        raise ValueError(
            "LM transition/completion output requires --query-path-lm-corpus-dir"
        )
    if (
        output_query_path_sc is not None
        or output_lm_transition_sc is not None
        or output_transition_completion_sc is not None
    ):
        sc_query_path_priors, sc_query_path_stats = _build_query_path_prior_map(
            sc_map,
            usage_score_map=usage_score_map,
            source_hits_map=source_hits_map,
            pageviews_signal_map=pageviews_signal_map,
            jieba_direct_signal_map=jieba_direct_signal_map,
            jieba_pos_map=jieba_pos_map,
            char_frequency_prior=char_frequency_prior,
            stats_prefix="sc",
        )
        stats.update(sc_query_path_stats)
        if (
            output_lm_transition_sc is not None
            or output_transition_completion_sc is not None
        ) and query_path_lm_corpus_dir is not None:
            sc_lm_query_path_priors, sc_lm_query_path_stats = _build_lm_corpus_query_path_prior_map(
                sc_map,
                query_path_lm_corpus_dir,
                convert_text=lambda text: _convert_text_with_char_map(text, trad_to_simp_char_map),
                additional_exact_texts={
                    sc_word
                    for sc_word, _tc_word, _usage_score, _explicit_pinyin
                    in curated_daily_post_rank_exact_entries
                },
                single_char_readings_map=output_unihan_readings_map,
                single_char_default_pinyin_map=output_unihan_map,
                single_char_source_rank_map=output_unihan_source_rank_map,
                single_char_pinlu_detail_map=output_unihan_pinlu_detail_map,
                char_frequency_prior=char_frequency_prior,
                jieba_pos_map=jieba_pos_map,
                stats_prefix="sc",
                exact_pairs_only=args.lm_transition_exact_pairs_only,
                general_transitions_only=args.lm_transition_general_only,
                completion_evidence_out=sc_transition_completion_evidence,
            )
            stats.update(sc_lm_query_path_stats)
            if output_transition_completion_sc is not None:
                (
                    sc_transition_completion_index,
                    sc_transition_completion_stats,
                ) = _build_transition_completion_index(
                    sc_map,
                    sc_transition_completion_evidence,
                    unihan_map=output_unihan_map,
                    unihan_readings_map=output_unihan_readings_map,
                    unihan_source_rank_map=output_unihan_source_rank_map,
                    unihan_pinlu_detail_map=output_unihan_pinlu_detail_map,
                    stats_prefix="sc",
                )
                stats.update(sc_transition_completion_stats)
            if output_lm_transition_sc is not None:
                sc_lm_transition_priors, sc_lm_transition_stats = _select_dedicated_lm_transitions(
                    sc_query_path_priors,
                    sc_lm_query_path_priors,
                    stats_prefix="sc",
                )
                stats.update(sc_lm_transition_stats)
                sc_lm_transition_priors, sc_lm_merge_stats = _merge_frozen_lm_transitions(
                    baseline_lm_transition_sc,
                    sc_lm_transition_priors,
                    stats_prefix="sc",
                )
                stats.update(sc_lm_merge_stats)
        stats["sc_query_path_prior_rows"] = len(sc_query_path_priors)
    if (
        output_query_path_tc is not None
        or output_lm_transition_tc is not None
        or output_transition_completion_tc is not None
    ):
        tc_query_path_priors, tc_query_path_stats = _build_query_path_prior_map(
            tc_map,
            usage_score_map=tc_usage_score_map,
            source_hits_map=tc_source_hits_map,
            pageviews_signal_map=tc_pageviews_signal_map,
            jieba_direct_signal_map=tc_jieba_direct_signal_map,
            jieba_pos_map=tc_jieba_pos_map,
            char_frequency_prior=tc_char_frequency_prior,
            stats_prefix="tc",
        )
        stats.update(tc_query_path_stats)
        if (
            output_lm_transition_tc is not None
            or output_transition_completion_tc is not None
        ) and query_path_lm_corpus_dir is not None:
            opencc_sc_to_tc_for_lm = _build_opencc_sc_to_tc_map(opencc_entries) if opencc_entries else {}
            tc_lm_query_path_priors, tc_lm_query_path_stats = _build_lm_corpus_query_path_prior_map(
                tc_map,
                query_path_lm_corpus_dir,
                convert_text=lambda text: _convert_sc_text_to_tc_with_phrase_hints(
                    text,
                    opencc_sc_to_tc_for_lm,
                    simp_to_trad_char_map,
                ),
                additional_exact_texts={
                    tc_word or sc_word
                    for sc_word, tc_word, _usage_score, _explicit_pinyin
                    in curated_daily_post_rank_exact_entries
                },
                single_char_readings_map=output_unihan_readings_map,
                single_char_default_pinyin_map=output_unihan_map,
                single_char_source_rank_map=output_unihan_source_rank_map,
                single_char_pinlu_detail_map=output_unihan_pinlu_detail_map,
                char_frequency_prior=tc_char_frequency_prior,
                jieba_pos_map=tc_jieba_pos_map,
                stats_prefix="tc",
                exact_pairs_only=args.lm_transition_exact_pairs_only,
                general_transitions_only=args.lm_transition_general_only,
                completion_evidence_out=tc_transition_completion_evidence,
            )
            stats.update(tc_lm_query_path_stats)
            if output_transition_completion_tc is not None:
                (
                    tc_transition_completion_index,
                    tc_transition_completion_stats,
                ) = _build_transition_completion_index(
                    tc_map,
                    tc_transition_completion_evidence,
                    unihan_map=output_unihan_map,
                    unihan_readings_map=output_unihan_readings_map,
                    unihan_source_rank_map=output_unihan_source_rank_map,
                    unihan_pinlu_detail_map=output_unihan_pinlu_detail_map,
                    stats_prefix="tc",
                )
                stats.update(tc_transition_completion_stats)
            if output_lm_transition_tc is not None:
                tc_lm_transition_priors, tc_lm_transition_stats = _select_dedicated_lm_transitions(
                    tc_query_path_priors,
                    tc_lm_query_path_priors,
                    stats_prefix="tc",
                )
                stats.update(tc_lm_transition_stats)
                tc_lm_transition_priors, tc_lm_merge_stats = _merge_frozen_lm_transitions(
                    baseline_lm_transition_tc,
                    tc_lm_transition_priors,
                    stats_prefix="tc",
                )
                stats.update(tc_lm_merge_stats)
        stats["tc_query_path_prior_rows"] = len(tc_query_path_priors)
    suspicious_sc_entries = _collect_suspicious_high_weight_entries(
        sc_map,
        usage_score_map=usage_score_map,
        source_hits_map=source_hits_map,
        pageviews_signal_map=pageviews_signal_map,
        wiki_titles=wiki_titles,
        wiki_augmented_terms=wiki_alias_sc_terms,
        jieba_direct_signal_map=jieba_direct_signal_map,
        jieba_pos_map=jieba_pos_map,
        char_frequency_prior=char_frequency_prior,
    )
    sc_curated_daily_visibility_cap_stats = _cap_curated_daily_visibility_exact_weights(
        sc_map,
        curated_daily_entries,
        opencc_entries,
        simp_to_trad_char_map,
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_detail_map,
        use_traditional=False,
        stats_prefix="sc",
        min_hanzi=args.min_hanzi,
    )
    tc_curated_daily_visibility_cap_stats = _cap_curated_daily_visibility_exact_weights(
        tc_map,
        curated_daily_entries,
        opencc_entries,
        simp_to_trad_char_map,
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_detail_map,
        use_traditional=True,
        stats_prefix="tc",
        min_hanzi=args.min_hanzi,
    )
    stats.update(sc_curated_daily_visibility_cap_stats)
    stats.update(tc_curated_daily_visibility_cap_stats)
    sc_curated_daily_supplement_cap_stats = _cap_curated_daily_supplement_exact_weights(
        sc_map,
        curated_daily_supplement_entries,
        opencc_entries,
        simp_to_trad_char_map,
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_detail_map,
        use_traditional=False,
        stats_prefix="sc",
        min_hanzi=args.min_hanzi,
    )
    tc_curated_daily_supplement_cap_stats = _cap_curated_daily_supplement_exact_weights(
        tc_map,
        curated_daily_supplement_entries,
        opencc_entries,
        simp_to_trad_char_map,
        unihan_map,
        unihan_readings_map,
        unihan_reading_source_map,
        unihan_pinlu_detail_map,
        use_traditional=True,
        stats_prefix="tc",
        min_hanzi=args.min_hanzi,
    )
    stats.update(sc_curated_daily_supplement_cap_stats)
    stats.update(tc_curated_daily_supplement_cap_stats)
    stats.update(
        _cap_project_vertical_exact_weights(
            sc_map,
            vertical_entries,
            use_traditional=False,
            stats_prefix="sc",
        )
    )
    stats.update(
        _cap_project_vertical_exact_weights(
            tc_map,
            vertical_entries,
            use_traditional=True,
            stats_prefix="tc",
        )
    )
    sc_low_signal_competitor_cap_stats = _cap_low_signal_competitors_against_direct_leaders(
        sc_map,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        char_frequency_prior,
        curated_daily_sc_terms,
        curated_daily_supplement_sc_terms,
        "sc",
        term_semantic_bonus_map=cedict_semantic_bonus_map,
        term_style_penalty_map=cedict_style_penalty_map,
    )
    tc_low_signal_competitor_cap_stats = _cap_low_signal_competitors_against_direct_leaders(
        tc_map,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        tc_char_frequency_prior,
        curated_daily_tc_terms,
        curated_daily_supplement_tc_terms,
        "tc",
        term_semantic_bonus_map=cedict_semantic_bonus_map,
        term_style_penalty_map=cedict_style_penalty_map,
    )
    stats.update(sc_low_signal_competitor_cap_stats)
    stats.update(tc_low_signal_competitor_cap_stats)
    sc_productive_short_root_stats = _boost_high_productivity_short_roots(
        sc_map,
        source_hits_map,
        jieba_pos_map,
        "sc",
    )
    tc_productive_short_root_stats = _boost_high_productivity_short_roots(
        tc_map,
        tc_source_hits_map,
        tc_jieba_pos_map,
        "tc",
    )
    stats.update(sc_productive_short_root_stats)
    stats.update(tc_productive_short_root_stats)
    sc_curated_daily_aspect_cap_stats = _cap_curated_daily_aspect_visibility_weights(
        sc_map,
        curated_daily_entries,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        use_traditional=False,
        stats_prefix="sc",
    )
    tc_curated_daily_aspect_cap_stats = _cap_curated_daily_aspect_visibility_weights(
        tc_map,
        curated_daily_entries,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        use_traditional=True,
        stats_prefix="tc",
    )
    stats.update(sc_curated_daily_aspect_cap_stats)
    stats.update(tc_curated_daily_aspect_cap_stats)
    sc_styled_competitor_cap_stats = _cap_styled_exact_competitors(
        sc_map,
        cedict_style_penalty_map,
        usage_score_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        stats_prefix="sc",
    )
    tc_styled_competitor_cap_stats = _cap_styled_exact_competitors(
        tc_map,
        cedict_style_penalty_map,
        tc_usage_score_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        stats_prefix="tc",
    )
    stats.update(sc_styled_competitor_cap_stats)
    stats.update(tc_styled_competitor_cap_stats)
    curated_daily_explicit_pinyin_keys = _build_curated_daily_explicit_pinyin_key_set(
        curated_daily_entries + curated_daily_supplement_entries
    )
    curated_daily_explicit_pinyin_keys.update(
        _build_vertical_explicit_pinyin_key_set(vertical_entries)
    )
    curated_daily_explicit_pinyin_keys.update(
        (pinyin, text)
        for text, pinyin in word_pinyin_overrides.items()
        if text and "'" in pinyin
    )
    sc_output_pinyin_bucket_map = _build_output_pinyin_bucket_map(
        sc_map,
        preserve_pinyin_keys=curated_daily_explicit_pinyin_keys,
        unihan_map=output_unihan_map,
        unihan_readings_map=output_unihan_readings_map,
        unihan_source_rank_map=output_unihan_source_rank_map,
        unihan_pinlu_detail_map=output_unihan_pinlu_detail_map,
    )
    tc_output_pinyin_bucket_map = _build_output_pinyin_bucket_map(
        tc_map,
        preserve_pinyin_keys=curated_daily_explicit_pinyin_keys,
        unihan_map=output_unihan_map,
        unihan_readings_map=output_unihan_readings_map,
        unihan_source_rank_map=output_unihan_source_rank_map,
        unihan_pinlu_detail_map=output_unihan_pinlu_detail_map,
    )
    sc_final_low_signal_competitor_cap_stats = _cap_low_signal_competitors_against_direct_leaders(
        sc_map,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        char_frequency_prior,
        curated_daily_sc_terms,
        curated_daily_supplement_sc_terms,
        "sc_final",
        bucket_pinyin_map=sc_output_pinyin_bucket_map,
        term_semantic_bonus_map=cedict_semantic_bonus_map,
        term_style_penalty_map=cedict_style_penalty_map,
    )
    tc_final_low_signal_competitor_cap_stats = _cap_low_signal_competitors_against_direct_leaders(
        tc_map,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        tc_char_frequency_prior,
        curated_daily_tc_terms,
        curated_daily_supplement_tc_terms,
        "tc_final",
        bucket_pinyin_map=tc_output_pinyin_bucket_map,
        term_semantic_bonus_map=cedict_semantic_bonus_map,
        term_style_penalty_map=cedict_style_penalty_map,
    )
    stats.update(sc_final_low_signal_competitor_cap_stats)
    stats.update(tc_final_low_signal_competitor_cap_stats)
    sc_final_normative_homophone_stats = _enforce_final_normative_homophone_order(
        sc_map,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        char_frequency_prior,
        cedict_style_penalty_map,
        cedict_semantic_bonus_map,
        "sc_final",
        bucket_pinyin_map=sc_output_pinyin_bucket_map,
        protected_terms=curated_daily_supplement_sc_terms,
    )
    tc_final_normative_homophone_stats = _enforce_final_normative_homophone_order(
        tc_map,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        tc_char_frequency_prior,
        cedict_style_penalty_map,
        cedict_semantic_bonus_map,
        "tc_final",
        bucket_pinyin_map=tc_output_pinyin_bucket_map,
        protected_terms=curated_daily_supplement_tc_terms,
    )
    stats.update(sc_final_normative_homophone_stats)
    stats.update(tc_final_normative_homophone_stats)
    sc_final_short_exact_direct_stats = _cap_short_exact_homophones_by_direct_signal(
        sc_map,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        char_frequency_prior,
        curated_daily_sc_terms,
        curated_daily_supplement_sc_terms,
        "sc_final",
        bucket_pinyin_map=sc_output_pinyin_bucket_map,
        term_style_penalty_map=cedict_style_penalty_map,
        term_semantic_bonus_map=cedict_semantic_bonus_map,
    )
    tc_final_short_exact_direct_stats = _cap_short_exact_homophones_by_direct_signal(
        tc_map,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        tc_char_frequency_prior,
        curated_daily_tc_terms,
        curated_daily_supplement_tc_terms,
        "tc_final",
        bucket_pinyin_map=tc_output_pinyin_bucket_map,
        term_style_penalty_map=cedict_style_penalty_map,
        term_semantic_bonus_map=cedict_semantic_bonus_map,
    )
    stats.update(sc_final_short_exact_direct_stats)
    stats.update(tc_final_short_exact_direct_stats)
    sc_final_curated_exact_leader_stats = _cap_weak_exact_homophones_against_curated_daily_leaders(
        sc_map,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        curated_daily_sc_terms,
        curated_daily_supplement_sc_terms,
        "sc_final",
        bucket_pinyin_map=sc_output_pinyin_bucket_map,
        term_style_penalty_map=cedict_style_penalty_map,
        term_semantic_bonus_map=cedict_semantic_bonus_map,
    )
    tc_final_curated_exact_leader_stats = _cap_weak_exact_homophones_against_curated_daily_leaders(
        tc_map,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        curated_daily_tc_terms,
        curated_daily_supplement_tc_terms,
        "tc_final",
        bucket_pinyin_map=tc_output_pinyin_bucket_map,
        term_style_penalty_map=cedict_style_penalty_map,
        term_semantic_bonus_map=cedict_semantic_bonus_map,
    )
    stats.update(sc_final_curated_exact_leader_stats)
    stats.update(tc_final_curated_exact_leader_stats)
    sc_final_curated_productive_visibility_stats = _cap_curated_productive_visibility_against_direct_leaders(
        sc_map,
        curated_daily_entries + curated_daily_supplement_entries,
        usage_score_map,
        source_hits_map,
        pageviews_signal_map,
        jieba_direct_signal_map,
        jieba_pos_map,
        use_traditional=False,
        stats_prefix="sc_final",
        bucket_pinyin_map=sc_output_pinyin_bucket_map,
    )
    tc_final_curated_productive_visibility_stats = _cap_curated_productive_visibility_against_direct_leaders(
        tc_map,
        curated_daily_entries + curated_daily_supplement_entries,
        tc_usage_score_map,
        tc_source_hits_map,
        tc_pageviews_signal_map,
        tc_jieba_direct_signal_map,
        tc_jieba_pos_map,
        use_traditional=True,
        stats_prefix="tc_final",
        bucket_pinyin_map=tc_output_pinyin_bucket_map,
    )
    stats.update(sc_final_curated_productive_visibility_stats)
    stats.update(tc_final_curated_productive_visibility_stats)
    sc_de_complement_pair_cap_stats = _cap_curated_daily_de_complement_pair_weights(
        sc_map,
        curated_daily_entries,
        use_traditional=False,
        stats_prefix="sc_final",
    )
    tc_de_complement_pair_cap_stats = _cap_curated_daily_de_complement_pair_weights(
        tc_map,
        curated_daily_entries,
        use_traditional=True,
        stats_prefix="tc_final",
    )
    stats.update(sc_de_complement_pair_cap_stats)
    stats.update(tc_de_complement_pair_cap_stats)
    sc_single_char_rebalance_stats = _rebalance_single_char_homophones_by_leading_support(
        sc_map,
        sc_leading_term_count_map,
        sc_leading_support_sum_map,
        sc_family_support_sum_map,
        unihan_pinlu_detail_map,
        "sc_final",
        single_char_frequency_map=single_char_frequency_map,
    )
    tc_single_char_rebalance_stats = _rebalance_single_char_homophones_by_leading_support(
        tc_map,
        tc_leading_term_count_map,
        tc_leading_support_sum_map,
        tc_family_support_sum_map,
        unihan_pinlu_detail_map,
        "tc_final",
        single_char_frequency_map=tc_single_char_frequency_map,
    )
    stats.update(sc_single_char_rebalance_stats)
    stats.update(tc_single_char_rebalance_stats)
    sc_single_char_head_productivity_stats = _promote_single_char_homophones_by_head_productivity(
        sc_map,
        sc_leading_term_count_map,
        sc_leading_support_sum_map,
        sc_family_support_sum_map,
        unihan_pinlu_detail_map,
        "sc_final",
        single_char_frequency_map=single_char_frequency_map,
        single_char_pos_map=single_char_pos_map,
    )
    tc_single_char_head_productivity_stats = _promote_single_char_homophones_by_head_productivity(
        tc_map,
        tc_leading_term_count_map,
        tc_leading_support_sum_map,
        tc_family_support_sum_map,
        unihan_pinlu_detail_map,
        "tc_final",
        single_char_frequency_map=tc_single_char_frequency_map,
        single_char_pos_map=tc_single_char_pos_map,
    )
    stats.update(sc_single_char_head_productivity_stats)
    stats.update(tc_single_char_head_productivity_stats)
    sc_single_char_compound_root_stats = _dampen_compound_root_inflated_single_chars(
        sc_map,
        sc_leading_support_sum_map,
        sc_family_support_sum_map,
        unihan_pinlu_detail_map,
        single_char_frequency_map,
        "sc_final",
    )
    tc_single_char_compound_root_stats = _dampen_compound_root_inflated_single_chars(
        tc_map,
        tc_leading_support_sum_map,
        tc_family_support_sum_map,
        unihan_pinlu_detail_map,
        tc_single_char_frequency_map,
        "tc_final",
    )
    stats.update(sc_single_char_compound_root_stats)
    stats.update(tc_single_char_compound_root_stats)
    sc_single_char_final_input_stats = _promote_single_char_homophones_by_head_productivity(
        sc_map,
        sc_leading_term_count_map,
        sc_leading_support_sum_map,
        sc_family_support_sum_map,
        unihan_pinlu_detail_map,
        "sc_final_post",
        single_char_frequency_map=single_char_frequency_map,
        single_char_pos_map=single_char_pos_map,
    )
    tc_single_char_final_input_stats = _promote_single_char_homophones_by_head_productivity(
        tc_map,
        tc_leading_term_count_map,
        tc_leading_support_sum_map,
        tc_family_support_sum_map,
        unihan_pinlu_detail_map,
        "tc_final_post",
        single_char_frequency_map=tc_single_char_frequency_map,
        single_char_pos_map=tc_single_char_pos_map,
    )
    stats.update(sc_single_char_final_input_stats)
    stats.update(tc_single_char_final_input_stats)
    tc_final_sc_guided_homophone_stats = _propagate_tc_homophone_preference_from_sc(
        sc_map,
        tc_map,
        tc_to_sc_map,
        stats_prefix="tc_final_post",
        min_boost_gap=20,
        force_sc_leader_order=True,
    )
    stats.update(tc_final_sc_guided_homophone_stats)
    sc_strong_curated_daily_exact_stats = _restore_strong_curated_daily_exact_weights(
        sc_map,
        curated_daily_entries,
        opencc_entries,
        simp_to_trad_char_map,
        output_unihan_map,
        output_unihan_readings_map,
        output_unihan_source_rank_map,
        output_unihan_pinlu_detail_map,
        use_traditional=False,
        stats_prefix="sc_final_post",
        min_hanzi=args.min_hanzi,
    )
    tc_strong_curated_daily_exact_stats = _restore_strong_curated_daily_exact_weights(
        tc_map,
        curated_daily_entries,
        opencc_entries,
        simp_to_trad_char_map,
        output_unihan_map,
        output_unihan_readings_map,
        output_unihan_source_rank_map,
        output_unihan_pinlu_detail_map,
        use_traditional=True,
        stats_prefix="tc_final_post",
        min_hanzi=args.min_hanzi,
    )
    stats.update(sc_strong_curated_daily_exact_stats)
    stats.update(tc_strong_curated_daily_exact_stats)
    stats.update(
        _cap_curated_daily_aspect_visibility_weights(
            sc_map,
            curated_daily_entries,
            usage_score_map,
            source_hits_map,
            pageviews_signal_map,
            jieba_direct_signal_map,
            jieba_pos_map,
            use_traditional=False,
            stats_prefix="sc_final_post",
        )
    )
    stats.update(
        _cap_curated_daily_aspect_visibility_weights(
            tc_map,
            curated_daily_entries,
            tc_usage_score_map,
            tc_source_hits_map,
            tc_pageviews_signal_map,
            tc_jieba_direct_signal_map,
            tc_jieba_pos_map,
            use_traditional=True,
            stats_prefix="tc_final_post",
        )
    )
    stats.update(
        _restore_project_proper_noun_exact_floor(
            sc_map,
            vertical_entries,
            use_traditional=False,
            stats_prefix="sc_final_post",
        )
    )
    stats.update(
        _restore_project_proper_noun_exact_floor(
            tc_map,
            vertical_entries,
            use_traditional=True,
            stats_prefix="tc_final_post",
        )
    )
    stats.update(
        _cap_curated_daily_de_complement_pair_weights(
            sc_map,
            curated_daily_entries,
            use_traditional=False,
            stats_prefix="sc_final_post",
        )
    )
    stats.update(
        _cap_curated_daily_de_complement_pair_weights(
            tc_map,
            curated_daily_entries,
            use_traditional=True,
            stats_prefix="tc_final_post",
        )
    )
    stats.update(
        _cap_low_signal_competitors_against_curated_supplement_terms(
            sc_map,
            curated_daily_supplement_sc_terms,
            curated_daily_sc_terms | curated_daily_supplement_sc_terms,
            usage_score_map,
            source_hits_map,
            pageviews_signal_map,
            jieba_direct_signal_map,
            jieba_pos_map,
            char_frequency_prior,
            wiki_titles,
            wiki_alias_sc_terms,
            "sc_final_post",
            bucket_pinyin_map=sc_output_pinyin_bucket_map,
        )
    )
    stats.update(
        _cap_low_signal_competitors_against_curated_supplement_terms(
            tc_map,
            curated_daily_supplement_tc_terms,
            curated_daily_tc_terms | curated_daily_supplement_tc_terms,
            tc_usage_score_map,
            tc_source_hits_map,
            tc_pageviews_signal_map,
            tc_jieba_direct_signal_map,
            tc_jieba_pos_map,
            tc_char_frequency_prior,
            wiki_titles,
            wiki_alias_tc_terms,
            "tc_final_post",
            bucket_pinyin_map=tc_output_pinyin_bucket_map,
        )
    )

    low_priority_supplement_sc_terms = {
        sc_word
        for sc_word, _tc_word, usage_score, _explicit_pinyin in curated_daily_supplement_entries
        if usage_score <= 0.0
    }
    low_priority_supplement_tc_terms = {
        tc_word
        for _sc_word, tc_word, usage_score, _explicit_pinyin in curated_daily_supplement_entries
        if usage_score <= 0.0
    }
    stable_tail_exact_sc_terms = {
        "安泰胶",
        "百得胶",
        "白云胶",
        "不被",
        "不全",
        "不同了",
        "扯下",
        "尝试一下",
        "持续到",
        "道康宁",
        "道康宁胶",
        "德高胶",
        "邓白氏",
        "东方雨虹",
        "孤鹜",
        "硅宝胶",
        "行高",
        "行楷",
        "汉高",
        "汉高百得",
        "会被",
        "汇文",
        "回天胶",
        "揭掉",
        "揭去",
        "揭下",
        "截掉",
        "截去",
        "截下",
        "金句",
        "科顺",
        "科顺防水",
        "马贝胶",
        "皮革厂",
        "取下",
        "撕下",
        "瓦克",
        "瓦克胶",
        "往上",
        "往右",
        "往左",
        "西卡",
        "西卡胶",
        "霞鹜",
        "霞鹜漫黑",
        "霞鹜文楷",
        "霞鹜文楷等宽",
        "霞鹜晰黑",
        "霞鹜新晰黑",
        "霞鹜新致宋",
        "之江胶",
        "篆体",
        "字间距",
        "字距",
        "字体名",
        "字重",
        "衬线",
        "无衬线",
        "衬线体",
        "无衬线体",
        "等宽",
        "等宽字体",
        "等宽体",
        "非等宽",
        "非等宽字体",
        "中文字体",
        "西文字体",
        "正文字体",
        "标题字体",
        "字体大小",
        "字体列表",
        "字体风格",
        "默认字体",
        "系统字体",
        "自画",
        "自绘",
        "卓宝",
        "提到过",
        "接受了",
        "无法接受",
        "主力产品",
        "视频通话",
        "甚至是",
        "编译运行",
        "花了",
        "靠着",
        "靠了",
        "卡着",
        "卡了",
        "盖了",
        "觉着",
        "搅着",
        "搅了",
        "嚼着",
        "嚼了",
        "滴着",
        "滴了",
        "沉了",
        "淹着",
        "淹了",
        "截了",
        "揭了",
        "泡着",
        "拖着",
        "拖了",
        "托着",
        "托了",
        "垫着",
        "垫了",
        "压着",
        "压了",
        "夹着",
        "夹了",
        "堵着",
        "堵了",
        "裹着",
        "裹了",
        "飘着",
        "飘了",
        "扣着",
        "扣了",
        "蹭着",
        "蹭了",
        "摁着",
        "摁了",
        "阉了",
        "㧟了",
        "㧟着",
        "薅了",
        "薅着",
        "情趣",
        "清癯",
        "睡不着",
        "睡着",
        "搞事",
        "搞事情",
        "抬起来",
        "睡好",
        "站好",
        "坐好",
        "走好",
        "打好",
        "过个",
        "吃得",
        "搭子",
        "雷点",
        "避坑",
        "拔草",
        "住了",
        "是会",
        "堵嘴",
        "在线等",
        "挺急",
        "蛮急",
        "氛围感",
        "挺胸",
        "戳中",
        "填上",
        "奔着",
        "更文",
        "薅住",
        "揪过来",
        "揪住",
        "揪着",
        "铐起",
        "铐着",
        "窸窸窣窣",
        "腰腿",
        "腿间",
        "趁我",
        "扶墙",
        "蒙头",
        "丢在",
        "两折",
        "抡圆",
        "绳缚",
        "硬拽",
        "拽回",
        "拽起",
        "抵在",
        "抵着",
        "趴好",
        "蹲好",
        "躺好",
        "敢弄",
        "敢做",
        "敢当",
        "就往",
        "死里",
        "拇指铐",
        "揣兜里",
        "背铐",
        "了不",
        "溜进",
        "耳后",
        "痒了",
        "很痒",
        "非常痒",
        "挺痒",
        "约拍",
        "盼他",
        "盼她",
        "盼它",
        "怕它",
        "怕他",
        "怕她",
        "铐住",
        "扎进",
        "约调",
        "挨了",
        "一晌",
        "贪欢",
        "一晌贪欢",
        "锁推",
        "掉马",
        "绑完",
        "被铐",
        "后入",
        "女上",
        "前入",
        "丢个",
        "浴巾",
        "余烬",
        "还需",
        "还需要",
        "憋着",
        "憋住",
        "憋了",
        "瘪了",
        "瘪着",
        "抹匀",
        "死盯",
        "猛抽",
        "顶喜欢",
        "顶好",
        "开来",
        "发力",
        "抵向",
        "揉捏",
        "揉着",
        "揉了",
        "探向",
        "探进",
        "探入",
        "两腿",
        "探到",
        "沾了",
        "粘着",
        "向里",
        "往里",
        "白洗",
        "舔干净",
        "伸头",
        "含住",
        "含了",
        "下探",
        "上探",
        "找准",
        "扣在",
        "呛了",
        "呛着",
        "容她",
        "容他",
        "钳着",
        "钳上",
        "握紧",
        "凑到",
        "挨操",
        "挨肏",
        "拖出",
        "拖回",
        "每句",
        "每一句",
        "要用",
        "不要用",
        "加吗",
        "加吧",
        "减吗",
        "减吧",
        "建吗",
        "建吧",
        "夹吗",
        "夹吧",
        "接吗",
        "接吧",
        "截吗",
        "截吧",
        "揭吗",
        "揭吧",
        "加的",
        "加得",
        "减的",
        "减得",
        "建的",
        "建得",
        "夹的",
        "夹得",
        "接的",
        "接得",
        "截的",
        "截得",
        "揭的",
        "揭得",
    }
    stable_tail_exact_tc_terms = {
        "安泰膠",
        "百得膠",
        "白雲膠",
        "不被",
        "不全",
        "不同了",
        "扯下",
        "嘗試一下",
        "持續到",
        "道康寧",
        "道康寧膠",
        "德高膠",
        "鄧白氏",
        "東方雨虹",
        "孤鶩",
        "硅寶膠",
        "行高",
        "行楷",
        "漢高",
        "漢高百得",
        "會被",
        "匯文",
        "回天膠",
        "揭掉",
        "揭去",
        "揭下",
        "截掉",
        "截去",
        "截下",
        "金句",
        "科順",
        "科順防水",
        "馬貝膠",
        "皮革廠",
        "取下",
        "撕下",
        "瓦克",
        "瓦克膠",
        "往上",
        "往右",
        "往左",
        "西卡",
        "西卡膠",
        "霞鶩",
        "霞鶩漫黑",
        "霞鶩文楷",
        "霞鶩文楷等寬",
        "霞鶩晰黑",
        "霞鶩新晰黑",
        "霞鶩新致宋",
        "之江膠",
        "篆體",
        "字間距",
        "字距",
        "字體名",
        "字重",
        "襯線",
        "無襯線",
        "襯線體",
        "無襯線體",
        "等寬",
        "等寬字體",
        "等寬體",
        "非等寬",
        "非等寬字體",
        "中文字體",
        "西文字體",
        "正文字體",
        "標題字體",
        "字體大小",
        "字體列表",
        "字體風格",
        "默認字體",
        "系統字體",
        "自畫",
        "自繪",
        "卓寶",
        "提到過",
        "接受了",
        "無法接受",
        "主力產品",
        "視頻通話",
        "甚至是",
        "編譯運行",
        "花了",
        "靠著",
        "靠了",
        "卡著",
        "卡了",
        "蓋了",
        "覺著",
        "攪著",
        "攪了",
        "嚼著",
        "嚼了",
        "滴著",
        "滴了",
        "沉了",
        "淹著",
        "淹了",
        "截了",
        "揭了",
        "泡著",
        "拖著",
        "拖了",
        "託著",
        "託了",
        "墊著",
        "墊了",
        "壓著",
        "壓了",
        "夾著",
        "夾了",
        "堵著",
        "堵了",
        "裹著",
        "裹了",
        "飄著",
        "飄了",
        "扣著",
        "扣了",
        "蹭著",
        "蹭了",
        "摁著",
        "摁了",
        "閹了",
        "㧟了",
        "㧟著",
        "薅了",
        "薅著",
        "情趣",
        "清癯",
        "睡不著",
        "睡著",
        "搞事",
        "搞事情",
        "抬起來",
        "睡好",
        "站好",
        "坐好",
        "走好",
        "打好",
        "過個",
        "吃得",
        "搭子",
        "雷點",
        "避坑",
        "拔草",
        "住了",
        "是會",
        "堵嘴",
        "在線等",
        "挺急",
        "蠻急",
        "氛圍感",
        "挺胸",
        "戳中",
        "填上",
        "奔著",
        "更文",
        "薅住",
        "揪過來",
        "揪住",
        "揪著",
        "銬起",
        "銬著",
        "窸窸窣窣",
        "腰腿",
        "腿間",
        "趁我",
        "扶牆",
        "蒙頭",
        "丟在",
        "兩折",
        "掄圓",
        "繩縛",
        "硬拽",
        "拽回",
        "拽起",
        "抵在",
        "抵著",
        "趴好",
        "蹲好",
        "躺好",
        "敢弄",
        "敢做",
        "敢當",
        "就往",
        "死裏",
        "拇指銬",
        "揣兜裏",
        "背銬",
        "了不",
        "溜進",
        "耳後",
        "癢了",
        "很癢",
        "非常癢",
        "挺癢",
        "約拍",
        "盼他",
        "盼她",
        "盼它",
        "怕它",
        "怕他",
        "怕她",
        "銬住",
        "扎進",
        "約調",
        "挨了",
        "一晌",
        "貪歡",
        "一晌貪歡",
        "鎖推",
        "掉馬",
        "綁完",
        "被銬",
        "後入",
        "女上",
        "前入",
        "丟個",
        "浴巾",
        "餘燼",
        "還需",
        "還需要",
        "憋著",
        "憋住",
        "憋了",
        "癟了",
        "癟著",
        "抹勻",
        "死盯",
        "猛抽",
        "頂喜歡",
        "頂好",
        "開來",
        "發力",
        "抵向",
        "揉捏",
        "揉著",
        "揉了",
        "探向",
        "探進",
        "探入",
        "兩腿",
        "探到",
        "沾了",
        "粘著",
        "向裏",
        "往裏",
        "白洗",
        "舔乾淨",
        "伸頭",
        "含住",
        "含了",
        "下探",
        "上探",
        "找準",
        "扣在",
        "嗆了",
        "嗆著",
        "容她",
        "容他",
        "鉗著",
        "鉗上",
        "握緊",
        "湊到",
        "挨操",
        "挨肏",
        "拖出",
        "拖回",
        "每句",
        "每一句",
        "要用",
        "不要用",
        "加嗎",
        "加吧",
        "減嗎",
        "減吧",
        "建嗎",
        "建吧",
        "夾嗎",
        "夾吧",
        "接嗎",
        "接吧",
        "截嗎",
        "截吧",
        "揭嗎",
        "揭吧",
        "加的",
        "加得",
        "減的",
        "減得",
        "建的",
        "建得",
        "夾的",
        "夾得",
        "接的",
        "接得",
        "截的",
        "截得",
        "揭的",
        "揭得",
    }

    stats.update(
        _promote_short_exact_homophones_by_pairwise_direct_signal(
            sc_map,
            jieba_direct_signal_map,
            jieba_pos_map,
            curated_daily_sc_terms,
            curated_daily_supplement_sc_terms,
            "sc_final_post",
            bucket_pinyin_map=sc_output_pinyin_bucket_map,
            term_style_penalty_map=cedict_style_penalty_map,
            thuocl_corroborated_signal_map=thuocl_corroborated_signal_map,
        )
    )
    tc_final_terms = {text for _pinyin, text in tc_map.keys()}
    (
        tc_final_jieba_direct_signal_map,
        tc_final_jieba_char_fallback_terms,
    ) = _build_tc_signal_map_with_char_fallback(
        jieba_direct_signal_map,
        tc_to_sc_map,
        trad_to_simp_char_map,
        tc_final_terms,
    )
    (
        tc_final_thuocl_corroborated_signal_map,
        tc_final_thuocl_char_fallback_terms,
    ) = _build_tc_signal_map_with_char_fallback(
        thuocl_corroborated_signal_map,
        tc_to_sc_map,
        trad_to_simp_char_map,
        tc_final_terms,
    )
    stats["tc_final_jieba_char_fallback_terms"] = tc_final_jieba_char_fallback_terms
    stats["tc_final_thuocl_char_fallback_terms"] = tc_final_thuocl_char_fallback_terms
    stats.update(
        _promote_short_exact_homophones_by_pairwise_direct_signal(
            tc_map,
            tc_final_jieba_direct_signal_map,
            tc_jieba_pos_map,
            curated_daily_tc_terms,
            curated_daily_supplement_tc_terms,
            "tc_final_post",
            bucket_pinyin_map=tc_output_pinyin_bucket_map,
            term_style_penalty_map=cedict_style_penalty_map,
            thuocl_corroborated_signal_map=tc_final_thuocl_corroborated_signal_map,
        )
    )

    sc_map, sc_pinyin_alias_stats = _expand_leading_text_pinyin_aliases(
        sc_map,
        "sc_final_post",
    )
    tc_map, tc_pinyin_alias_stats = _expand_leading_text_pinyin_aliases(
        tc_map,
        "tc_final_post",
    )
    stats.update(sc_pinyin_alias_stats)
    stats.update(tc_pinyin_alias_stats)

    stats.update(
        _inject_curated_daily_post_rank_exact_entries(
            sc_map,
            tc_map,
            curated_daily_post_rank_exact_entries,
        )
    )
    post_rank_exact_sc_terms = {
        sc_word
        for sc_word, _tc_word, _usage_score, _explicit_pinyin
        in curated_daily_post_rank_exact_entries
    }
    post_rank_exact_tc_terms = {
        tc_word or sc_word
        for sc_word, tc_word, _usage_score, _explicit_pinyin
        in curated_daily_post_rank_exact_entries
    }
    low_priority_supplement_sc_terms.update(post_rank_exact_sc_terms)
    low_priority_supplement_tc_terms.update(post_rank_exact_tc_terms)
    curated_daily_explicit_pinyin_keys.update(
        _build_curated_daily_explicit_pinyin_key_set(
            curated_daily_post_rank_exact_entries
        )
    )

    stats.update(
        _restore_common_polyphonic_reading_visibility(
            mapping=sc_map,
            competing_single_char_map=support_single_char_sc_map,
            unihan_readings_map=unihan_readings_map,
            unihan_mandarin_map=unihan_map,
            unihan_pinlu_detail_map=unihan_pinlu_detail_map,
            phrase_term_count_map=sc_reading_term_count_map,
            phrase_support_sum_map=sc_reading_support_sum_map,
            visibility_phrase_term_count_map=sc_visibility_reading_term_count_map,
            visibility_phrase_support_sum_map=sc_visibility_reading_support_sum_map,
            inferred_phrase_term_count_map=sc_inferred_reading_term_count_map,
            inferred_phrase_support_sum_map=sc_inferred_reading_support_sum_map,
            visibility_inferred_phrase_term_count_map=sc_visibility_inferred_reading_term_count_map,
            visibility_inferred_phrase_support_sum_map=sc_visibility_inferred_reading_support_sum_map,
            family_term_count_map=sc_family_term_count_map,
            visibility_family_term_count_map=sc_visibility_family_term_count_map,
            single_char_frequency_map=single_char_frequency_map,
            single_char_pos_map=single_char_pos_map,
            explicit_pinyin_overrides=word_pinyin_overrides,
            stats_prefix="sc_final_post",
        )
    )
    stats.update(
        _restore_common_polyphonic_reading_visibility(
            mapping=tc_map,
            competing_single_char_map=support_single_char_tc_map,
            unihan_readings_map=unihan_readings_map,
            unihan_mandarin_map=unihan_map,
            unihan_pinlu_detail_map=unihan_pinlu_detail_map,
            phrase_term_count_map=tc_reading_term_count_map,
            phrase_support_sum_map=tc_reading_support_sum_map,
            visibility_phrase_term_count_map=tc_visibility_reading_term_count_map,
            visibility_phrase_support_sum_map=tc_visibility_reading_support_sum_map,
            inferred_phrase_term_count_map=tc_inferred_reading_term_count_map,
            inferred_phrase_support_sum_map=tc_inferred_reading_support_sum_map,
            visibility_inferred_phrase_term_count_map=tc_visibility_inferred_reading_term_count_map,
            visibility_inferred_phrase_support_sum_map=tc_visibility_inferred_reading_support_sum_map,
            family_term_count_map=tc_family_term_count_map,
            visibility_family_term_count_map=tc_visibility_family_term_count_map,
            single_char_frequency_map=tc_single_char_frequency_map,
            single_char_pos_map=tc_single_char_pos_map,
            explicit_pinyin_overrides=word_pinyin_overrides,
            stats_prefix="tc_final_post",
        )
    )

    if parser_name == "unihan_only" and not args.refresh_unihan_single_char_weights:
        stats.update(
            _preserve_existing_unihan_single_char_weights(
                sc_map,
                previous_snapshot_sc,
                "sc_unihan_stability",
            )
        )
        stats.update(
            _preserve_existing_unihan_single_char_weights(
                tc_map,
                previous_snapshot_tc,
                "tc_unihan_stability",
            )
        )

    # Stability preservation deliberately restores prior weights. Apply the
    # small audited relative-order rules last so they remain effective in the
    # normal non-refresh build as well as a full Unihan refresh.
    stats.update(
        _enforce_single_char_relative_order_overrides(
            sc_map,
            "sc_final_post",
        )
    )
    stats.update(
        _enforce_single_char_relative_order_overrides(
            tc_map,
            "tc_final_post",
        )
    )

    _write_dict(
        output_sc,
        sc_map,
        preferred_terms=curated_daily_sc_terms,
        low_priority_output_terms=low_priority_supplement_sc_terms,
        post_low_priority_output_terms=stable_tail_exact_sc_terms,
        preserve_pinyin_keys=curated_daily_explicit_pinyin_keys,
        unihan_map=output_unihan_map,
        unihan_readings_map=output_unihan_readings_map,
        unihan_source_rank_map=output_unihan_source_rank_map,
        unihan_pinlu_detail_map=output_unihan_pinlu_detail_map,
        contains_popularity_excluded_terms=contains_popularity_excluded_sc_terms,
    )
    _write_dict(
        output_tc,
        tc_map,
        preferred_terms=curated_daily_tc_terms,
        low_priority_output_terms=low_priority_supplement_tc_terms,
        post_low_priority_output_terms=stable_tail_exact_tc_terms,
        preserve_pinyin_keys=curated_daily_explicit_pinyin_keys,
        unihan_map=output_unihan_map,
        unihan_readings_map=output_unihan_readings_map,
        unihan_source_rank_map=output_unihan_source_rank_map,
        unihan_pinlu_detail_map=output_unihan_pinlu_detail_map,
        contains_popularity_excluded_terms=contains_popularity_excluded_tc_terms,
    )
    if output_transition_completion_sc is not None:
        sc_transition_completion_index, completion_stats = (
            _filter_transition_completion_against_written_dictionary(
                sc_transition_completion_index,
                output_sc,
                single_char_readings_map=output_unihan_readings_map,
                stats_prefix="sc",
            )
        )
        stats.update(completion_stats)
    if output_transition_completion_tc is not None:
        tc_transition_completion_index, completion_stats = (
            _filter_transition_completion_against_written_dictionary(
                tc_transition_completion_index,
                output_tc,
                single_char_readings_map=output_unihan_readings_map,
                stats_prefix="tc",
            )
        )
        stats.update(completion_stats)
    if (
        output_completion_prior_sc is not None
        or output_completion_prior_tc is not None
        or output_completion_lookup_sc is not None
        or output_completion_lookup_tc is not None
    ):
        opencc_sc_to_tc_for_completion = (
            _build_opencc_sc_to_tc_map(opencc_entries) if opencc_entries else {}
        )
        completion_sc_layers, completion_tc_layers = (
            _build_completion_vertical_layer_maps(
                vertical_entries,
                convert_sc_to_tc=lambda text: _convert_sc_text_to_tc_with_phrase_hints(
                    text,
                    opencc_sc_to_tc_for_completion,
                    simp_to_trad_char_map,
                ),
            )
        )
        completion_sc_path_scores = _build_completion_path_score_map(
            baseline_lm_transition_sc, sc_lm_transition_priors
        )
        completion_tc_path_scores = _build_completion_path_score_map(
            baseline_lm_transition_tc, tc_lm_transition_priors
        )
        if output_completion_prior_sc is not None or output_completion_lookup_sc is not None:
            sc_completion_prior, completion_prior_stats = (
                _build_completion_popularity_prior(
                    output_sc,
                    usage_score_map=usage_score_map,
                    corpus_frequency_map=jieba_direct_signal_map,
                    document_frequency_map=thuocl_signal_map,
                    persistence_map=pageviews_persistence_signal_map,
                    source_hits_map=source_hits_map,
                    vertical_layer_map=completion_sc_layers,
                    curated_hot_terms=curated_daily_sc_terms,
                    curated_low_terms=curated_daily_supplement_sc_terms,
                    path_score_map=completion_sc_path_scores,
                    stats_prefix="sc",
                )
            )
            if output_completion_prior_sc is not None:
                _write_completion_popularity_prior(
                    output_completion_prior_sc, sc_completion_prior
                )
            stats.update(completion_prior_stats)
            if output_completion_lookup_sc is not None:
                sc_completion_lookup, completion_lookup_stats = (
                    _build_completion_exact_lookup(
                        output_sc,
                        sc_completion_prior,
                        stats_prefix="sc",
                    )
                )
                _write_completion_exact_lookup(
                    output_completion_lookup_sc, sc_completion_lookup
                )
                stats.update(completion_lookup_stats)
        if output_completion_prior_tc is not None or output_completion_lookup_tc is not None:
            tc_completion_prior, completion_prior_stats = (
                _build_completion_popularity_prior(
                    output_tc,
                    usage_score_map=tc_usage_score_map,
                    corpus_frequency_map=tc_jieba_direct_signal_map,
                    document_frequency_map=tc_thuocl_signal_map,
                    persistence_map=tc_pageviews_persistence_signal_map,
                    source_hits_map=tc_source_hits_map,
                    vertical_layer_map=completion_tc_layers,
                    curated_hot_terms=curated_daily_tc_terms,
                    curated_low_terms=curated_daily_supplement_tc_terms,
                    path_score_map=completion_tc_path_scores,
                    stats_prefix="tc",
                )
            )
            if output_completion_prior_tc is not None:
                _write_completion_popularity_prior(
                    output_completion_prior_tc, tc_completion_prior
                )
            stats.update(completion_prior_stats)
            if output_completion_lookup_tc is not None:
                tc_completion_lookup, completion_lookup_stats = (
                    _build_completion_exact_lookup(
                        output_tc,
                        tc_completion_prior,
                        stats_prefix="tc",
                    )
                )
                _write_completion_exact_lookup(
                    output_completion_lookup_tc, tc_completion_lookup
                )
                stats.update(completion_lookup_stats)
    if output_query_path_sc is not None:
        _write_query_path_prior(output_query_path_sc, sc_query_path_priors)
    if output_query_path_tc is not None:
        _write_query_path_prior(output_query_path_tc, tc_query_path_priors)
    if output_lm_transition_sc is not None:
        _write_query_path_prior(output_lm_transition_sc, sc_lm_transition_priors)
    if output_lm_transition_tc is not None:
        _write_query_path_prior(output_lm_transition_tc, tc_lm_transition_priors)
    if output_transition_completion_sc is not None:
        _write_transition_completion(
            output_transition_completion_sc,
            sc_transition_completion_index,
        )
    if output_transition_completion_tc is not None:
        _write_transition_completion(
            output_transition_completion_tc,
            tc_transition_completion_index,
        )
    manifest_sources = list(sources)
    manifest_source_ids = {str(source.get("id", "")).strip() for source in manifest_sources}
    for vertical_source in vertical_source_configs:
        source_id = str(vertical_source.get("id", "")).strip()
        if source_id and source_id not in manifest_source_ids:
            manifest_sources.append(vertical_source)
            manifest_source_ids.add(source_id)

    _write_manifest(manifest, args.profile, manifest_sources)
    _write_report(
        report,
        args.profile,
        manifest_sources,
        output_sc,
        output_tc,
        output_query_path_sc,
        output_query_path_tc,
        output_lm_transition_sc,
        output_lm_transition_tc,
        output_transition_completion_sc,
        output_transition_completion_tc,
        stats,
        len(sc_map),
        len(tc_map),
        args.min_hanzi,
        args.max_entries,
        suspicious_sc_entries,
    )

    print(f"Build completed: profile={args.profile} sc={len(sc_map)} tc={len(tc_map)}")
    print(f"Manifest updated: {manifest}")
    print(f"Report written: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

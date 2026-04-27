#!/usr/bin/env python3
"""
Build public lexicon seed files from external sources.

Output format:
  pinyin<TAB>text<TAB>weight
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
import sys
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from typing import Dict, List, Set, Tuple


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
DAILY_CHAT_SEED_CHARS = set("的得地就也还才又都把被给跟让像向对从为在这那哪怎啥谁您你我他她它咱吗呢吧呀啊嘛哦呗啦了着过说看来去")
STRONG_TWO_CHAR_DAILY_HEAD_CHARS = set(
    "\u4e0d\u6ca1\u522b\u8fd9\u90a3\u54ea\u600e\u5565\u8c01\u60a8\u4f60\u6211\u4ed6\u5979\u5b83\u54b1"
    "\u6709\u65e0\u53ef\u80fd\u4f1a\u8981\u60f3\u8be5\u771f\u633a\u592a\u597d\u5148\u518d\u8fd8\u4e5f"
    "\u5c31\u624d\u53c8\u90fd\u8001\u603b"
)
STRONG_TWO_CHAR_DAILY_TAIL_CHARS = set(
    "\u5417\u5462\u5427\u5440\u554a\u561b\u54e6\u5457\u5566\u4e86\u7740\u8fc7"
    "\u662f\u7684\u5f97\u6765\u53bb\u770b\u8bf4\u505a\u641e\u5f04\u95ee\u67e5\u542c\u8bd5\u6539"
    "\u7ed9\u8981\u4f1a\u80fd\u884c\u597d\u5bf9\u9519\u5fd9\u7d2f\u723d\u75bc\u75db"
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
CURATED_DAILY_NUMBER_WEIGHT_CAP = 940
# Fiction entities are supplemental names and should not inherit everyday-word
# priors. Product/platform proper nouns are handled by the generic vertical path
# because they are frequently normal daily input terms.
NAMED_ENTITY_VERTICAL_LAYERS = {"fiction_entities"}

CEDICT_LINE_RE = re.compile(r"^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.*)/$")
CJK_RE = re.compile("[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002A6DF]")
CJK_FULL_RE = re.compile(
    "^[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002A6DF]+$"
)
CJK_WINDOWS_FULL_RE = re.compile("^[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+$")
PINYIN_RE = re.compile(r"^[a-z]+$")
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
}

MULTI_CHAR_TERM_DROP_OVERRIDES: Set[str] = {
    # Legacy orthography no longer preferred in modern IME usage.
    "补钉",
    "補釘",
}

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


def _normalize_compact_pinyin_key(raw: str) -> str:
    value = raw.strip().lower()
    value = value.replace("’", "'").replace("'", "")
    value = re.sub(r"\s+", "", value)
    return value


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
    overrides: Dict[str, str] = {}
    for sc_word, tc_word, _usage_score, explicit_pinyin in entries:
        if not explicit_pinyin:
            continue
        if sc_word and sc_word not in overrides:
            overrides[sc_word] = explicit_pinyin
        if tc_word and tc_word not in overrides:
            overrides[tc_word] = explicit_pinyin
    return overrides


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


def _vertical_ranking_usage_score(
    text: str,
    layer_id: str,
    usage_score: float,
    *,
    supported_named_entity: bool = False,
) -> float:
    if _is_named_entity_vertical_layer(layer_id) and not supported_named_entity:
        return _cap_named_entity_vertical_usage_score(usage_score, _cjk_len(text))
    if layer_id == "idioms_allusions":
        bounded = min(1.0, max(0.0, usage_score))
        text_len = _cjk_len(text)
        if text_len <= 3:
            return min(bounded, 0.50)
        if text_len == 4:
            return min(bounded, 0.72)
        if text_len <= 6:
            return min(bounded, 0.64)
        return min(bounded, 0.58)
    return min(1.0, max(0.0, usage_score))


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
    return _apply_explicit_term_pinyin_overrides(mapping, overrides, stat_prefix)


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
            if length <= 4 and (bounded_usage >= 0.05 or jieba_direct_score >= 0.08):
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
    if not text:
        return False
    if any(ch not in DAILY_NUMBER_WORD_CHARS for ch in text):
        return False
    if not any(ch in DAILY_NUMBER_WORD_UNIT_CHARS for ch in text):
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
    if text in preferred_terms:
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

        best_support, best_pinyin, _best_weight = supports[0]
        second_support = supports[1][0]
        if best_support < 520.0:
            continue
        if best_support < second_support * 1.35:
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

        aligned_items: List[Tuple[str, int, int]] = []
        best_sc_weight = 0
        best_tc_weight = 0
        for tc_text, tc_weight in tc_items:
            candidate_sc_texts: Set[str] = set()
            if tc_text in sc_bucket:
                candidate_sc_texts.add(tc_text)
            candidate_sc_texts.update(tc_to_sc_map.get(tc_text, set()))

            sc_weight = 0
            for sc_text in candidate_sc_texts:
                sc_weight = max(sc_weight, sc_bucket.get(sc_text, 0))
            if sc_weight <= 0:
                continue

            aligned_items.append((tc_text, tc_weight, sc_weight))
            best_sc_weight = max(best_sc_weight, sc_weight)
            best_tc_weight = max(best_tc_weight, tc_weight)

        if len(aligned_items) < 2 or best_sc_weight <= 0 or best_tc_weight <= 0:
            continue

        stats[f"{stats_prefix}_homophone_sc_guided_buckets"] += 1
        for tc_text, tc_weight, sc_weight in aligned_items:
            sc_ratio = min(1.0, max(0.0, float(sc_weight) / float(best_sc_weight)))
            target_weight = max(1, int(round(best_tc_weight * sc_ratio)))
            gap = target_weight - tc_weight
            key = (pinyin, tc_text)

            if gap >= 56:
                if sc_ratio >= 0.99:
                    boost_factor = 0.68
                elif sc_ratio >= 0.95:
                    boost_factor = 0.55
                else:
                    boost_factor = 0.42
                boost = min(220, max(24, int(round(gap * boost_factor))))
                new_weight = tc_weight + boost
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
    preferred_terms: Set[str] | None,
    stats_prefix: str,
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
        f"{stats_prefix}_homophone_short_everyday_boosted": 0,
        f"{stats_prefix}_homophone_short_everyday_non_daily_damped": 0,
        f"{stats_prefix}_homophone_short_popular_wiki_boosted": 0,
        f"{stats_prefix}_homophone_short_popular_named_bucket_damped": 0,
        f"{stats_prefix}_homophone_daily_phrase_short_non_daily_damped": 0,
        f"{stats_prefix}_homophone_preferred_term_boosted": 0,
        f"{stats_prefix}_homophone_preferred_term_damped": 0,
        f"{stats_prefix}_homophone_short_family_noun_damped": 0,
    }
    if not mapping:
        return stats
    has_robust_usage = bool(
        usage_score_map or source_hits_map or pageviews_signal_map or wiki_titles
    )

    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    term_style_penalty_map = term_style_penalty_map or {}
    preferred_terms = preferred_terms or set()
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
        bucket_has_short_popular_named_term = False
        bucket_dominant_common_text = ""
        bucket_dominant_common_signal = -1.0
        bucket_dominant_common_runner_up = -1.0
        strong_short_head_terms: Set[str] = set()
        for text, _weight in items:
            text_len = _cjk_len(text)
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
            if _is_daily_phrase_candidate(
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
            if text in preferred_terms:
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
        for text, weight in items:
            text_len = _cjk_len(text)
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
            daily_number_support = _is_daily_number_word_candidate(
                text,
                text_len=text_len,
                usage_score=usage_score,
                source_hits=source_hits,
                pos_tag=pos_tag,
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
            min_char_prior = _compute_min_char_prior(text, char_prior)
            if text_len <= 2:
                char_weight = 220.0
            elif text_len <= 4:
                char_weight = 72.0
            else:
                char_weight = 28.0
            if text_len <= 2 and _is_conversational_pos(pos_tag):
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
                )
                if text_len <= 2:
                    common_signal += char_score * 60.0
                    if _is_conversational_pos(pos_tag):
                        common_signal += 68.0
                        if text and text[0] in ("不", "没", "无", "非", "未"):
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

            if bucket_has_preferred_term:
                if text in preferred_terms:
                    delta += 24 if text_len <= 2 else 14
                    stats[f"{stats_prefix}_homophone_preferred_term_boosted"] += 1
                elif text_len <= 3:
                    # Curated daily terms are an explicit product preference.
                    # In the same homophone bucket, short non-curated terms
                    # should yield unless they are also manually promoted.
                    delta -= 96 if text_len <= 2 else 44
                    stats[f"{stats_prefix}_homophone_preferred_term_damped"] += 1

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

            if delta == 0:
                continue

            new_weight = max(1, min(1000, weight + delta))
            if new_weight == weight:
                continue

            mapping[(pinyin, text)] = new_weight
            stats[f"{stats_prefix}_homophone_entries_adjusted"] += 1
            if new_weight > weight:
                stats[f"{stats_prefix}_homophone_entries_boosted"] += 1
            else:
                stats[f"{stats_prefix}_homophone_entries_damped"] += 1

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
    plain_senses = 0

    for sense in senses:
        is_dialect = "dialect" in sense
        is_literary = (
            ("literary" in sense)
            or ("classical" in sense)
            or ("archaic" in sense)
        )
        if is_dialect:
            dialect_senses += 1
        if is_literary:
            literary_senses += 1
        if (not is_dialect) and (not is_literary):
            plain_senses += 1

    total_senses = max(1, len(senses))
    dialect_ratio = dialect_senses / total_senses
    literary_ratio = literary_senses / total_senses

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
        "place name",
    )

    for sense in senses:
        if sense.startswith(("variant of ", "old variant of ", "see also ")):
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
]:
    sc: Dict[Tuple[str, str], int] = {}
    tc: Dict[Tuple[str, str], int] = {}
    term_style_penalty_map: Dict[Tuple[str, str], int] = {}
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
            if style_penalty > term_style_penalty_map.get(key, 0):
                term_style_penalty_map[key] = style_penalty

    return sc, tc, stats, term_style_penalty_map


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
) -> Tuple[List[Tuple[str, str, float, str]], Dict[str, int]]:
    stats = {
        "curated_daily_phrase_rows": 0,
        "curated_daily_phrase_kept": 0,
        "curated_daily_phrase_skipped_short": 0,
        "curated_daily_phrase_skipped_non_cjk": 0,
        "curated_daily_phrase_skipped_malformed": 0,
    }
    entries: List[Tuple[str, str, float, str]] = []
    text = _decode_text(payload)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        stats["curated_daily_phrase_rows"] += 1
        parts = line.split("\t")
        if len(parts) < 2:
            stats["curated_daily_phrase_skipped_malformed"] += 1
            continue
        sc_word = parts[0].strip()
        tc_word = parts[1].strip()
        try:
            usage_score = float(parts[2].strip()) if len(parts) >= 3 and parts[2].strip() else 0.82
        except ValueError:
            usage_score = 0.82
        if (not sc_word) or (not CJK_FULL_RE.fullmatch(sc_word)):
            stats["curated_daily_phrase_skipped_non_cjk"] += 1
            continue
        if _cjk_len(sc_word) < min_hanzi:
            stats["curated_daily_phrase_skipped_short"] += 1
            continue
        if not tc_word:
            tc_word = sc_word
        explicit_pinyin = parts[3].strip().lower() if len(parts) >= 4 else ""
        if explicit_pinyin and not PINYIN_RE.fullmatch(explicit_pinyin):
            explicit_pinyin = ""
        entries.append(
            (
                sc_word,
                tc_word,
                min(1.0, max(0.0, usage_score)),
                explicit_pinyin,
            )
        )
        stats["curated_daily_phrase_kept"] += 1
    return entries, stats


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
            _normalize_pinyin(parts[3].strip())
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

    # Keep pragmatic override from historical Unihan import behavior.
    _add_unihan_reading(
        readings_map,
        source_rank_map,
        "嗯",
        "en",
        UNIHAN_SOURCE_PINLU,
    )
    if "嗯" not in mandarin_map:
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
            if len(parts) != 3:
                continue

            text = parts[1].strip()
            if _cjk_len(text) < 2 or not CJK_FULL_RE.fullmatch(text):
                continue
            if exclude_texts and text in exclude_texts:
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
            if len(parts) != 3:
                continue

            pinyin = parts[0].strip()
            text = parts[1].strip()
            if _cjk_len(text) < 2 or not CJK_FULL_RE.fullmatch(text):
                continue
            if exclude_texts and text in exclude_texts:
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
            if len(parts) != 3:
                continue

            pinyin = parts[0].strip()
            text = parts[1].strip()
            if _cjk_len(text) < 2 or not CJK_FULL_RE.fullmatch(text):
                continue
            if exclude_texts and text in exclude_texts:
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

        pinyin = _normalize_pinyin(parts[1])
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
        tc, normalize_stats = _normalize_tc_mapping_with_char_map(tc, simp_to_trad_char_map)
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


def _apply_explicit_script_pair(
    trad_ch: str,
    simp_ch: str,
    trad_to_simp_char_map: Dict[str, str],
    simp_to_trad_char_map: Dict[str, str],
    sc_chars: Set[str],
    tc_chars: Set[str],
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
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    if not simp_to_trad_char_map:
        return mapping, {
            "tc_char_normalized_converted_entries": 0,
            "tc_char_normalized_total_entries": len(mapping),
        }

    normalized: Dict[Tuple[str, str], int] = {}
    converted_entries = 0

    for (pinyin, text), weight in mapping.items():
        converted_chars: List[str] = []
        changed = False
        for ch in text:
            replacement = simp_to_trad_char_map.get(ch, ch)
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
    }
    jieba_direct_signal_map = jieba_direct_signal_map or {}
    jieba_pos_map = jieba_pos_map or {}
    term_style_penalty_map = term_style_penalty_map or {}
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

            delta = 0
            if (
                reading_pinlu >= 3000
                and leading_support >= 1200.0
                and leading_ratio >= 0.70
            ):
                delta += 120
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
) -> int:
    if not is_number_word:
        daily_floor = 1080 + int(round(max(0.0, min(1.0, usage_score)) * 180.0))
        return max(weight, daily_floor)

    # Number words are useful daily entries, but should not be as dominant as
    # conversational words/phrases. Keep them strong enough to surface while
    # leaving room for non-numeric homophones and user learning.
    number_cap = CURATED_DAILY_NUMBER_WEIGHT_CAP
    number_floor = min(
        number_cap,
        840 + int(round(max(0.0, min(1.0, usage_score)) * 110.0)),
    )
    return min(number_cap, max(weight, number_floor))


def _is_pure_daily_number_word(text: str) -> bool:
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
        if _is_pure_daily_number_word(text):
            number_terms.add(text)

    stats[f"{stats_prefix}_curated_daily_number_cap_terms"] = len(number_terms)
    if not number_terms:
        return stats

    for key, weight in list(mapping.items()):
        _pinyin, text = key
        if text not in number_terms or weight <= CURATED_DAILY_NUMBER_WEIGHT_CAP:
            continue
        mapping[key] = CURATED_DAILY_NUMBER_WEIGHT_CAP
        stats[f"{stats_prefix}_curated_daily_number_cap_rows"] += 1

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
            return min(1120, 900 + int(round(usage * 220.0)))
        if prefix_len == 3:
            return min(1080, 840 + int(round(usage * 200.0)))
        return min(1040, 800 + int(round(usage * 180.0)))

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
            existing_weight = mapping.get(key)
            if existing_weight is None:
                continue

            stats[f"{stats_prefix}_curated_daily_prefix_terms_considered"] += 1
            inherited_usage = max(
                min(1.0, max(0.0, usage_score_map.get(prefix, 0.0))),
                min(0.86, max(0.28, min(1.0, max(0.0, usage_score)) - 0.06)),
            )
            floor_weight = prefix_floor(prefix_len, inherited_usage)
            if existing_weight < floor_weight:
                mapping[key] = floor_weight
                stats[f"{stats_prefix}_curated_daily_prefix_reinforced"] += 1

            usage_score_map[prefix] = max(usage_score_map.get(prefix, 0.0), inherited_usage)
            source_hits_map[prefix] = max(source_hits_map.get(prefix, 0), 2)

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

    existing_texts = {text for _pinyin, text in mapping.keys()}
    char_prior = _build_effective_char_prior(mapping, char_frequency_prior)

    def prefix_floor(prefix_len: int, inherited_usage: float) -> int:
        usage = min(1.0, max(0.0, inherited_usage))
        if prefix_len <= 2:
            return min(1120, 900 + int(round(usage * 220.0)))
        if prefix_len == 3:
            return min(1080, 840 + int(round(usage * 200.0)))
        return min(1040, 800 + int(round(usage * 180.0)))

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

            inherited_usage = max(
                min(1.0, max(0.0, usage_score_map.get(prefix, 0.0))),
                min(0.86, max(0.28, min(1.0, max(0.0, usage_score)) - 0.06)),
            )
            if prefix_weight < prefix_floor(prefix_len, inherited_usage) - 8:
                continue

            competitor_cap = max(1, min(prefix_weight - 420, 760))
            if competitor_cap <= 0:
                continue

            for competitor_text, competitor_weight in by_pinyin.get(prefix_pinyin, []):
                if competitor_text == prefix:
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
) -> Tuple[Dict[str, int], Set[str], Set[str]]:
    stats = {
        "curated_daily_terms_total": 0,
        "curated_daily_terms_added_sc": 0,
        "curated_daily_terms_boosted_sc": 0,
        "curated_daily_terms_added_tc": 0,
        "curated_daily_terms_boosted_tc": 0,
        "curated_daily_number_terms_boosted_sc": 0,
        "curated_daily_number_terms_boosted_tc": 0,
        "curated_daily_terms_skipped_short": 0,
        "curated_daily_terms_skipped_no_pinyin": 0,
    }
    sc_terms: Set[str] = set()
    tc_terms: Set[str] = set()
    opencc_sc_to_tc = _build_opencc_sc_to_tc_map(opencc_entries)
    tc_existing_texts = {text for _pinyin, text in tc.keys()}
    sc_char_prior = _build_effective_char_prior(sc, char_frequency_prior)
    tc_char_prior = _build_effective_char_prior(tc, tc_char_frequency_prior)

    for sc_word, tc_word, usage_score, explicit_pinyin in curated_entries:
        stats["curated_daily_terms_total"] += 1
        if _cjk_len(sc_word) < min_hanzi:
            stats["curated_daily_terms_skipped_short"] += 1
            continue

        pinyin = explicit_pinyin or _pinyin_from_unihan(
            sc_word,
            unihan_map,
            unihan_readings_map,
            unihan_source_rank_map,
            unihan_pinlu_detail_map,
        )
        if not pinyin:
            stats["curated_daily_terms_skipped_no_pinyin"] += 1
            continue

        source_hits = 4
        usage_score_map[sc_word] = max(usage_score_map.get(sc_word, 0.0), usage_score)
        source_hits_map[sc_word] = max(source_hits_map.get(sc_word, 0), source_hits)

        sc_jieba_direct = max(
            jieba_direct_signal_map.get(sc_word, 0.0),
            min(0.26, usage_score * 0.32),
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
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=0.0,
            wiki_hit=True,
            core_entry=False,
            jieba_direct_score=sc_jieba_direct,
            pos_tag=sc_pos_tag,
            char_score=sc_char_score,
        )
        if sc_daily_number_support:
            sc_weight = min(1000, sc_weight + (40 if _cjk_len(sc_word) <= 2 else 26))
            stats["curated_daily_number_terms_boosted_sc"] += 1
        sc_weight = _finalize_curated_daily_weight(
            sc_weight,
            usage_score=usage_score,
            is_number_word=sc_daily_number_support,
        )
        sc_key = (pinyin, sc_word)
        existing_sc_weight = sc.get(sc_key)
        if existing_sc_weight is None:
            sc[sc_key] = sc_weight
            stats["curated_daily_terms_added_sc"] += 1
            sc_terms.add(sc_word)
        elif sc_weight > existing_sc_weight:
            sc[sc_key] = sc_weight
            stats["curated_daily_terms_boosted_sc"] += 1
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

        tc_usage_score_map[tc_candidate] = max(tc_usage_score_map.get(tc_candidate, 0.0), usage_score)
        tc_source_hits_map[tc_candidate] = max(tc_source_hits_map.get(tc_candidate, 0), source_hits)

        tc_jieba_direct = max(
            tc_jieba_direct_signal_map.get(tc_candidate, 0.0),
            min(0.26, usage_score * 0.32),
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
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=0.0,
            wiki_hit=True,
            core_entry=False,
            jieba_direct_score=tc_jieba_direct,
            pos_tag=tc_pos_tag,
            char_score=tc_char_score,
        )
        if tc_daily_number_support:
            tc_weight = min(1000, tc_weight + (40 if _cjk_len(tc_candidate) <= 2 else 26))
            stats["curated_daily_number_terms_boosted_tc"] += 1
        tc_weight = _finalize_curated_daily_weight(
            tc_weight,
            usage_score=usage_score,
            is_number_word=tc_daily_number_support,
        )
        tc_key = (pinyin, tc_candidate)
        existing_tc_weight = tc.get(tc_key)
        if existing_tc_weight is None:
            tc[tc_key] = tc_weight
            stats["curated_daily_terms_added_tc"] += 1
            tc_terms.add(tc_candidate)
        elif tc_weight > existing_tc_weight:
            tc[tc_key] = tc_weight
            stats["curated_daily_terms_boosted_tc"] += 1
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
) -> Dict[str, int]:
    stats = {
        "curated_daily_exact_tc_reinforced": 0,
        "curated_daily_exact_tc_added": 0,
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

        source_hits = max(4, tc_source_hits_map.get(tc_candidate, 0))
        usage_score = max(usage_score, tc_usage_score_map.get(tc_candidate, 0.0))
        tc_jieba_direct = max(
            tc_jieba_direct_signal_map.get(tc_candidate, 0.0),
            min(0.26, usage_score * 0.32),
        )
        tc_pos_tag = tc_jieba_pos_map.get(tc_candidate, "")
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
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=0.0,
            wiki_hit=True,
            core_entry=False,
            jieba_direct_score=tc_jieba_direct,
            pos_tag=tc_pos_tag,
            char_score=tc_char_score,
        )
        if tc_daily_number_support:
            tc_weight = min(1000, tc_weight + (40 if _cjk_len(tc_candidate) <= 2 else 26))
        tc_weight = _finalize_curated_daily_weight(
            tc_weight,
            usage_score=usage_score,
            is_number_word=tc_daily_number_support,
        )

        tc_key = (pinyin, tc_candidate)
        existing_tc_weight = tc.get(tc_key)
        if existing_tc_weight is None:
            tc[tc_key] = tc_weight
            stats["curated_daily_exact_tc_added"] += 1
        elif tc_weight > existing_tc_weight:
            tc[tc_key] = tc_weight
            stats["curated_daily_exact_tc_reinforced"] += 1

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
) -> Dict[str, int]:
    stats = {
        "curated_daily_exact_sc_reinforced": 0,
        "curated_daily_exact_sc_added": 0,
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

        source_hits = max(4, source_hits_map.get(sc_word, 0))
        usage_score = max(usage_score, usage_score_map.get(sc_word, 0.0))
        sc_jieba_direct = max(
            jieba_direct_signal_map.get(sc_word, 0.0),
            min(0.26, usage_score * 0.32),
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
            usage_score=usage_score,
            source_hits=source_hits,
            pageview_score=0.0,
            wiki_hit=True,
            core_entry=False,
            jieba_direct_score=sc_jieba_direct,
            pos_tag=sc_pos_tag,
            char_score=sc_char_score,
        )
        if sc_daily_number_support:
            sc_weight = min(1000, sc_weight + (40 if _cjk_len(sc_word) <= 2 else 26))
        sc_weight = _finalize_curated_daily_weight(
            sc_weight,
            usage_score=usage_score,
            is_number_word=sc_daily_number_support,
        )

        sc_key = (pinyin, sc_word)
        existing_sc_weight = sc.get(sc_key)
        if existing_sc_weight is None:
            sc[sc_key] = sc_weight
            stats["curated_daily_exact_sc_added"] += 1
        elif sc_weight > existing_sc_weight:
            sc[sc_key] = sc_weight
            stats["curated_daily_exact_sc_reinforced"] += 1

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
        elif not supported_named_entity:
            penalty = _compute_generic_vertical_penalty(tc_candidate, layer_id, source_id)
            if penalty > 0:
                tc_weight = max(1, tc_weight - penalty)

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
            min(0.34, max(parent_usage * 0.82, 0.18)),
        )
        sc_source_hits = max(
            source_hits_map.get(sc_alias, 0),
            max(2, min(parent_source_hits, 4)),
        )
        sc_pageview = max(
            pageviews_signal_map.get(sc_alias, 0.0),
            min(parent_pageview, 0.24),
        )
        sc_jieba_direct = max(
            jieba_direct_signal_map.get(sc_alias, 0.0),
            min(0.12, max(parent_jieba_direct * 0.50, sc_usage * 0.22)),
        )
        sc_pos_tag = jieba_pos_map.get(sc_parent, "ns") or "ns"
        sc_char_score = _compute_text_single_char_prior(sc_alias, sc_char_prior)
        sc_weight = _compute_weight_with_signals(
            sc_alias,
            usage_score=sc_usage,
            source_hits=sc_source_hits,
            pageview_score=sc_pageview,
            wiki_hit=True,
            core_entry=False,
            jieba_direct_score=sc_jieba_direct,
            pos_tag=sc_pos_tag,
            char_score=sc_char_score,
        )
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
                wiki_hit=True,
                core_entry=False,
                jieba_direct_score=tc_jieba_direct,
                pos_tag=tc_pos_tag,
                char_score=tc_char_score,
            )
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
        "vertical_medicine_penalized_tc": 0,
        "vertical_medicine_penalty_tc_total": 0,
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
        elif not sc_supported_named_entity:
            penalty = _compute_generic_vertical_penalty(sc_word, layer_id, source_id)
            if penalty > 0:
                sc_weight = max(1, sc_weight - penalty)
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
        elif not tc_supported_named_entity:
            penalty = _compute_generic_vertical_penalty(tc_candidate, layer_id, source_id)
            if penalty > 0:
                tc_weight = max(1, tc_weight - penalty)
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
        if len(text) > 1 and text in drop_terms:
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
    unihan_map: Dict[str, str] | None = None,
    unihan_readings_map: Dict[str, Set[str]] | None = None,
    unihan_source_rank_map: Dict[Tuple[str, str], int] | None = None,
    unihan_pinlu_detail_map: Dict[Tuple[str, str], int] | None = None,
) -> None:
    preferred_terms = preferred_terms or set()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for (pinyin, text), weight in sorted(
            mapping.items(),
            key=lambda kv: (
                kv[0][0],
                -kv[1],
                0 if kv[0][1] in preferred_terms else 1,
                kv[0][1],
            ),
        ):
            output_pinyin = _canonicalize_output_pinyin(
                pinyin,
                text,
                unihan_map,
                unihan_readings_map,
                unihan_source_rank_map,
                unihan_pinlu_detail_map,
            )
            f.write(f"{output_pinyin}\t{text}\t{weight}\n")


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


def _restore_missing_texts_from_snapshot(
    mapping: Dict[Tuple[str, str], int],
    previous_snapshot: Dict[Tuple[str, str], int],
    explicit_drop_terms: Set[str],
    stats_prefix: str,
    snapshot_restore_block_terms: Set[str] | None = None,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int]]:
    snapshot_restore_block_terms = snapshot_restore_block_terms or set()
    stats = {
        f"{stats_prefix}_snapshot_rows_considered": len(previous_snapshot),
        f"{stats_prefix}_snapshot_rows_restored": 0,
        f"{stats_prefix}_snapshot_texts_restored": 0,
        f"{stats_prefix}_snapshot_rows_skipped_explicit_drop": 0,
        f"{stats_prefix}_snapshot_rows_skipped_blocked_prefix": 0,
    }
    if not previous_snapshot:
        return mapping, stats

    restored = dict(mapping)
    current_texts = {text for _pinyin, text in restored.keys()}
    restored_texts: Set[str] = set()
    for key, weight in previous_snapshot.items():
        _pinyin, text = key
        if len(text) > 1 and text in explicit_drop_terms:
            stats[f"{stats_prefix}_snapshot_rows_skipped_explicit_drop"] += 1
            continue
        if len(text) > 1 and text in snapshot_restore_block_terms:
            stats[f"{stats_prefix}_snapshot_rows_skipped_blocked_prefix"] += 1
            continue
        if text in current_texts:
            continue
        restored[key] = weight
        current_texts.add(text)
        restored_texts.add(text)
        stats[f"{stats_prefix}_snapshot_rows_restored"] += 1

    stats[f"{stats_prefix}_snapshot_texts_restored"] = len(restored_texts)
    return restored, stats


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
            if CJK_FULL_RE.fullmatch(prefix):
                blocked.add(prefix)
    return blocked


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


def _write_query_path_prior(path: pathlib.Path, mapping: Dict[Tuple[str, str], int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for (query_pinyin, path_text), weight in sorted(
            mapping.items(), key=lambda kv: (kv[0][0], kv[0][1], -kv[1])
        ):
            f.write(f"{query_pinyin}\t{path_text}\t{weight}\n")


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
    if (output_query_path_sc is not None) or (output_query_path_tc is not None):
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

    for key in sc_blocklist:
        if key in sc_map:
            del sc_map[key]
            stats["known_incorrect_jiancha_entries_removed_sc"] += 1
    for key in tc_blocklist:
        if key in tc_map:
            del tc_map[key]
            stats["known_incorrect_jiancha_entries_removed_tc"] += 1

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
    parser.add_argument("--support-dict-sc", default="")
    parser.add_argument("--support-dict-tc", default="")
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
    previous_snapshot_sc = _load_existing_dict_snapshot(output_sc)
    previous_snapshot_tc = _load_existing_dict_snapshot(output_tc)
    support_dict_sc = repo_root / args.support_dict_sc if args.support_dict_sc else None
    support_dict_tc = repo_root / args.support_dict_tc if args.support_dict_tc else None
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
    jieba_pos_map: Dict[str, str] = {}
    char_frequency_prior: Dict[str, float] = {}
    pageviews_signal_map: Dict[str, float] = {}
    pageviews_persistence_signal_map: Dict[str, float] = {}
    pageviews_burst_signal_map: Dict[str, float] = {}
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
    curated_daily_entries: List[Tuple[str, str, float, str]] = []
    curated_daily_parse_stats: Dict[str, int] = {}
    curated_usage_score_map: Dict[str, float] = {}
    curated_source_hits_map: Dict[str, int] = {}
    curated_tc_usage_score_map: Dict[str, float] = {}
    curated_tc_source_hits_map: Dict[str, int] = {}
    curated_daily_stats: Dict[str, int] = {}
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
    sc_family_term_count_map: Dict[str, int] = {}
    sc_family_support_sum_map: Dict[str, float] = {}
    tc_family_term_count_map: Dict[str, int] = {}
    tc_family_support_sum_map: Dict[str, float] = {}
    sc_reading_term_count_map: Dict[Tuple[str, str], int] = {}
    sc_reading_support_sum_map: Dict[Tuple[str, str], float] = {}
    tc_reading_term_count_map: Dict[Tuple[str, str], int] = {}
    tc_reading_support_sum_map: Dict[Tuple[str, str], float] = {}
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
        sc_map, tc_map, stats, cedict_style_penalty_map = _parse_cedict_entries(
            source_text, args.min_hanzi
        )
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
            stats.update(curated_daily_parse_stats)
            stats.update(curated_daily_stats)
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

        sc_map, tc_map, cedict_stats, cedict_style_penalty_map = _parse_cedict_entries(
            cedict_text, args.min_hanzi
        )
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
        unihan_simplified_variant_map = _load_unihan_simplified_variant_map(unihan_payload)
        for trad_ch, simp_ch in unihan_simplified_variant_map.items():
            _apply_explicit_script_pair(
                trad_ch,
                simp_ch,
                trad_to_simp_char_map,
                simp_to_trad_char_map,
                sc_script_chars,
                tc_script_chars,
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
            tc_map, simp_to_trad_char_map
        )
        tc_map, tc_backfill_stats = _backfill_tc_mapping_from_sc_with_char_map(
            sc_map, tc_map, simp_to_trad_char_map
        )
        tc_map, tc_script_filter_stats = _filter_tc_mapping_with_script_hints(
            tc_map, sc_script_chars, tc_script_chars
        )
        curated_daily_explicit_pinyin_overrides = _build_curated_daily_explicit_pinyin_override_map(
            curated_daily_entries
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
        stats["jieba_pos_terms"] = len(jieba_pos_map)
        stats["char_frequency_prior_terms"] = len(char_frequency_prior)
        stats["pageviews_persistence_terms"] = len(pageviews_persistence_signal_map)
        stats["pageviews_burst_terms"] = len(pageviews_burst_signal_map)
        stats.update(wiki_stats)
        stats["wiktionary_title_set_size"] = len(wiktionary_titles)
        stats.update(wiktionary_stats)
        stats.update(wiktionary_seed_stats)
        stats.update(curated_daily_parse_stats)
        stats.update(sc_curated_daily_pinyin_override_stats)
        stats.update(tc_curated_daily_pinyin_override_stats)
        stats.update(sc_rescore_stats)
        stats.update(tc_rescore_stats)
        stats.update(augment_stats)
        stats.update(curated_daily_sc_exact_stats)
        stats.update(curated_daily_tc_exact_stats)
        stats.update(daily_prefix_stats)
        stats.update(wiki_proper_stats)
        stats.update(curated_daily_stats)
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
        unihan_simplified_variant_map = _load_unihan_simplified_variant_map(unihan_payload)
        for trad_ch, simp_ch in unihan_simplified_variant_map.items():
            _apply_explicit_script_pair(
                trad_ch,
                simp_ch,
                trad_to_simp_char_map,
                simp_to_trad_char_map,
                sc_script_chars,
                tc_script_chars,
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
            )
        sc_map, sc_char_normalize_stats = _normalize_sc_mapping_with_char_map(
            sc_map, trad_to_simp_char_map, simp_to_trad_char_map
        )
        sc_map, sc_script_filter_stats = _filter_sc_mapping_with_script_hints(
            sc_map, sc_script_chars, tc_script_chars
        )
        tc_map, tc_char_normalize_stats = _normalize_tc_mapping_with_char_map(
            tc_map, simp_to_trad_char_map
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
        (
            trad_to_simp_char_map,
            simp_to_trad_char_map,
            sc_script_chars,
            tc_script_chars,
        ) = _build_char_variant_hints(opencc_tc_to_sc_map, opencc_entries)
        unihan_simplified_variant_map = _load_unihan_simplified_variant_map(unihan_payload)
        for trad_ch, simp_ch in unihan_simplified_variant_map.items():
            _apply_explicit_script_pair(
                trad_ch,
                simp_ch,
                trad_to_simp_char_map,
                simp_to_trad_char_map,
                sc_script_chars,
                tc_script_chars,
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
            )
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
        if vertical_source_configs:
            vertical_entries: List[Tuple[str, str, float, str]] = []
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
        )
        stats.update(opencc_stats)
        stats.update(vertical_manifest_stats)
        stats.update(vertical_parse_stats)
        stats["unihan_family_support_terms_sc"] = len(sc_family_term_count_map)
        stats["unihan_family_support_terms_tc"] = len(tc_family_term_count_map)
        stats["unihan_reading_support_terms_sc"] = len(sc_reading_term_count_map)
        stats["unihan_reading_support_terms_tc"] = len(tc_reading_term_count_map)
        stats["unihan_leading_support_terms_sc"] = len(sc_leading_term_count_map)
        stats["unihan_leading_support_terms_tc"] = len(tc_leading_term_count_map)
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
        preferred_terms=curated_daily_sc_terms,
        stats_prefix="sc",
    )
    stats.update(sc_homophone_stats)
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
        preferred_terms=curated_daily_tc_terms,
        stats_prefix="tc",
    )
    stats.update(tc_homophone_stats)
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
    )
    stats.update(sc_snapshot_restore_stats)
    stats.update(tc_snapshot_restore_stats)
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
    sc_query_path_priors: Dict[Tuple[str, str], int] = {}
    tc_query_path_priors: Dict[Tuple[str, str], int] = {}
    if output_query_path_sc is not None:
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
        stats["sc_query_path_prior_rows"] = len(sc_query_path_priors)
    if output_query_path_tc is not None:
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
    stats.update(_remove_known_incorrect_jiancha_entries(sc_map, tc_map))

    _write_dict(
        output_sc,
        sc_map,
        preferred_terms=curated_daily_sc_terms,
        unihan_map=output_unihan_map,
        unihan_readings_map=output_unihan_readings_map,
        unihan_source_rank_map=output_unihan_source_rank_map,
        unihan_pinlu_detail_map=output_unihan_pinlu_detail_map,
    )
    _write_dict(
        output_tc,
        tc_map,
        preferred_terms=curated_daily_tc_terms,
        unihan_map=output_unihan_map,
        unihan_readings_map=output_unihan_readings_map,
        unihan_source_rank_map=output_unihan_source_rank_map,
        unihan_pinlu_detail_map=output_unihan_pinlu_detail_map,
    )
    if output_query_path_sc is not None:
        _write_query_path_prior(output_query_path_sc, sc_query_path_priors)
    if output_query_path_tc is not None:
        _write_query_path_prior(output_query_path_tc, tc_query_path_priors)
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

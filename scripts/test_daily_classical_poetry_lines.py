"""Lines of classical poems (the school curriculum, 唐诗三百首, 千家诗, 宋词三百首)
are exact rows: typed in full they are the first candidate, and from two
syllables typed on a line can be offered in full in the Tab area (its
completion prior is the ordinary one of a supplement row without corpus
evidence; at first the rows were exact-only, and a line came up only once it
was typed in full). They take no part in ranking or path statistics, and the
short promotion tables are the same with and without their completions.
长 has one reading in a line, by its meaning. 本机 goes above 本纪 and 笨鸡."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_external_cedict as builder
from test_daily_whitespace_phrases import read_rows

MANIFEST = ROOT / "manifests/curated_daily_supplement_phrases.tsv"
HEADER_POETRY = "# Classical poetry lines, 2026-10-15:"
HEADER_FORCED = "# Existing words set higher, 2026-10-15: 本机"
# Lines that must be there with their reading as typed.
SAMPLES = (
    ("chunmianbujuexiao", "春眠不觉晓", "春眠不覺曉"),
    ("chuchuwentiniao", "处处闻啼鸟", "處處聞啼鳥"),
    ("bairiyishanjin", "白日依山尽", "白日依山盡"),
    ("xiaohecailujianjianjiao", "小荷才露尖尖角", "小荷才露尖尖角"),
    ("xiantianxiazhiyoueryou", "先天下之忧而忧", "先天下之憂而憂"),
    ("guanguanjujiu", "关关雎鸠", "關關雎鳩"),
)
# Verse readings taught beside the standard ones keep a second row: 斜 xia,
# 衰 cui, and 骑 ji where it is a noun (horseman).
SECOND_READINGS = (
    ("yuanshanghanshanshijingxie", "远上寒山石径斜"),
    ("yuanshanghanshanshijingxia", "远上寒山石径斜"),
    ("kanyiqihongchen", "看一骑红尘"),
    ("kanyijihongchen", "看一骑红尘"),
)
# Characters read by their meaning have one reading in a line (2026-10-16).
# pypinyin read 长 zhang in most lines (日月长, and 唯见长江天际流 after its word
# 见长), and every line with 还 重 落 had two rows. 长 is zhang where it means to
# grow, elder or to lead and chang elsewhere; 还 huan (return) or hai (still);
# 重 chong (again, layers) or zhong (heavy, to value); 落 luo; 骑 qi as a verb.
ZHANG_LINES = {
    "长大一相逢", "杨家有女初长成", "生长明妃尚有村", "长者虽有问", "幼为长所育",
    "草长平湖白鹭飞", "去日儿童皆长大", "争长嶫相望", "暂凭杯酒长精神", "渠荒新叶长慈姑",
    "荆榛长满繁华地", "草长莺飞二月天",
}
# Lines read both ways keep both rows.
BOTH_WAYS = {
    "长": {"枣花未落桐阴长"},
    "还": {"还从物外起田园", "还作江南会", "冰池晴绿照还空", "推手含情还却手", "还宿河桥深处"},
    "重": {"塞上重笳音"},
}
# (pinyin, line) that must be there and be the only reading of the line
BY_MEANING = (
    ("penglaigongzhongriyuechang", "蓬莱宫中日月长"),
    ("weijianchangjiangtianjiliu", "唯见长江天际流"),
    ("danyuanrenchangjiu", "但愿人长久"),
    ("caozhangyingfeieryuetian", "草长莺飞二月天"),
    ("qianlijianglingyirihuan", "千里江陵一日还"),
    ("mingyueheshizhaowohuan", "明月何时照我还"),
    ("zhanuanhuanhanshihou", "乍暖还寒时候"),
    ("yushuohaixiu", "欲说还休"),
    ("sihuahaisifeihua", "似花还似非花"),
    ("qingzhouyiguowanchongshan", "轻舟已过万重山"),
    ("huazhongjinguancheng", "花重锦官城"),
    ("shanchongshuifuyiwulu", "山重水复疑无路"),
    ("luoxiayuguwuqifei", "落霞与孤鹜齐飞"),
    ("langqizhumalai", "郎骑竹马来"),
    ("momoliangqingnanyu", "脉脉两情难语"),
    ("jingponichangyuyiqu", "惊破霓裳羽衣曲"),
    ("rouqingsishui", "柔情似水"),
)
# Lines whose corrected reading another source had heavier keep its weight;
# they and 郎骑竹马来 (qi from an older row) keep that row's completion prior.
KEPT_WEIGHTS = {"大珠小珠落玉盘": 445, "同是天涯沦落人": 451, "无可奈何花落去": 638,
                "柔情似水": 423, "落霞与孤鹜齐飞": 445}
MERGED = set(KEPT_WEIGHTS) | {"郎骑竹马来"}


def readings_of(char, pinyin, text):
    """The syllables of char in a reading of text, or None where the parser
    does not cut the reading one syllable per character."""
    syllables = builder._runtime_parse_compact_pinyin(pinyin)
    if len(syllables) != len(text):
        return None
    return ",".join(syllable for syllable, ch in zip(syllables, text) if ch == char)


FORCED = (("benji", "本机", "本機", 760),)


def block(header):
    """(pinyin, simplified, traditional, weight, mode) rows under a header."""
    rows = []
    inside = False
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.startswith(header):
            inside = True
            continue
        if inside:
            if not line or line.startswith("#"):
                break
            sc, tc, usage, pinyin, mode = line.split("\t")
            rows.append((pinyin, sc, tc, int(round(float(usage) * 1000)), mode))
    return rows


ROWS = tuple(row[:4] for row in block(HEADER_POETRY))


class DailyClassicalPoetryTests(unittest.TestCase):
    def test_block_rows(self):
        rows = block(HEADER_POETRY)
        self.assertGreater(len(rows), 7800)
        self.assertEqual({"exact_rank_no_contains"}, {row[4] for row in rows})
        self.assertEqual(len(rows), len({(row[0], row[1]) for row in rows}))
        self.assertEqual(len(rows), len({(row[0], row[2]) for row in rows}))
        weights = {}
        for pinyin, sc, tc, weight, _ in rows:
            self.assertTrue(4 <= len(sc) <= 11, sc)
            self.assertEqual(len(sc), len(tc), sc)
            self.assertTrue(pinyin.isascii() and pinyin.islower() and pinyin.isalpha(), pinyin)
            # four characters 200, school poems 360, the rest 300 (homophones one less)
            if sc in KEPT_WEIGHTS:
                self.assertEqual(KEPT_WEIGHTS[sc], weight, sc)
                continue
            self.assertTrue(any(top - 3 <= weight <= top for top in (200, 300, 360)), (sc, weight))
            weights.setdefault(pinyin, []).append(weight)
        for pinyin, values in weights.items():
            self.assertEqual(len(values), len(set(values)), pinyin)
        for sample in SAMPLES + tuple((p, s, None) for p, s in SECOND_READINGS):
            self.assertTrue(any(row[0] == sample[0] and row[1] == sample[1] and
                                (sample[2] is None or row[2] == sample[2]) for row in rows), sample)

    def test_characters_read_by_meaning(self):
        found = {}
        for pinyin, sc, _tc, _weight, _mode in block(HEADER_POETRY):
            for char in "长还重落脉骑":
                if char in sc:
                    reading = readings_of(char, pinyin, sc)
                    if reading is not None:
                        found.setdefault((char, sc), set()).add(reading)
        for char, minimum in (("长", 200), ("还", 80), ("重", 80), ("落", 140)):
            lines = {sc for c, sc in found if c == char}
            self.assertGreater(len(lines), minimum, char)
            for sc in lines:
                readings = found[(char, sc)]
                if sc in BOTH_WAYS.get(char, ()):
                    self.assertEqual(2, len(readings), sc)
                else:
                    self.assertEqual(1, len(readings), sc)
        for (char, sc), readings in found.items():
            if char == "长" and sc not in BOTH_WAYS["长"]:
                wanted = "zhang" if sc in ZHANG_LINES else "chang"
                self.assertEqual({",".join([wanted] * sc.count("长"))}, readings, sc)
            if char == "落":
                self.assertNotIn("lao", ",".join(readings), sc)
            if char == "脉" and "脉脉" in sc:
                self.assertEqual({"mo,mo"}, readings, sc)
        rows = {}
        for pinyin, sc, _tc, _weight, _mode in block(HEADER_POETRY):
            rows.setdefault(sc, set()).add(pinyin)
        for pinyin, sc in BY_MEANING:
            self.assertEqual({pinyin}, rows[sc], sc)

    def test_no_other_reading_of_a_line_read_anew(self):
        # Rows of other sources that read such a character otherwise are gone
        # (但愿人长久 was also zhang at 812, 唯见长江天际流 zhang at 10).
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            block_keys = {(row[0], row[index]) for row in ROWS}
            for pinyin, sc in BY_MEANING:
                text = next(row[index] for row in ROWS if row[1] == sc)
                found = {key for key in rows if key[1] == text}
                self.assertEqual({(pinyin, text)}, {(p.replace("'", ""), t) for p, t in found}, text)
                self.assertTrue(found <= block_keys or len(found) == 1, text)

    def test_explicit_readings_and_ranks_survive_rebuild(self):
        entries, _ = builder._parse_curated_daily_phrase_entries(MANIFEST.read_bytes(), 2)
        wanted = {(row[0], row[1]) for row in ROWS}
        selected = [entry for entry in entries if (entry[3], entry[0]) in wanted]
        regular, exact = builder._partition_curated_daily_post_rank_exact_entries(selected)
        self.assertFalse(regular)
        self.assertEqual(len(ROWS), len(exact))
        maps = ({}, {})
        builder._inject_curated_daily_post_rank_exact_entries(*maps, exact)
        for index, mapping in enumerate(maps, 1):
            self.assertEqual({(row[0], row[index]): row[3] for row in ROWS}, mapping)

    def test_generated_entries(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in ROWS:
                self.assertEqual([str(row[3]), "no_contains"], rows[(row[0], row[index])])

    def test_ordinary_prior(self):
        # popularity 80 from the base share alone, no layer: not exact-only
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_completion_prior_{variant}.txt")
            for row in ROWS:
                if row[1] in MERGED:
                    self.assertIn((row[0], row[index]), rows)
                    continue
                self.assertEqual((80, 0, 0, 0, 0, 0, 0),
                                 tuple(map(int, rows[(row[0], row[index])])), row[1])

    def test_completions(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            keys = {(row[0], row[index]) for row in ROWS}
            offered = {}
            for line in (ROOT / "data/generated" / f"dict_completion_lookup_{variant}.txt").read_text(
                    encoding="utf-8").splitlines():
                # prefix, pinyin, text, scores
                fields = line.split("\t")
                # (a line the dictionary had before is offered by its own row)
                key = (fields[1].replace("'", ""), fields[2]) if len(fields) > 2 else None
                if key in keys:
                    offered.setdefault(key, set()).add(fields[0])
            # Every line of three syllables or more that the runtime can match
            # (as many characters as syllables) is offered from some prefix.
            for pinyin, text in keys:
                syllables = builder._runtime_parse_compact_pinyin(pinyin)
                if len(syllables) >= 3 and len(syllables) == len(text) and "r" not in syllables:
                    self.assertIn((pinyin, text), offered, text)
            sample = ("chunmianbujuexiao", SAMPLES[0][index])
            self.assertTrue({"chunmian", "chunmianbu", "chunmianbujue"} <= offered[sample], offered[sample])

    def test_next_lines(self):
        # Typed in full, a line offers the mark and the next line of its poem
        # in the Tab area: rows of the long continuation table, appended by
        # build_long_completion_index.py --poetry-next-lines.
        import build_long_completion_index as continuation
        manifest = ROOT / "manifests/classical_poetry_next_lines.tsv"
        rows = [line.split("\t") for line in manifest.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#")]
        self.assertGreater(len(rows), 5000)
        self.assertIn(["春眠不觉晓", "春眠不覺曉", "，", "处处闻啼鸟", "處處聞啼鳥", "chu'chu'wen'ti'niao"], rows)
        for index, variant in enumerate(("sc", "tc")):
            entries = read_rows(f"dict_clean_{variant}.txt")
            texts = {text for _pinyin, text in entries}
            for row in rows:
                self.assertIn(row[2], "，。？！；：、", row)
                # anchor and next line are entries: typed in full each is one
                self.assertIn(row[index], texts, row)
                self.assertIn(row[3 + index], texts, row)
                self.assertEqual(len(row[3 + index]), len(row[5].split("'")), row)
            generated = (ROOT / "data/generated" / f"dict_long_completion_{variant}.txt").read_text(
                encoding="utf-8").splitlines()
            expected = continuation.poetry_next_line_rows(manifest, traditional=variant == "tc")
            self.assertEqual(expected, generated[-len(expected):])

    def test_forced_weights(self):
        self.assertEqual(FORCED, tuple(row[:4] for row in block(HEADER_FORCED)))
        self.assertEqual({"exact_rank"}, {row[4] for row in block(HEADER_FORCED)})
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in FORCED:
                self.assertEqual(str(row[3]), rows[(row[0], row[index])][0], row)
            # above the history book and the farm chicken
            for other in (("本纪", "本紀"), ("笨鸡", "笨雞")):
                self.assertGreater(int(rows[("benji", FORCED[0][index])][0]),
                                   int(rows[("benji", other[index - 1])][0]), other)


if __name__ == "__main__":
    unittest.main()

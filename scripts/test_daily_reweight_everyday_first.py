"""Keys whose first word by weight, or by the short promotion table, was rarer in everyday use than another word of
the key, reweighted on 2026-11-22. The short-word choice without a context of the character LM distilled from a larger
model (stage E2) no longer corrects them, where the earlier LM's choice had: the word the general text and everyday
conversation (LCCC) both write more often, or conversation far more often and the general text not three times less,
goes one above the words it passes (1000 at most, the word that held 1000 then 999); a promoted rarer word goes below
the next more frequent word of its key, so that the promotion is decided again. Where the engine still chose the other
word without a context, that word goes lower. One weight orders both variants. Left as they were: near ties, words an
earlier batch or a regression sample placed (but the original sample of wugu), keys whose first word is a third word,
and keys whose promotion came back at every weight tried."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from test_daily_whitespace_phrases import read_rows
from test_daily_cuo_xiu_sha_shui_phrases import block

HEADER_FORCED = '# Reweighted 2026-11-22 (exact_rank, the weight / 1000): keys whose first word by weight, or by the short promotion table, is rarer in everyday use than another word of the key (in the general text and in everyday conversation, LCCC), which the short-word choice without a context of the distilled character LM (stage E2) no longer corrects: the everyday word goes one above the words it passes (1000 at most, the word that held 1000 then 999), a promoted rarer word below the next more frequent word of its key, so that the promotion is decided again; one weight orders both variants.'
# (pinyin, simplified, traditional, weight) of the round's own block; the other weights are in the rows of the earlier
# batches that weighed the words (WEIGHTS holds every word of the round).
FORCED = [('pingding', '评定', '評定', 802), ('chengxing', '成型', '成型', 872), ('renqi', '人气', '人氣', 1000), ('renqi', '任期', '任期', 999), ('shuqi', '暑期', '暑期', 972), ('renshou', '人寿', '人壽', 180), ('huanxing', '唤醒', '喚醒', 711), ('suoxie', '缩写', '縮寫', 701), ('bingcheng', '秉承', '秉承', 777), ('zhenzhi', '真挚', '真摯', 345), ('wugu', '无辜', '無辜', 1000), ('wugu', '无故', '無故', 800), ('weizhe', '围着', '圍著', 1000), ('weizhe', '为着', '為著', 999), ('shenming', '神明', '神明', 1000), ('shenming', '申明', '申明', 999), ('kongxi', '空隙', '空隙', 1000), ('kongxi', '空袭', '空襲', 999), ('zifei', '自费', '自費', 436), ('youzi', '游子', '遊子', 394), ('bita', '比他', '比他', 283), ('bita', '比她', '比她', 282), ('bita', '比它', '比它', 281), ('chengzhi', '诚挚', '誠摯', 773), ('jinlin', '紧邻', '緊鄰', 980), ('anxiang', '安详', '安詳', 764), ('anxiang', '暗想', '暗想', 110), ('shangyuan', '伤员', '傷員', 1000), ('shangyuan', '上元', '上元', 999), ('chicheng', '驰骋', '馳騁', 734), ('chicheng', '赤诚', '赤誠', 733), ('chicheng', '池晟', '池晟', 732), ('yingjun', '英俊', '英俊', 553), ('guoke', '过客', '過客', 11), ('shengcai', '生菜', '生菜', 1000), ('shengcai', '剩菜', '剩菜', 999), ('mingjing', '明镜', '明鏡', 950), ('hengshan', '衡山', '衡山', 561), ('jiaotiao', '教条', '教條', 421), ('daosui', '捣碎', '搗碎', 1000), ('daosui', '稻穗', '稻穗', 999), ('hujun', '户均', '戶均', 441), ('changye', '长夜', '長夜', 281), ('dizai', '抵在', '抵在', 200), ('bibi', '比比', '比比', 281), ('yuanhe', '缘何', '緣何', 628), ('cefan', '侧翻', '側翻', 698), ('fansuan', '反酸', '反酸', 441), ('gouqian', '勾芡', '勾芡', 281), ('chaogang', '超纲', '超綱', 26), ('guzhai', '古宅', '古宅', 329), ('qianshang', '签上', '簽上', 21), ('fengzhao', '凤爪', '鳳爪', 429), ('midao', '迷倒', '迷倒', 139), ('mingwan', '冥顽', '冥頑', 150), ('daqiang', '打枪', '打槍', 827), ('daqiang', '搭腔', '搭腔', 140), ('lamo', '拉磨', '拉磨', 330)]
WEIGHTS = [('pingding', '评定', '評定', 802), ('chengxing', '成型', '成型', 872), ('renqi', '人气', '人氣', 1000), ('renqi', '任期', '任期', 999), ('shuqi', '暑期', '暑期', 972), ('renshou', '人寿', '人壽', 180), ('huanxing', '唤醒', '喚醒', 711), ('suoxie', '缩写', '縮寫', 701), ('bingcheng', '秉承', '秉承', 777), ('shouhou', '售后', '售後', 651), ('yili', '毅力', '毅力', 282), ('yili', '一粒', '一粒', 281), ('zhenzhi', '真挚', '真摯', 345), ('wugu', '无辜', '無辜', 1000), ('wugu', '无故', '無故', 800), ('weizhe', '围着', '圍著', 1000), ('weizhe', '为着', '為著', 999), ('shenming', '神明', '神明', 1000), ('shenming', '申明', '申明', 999), ('kongxi', '空隙', '空隙', 1000), ('kongxi', '空袭', '空襲', 999), ('zifei', '自费', '自費', 436), ('youzi', '柚子', '柚子', 395), ('youzi', '游子', '遊子', 394), ('bita', '比他', '比他', 283), ('bita', '比她', '比她', 282), ('bita', '比它', '比它', 281), ('zhuangzai', '装在', '裝在', 306), ('chengzhi', '诚挚', '誠摯', 773), ('jinlin', '紧邻', '緊鄰', 980), ('anxiang', '安详', '安詳', 764), ('anxiang', '暗香', '暗香', 111), ('anxiang', '暗想', '暗想', 110), ('shangyuan', '伤员', '傷員', 1000), ('shangyuan', '上元', '上元', 999), ('chicheng', '驰骋', '馳騁', 734), ('chicheng', '赤诚', '赤誠', 733), ('chicheng', '池晟', '池晟', 732), ('yingjun', '英俊', '英俊', 553), ('guoke', '过客', '過客', 11), ('shengcai', '生菜', '生菜', 1000), ('shengcai', '剩菜', '剩菜', 999), ('mingjing', '明镜', '明鏡', 950), ('hengshan', '衡山', '衡山', 561), ('jiaotiao', '教条', '教條', 421), ('daosui', '捣碎', '搗碎', 1000), ('daosui', '稻穗', '稻穗', 999), ('hujun', '户均', '戶均', 441), ('changye', '长夜', '長夜', 281), ('dizai', '滴在', '滴在', 281), ('dizai', '抵在', '抵在', 200), ('bibi', '比比', '比比', 281), ('yuanhe', '缘何', '緣何', 628), ('cefan', '侧翻', '側翻', 698), ('fansuan', '反酸', '反酸', 441), ('gouqian', '勾芡', '勾芡', 281), ('chaogang', '超纲', '超綱', 26), ('guzhai', '古宅', '古宅', 329), ('hengping', '横屏', '橫屏', 250), ('qianshang', '签上', '簽上', 21), ('fengzhao', '凤爪', '鳳爪', 429), ('midao', '迷倒', '迷倒', 139), ('mingwan', '冥顽', '冥頑', 150), ('zhiguai', '只怪', '只怪', 199), ('pinse', '拼色', '拼色', 199), ('jiabing', '加冰', '加冰', 441), ('daqiang', '打枪', '打槍', 827), ('daqiang', '搭腔', '搭腔', 140), ('shuishu', '谁输', '誰輸', 306), ('liudang', '留档', '留檔', 662), ('lamo', '拉磨', '拉磨', 330), ('yaotu', '要吐', '要吐', 419), ('yaotu', '要涂', '要塗', 418), ('xingya', '行呀', '行呀', 199)]
# (pinyin, simplified, traditional): the key's first word by weight in both variants, and no promotion over it.
FIRSTS = [('pingding', '评定', '評定'), ('chengxing', '成型', '成型'), ('renqi', '人气', '人氣'), ('shuqi', '暑期', '暑期'), ('renshou', '忍受', '忍受'), ('huanxing', '唤醒', '喚醒'), ('suoxie', '缩写', '縮寫'), ('bingcheng', '秉承', '秉承'), ('shouhou', '售后', '售後'), ('yili', '毅力', '毅力'), ('zhenzhi', '真挚', '真摯'), ('wugu', '无辜', '無辜'), ('weizhe', '围着', '圍著'), ('shenming', '神明', '神明'), ('kongxi', '空隙', '空隙'), ('zifei', '自费', '自費'), ('youzi', '柚子', '柚子'), ('bita', '比他', '比他'), ('zhuangzai', '装在', '裝在'), ('chengzhi', '诚挚', '誠摯'), ('jinlin', '紧邻', '緊鄰'), ('anxiang', '安详', '安詳'), ('shangyuan', '伤员', '傷員'), ('chicheng', '驰骋', '馳騁'), ('yingjun', '英俊', '英俊'), ('guoke', '过客', '過客'), ('shengcai', '生菜', '生菜'), ('mingjing', '明镜', '明鏡'), ('hengshan', '衡山', '衡山'), ('jiaotiao', '教条', '教條'), ('daosui', '捣碎', '搗碎'), ('hujun', '户均', '戶均'), ('changye', '长夜', '長夜'), ('dizai', '滴在', '滴在'), ('bibi', '比比', '比比'), ('yuanhe', '缘何', '緣何'), ('cefan', '侧翻', '側翻'), ('fansuan', '反酸', '反酸'), ('gouqian', '勾芡', '勾芡'), ('chaogang', '超纲', '超綱'), ('guzhai', '古宅', '古宅'), ('hengping', '横屏', '橫屏'), ('qianshang', '签上', '簽上'), ('fengzhao', '凤爪', '鳳爪'), ('midao', '迷倒', '迷倒'), ('mingwan', '明晚', '明晚'), ('zhiguai', '只怪', '只怪'), ('pinse', '拼色', '拼色'), ('jiabing', '加冰', '加冰'), ('daqiang', '打枪', '打槍'), ('shuishu', '谁输', '誰輸'), ('liudang', '留档', '留檔'), ('lamo', '拉磨', '拉磨'), ('yaotu', '要吐', '要吐'), ('xingya', '行呀', '行呀')]
# mingjing: the promotion builder still puts 明净 above 明镜 (lower weights of 明净 widen its lead), and the short-word
# choice without a context gives 明镜 back.
PROMOTED_BACK = {"mingjing": ("明净", "明淨")}


def promotions(variant):
    rows = {}
    for line in (ROOT / f"data/generated/dict_short_promotion_{variant}.txt").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            fields = line.split("\t")
            rows[fields[0]] = (fields[1], fields[2])
    return rows


class DailyReweightEverydayFirstTests(unittest.TestCase):
    def test_block(self):
        forced = block(HEADER_FORCED)
        self.assertEqual({"exact_rank"}, {row[4] for row in forced})
        self.assertEqual({row[:4] for row in FORCED}, {tuple(row[:4]) for row in forced})

    def test_generated_weights(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            rows = read_rows(f"dict_clean_{variant}.txt")
            for row in WEIGHTS:
                self.assertEqual(str(row[3]), rows[(row[0], row[index])][0], (variant, row))

    def test_first_words(self):
        for index, variant in enumerate(("sc", "tc"), 1):
            keys = {}
            for (pinyin, text), fields in read_rows(f"dict_clean_{variant}.txt").items():
                keys.setdefault(pinyin, {})[text] = int(fields[0])
            promoted = promotions(variant)
            for row in FIRSTS:
                pinyin, first = row[0], row[index]
                words = {t: w for t, w in keys[pinyin].items() if len(t) >= 2}
                self.assertEqual(first, max(words, key=words.get), (variant, pinyin))
                self.assertEqual(1, list(words.values()).count(words[first]), (variant, pinyin))
                if pinyin in PROMOTED_BACK:
                    self.assertEqual((first, PROMOTED_BACK[pinyin][index - 1]), promoted.get(pinyin), (variant, pinyin))
                else:
                    self.assertNotEqual(first, promoted.get(pinyin, ("", ""))[0],
                                        (variant, pinyin, promoted.get(pinyin)))

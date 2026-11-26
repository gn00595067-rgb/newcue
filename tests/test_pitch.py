# -*- coding: utf-8 -*-
"""加碼優惠提示、效益說明（第二階段 2-1、2-2）。"""
from datetime import date

import pitch


def _cfg(rad=None, cf=None, nat=True):
    c = {}
    if rad is not None:
        c["全家廣播"] = {"share": rad, "sec_shares": {15: 100}, "is_national": nat, "regions": ["全省"]}
    if cf is not None:
        c["家樂福"] = {"share": cf, "sec_shares": {15: 100}, "is_national": True, "regions": ["全省"]}
    return c


def test_接近50萬提示():
    h = pitch.upsell_hints(_cfg(rad=100), 450_000)
    assert len(h) == 1 and "再加 5萬達 50萬" in h[0] and "全家 10%" in h[0] and "萬家福 15%" in h[0]


def test_差太多或已最高不提示():
    assert pitch.upsell_hints(_cfg(rad=100), 300_000) == []       # 差 20 萬 > 15 萬
    assert pitch.upsell_hints(_cfg(rad=100), 1_200_000) == []     # 專案談
    assert pitch.upsell_hints(_cfg(rad=100, nat=False), 450_000) == []   # 單區不提示


def test_10_90萬級與萬家福():
    assert "達 90萬" in pitch.upsell_hints(_cfg(rad=100), 800_000)[0]
    h = pitch.upsell_hints(_cfg(cf=100), 700_000)
    assert len(h) == 1 and "再加 5萬達 75萬" in h[0] and "25%" in h[0]


def _row(media, region, stores, spots, days, gift=False):
    r = {"media": media, "region": region, "program_num": stores, "spots": spots,
         "schedule": [spots // days] * days}
    if gift:
        r["is_rebate"] = True
    return r


def test_效益說明():
    rows = [_row("全家廣播", "中區", 850, 930, 31), _row("全家廣播", "中區", "", 93, 31, gift=True)]
    s = pitch.benefit_summary(rows, 31, 230_000, date(2027, 3, 1), date(2027, 3, 31))
    t = s["total"]
    assert t["spots"] == 1023 and t["gift_spots"] == 93
    assert t["impressions"] == 850 * 1023 and t["gift_impressions"] == 850 * 93
    assert round(t["cpm"]) == round(230_000 / (850 * 1023) * 1000)
    txt = "".join(s["text"])
    assert "全家便利商店店內廣播 850 店（每店每天約 33 檔）" in txt
    assert "其中加贈 93 檔" in txt and "2027/03/01～2027/03/31 共 31 天" in txt

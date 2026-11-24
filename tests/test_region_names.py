# -*- coding: utf-8 -*-
"""宜歆 10/21 #5：東吳／聲活／鉑霖 CUE 播出地區改實際寫法（北區→北北基…）；只改顯示，region 不動。"""
import simple_config as sc
from utils import cue_location


def test_general_cue_location_names():
    got = [cue_location({"media": "全家廣播", "region": r}) for r in ("北區", "桃竹苗", "中區", "雲嘉南", "高屏", "東區", "全省")]
    assert got == ["北北基", "桃竹苗", "中彰投", "雲嘉南", "高屏", "宜花東", "全省"]
    assert cue_location({"media": "家樂福", "region": "全省超市"}) == "超市"          # 家樂福照舊


def test_simple_subsidiary_labels_match():
    assert [sc.REGION_LABELS[r] for r in sc.REGIONS_ORDER] == ["北北基", "桃竹苗", "中彰投", "雲嘉南", "高屏", "宜花東"]

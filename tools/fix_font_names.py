# -*- coding: utf-8 -*-
"""
修正 assets/fonts 的 Noto Sans TC name table。

問題：Regular 與 Bold 兩檔的 nameID6(PostScript name) 都寫成 NotoSansTC-Thin、
     nameID2(subfamily) 都是 Regular → reportlab 以 PS name 當 BaseFont 去重，
     兩個字型被視為同一個，整份 PDF 只嵌一個 subset、setFont("CJK-Bold") 畫出來仍是 Regular。

修法：把每檔改成正確、且彼此不同的 name：
  nameID1 = "Noto Sans TC"
  nameID2 = "Regular" / "Bold"
  nameID4 = "Noto Sans TC Regular" / "Noto Sans TC Bold"
  nameID6 = "NotoSansTC-Regular" / "NotoSansTC-Bold"   ← PS name 必須不同

覆寫原檔。跑法：python tools/fix_font_names.py
"""
import os

from fontTools.ttLib import TTFont

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "assets", "fonts")

TARGETS = [
    ("NotoSansTC-Regular.ttf", "NotoSansTC-Regular", "Regular"),
    ("NotoSansTC-Bold.ttf", "NotoSansTC-Bold", "Bold"),
]


def fix(path, ps_name, subfamily):
    t = TTFont(path)
    for n in t["name"].names:
        if n.nameID == 1:
            n.string = "Noto Sans TC"
        elif n.nameID == 2:
            n.string = subfamily
        elif n.nameID == 4:
            n.string = "Noto Sans TC " + subfamily
        elif n.nameID == 6:
            n.string = ps_name
    t.save(path)
    # 驗證
    t2 = TTFont(path)
    got = {n.nameID: n.toUnicode() for n in t2["name"].names if n.nameID in (1, 2, 4, 6)}
    print(f"{os.path.basename(path)} -> {got}")


def main():
    for fn, ps, sub in TARGETS:
        fix(os.path.join(FONT_DIR, fn), ps, sub)


if __name__ == "__main__":
    main()

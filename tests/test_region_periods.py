"""各區不同走期（spec：docs/specs/各區不同走期.md）：utils.apply_region_periods。"""
from datetime import date

from utils import apply_region_periods, calculate_schedule

S, E = date(2026, 1, 1), date(2026, 1, 31)


def _row(media, region, spots, days=31, **kw):
    return {"media": media, "region": region, "spots": spots, "schedule": calculate_schedule(spots, days), **kw}


def test_北區整月_桃竹苗半月():
    rows = [_row("全家廣播", "北區", 620), _row("全家廣播", "桃竹苗", 310)]
    apply_region_periods(rows, {"全家廣播": {"桃竹苗": (date(2026, 1, 1), date(2026, 1, 15))}}, S, E)
    north, tao = rows
    assert north["schedule"] == calculate_schedule(620, 31)          # 沒設的區不動
    assert sum(tao["schedule"]) == 310                                # 總檔次不變
    assert all(v > 0 for v in tao["schedule"][:15])
    assert tao["schedule"][15:] == [0] * 16                           # 1/16 起留空
    assert len(tao["schedule"]) == 31


def test_走期在中段():
    rows = [_row("新鮮視", "中區", 100)]
    apply_region_periods(rows, {"新鮮視": {"中區": (date(2026, 1, 11), date(2026, 1, 20))}}, S, E)
    sch = rows[0]["schedule"]
    assert sch[:10] == [0] * 10 and sch[20:] == [0] * 11
    assert sch[10:20] == [10] * 10


def test_只套對應平台():
    rows = [_row("新鮮視", "桃竹苗", 310)]
    before = list(rows[0]["schedule"])
    apply_region_periods(rows, {"全家廣播": {"桃竹苗": (date(2026, 1, 1), date(2026, 1, 15))}}, S, E)
    assert rows[0]["schedule"] == before


def test_加贈已在區走期內不動_奇數總檔不補偶():
    sch = [0] * 31
    sch[2:5] = [3, 3, 3]                                             # 加贈 1/3～1/5 每天 3 檔
    rows = [{"media": "全家廣播", "region": "桃竹苗", "spots": 9, "schedule": list(sch), "is_custom_bonus": True}]
    period = {"全家廣播": {"桃竹苗": (date(2026, 1, 1), date(2026, 1, 15))}}
    apply_region_periods(rows, period, S, E)
    assert rows[0]["schedule"] == sch
    # 超出走期 → 重排進走期內，奇數總檔維持 9
    sch2 = [0] * 31
    sch2[20:23] = [3, 3, 3]
    rows = [{"media": "全家廣播", "region": "桃竹苗", "spots": 9, "schedule": list(sch2)}]
    apply_region_periods(rows, period, S, E)
    assert sum(rows[0]["schedule"]) == 9 and rows[0]["schedule"][15:] == [0] * 16


def test_沒有排程或長度不符略過():
    rows = [{"media": "全家廣播", "region": "桃竹苗", "spots": 10, "schedule": None},
            {"media": "全家廣播", "region": "桃竹苗", "spots": 10, "schedule": [2] * 5}]
    apply_region_periods(rows, {"全家廣播": {"桃竹苗": (date(2026, 1, 1), date(2026, 1, 15))}}, S, E)
    assert rows[0]["schedule"] is None and rows[1]["schedule"] == [2] * 5

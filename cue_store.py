# -*- coding: utf-8 -*-
"""
CUE 快照（Ragic 串接第 2 期：存檔／讀回／版本／異動紀錄）。規格：docs/specs/Ragic串接_訂檔流程.md

各製作模式算完的結果 → 統一的「快照」dict：
  header  客戶、產品、格式、業務、走期、金額
  waves   [{label, start, end, rows:[正規化列]}]；一般CUE 無分波段時只有一波
  restore 還原該模式輸入欄位用的 session 值（日期已序列化）
  customer 從 Ragic 帶入的客戶（編號、現折、退佣…）
  version / history 版本與異動紀錄
正規化列：{platform: 全家廣播|新鮮視|家樂福, region, seconds, spots, schedule, net, list, kind}
  net＝該列分攤的實收未稅（訂檔收入子表用），回饋／加贈／超市（計價於量販）為 0。

快照以 JSON 存在 cue/2「投放參數詳情」欄尾端（[CUESNAP] 標記），舊版 [EXT]／[AGENCY_EXT] 文字保留在前面，
原本的還原機制照常可用。本模組不 import streamlit。
"""
import json
from datetime import date, datetime

from agency_cue import rhu

SNAP_MARK = "[CUESNAP]"
NO_CHANGE = "內容無變動（重新存檔）"
SCHEMA = 1
REGIONS6 = ["北區", "桃竹苗", "中區", "雲嘉南", "高屏", "東區"]

# cue/2 欄位 ID（RAGIC_MAP 以外、第 2 期起寫入的欄位；2026-10-13 以 naming=EID 對照實際紀錄取得）
CUE2_CUSTOMER_ID = "1015919"   # 客戶編號(成交)（連結客戶表，doLinkLoad 會帶客戶名稱2／業務／客服／現折／退佣…）
CUE2_WAVES = "1015933"         # 總波段
CUE2_NET_TOTAL = "1016046"     # 平台實收總計
CUE2_ORIG_PRICE = "1016047"    # 原CUE表成交價


# =============================================================================
# 序列化（session 值含 date）
# =============================================================================
def to_jsonable(v):
    if isinstance(v, datetime):
        return {"__dt__": v.isoformat()}
    if isinstance(v, date):
        return {"__date__": v.isoformat()}
    if isinstance(v, (list, tuple)):
        return [to_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): to_jsonable(x) for k, x in v.items()}
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def from_jsonable(v):
    if isinstance(v, dict):
        if set(v) == {"__date__"}:
            return date.fromisoformat(v["__date__"])
        if set(v) == {"__dt__"}:
            return datetime.fromisoformat(v["__dt__"])
        return {k: from_jsonable(x) for k, x in v.items()}
    if isinstance(v, list):
        return [from_jsonable(x) for x in v]
    return v


# =============================================================================
# 各模式 → 正規化列
# =============================================================================
def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _row(platform, region, seconds, spots, schedule, net=0, lst=0, kind="main"):
    return {"platform": platform, "region": region, "seconds": int(seconds or 0),
            "spots": int(spots or 0), "schedule": list(schedule) if schedule else None,
            "net": int(net or 0), "list": int(lst or 0), "kind": kind}


def norm_general_rows(rows):
    """一般 CUE rows（一般CUE／年約季約子公司格式／專案CUE／一鍵CUE 經 simple_general）→ 正規化列。
    Package 群組（is_pkg_member，同 media＋nat_pkg；不分秒數，固定專案多秒數共用一個專案價）
    實收依各列定價比例分攤。呼叫端應再以 scale_net 對齊成交價。"""
    out, groups = [], {}
    for r in rows:
        kind = "rebate" if r.get("is_rebate") else ("bonus" if r.get("is_custom_bonus") else "main")
        sch = r.get("schedule") or []
        spots = r.get("spots") or sum(x for x in sch if isinstance(x, (int, float)))
        nr = _row(r.get("media"), r.get("region"), r.get("seconds"), spots, sch,
                  lst=_num(r.get("rate_display")) or 0, kind=kind)
        if kind == "main":
            if r.get("is_pkg_member"):
                gk = (r.get("media"), r.get("nat_pkg_display"))
                groups.setdefault(gk, []).append(nr)
            else:
                nr["net"] = int(_num(r.get("pkg_display")) or 0)
        out.append(nr)
    for (_m, pkg), members in groups.items():
        _spread(members, int(_num(pkg) or 0))
    return out


def _spread(members, total):
    """total 依各列 list（定價）比例分給 members，尾差給最後一列；全無定價時給第一列。"""
    weights = [m["list"] for m in members]
    if not members:
        return
    if sum(weights) <= 0:
        members[0]["net"] = total
        return
    acc = 0
    for m in members[:-1]:
        m["net"] = rhu(total * m["list"] / sum(weights))
        acc += m["net"]
    members[-1]["net"] = total - acc


def norm_agency_model(model):
    """代理商 CUE model（agency_cue.build_agency_model／年約季約代理商）→ 正規化列。"""
    import agency_cue as ac
    out = []
    for sh in model.get("sheets", []):
        fam = sh["platform"] == ac.PLATFORM_FAMILY
        for r in sh["rows"]:
            k = r["kind"]
            if fam:
                plat, reg = "全家廣播", "全省"
            else:
                plat, reg = "家樂福", ("全省超市" if k in (ac.KIND_SUPER, ac.KIND_SUPER_REBATE) else "全省量販")
            kind = "main" if k == ac.KIND_MAIN else ("super" if k == ac.KIND_SUPER else
                                                     ("comp" if k == ac.KIND_COMP else "rebate"))
            net = _num(r.get("net_display")) if k == ac.KIND_MAIN else 0
            out.append(_row(plat, reg, sh["seconds"], r["spots"], r.get("schedule"),
                            net=net or 0, lst=r.get("list_total") or 0, kind=kind))
    return out


def norm_simple_sheet(model, sheet):
    """簡易模式（含代理商一鍵模板）單一秒數版 → 正規化列。"""
    if model.family == "subsidiary":
        from simple_general import sheet_to_rows
        return norm_general_rows(sheet_to_rows(sheet))
    out = []
    for blk in sheet.blocks:
        fam = blk.platform == "全家企頻"
        for r in blk.rows:
            plat = "全家廣播" if fam else "家樂福"
            reg = "全省" if fam else ("全省超市" if r.kind in ("super", "super_bonus") else "全省量販")
            kind = {"main": "main", "super": "super"}.get(r.kind, "rebate")
            net = _num(r.net_display) if r.kind == "main" else 0
            out.append(_row(plat, reg, sheet.seconds, r.spots, r.schedule, net=net or 0,
                            lst=r.list_total or 0, kind=kind))
    return out


def scale_net(rows, target):
    """各列實收按比例縮放到 target（主管覆寫成交價等），尾差給最大的一列。"""
    cur = sum(r["net"] for r in rows)
    if not target or cur <= 0 or cur == target:
        return rows
    for r in rows:
        r["net"] = rhu(r["net"] * target / cur)
    diff = int(target) - sum(r["net"] for r in rows)
    if diff:
        max(rows, key=lambda r: r["net"])["net"] += diff
    return rows


def split_waves(rows, start, segments):
    """整段走期的正規化列 → 各波段（schedule 依日切出，實收依該波檔次比例分攤，尾差給最後一波）。
    segments：[(波段開始, 波段結束), ...]；start：整段走期開始日。"""
    waves = [{"label": f"波段{i + 1}", "start": a, "end": b, "rows": []} for i, (a, b) in enumerate(segments)]
    for r in rows:
        sch = r.get("schedule") or []
        given = 0
        for i, (a, b) in enumerate(segments):
            d0, d1 = (a - start).days, (b - start).days
            part = sch[d0:d1 + 1] if sch else []
            spots = sum(x for x in part if isinstance(x, (int, float)))
            nr = dict(r, schedule=part or None, spots=int(spots))
            if i == len(segments) - 1:
                nr["net"] = r["net"] - given
            else:
                nr["net"] = rhu(r["net"] * spots / r["spots"]) if r["spots"] else 0
                given += nr["net"]
            if spots or nr["net"]:
                waves[i]["rows"].append(nr)
    return waves


# =============================================================================
# 快照
# =============================================================================
def make_snapshot(mode, header, waves, restore=None, customer=None):
    """waves：[{"label","start","end","rows"}]（日期可為 date）。"""
    return {
        "schema": SCHEMA, "mode": mode,
        "header": to_jsonable(header),
        "waves": [to_jsonable(w) for w in waves],
        "restore": to_jsonable(restore or {}),
        "customer": to_jsonable(customer or {}),
        "version": 0, "history": [],
    }


def all_rows(snap):
    return [r for w in snap.get("waves", []) for r in w.get("rows", [])]


def _as_general(rows):
    return [{"media": r["platform"], "region": r["region"]} for r in rows]


def summarize(snap):
    """供 cue/2 欄位與畫面摘要：平台、平台細項、總檔數、秒數、實收合計、波段數。"""
    from utils import build_platform_detail_text, build_platform_text
    from ragic_booking.order_from_cue import count_spots
    rows = all_rows(snap)
    cfg = {}
    for m in ("全家廣播", "新鮮視"):
        regs = {r["region"] for r in rows if r["platform"] == m}
        cfg[m] = {"is_national": "全省" in regs or set(REGIONS6) <= regs}
    return {
        "platform": build_platform_text(_as_general(rows)),
        "platform_detail": build_platform_detail_text(_as_general(rows), cfg),
        # 全省展開的六區列只計一次（宜歆 10/27 #12：年約 2 波×200 檔顯示成 2,400）
        "total_spots": sum(count_spots(w.get("rows", [])) for w in snap.get("waves", [])),
        "seconds": "、".join(str(s) for s in sorted({r["seconds"] for r in rows if r["seconds"]})),
        "net_total": sum(r["net"] for r in rows),
        "waves": len(snap.get("waves", [])),
    }


def _wave_totals(snap):
    out = {}
    for i, w in enumerate(snap.get("waves", [])):
        for r in w.get("rows", []):
            k = (i, r["platform"], r["seconds"])
            t = out.setdefault(k, [0, 0])
            t[0] += r["spots"]
            t[1] += r["net"]
    return out


_PLAT_DISP = {"全家廣播": "全家", "新鮮視": "新鮮視", "家樂福": "萬家福．樂家康"}


def diff_summary(old, new):
    """兩版快照的異動摘要（人看的條列）。old 為 None＝新建。"""
    if not old:
        return ["新建"]
    msgs = []
    oh, nh = old.get("header", {}), new.get("header", {})
    for k, label in (("client", "客戶"), ("product", "產品"), ("format", "格式"),
                     ("start", "開始日"), ("end", "結束日"), ("budget", "預算"), ("final", "成交價")):
        a, b = from_jsonable(oh.get(k)), from_jsonable(nh.get(k))
        if a != b:
            msgs.append(f"{label}：{a} → {b}")
    if len(old.get("waves", [])) != len(new.get("waves", [])):
        msgs.append(f"波段數：{len(old.get('waves', []))} → {len(new.get('waves', []))}")
    ot, nt = _wave_totals(old), _wave_totals(new)
    for k in sorted(set(ot) | set(nt), key=lambda x: (x[0], x[1], x[2])):
        a, b = ot.get(k, [0, 0]), nt.get(k, [0, 0])
        if a != b:
            i, plat, sec = k
            wl = f"第{i + 1}波 " if len(new.get("waves", [])) > 1 else ""
            parts = []
            if a[0] != b[0]:
                parts.append(f"檔次 {a[0]:,} → {b[0]:,}")
            if a[1] != b[1]:
                parts.append(f"實收 {a[1]:,} → {b[1]:,}")
            msgs.append(f"{wl}{_PLAT_DISP.get(plat, plat)} {sec}秒：" + "，".join(parts))
    if not msgs:
        # 檔次總數相同但逐日分配不同
        if [r.get("schedule") for r in all_rows(old)] != [r.get("schedule") for r in all_rows(new)]:
            msgs.append("每日檔次分配調整")
        else:
            msgs.append(NO_CHANGE)
    return msgs


def has_changes(old, new):
    """目前畫面（new）相對已存版本（old）是否有尚未存檔的變更。"""
    return bool(old) and diff_summary(old, new) != [NO_CHANGE]


def next_version(old, new, user_name, now=None):
    """new 接續 old 的版本與異動紀錄（old 為 None 時從 v1 開始）。回傳 new（就地修改）。"""
    now = now or datetime.now()
    hist = list((old or {}).get("history", []))
    ver = int((old or {}).get("version", 0)) + 1
    hist.append({"v": ver, "at": now.strftime("%Y-%m-%d %H:%M"), "by": user_name or "",
                 "changes": diff_summary(old, new)})
    new["version"] = ver
    new["history"] = hist
    return new


# =============================================================================
# 投放參數詳情（details）文字與 cue/2 欄位
# =============================================================================
def details_text(snap, legacy=""):
    """舊版文字（含 [EXT]／[AGENCY_EXT]）＋ [CUESNAP] JSON。"""
    js = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
    return (legacy.rstrip() + "\n\n" if legacy else "") + SNAP_MARK + js


def parse_snapshot(details):
    if not details or SNAP_MARK not in details:
        return None
    try:
        snap = json.loads(details.split(SNAP_MARK, 1)[1].strip())
    except (ValueError, IndexError):
        return None
    return snap if isinstance(snap, dict) and snap.get("schema") else None


def legacy_part(details):
    """details 中 [CUESNAP] 之前的舊版文字。"""
    return (details or "").split(SNAP_MARK, 1)[0].rstrip()


def ragic_fields(snap, ragic_map, extra=None):
    """快照 → cue/2 欄位 {欄位ID: 值}（不含 details 與附件）。extra 為模式專屬欄位（覆蓋同 ID）。"""
    h = from_jsonable(snap.get("header", {}))
    s = summarize(snap)
    f = {}

    def put(key, val):
        fid = ragic_map.get(key) if not key.isdigit() else key
        if fid and val not in (None, ""):
            f[fid] = val.isoformat() if isinstance(val, date) else val

    put("client", h.get("client"))
    put("product", h.get("product"))
    put("tax_id", h.get("tax_id"))
    put("format", h.get("format"))
    put("sales", h.get("sales"))
    put("date_start", h.get("start"))
    put("date_end", h.get("end"))
    put("budget_raw", h.get("budget"))
    put("budget_fin", h.get("final", h.get("budget")))
    put("prod_cost", h.get("prod_cost"))
    put("platform", s["platform"])
    put("platform_detail", s["platform_detail"])
    put("total_spots", s["total_spots"])
    put("seconds_union", s["seconds"])
    put(CUE2_WAVES, s["waves"])
    put(CUE2_NET_TOTAL, s["net_total"])
    cust = snap.get("customer") or {}
    put(CUE2_CUSTOMER_ID, cust.get("編號"))
    f.update(extra or {})
    return f


# =============================================================================
# 送審／審核狀態（第 4 期）
# =============================================================================
DRAFT = "草稿"
PENDING = "待審"
REJECTED = "退回"
BOOKED = "已訂檔"
BOOKED_CHANGED = "已訂檔－有異動未送審"
PENDING_CHANGE = "異動待審"
REVIEWABLE = (PENDING, PENDING_CHANGE)


def status_of(snap):
    return (snap or {}).get("status") or DRAFT


def carry_over(old, new):
    """存檔時沿用前一版的送審／訂檔資訊並決定新狀態（就地修改 new，回傳 new）。
    改了內容：待審／退回 → 草稿（需重新送審）；已訂檔 → 已訂檔－有異動未送審。內容沒變則維持原狀態。"""
    if not old:
        new["status"] = DRAFT
        return new
    for k in ("booking", "review", "audit", "save_no", "owner", "ops", "cue_apply"):   # 編號／存檔人沿用第一次存檔
        if old.get(k):
            new[k] = old[k]
    st_old = status_of(old)
    changed = has_changes(old, new)
    if not changed:
        new["status"] = st_old
    elif old.get("booking"):
        new["status"] = BOOKED_CHANGED
    else:
        new["status"] = DRAFT
    return new


def mark_submitted(snap, user_name, params, now=None):
    """業務送審：已訂檔過的為「異動待審」，否則「待審」。params＝公司、類別、收款日、發票日等訂檔補充資料。"""
    now = now or datetime.now()
    snap["status"] = PENDING_CHANGE if snap.get("booking") else PENDING
    snap["review"] = {"submitted_by": user_name, "submitted_at": now.strftime("%Y-%m-%d %H:%M"),
                      "params": to_jsonable(params)}
    snap.setdefault("history", []).append({"v": snap.get("version", 0), "at": now.strftime("%Y-%m-%d %H:%M"),
                                           "by": user_name, "changes": [f"送審（{snap['status']}）"]})
    return snap


def mark_reviewed(snap, user_name, approved, *, reason="", booking=None, now=None):
    """主管審核結果：核准＝已訂檔（記 CUE號／各波訂檔 rid）；退回＝退回（記原因）。"""
    now = now or datetime.now()
    at = now.strftime("%Y-%m-%d %H:%M")
    rv = dict(snap.get("review") or {})
    rv.update({"reviewed_by": user_name, "reviewed_at": at, "result": "核准" if approved else "退回",
               "reason": reason})
    snap["review"] = rv
    if approved:
        snap["status"] = BOOKED
        if booking:
            snap["booking"] = booking
        msg = f"主管核准並訂檔（CUE號 {(booking or {}).get('cue_id', '')}）"
    else:
        snap["status"] = REJECTED
        msg = f"主管退回：{reason}"
    snap.setdefault("history", []).append({"v": snap.get("version", 0), "at": at, "by": user_name, "changes": [msg]})
    return snap


def mark_booked(snap, user_name, params, booking, now=None):
    """送出訂檔（第 5 期：送出即申請 CUE號＋建訂檔＝成交）。已訂檔過的為更新原訂檔。"""
    now = now or datetime.now()
    at = now.strftime("%Y-%m-%d %H:%M")
    updated = bool(snap.get("booking"))
    snap["status"] = BOOKED
    snap["booking"] = booking
    rv = dict(snap.get("review") or {})
    rv.update({"submitted_by": user_name, "submitted_at": at, "params": to_jsonable(params)})
    snap["review"] = rv
    snap["audit"] = {"result": AUDIT_PENDING, "booking_at": at}   # 每次送出（含更新原訂檔）都要主管重審
    msg = (f"更新原訂檔（CUE號 {booking.get('cue_id', '')}）" if updated
           else f"送出訂檔：CUE號 {booking.get('cue_id', '')}，成交")
    snap.setdefault("history", []).append({"v": snap.get("version", 0), "at": at, "by": user_name, "changes": [msg]})
    return snap


# =============================================================================
# 主管必審（2026-10-14：每份送出的訂檔都要主管審過，取代抽查）
# =============================================================================
AUDIT_PENDING = "待審"
AUDIT_OK = "核准"
AUDIT_REJECTED = "退回"


def audit_of(snap):
    """審核結果：未送訂檔＝""；已送訂檔但沒有審核紀錄（舊存檔）＝待審。"""
    snap = snap or {}
    if not snap.get("booking"):
        return ""
    return (snap.get("audit") or {}).get("result") or AUDIT_PENDING


def mark_audited(snap, user_name, approved, *, reason="", now=None):
    """主管審核送出的訂檔：核准＝維持已訂檔；退回＝狀態退回、不計成交（訂檔由營運在 Ragic 處理）。"""
    now = now or datetime.now()
    at = now.strftime("%Y-%m-%d %H:%M")
    au = dict(snap.get("audit") or {})
    au.update({"result": AUDIT_OK if approved else AUDIT_REJECTED, "by": user_name, "at": at, "reason": reason})
    snap["audit"] = au
    if approved:
        msg = "主管審核：核准"
    else:
        snap["status"] = REJECTED
        msg = f"主管審核：退回（{reason}）"
    snap.setdefault("history", []).append({"v": snap.get("version", 0), "at": at, "by": user_name, "changes": [msg]})
    return snap

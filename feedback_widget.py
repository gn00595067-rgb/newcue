"""
app 內建回饋按鈕：同事在 app 裡截圖 + 一句話 → 自動開 GitHub Issue（label: feedback）。
之後在 Claude Code 用 /triage 一次拉出來處理，LINE 就不用再轉貼截圖。

用法（放在 app.py 側欄或頁尾）：
    from feedback_widget import render_feedback
    render_feedback(app_name="newcue")

Secrets（Streamlit Cloud → Settings → Secrets）：
    GH_TOKEN = "github_pat_..."      # fine-grained token，只給該 repo 的 Issues:write + Contents:write
    GH_REPO  = "gn00595067-rgb/newcue"

截圖會 commit 到 repo 的 feedback/img/ 再貼進 issue（GitHub Issue API 不能直接上傳圖片）。
"""
import base64
import datetime as dt

import requests
import streamlit as st

_API = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"Bearer {st.secrets['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }


def _upload_image(repo: str, filename: str, data: bytes) -> str:
    """把截圖 commit 進 feedback/img/，回傳 raw URL。"""
    path = f"feedback/img/{filename}"
    r = requests.put(
        f"{_API}/repos/{repo}/contents/{path}",
        headers=_headers(),
        json={
            "message": f"回饋截圖 {filename}",
            "content": base64.b64encode(data).decode(),
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["content"]["download_url"]


def _create_issue(repo: str, title: str, body: str, labels: list[str]) -> str:
    r = requests.post(
        f"{_API}/repos/{repo}/issues",
        headers=_headers(),
        json={"title": title, "body": body, "labels": labels},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["html_url"]


def render_feedback(app_name: str, key: str = "fb"):
    with st.expander("🐞 回報問題 / 提建議"):
        with st.form(key=f"{key}_form", clear_on_submit=True):
            who = st.text_input("你的名字", key=f"{key}_who")
            kind = st.radio("類型", ["問題(bug)", "建議", "疑問"], horizontal=True, key=f"{key}_kind")
            note = st.text_area("發生什麼事？（一兩句就好）", key=f"{key}_note")
            img = st.file_uploader("截圖（可不附）", type=["png", "jpg", "jpeg"], key=f"{key}_img")
            ok = st.form_submit_button("送出")

        if not ok:
            return
        if not note.strip():
            st.warning("請至少寫一句發生什麼事")
            return

        try:
            repo = st.secrets["GH_REPO"]
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            body = f"**來自**：{who or '匿名'}\n**類型**：{kind}\n**app**：{app_name}\n\n{note}\n"
            if img is not None:
                ext = img.name.rsplit(".", 1)[-1].lower()
                url = _upload_image(repo, f"{app_name}-{stamp}.{ext}", img.getvalue())
                body += f"\n![截圖]({url})\n"
            title = f"[{app_name}] {kind}：{note.strip()[:40]}"
            link = _create_issue(repo, title, body, ["feedback", app_name])
            st.success("已送出，謝謝！")
            st.caption(link)
        except KeyError as e:
            st.error(f"缺少 secret：{e}")
        except requests.HTTPError as e:
            st.error(f"送出失敗：{e.response.status_code} {e.response.text[:200]}")

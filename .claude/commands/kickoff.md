---
description: 新專案起手式：策略分析 → user stories → MVP 範圍 → 骨架檔案。加 --lite 只切範圍不做分析
model: opus
---
新專案：$ARGUMENTS

若參數含 `--lite`，跳過步驟 1–2，直接做 3–5。

1. **策略分析**（一頁以內，寫入 `docs/specs/00-strategy.md`）
   - 目標使用者是誰、現在怎麼做這件事、痛點
   - 做完的成功指標（同事看得到的，例如「每週省 2 小時」）
   - 明確不做的事
2. **User stories**（寫入 `docs/specs/01-user-stories.md`）
   - 格式「身為 <角色>，我要 <做什麼>，好讓 <為什麼>」，每條標 P0/P1/P2
3. **資料與畫面**（寫入 `docs/specs/02-data-and-screens.md`）
   - 資料來源、核心資料表、畫面清單（一畫面一行）
4. **MVP 範圍**：只取 P0，最多 3 個功能，其餘列入「第二版」
5. **建骨架**：填好 `CLAUDE.md` 的「一句話／架構速覽」；在 `docs/WORKLOG.md` 追加「專案啟動」；`docs/DECISIONS.md` 記下 MVP 範圍切分的理由

需求資訊不足的地方，一次把問題列給我，不要自己假設。
全部完成後問我：「要開始實作 P0 第一項嗎？」

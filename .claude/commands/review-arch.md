---
description: 高階模型做整體架構審查（唯讀），取代打包丟網頁分析
allowed-tools: Read, Glob, Grep, Bash(git log:*), Bash(pytest:*), Write
model: opus
---
審查焦點：$ARGUMENTS（空白則做整體審查）

以資深架構師身分審查本 repo，**不改任何程式碼**：
1. 先讀 `CLAUDE.md`、`docs/specs/`、`docs/DECISIONS.md`，理解意圖與已知限制。
2. 看程式結構、資料流、外部依賴、測試覆蓋。
3. 輸出到 `docs/reviews/<今天日期>.md`：
   - 一段總評（這個 codebase 現在健康嗎）
   - 最值得先修的 3 件事（各附：問題、為什麼重要、建議做法、預估改動大小）
   - 可以不管的事（避免我過度優化）
   - 對照 CLAUDE.md 的地雷，有沒有新的風險
4. 摘要三行給我。

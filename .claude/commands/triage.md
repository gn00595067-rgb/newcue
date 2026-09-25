---
description: 拉出所有未處理回饋，排優先順序，一次處理一條
allowed-tools: Read, Glob, Grep, Bash(gh issue:*)
---
1. 讀 `docs/feedback/*.md` 中所有 `- [ ]` 未勾選項目。
2. 若專案有設 GitHub Issues 回饋（`gh issue list --label feedback --state open`），一併列入。
3. 依「嚴重度 → 影響人數 → 改動大小」排序，列成表格給我。
4. 問我從哪一條開始。處理完一條就把該項改成 `- [x]` 並在後面加上處理日期，或 `gh issue close`。
額外篩選：$ARGUMENTS

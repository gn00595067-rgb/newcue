---
description: 收工：寫 WORKLOG、更新「下次續做」、提示是否 commit
allowed-tools: Read, Edit, Write, Bash(git status:*), Bash(git diff:*), Bash(git log:*)
model: sonnet
---
1. 看 `git status` 與 `git diff --stat`，對照這個 session 做了什麼。
2. 在 `docs/WORKLOG.md` 追加一條：`- <今天> ｜ 做了什麼 ｜ 為什麼 ｜ 下一步`（給人看的白話，一行）。
3. 若有「選 A 不選 B」的判斷還沒記，補進 `docs/DECISIONS.md`。
4. 更新 `CLAUDE.md` 的「下次續做」段落（取代舊內容，不要堆積）。
5. 若有新踩的坑，加進 `CLAUDE.md` 的「地雷」。
6. 最後告訴我：有沒有未 commit 的改動、建議的 commit message（寫為什麼）。不要自己 commit。
補充：$ARGUMENTS

---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up.
argument-hint: "What will the next session be used for?"
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work.

## Save location

First, check whether this is a hackathon repo by running:

```bash
git tag
```

- If **no submission tags exist** (`day1-complete`, `day2-complete`) → today is Day 1. Save to `.hackathon/day1-summary.md`.
- If **`day1-complete` exists** but not `day2-complete` → today is Day 2. Save to `.hackathon/day2-summary.md`.
- If **neither condition applies** (not a hackathon repo) → save to the temporary directory of the user's OS.

Always save to the determined path — do not ask the user where to save.

## Content

Include a "suggested skills" section in the document, which suggests skills that the agent should invoke.

Do not duplicate content already captured in other artifacts (PRDs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.

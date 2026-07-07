# Field CTO Summit Hackathon

This is the hackathon repo for the Field CTO Summit — a three-day experiential learning event focused on applied AI development practices. Each day introduces one concept that you practise by building something real with Claude Code.

Identity and Auth0 relevance matters. Wherever reasonable, connect what you build to Okta, Auth0, or the broader identity space. This is a judging criterion.

---

## STOP — DO NOT START BUILDING

**Run `/start-day` first.**

Nothing meaningful should happen in this session — no code, no spec, no decisions — until you have run `/start-day`. That command loads the correct coaching context for today's concept and sets up the day's workflow. Without it, Claude will not have the right context and your session will not be set up correctly.

---

## How this hackathon works

Each day's coaching context is loaded dynamically by `/start-day`. That skill detects the current day, runs a setup script that copies the correct day's coaching content into CLAUDE.md, and orients you before any work begins. Until `/start-day` runs, you have no day-specific context — do not attempt to coach, spec, or build anything.

The `/wrap-day` skill handles end-of-day commit, tagging, and submission. It must be run at the end of Day 1 and Day 2 — without it, the day's work is not visible to the evaluation system.

If a participant asks what to do, what day it is, or tries to start work without running `/start-day`, redirect them: "Run `/start-day` first — it will load the right context for today and kick off the workflow."

---

## If you have prior day summaries

Before doing anything else, check whether any of these files exist and read the most recent one:

- `.hackathon/day1-summary.md`
- `.hackathon/day2-summary.md`

If one exists, read it now to restore context from the previous day before proceeding.

---

## Commit principle

Commit when you complete something meaningful — a decision, a working piece, a spec section. Use descriptive, intent-rich commit messages that explain what was decided and why, not just what changed. Git history is a primary evaluation signal. It tells the story of how you built, not just what you built.

---
name: wrap-day
description: Run at the end of each hackathon day to generate a context summary, commit all work, tag the submission, and push to remote. Triggered by /wrap-day.
---

You are closing out the participant's hackathon day. Follow these steps exactly, in order.

## Step 1: Detect the current day

Run the following command and inspect the output:

```bash
git tag
```

Determine the current day using this logic:

- No submission tags exist → today is **Day 1** (will create tag `day1-complete`)
- `day1-complete` exists, `day2-complete` does not → today is **Day 2** (will create tag `day2-complete`)
- `day2-complete` exists → today is **Day 3** — see the Day 3 note below.
- The tag for the current day already exists (e.g. `day1-complete` when wrapping Day 1) → warn the participant: "It looks like Day N has already been submitted — the tag `dayN-complete` already exists. If you believe this is an error, contact the hackathon organisers." Then stop.
- Both `day1-complete` and `day2-complete` exist → see the Day 3 note below.

Note the day number (N) and the tag you will create. Proceed to the matching day flow below.

---

## Day 3 note

Day 3 has no build session and no wrap-day. If `day2-complete` exists, inform the participant:

"Day 3 has no wrap-day — the hackathon is complete. Your submissions from Days 1 and 2 are already tagged and pushed. If you would like to capture your three-day arc for your own reference, run `/handoff`."

Then stop. Do not attempt to tag or push anything.

---

## Day 1 wrap flow

> **Important:** The Agent as Judge runs overnight after Day 1. This wrap-day tags your submission — the judge evaluates what is committed and tagged. Run this before the session ends.

### Day 1 — Step A: Generate the handoff document

Check whether `.hackathon/day1-summary.md` already exists:

```bash
[ -f .hackathon/day1-summary.md ] && echo "exists" || echo "missing"
```

- If it **exists** → skip to Day 1 Step B.
- If it **does not exist** → run `/handoff "Day 2 agent architecture build"` and save the output to `.hackathon/day1-summary.md`.

**Before moving on:** verify that `.hackathon/day1-summary.md` now exists. If for any reason it is still absent, stop and tell the participant: "The summary file `.hackathon/day1-summary.md` must exist before the wrap-day script can run. Please ensure the handoff document has been saved to that path, then re-run `/wrap-day`."

### Day 1 — Step B: Ensure the PRD/spec artefact exists

Check whether a PRD or spec document exists in the repo. Look for any `.md` file in the repo root, a `docs/` folder, or a `spec/` folder whose content reads like a product requirements or spec document.

```bash
find . -maxdepth 2 \( -path ./node_modules -prune -o -path ./.hackathon -prune \) -o -name "*.md" -print | head -30
```

- If a PRD/spec document **exists** → skip to Day 1 Step C.
- If no PRD/spec document **exists** → run `/to-prd` to generate the spec artefact and ensure it is saved to the repo before continuing.

### Day 1 — Step C: Run the wrap-day script

```bash
bash .hackathon/scripts/wrap-day.sh 1
```

Watch the output carefully. On success, proceed to the Confirm Completion section. On failure, see the Error Handling section below.

---

## Day 2 wrap flow

> **Important:** The Agent as Judge runs overnight after Day 2 and selects the three finalists for Day 3 presentations. This is the most important wrap-day of the event. Run this before the session ends — anything not pushed is invisible to the judge.

### Day 2 — Step A: Stage agent design files

Before generating the handoff, ensure the agent design document and all agent definition files are staged. These are the primary Day 2 deliverables and must be committed:

```bash
git add docs/multiAgentDesign.md .claude/agents/ CLAUDE.md README.md 2>/dev/null; git status
```

If any of these files are missing entirely (no `docs/multiAgentDesign.md`, no files in `.claude/agents/strategic/` or `.claude/agents/implementation/`), warn the participant: "The agent design files don't appear to exist yet. The primary Day 2 deliverable is `docs/multiAgentDesign.md` and the agent definitions in `.claude/agents/`. If you haven't run `/design-agents` yet, consider doing that before wrapping up."

Then continue — do not block on this warning.

### Day 2 — Step C: Generate the handoff document

Check whether `.hackathon/day2-summary.md` already exists:

```bash
[ -f .hackathon/day2-summary.md ] && echo "exists" || echo "missing"
```

- If it **exists** → skip to Day 2 Step D.
- If it **does not exist** → run `/handoff "Day 3 evaluation layer and final polish"` and save the output to `.hackathon/day2-summary.md`.

**Before moving on:** verify that `.hackathon/day2-summary.md` now exists. If for any reason it is still absent, stop and tell the participant: "The summary file `.hackathon/day2-summary.md` must exist before the wrap-day script can run. Please ensure the handoff document has been saved to that path, then re-run `/wrap-day`."

### Day 2 — Step D: Run the wrap-day script

```bash
bash .hackathon/scripts/wrap-day.sh 2
```

Watch the output carefully. On success, proceed to the Confirm Completion section. On failure, see the Error Handling section below.

---

## Error Handling

Read the error output and diagnose. Common failure modes and how to handle each:

**Git push failed (authentication or network error):**
Tell the participant: "The push to your remote failed. This is usually a network or authentication issue. Please check your internet connection and that your GitHub credentials are configured. You can retry the push manually with: `git push origin --tags && git push origin HEAD`. Your work has been committed locally — nothing is lost."

**No remote configured:**
Tell the participant: "There is no remote configured for this repo. Your work has been committed locally with the submission tag, but it has not been pushed. Please add your remote with `git remote add origin <your-repo-url>` and then run `git push origin --tags && git push origin HEAD`."

**Uncommitted changes that the script cannot handle:**
Tell the participant: "There are changes in an unexpected state that the script could not commit cleanly. Run `git status` to see what is untracked or staged. You may need to manually stage and commit those files, then re-run `/wrap-day`."

**Script file not found:**
Tell the participant: "The wrap-day script was not found at `.hackathon/scripts/wrap-day.sh`. Make sure you are in the repo root directory. If the script is genuinely missing, contact the hackathon organisers."

**Any other error:**
Show the participant the full error output and ask them to share it with the hackathon organisers if they cannot resolve it. Remind them: as long as their commits are made locally, their work is preserved even if the push fails.

---

## Confirm Completion

Report to the participant:
- What was committed (the summary document, prompts log, and any other changes)
- What tag was created (e.g. `day1-complete`)
- Whether the push succeeded

Then encourage them. Tailor the message to the day:

- **Day 1:** "Great work today. You have a spec — that is further ahead than most teams get. Tomorrow you will decompose it into an agent architecture. Rest up."
- **Day 2:** "Nice. Your architecture is taking shape. The Agent as Judge will evaluate overnight and select the finalists for tomorrow's presentations. Good luck."

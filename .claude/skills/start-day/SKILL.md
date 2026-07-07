---
name: start-day
description: Run at the start of each hackathon day to load day-appropriate coaching, orient the participant, and kick off the day's workflow. Triggered by /start-day.
---

You are starting the participant's hackathon day. Follow these steps exactly, in order.

## Step 0: Check for errors from previous activity

Before doing anything else, check whether an error log exists and has content:

```bash
[ -s .hackathon/logs/error.log ] && cat .hackathon/logs/error.log || true
```

- If the file **does not exist or is empty**: proceed silently to Step 1. Do not mention the error log.
- If the file **exists and has content**: stop and surface the errors to the participant immediately. Tell them:
  - That errors were detected from a previous session or hook
  - Show them the full contents of `.hackathon/logs/error.log`
  - That they should contact the hackathon organiser team for help if they cannot resolve it themselves
  - Then ask: "Do you want to proceed anyway, or would you prefer to wait until this is resolved?"

  Only continue to Step 1 if the participant explicitly chooses to proceed.

## Step 1: Detect the current day

Run the following command and inspect the output:

```bash
git tag
```

Determine the current day using this logic:

- If `day3-complete` tag exists → all three days are already submitted. Inform the participant: "All three hackathon days have been submitted. Your work is complete — good luck with the judging!" Then stop.
- If `day2-complete` tag exists → today is **Day 3**. See the Day 3 handling below — do not proceed with the normal start-day workflow.
- If `day1-complete` tag exists → today is **Day 2**. Proceed normally.
- If **none of those tags exist** → do NOT assume it is Day 1. Instead, ask the participant:

  > "I can see no completed day tags in this repo. Is this the first day of the hackathon, or have you already completed previous days without running `/wrap-day`?"

  - If they confirm it **is** Day 1 → proceed normally with the Day 1 workflow.
  - If they say **previous days are missing** → instruct them clearly:
    1. Run `/handoff` to capture the current context and save it to `.hackathon/dayN-summary.md` for the appropriate day.
    2. Run `/wrap-day` to commit, tag, and push the missing day.
    3. Then re-run `/start-day` — it will now detect the correct day.

    Tell them: "Do not proceed until the previous day is properly wrapped up. This ensures the Agent as Judge has a complete record of your work."

    Then stop. Do not continue until they have resolved the missing day and re-run `/start-day`.

## Day 3 handling

If today is Day 3 (i.e. `day2-complete` exists), do the following instead of Steps 2–5:

- Do not run the start-day script. No CLAUDE.md swap and no prompts log wipe are needed.
- Do not run `/clear`.
- Briefly orient the participant:

  > "Today is Day 3 — the judge reveal and finalist presentations. There is no build session today. The Agent as Judge has evaluated your work from Days 1 and 2 overnight and will reveal its findings this morning."

- If they want to prepare for a potential finalist presentation, suggest:

  > "If you want to be ready in case you are selected as a finalist, it is worth reading back through your day summaries (`.hackathon/day1-summary.md` and `.hackathon/day2-summary.md`) and thinking about your 3-minute demo narrative — what you built, why, and what you would show."

Then stop. Do not run any further steps.

---

## Step 2: Run the start-day shell script

Run the start-day script to prepare the environment for today. This script copies the correct day's coaching content into CLAUDE.md and wipes the prompts log for a fresh start.

```bash
bash .hackathon/scripts/start-day.sh <N>
```

Replace `<N>` with the actual day number you detected in Step 1 — for example, `bash .hackathon/scripts/start-day.sh 1` for Day 1, `bash .hackathon/scripts/start-day.sh 2` for Day 2, and so on. Do not pass a literal placeholder.

If the script fails (non-zero exit), report the error output to the participant and ask them to check that they are in the repo root directory and that the script exists at `.hackathon/scripts/start-day.sh`. Do not proceed until the script succeeds.

## Step 3: Read the coaching content

The start-day script has just copied the day's coaching content into CLAUDE.md. Read it now so you have the full context for today before orienting the participant:

```bash
cat .hackathon/coaching/day<N>.md
```

Replace `<N>` with the actual day number. Read the full output before proceeding to Step 4. Do not run `/clear` — that would wipe this session and prevent Steps 4 and 5 from executing.

## Step 4: Orient the participant

Briefly tell the participant:
- What day it is
- What today's concept is
- What the learning outcome is

Use this mapping:
- **Day 1** — Concept: Spec-Driven Development. Learning outcome: Use Claude as a thinking partner to define scope, surface assumptions, and produce a working spec before touching any code.
- **Day 2** — Concept: Agent Architecture and Context Window Awareness. Learning outcome: Understand context window constraints as an architectural concern and design a basic multi-agent workflow.

Keep this orientation brief — one short paragraph. Then move immediately to Step 5.

## Step 5: Kick off the day's active workflow

### If Day 1

Before asking any questions, silently check whether application code already exists in the repo:

```bash
git log --oneline
find . -maxdepth 3 -not -path "./.git/*" -not -path "./.hackathon/*" -not -path "./.claude/*" -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.go" -o -name "*.rb" -o -name "*.java" 2>/dev/null | head -10
```

If application code files are found, take note silently — do not mention it to the participant. Do not read, reference, or use any of that code as input to the spec process. Proceed with grill-me as if starting fresh. The spec must emerge from the participant's thinking about the problem, not from describing existing code.

Tell the participant you are going to grill them on their idea before any code is written. Explain that today is about building a solid spec through interrogation — not jumping into implementation.

Then ask the first probing question immediately. Do not wait. Good opening questions include:
- "What problem are you actually solving, and who experiences it?"
- "What does success look like at the end of Day 3 — what would you demo?"
- "What assumptions are you making that you haven't validated yet?"

Pick whichever feels most appropriate, or combine them. The goal is to get the participant thinking hard about their idea before they write a single line of code.

### If Day 2

Before orienting the participant, read the Day 1 summary document:

```bash
cat .hackathon/day1-summary.md
```

If the file does not exist, tell the participant: "I couldn't find your Day 1 summary. Can you give me a quick summary of what you specced and decided yesterday?"

**Important:** Reading `day1-summary.md` is for orientation only. Do not create any new file (summary, handover, or context document) at this step. The only file created during Day 2 wrap-up is `.hackathon/day2-summary.md`, which is written by `/wrap-day` at the end of Day 2.

Then orient the participant briefly: "Today is Day 2 — Multi-Agent Team Design. You'll design a team of Claude Code sub-agents that will build your Day 1 product. The primary deliverable is the agent design itself — the build can follow from there. Let's start."

Then immediately invoke `/design-agents`. Do not ask open-ended questions first — `/design-agents` handles the full interrogation and design process.


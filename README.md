# Office of the Field CTO - Velocity 27 Summit Hackathon

A three-day experiential learning hackathon focused on applied AI development practices. Each day introduces one concept — Define → Architect → Present — that you experience by building something real with Claude Code. Builds should connect to Okta/Auth0/Identity wherever reasonable.

---

## Daily time context

| Day | Time | Focus |
|-----|------|-------|
| Day 1 | ~30 min | Spec-driven development + Getting on the same page |
| Day 2 | ~20 min | LLM Context Windows + Multi Agent architecture |
| Day 3 | ~20 min | Agent as Judge + finalist presentations + voting |

---

## Pre-work (complete before Day 1)

Complete all of these steps before the first session starts.

1. **Set up Claude Code** — follow the [Claude Code Onboarding guide](https://oktainc.atlassian.net/wiki/spaces/BTPE/pages/628296601) on Confluence. This covers installation, API key configuration, and editor setup.

2. **Create your hackathon repo** — once you are in the org, create a private repo inside `ofctoV27` using the official template:
   ```
   gh repo create ofctoV27/{YOUR_REPO_NAME} --template "ofctoV27/ofcto27_Hackathon" --private
   ```
   One repo per entry — solo or team. Pick a repo name that identifies you or your team.

3. **Clone your repo locally**:
   ```
   gh repo clone ofctoV27/{YOUR_REPO_NAME}
   ```

If you hit any setup issues, contact the event organisers before Day 1.

---

## Each day, in order

1. **Attend the day's concept intro** — 5 minutes at the start of each session. Don't skip it.
2. **Open your repo in your editor of choice** — VS Code or terminal, from the root of your cloned repo.
3. **Start your session** — run `/start-day` as your first message to Claude. This loads the day's coaching, sets up the context, and kicks things off.
4. **Hack** — work with Claude, answer its prompts, challenge it, brainstorm. This is the build session. Commit often!
5. **Wrap up** — when your time is up, run `/wrap-day`. This commits and submits everything. Day 1 and Day 2 only — not needed on Day 3.

### `/start-day`
Run this every morning before you do anything else. It loads the day's coaching context and kicks off the day's workflow. Nothing meaningful should happen before you run this — including writing code.

### `/wrap-day`
Run this at the end of Day 1 and Day 2. Not needed on Day 3.

It generates a summary of what you built and decided, commits everything including your session prompt log, tags your submission, and pushes. This is how your work gets submitted. If you don't run it, your day's work is not visible to the evaluation system.

---

## Expectations

**Identity relevance:** Wherever reasonable, connect your build to Okta, Auth0, or the identity space. This is a judging criterion. You do not need to force it, but you should look for the angle.

**Commit behaviour:** Commit frequently with meaningful messages. Describe what you decided and why, not just what changed as it tells the story of how you built, not just what you built. Short, vague commits aren't your friend.

**Prompt quality:** Your session prompts are logged automatically. How you interact with Claude — the quality of your questions, how you direct the work, how you iterate is key to this exercise.

---

## Getting help

For questions about the hackathon format, evaluation, or logistics: speak to the event organisers directly.

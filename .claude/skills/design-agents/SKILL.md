---
name: design-agents
description: Design a team of Claude Code sub-agents to help build a project. Uses a two-tier model (strategic vs implementation). Interrogates the problem one question at a time, proposes a team, gets confirmation, then creates agent definition files and design document.
---

Design a team of Claude Code sub-agents to help build this project. Follow these steps exactly.

## Step 1 — Gather context

Look for existing context in this order. Stop as soon as you have enough to proceed:
1. Any files passed or referenced in the conversation
2. Common spec/design locations: `docs/solution.md`, `docs/prd.md`, `docs/architecture.md`, `README.md`
3. Any summary files (e.g. `.hackathon/day1-summary.md` or similar)
4. If none found, ask one question: "What are we building? Give me a one-paragraph summary of the problem, the solution, and the key technical components."

Do NOT read or reference any application code — agent design decisions must come from the problem understanding, not from existing implementation.

## Step 2 — Interrogate the agent architecture

**Critical instruction: ask exactly ONE question at a time. Wait for the participant's answer before asking the next question. Do not list multiple questions together. Do not preview upcoming questions.**

Use the two-tier agent model as the frame for this interrogation:

- **Tier 1 — Strategic agents**: cross-cutting, big-picture roles that plan, sequence, and coordinate. They hold the full product vision and spot dependencies. They do NOT write code. Definitions live in `.claude/agents/strategic/`.
- **Tier 2 — Implementation agents**: focused doers that own a system layer (discipline agents) or deep expertise in one tool (technology specialist agents). They write code and take direction from Tier 1 or the main session. Definitions live in `.claude/agents/implementation/`.

Before asking any questions, share the following mental model with the participant:

---

"Before we design your team, let me share the mental model we'll use — it maps directly to how real software delivery teams are structured, because the same logic applies.

There are two tiers of agent:

**Tier 1 — Strategic.** These are your team leads: Product Owner, Architect, Project Manager. They hold the big picture, coordinate across boundaries, and spot dependencies. Critically, they do *not* write code — their job is to plan, sequence, and direct. Their context is wide but shallow: they need to understand the whole problem, but not the implementation details of any single piece.

**Tier 2 — Implementation.** These are your doers. There are two flavours: *discipline agents* who own a system layer end-to-end (Frontend, Backend, Data), and *technology specialists* who own deep expertise in one tool (Auth0, Stripe, a cloud provider). Their context is narrow but deep — they need to know their piece and its interfaces, and nothing more.

The reason this works is that each agent gets exactly the context it needs and nothing that would distract it. That's not just good practice — it's how you manage the context window as an architectural constraint.

Now let's design your team."

---

Then ask the following questions one at a time. For each, provide a recommended answer based on what you know so far, then wait for the participant's response before continuing.

---

**Question 1 — What Tier 1 strategic roles does this problem need?**

Think about who needs to hold the big picture. Every team needs someone who owns the "what" (user stories, success criteria), someone who owns the "how" (technical shape, integration points), and usually someone who sequences and assigns the work. Which of these apply here, and does your problem need any additional strategic roles?

Wait for answer. Then ask:

---

**Question 2 — What Tier 2 discipline agents does this problem need?**

Think about the system layers that need to be built. Common disciplines are Frontend, Backend, Data, and DevOps/Infra — but not every project needs all four. Which layers exist in your build, and which are significant enough to warrant a dedicated agent?

Wait for answer. Then ask:

---

**Question 3 — Are there any technology specialist agents needed?**

Think about specific tools or platforms where a generalist engineer would spend significant time googling. Examples: Auth0/Okta for identity, Stripe for payments, a specific cloud provider's managed services. A specialist agent owns deep expertise in one tool and gets consulted by discipline agents at the boundary of their knowledge. Does your build have any integrations that warrant a specialist?

Wait for answer. Then ask:

---

**Question 4 — What does each agent need to know — and NOT know?**

For each agent identified across both tiers: what context is essential for it to do its job? What would pollute its context and degrade its output? Context boundary decisions are architectural decisions — the discipline of keeping context narrow is what makes the multi-agent approach work.

Wait for answer. Then ask:

---

**Question 5 — What is the first task sequence?**

If you were to start building right now, what is the thinnest end-to-end slice — one complete path from requirement to working output — that would touch every agent role? Walk through which Tier 1 agent initiates, which Tier 2 agents pick up work, and what each produces. This proves the architecture is viable, not just theoretical.

---

Keep this interrogation tight. If the participant has clear answers, move on immediately. If they are running short on time (they say so, or more than 10 minutes have passed since starting), skip remaining questions, make reasonable assumptions based on the context gathered, and proceed to Step 3.

## Step 3 — Propose the agent team

Present a concise team proposal structured by tier:

```
Proposed agent team:

**Tier 1 — Strategic**
1. **[role-name]** — [one sentence: what it does, what it knows, what it produces]
2. **[role-name]** — ...

**Tier 2 — Implementation**
3. **[role-name]** (discipline) — [one sentence]
4. **[role-name]** (specialist) — [one sentence]

Coordinator: [who orchestrates — usually the main session]
First task sequence: [brief description of the tracer thread through the team]
```

Invite the participant to challenge any decision: "Does this decomposition make sense for your problem? Push back on any role that feels wrong or missing."

If the participant is running short on time, skip the challenge round and proceed directly to Step 4.

## Step 4 — Write the outputs

Once the team is confirmed (or time pressure forces auto-proceed), write all outputs in sequence.

### Output A: `docs/multiAgentDesign.md`

```markdown
# Multi-Agent Design

## Problem
[One paragraph: what is being built, what complexity makes a multi-agent approach valuable here]

## Agent Team

### Tier 1 — Strategic Agents

#### [Role Name]
**Purpose:** [what this agent does]
**Context it needs:** [what to pass when spawning it]
**Context it must NOT have:** [what to keep out to preserve focus]
**Produces:** [what it outputs]
**Why separate:** [the reasoning — what goes wrong if this role is merged with another]

[repeat for each Tier 1 agent]

### Tier 2 — Implementation Agents

#### [Role Name] (discipline / specialist)
**Purpose:** [what this agent does]
**Context it needs:** [what to pass when spawning it]
**Context it must NOT have:** [what to keep out to preserve focus]
**Produces:** [what it outputs]
**Why separate:** [the reasoning]

[repeat for each Tier 2 agent]

## Coordinator Role
[Who orchestrates — what the main session does vs delegates]

## Interfaces
[How agents hand off — what flows between them, including Tier 1 → Tier 2 direction]

## First Task Sequence
[The tracer thread: how a thin end-to-end slice flows through the team]

## Design Decisions
[Any non-obvious choices made and why — alternatives considered and rejected]
```

### Output B: Agent definition files — one file per agent

Tier 1 agents go in `.claude/agents/strategic/<role-name>.md`.
Tier 2 agents go in `.claude/agents/implementation/<role-name>.md`.

```markdown
---
name: role-name
description: 2-3 sentences — WHEN to invoke this agent, WHAT it knows, WHAT it produces. Written so the main session can make routing decisions without reading the full file.
---

## Role
[What this agent is responsible for — Tier 1 strategic or Tier 2 implementation/specialist]

## Context you will receive
[What the main session or a Tier 1 agent should pass when spawning this agent — be specific]

## Your constraints
[What you must NOT do — scope boundaries that keep this agent focused]

## Output contract
[What you produce — format, location, or handoff to next agent]

## Working style
[Any specific instructions for how this agent should operate]
```

### Output C: Update `CLAUDE.md`

Append an "Agent Team" section:

```markdown
## Agent Team

The following sub-agents are defined in `.claude/agents/`. Delegate implementation work to them — do not implement directly in the main session.

### Tier 1 — Strategic

| Agent | File | Purpose |
|---|---|---|
| [name] | `.claude/agents/strategic/[file].md` | [one-line purpose] |

### Tier 2 — Implementation

| Agent | File | Purpose |
|---|---|---|
| [name] | `.claude/agents/implementation/[file].md` | [one-line purpose] |
```

### Output D: Note in `README.md`

Add under an "## Agent Team" heading:

```markdown
## Agent Team

This project uses a two-tier team of Claude Code sub-agents to manage the build. See [`docs/multiAgentDesign.md`](docs/multiAgentDesign.md) for the design rationale and [`.claude/agents/`](.claude/agents/) for the agent definitions.
```

## Step 5 — Commit and confirm

After writing all files:
```bash
git add docs/multiAgentDesign.md .claude/agents/ CLAUDE.md README.md
git commit -m "feat(agents): add multi-agent team design and agent definitions"
git push
```

Tell the participant:

"Your agent team is designed, defined, and committed.

**Before building, I strongly recommend running `/wrap-day` now** to tag this agent design as your Day 2 submission. The design is what the Agent as Judge evaluates — locking it in now means it's safe regardless of what happens in the build phase. You can keep building after wrapping; anything pushed before midnight counts."

If they want to start building immediately, clarify how this works:

**Spawning agents happens here, in this session — not in new windows.** This session IS the orchestrator. You use the Agent tool to spawn sub-agents directly. Each agent runs with its own focused context based on its definition file. This is what `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` enables — genuine parallel agent execution, not separate Claude windows.

When ready to build:
1. Spawn the PM agent first — pass it `docs/multiAgentDesign.md` and ask it to break the first tracer bullet into sequenced sub-deliverables
2. Once the PM produces the task list, spawn Tier 2 agents in parallel for independent sub-deliverables
3. Review outputs, sequence the next wave, repeat
4. Never implement directly in this session — always delegate to the right agent

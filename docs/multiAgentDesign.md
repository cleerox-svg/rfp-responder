# Multi-Agent Design — NaughtRFP

## Problem

NaughtRFP is a fully working AI-powered RFP responder for Okta Pre-Sales SEs. The codebase spans five distinct layers — Flask backend, vanilla JS SPA, SQLite data layer, a 9-agent AI pipeline, and third-party integrations (Okta OIDC, LiteLLM proxy, MCP servers) — each with its own patterns, constraints, and domain knowledge. Building and improving this system with a single Claude Code session would cause context window bloat, attention degradation, and cross-layer confusion. A team of focused sub-agents — each holding exactly the context it needs — produces better output faster and makes parallel work genuinely possible.

**First task sequence for this team:** Since the code is already built, the team's first job is assessment not construction. Implementation agents assess their respective areas in parallel, the Architect synthesizes findings into a prioritized improvement plan, and the PM sequences implementation tasks back to the agents.

---

## Agent Team

### Tier 1 — Strategic Agents

#### Product Owner
**Purpose:** Holds the user stories, success criteria, and scope boundaries. The authoritative voice on what the product must do from a user perspective. Arbitrates scope decisions when implementation agents surface trade-offs.

**Context it needs:** `docs/prd.md`, `docs/solution.md`, the demo scenario, and the out-of-scope list.

**Context it must NOT have:** Application code, database schema, model names, deployment details. The PO reasons about user value — implementation details pollute that frame.

**Produces:** Acceptance criteria for features, scope rulings on edge cases, user story clarifications on demand.

**Why separate:** If the PO holds implementation context, it starts optimising for what's easy to build rather than what the user needs. Separation keeps product decisions honest.

---

#### Architect
**Purpose:** Owns the technical shape of the system — pipeline flow, API contracts, SQLite design, context window strategy, and integration seams. Synthesizes assessment reports from implementation agents into a prioritized improvement plan.

**Context it needs:** `docs/solution.md`, `docs/multiAgentDesign.md`, the agent pipeline diagram, API surface, DB schema overview, and all implementation agent assessment reports when synthesizing.

**Context it must NOT have:** UI component details, user stories, individual route implementations. The Architect reasons about structure and interfaces, not specifics.

**Produces:** API contracts, schema decisions, improvement prioritization, architectural rulings on cross-cutting concerns.

**Why separate:** Architectural decisions made inside an implementation agent get optimised for that agent's layer. The Architect sees the whole system and makes decisions that hold across layers.

---

#### Project Manager
**Purpose:** Sequences work, identifies parallelism opportunities, manages dependencies, and fans tasks to implementation agents. Takes the Architect's improvement plan and breaks it into independently-grabbable tasks.

**Context it needs:** `docs/multiAgentDesign.md`, the current backlog, the Architect's improvement plan, and agent availability.

**Context it must NOT have:** Implementation details, user stories, DB schema. The PM reasons about sequencing and dependencies, not content.

**Produces:** Sequenced task list with dependency map, parallel wave identification, agent assignments.

**Why separate:** Without a dedicated sequencer, the main session becomes a bottleneck — it has to reason about dependencies before every delegation. The PM offloads that reasoning entirely.

---

### Tier 2 — Implementation Agents

#### Backend Engineer (discipline)
**Purpose:** Owns `app.py` — all Flask routes, SSE streaming, multi-document upload, export handler, and the Okta auth stubs. Implements and improves backend logic within the API contracts the Architect defines.

**Context it needs:** API contracts from the Architect, `app.py` content, `export_handler.py`, Flask and SSE patterns, auth stub design.

**Context it must NOT have:** Frontend component structure, agent pipeline internals (`agents.py`), DB query implementation, LiteLLM/Okta specifics (Integration Specialist owns those boundaries).

**Produces:** Route implementations, SSE event schemas, export logic, auth route stubs.

**Why separate:** Flask route logic and AI pipeline logic have different change rates and different failure modes. Mixing them in one agent causes cross-contamination of concerns.

---

#### Frontend Engineer (discipline)
**Purpose:** Owns the full SPA — `static/app.js`, `templates/index.html`, `static/style.css`. All pages, routing, agent card UI, KB view, demo prep UI, settings page, and the Okta auth UI (domain/client ID fields, enable toggle).

**Context it needs:** API contracts (what endpoints exist and what they return), `app.js` and `index.html` content, the CSS depth token system, agent card data structure from `AGENTS_DATA`.

**Context it must NOT have:** Backend route implementation, DB schema, agent pipeline code, LiteLLM configuration. The frontend talks to the API — it doesn't need to know what's behind it.

**Produces:** UI components, page implementations, SPA routing updates, agent card enhancements.

**Why separate:** Frontend and backend have fundamentally different concerns. A single agent holding both starts making architectural trade-offs that serve neither layer well.

---

#### Data Engineer (discipline)
**Purpose:** Owns `db.py` — SQLite schema, FTS5 virtual tables, covering indexes, thread-local connection management, WAL mode configuration, and all query patterns. The authoritative source on data access.

**Context it needs:** `db.py` content, the schema (tables: rfps, rfp_documents, questions, knowledge_base, settings, token_usage, demo_plans), FTS5 constraints, WAL mode and thread-safety rules.

**Context it must NOT have:** Flask routes, frontend code, agent pipeline logic. Data access patterns should be reasoned about independently of who calls them.

**Produces:** Schema changes, new query methods, index recommendations, migration scripts, thread-safety rulings.

**Why separate:** SQLite with FTS5, WAL mode, and thread-local connections has non-obvious constraints. A generalist agent holding both data and application logic will make mistakes at the boundary.

---

#### AI Pipeline Engineer (discipline)
**Purpose:** Owns `agents.py` exclusively — all 9 agent classes, tool definitions (`SEARCH_KB_TOOL`, `SEARCH_WEB_TOOL`, `FLAG_REVIEW_TOOL`), model constants (`_MODEL`, `_MODEL_FAST`), the agentic tool loop in `_research_and_answer`, KB pre-fetch strategy, and parallel worker configuration.

**Context it needs:** `agents.py` content, model constants and their rationale, tool schemas, the KB search interface from `db.py`, the confidence threshold (60% POC / 80-90% production), `_ANSWER_WORKERS` setting.

**Context it must NOT have:** Flask routes, frontend code, auth configuration, DB schema details beyond the KB search interface.

**Produces:** Agent class improvements, tool definition updates, model assignment changes, agentic loop refinements, parallelism tuning.

**Why separate:** The agent pipeline is the most complex and highest-stakes component. Mixing it with backend or data concerns causes the most expensive errors.

---

#### Integration Specialist (specialist)
**Purpose:** Owns all third-party integration surfaces: Okta OIDC (Authorization Code + PKCE), LiteLLM proxy configuration (`llm.atko.ai`, SSL bypass, model naming), MCP server connections (Google Workspace, Slack, and future integrations), and the `.env` bootstrap pattern.

**Context it needs:** Auth route stubs in `app.py`, `.env.example`, LiteLLM proxy specifics, Okta OIDC flow, MCP tool surfaces and resource schemas, `httpx` SSL bypass pattern.

**Context it must NOT have:** Application business logic, DB schema, frontend components, agent pipeline internals.

**Produces:** Auth flow implementation, LiteLLM configuration guidance, MCP connection patterns, integration troubleshooting, `.env` variable additions for new integrations.

**Why separate:** Each integration has its own auth model, SDK patterns, and edge cases. A generalist wastes tokens re-learning these boundaries. The specialist holds that knowledge permanently.

---

## Coordinator Role

The **main session** is the orchestrator. It:
- Spawns Tier 1 agents to plan and synthesize
- Fans implementation agents out in parallel waves
- Reviews outputs and decides the next wave
- Never writes application code directly

The main session's context stays lean: it holds `docs/multiAgentDesign.md`, the current task state, and outputs from completed agents. It does not accumulate implementation details.

---

## Interfaces

### Assessment wave (first task sequence)
```
Main session
  ├─► Backend Engineer        ─┐
  ├─► Frontend Engineer        │  parallel — no cross-dependencies
  ├─► Data Engineer            │  each returns: findings + recommendations
  ├─► AI Pipeline Engineer    ─┘
  └─► Integration Specialist  ─┘
         ↓ (all reports collected)
  └─► Architect  ← receives all 5 reports
         ↓ produces: prioritized improvement plan
  └─► Project Manager  ← receives improvement plan
         ↓ produces: sequenced task list with parallel waves
  └─► Main session fans back to implementation agents
```

### Ongoing build loop
```
PM produces task list
  ├─► Tier 2 agents (independent tasks) — parallel
  │     each returns: completed code, test notes, open questions
  └─► Architect reviews cross-cutting decisions on demand
```

### Communication model
- Tier 1 agents direct via the main session (or directly with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`)
- Implementation agents escalate architecture questions to the Architect
- Implementation agents escalate user-value questions to the Product Owner
- Integration Specialist is consulted by Backend and AI Pipeline Engineers at their integration boundaries

---

## First Task Sequence

**Parallel wave 1 — Assessment** (spawn all simultaneously):
1. AI Pipeline Engineer → audit `agents.py`: model assignments, tool loop, parallelism, confidence thresholds
2. Backend Engineer → audit `app.py`: routes, SSE, auth stubs, export handler, env bootstrap
3. Data Engineer → audit `db.py`: schema completeness, FTS5 strategy, index coverage, thread-safety
4. Frontend Engineer → audit `app.js` + `index.html`: SPA completeness, agent card UI, model badges, settings
5. Integration Specialist → audit auth plumbing, LiteLLM config, `.env.example`, MCP readiness

**Sequential — Synthesis:**
6. Architect receives all 5 reports → produces prioritized improvement plan
7. Project Manager receives improvement plan → sequences tasks, identifies next parallel wave, assigns agents

**Parallel wave 2 — Implementation** (tasks with no inter-dependencies run simultaneously)

---

## Design Decisions

**Why an AI Pipeline Engineer as a separate discipline:** `agents.py` is ~1,100 lines containing the most complex and highest-stakes logic in the system. Giving this its own agent means it always arrives with full, uncontaminated focus on the pipeline.

**Why Integration Specialist rather than Okta Specialist:** The integration surface will grow — Google Workspace, Slack, Salesforce MCP, and Highspot are all planned. Scoping to the integration pattern (not the specific tool) makes this agent durable as new integrations are added.

**Why assessment before construction:** The code exists and largely works. Assessment wave → Architect synthesis → PM sequencing means improvements are prioritized by impact, not by which agent happened to notice something first.

**Why the PM is Tier 1 not Tier 2:** Sequencing and dependency management requires full visibility across all workstreams. Tier 1 placement gives the PM the wide-but-shallow context it actually needs without burdening it with implementation details.

# PRD — NaughtRFP: AI-Powered RFP Responder for Okta Pre-Sales SEs

## Problem Statement

Okta Pre-Sales Solutions Engineers spend 8–40 hours per RFP manually reading, assessing, researching, and populating security and technical questionnaires. Responses are inconsistent across team members, knowledge from past RFPs is siloed in individual documents, and demo preparation is disconnected from the RFP analysis and starts from scratch every time. This time cost directly limits the number of deals an SE can run in parallel and introduces quality risk on every submission.

## Solution

NaughtRFP is a multi-agent AI platform purpose-built for Okta Pre-Sales SEs. It accepts RFP files, runs a coordinated pipeline of specialised AI agents to parse structure, assess fit against Okta's product portfolio, auto-answer requirements from a layered knowledge base and live Okta web sources, and flags uncertain answers for human review rather than hallucinating. Once the SE approves the responses, the platform exports the completed file in the original format and generates a structured demo plan tied to what the customer actually asked about. Every completed RFP is ingested back into the knowledge base, so the system compounds in quality over time.

The platform is explicitly built for the Okta identity and security sales motion. The knowledge base is seeded from Okta's own SIG Core 2024 pre-approved security responses and Okta product Q&A, grounding every answer in what Okta actually offers.

## User Stories

1. As an Okta Pre-Sales SE, I want to upload a CSV or XLSX RFP file, so that the system can begin processing it without manual data entry.
2. As an Okta Pre-Sales SE, I want to upload multiple files under a single RFP project, so that I can handle multi-document RFPs as one unit.
3. As an Okta Pre-Sales SE, I want the system to automatically detect which columns contain requirements, question IDs, and response fields, so that I don't have to map the file structure manually.
4. As an Okta Pre-Sales SE, I want to see a live agent activity feed while the pipeline runs, so that I can trust the system is working and understand what each agent is doing.
5. As an Okta Pre-Sales SE, I want the system to identify the customer, their industry, and the RFP scope automatically from the file content, so that the context is set without me having to enter it.
6. As an Okta Pre-Sales SE, I want each requirement to be categorised by Okta product area and risk level, so that I can understand the shape of the RFP at a glance.
7. As an Okta Pre-Sales SE, I want the system to auto-answer as many requirements as possible from the knowledge base, so that I only have to focus on the ones that need human judgment.
8. As an Okta Pre-Sales SE, I want the system to search Okta's public documentation and trust portal when the knowledge base doesn't have sufficient context, so that answers are grounded in current Okta information.
9. As an Okta Pre-Sales SE, I want each AI-generated answer to include a confidence score, so that I know how much to trust it before approving.
10. As an Okta Pre-Sales SE, I want each answer to cite its source (KB entry or web page), so that I can verify the answer before submitting it to the customer.
11. As an Okta Pre-Sales SE, I want each answer to be tagged with the relevant Okta products, so that I understand which parts of the portfolio are implicated.
12. As an Okta Pre-Sales SE, I want answers to use standard vendor response codes (F, P, C, NE, N), so that the export matches what customers expect in an RFP response.
13. As an Okta Pre-Sales SE, I want uncertain or low-confidence answers to be flagged for my review rather than submitted automatically, so that I never send a hallucinated or incorrect response to a customer.
14. As an Okta Pre-Sales SE, I want to see all flagged questions in a single Human Review view, so that I can work through them efficiently without scanning the full requirement list.
15. As an Okta Pre-Sales SE, I want to edit flagged answers inline with a response code picker and free-text field, so that I can correct or complete them without leaving the review view.
16. As an Okta Pre-Sales SE, I want to approve a flagged answer as-is, so that I can confirm the AI's response is acceptable without retyping it.
17. As an Okta Pre-Sales SE, I want to re-run the AI on an individual flagged question, so that I can get a fresh attempt after changing context or after a KB update.
18. As an Okta Pre-Sales SE, I want to see an overall fit score and risk score for the RFP, so that I can quickly assess whether this is a strong deal before investing more time.
19. As an Okta Pre-Sales SE, I want to filter the questions view by category or by "Needs Review" status, so that I can navigate large RFPs efficiently.
20. As an Okta Pre-Sales SE, I want to export the completed RFP in the same format it was uploaded (CSV or XLSX), so that I can send it directly to the customer without reformatting.
21. As an Okta Pre-Sales SE, I want the exported file to have colour-coded response codes, so that the output is visually clear and professional.
22. As an Okta Pre-Sales SE, I want internal citations and confidence notes to be stripped from the export, so that only the vendor-facing content is visible to the customer.
23. As an Okta Pre-Sales SE, I want to generate a demo plan from a completed RFP with a single button click, so that my demo preparation is directly tied to what the customer asked about.
24. As an Okta Pre-Sales SE, I want the demo plan to include ordered sections with demo steps, talking points, and differentiators, so that I have a ready-to-use script rather than blank notes.
25. As an Okta Pre-Sales SE, I want the demo plan to flag areas where the RFP had uncertain answers, so that I know what to prepare to address verbally in the demo.
26. As an Okta Pre-Sales SE, I want to confirm a demo plan to save it to the Demo Library, so that my team can reuse it for similar deals.
27. As an Okta Pre-Sales SE, I want to browse the Demo Library, so that I can find and reuse demo plans from past deals without starting from scratch.
28. As an Okta Pre-Sales SE, I want to ingest a completed RFP into the knowledge base, so that the platform improves for future RFPs of the same type.
29. As an Okta Pre-Sales SE, I want to search the knowledge base by keyword or AI semantic search, so that I can find relevant Q&A pairs directly when I need them.
30. As an Okta Pre-Sales SE, I want to see a BLUF (Bottom Line Up Front) summary when I run an AI KB search, so that I get a synthesised answer rather than a raw list of entries.
31. As an Okta Pre-Sales SE, I want the knowledge base to be pre-seeded with Okta's official SIG Core 2024 responses, so that the system is immediately useful without requiring manual population.
32. As an Okta Pre-Sales SE, I want to configure my API key and LiteLLM proxy URL in a settings screen, so that the platform connects to Okta's internal LLM gateway without hardcoded credentials.
33. As an Okta Pre-Sales SE, I want to test my LiteLLM connection from the settings screen, so that I can verify setup before processing a real RFP.
34. As an Okta Pre-Sales SE, I want to see token usage and estimated spend, so that I can monitor AI costs during a session.

## Implementation Decisions

- **Agent pipeline:** 9 specialised agents run in sequence — Customer, Parser, Analysis, Research, Answer (parallel), Scoring, Review, KB Ingestion, Demo Prep. Each has a defined role and structured output passed to the next agent.
- **Answer Agent agentic loop:** The Answer Agent calls tools iteratively (search KB, search web, flag for review) before producing a final answer. It does not guess — if confidence is below threshold, it flags.
- **Confidence threshold:** POC uses 60% as the flag threshold. Production target is 80–90%, to be validated against a real SE review sample before hardcoding.
- **Parallelism:** The Answer Agent runs 6 workers simultaneously via ThreadPoolExecutor to process requirements in parallel.
- **KB pre-fetch:** The Research Agent bulk pre-fetches top KB matches for all questions before the parallel pool starts, eliminating per-question API round trips.
- **Knowledge base layers:** SIG Core 2024 seed (~615 entries) + hand-crafted Okta baseline Q&A (~25 entries) + past RFP ingestion (compounding). SQLite FTS5 for search with multi-strategy fallback (phrase → prefix-AND → prefix-OR → LIKE).
- **Web search:** DuckDuckGo site-restricted to `okta.com` and `trust.okta.com`. Results summarised by Claude before injection. 1-hour in-memory page cache per run.
- **Live agent feed:** Server-Sent Events (SSE) stream agent status to the UI in real time during processing.
- **Export:** openpyxl for XLSX with colour-coded response codes. Internal citations and review notes stripped before export.
- **AI model:** `claude-sonnet-4-6` via Okta's internal LiteLLM proxy (`llm.atko.ai`). API key stored in SQLite, never hardcoded.
- **Backend:** Python + Flask. No build step.
- **Frontend:** Vanilla JS + HTML. No framework, no build step. Single-page app with collapsible sidebar.
- **Database:** SQLite with WAL mode, thread-local connections, covering indexes. Zero-install.

## Out of Scope

- Google Sheets or Google Docs ingestion
- Email draft generation for customer submissions
- SIG or certification file upload as direct KB sources
- Okta/Auth0 authentication on the app itself
- Multi-tenancy or role-based access control
- Mobile or responsive layout
- Confidence threshold above 60% (deferred to post-POC)

## Further Notes

- **Judging criterion — identity relevance:** NaughtRFP is explicitly an Okta identity sales tool. The KB is grounded in Okta's own approved responses, and the platform directly accelerates Okta's Pre-Sales motion. This is not incidental — it is the core use case.
- **Judging criterion — agentic AI:** The platform demonstrates genuine agentic behaviour: 9 specialised agents with defined roles, real tool use with mid-loop decision making, and appropriate refusal (flagging rather than hallucinating). The live agent feed makes this visible to judges.
- **Compounding value:** The KB ingestion loop means the platform gets better with every RFP processed. This is a structural differentiator over one-shot AI tools.
- **Confidence threshold note:** The 60% POC threshold will surface more flagged items than the production system would. This is intentional — better to over-flag in a demo than to show a hallucinated answer going through unchallenged.

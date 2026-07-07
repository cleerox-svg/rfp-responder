---
name: to-prd
description: Turn the current conversation context into a PRD and publish it to docs/prd.md. Use when user wants to create a PRD from the current context.
---

This skill takes the current conversation context and produces a PRD. Do NOT interview the user — just synthesise what you already know from the conversation.

Do NOT read or explore the codebase. The PRD must be derived entirely from the conversation — what was discussed, decided, and scoped. If code already exists in the repo, ignore it.

## Process

1. Synthesise the user stories, scope decisions, identity angle, and demo scenario from the conversation so far. If any of these are unclear, make a reasonable decision based on what has been discussed — do not ask follow-up questions.

2. Write the PRD using the template below.

3. Save the output as `docs/prd.md` in the repository. Always use this exact path — do not use a different filename.

<prd-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Implementation Decisions

A list of implementation decisions that were made if any. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

## Out of Scope

A description of the things that are out of scope for this PRD.

## Further Notes

Any further notes about the feature.

</prd-template>

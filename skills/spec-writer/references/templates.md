# Spec templates

Pick the template that matches the work. Keep every section, even when the answer is one line ("Non-goals: none beyond the defaults"). A missing section reads as "not thought about", and the executor fills it by guessing.

Text in `<angle brackets>` is to be replaced. The linter flags any left behind.

## Contents

1. Feature spec
2. Bug-fix spec
3. Refactor or migration spec
4. API spec (add to a feature spec)
5. Agent task brief (short form)
6. Keyword preamble (paste into any spec)

## 1. Feature spec

```markdown
# <Feature name>

Status: draft | ready | in progress | done
Owner: <who answers questions>
Executor: <AI agent / engineer / team>
Last updated: <YYYY-MM-DD>

<Keyword preamble, section 6>

## Summary
<Two or three sentences: what will exist after this ships, for whom, and why it matters now.>

## Background
<Facts the executor needs and can't infer: current behavior, who uses it, what prompted this, what was tried before. Link or quote; don't paraphrase numbers.>

## Goals
- G1. <outcome, measurable where possible>

## Non-goals
- <things a reasonable executor might do that are not wanted, each with a short reason>

## Definitions
| Term | Meaning |
|---|---|
| <term> | <one meaning, used consistently everywhere below> |

## Requirements

### Functional
- R1. <EARS-style requirement with MUST/SHOULD/MAY.> (why: <reason, if not self-evident>)

### Errors and edge cases
- R10. If <unwanted condition>, then <system> MUST <response>. Error shown: "<exact text>".
- Deliberately out of scope: <edge case> — <what happens instead>.

### Non-functional
- R20. Performance: <number, percentile, load, environment>.
- R21. Security and privacy: <specific rules: who may do what, what is logged, what is never logged>.
- R22. Accessibility: <standard and level, or specific behaviors>.
- R23. Compatibility: <browsers, versions, API consumers that must keep working>.

## Interfaces and data
<API shapes, UI states, schema changes, events. Use examples, each labeled normative or illustrative.>

## Implementation constraints
- Files and modules in scope: <paths>
- Do not modify: <paths or interfaces>, because <reason>
- Follow the pattern in: <path>
- Dependencies: <none new / allowed list>
- Executor's choice: <things that genuinely don't matter>

## Acceptance criteria
- AC1 (R1). Given <state>, when <action>, then <observable result>.
- AC-regression. <Existing behavior that must still work, and how to check it.>

## Verification
- `<command>` passes (currently passes on main).
- Manual: <exact steps and expected result>.

## Rollout
<Feature flag, migration or backfill order, backwards compatibility window, how to roll back.>

## Assumptions
- A1. <decision made without the owner's confirmation; owner may overrule>

## Open questions
- Q1. <question> — Owner: <name>. Default until answered: <assumption>.

## Execution rules
<For an AI executor: the block from agent-executors.md, adapted to this spec.>
```

## 2. Bug-fix spec

```markdown
# Fix: <symptom in one line>

<Keyword preamble>

## Observed
<What happens, with exact error text, logs, screenshots described. Frequency. Since when.>

## Expected
<What should happen instead, as observable behavior.>

## Reproduction
1. <step, with exact data>
2. ...
Environment: <version, browser, OS, config, data conditions>

## Known facts and suspects
<Root cause if known, with evidence. If not known: what has been ruled out.>

## Requirements
- R1. Find the root cause before changing code, and state it in the report with evidence (why: a symptom patch hides the bug and it returns elsewhere).
- R2. <The fixed behavior, as a testable statement.>
- R3. Add a test that fails before the fix and passes after it.

## Scope
- In scope: <paths>
- Non-goals: <related problems not to fix in this change, so the diff stays reviewable>

## Acceptance criteria
- AC1. The reproduction steps above produce the expected behavior.
- AC2. The new test fails on the parent commit and passes with the fix.
- AC3. `<test command>` passes.

## If blocked
<E.g.: if the root cause is in a third-party library, stop and report with a proposed workaround; don't patch the vendored code.>
```

## 3. Refactor or migration spec

The defining requirement of a refactor is that behavior doesn't change, so the spec is mostly about proving that.

```markdown
# Refactor: <what changes structurally>

<Keyword preamble>

## Motivation
<Why now, and what the new structure makes possible.>

## Invariants
- I1. <Observable behavior that MUST stay identical: outputs, API responses, stored data, performance bounds.>

## How invariance is proven
- <Characterization tests to write first, or golden-output comparisons, or replaying recorded traffic.>
- These checks MUST pass before and after each step.

## Steps
1. <Step that leaves the system working and deployable.>
2. ...
Each step is a separate commit (or PR) that passes the checks above.

## Data migration (if any)
- Expand: <add new structure alongside old>
- Migrate: <backfill, batch size, how progress is tracked, idempotent re-runs>
- Contract: <remove old structure only after all readers use the new one>
- Rollback: <how to undo each step>

## Non-goals
- No behavior changes, including "obvious" bug fixes found along the way: note them in the report instead (why: mixing fixes into a refactor makes regressions impossible to attribute).

## Acceptance criteria
- AC1. All invariant checks pass on the final commit.
- AC2. <Old structure X no longer referenced: `grep -r "<symbol>" src/` returns nothing.>
```

## 4. API spec (add to a feature spec)

~~~markdown
## API

### `POST /v1/<resource>`
Auth: <scheme and required permission>
Idempotency: <Idempotency-Key header honored for 24 h / not idempotent>
Rate limit: <N per minute per key; 429 with Retry-After>

Request (normative):
```json
{"name": "Oak shelf", "quantity": 4}
```

| Field | Type | Required | Rules |
|---|---|---|---|
| name | string | yes | 1–120 chars, trimmed |
| quantity | integer | yes | 1–10,000 |

Response 201 (normative):
```json
{"id": "itm_123", "name": "Oak shelf", "quantity": 4, "created_at": "2026-10-15T09:00:00Z"}
```

Errors:
| Status | Code | When | Message |
|---|---|---|---|
| 400 | `invalid_quantity` | quantity outside 1–10,000 | "Quantity must be between 1 and 10,000." |
| 409 | `duplicate_name` | name already exists in this workspace | "An item with this name already exists." |

Compatibility: <existing clients and fields that must keep working; versioning rule>
Pagination (list endpoints): <cursor-based, page size default and maximum, sort order and tie-breaker>
~~~

## 5. Agent task brief (short form)

For a well-understood task handed to a coding agent. It's still a spec: decisions, scope, done criteria, stop rules. It's just shorter.

```markdown
# Task: <imperative one-liner>

## Objective
<What will be true when this is done, and why it matters.>

## Context
<What the agent can't infer: relevant history, users, constraints. Key files: <paths>.>

## Requirements
- R1. <testable requirement>
- R2. ...

## Constraints
- Only modify: <paths>. (why: <reason>)
- Don't: <specific shortcut or out-of-scope change>. (why: <reason>)
- Follow: <existing pattern at path>.

## Done when
- [ ] <observable check>
- [ ] `<command>` passes.

## If something doesn't fit
- You may decide alone: <list>, using <default>.
- Stop and report instead of working around: <list of conditions>.

## Report back with
- What changed (files, summary)
- Verification run (commands and results)
- Deviations from this brief, and why
- Anything left open
```

## 6. Keyword preamble

Paste near the top of every spec:

```markdown
The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are used as in RFC 2119 and RFC 8174, and only when in capitals. MUST is required for acceptance. SHOULD is expected unless a stated exception applies; any deviation is reported with its reason. MAY is optional.
```

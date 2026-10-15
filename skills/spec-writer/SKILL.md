---
name: spec-writer
description: Writes and hardens implementation specs that an AI coding agent or an engineer can execute without guessing. Turns an idea, ticket, conversation or rough PRD into a directive spec with decisions instead of options, numbered testable requirements (MUST/SHOULD/MAY, EARS patterns), explicit non-goals and file scope, error and edge-case handling, concrete examples, acceptance criteria with verification commands, and rules for when the executor should stop and ask. Then runs adversarial passes and a linter for vague words, hedges, deferred decisions and missing sections. Use when the user asks to write, draft, tighten or review a spec, tech spec, feature spec, PRD, requirements doc, acceptance criteria, ticket, task brief, or instructions for Claude Code, Codex, Cursor or another agent to implement, or says a spec is too vague or an agent keeps building the wrong thing.
---

# Spec writer

A spec is a set of decisions handed to someone who wasn't in the room. Every sentence that can be read two ways is a decision passed to the executor, the person (or agent) with the least context. A human engineer might ask. An AI agent usually won't: it picks a plausible reading, silently, and may pick a different one on the next run. So the spec's job is to make the right implementation the only reasonable reading, and to make "done" something anyone can check.

Two words describe the target:

- **Directive**: decisions stated as decisions, in the imperative, one meaning per sentence, with no menu of options and no "ideally". Directive is not loud. It means clear, not capitalized. Where something genuinely doesn't matter, say so explicitly ("naming of internal helpers: executor's choice"); granting freedom on purpose is also a decision.
- **Robust**: the spec still produces the right result when things go wrong (bad input, failures, edge cases), when the executor reads it literally, and when reality contradicts it. That means unhappy paths, verification, and instructions for what to do when stuck.

## Principles

Each of these exists because of a specific way specs fail.

1. **Decide; don't offer.** "Use Redis or an in-memory cache" hands over an architecture decision. Pick one and give the reason in a clause. If you can't decide, put it under Open questions with a default ("Until answered, assume X"), so the work isn't blocked and the assumption is visible.
2. **Make requirements testable.** Each requirement has an ID, an actor, a trigger and an observable result. "The system handles duplicates gracefully" can't be tested. "R4: When a signup uses an email that already exists, the API MUST return 409 with error code `email_taken` and MUST NOT create a user" can. The EARS sentence patterns in [references/requirement-patterns.md](references/requirement-patterns.md) make this mechanical.
3. **Use the requirement keywords strictly.** MUST, MUST NOT, SHOULD, MAY (RFC 2119), in capitals, defined once at the top. Lowercase "should" in a requirement is the most common ambiguity in specs: some readers take it as mandatory and some as optional. Every SHOULD says when deviating is acceptable; if you can't name a case, it's a MUST.
4. **Quantify adjectives.** Fast, scalable, robust, secure, user-friendly, large, minimal: each needs a number or a definition (p95 under 200 ms at 50 requests per second; files up to 100 MB; passes the OWASP ASVS level 1 checks for input validation). The reference has a replacement table.
5. **Fence the scope.** Goals say what to build. Non-goals say what a reasonable executor might also do that you don't want: "no UI changes", "don't refactor the billing module", "no new dependencies". Agents in particular tend to over-deliver, by tidying neighboring code, adding features or "improving" interfaces. Non-goals stop that. Name the files and modules in scope, and the public interfaces that must not change.
6. **Ground every claim in the real system.** Name actual files, functions, tables and endpoints, and point at an existing pattern to copy ("follow `src/billing/invoices.py`"). Open them first: a wrong path or an invented function sends the executor on a hunt, or worse, makes it create the thing you thought existed. Mark what exists and what is new.
7. **Specify the unhappy paths.** Errors, empty states, limits, retries, partial failure, concurrency, permissions, time zones, Unicode. Go through [references/edge-cases.md](references/edge-cases.md) and write down the behavior for each one that applies. For the ones you deliberately skip, say so ("concurrent edits: out of scope, last write wins"); otherwise the executor can't tell "decided" from "forgot".
8. **Show examples.** A concrete input and its exact output, a sample payload, the exact error message. Examples are the least ambiguous part of any spec. Label each one as normative (must match exactly) or illustrative (shows the shape).
9. **Define done as checks.** Acceptance criteria, each mapped to requirements, each observable by a command or a specific manual step. Include regression criteria (what must keep working) and the exact verification commands (`pytest tests/billing`, `npm run typecheck`), after confirming those commands exist in the repo.
10. **Say what to do when reality disagrees.** The spec will be wrong somewhere. Tell the executor which decisions it may make alone (with a default), when to stop and ask, and what not to do as a workaround: "If R3 can't be met without changing the public API, stop and report. Don't change the API."
11. **One term, one meaning.** Define domain terms once. Never vary the name of a thing for style: a reader seeing "account", "workspace" and "organization" will assume three different things, and an agent will build three.
12. **Give the reason with the rule.** A one-line "why" after any requirement that isn't self-evident ("why: the nightly export reads this column"). Reasons let the executor handle cases you didn't foresee in the spirit you intended; bare rules only cover the cases you listed.
13. **Stay calm on the page.** No ALL-CAPS warnings, no "CRITICAL!!!", no repeating a rule in five places. Current models follow instructions closely; shouting makes them over-apply a rule to things it was never meant for. State each rule once, in its section, with its reason.
14. **Size it to one executor.** If a spec needs more than one focused working session, split it into milestones, each independently verifiable and leaving the system working, in dependency order.

## Workflow

### 1. Find the problem and the reader

Before writing anything, settle:
- **The problem**: what's wrong or missing today, for whom, and how you'll know it's fixed.
- **The executor**: an AI coding agent, an in-house engineer, a contractor? What context will it have? An agent starting fresh has none beyond the spec and the repo, so the spec carries everything else: the why, the users, the history, the constraints.
- **The spec type**: feature, bug fix, refactor or migration, API, or a short task brief for an agent. Each has a template in [references/templates.md](references/templates.md).

### 2. Investigate

If there's a codebase, read the relevant parts before writing: current behavior, the files involved, existing patterns, tests, and the commands used to build, test and lint. Collect facts, not impressions. A spec built on a wrong picture of the code is directive in the wrong direction.

### 3. Ask only the blocking questions

Ask the user only what would change the architecture, the scope or the definition of done. Batch the questions (at most about five) and attach your recommended default to each, so the user can answer "defaults are fine". Decide everything else yourself and list it under Assumptions, where the user can overrule it.

### 4. Draft from the template

Fill in the template for the type. Keep the sections even when short. An empty "Non-goals: none" is a statement; a missing section is a gap the executor fills by guessing.

### 5. Harden it

Run these passes in order. They're what makes the spec robust rather than merely tidy.

1. **Two-implementer test.** For each requirement: could two competent people build different things and both claim compliance? If so, tighten it, usually with a number, an example, or a named behavior for the edge case.
2. **Literal-executor test.** Read the spec as an agent that does exactly what's written and nothing more. What would be missing? Setup steps, data to seed, a migration, updating docs or config, where the new code goes.
3. **Shortcut test.** How could the acceptance criteria be passed without doing the real work? Hardcoding the test's expected values, skipping or deleting failing tests, mocking the thing under test, catching all exceptions, loosening validation, special-casing the example input. Close each realistic shortcut with a requirement or constraint (with its reason). [references/agent-executors.md](references/agent-executors.md) lists the common ones.
4. **Failure walk.** Go through the edge-case checklist for each input and external dependency.
5. **Consistency check.** Requirements against non-goals and constraints; numbers, names and IDs the same everywhere; every requirement covered by at least one acceptance criterion, and every criterion traceable to a requirement.
6. **Lint.** Run `python3 scripts/spec_lint.py spec.md`. It flags vague words, hedges, deferred decisions, lowercase "should", placeholders, shouting, missing sections, unnumbered requirements and acceptance criteria with nothing observable. Fix each finding or leave it on purpose (background prose can be looser than requirements).

### 6. Deliver

Write the spec as a markdown file (`specs/<short-name>.md`, or where the repo keeps them). Then tell the user, briefly:
- the assumptions you made that they should confirm
- the open questions that need an owner
- anything you couldn't verify (for example, a command you couldn't run)

## Reviewing an existing spec

When asked to review rather than write, run the linter and the hardening passes, then return the problems ranked by how likely they are to produce the wrong build: deferred decisions and untestable requirements first, wording last. Give each problem with a concrete rewrite. Rewrite the whole spec only if asked.

## Writing for an AI executor

Everything above applies with more force when the executor is an agent. In particular:
- Put the context it can't infer into the spec: who the users are, why the change matters, what was tried before.
- List files in scope and files not to touch.
- Give verification commands that exist and pass on the main branch today, so failures mean something.
- Say which decisions it may make alone and which need a question first.
- Name the shortcuts that would count as failure, with the reason.
- Say what its final report must contain: what changed, how it was verified (with command output), deviations from the spec and why, and open issues.

[references/agent-executors.md](references/agent-executors.md) has the failure modes and a reusable "execution rules" block to adapt for each spec.

## References

- [references/templates.md](references/templates.md): templates for feature, bug-fix, refactor or migration, API, and agent task-brief specs. Read before drafting.
- [references/requirement-patterns.md](references/requirement-patterns.md): EARS patterns, keyword rules, acceptance-criteria formats, the vague-to-precise table, and before/after examples.
- [references/edge-cases.md](references/edge-cases.md): the failure-walk checklist.
- [references/agent-executors.md](references/agent-executors.md): how agents go wrong on specs, and the clauses that prevent it.
- `scripts/spec_lint.py`: the linter. `--strict` treats warnings as errors; `--json` for machine output.

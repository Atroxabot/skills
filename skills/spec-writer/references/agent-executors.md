# Writing specs for AI executors

AI coding agents are capable, fast and literal. They rarely ask clarifying questions, they fill gaps with the most plausible guess, and they are strongly pulled toward making checks pass and declaring success. A spec for an agent has to anticipate that, without micromanaging the parts that don't matter.

## How agents go wrong, and the clause that prevents it

| Failure mode | What it looks like | Put in the spec |
|---|---|---|
| Silent assumption | Picks one reading of an ambiguous requirement and never mentions it | Decisions instead of options; "If a requirement is ambiguous, choose the reading closest to the stated goal and list the choice under Deviations in the report" |
| Gaming the checks | Hardcodes expected values, special-cases the test input, loosens an assertion, deletes or skips a failing test | "Don't modify existing tests unless a requirement says so; if one seems wrong, stop and report (why: tests encode behavior other people rely on)." "The implementation must work for inputs beyond the examples." |
| Mocking the thing under test | Tests pass because the real logic is replaced | "Tests for R1–R4 exercise the real `<module>`; mock only network and clock" |
| Swallowing errors | `try/except: pass`, broad catches, default values that hide failures | Specify error behavior per case; "Don't catch exceptions you can't handle meaningfully; let them surface" |
| Scope creep | Refactors neighbors, renames things, upgrades dependencies, adds features "while here" | Non-goals; "Only modify: <paths>"; "No new dependencies"; "Note other problems you see in the report instead of fixing them" |
| Interface drift | Changes a function signature or API response to make its job easier | "These interfaces must not change: <list>" with the reason |
| Inventing what isn't there | Calls a helper that doesn't exist, assumes a config key, guesses a path | Name real files and functions; "If something the spec refers to doesn't exist, stop and report; don't create a substitute" |
| Ignoring conventions | New code in a different style, structure or library than the rest | "Follow the pattern in <path>"; name the linter and formatter commands |
| Premature completion | Says "done" without running anything, or after the first green test | Verification commands in Done-when; "The report must include the commands run and their result" |
| Fixing the symptom | Adds a null check where the null shouldn't exist | For bugs: "Find and state the root cause before changing code" |
| Over-applying a rule | Treats a strongly worded rule as absolute, even where it obviously doesn't apply | Calm wording plus a reason, so the agent can tell where the rule's purpose ends |
| Under-delivering at the edges | Happy path done, docs, config, migrations and error states missing | List them as requirements or Done-when items |
| Thrashing when blocked | Tries workaround after workaround, each further from the spec | "If blocked after a reasonable attempt, stop and report what you tried" |

## Be directive about what matters, explicit about what doesn't

Over-specifying is its own failure: the agent follows a detailed implementation recipe even where it's worse than the obvious approach, and long specs bury the important rules. So:
- Fix the **what**, the **interfaces**, the **constraints** and the **done criteria** firmly.
- Fix the **how** only where you've made a real decision (a library, a pattern, an algorithm that matters).
- Say "executor's choice" for the rest. That's a decision too, and it stops the agent asking, or worse, guessing what you'd prefer.

## Tone

- Write instructions as plain statements with reasons. "Don't change `UserSerializer`'s fields (why: the mobile app parses them)" works better than "NEVER EVER touch UserSerializer!!!". Current models take instructions seriously; capitals and alarms make them apply the rule rigidly, including in cases you'd have allowed.
- Prefer stating the target over listing prohibitions. "Return errors as `{code, message}` objects" beats "don't return plain strings".
- Say each rule once, in its section. Repetition reads as extra emphasis and skews priorities.

## Context the agent needs

An agent starting a task knows the repository and the spec, nothing else. Give it:
- the goal behind the task, and who benefits (this decides ambiguous cases better than any rule)
- relevant history ("we tried caching at the CDN; it broke per-user prices")
- where to look: the key files, the pattern to imitate, the tests that cover the area
- the environment: how to run the app, the tests and the linters, and any service it can't reach

## Reusable execution-rules block

Adapt this to each spec. Delete lines that don't apply, and fill in the specifics; generic rules carry less weight than concrete ones.

```markdown
## Execution rules

Scope
- Modify only: <paths>. Other files may be read freely.
- No new dependencies without asking (why: each one needs a license and security review).
- These interfaces must not change: <list> (why: <consumers>).

Making decisions
- You may decide alone, using the default given: <naming of internal helpers; file layout inside <dir>; ...>.
- If a requirement is ambiguous, pick the reading that best serves the Summary's goal, and list the choice under Deviations in your report.
- Stop and report, instead of working around, if: a referenced file or function doesn't exist; a requirement conflicts with a non-goal or constraint; meeting a requirement would mean changing a protected interface; the verification commands fail before you've changed anything.

Quality bar
- Don't modify existing tests unless a requirement says so. If one looks wrong, stop and report (why: tests encode behavior others rely on).
- New behavior gets tests that exercise the real code; mock only network, clock and randomness.
- The implementation must work for inputs beyond the examples in this spec.
- Errors: follow the error requirements; don't add catch-all handlers that hide failures.
- Leave other problems you notice as notes in the report rather than fixing them in this change.

Done
- All acceptance criteria met, and these pass: <commands>.

Report
- Summary of the change and the files touched
- Commands run, and their results
- Deviations from the spec, each with its reason
- Assumptions made, open issues, and problems noticed but not fixed
```

## Handing the spec over

- Put the spec in the repository (or paste it whole into the agent's first message). Don't rely on the agent reading a link it may not be able to open.
- If the work spans milestones, give one milestone per session, with the full spec for context and a clear "do milestone 2 only".
- Read the report against the acceptance criteria, not against the summary. Agents describe their work optimistically; the checks are the ground truth.

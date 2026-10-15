# Requirement patterns

How to write requirements and acceptance criteria that mean one thing. The sources are at the end.

## Contents

1. What a good requirement is
2. EARS sentence patterns
3. Requirement keywords
4. Acceptance criteria formats
5. Vague to precise
6. Before and after
7. Examples in specs
8. Rationale lines
9. Sources

## 1. What a good requirement is

Requirements-engineering standards (ISO/IEC/IEEE 29148) list the qualities; in practice they come down to these questions:

| Quality | Ask |
|---|---|
| Unambiguous | Can it be read two ways? |
| Verifiable | What observation proves it's met? |
| Singular | Does it say one thing? Split anything joined by "and" that could pass or fail separately. |
| Feasible | Can it be built within the stated constraints? |
| Consistent | Does it contradict another requirement, a non-goal or a constraint? |
| Necessary | Would anyone miss it? If not, cut it: every extra requirement costs attention. |
| Implementation-free (mostly) | Does it say *what*, leaving *how* open, unless the how is itself a decision you've made on purpose? |
| Traceable | Does it have an ID, and is it covered by an acceptance criterion? |

## 2. EARS sentence patterns

EARS (Easy Approach to Requirements Syntax) gives a fixed shape for each kind of requirement. The shape forces you to name the trigger and the response, which is where vagueness usually hides.

| Pattern | Shape | Example |
|---|---|---|
| Ubiquitous (always true) | The `<system>` MUST `<response>`. | The export MUST write UTF-8 without a byte-order mark. |
| Event-driven | When `<trigger>`, the `<system>` MUST `<response>`. | When a payment succeeds, the order service MUST send the receipt email within 60 seconds. |
| State-driven | While `<state>`, the `<system>` MUST `<response>`. | While the account is suspended, the API MUST reject write requests with 403 `account_suspended`. |
| Unwanted behavior | If `<condition>`, then the `<system>` MUST `<response>`. | If the upload exceeds 100 MB, then the client MUST stop before sending and show "Files must be 100 MB or smaller." |
| Optional feature | Where `<feature is present>`, the `<system>` MUST `<response>`. | Where SSO is enabled for the workspace, the login page MUST hide the password form. |
| Complex | Combinations of the above. | While offline, when the user saves a draft, the app MUST store it locally and sync it within 30 seconds of reconnecting. |

Use "If ... then" for every error and edge case. Most missing behavior in specs is unwanted behavior nobody wrote down.

## 3. Requirement keywords

- **MUST / MUST NOT**: required. Failing one fails acceptance.
- **SHOULD / SHOULD NOT**: expected, with stated exceptions. Write the exception in the same sentence ("SHOULD paginate at 50 items, unless the client sends `limit`"). If you can't name an exception, it's a MUST.
- **MAY**: genuinely optional. Use it rarely; often "executor's choice" in the constraints section is clearer.
- Use capitals for the keyword meaning, and avoid the lowercase words in requirement text. "The page should load quickly" is a wish, not a requirement.
- Put the keyword preamble (templates.md, section 6) at the top of the spec, so the meaning isn't left to the reader.

Don't use "will", "shall" and "must" interchangeably in one document. Readers assume different words mean different strengths.

## 4. Acceptance criteria formats

**Given / When / Then**, for behavior:

```
AC3 (R4). Given a user with email ana@example.com exists,
          when a signup request uses ANA@example.com,
          then the response is 409 with code "email_taken"
          and no new user row exists.
```

Note the specifics: the case variant tests case-insensitive matching, and the last clause checks for the absence of a side effect.

**Checklist**, for structural or non-behavioral criteria:

```
- [ ] `grep -rn "legacy_client" src/` returns no matches.
- [ ] `npm run typecheck` exits 0.
- [ ] p95 latency of GET /items under the k6 script in perf/items.js is below 200 ms.
```

Rules:
- Each criterion is checkable by a command, a test or a specific manual step, by someone who didn't write the code.
- Each one names the requirement(s) it covers, and every requirement has at least one.
- Include at least one **regression** criterion: something that worked before and must still work.
- Include **negative** criteria where a side effect would be harmful: no email sent, no row written, no log line containing the token.

## 5. Vague to precise

| Vague | Ask | Precise |
|---|---|---|
| fast, quickly, performant | How fast, measured how, under what load? | p95 below 200 ms at 50 requests/s on the staging profile |
| scalable | To what, and what stays constant? | Handles 10× current peak (2,000 rps) with the same p95 |
| robust, resilient, reliable | Against which failures, and what happens then? | If the payment API times out (5 s), retry twice with backoff, then mark the order `payment_pending` |
| gracefully handle errors | Which errors, and what does the user see? | List each error with status, code and message |
| user-friendly, intuitive, clean | What can the user do, in what steps? | Name the behaviors: inline validation, keyboard shortcuts, the empty state's text |
| secure | Against what threat, by what rule? | Only workspace admins can call it (403 otherwise); tokens never appear in logs |
| large, many, a lot | What number? | Up to 100 MB; up to 10,000 rows |
| support X | Read, write, both? All versions? Which fields? | Import CSV (RFC 4180, UTF-8 or UTF-16 with BOM), columns as listed |
| appropriate, reasonable, sensible, proper | Says who? | State the rule the word is hiding |
| as needed, if necessary, where possible | Who decides, by what test? | State the condition, or make it a MUST |
| etc., and so on | What else, exactly? | Finish the list, or write "only the items listed" |
| minimal, small | Minimal by what measure? | "Changes limited to `src/auth/`; no schema changes" |
| real-time, instant | Within what latency? | Visible to other users within 2 s |
| up to date | How stale is acceptable? | Data at most 5 minutes old |
| improve, optimize, enhance | From what to what? | From 1.8 s to under 0.8 s median |
| validate the input | Against which rules, and what on failure? | Field rules table plus error responses |
| log errors | Where, at what level, with which fields, without what? | Error level, with request ID and user ID, never the request body |
| handle edge cases | Which ones? | List them (edge-cases.md) |
| similar to X, like Y | In which respects? | Name the properties to copy and the ones not to |
| ideally, try to, consider | Is it required? | MUST, SHOULD with exception, or delete |
| TBD, TODO | Who decides, and by when? | Open question with an owner and a default |

## 6. Before and after

**Before:**
> The export feature should be fast and support large files. It should handle errors gracefully and be secure. Users can choose CSV or Excel.

**After:**
> - R1. The table view MUST export the current filtered table to CSV (RFC 4180, UTF-8, comma separator, header row).
> - R2. When the table has up to 100,000 rows, the export MUST finish within 10 s (p95, production data sizes).
> - R3. If the table exceeds 100,000 rows, then the export MUST run as a background job and email a download link that expires after 24 hours. (why: the request would time out at 30 s)
> - R4. If the export job fails, then the user MUST receive an email saying "Your export failed. Try again, or contact support with reference {job_id}." and the failure MUST be logged at error level with the job ID.
> - R5. Only users who can view the table MAY export it; others get 403 `forbidden`. Download links MUST be single-user (signed for the requesting user).
> - Non-goal: Excel format (CSV opens in Excel; native .xlsx is a separate request).

What changed: the choice between CSV and Excel became a decision with a reason; every adjective became a number or a behavior; errors got exact behavior; "secure" became two rules.

## 7. Examples in specs

- Label each example **normative** (output must match exactly) or **illustrative** (shows the shape; values will differ). Without the label, executors either copy illustrative values into code or ignore a format you needed exactly.
- Make examples realistic and specific: real-looking names, edge-ish values (an apostrophe in a name, a non-ASCII character, a zero amount).
- Include at least one failure example per interface: the bad input and the exact error.
- Don't make the only example the easy case. Executors, human and AI, build to the example.

## 8. Rationale lines

Add `(why: ...)` after any requirement whose reason isn't obvious from the requirement itself. One clause, not a paragraph.

- "MUST NOT rename the `status` column (why: the nightly finance export reads it by name)."
- "MUST use the existing `RetryPolicy` class (why: retries are metered per tenant there)."

A rule with its reason lets the executor do the right thing in cases the rule didn't name, and makes it obvious when the rule no longer applies. It also lets reviewers challenge the reason instead of the rule.

## 9. Sources

The ideas here draw on: RFC 2119 and RFC 8174 for the requirement keywords; the EARS method (Mavin, Wilkinson, Harwood and Novak, "Easy Approach to Requirements Syntax", IEEE RE 2009); ISO/IEC/IEEE 29148:2018 for the qualities of good requirements; the Given/When/Then form from behavior-driven development; and Anthropic's published prompt-engineering guidance on being explicit, giving reasons, and avoiding emphatic over-instruction. The wording and examples are our own.

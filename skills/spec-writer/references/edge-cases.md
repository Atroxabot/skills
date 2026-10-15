# Edge-case checklist

Walk this list for every input, stored object and external dependency in the spec. For each item that applies, write the behavior as a requirement (usually "If ..., then ... MUST ..."). For each item you deliberately skip, write one line saying what happens instead, so the executor can tell a decision from an oversight.

You won't need most items for any one spec. The point of the list is that the one you need is the one nobody thought of.

## Inputs

- Empty: empty string, empty list, missing field, `null`, whitespace only.
- Boundaries: zero, negative, exactly at the limit, one past the limit, maximum integer, very long strings.
- Format: wrong type, malformed (invalid JSON, a CSV with a ragged row), wrong encoding, a BOM, mixed line endings.
- Text: Unicode (accents, CJK, emoji, right-to-left), combining characters, case variants (`Ana` vs `ana`), leading or trailing spaces, look-alike characters.
- Duplicates: the same item twice in one request; an item that already exists.
- Injection: input that reaches SQL, shell, HTML, file paths, templates, logs or a prompt.
- Files: zero bytes, huge, wrong extension for the content, password-protected, corrupt, a name with path separators.

## State

- First use: no data yet (the empty state, with its exact text).
- Missing references: the parent was deleted, the ID doesn't exist, it belongs to someone else.
- Lifecycle: draft, archived, suspended, soft-deleted, expired. Which actions are allowed in each?
- Stale data: the client acts on a version that has since changed.
- Partial setup: a feature flag on for some users, a migration half applied.

## Concurrency and ordering

- Two users editing the same thing (last write wins, a conflict error, or a merge?).
- The same request sent twice (double click, client retry): is it idempotent?
- Events arriving out of order or late.
- A long job running while its input changes.
- Race between a check and the action ("is the name free?" and then "create").

## Failure of dependencies

- Timeouts: how long to wait, then what.
- Retries: how many, with what backoff, and what's safe to retry.
- Partial failure: step 2 of 3 failed. What is rolled back, what's left, and how is it reported?
- The dependency returns nonsense: an unexpected status, an empty body, the wrong schema.
- Rate limited (429): back off and how much.
- Down for an extended time: queue, degrade, or fail? What does the user see?

## Permissions and identity

- Not signed in; signed in without permission; permission revoked mid-session.
- Acting on another tenant's or user's data by changing an ID.
- Admin and service accounts: same rules or different?
- Audit: which actions must be recorded, with what fields?

## Time

- Time zones: stored in UTC? Displayed in whose zone?
- Daylight saving: the hour that happens twice, the hour that doesn't happen, schedules across the change.
- Date boundaries: month end, leap day, year end, "end of day" in which zone.
- Clock differences between servers; expired tokens; anything scheduled in the past.

## Scale and limits

- The largest realistic dataset, and 10× that.
- Pagination: page size, maximum, stable sort order with a tie-breaker.
- Memory: streaming vs loading everything.
- Quotas: what happens when a user hits one.

## Money and numbers

- Rounding rule and where it's applied; currencies with 0 or 3 decimal places.
- Floats never used for money.
- Negative amounts, refunds, partial refunds.
- Unit consistency (cents vs dollars, ms vs s, bytes vs MB).

## Localization

- Translated strings and their length (German runs about 30% longer).
- Number, date and currency formats by locale.
- Pluralization rules.
- Right-to-left layout.

## Operations

- Logging: what's logged, at what level, and what must never be logged (secrets, tokens, personal data).
- Metrics and alerts the change needs.
- Configuration: new settings, their defaults, and what happens when one is missing.
- Deploy order: can old and new versions run side by side during the rollout?
- Rollback: can this change be undone without data loss?
- Backfills: for existing records, what value do new fields get?

## Compatibility

- Existing API clients, mobile apps on old versions, saved links, webhooks and integrations.
- Data written by the old version read by the new one, and the reverse during rollout.
- Browser, OS and device support.

## Accessibility

- Keyboard-only use, focus order, screen-reader labels, color contrast, motion, error messages tied to their fields.
